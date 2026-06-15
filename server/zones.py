"""
Shared channel-classification logic.

A channel falls into one of four zones based on two independent signals:
  - channel liveness: days since its last upload (from RSS / API enrichment)
  - your engagement:   how many of its videos you watched (from Takeout history)

    not_found  channel is gone from YouTube (deleted / terminated)  -> remove
    green      active AND you watched it recently                   -> keep
    red        dead AND you never watched it (in the history window) -> remove
    yellow     everything in between — needs a human decision        -> pending

The zone drives the default vote and the colour accent on the card. The user
can always override it.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

# A channel is "dead" if it hasn't uploaded in this long.
DEAD_DAYS = 365
VERY_DEAD_DAYS = 365 * 2


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def days_since(iso: str | None, *, ref: datetime | None = None) -> int | None:
    dt = parse_iso(iso)
    if dt is None:
        return None
    return ((ref or now_utc()) - dt).days


def topic_label(url: str) -> str:
    """https://en.wikipedia.org/wiki/Music_of_Asia -> 'Music of Asia'."""
    m = re.search(r"/wiki/(.+)$", url)
    if not m:
        return url
    return m.group(1).replace("_", " ").split("(")[0].strip()


# Default vote per zone — used both as the compute_zone fallback and to derive a
# default for a zone restored from a decisions.json export.
ZONE_DEFAULT_DECISION = {
    "not_found": "remove",
    "red": "remove",
    "green": "keep",
    "yellow": "pending",
}


def compute_zone(channel: dict, *, ref: datetime | None = None) -> tuple[str, str]:
    """Return (zone, default_decision) for a stored channel record."""
    # Restored from a decisions.json export: honour the saved zone verbatim, even
    # after re-enrichment, so the user's sorted colours survive the round-trip.
    # Exception: a saved "not_found" is dropped once re-enrichment proves the
    # channel alive — a channel that exists must never stay auto-removed.
    saved = channel.get("zone_saved")
    if saved in ZONE_DEFAULT_DECISION:
        if not (saved == "not_found" and channel.get("enriched")
                and channel.get("channel_status") == "ok"):
            return saved, ZONE_DEFAULT_DECISION[saved]

    if channel.get("channel_status") == "not_found":
        return "not_found", "remove"

    d_last_upload = days_since(channel.get("last_upload_at"), ref=ref)
    is_dead = d_last_upload is None or d_last_upload > DEAD_DAYS
    is_very_dead = d_last_upload is None or d_last_upload > VERY_DEAD_DAYS

    watched_6mo = channel.get("watch_6mo", 0) or 0
    watched_any = channel.get("watch_total", 0) or 0

    # We couldn't reach YouTube for this channel — there is no liveness signal,
    # so it must never default to "remove"; engagement alone decides.
    if channel.get("channel_status") == "unreachable":
        return ("green", "keep") if watched_6mo > 0 else ("yellow", "pending")

    if not is_dead and watched_6mo > 0:
        return "green", "keep"
    if is_very_dead and watched_any == 0:
        return "red", "remove"
    if is_dead and watched_any == 0:
        return "red", "remove"
    return "yellow", "pending"


# ─── Keep-likelihood: a single predicted verdict per channel ────────────────
# A 0–100 score that predicts "will you keep this?" so the card can lead with an
# instant verdict and the user knows which way to swipe before reading anything.
#
# Engagement (how much / how recently you watched) dominates — it's the signal
# the user actually decides on. Liveness only breaks ties in the uncertain
# middle: an active-but-never-watched channel might be a *forgotten favourite*
# (the history window is finite), so it never drops to "definitely drop"; a
# dead-and-never-watched channel does.

# Band cutoffs (inclusive lower bound). Order high→low.
VERDICT_BANDS = [
    (82, "keep_strong", "Definitely keep", "keep"),
    (62, "keep",        "Probably keep",   "keep"),
    (40, "unsure",      "Your call",       "unsure"),
    (23, "drop",        "Probably remove", "remove"),
    (0,  "drop_strong", "Definitely remove", "remove"),
]


def keep_score(c: dict, *, ref: datetime | None = None) -> int:
    """Predicted keep-likelihood, 0–100 ("Pull").

    Built around a neutral base of 50 ("your call"): watch engagement pulls it
    up, death/neglect pulls it down. Recency is a *multiplier* on engagement —
    watching 30 videos but not in 18 months must not score like watching 30 last
    week. The neglect term is asymmetric: a still-active channel you never watched
    might be a forgotten favourite (the history window is finite), so it can never
    be condemned to "definitely drop" on neglect alone — only deadness does that.
    """
    ref = ref or now_utc()
    if c.get("channel_status") == "not_found":
        return 0  # a deleted channel can't be kept

    # 1. Watch engagement (the spine) — saturating bucket curve on watch volume.
    wt = c.get("watch_total", 0) or 0
    if wt == 0:    watch_pts = 0
    elif wt <= 2:  watch_pts = 14
    elif wt <= 5:  watch_pts = 26
    elif wt <= 10: watch_pts = 34
    elif wt <= 20: watch_pts = 40
    elif wt <= 50: watch_pts = 44
    else:          watch_pts = 45

    # Recency MULTIPLIER on that engagement.
    d_watch = days_since(c.get("watch_last_at"), ref=ref)
    if d_watch is None:    rec_mult = 1.0     # only reached when wt == 0
    elif d_watch <= 30:    rec_mult = 1.00
    elif d_watch <= 90:    rec_mult = 0.90
    elif d_watch <= 180:   rec_mult = 0.75
    elif d_watch <= 365:   rec_mult = 0.58
    else:                  rec_mult = 0.45
    engagement = watch_pts * rec_mult         # 0 .. 45

    # Recent-repeat bonus — the strongest "keeper" tell.
    w6 = c.get("watch_6mo", 0) or 0
    if w6 == 0:    recent_bonus = 0
    elif w6 <= 2:  recent_bonus = 6
    elif w6 <= 5:  recent_bonus = 10
    elif w6 <= 10: recent_bonus = 13
    else:          recent_bonus = 15

    # 2. Death / neglect down-force (asymmetric).
    d_up = days_since(c.get("last_upload_at"), ref=ref)
    if c.get("channel_status") == "unreachable":
        live = "unknown"                  # fetch failed — no liveness evidence
    elif d_up is None:   live = "no_uploads"
    elif d_up <= 90:     live = "active"
    elif d_up <= 365:    live = "slowing"
    elif d_up <= 730:    live = "dormant"
    else:                live = "dead"

    if wt == 0:
        # Asymmetric by liveness. Only DEAD (>2y) + never-watched is the
        # archetypal "definitely drop"; a still-active channel you never watched
        # is a possible forgotten favourite, so it stays neutral ("your call").
        # "unknown" is treated like "active": no evidence is not evidence of death.
        neglect = {"active": 8, "unknown": 8, "slowing": 20, "no_uploads": 26,
                   "dormant": 26, "dead": 46}[live]
    else:
        neglect = 0 if live in ("active", "slowing", "unknown") else (4 if live in ("dormant", "no_uploads") else 8)

    # 3. Assemble around a neutral 50.
    score = 50 + engagement + recent_bonus - neglect

    # 4. Window-caveat guardrail: a channel not known to be dead is never "definitely drop".
    if live in ("active", "slowing", "unknown") and score < 23:
        score = 23

    return int(round(max(0, min(100, score))))


def verdict_for(c: dict, *, ref: datetime | None = None) -> dict:
    """Return {score, key, label, lean} for the card's predicted verdict."""
    s = keep_score(c, ref=ref)
    if c.get("channel_status") == "not_found":
        return {"score": 0, "key": "gone", "label": "Gone from YouTube", "lean": "remove"}
    for lo, key, label, lean in VERDICT_BANDS:
        if s >= lo:
            return {"score": s, "key": key, "label": label, "lean": lean}
    return {"score": s, "key": "drop_strong", "label": "Definitely remove", "lean": "remove"}


def to_api_record(c: dict, *, ref: datetime | None = None) -> dict:
    """Flatten a stored channel into the shape the frontend consumes."""
    ref = ref or now_utc()
    zone, default = compute_zone(c, ref=ref)
    verdict = verdict_for(c, ref=ref)
    return {
        "keep_score": verdict["score"],
        "verdict": verdict["key"],
        "verdict_label": verdict["label"],
        "verdict_lean": verdict["lean"],
        "id": c["channel_id"],
        "title": c.get("title") or c.get("title_from_subs") or "(no title)",
        "url": c.get("url") or f"https://www.youtube.com/channel/{c['channel_id']}",
        "handle": c.get("handle"),
        "description": (c.get("description") or "").strip(),
        "thumbnail": c.get("thumbnail"),
        "subscribers": c.get("subscribers"),
        "videos": c.get("videos"),
        "country": c.get("country"),
        "topics": [topic_label(t) for t in (c.get("topics") or [])],
        "last_upload_at": c.get("last_upload_at"),
        "days_since_last_upload": days_since(c.get("last_upload_at"), ref=ref),
        "watch_total": c.get("watch_total", 0),
        "watch_12mo": c.get("watch_12mo", 0),
        "watch_6mo": c.get("watch_6mo", 0),
        "watch_last_at": c.get("watch_last_at"),
        "days_since_last_watch": days_since(c.get("watch_last_at"), ref=ref),
        "status": c.get("channel_status", "unknown"),
        "enriched": bool(c.get("enriched")),
        "zone": zone,
        "default_decision": default,
    }
