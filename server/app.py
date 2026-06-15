"""
Subscription Sweep — web server.

The flow the frontend drives:

    empty  ->  import Takeout  ->  enrich (keyless)  ->  swipe  ->  export

Runs in two modes (see config.py):

  local (default)  single user on 127.0.0.1, state in data/ — your data never
                   leaves your machine.
  hosted           public multi-user instance: per-browser-session isolation
                   (HttpOnly cookie -> data/sessions/<sid>/), TTL cleanup,
                   tighter upload limits. See deploy/ for the runbook.

Per-user storage (all git-ignored):
    library.json    the ingested + enriched channel library
    session.json    the swipe session (resumable)
    decisions.json  the exported keep/remove list

No Google API key. No accounts. Enrichment scrapes public pages (see enrich.py)
through a shared cross-user cache (cache.py).
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import config, enrich, exports, ingest
from . import store as store_mod
from .store import Store
from .zones import to_api_record

STATIC_DIR = config.ROOT / "static"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── App + middleware ───────────────────────────────────────────────────────

app = FastAPI(title="Subscription Sweep", docs_url=None, redoc_url=None)

# The API is unauthenticated (local) / cookie-scoped (hosted) — pinning the
# Host header stops DNS-rebinding attacks from reaching it through a browser.
if "*" not in config.ALLOWED_HOSTS:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.ALLOWED_HOSTS)


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    """Local: always serve fresh assets so an updated build never leaves a
    stale app.js/index.html mismatch. Hosted: same for HTML/API, but static
    assets may cache briefly."""
    resp = await call_next(request)
    if config.HOSTED and request.url.path.startswith("/static"):
        resp.headers["Cache-Control"] = "public, max-age=300"
    else:
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


if config.HOSTED:
    @app.middleware("http")
    async def session_cookie(request: Request, call_next):
        # Only the API touches per-user state, so only the API mints a session.
        # Minting on cacheable /static responses would let a shared cache store
        # one visitor's Set-Cookie and serve it to the next — and would spawn a
        # throwaway session per asset on first load.
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        sid = request.cookies.get(store_mod.SID_COOKIE)
        fresh = not store_mod.valid_sid(sid)
        if fresh:
            sid = store_mod.new_sid()
        request.state.sid = sid
        resp = await call_next(request)
        if fresh:
            resp.set_cookie(
                store_mod.SID_COOKIE, sid,
                max_age=config.SESSION_TTL_HOURS * 3600,
                httponly=True, samesite="lax", secure=config.COOKIE_SECURE,
            )
        return resp


def get_store(request: Request) -> Store:
    if config.HOSTED:
        return store_mod.store_for_sid(request.state.sid)
    return store_mod.local_store()


@app.on_event("startup")
def _startup() -> None:
    if config.HOSTED:
        store_mod.sweep_expired_sessions()
        store_mod.start_sweeper()
    else:
        # Resume enrichment if a library exists with unenriched channels.
        st = store_mod.local_store()
        if st.load_library():
            st.start_enrichment()


# ─── Pages / static ─────────────────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/privacy")
def privacy():
    return FileResponse(STATIC_DIR / "privacy.html")


@app.get("/favicon.ico")
def favicon():
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ─── Status ─────────────────────────────────────────────────────────────────

def _staging_summary(st: Store) -> dict:
    """What the import wizard shows about the pending upload. `restore` is
    non-zero only for a re-imported decisions.json."""
    return {
        "subscriptions": len(st.staging["subscriptions"]),
        "watch_events": len(st.staging["watch"]),
        "restore": len(st.staging["decisions"]),
    }


def _stage(st: Store) -> str:
    if not st.load_library():
        return "empty"
    if st.enrich_status()["running"]:
        return "enriching"
    return "ready"


@app.get("/api/status")
def api_status(st: Store = Depends(get_store)):
    lib = st.load_library()
    enriched_n = sum(1 for c in lib["channels"] if c.get("enriched")) if lib else 0
    session = None
    if st.session_file.exists():
        try:
            s = json.loads(st.session_file.read_text(encoding="utf-8"))
            voted = sum(1 for d in s.get("decisions", {}).values() if d in ("keep", "remove"))
            session = {"queue_total": len(s.get("queue", [])), "voted": voted,
                       "started_at": s.get("started_at")}
        except json.JSONDecodeError:
            session = None
    return {
        "mode": config.MODE,
        "stage": _stage(st),
        "library": ({
            "channels": len(lib["channels"]),
            "enriched": enriched_n,
            "watch_window": lib.get("watch_window"),
            "created_at": lib.get("created_at"),
        } if lib else None),
        "enrichment": st.enrich_status(),
        "session": session,
        "staging": _staging_summary(st),
    }


# ─── Import / build ─────────────────────────────────────────────────────────

@app.post("/api/import")
async def api_import(request: Request, st: Store = Depends(get_store)):
    """Accept one uploaded file (raw body). Auto-expands a .zip. Accumulates
    into staging; call /api/library/build to finalize."""
    if config.HOSTED:
        now = time.time()
        st.import_times = [t for t in st.import_times if now - t < 3600]
        if len(st.import_times) >= config.IMPORTS_PER_HOUR:
            return JSONResponse({"error": "too many uploads — try again later"}, status_code=429)
        st.import_times.append(now)

    name = request.query_params.get("name", "upload.bin")
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > config.MAX_UPLOAD_BYTES:
            return JSONResponse({"error": "file too large"}, status_code=413)
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        return JSONResponse({"error": "empty body"}, status_code=400)

    # The same file dropped twice would double every watch count — skip it.
    digest = hashlib.sha256(data).hexdigest()
    if digest in st.staging["hashes"]:
        return {
            "files_recognized": 0,
            "duplicate": True,
            "added": {"subscriptions": 0, "watch_events": 0},
            "staging": _staging_summary(st),
        }

    found_subs = found_watch = 0
    files_seen = 0
    try:
        for fname, fbytes in ingest.iter_files(name, data):
            try:
                result = ingest.classify_file(fname, fbytes)
            except Exception:
                continue                 # one malformed file must not 500 the import
            if not result:
                continue
            files_seen += 1
            kind, payload = result
            if kind == "subscriptions":
                for row in payload:
                    st.staging["subscriptions"][row["channel_id"]] = row
                found_subs += len(payload)
            elif kind == "watch":
                st.staging["watch"].extend(payload)
                found_watch += len(payload)
            elif kind == "decisions":
                # Re-importing this app's own export: each channel becomes a
                # subscription (so the count + build path work) carrying its saved
                # zone, plus the decision to replay into the restored session.
                for row in payload:
                    cid = row["channel_id"]
                    st.staging["subscriptions"][cid] = {
                        "channel_id": cid, "url": row["url"],
                        "title": row["title"], "zone_saved": row.get("zone"),
                    }
                    st.staging["decisions"][cid] = row["decision"]
                found_subs += len(payload)
    except Exception:
        # zip-level failure (encrypted/corrupt member) — report, don't crash
        return JSONResponse({"error": "could not read the file"}, status_code=400)

    st.staging["hashes"].add(digest)
    return {
        "files_recognized": files_seen,
        "added": {"subscriptions": found_subs, "watch_events": found_watch},
        "staging": _staging_summary(st),
    }


def _restore_session(st: Store, decisions: dict, lib: dict) -> None:
    """Recreate session.json from a re-imported decisions.json so the user lands
    back on their in-progress review. The queue is every channel in the library;
    keep/remove are the votes already cast, pending are the ones still to swipe."""
    ids = [c["channel_id"] for c in lib["channels"]]
    known = set(ids)
    dmap = {cid: d for cid, d in decisions.items() if cid in known}
    session = {
        "version": 2,
        "started_at": now_iso(),
        "updated_at": now_iso(),
        "config": {"include_yellow": True, "include_red": True,
                   "include_green": True, "red_mode": "all"},
        "queue": ids,
        "decisions": dmap,
        "votes": [],
        "restored": True,
    }
    st.dir.mkdir(parents=True, exist_ok=True)
    st.session_file.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")


@app.post("/api/library/build")
def api_build(st: Store = Depends(get_store)):
    """Finalize staged uploads into the library and kick off enrichment."""
    if not st.staging["subscriptions"]:
        return JSONResponse(
            {"error": "no subscriptions found — upload your Takeout subscriptions.csv (or the whole .zip)"},
            status_code=400,
        )
    subs = list(st.staging["subscriptions"].values())
    restoring = bool(st.staging["decisions"])
    # Retire any enrichment still running against the OLD library, so the new
    # one can start its own run (and the old one can't save over it).
    st.stop_enrichment()
    with st.lock:
        st.library = ingest.build_library(subs, st.staging["watch"])
        st.save_library()
        if restoring:
            _restore_session(st, st.staging["decisions"], st.library)
        elif st.session_file.exists():
            # A fresh import invalidates a session built over the old library.
            st.session_file.unlink()
    st.staging["subscriptions"].clear()
    st.staging["watch"].clear()
    st.staging["decisions"].clear()
    st.staging["hashes"].clear()
    st.start_enrichment()
    lib = st.library
    return {
        "ok": True,
        "channels": len(lib["channels"]),
        "watch_window": lib["watch_window"],
        "restored": restoring,
    }


# ─── Enrichment ─────────────────────────────────────────────────────────────

@app.post("/api/enrich/start")
def api_enrich_start(st: Store = Depends(get_store)):
    return {"started": st.start_enrichment(), "running": st.enrich_status()["running"]}


@app.post("/api/enrich/stop")
def api_enrich_stop(st: Store = Depends(get_store)):
    run = st.enrich["run"]
    if run:
        run["stop"] = True
    return {"ok": True}


@app.get("/api/channels")
def api_channels(st: Store = Depends(get_store)):
    lib = st.load_library()
    if not lib:
        return JSONResponse([], status_code=200)
    return JSONResponse([to_api_record(c) for c in lib["channels"]])


# ─── Session state (frontend owns the shape) ────────────────────────────────

@app.get("/api/state")
def api_get_state(st: Store = Depends(get_store)):
    if not st.session_file.exists():
        return Response(status_code=204)
    try:
        return JSONResponse(json.loads(st.session_file.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return Response(status_code=204)


@app.post("/api/state")
async def api_save_state(request: Request, st: Store = Depends(get_store)):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "expected an object"}, status_code=400)
    body["updated_at"] = now_iso()
    st.dir.mkdir(parents=True, exist_ok=True)
    st.session_file.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "updated_at": body["updated_at"]}


@app.post("/api/state/reset")
def api_reset_state(st: Store = Depends(get_store)):
    if st.session_file.exists():
        st.session_file.unlink()
    return {"ok": True}


@app.post("/api/reset-all")
def api_reset_all(st: Store = Depends(get_store)):
    """Wipe everything and start from scratch (in hosted mode: only *your*
    session — stores are per-cookie)."""
    st.stop_enrichment()
    with st.lock:
        for f in (st.library_file, st.session_file, st.decisions_file):
            if f.exists():
                f.unlink()
        st.library = None
        st.staging["subscriptions"].clear()
        st.staging["watch"].clear()
        st.staging["decisions"].clear()
        st.staging["hashes"].clear()
    return {"ok": True}


# ─── Exports ────────────────────────────────────────────────────────────────

def _decisions_payload(st: Store) -> dict | None:
    """Build the keep/remove/pending breakdown from the library + session.
    A channel you queued but never swiped stays "pending" (never auto-removed);
    only channels you didn't queue fall back to their zone default. Returns None
    if there's no library yet."""
    lib = st.load_library()
    if not lib:
        return None
    state = {}
    if st.session_file.exists():
        try:
            state = json.loads(st.session_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
    decisions = state.get("decisions", {})
    queue = set(state.get("queue", []))

    records = [to_api_record(c) for c in lib["channels"]]
    to_remove, to_keep, pending = [], [], []
    for c in records:
        d = decisions.get(c["id"])
        if d not in ("keep", "remove", "pending"):
            d = "pending" if c["id"] in queue else c["default_decision"]
        # A channel YouTube deleted/banned is always unsubscribed — keep the
        # export consistent with the "Gone from YouTube" tab (auto-removed).
        # "not_found" is trustworthy here: enrichment reports it only on
        # positive evidence (404 / terminated page), never on network failure.
        if c["zone"] == "not_found" or c["status"] == "not_found":
            d = "remove"
        entry = {"channel_id": c["id"], "title": c["title"], "handle": c.get("handle"),
                 "url": c["url"], "zone": c["zone"]}
        (to_remove if d == "remove" else to_keep if d == "keep" else pending).append(entry)

    return {
        "exported_at": now_iso(),
        "summary": {"total": len(records), "to_remove": len(to_remove),
                    "to_keep": len(to_keep), "pending": len(pending)},
        "to_remove": to_remove,
        "to_keep": to_keep,
        "pending": pending,
    }


@app.get("/api/export")
def api_export(st: Store = Depends(get_store)):
    """Build decisions.json from the session, persist it, and return it."""
    payload = _decisions_payload(st)
    if payload is None:
        return JSONResponse({"error": "no library"}, status_code=400)
    st.dir.mkdir(parents=True, exist_ok=True)
    st.decisions_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


@app.get("/api/export/unsubscribe.json")
def api_export_unsub_json(st: Store = Depends(get_store)):
    """Flat machine-readable list of channels to unsubscribe from (for scripts)."""
    payload = _decisions_payload(st)
    if payload is None:
        return JSONResponse({"error": "no library"}, status_code=400)
    body = json.dumps(exports.build_unsubscribe_json(payload), ensure_ascii=False, indent=2)
    return Response(body, media_type="application/json; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="unsubscribe.json"'})


@app.get("/api/export/brief.md")
def api_export_brief(st: Store = Depends(get_store)):
    """Self-contained brief the user can hand to their own AI agent."""
    payload = _decisions_payload(st)
    if payload is None:
        return JSONResponse({"error": "no library"}, status_code=400)
    return Response(exports.build_agent_brief(payload), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="unsubscribe-brief.md"'})


@app.get("/api/export/unsubscribe.html")
def api_export_html(request: Request, st: Store = Depends(get_store)):
    """Standalone manual-unsubscribe page (opens in the browser, tracks progress)."""
    payload = _decisions_payload(st)
    if payload is None:
        return JSONResponse({"error": "no library"}, status_code=400)
    lang = request.query_params.get("lang", "en")
    if lang not in ("ru", "en"):
        lang = "en"
    return Response(exports.build_unsubscribe_html(payload, lang), media_type="text/html; charset=utf-8")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
