"""
Per-user state — the seam between local and hosted mode.

A Store owns everything that used to be module-global in app.py: the in-memory
library, upload staging, the enrichment run, and the three files on disk
(library.json / session.json / decisions.json).

  local mode   one process-wide Store over data/ — behaviour and file layout
               identical to the original single-user app.
  hosted mode  one Store per browser session (HttpOnly cookie "sweep_sid"),
               under data/sessions/<sid>/, deleted after SESSION_TTL_HOURS of
               inactivity by the sweeper thread.

Enrichment runs are per-store but throttled globally: MAX_ENRICH_SESSIONS
bounds how many stores enrich at once, and enrich.py's fetch semaphore bounds
total concurrent requests to YouTube either way.
"""
from __future__ import annotations

import json
import re
import secrets
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config, enrich

SID_RE = re.compile(r"^[A-Za-z0-9_-]{40,64}$")   # shape of token_urlsafe(32)
SID_COOKIE = "sweep_sid"

# How many stores may run enrichment simultaneously (hosted fairness guard).
_enrich_slots = threading.BoundedSemaphore(config.MAX_ENRICH_SESSIONS)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    """All state for one user (the only user, in local mode)."""

    def __init__(self, data_dir: Path):
        self.dir = data_dir
        self.lock = threading.Lock()
        self.library: dict | None = None
        # accumulates uploaded files; `decisions` only fills when the user
        # re-imports this app's own decisions.json export; `hashes` skips a
        # file dropped twice (which would double watch counts).
        self.staging: dict = {"subscriptions": {}, "watch": [], "decisions": {}, "hashes": set()}
        # The active enrichment run state dict, or None — see start_enrichment.
        self.enrich: dict = {"run": None}
        self.import_times: list[float] = []    # hosted /api/import throttle
        self._last_touch = 0.0

    # ── files ────────────────────────────────────────────────────────────
    @property
    def library_file(self) -> Path:
        return self.dir / "library.json"

    @property
    def session_file(self) -> Path:
        return self.dir / "session.json"

    @property
    def decisions_file(self) -> Path:
        return self.dir / "decisions.json"

    def touch(self) -> None:
        """Bump the directory mtime — the sweeper's inactivity clock."""
        now = time.time()
        if now - self._last_touch < 60:
            return
        self._last_touch = now
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            import os
            os.utime(self.dir, None)
        except OSError:
            pass

    # ── library ──────────────────────────────────────────────────────────
    def load_library(self) -> dict | None:
        if self.library is not None:
            return self.library
        if self.library_file.exists():
            try:
                self.library = json.loads(self.library_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.library = None
        return self.library

    def save_library(self) -> None:
        """Caller holds self.lock (same contract as the original app)."""
        if self.library is None:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.library_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.library, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.library_file)

    # ── enrichment ───────────────────────────────────────────────────────
    def enrich_status(self) -> dict:
        run = self.enrich["run"]
        if not run:
            return {"running": False, "done": 0, "total": 0}
        return {"running": run["running"], "done": run["done"], "total": run["total"]}

    def stop_enrichment(self) -> None:
        """Detach + signal the active run (if any). The run's saves are guarded
        by identity (`self.enrich["run"] is run`), so once detached it winds
        down without touching anything current."""
        run = self.enrich["run"]
        if run:
            run["stop"] = True
            self.enrich["run"] = None

    def start_enrichment(self) -> bool:
        if config.DISABLE_ENRICH:
            return False
        lib = self.load_library()
        if not lib or not any(not c.get("enriched") for c in lib["channels"]):
            return False
        with self.lock:
            active = self.enrich["run"]
            if active and active["running"]:
                return False            # double-start guard (check-and-set under lock)
            run = {"running": True, "done": 0, "total": 0, "stop": False}
            self.enrich["run"] = run
        threading.Thread(target=self._run_enrichment, args=(run,), daemon=True).start()
        return True

    def _run_enrichment(self, run: dict) -> None:
        try:
            with _enrich_slots:         # bounded concurrent enriching sessions
                if run["stop"]:
                    return
                lib = self.load_library()
                if not lib:
                    return
                channels = lib["channels"]
                run["total"] = len([c for c in channels if not c.get("enriched")])

                save_counter = {"n": 0}

                def current() -> bool:
                    return self.enrich["run"] is run

                def on_result(_c):
                    save_counter["n"] += 1
                    if save_counter["n"] % 20 == 0:
                        with self.lock:
                            if current():   # a superseded run must not save over the new library
                                self.save_library()

                def progress(done, total, _c):
                    run["done"] = done

                enrich.enrich_library(
                    channels,
                    progress_cb=progress,
                    on_result=on_result,
                    should_stop=lambda: run["stop"],
                )
                with self.lock:
                    if current():
                        self.save_library()
        finally:
            run["running"] = False      # never leave a session stuck in "enriching"


# ─── Registry (hosted) ───────────────────────────────────────────────────────

_local_store: Store | None = None
_stores: dict[str, Store] = {}
_registry_lock = threading.Lock()


def local_store() -> Store:
    global _local_store
    with _registry_lock:
        if _local_store is None:
            _local_store = Store(config.DATA_DIR)
        return _local_store


def new_sid() -> str:
    return secrets.token_urlsafe(32)


def valid_sid(sid: str | None) -> bool:
    return bool(sid and SID_RE.match(sid))


def store_for_sid(sid: str) -> Store:
    """Find or create the session's store. On first sight of an existing
    on-disk session (process restart), resume its unfinished enrichment."""
    with _registry_lock:
        st = _stores.get(sid)
        if st is None:
            st = Store(config.SESSIONS_DIR / sid)
            _stores[sid] = st
            resume = st.library_file.exists()
        else:
            resume = False
    if resume:
        st.start_enrichment()
    st.touch()
    return st


def drop_session(sid: str) -> None:
    with _registry_lock:
        st = _stores.pop(sid, None)
    if st:
        st.stop_enrichment()
    d = config.SESSIONS_DIR / sid
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


# ─── TTL sweeper (hosted) ────────────────────────────────────────────────────

def sweep_expired_sessions() -> int:
    """Delete session dirs idle past the TTL. Returns how many were removed."""
    if not config.SESSIONS_DIR.exists():
        return 0
    cutoff = time.time() - config.SESSION_TTL_HOURS * 3600
    removed = 0
    for d in config.SESSIONS_DIR.iterdir():
        if not d.is_dir():
            continue
        try:
            if d.stat().st_mtime < cutoff:
                drop_session(d.name)
                removed += 1
        except OSError:
            continue
    return removed


def start_sweeper() -> None:
    def loop():
        while True:
            try:
                sweep_expired_sessions()
            except Exception:
                pass                    # the sweeper must never die
            time.sleep(15 * 60)
    threading.Thread(target=loop, daemon=True).start()
