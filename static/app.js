// ════════════════════════════════════════════════════════════════════════
//  Subscription Sweep — frontend
//  Flow: welcome → import Takeout → enrich → plan → swipe → review → done
// ════════════════════════════════════════════════════════════════════════

const App = {
  channels: [],
  byId: {},
  state: null,            // swipe session (null = none)
  view: "loading",
  status: null,           // last /api/status payload
  watchWindow: null,
  reviewTab: "remove",
  reviewSort: "alpha",   // alpha | subs | watched | recent
  reviewQuery: "",
  unsubQuery: "",
  busy: false,
  saveTimer: null,
  enrichPoll: null,
};

// ─── tiny utils ──────────────────────────────────────────────────────────
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

function locale() { return getLang() === "ru" ? "ru-RU" : "en-US"; }
function fmtNum(n) {
  if (n === null || n === undefined) return "?";
  if (n >= 1e9) return (n / 1e9).toFixed(1).replace(/\.0$/, "") + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(n >= 1e5 ? 0 : 1).replace(/\.0$/, "") + "K";
  return new Intl.NumberFormat(locale()).format(n);
}
function fmtRelDays(days) {
  if (days === null || days === undefined) return "—";
  if (days < 1) return t("time.today");
  if (days === 1) return t("time.yesterday");
  if (days < 30) return t("time.d_ago", { n: days });
  if (days < 365) return t("time.mo_ago", { n: Math.round(days / 30) });
  const y = days / 365;
  return t("time.y_ago", { n: y < 2 ? Math.round(y * 10) / 10 : Math.round(y) });
}
function fmtETA(count) {
  const mins = Math.max(1, Math.round((count * 2.2) / 60));
  return mins < 60 ? t("time.min", { n: mins }) : t("time.hr", { n: Math.round(mins / 60 * 10) / 10 });
}
function escapeHTML(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (m) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
}
function monthYear(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString(locale(), { month: "long", year: "numeric" });
}
function flag(cc) {
  if (!cc || cc.length !== 2) return null;
  return cc.toUpperCase().replace(/./g, (c) => String.fromCodePoint(127397 + c.charCodeAt(0)));
}

function showView(name) {
  $$(".view").forEach((v) => v.classList.remove("active"));
  const el = $(`#view-${name}`);
  if (el) el.classList.add("active");
  App.view = name;
  placeLangSwitch();
}

// Keep the language switcher in-flow inside the topbar on app screens (so it
// never floats over the buttons); fixed in the corner everywhere else.
function placeLangSwitch() {
  const ls = $(".lang-switch");
  if (!ls) return;
  if (App.view === "swipe") $("#view-swipe .session").appendChild(ls);
  else if (App.view === "review") $("#view-review .topbar").appendChild(ls);
  else if (App.view === "unsubscribe") $("#view-unsubscribe .topbar").appendChild(ls);
  else document.body.appendChild(ls);
}
function toast(msg, ms = 2200) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (el.hidden = true), ms);
}
function announce(msg) {
  const el = $("#sr-live");
  if (el) el.textContent = msg;
}

// In-style modal confirm — replaces window.confirm so prompts match the app
// instead of the browser chrome. Returns a Promise<boolean>; Esc / backdrop /
// Cancel resolve false. `danger` paints the confirm button red.
function confirmDialog({ message, title = "", ok, cancel, danger = false } = {}) {
  return new Promise((resolve) => {
    const dlg = $("#dialog-confirm");
    const titleEl = $("#confirm-title");
    titleEl.textContent = title;
    titleEl.hidden = !title;
    $("#confirm-message").textContent = message || "";
    const okBtn = $("#confirm-ok");
    const cancelBtn = $("#confirm-cancel");
    okBtn.textContent = ok || t("dialog.ok");
    cancelBtn.textContent = cancel || t("dialog.cancel");
    okBtn.classList.toggle("danger", !!danger);
    let settled = false;
    const finish = (val) => {
      if (settled) return;
      settled = true;
      okBtn.removeEventListener("click", onOk);
      cancelBtn.removeEventListener("click", onCancel);
      dlg.removeEventListener("cancel", onEsc);
      dlg.removeEventListener("click", onBackdrop);
      if (dlg.open) dlg.close();
      resolve(val);
    };
    const onOk = () => finish(true);
    const onCancel = () => finish(false);
    const onEsc = (e) => { e.preventDefault(); finish(false); };           // Esc
    const onBackdrop = (e) => { if (e.target === dlg) finish(false); };    // backdrop click
    okBtn.addEventListener("click", onOk);
    cancelBtn.addEventListener("click", onCancel);
    dlg.addEventListener("cancel", onEsc);
    dlg.addEventListener("click", onBackdrop);
    dlg.showModal();
    cancelBtn.focus();
  });
}

// ─── API ─────────────────────────────────────────────────────────────────
const api = {
  status: () => fetch("/api/status").then((r) => r.json()),
  channels: () => fetch("/api/channels").then((r) => r.json()),
  build: () => fetch("/api/library/build", { method: "POST" }).then((r) => r.json()),
  enrichStart: () => fetch("/api/enrich/start", { method: "POST" }),
  state: async () => {
    const r = await fetch("/api/state");
    return r.status === 204 ? null : r.json();
  },
  resetState: () => fetch("/api/state/reset", { method: "POST" }),
  resetAll: () => fetch("/api/reset-all", { method: "POST" }),
  upload: (file) =>
    fetch(`/api/import?name=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: file,
    }).then((r) => r.json()),
};

function saveStateNow() {
  if (!App.state) return;
  return fetch("/api/state", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(App.state),
  });
}
function saveStateDebounced(ms = 500) {
  clearTimeout(App.saveTimer);
  App.saveTimer = setTimeout(saveStateNow, ms);
}

// ════════════════════════════════════════════════════════════════════════
//  ONBOARDING
// ════════════════════════════════════════════════════════════════════════

function setupWelcome() {
  $("#btn-welcome-next").onclick = () => showView("import");
}

function setupImport() {
  const dz = $("#dropzone");
  const input = $("#file-input");
  $("#dz-browse").onclick = () => input.click();
  dz.addEventListener("click", (e) => {
    if (e.target.closest("button") || e.target.closest("a")) return;
    input.click();
  });
  input.addEventListener("change", () => handleFiles([...input.files]));

  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("dragover"); }));
  dz.addEventListener("drop", (e) => handleFiles([...e.dataTransfer.files]));

  $("#btn-build").onclick = buildLibrary;
}

async function handleFiles(files) {
  if (!files.length) return;
  $("#dz-inner").hidden = true;
  $("#dz-progress").hidden = false;
  let last = null;
  for (const f of files) {
    $("#dz-progress-text").textContent = t("import.reading", { name: f.name });
    try {
      last = await api.upload(f);
    } catch (e) {
      toast(t("toast.cant_read"));
    }
  }
  $("#dz-progress").hidden = true;
  $("#dz-inner").hidden = false;
  if (!last) return;
  App.lastStaging = last.staging;
  renderDetected();
}

function renderDetected() {
  const s = App.lastStaging;
  if (!s) return;
  $("#detected").hidden = false;
  const warn = $("#det-warn");
  const buildLabel = $("#btn-build").querySelector("[data-i18n]");

  // Re-importing this app's own decisions.json — a full restore, not a Takeout load.
  if (s.restore) {
    $("#det-subs").textContent = s.restore.toLocaleString(locale());
    $("#det-subs-label").textContent = t("import.det_restore");
    $("#det-watch-wrap").hidden = true;
    warn.hidden = false;
    warn.textContent = t("import.restore_note");
    if (buildLabel) buildLabel.textContent = t("import.restore_build");
    $("#btn-build").disabled = false;
    return;
  }
  $("#det-watch-wrap").hidden = false;
  $("#det-subs-label").textContent = t("import.det_subs");
  if (buildLabel) buildLabel.textContent = t("import.build");
  $("#det-subs").textContent = s.subscriptions.toLocaleString(locale());
  $("#det-watch").textContent = s.watch_events.toLocaleString(locale());
  if (s.subscriptions === 0) {
    warn.hidden = false; warn.textContent = t("import.warn_no_subs");
    $("#btn-build").disabled = true;
  } else if (s.watch_events === 0) {
    warn.hidden = false; warn.textContent = t("import.warn_no_watch");
    $("#btn-build").disabled = false;
  } else {
    warn.hidden = true;
    $("#btn-build").disabled = false;
  }
}

async function buildLibrary() {
  $("#btn-build").disabled = true;
  $("#btn-build").innerHTML = t("import.building");
  const res = await api.build();
  if (res.error) {
    toast(res.error);
    $("#btn-build").disabled = false;
    $("#btn-build").innerHTML = `<span>${t("import.build")}</span> <span class="cta-arr">→</span>`;
    return;
  }
  App.watchWindow = res.watch_window;
  if (res.restored) {
    // decisions.json round-trip: zones + decisions are restored on the server.
    // Land on "What should we go through?" (the plan screen) — it shows the
    // restored zone counts plus a "Continue" button straight back to the
    // in-progress review — while enrichment refreshes card details (thumbnails,
    // sub counts) in the background.
    await loadChannels();
    App.state = await api.state();
    startEnrichWatch();
    enterPlan();
    return;
  }
  enterEnrich();
}

// Views where the background-enrichment badge makes sense (the user is past
// import but enrichment is still topping up channel details).
const ENRICH_BADGE_VIEWS = ["plan", "swipe", "review", "resume"];

// When enrichment runs in the background (after a restore, or resumed on boot),
// show a small progress badge and let avatars fill in as channels are fetched —
// without yanking the card/list the user is currently on.
function startEnrichWatch() {
  clearInterval(App.bgEnrichPoll);
  let lastPulled = -1;
  const tick = async () => {
    let st;
    try { st = await api.status(); } catch { return; }
    const e = st.enrichment || {};
    if (e.running) {
      const total = e.total || (st.library ? st.library.channels : 0) || 0;
      if (ENRICH_BADGE_VIEWS.includes(App.view)) {
        enrichBadge(t("enrich.bg", {
          done: (e.done || 0).toLocaleString(locale()),
          total: total.toLocaleString(locale()),
        }));
      } else {
        enrichBadge(null);
      }
      // Every ~40 freshly-enriched channels, pull the new data and surface it
      // where it won't disrupt the user: patch avatars into the review list
      // (no scroll reset), refresh plan zone counts. The swipe card is left
      // alone mid-decision and picks up fresh data on the next render.
      if ((e.done || 0) - lastPulled >= 40) {
        lastPulled = e.done || 0;
        await loadChannels();
        if (App.view === "review") { updateReviewCounts(); patchReviewAvatars(); }
        else if (App.view === "plan") setupPlan();
      }
    } else if (st.stage === "ready") {
      clearInterval(App.bgEnrichPoll);
      await loadChannels();
      if (window.refreshView) window.refreshView();
      enrichBadge(t("enrich.bg_done"), true);
    }
  };
  tick();
  App.bgEnrichPoll = setInterval(tick, 2500);
}

// The progress badge. text=null hides it; done=true shows a brief "ready" state
// then auto-hides.
function enrichBadge(text, done = false) {
  const el = $("#enrich-badge");
  if (!el) return;
  if (text == null) { el.hidden = true; return; }
  el.querySelector(".eb-text").textContent = text;
  el.classList.toggle("done", done);
  el.hidden = false;
  if (done) {
    clearTimeout(enrichBadge._t);
    enrichBadge._t = setTimeout(() => { el.hidden = true; }, 3500);
  }
}

// Drop freshly-fetched avatars into already-rendered review rows in place, so
// the list visibly fills in during background enrichment without re-rendering
// (which would reset the scroll position and lose the user's place).
function patchReviewAvatars() {
  const root = $("#review-list");
  if (!root) return;
  for (const c of App.channels) {
    if (!c.thumbnail) continue;
    const ph = root.querySelector(`.review-row[data-id="${c.id}"] .ph`);
    if (!ph) continue;
    const img = document.createElement("img");
    img.className = "review-avatar";
    img.loading = "lazy";
    img.alt = "";
    img.src = c.thumbnail;
    ph.replaceWith(img);
  }
}

// Refresh just the review tab counts (cheap, no scroll reset) as zones settle.
function updateReviewCounts() {
  if (App.view !== "review") return;
  const g = reviewGroups();
  $("#tab-count-remove").textContent = g.remove.length;
  $("#tab-count-keep").textContent = g.keep.length;
  $("#tab-count-pending").textContent = g.pending.length;
  $("#tab-count-gone").textContent = g.gone.length;
}

// ─── enrichment progress ─────────────────────────────────────────────────
function enterEnrich() {
  showView("enrich");
  pollEnrich();
}
function pollEnrich() {
  clearInterval(App.enrichPoll);
  const tick = async () => {
    const st = await api.status();
    App.status = st;
    if (st.library) App.watchWindow = st.library.watch_window;
    const e = st.enrichment;
    const total = e.total || (st.library ? st.library.channels : 0) || 1;
    const done = e.done;
    const pct = Math.min(100, Math.round((done / total) * 100));
    $("#enrich-pct").textContent = pct;
    $("#enrich-done").textContent = done.toLocaleString("en-US");
    $("#enrich-total").textContent = total.toLocaleString("en-US");
    const circ = 327;
    $("#er-fill").style.strokeDashoffset = circ - (circ * pct) / 100;
    // allow starting once a useful chunk is ready
    $("#btn-enrich-skip").hidden = done < 40;
    if (!e.running && st.stage === "ready") {
      clearInterval(App.enrichPoll);
      await afterEnrich();
    }
  };
  tick();
  App.enrichPoll = setInterval(tick, 1200);
  $("#btn-enrich-skip").onclick = async () => {
    clearInterval(App.enrichPoll);
    await afterEnrich();
  };
}
async function afterEnrich() {
  await loadChannels();
  // If a session already exists (e.g. the page was reloaded mid-enrichment
  // after a restore), pick it up so the plan screen can offer "Continue".
  if (!App.state) App.state = await api.state();
  // Left enrichment early via "Start now"? Keep the corner badge going so the
  // user can watch previews fill in while they sort.
  if (App.status && App.status.enrichment && App.status.enrichment.running) startEnrichWatch();
  enterPlan();
}

async function loadChannels() {
  App.channels = await api.channels();
  App.byId = Object.fromEntries(App.channels.map((c) => [c.id, c]));
}

// ════════════════════════════════════════════════════════════════════════
//  PLAN (zone selection)
// ════════════════════════════════════════════════════════════════════════

function zoneCounts() {
  const c = { yellow: 0, red: 0, green: 0, not_found: 0 };
  for (const ch of App.channels) c[ch.zone] = (c[ch.zone] || 0) + 1;
  return c;
}

function enterPlan() {
  showView("plan");
  setupPlan();
}
function setupPlan() {
  const counts = zoneCounts();
  $("#plan-total").textContent = App.channels.length;
  $("#count-yellow").textContent = counts.yellow;
  $("#count-red").textContent = counts.red;
  $("#count-green").textContent = counts.green;
  $("#count-dead").textContent = counts.not_found;
  $("#eta-yellow").textContent = "~" + fmtETA(counts.yellow);
  // ETA reflects the whole zone (like yellow/green), so "248 · ~9 min" reads
  // consistently. The sample-vs-all choice is reflected in the queue total
  // below, not here — otherwise "248 · ~1 min" looks contradictory.
  $("#eta-red").textContent = "~" + fmtETA(counts.red);
  $("#eta-green").textContent = "~" + fmtETA(counts.green);

  if (App.watchWindow && App.watchWindow.start) {
    $("#window-note").textContent = t("plan.window_note",
      { from: monthYear(App.watchWindow.start), to: monthYear(App.watchWindow.end) });
  } else {
    $("#window-note").textContent = t("plan.window_note_default");
  }

  const update = () => {
    const cfg = readPlanConfig();
    const q = buildQueue(cfg).length;
    $("#queue-count").textContent = q;
    $("#queue-eta").textContent = fmtETA(q);
  };
  ["#opt-yellow", "#opt-red", "#opt-green"].forEach((s) => ($(s).onchange = update));
  $$("input[name='red-mode']").forEach((r) => (r.onchange = update));
  update();
  $("#btn-start").onclick = startSession;
  $("#btn-reimport").onclick = loadNewData;
  // let people return to an in-progress session without restarting
  const resumeBtn = $("#btn-plan-resume");
  const hasSession = !!(App.state && App.state.queue && App.state.queue.length);
  resumeBtn.hidden = !hasSession;
  if (hasSession) {
    // Spell out that this *continues* the existing sort (vs the CTA, which
    // starts a fresh one) and show how much is left, so the two never read alike.
    const left = pendingQueue().length;
    resumeBtn.textContent = left ? t("plan.resume_left", { n: left }) : t("plan.resume_review");
  }
  resumeBtn.onclick = () => {
    if (!App.state) return;
    if (pendingQueue().length) { showView("swipe"); renderSwipe(); }
    else enterReview();
  };
  // The CTA starts a *fresh* sort over the current selection — when a session
  // already exists that means discarding it, so say "Start over", not "Start".
  const startLabel = $("#btn-start [data-i18n]");
  if (startLabel) startLabel.textContent = hasSession ? t("plan.start_over") : t("plan.start");
}

// Return to the plan screen (change categories / load a different file) from
// anywhere, without dropping the current session.
function goToPlan() {
  if (!App.channels.length) return;
  enterPlan();
}

// Wipe the current library/session and return to the import wizard to load a
// different Takeout export.
async function loadNewData() {
  if (!(await confirmDialog({ message: t("plan.reimport_confirm"), danger: true }))) return;
  clearInterval(App.enrichPoll);
  clearInterval(App.bgEnrichPoll);
  await api.resetAll();
  App.state = null;
  App.channels = [];
  App.byId = {};
  App.lastStaging = null;
  App.lastSummary = null;
  showView("import");
}
function readPlanConfig() {
  return {
    include_yellow: $("#opt-yellow").checked,
    include_red: $("#opt-red").checked,
    include_green: $("#opt-green").checked,
    red_mode: document.querySelector("input[name='red-mode']:checked").value,
  };
}

function buildQueue(cfg) {
  const byZone = (z) => App.channels.filter((c) => c.zone === z);
  let queue = [];
  if (cfg.include_yellow) queue.push(...byZone("yellow"));
  if (cfg.include_red) {
    const red = byZone("red");
    if (cfg.red_mode === "sample") {
      queue.push(...[...red].sort(() => Math.random() - 0.5).slice(0, 30));
    } else queue.push(...red);
  }
  if (cfg.include_green) queue.push(...byZone("green"));

  // interleave by primary topic (or zone) for variety
  const buckets = {};
  for (const c of queue) {
    const k = (c.topics && c.topics[0]) || c.zone;
    (buckets[k] = buckets[k] || []).push(c);
  }
  Object.values(buckets).forEach((b) => b.sort(() => Math.random() - 0.5));
  const lists = Object.values(buckets);
  const out = [];
  let any = true;
  while (any) {
    any = false;
    for (const b of lists) if (b.length) { out.push(b.shift()); any = true; }
  }
  return out.map((c) => c.id);
}

async function startSession() {
  const config = readPlanConfig();
  const queue = buildQueue(config);
  if (!queue.length) { toast(t("toast.pick_zone")); return; }
  // Don't silently wipe work in progress. This includes a session restored from
  // a decisions.json import (which has no votes yet, but carries decisions we
  // must not lose) — guard on votes OR restored OR any existing decisions.
  const hasWork = App.state && (
    (App.state.votes && App.state.votes.length) ||
    App.state.restored ||
    (App.state.decisions && Object.keys(App.state.decisions).length)
  );
  if (hasWork && !(await confirmDialog({ message: t("plan.new_confirm"), danger: true }))) return;
  App.state = {
    version: 2,
    started_at: new Date().toISOString(),
    config, queue, decisions: {}, votes: [],
  };
  await saveStateNow();
  enterSwipe();
}

// ════════════════════════════════════════════════════════════════════════
//  SWIPE
// ════════════════════════════════════════════════════════════════════════

function enterSwipe() {
  showView("swipe");
  renderSwipe();
}

function pendingQueue() {
  // returns channel ids still needing a vote, in order
  const out = [];
  if (!App.state) return out;
  for (const id of App.state.queue) {
    const d = App.state.decisions[id];
    if (d !== "keep" && d !== "remove") out.push(id);
  }
  return out;
}
function currentChannel() {
  const q = pendingQueue();
  return q.length ? App.byId[q[0]] : null;
}
function nextChannel() {
  const q = pendingQueue();
  return q.length > 1 ? App.byId[q[1]] : null;
}
function votedCount() {
  if (!App.state) return 0;
  let n = 0;
  for (const id of App.state.queue) {
    const d = App.state.decisions[id];
    if (d === "keep" || d === "remove") n++;
  }
  return n;
}
function tally() {
  let keep = 0, remove = 0;
  if (App.state) for (const d of Object.values(App.state.decisions)) {
    if (d === "keep") keep++; else if (d === "remove") remove++;
  }
  return { keep, remove };
}

function renderSwipe() {
  const total = App.state.queue.length;
  const voted = votedCount();
  $("#progress-current").textContent = voted;
  $("#progress-total").textContent = total;
  $("#progress-eta").textContent = total - voted > 0 ? t("swipe.eta_left", { eta: fmtETA(total - voted) }) : t("swipe.done");
  $("#progress-fill").style.width = `${total ? (voted / total) * 100 : 0}%`;
  const tal = tally();
  $("#stat-kept").textContent = tal.keep;
  $("#stat-removed").textContent = tal.remove;
  const undoBtn = $("#btn-undo-mid");
  if (undoBtn) undoBtn.disabled = !(App.state.votes && App.state.votes.length);

  const ch = currentChannel();
  if (!ch) { enterReview(); return; }

  const deck = $("#card-deck");
  deck.innerHTML = "";
  // peek cards
  const nxt = nextChannel();
  const peek2 = document.createElement("div");
  peek2.className = "peek peek-2";
  deck.appendChild(peek2);
  const peek1 = document.createElement("div");
  peek1.className = "peek peek-1";
  peek1.innerHTML = `
    <div class="peek-label"><span class="next-pill"></span>${nxt ? escapeHTML(t("peek.next")) + " · " + escapeHTML(nxt.title) : escapeHTML(t("peek.last"))}</div>
    ${nxt && nxt.thumbnail ? `<img class="peek-avatar" src="${escapeHTML(nxt.thumbnail)}" alt="">` : `<div class="peek-avatar"></div>`}`;
  deck.appendChild(peek1);
  // hero
  const card = buildCardEl(ch);
  card.classList.add("enter");
  deck.appendChild(card);
  attachDrag(card);
  requestAnimationFrame(fitCard);
}

// Scale the deck so the whole card always fits the available stage area — never
// scaling up past 1:1. Guarantees the card never overlaps the topbar or the
// action buttons, at any window size.
function fitCard() {
  if (App.view !== "swipe") return;
  const deck = $("#card-deck");
  const stage = deck && deck.closest(".stage");
  const card = deck && deck.querySelector(".card");
  if (!stage || !card) return;
  deck.style.transform = "none";              // reset to measure natural size
  const natH = card.offsetHeight, natW = deck.offsetWidth;
  const availH = stage.clientHeight - 20, availW = stage.clientWidth - 20;
  const scale = Math.min(1, availH / natH, availW / natW);
  deck.style.transformOrigin = "center center";
  deck.style.transform = scale < 0.999 ? `scale(${scale.toFixed(3)})` : "none";
}

function livenessLabel(d) {
  if (d === null || d === undefined) return t("liveness.no_videos");
  if (d <= 7) return t("liveness.this_week");
  if (d <= 30) return t("liveness.this_month");
  if (d <= 90) return t("liveness.regularly");
  if (d <= 365) return t("liveness.slowing");
  if (d <= 730) return t("liveness.quiet_year");
  return t("liveness.dead");
}
const VERDICT_GLYPH = {
  keep: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`,
  remove: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>`,
  unsure: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 2.5-3 4"/><circle cx="12" cy="17.5" r="0.6" fill="currentColor" stroke="none"/></svg>`,
};

function buildCardEl(c) {
  const el = document.createElement("article");
  el.className = "card";
  el.dataset.verdict = c.verdict;        // keep_strong | keep | unsure | drop | drop_strong | gone
  el.dataset.lean = c.verdict_lean;      // keep | remove | unsure
  el.dataset.id = c.id;

  const fl = flag(c.country);
  const watched = c.watch_total;
  const cold = watched === 0;
  const subsText = c.subscribers != null ? t("card.subscribers", { n: fmtNum(c.subscribers) }) : t("card.subs_hidden");
  const desc = cleanDesc(c.description);
  const verdictLabel = t("verdict." + c.verdict);
  const watchedLabel = watched === 1 ? t("card.watched_label_one") : t("card.watched_label_other");

  // verdict bar: word + glyph + an arrow pointing the swipe direction
  const lean = c.verdict_lean;
  const arrow = lean === "keep" ? `<span class="vb-arrow">→</span>`
    : lean === "remove" ? `<span class="vb-arrow">←</span>` : "";
  const glyph = VERDICT_GLYPH[lean] || "?";

  // two clearly-separated facts, each in its own labelled slot:
  //   "you last watched it"  vs  "the channel's last video"
  const watchedFact = cold ? t("fact.watched_never") : fmtRelDays(c.days_since_last_watch);
  // "unreachable" = we couldn't check (network/rate-limit) — say so honestly
  // instead of the misleading "no videos", and don't paint it dead-red.
  const unreachable = c.status === "unreachable";
  const uploadFact = unreachable ? t("meta.unreachable")
    : c.days_since_last_upload == null ? t("fact.upload_none") : fmtRelDays(c.days_since_last_upload);
  const uploadDead = !unreachable && (c.days_since_last_upload == null || c.days_since_last_upload > 365);

  el.setAttribute("role", "group");
  el.setAttribute("aria-label", t("aria.card", {
    title: c.title, verdict: verdictLabel, n: watched,
    videos: watched === 1 ? t("aria.videos_one") : t("aria.videos_other"),
  }));

  el.innerHTML = `
    <div class="stamp keep">${escapeHTML(t("stamp.keep"))}</div>
    <div class="stamp remove">${escapeHTML(t("stamp.remove"))}</div>

    <div class="verdict-bar">
      ${lean === "remove" ? arrow : ""}
      <span class="vb-glyph">${glyph}</span>
      <span class="vb-label">${escapeHTML(verdictLabel)}</span>
      ${lean === "keep" ? arrow : ""}
    </div>

    <div class="identity">
      <div class="avatar-wrap">
        ${c.thumbnail
          ? `<img class="avatar" src="${escapeHTML(c.thumbnail)}" alt="" draggable="false">`
          : `<div class="avatar-placeholder">${escapeHTML((c.title || "?").slice(0, 1))}</div>`}
        ${fl ? `<span class="country-flag">${fl}</span>` : ""}
      </div>
      <h1 class="channel-name"><a href="${escapeHTML(c.url)}" target="_blank" rel="noopener" title="${escapeHTML(c.title)}">${escapeHTML(c.title)}</a></h1>
      <div class="sub-line">${c.handle ? `${escapeHTML(c.handle)} · ` : ""}${subsText}</div>
    </div>

    <div class="watch-hero ${cold ? "cold" : ""}">
      <div class="wh-number"><span class="num">${watched}</span></div>
      <div class="wh-label">${escapeHTML(watchedLabel)}</div>
    </div>

    <div class="facts">
      <div class="fact">
        <span class="fact-k">${escapeHTML(t("fact.watched_k"))}</span>
        <span class="fact-v">${escapeHTML(watchedFact)}</span>
      </div>
      <div class="fact">
        <span class="fact-k">${escapeHTML(t("fact.upload_k"))}</span>
        <span class="fact-v ${uploadDead ? "fact-dead" : ""}">${escapeHTML(uploadFact)}</span>
      </div>
    </div>

    <div class="about">
      <div class="about-k">${escapeHTML(t("about.label"))}</div>
      <p class="about-v ${desc ? "" : "muted-desc"}">${escapeHTML(desc || t("card.no_desc"))}</p>
    </div>
  `;
  const av = el.querySelector(".avatar");
  if (av) av.addEventListener("click", (e) => { e.stopPropagation(); zoomAvatar(c.thumbnail); });
  return el;
}

function cleanDesc(s) {
  if (!s) return "";
  let out = s.replace(/https?:\/\/\S+/g, "").replace(/\s+/g, " ").trim();
  if (out.length > 320) out = out.slice(0, 317) + "…";
  return out;
}
function zoomAvatar(src) {
  if (!src) return;
  const ov = document.createElement("div");
  ov.className = "avatar-zoom";
  ov.innerHTML = `<img src="${escapeHTML(src)}" alt="">`;
  ov.addEventListener("click", () => ov.remove());
  document.body.appendChild(ov);
}

// ─── drag to decide ──────────────────────────────────────────────────────
function attachDrag(card) {
  let dragging = false, sx = 0, sy = 0, dx = 0, dy = 0;
  const keep = card.querySelector(".stamp.keep");
  const remove = card.querySelector(".stamp.remove");
  const THRESH = 150;

  card.addEventListener("pointerdown", (e) => {
    if (e.target.closest("a") || e.target.closest(".avatar")) return;
    dragging = true; sx = e.clientX; sy = e.clientY; dx = dy = 0;
    card.style.transition = "none";
    card.classList.remove("enter");
    card.setPointerCapture(e.pointerId);
  });
  card.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    dx = e.clientX - sx; dy = e.clientY - sy;
    card.style.transform = `translate(${dx}px, ${dy * 0.4}px) rotate(${dx / 24}deg)`;
    const p = Math.min(Math.abs(dx) / THRESH, 1);
    keep.style.opacity = dx > 14 ? p : 0;
    remove.style.opacity = dx < -14 ? p : 0;
  });
  const release = () => {
    if (!dragging) return;
    dragging = false;
    if (Math.abs(dx) > THRESH) {
      vote(dx > 0 ? "keep" : "remove", card);
    } else {
      card.style.transition = "transform 0.4s var(--ease)";
      card.style.transform = "";
      keep.style.opacity = 0; remove.style.opacity = 0;
    }
  };
  card.addEventListener("pointerup", release);
  card.addEventListener("pointercancel", release);
}

function flyOut(card, decision) {
  const dir = decision === "keep" ? 1 : decision === "remove" ? -1 : 0;
  card.style.transition = "transform 0.34s var(--ease), opacity 0.34s";
  if (dir === 0) card.style.transform = "translateY(140px) scale(0.92)";
  else card.style.transform = `translate(${dir * 760}px, 40px) rotate(${dir * 16}deg)`;
  card.style.opacity = "0";
}

// ─── vote / skip / undo ──────────────────────────────────────────────────
async function vote(decision, cardEl) {
  if (App.busy) return;
  const ch = currentChannel();
  if (!ch) return;
  App.busy = true;

  App.state.decisions[ch.id] = decision;
  App.state.votes.push({ channel_id: ch.id, decision, at: new Date().toISOString() });
  announce(t(decision === "keep" ? "aria.kept" : "aria.removed", { title: ch.title }));
  saveStateDebounced();

  const card = cardEl || $("#card-deck .card");
  if (card) flyOut(card, decision);

  await wait(280);
  App.busy = false;
  renderSwipe();
}

async function skip() {
  if (App.busy) return;
  const ch = currentChannel();
  if (!ch) return;
  App.busy = true;
  // move to back of queue
  const idx = App.state.queue.indexOf(ch.id);
  if (idx >= 0) { App.state.queue.splice(idx, 1); App.state.queue.push(ch.id); }
  const card = $("#card-deck .card");
  if (card) flyOut(card, "skip");
  saveStateDebounced();
  await wait(260);
  App.busy = false;
  renderSwipe();
}

function undo() {
  if (App.busy || !App.state || !App.state.votes.length) { toast(t("toast.nothing_undo")); return; }
  const last = App.state.votes.pop();
  delete App.state.decisions[last.channel_id];
  // ensure it's back in the queue near the front
  if (!App.state.queue.includes(last.channel_id)) App.state.queue.unshift(last.channel_id);
  const ch = App.byId[last.channel_id];
  toast(t("toast.undone", { name: ch ? ch.title : "—" }));
  saveStateDebounced();
  renderSwipe();
}

// ════════════════════════════════════════════════════════════════════════
//  REVIEW
// ════════════════════════════════════════════════════════════════════════

function finalDecision(c) {
  const d = App.state ? App.state.decisions[c.id] : undefined;
  if (d === "keep" || d === "remove" || d === "pending") return d;
  // Not personally decided. A channel you put in your review queue but didn't
  // swipe stays "not reviewed" (never auto-removed) — only channels you DIDN'T
  // queue fall back to their zone default.
  if (App.state && App.state.queue && App.state.queue.includes(c.id)) return "pending";
  return c.default_decision;
}

function enterReview() {
  showView("review");
  renderReview();
}
// Group channels for the review tabs as four NON-overlapping categories.
// Channels YouTube itself deleted/banned (zone "not_found") form their own
// category and live ONLY there — never also under "Removing" — so a channel is
// never in two tabs at once. They're auto-unsubscribed (nothing left to keep),
// which is why their decision isn't user-editable here.
function reviewGroups() {
  const groups = { remove: [], keep: [], pending: [], gone: [] };
  for (const c of App.channels) {
    if (c.zone === "not_found" || c.status === "not_found") { groups.gone.push(c); continue; }
    (groups[finalDecision(c)] || groups.pending).push(c);
  }
  return groups;
}
// Sort a tab's channel list per App.reviewSort. Alphabetical by default; other
// modes fall back to alphabetical for ties so order is stable.
function sortReviewList(list) {
  const byTitle = (a, b) =>
    (a.title || "").localeCompare(b.title || "", locale(), { sensitivity: "base", numeric: true });
  const uploadTs = (c) => {
    const d = c.last_upload_at ? Date.parse(c.last_upload_at) : NaN;
    return Number.isNaN(d) ? -Infinity : d;   // unknown / no uploads sort last
  };
  const arr = [...list];
  switch (App.reviewSort) {
    case "subs":    arr.sort((a, b) => (b.subscribers || 0) - (a.subscribers || 0) || byTitle(a, b)); break;
    case "watched": arr.sort((a, b) => (b.watch_total || 0) - (a.watch_total || 0) || byTitle(a, b)); break;
    case "recent":  arr.sort((a, b) => uploadTs(b) - uploadTs(a) || byTitle(a, b)); break;
    case "alpha":
    default:        arr.sort(byTitle);
  }
  return arr;
}
function renderReview() {
  const groups = reviewGroups();
  $("#tab-count-remove").textContent = groups.remove.length;
  $("#tab-count-keep").textContent = groups.keep.length;
  $("#tab-count-pending").textContent = groups.pending.length;
  $("#tab-count-gone").textContent = groups.gone.length;
  // Everything getting unsubscribed = your "remove" picks PLUS the dead channels
  // (auto-removed). Keep the footer count honest about the total.
  $("#rf-note").textContent = t("review.foot", { n: groups.remove.length + groups.gone.length });
  $("#review-sub").textContent = t("review.sub",
    { remove: groups.remove.length, keep: groups.keep.length, pending: groups.pending.length, gone: groups.gone.length });

  // The dead-channels tab is informational — they're auto-unsubscribed, so the
  // bulk keep/remove/reset actions don't apply. Hide them and show a note.
  const onGone = App.reviewTab === "gone";
  const controls = $(".review-controls");
  if (controls) controls.classList.toggle("on-gone-tab", onGone);
  const goneNote = $("#review-gone-note");
  if (goneNote) goneNote.hidden = !onGone;

  // "Back to sorting" re-offers queue channels you haven't swiped yet; show how
  // many remain so it's clear even when the "Undecided" tab reads 0.
  const back = $("#btn-back-swipe");
  if (back) {
    const left = pendingQueue().length;
    back.disabled = !left;
    back.textContent = left ? `${t("review.back")} · ${left}` : t("review.back");
  }

  let list = groups[App.reviewTab] || [];
  if (App.reviewQuery) {
    const q = App.reviewQuery.toLowerCase();
    list = list.filter((c) =>
      c.title.toLowerCase().includes(q) || (c.handle || "").toLowerCase().includes(q));
  }
  list = sortReviewList(list);

  const root = $("#review-list");
  if (!list.length) {
    root.innerHTML = `<div class="review-empty">${escapeHTML(t("review.empty"))}</div>`;
    return;
  }
  root.innerHTML = list.map(reviewRow).join("");
  // Dead channels have a fixed decision — no toggle/reset wired for them.
  if (!onGone) {
    $$(".review-row .review-check").forEach((el) => {
      const toggle = () => toggleReview(el.closest(".review-row").dataset.id);
      el.addEventListener("click", toggle);
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
      });
    });
    $$(".review-row .row-reset").forEach((el) =>
      el.addEventListener("click", (e) => { e.stopPropagation(); resetToPending(el.dataset.id); }));
  }
}
function reviewRow(c) {
  // A channel YouTube deleted/banned — no page left, always auto-unsubscribed.
  const gone = c.zone === "not_found" || c.status === "not_found";
  const d = gone ? "remove" : finalDecision(c);
  const checked = d === "remove";
  const userVoted = !gone && !!(App.state && App.state.decisions[c.id]);
  const lastUp = c.status === "unreachable" ? t("meta.unreachable")
    : c.days_since_last_upload === null ? t("row.no_videos") : t("row.uploaded", { t: fmtRelDays(c.days_since_last_upload) });
  const watched = c.watch_total === 0 ? t("row.watched0") : t("row.watchedN", { n: c.watch_total, t: fmtRelDays(c.days_since_last_watch) });
  const badge = gone ? t("badge.gone") : d === "keep" ? t("badge.kept") : d === "remove" ? t("badge.removing") : t("badge.undecided");
  const subs = c.subscribers != null ? t("row.subs", { n: fmtNum(c.subscribers) }) + " · " : "";
  // Spell out why a dead channel has no metadata instead of a blank line.
  const meta = gone ? t("row.gone") : (subs + lastUp + " · " + watched);
  return `
    <div class="review-row ${checked ? "checked" : "unchecked"} ${userVoted ? "changed" : ""} ${gone ? "gone" : ""}" data-id="${c.id}" data-decision="${d}">
      <div class="review-check ${gone ? "fixed" : ""}" ${gone ? "" : `role="checkbox" tabindex="0" aria-checked="${checked}" aria-label="${escapeHTML(t("badge.removing"))}"`}></div>
      ${c.thumbnail ? `<img class="review-avatar" src="${escapeHTML(c.thumbnail)}" loading="lazy" alt="">` : `<div class="ph">${escapeHTML((c.title || "?").slice(0, 1))}</div>`}
      <div class="info">
        <div class="row-title"><a href="${escapeHTML(c.url)}" target="_blank" rel="noopener">${escapeHTML(c.title)}</a>${c.handle ? `<span class="rt-handle">${escapeHTML(c.handle)}</span>` : ""}</div>
        <div class="row-meta">${escapeHTML(meta)}</div>
      </div>
      <div class="row-end">
        <span class="row-badge">${escapeHTML(badge)}</span>
        ${!gone && d !== "pending" ? `<button class="row-reset" data-id="${c.id}" title="${escapeHTML(t("review.reset_row"))}" aria-label="${escapeHTML(t("review.reset_row"))}">↺</button>` : ""}
      </div>
    </div>`;
}
function toggleReview(id) {
  if (!App.state) return;
  const cur = finalDecision(App.byId[id]);
  App.state.decisions[id] = cur === "remove" ? "keep" : "remove";
  saveStateDebounced();
  renderReview();
}

// Reset a channel to "undecided" so it returns to the queue and gets offered again.
function resetToPending(id) {
  if (!App.state) return;
  App.state.decisions[id] = "pending";
  if (!App.state.queue.includes(id)) App.state.queue.push(id);
  saveStateDebounced();
  renderReview();
}
function bulkSet(decision) {
  const groups = reviewGroups();
  let list = groups[App.reviewTab] || [];
  if (App.reviewQuery) {
    const q = App.reviewQuery.toLowerCase();
    list = list.filter((c) => c.title.toLowerCase().includes(q) || (c.handle || "").toLowerCase().includes(q));
  }
  for (const c of list) {
    App.state.decisions[c.id] = decision;
    if (decision === "pending" && !App.state.queue.includes(c.id)) App.state.queue.push(c.id);
  }
  saveStateDebounced();
  renderReview();
}
function setupReview() {
  $$(".tab").forEach((tab) => (tab.onclick = () => {
    App.reviewTab = tab.dataset.tab;
    $$(".tab").forEach((x) => x.classList.remove("active"));
    tab.classList.add("active");
    renderReview();
  }));
  $("#review-search").addEventListener("input", (e) => { App.reviewQuery = e.target.value; renderReview(); });
  const sortSel = $("#review-sort");
  if (sortSel) {
    sortSel.value = App.reviewSort;
    sortSel.onchange = (e) => { App.reviewSort = e.target.value; renderReview(); };
  }
  $("#btn-bulk-keep").onclick = () => bulkSet("keep");
  $("#btn-bulk-remove").onclick = () => bulkSet("remove");
  $("#btn-bulk-reset").onclick = () => bulkSet("pending");
  $("#btn-back-swipe").onclick = () => {
    if (pendingQueue().length) { showView("swipe"); renderSwipe(); }
  };
  $("#btn-export").onclick = exportAndDone;
  $("#btn-review-home").onclick = goToPlan;
  $("#btn-back-review").onclick = () => { showView("review"); renderReview(); };
  $("#btn-open-unsub").onclick = enterUnsubscribe;
}

async function exportAndDone() {
  const data = await fetch("/api/export").then((r) => r.json());
  if (data.error) { toast(data.error); return; }
  App.lastSummary = data.summary;
  renderDoneSummary();
  showView("done");
}
function renderDoneSummary() {
  const s = App.lastSummary;
  if (!s) return;
  $("#done-summary").textContent = t("done.summary",
    { total: s.total, remove: s.to_remove, keep: s.to_keep });
  // Download link for the standalone (offline/portable) version, in the user's language.
  const dl = $("#btn-dl-html");
  if (dl) dl.href = `/api/export/unsubscribe.html?lang=${getLang()}`;
}

// ════════════════════════════════════════════════════════════════════════
//  UNSUBSCRIBE (in-app screen; mirrors the standalone page, shares i18n + lang)
// ════════════════════════════════════════════════════════════════════════

// Everything getting unsubscribed = your "remove" picks + dead channels.
function unsubChannels() {
  return App.channels.filter((c) =>
    c.zone === "not_found" || c.status === "not_found" || finalDecision(c) === "remove");
}

function setupUnsubscribe() {
  $("#btn-unsub-back").onclick = () => { showView("done"); renderDoneSummary(); };
  $("#unsub-search").addEventListener("input", (e) => { App.unsubQuery = e.target.value; renderUnsubscribe(); });
  $("#unsub-hide").addEventListener("change", renderUnsubscribe);
  $("#unsub-automark").addEventListener("change", (e) =>
    localStorage.setItem("yt-unsub-automark", e.target.checked ? "1" : "0"));
}

function enterUnsubscribe() {
  if (!App.state) return;
  if (!App.state.unsubscribed) App.state.unsubscribed = {};
  $("#unsub-automark").checked = localStorage.getItem("yt-unsub-automark") !== "0";  // default on
  showView("unsubscribe");
  renderUnsubscribe();
}

function unsubCounts() {
  const all = unsubChannels();
  const done = App.state.unsubscribed || {};
  const ndone = all.filter((c) => done[c.id]).length;
  $("#unsub-done").textContent = ndone;
  $("#unsub-total").textContent = all.length;
  $("#unsub-fill").style.width = (all.length ? (ndone / all.length * 100) : 0) + "%";
  $("#unsub-alldone").hidden = !(all.length && ndone === all.length);
}

function renderUnsubscribe() {
  if (!App.state) return;
  const done = App.state.unsubscribed || (App.state.unsubscribed = {});
  // keep the standalone-download link pointing at the current language
  $("#unsub-download").href = `/api/export/unsubscribe.html?lang=${getLang()}`;
  unsubCounts();
  let list = [...unsubChannels()].sort((a, b) =>
    (a.title || "").localeCompare(b.title || "", locale(), { sensitivity: "base", numeric: true }));
  const q = (App.unsubQuery || "").toLowerCase();
  if (q) list = list.filter((c) => c.title.toLowerCase().includes(q) || (c.handle || "").toLowerCase().includes(q));
  if ($("#unsub-hide").checked) list = list.filter((c) => !done[c.id]);

  const root = $("#unsub-list");
  if (!list.length) { root.innerHTML = `<div class="review-empty">${escapeHTML(t("unsub.empty"))}</div>`; return; }
  root.innerHTML = list.map((c) => unsubRow(c, !!done[c.id])).join("");
  $$("#unsub-list .unsub-row").forEach((row) => {
    const id = row.dataset.id;
    row.querySelector(".unsub-cb").addEventListener("change", (e) => toggleUnsub(id, e.target.checked, row));
    // Opening a channel auto-ticks it when the toggle is on — open, unsubscribe, done.
    row.querySelector(".row-open").addEventListener("click", () => {
      if ($("#unsub-automark").checked && !done[id]) toggleUnsub(id, true, row);
    });
  });
}

function unsubRow(c, isDone) {
  const gone = c.zone === "not_found" || c.status === "not_found";
  const subs = c.subscribers != null ? t("row.subs", { n: fmtNum(c.subscribers) }) + " · " : "";
  const meta = gone ? t("row.gone") : (subs + (c.handle || c.id));
  const av = c.thumbnail
    ? `<img class="review-avatar" src="${escapeHTML(c.thumbnail)}" loading="lazy" alt="">`
    : `<div class="ph">${escapeHTML((c.title || "?").slice(0, 1))}</div>`;
  return `<div class="unsub-row ${isDone ? "done" : ""}" data-id="${c.id}">
    <input type="checkbox" class="unsub-cb" ${isDone ? "checked" : ""} aria-label="done">
    ${av}
    <div class="info">
      <div class="row-title"><a href="${escapeHTML(c.url)}" target="_blank" rel="noopener">${escapeHTML(c.title)}</a></div>
      <div class="row-meta ${gone ? "gone" : ""}">${escapeHTML(meta)}</div>
    </div>
    <a class="row-open" href="${escapeHTML(c.url)}" target="_blank" rel="noopener">${escapeHTML(t("unsub.open"))}</a>
  </div>`;
}

function toggleUnsub(id, val, rowEl) {
  if (!App.state.unsubscribed) App.state.unsubscribed = {};
  if (val) App.state.unsubscribed[id] = true; else delete App.state.unsubscribed[id];
  saveStateDebounced();
  if ($("#unsub-hide").checked) { renderUnsubscribe(); return; }  // row should leave the list
  const row = rowEl || $(`#unsub-list .unsub-row[data-id="${id}"]`);
  if (row) {
    row.classList.toggle("done", val);
    const cb = row.querySelector(".unsub-cb"); if (cb) cb.checked = val;
  }
  unsubCounts();
}

// ════════════════════════════════════════════════════════════════════════
//  RESUME
// ════════════════════════════════════════════════════════════════════════

function setupResume() {
  const total = App.state.queue.length;
  const voted = votedCount();
  const left = total - voted;
  $("#resume-progress").textContent = t("resume.progress",
    { voted, total, left, eta: fmtETA(left) });
  $("#btn-resume").onclick = () => { showView("swipe"); renderSwipe(); };
  $("#btn-view-decisions").onclick = () => enterReview();
  $("#btn-restart").onclick = async () => {
    if (!(await confirmDialog({ message: t("resume.confirm"), danger: true }))) return;
    await api.resetState();
    App.state = null;
    enterPlan();
  };
}

// ════════════════════════════════════════════════════════════════════════
//  KEYBOARD
// ════════════════════════════════════════════════════════════════════════

function setupKeyboard() {
  document.addEventListener("keydown", (e) => {
    if (document.querySelector(".avatar-zoom") && e.key === "Escape") {
      document.querySelector(".avatar-zoom").remove(); return;
    }
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") {
      if (e.key === "Escape") e.target.blur();
      return;
    }
    if (App.view === "swipe") {
      switch (e.key) {
        case "ArrowLeft": vote("remove"); e.preventDefault(); break;
        case "ArrowRight": vote("keep"); e.preventDefault(); break;
        case "ArrowDown": case " ": skip(); e.preventDefault(); break;
        case "ArrowUp": case "u": case "U": case "Backspace": undo(); e.preventDefault(); break;
        case "Enter": { const ch = currentChannel(); if (ch) window.open(ch.url, "_blank"); break; }
        case "f": case "F": enterReview(); e.preventDefault(); break;
        case "?": $("#dialog-help").showModal(); e.preventDefault(); break;
      }
    } else if (App.view === "review") {
      if (e.key === "/") { $("#review-search").focus(); e.preventDefault(); }
      if (e.key === "Escape") { showView("swipe"); renderSwipe(); }
    }
  });
}

function setupSwipeClicks() {
  $("#card-deck").closest("#view-swipe").addEventListener("click", (e) => {
    const t = e.target.closest("[data-action]");
    if (!t) return;
    const a = t.dataset.action;
    if (a === "keep" || a === "remove") vote(a);
    else if (a === "skip") skip();
    else if (a === "undo") undo();
  });
  $("#btn-help").onclick = () => $("#dialog-help").showModal();
  $("#btn-finish").onclick = enterReview;
  const brand = $("#swipe-brand");
  brand.onclick = goToPlan;
  brand.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); goToPlan(); } };
}

// ════════════════════════════════════════════════════════════════════════
//  BOOT
// ════════════════════════════════════════════════════════════════════════

window.refreshView = function () {
  switch (App.view) {
    case "plan": if (App.channels.length) setupPlan(); break;
    case "swipe": if (App.state) renderSwipe(); break;
    case "review": renderReview(); break;
    case "resume": if (App.state) setupResume(); break;
    case "done": renderDoneSummary(); break;
    case "unsubscribe": if (App.state) renderUnsubscribe(); break;
    case "import": renderDetected(); break;
  }
};

async function boot() {
  showView("loading");
  // i18n: apply translations + wire the language switcher
  document.documentElement.lang = getLang();
  applyI18n(document);
  initLangSwitch();
  setupWelcome();
  setupImport();
  setupReview();
  setupUnsubscribe();
  setupKeyboard();
  setupSwipeClicks();
  window.addEventListener("resize", () => { clearTimeout(App._fitT); App._fitT = setTimeout(fitCard, 80); });

  let status;
  try {
    status = await api.status();
  } catch (e) {
    document.body.innerHTML = `<div style="padding:60px;color:var(--red);font-family:var(--mono)">Server not reachable: ${e.message}</div>`;
    return;
  }
  App.status = status;
  App.mode = status.mode || "local";
  document.body.classList.add("mode-" + App.mode);
  if (App.mode === "hosted") applyHostedCopy();
  if (status.library) App.watchWindow = status.library.watch_window;

  if (status.stage === "empty") {
    showView("welcome");
    return;
  }
  if (status.stage === "enriching") {
    // First-time enrichment (no session yet) blocks on the full-screen ring.
    // But if a session already exists (resumed/restored), enrichment is just
    // topping up channel details in the background — let the user keep working
    // and show the corner progress badge instead of the blocking screen.
    await loadChannels();
    App.state = await api.state();
    if (App.state && App.state.queue && App.state.queue.length) {
      startEnrichWatch();
      if (votedCount() >= App.state.queue.length) enterReview();
      else { setupResume(); showView("resume"); }
    } else {
      enterEnrich();
    }
    return;
  }
  // ready
  await loadChannels();
  App.state = await api.state();
  if (App.state && App.state.queue && App.state.queue.length) {
    if (votedCount() >= App.state.queue.length) enterReview();
    else { setupResume(); showView("resume"); }
  } else {
    enterPlan();
  }
}

// Hosted instance: the "100% local / never uploaded" promises are not true on
// a shared server — swap them for the honest hosted copy (and re-translate).
// Elements only relevant to one mode are toggled purely via CSS
// (body.mode-hosted + .local-only / .hosted-only).
function applyHostedCopy() {
  const swaps = {
    "welcome.f2.k": "welcome.f2.k_hosted",
    "welcome.f2.v": "welcome.f2.v_hosted",
    "import.privacy": "import.privacy_hosted",
  };
  for (const [from, to] of Object.entries(swaps)) {
    document.querySelectorAll(`[data-i18n="${from}"]`).forEach((el) => el.setAttribute("data-i18n", to));
  }
  applyI18n(document);
}

boot();
