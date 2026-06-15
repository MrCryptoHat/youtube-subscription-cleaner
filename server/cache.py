"""
Shared channel-enrichment cache.

enrich_channel(cid) is a pure function of the channel id — its result is the
same for every user. Caching it cuts re-import time for one user and, on a
hosted instance, dedupes popular channels across users (and keeps the pressure
on YouTube proportional to *distinct* channels, not visitors).

SQLite in WAL mode: cheap, stdlib-only, safe with the enrichment thread pool.
TTLs: CACHE_TTL_DAYS for live channels (a few days of staleness is nothing
against the 365-day "dead" threshold); CACHE_NOT_FOUND_TTL_HOURS for gone
channels so a mishap can't brand a channel deleted for a week. "unreachable"
results are never cached.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ChannelCache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS channel_cache ("
                " channel_id TEXT PRIMARY KEY,"
                " payload    TEXT NOT NULL,"
                " status     TEXT NOT NULL,"
                " fetched_at TEXT NOT NULL)"
            )
            self._conn.commit()

    def get(self, cid: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload, status, fetched_at FROM channel_cache WHERE channel_id=?",
                (cid,),
            ).fetchone()
        if not row:
            return None
        payload, status, fetched_at = row
        try:
            fetched = datetime.fromisoformat(fetched_at)
        except ValueError:
            return None
        ttl = (timedelta(hours=config.CACHE_NOT_FOUND_TTL_HOURS)
               if status == "not_found" else timedelta(days=config.CACHE_TTL_DAYS))
        if _now() - fetched > ttl:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def put(self, cid: str, result: dict) -> None:
        status = result.get("channel_status", "ok")
        if status == "unreachable":
            return  # a failed fetch is not a fact about the channel
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO channel_cache (channel_id, payload, status, fetched_at)"
                " VALUES (?,?,?,?)",
                (cid, json.dumps(result, ensure_ascii=False), status, _now().isoformat()),
            )
            self._conn.commit()


_instance: ChannelCache | None = None
_instance_lock = threading.Lock()


def shared() -> ChannelCache:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = ChannelCache(config.DATA_DIR / "cache" / "enrich.db")
        return _instance
