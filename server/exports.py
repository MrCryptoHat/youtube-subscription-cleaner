"""
Unsubscribe export formats — three takeaways the user can act on, none of which
depend on YouTube's current markup (unlike the optional Playwright script):

  * unsubscribe.json    — flat machine-readable list, easy to script against
  * unsubscribe-brief.md — a self-contained brief for the user's AI agent
  * unsubscribe.html    — a standalone page to do it by hand, with a saved
                          progress tracker

All three are built from the decisions payload (see app._decisions_payload).
"""
from __future__ import annotations

import json
import re

# Only ever link to YouTube itself. Anything else (or a smuggled scheme like
# javascript:) is rebuilt from the channel id.
_SAFE_URL_RE = re.compile(r"^https://(www\.|m\.)?youtube\.com/", re.IGNORECASE)


def _safe_url(url: str | None, cid: str) -> str:
    if url and _SAFE_URL_RE.match(url):
        return url
    return f"https://www.youtube.com/channel/{cid}"


def _script_safe_json(obj) -> str:
    """JSON serialised for embedding inside a <script> element. json.dumps does
    not escape '</script>' (or '<!--'), so a channel title could otherwise break
    out of the script context — escape every <, > and & to \\uXXXX."""
    return (json.dumps(obj, ensure_ascii=False)
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))


def _channels(payload: dict) -> list[dict]:
    """The to_remove list, trimmed to the fields anyone unsubscribing needs."""
    out = []
    for e in payload.get("to_remove", []):
        out.append({
            "channel_id": e["channel_id"],
            "title": e.get("title", ""),
            "handle": e.get("handle"),
            "url": _safe_url(e.get("url"), e["channel_id"]),
        })
    return out


# ─── 1. machine-readable JSON ────────────────────────────────────────────────

def build_unsubscribe_json(payload: dict) -> dict:
    chans = _channels(payload)
    return {
        "generated_at": payload.get("exported_at"),
        "action": "unsubscribe",
        "note": "Unsubscribe the authenticated YouTube account from every channel below.",
        "count": len(chans),
        "channels": chans,
    }


# ─── 2. brief for an AI agent ────────────────────────────────────────────────

_BRIEF = """\
# Task: unsubscribe from {count} YouTube channels

A user sorted their YouTube subscriptions and chose to unsubscribe from the
channels listed below. Unsubscribe their signed-in account from each one.

Generated: {generated}

## Rules (read first — these are safety boundaries)
- ONLY unsubscribe. Never subscribe to anything, never delete videos/playlists.
- If you cannot positively confirm the account is currently subscribed to a
  channel, SKIP it — do not guess.
- Be resumable: record which channels you've done so a re-run skips them.
- Be gentle: small random delays between channels. If YouTube shows a CAPTCHA,
  a "confirm it's you", or any rate-limit, STOP and tell the user instead of
  hammering. Hundreds of rapid actions can trip abuse detection.
- Report a summary at the end: done / skipped / failed (with reasons).

## Pick the path you actually have access to

### Path A — browser automation (Playwright, Puppeteer, computer-use, etc.)
For each channel URL:
1. Open `{{url}}?hl=en` (forcing English makes button labels predictable).
2. Find the channel-header subscribe button. Only proceed if its text/aria-label
   clearly means "Subscribed" (e.g. "Subscribed", "Вы подписаны"). If it says
   "Subscribe", you're already unsubscribed — skip. If unsure — skip.
3. Click it to open the menu; the LAST menu item is "Unsubscribe" (stable across
   languages). Click it.
4. A confirm dialog appears — click the affirmative button (`#confirm-button`),
   never Cancel.
5. Verify the header button now says "Subscribe"; log the result.

### Path B — YouTube Data API v3 (most robust, but quota-limited)
1. OAuth with scope `https://www.googleapis.com/auth/youtube`.
2. `subscriptions.list` (mine=true, part=snippet, paginate) → build a map from
   `snippet.resourceId.channelId` → the subscription's own `id`.
3. For each target channel_id, `subscriptions.delete?id={{subscriptionId}}`.
4. QUOTA: `subscriptions.delete` costs 50 units; the default daily quota is
   10,000 units (~200 deletions/day). For a list this size, spread the run over
   multiple days or request a quota increase. `list` is cheap (1 unit/page).

## Channels to unsubscribe ({count})

{list}

A machine-readable version of this list is in `unsubscribe.json` (fields:
channel_id, title, handle, url).
"""


def build_agent_brief(payload: dict) -> str:
    chans = _channels(payload)
    lines = []
    for i, c in enumerate(chans, 1):
        handle = f" ({c['handle']})" if c.get("handle") else ""
        lines.append(f"{i}. {c['title']}{handle} — {c['url']}  `{c['channel_id']}`")
    return _BRIEF.format(
        count=len(chans),
        generated=payload.get("exported_at") or "",
        list="\n".join(lines) if lines else "_(none)_",
    )


# ─── 3. standalone manual-unsubscribe page ───────────────────────────────────

_HTML_STRINGS = {
    "ru": {
        "title": "Отписаться от каналов",
        "lead": "Открой канал, нажми на YouTube «Вы подписаны» → «Отписаться», вернись сюда и отметь галочкой. Прогресс сохраняется в этом браузере — можно закрыть и продолжить позже.",
        "progress": "Готово",
        "open": "Открыть ↗",
        "search": "Поиск каналов…",
        "hide_done": "Скрыть отмеченные",
        "automark": "Отмечать при открытии",
        "automark_hint": "Открыл ссылку — канал сразу помечен отписанным. Галочку всегда можно снять.",
        "all_done": "Готово — все отмечены! 🎉",
        "reset": "Сбросить отметки",
    },
    "en": {
        "title": "Unsubscribe from channels",
        "lead": "Open a channel, on YouTube click “Subscribed” → “Unsubscribe”, come back here and tick it off. Progress is saved in this browser — you can close and resume later.",
        "progress": "Done",
        "open": "Open ↗",
        "search": "Search channels…",
        "hide_done": "Hide ticked",
        "automark": "Tick off when opened",
        "automark_hint": "Opening a channel marks it unsubscribed automatically. You can always untick it.",
        "all_done": "All ticked — done! \U0001F389",
        "reset": "Reset ticks",
    },
}


def build_unsubscribe_html(payload: dict, lang: str = "en") -> str:
    s = _HTML_STRINGS.get(lang, _HTML_STRINGS["en"])
    chans = _channels(payload)
    # Channel titles come from Takeout / scraped pages — hostile until proven
    # otherwise. _script_safe_json prevents a </script> breakout; the list itself
    # is rendered client-side via textContent.
    data_json = _script_safe_json(chans)
    strings_json = _script_safe_json(s)
    return _HTML_PAGE.replace("/*__DATA__*/", data_json).replace("/*__STR__*/", strings_json).replace("__LANG__", lang)


_HTML_PAGE = """\
<!doctype html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Unsubscribe</title>
<style>
  :root { --bg:#0a0908; --card:#16130f; --line:rgba(232,215,188,0.12); --line2:rgba(232,215,188,0.2);
          --fg:#efe7d8; --dim:#b8ad99; --faint:#756c5c; --ember:#ff7a3d; --green:#7ec77a; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--fg); font:15px/1.5 "Space Grotesk",system-ui,sans-serif;
         padding:32px 20px 80px; }
  .wrap { max-width:760px; margin:0 auto; }
  h1 { font-size:24px; font-weight:700; margin-bottom:8px; }
  .lead { color:var(--dim); font-size:14px; margin-bottom:20px; max-width:620px; }
  .bar { position:sticky; top:0; background:linear-gradient(180deg,var(--bg) 75%,transparent); padding:12px 0 14px; z-index:5; }
  .bar-row { display:flex; align-items:center; gap:14px; flex-wrap:wrap; }
  .count { font:600 14px "JetBrains Mono",monospace; color:var(--fg); white-space:nowrap; }
  .count b { color:var(--ember); }
  .track { flex:1; min-width:140px; height:8px; background:var(--card); border-radius:20px; overflow:hidden; border:1px solid var(--line); }
  .fill { height:100%; width:0; background:var(--ember); transition:width .3s; }
  input[type=search] { flex:1; min-width:160px; background:var(--card); border:1px solid var(--line2); border-radius:10px;
                       color:var(--fg); padding:9px 13px; font-size:13px; font-family:inherit; }
  input[type=search]:focus { outline:none; border-color:var(--ember); }
  .opts { display:flex; gap:16px; align-items:center; margin-top:10px; font-size:13px; color:var(--dim); }
  .opts label { display:flex; gap:6px; align-items:center; cursor:pointer; }
  .btn { background:transparent; border:1px solid var(--line2); border-radius:9px; color:var(--dim);
         padding:6px 11px; font:inherit; font-size:12px; cursor:pointer; }
  .btn:hover { color:var(--fg); border-color:var(--faint); }
  ul { list-style:none; margin-top:8px; }
  li { display:flex; align-items:center; gap:14px; padding:11px 6px; border-bottom:1px solid var(--line); }
  li.done { opacity:.45; }
  li.done .title { text-decoration:line-through; }
  .cb { width:22px; height:22px; flex-shrink:0; accent-color:var(--ember); cursor:pointer; }
  .meta { min-width:0; flex:1; }
  .title { font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .sub { font:11px "JetBrains Mono",monospace; color:var(--faint); margin-top:2px; }
  a.open { flex-shrink:0; color:var(--ember); text-decoration:none; border:1px solid rgba(255,122,61,.4);
           border-radius:9px; padding:7px 12px; font-size:13px; }
  a.open:hover { background:rgba(255,122,61,.1); }
  .alldone { color:var(--green); font-weight:600; padding:14px 0; }
  .empty { color:var(--faint); padding:24px 0; }
</style>
</head>
<body>
<div class="wrap">
  <h1 id="h1"></h1>
  <p class="lead" id="lead"></p>
  <div class="bar">
    <div class="bar-row">
      <span class="count"><b id="ndone">0</b> / <span id="ntotal">0</span> <span id="lbldone"></span></span>
      <div class="track"><div class="fill" id="fill"></div></div>
    </div>
    <div class="bar-row" style="margin-top:10px">
      <input type="search" id="q">
      <label class="opts" style="margin:0"><input type="checkbox" id="automark"> <span id="lblauto"></span></label>
      <label class="opts" style="margin:0"><input type="checkbox" id="hide"> <span id="lblhide"></span></label>
      <button class="btn" id="reset"></button>
    </div>
    <div class="alldone" id="alldone" hidden></div>
  </div>
  <ul id="list"></ul>
</div>
<script>
const DATA = /*__DATA__*/;
const STR = /*__STR__*/;
const KEY = "yt-unsub-done";
let done = {};
try { done = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { done = {}; }

document.getElementById("h1").textContent = STR.title;
document.getElementById("lead").textContent = STR.lead;
document.getElementById("lbldone").textContent = STR.progress;
document.getElementById("lblhide").textContent = STR.hide_done;
document.getElementById("reset").textContent = STR.reset;
document.getElementById("q").placeholder = STR.search;
document.getElementById("alldone").textContent = STR.all_done;
document.getElementById("ntotal").textContent = DATA.length;

const listEl = document.getElementById("list");
const qEl = document.getElementById("q");
const hideEl = document.getElementById("hide");
const autoEl = document.getElementById("automark");
document.getElementById("lblauto").textContent = STR.automark;
autoEl.closest("label").title = STR.automark_hint;
autoEl.checked = localStorage.getItem("yt-unsub-automark") !== "0";  // default on
autoEl.addEventListener("change", () => localStorage.setItem("yt-unsub-automark", autoEl.checked ? "1" : "0"));

function save() { localStorage.setItem(KEY, JSON.stringify(done)); }
function doneCount() { return DATA.filter(c => done[c.channel_id]).length; }

function render() {
  const q = qEl.value.trim().toLowerCase();
  const hideDone = hideEl.checked;
  listEl.innerHTML = "";
  let shown = 0;
  for (const c of DATA) {
    const isDone = !!done[c.channel_id];
    if (hideDone && isDone) continue;
    if (q && !(c.title.toLowerCase().includes(q) || (c.handle || "").toLowerCase().includes(q))) continue;
    shown++;
    const li = document.createElement("li");
    if (isDone) li.className = "done";
    const cb = document.createElement("input");
    cb.type = "checkbox"; cb.className = "cb"; cb.checked = isDone;
    cb.addEventListener("change", () => {
      if (cb.checked) done[c.channel_id] = true; else delete done[c.channel_id];
      save(); update(); if (hideEl.checked) render();
      li.classList.toggle("done", cb.checked);
    });
    const meta = document.createElement("div"); meta.className = "meta";
    const title = document.createElement("div"); title.className = "title"; title.textContent = c.title || c.channel_id;
    const sub = document.createElement("div"); sub.className = "sub"; sub.textContent = c.handle || c.channel_id;
    meta.appendChild(title); meta.appendChild(sub);
    const a = document.createElement("a"); a.className = "open"; a.href = c.url; a.target = "_blank";
    a.rel = "noopener"; a.textContent = STR.open;
    // Opening a channel auto-ticks it (when the toggle is on) — open, unsubscribe
    // on YouTube, done. The link still opens normally; the tick is a side effect.
    a.addEventListener("click", () => {
      if (!autoEl.checked || done[c.channel_id]) return;
      done[c.channel_id] = true; save(); update();
      cb.checked = true; li.classList.add("done");
      if (hideEl.checked) setTimeout(render, 60);
    });
    li.appendChild(cb); li.appendChild(meta); li.appendChild(a);
    listEl.appendChild(li);
  }
  if (!shown) { const d = document.createElement("div"); d.className = "empty"; d.textContent = "—"; listEl.appendChild(d); }
}
function update() {
  const n = doneCount();
  document.getElementById("ndone").textContent = n;
  document.getElementById("fill").style.width = (DATA.length ? (n / DATA.length * 100) : 0) + "%";
  document.getElementById("alldone").hidden = !(DATA.length && n === DATA.length);
}
qEl.addEventListener("input", render);
hideEl.addEventListener("change", render);
document.getElementById("reset").addEventListener("click", () => { done = {}; save(); update(); render(); });
update(); render();
</script>
</body>
</html>
"""
