"""
Language-agnostic Google Takeout ingestion.

Takeout localises both filenames and CSV headers, so nothing here matches on a
fixed name or column title. Instead we sniff content:

  - subscriptions  : a CSV whose rows contain a youtube.com/channel/UC… URL
  - watch history  : a JSON array of activity objects (preferred), or the
                     MyActivity HTML export (fallback — counts are reliable,
                     timestamps are best-effort because Takeout localises them)

Accepts a whole `.zip` or the individual files. Everything operates on bytes so
the web server can hand us an uploaded body directly.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

from .zones import now_utc

CHANNEL_ID_RE = re.compile(r"(UC[\w-]{22})")
CHANNEL_URL_RE = re.compile(r"youtube\.com/channel/(UC[\w-]{22})")

# Channel URLs end up in clickable links across the app and its exports. Only
# trust an https://youtube.com/... URL from an imported file; anything else
# (including a smuggled javascript: scheme) is rebuilt from the channel id.
SAFE_URL_RE = re.compile(r"^https://(www\.|m\.)?youtube\.com/", re.IGNORECASE)


def safe_channel_url(url: str | None, cid: str) -> str:
    if url and SAFE_URL_RE.match(url.strip()):
        return url.strip()
    return f"https://www.youtube.com/channel/{cid}"


# ─── File sniffing ──────────────────────────────────────────────────────────

def looks_like_subscriptions_csv(text: str) -> bool:
    head = text[:5000]
    return ("youtube.com/channel/" in head) and ("," in head)


def looks_like_watch_json(data) -> bool:
    return (
        isinstance(data, list)
        and len(data) > 0
        and isinstance(data[0], dict)
        and ("titleUrl" in data[0] or "subtitles" in data[0] or "title" in data[0])
    )


# Buckets in this app's own `decisions.json` export, mapped to the decision the
# user made for the channels inside them.
DECISION_BUCKETS = (("to_remove", "remove"), ("to_keep", "keep"), ("pending", "pending"))


def looks_like_decisions_export(data) -> bool:
    """True for *this app's own* decisions.json export — a dict carrying at least
    one of the to_remove / to_keep / pending lists. Lets us round-trip an export
    back into a full restore instead of mis-sniffing it as a one-row CSV."""
    return isinstance(data, dict) and any(
        isinstance(data.get(bucket), list) for bucket, _ in DECISION_BUCKETS
    )


def looks_like_watch_html(text: str) -> bool:
    head = text[:20000]
    return ("/channel/" in head or "watch?v=" in head) and ("mdl-" in head or "content-cell" in head or "<html" in head.lower())


# ─── Subscriptions ──────────────────────────────────────────────────────────

def parse_subscriptions_csv(text: str) -> list[dict]:
    """Return [{channel_id, url, title}]. Column order/header language agnostic:
    we locate the id, url and title cells by their shape, not their position."""
    out: list[dict] = []
    seen: set[str] = set()
    reader = csv.reader(io.StringIO(text))
    for i, row in enumerate(reader):
        if not row:
            continue
        joined = ",".join(row)
        m = CHANNEL_URL_RE.search(joined) or CHANNEL_ID_RE.search(joined)
        if not m:
            continue  # header row or junk
        cid = m.group(1)
        if cid in seen:
            continue
        seen.add(cid)
        url = safe_channel_url(next((c.strip() for c in row if "youtube.com/" in c), None), cid)
        # title = the cell that is neither the id nor a url
        title = ""
        for c in row:
            cs = c.strip()
            if cs and cs != cid and "youtube.com/" not in cs and not CHANNEL_ID_RE.fullmatch(cs):
                title = cs
                break
        out.append({"channel_id": cid, "url": url, "title": title})
    return out


# ─── Decisions export (this app's own round-trip) ────────────────────────────

def parse_decisions_export(data: dict) -> list[dict]:
    """Restore the app's own decisions.json. Returns one entry per channel:
    {channel_id, url, title, zone, decision} — `decision` (remove/keep/pending)
    comes from which bucket the channel sat in, `zone` is carried verbatim so the
    restored library keeps the colours the user left it with."""
    out: list[dict] = []
    seen: set[str] = set()
    for bucket, decision in DECISION_BUCKETS:
        for entry in data.get(bucket) or []:
            if not isinstance(entry, dict):
                continue
            raw_id = entry.get("channel_id") or ""
            m = CHANNEL_ID_RE.search(raw_id) or CHANNEL_URL_RE.search(entry.get("url", "") or "") \
                or CHANNEL_ID_RE.search(entry.get("url", "") or "")
            if not m:
                continue
            cid = m.group(1)
            if cid in seen:
                continue
            seen.add(cid)
            zone = entry.get("zone")
            out.append({
                "channel_id": cid,
                "url": safe_channel_url(entry.get("url"), cid),
                "title": entry.get("title", "") or "",
                "zone": zone if zone in ("red", "green", "yellow", "not_found") else None,
                "decision": decision,
            })
    return out


# ─── Watch history (JSON) ───────────────────────────────────────────────────

def parse_watch_history_json(data: list) -> list[tuple[str, datetime | None]]:
    events: list[tuple[str, datetime | None]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        cid = None
        subs = entry.get("subtitles") or []
        if subs and isinstance(subs, list) and isinstance(subs[0], dict):
            m = CHANNEL_URL_RE.search(subs[0].get("url", "") or "")
            if m:
                cid = m.group(1)
        if not cid:
            continue  # removed/private video — no channel
        t = None
        ts = entry.get("time")
        if ts:
            try:
                t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                t = None
        events.append((cid, t))
    return events


# ─── Watch history (HTML fallback) ──────────────────────────────────────────

_HTML_DATE_FORMATS = [
    "%b %d, %Y, %I:%M:%S %p",       # Jun 8, 2026, 12:05:59 PM
    "%b %d, %Y, %H:%M:%S",          # Jun 8, 2026, 13:05:59
    "%d %b %Y, %H:%M:%S",           # 8 Jun 2026, 13:05:59
    "%Y-%m-%d %H:%M:%S",
]


def _try_parse_html_date(text: str) -> datetime | None:
    """Takeout HTML timestamps are localised; parse the formats we can, give up
    gracefully otherwise (the event still counts, it just has no date)."""
    cleaned = re.sub(r"\s+(GMT|UTC|[A-Z]{2,4})$", "", text.strip())
    cleaned = re.sub(r" ", " ", cleaned)  # narrow no-break space Google uses
    for fmt in _HTML_DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


class _WatchHistoryHTMLParser(HTMLParser):
    """Walks Takeout MyActivity HTML cells, capturing (channel_id, timestamp)."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[str, datetime | None]] = []
        self._cur_channel: str | None = None
        self._capture_text = False
        self._text_buf: list[str] = []
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = d.get("class", "")
        if tag == "div" and "content-cell" in cls and "mdl-typography--text-right" not in cls:
            # the main activity cell — reset
            self._in_cell = True
            self._cur_channel = None
            self._text_buf = []
        if tag == "a" and self._in_cell:
            href = d.get("href", "")
            m = CHANNEL_URL_RE.search(href)
            if m:
                self._cur_channel = m.group(1)
        if self._in_cell:
            self._capture_text = True

    def handle_data(self, data):
        if self._capture_text and self._in_cell:
            self._text_buf.append(data)

    def handle_endtag(self, tag):
        if tag == "div" and self._in_cell:
            if self._cur_channel:
                # find a date-looking fragment in the captured text
                blob = " ".join(self._text_buf)
                ts = None
                m = re.search(r"[A-Za-z]{3,}\.?\s+\d{1,2},?\s+\d{4}.*", blob) or \
                    re.search(r"\d{1,2}\s+[A-Za-z]{3,}\.?\s+\d{4}.*", blob)
                if m:
                    ts = _try_parse_html_date(m.group(0))
                self.events.append((self._cur_channel, ts))
            self._in_cell = False
            self._capture_text = False


def parse_watch_history_html(text: str) -> list[tuple[str, datetime | None]]:
    p = _WatchHistoryHTMLParser()
    try:
        p.feed(text)
    except Exception:
        # fall back to a pure-regex channel sweep (counts only, no dates)
        return [(m.group(1), None) for m in CHANNEL_URL_RE.finditer(text)]
    if not p.events:
        return [(m.group(1), None) for m in CHANNEL_URL_RE.finditer(text)]
    return p.events


# ─── Orchestration ──────────────────────────────────────────────────────────

def _decode(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def classify_file(name: str, data: bytes) -> tuple[str, object] | None:
    """Return ('subscriptions', rows) | ('watch', events) | None."""
    lower = name.lower()
    # JSON?
    if lower.endswith(".json") or data[:1] in (b"[", b"{"):
        try:
            parsed = json.loads(_decode(data))
            if looks_like_decisions_export(parsed):
                return "decisions", parse_decisions_export(parsed)
            if looks_like_watch_json(parsed):
                return "watch", parse_watch_history_json(parsed)
        except (json.JSONDecodeError, ValueError):
            pass
    # CSV?
    if lower.endswith(".csv"):
        text = _decode(data)
        if looks_like_subscriptions_csv(text):
            return "subscriptions", parse_subscriptions_csv(text)
    # HTML?
    if lower.endswith((".html", ".htm")):
        text = _decode(data)
        if looks_like_watch_html(text):
            return "watch", parse_watch_history_html(text)
    # Unknown extension — sniff
    text = _decode(data[:8000])
    if looks_like_subscriptions_csv(text):
        return "subscriptions", parse_subscriptions_csv(_decode(data))
    return None


# Decompression guard rails. A full Takeout watch-history export is large but
# bounded (hundreds of MB); a zip bomb is not. Limits are deliberately generous
# so no real Takeout ever hits them.
MAX_ZIP_MEMBERS = 2_000
MAX_MEMBER_BYTES = 1_536 * 1024 * 1024       # 1.5 GB per file
MAX_TOTAL_BYTES = 4 * 1024 * 1024 * 1024     # 4 GB summed across members


def iter_files(name: str, data: bytes):
    """Yield (filename, bytes). Transparently expands a .zip, with caps on
    member count and decompressed size (zip-bomb protection)."""
    if name.lower().endswith(".zip") or data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                total = 0
                members = 0
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    if info.filename.lower().rsplit(".", 1)[-1] not in ("csv", "json", "html", "htm"):
                        continue
                    members += 1
                    if members > MAX_ZIP_MEMBERS:
                        return
                    if info.file_size > MAX_MEMBER_BYTES:
                        continue  # declared size already over the cap
                    # Read with a hard ceiling — the header's file_size can lie.
                    with zf.open(info) as fh:
                        content = fh.read(MAX_MEMBER_BYTES + 1)
                    if len(content) > MAX_MEMBER_BYTES:
                        continue
                    total += len(content)
                    if total > MAX_TOTAL_BYTES:
                        return
                    yield info.filename, content
            return
        except zipfile.BadZipFile:
            pass
    yield name, data


def build_library(subscriptions: list[dict], watch_events: list[tuple[str, datetime | None]]) -> dict:
    """Aggregate subscriptions + watch events into channel records."""
    now = now_utc()
    w12 = now - timedelta(days=365)
    w6 = now - timedelta(days=182)

    counts: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "w12": 0, "w6": 0, "last": None}
    )
    window_min = window_max = None
    for cid, t in watch_events:
        c = counts[cid]
        c["total"] += 1
        if t is not None:
            if t >= w12:
                c["w12"] += 1
            if t >= w6:
                c["w6"] += 1
            iso = t.isoformat()
            if c["last"] is None or iso > c["last"]:
                c["last"] = iso
            if window_min is None or t < window_min:
                window_min = t
            if window_max is None or t > window_max:
                window_max = t

    channels: list[dict] = []
    for s in subscriptions:
        cid = s["channel_id"]
        c = counts.get(cid, {"total": 0, "w12": 0, "w6": 0, "last": None})
        rec = {
            "channel_id": cid,
            "url": s.get("url") or f"https://www.youtube.com/channel/{cid}",
            "title_from_subs": s.get("title", ""),
            "title": s.get("title", ""),
            "watch_total": c["total"],
            "watch_12mo": c["w12"],
            "watch_6mo": c["w6"],
            "watch_last_at": c["last"],
            "enriched": False,
        }
        # Restored from a decisions.json export: pin the zone so re-enrichment
        # refreshes the card details without recomputing (and losing) the colours
        # the user already sorted into — the export carries no watch history, so a
        # fresh compute_zone would wrongly demote every green.
        if s.get("zone_saved"):
            rec["zone_saved"] = s["zone_saved"]
        channels.append(rec)

    matched = sum(1 for ch in channels if ch["watch_total"] > 0)
    return {
        "created_at": now.isoformat(),
        "watch_window": {
            "start": window_min.isoformat() if window_min else None,
            "end": window_max.isoformat() if window_max else None,
            "total_events": len(watch_events),
            "channels_matched": matched,
        },
        "channels": channels,
    }
