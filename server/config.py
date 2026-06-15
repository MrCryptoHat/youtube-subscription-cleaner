"""
Runtime configuration, environment-driven.

Two modes, one codebase:

  SWEEP_MODE=local   (default) — the classic single-user app on 127.0.0.1.
                     One data/ directory, byte-identical behaviour to before
                     the hosted mode existed. ./start.sh never sets anything.

  SWEEP_MODE=hosted  — a public multi-user instance. Every browser session
                     gets an isolated store under data/sessions/<sid>/ keyed
                     by an HttpOnly cookie, swept after SWEEP_SESSION_TTL_HOURS
                     of inactivity. The Playwright step is hidden in the UI
                     (it needs the user's own machine).

Everything here is read once at import time.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


MODE = (os.environ.get("SWEEP_MODE") or "local").strip().lower()
HOSTED = MODE == "hosted"

DATA_DIR = Path(os.environ.get("SWEEP_DATA_DIR") or (ROOT / "data"))
SESSIONS_DIR = DATA_DIR / "sessions"

# Hours of inactivity before a hosted session's data is deleted.
SESSION_TTL_HOURS = _int("SWEEP_SESSION_TTL_HOURS", 24)

# Session cookie `Secure` flag. MUST stay true in production (the hosted mode is
# meaningless without HTTPS — a non-Secure cookie over http would be re-minted on
# every request and no session would persist). Set SWEEP_COOKIE_SECURE=0 only for
# local hosted-mode testing over plain http.
COOKIE_SECURE = (os.environ.get("SWEEP_COOKIE_SECURE", "1")).lower() not in ("0", "false", "no")

# Upload ceiling. Local default is far above any real Takeout; hosted is tighter
# (the reverse proxy should enforce the same number).
MAX_UPLOAD_MB = _int("SWEEP_MAX_UPLOAD_MB", 250 if HOSTED else 2048)
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

# Global cap on concurrent fetches to YouTube — shared across ALL enrichment
# runs, so N hosted users can't multiply the pressure from one server IP.
FETCH_CONCURRENCY = _int("SWEEP_FETCH_CONCURRENCY", 4 if HOSTED else 8)

# Shared channel-info cache: a channel's public data is identical for every
# user, so popular channels are fetched once. "not_found" entries expire fast
# so a transient mishap can't poison the cache.
CACHE_TTL_DAYS = _int("SWEEP_CACHE_TTL_DAYS", 7)
CACHE_NOT_FOUND_TTL_HOURS = _int("SWEEP_CACHE_NOT_FOUND_TTL_HOURS", 24)

# How many sessions may enrich at the same time (hosted); further runs queue.
MAX_ENRICH_SESSIONS = _int("SWEEP_MAX_ENRICH_SESSIONS", 2 if HOSTED else 1)

# Per-session /api/import throttle (hosted abuse guard).
IMPORTS_PER_HOUR = _int("SWEEP_IMPORTS_PER_HOUR", 60)

# Skip the background enrichment fetch entirely — used by the test suite so it
# never reaches out to YouTube. Off in normal operation.
DISABLE_ENRICH = (os.environ.get("SWEEP_DISABLE_ENRICH") or "").lower() in ("1", "true", "yes")

# Host-header allowlist (DNS-rebinding protection for the unauthenticated API).
# Hosted operators MUST set this to their domain. "*" disables the check.
ALLOWED_HOSTS = [h.strip() for h in (os.environ.get(
    "SWEEP_ALLOWED_HOSTS") or "127.0.0.1,localhost,testserver").split(",") if h.strip()]
