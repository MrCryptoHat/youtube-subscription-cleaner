"""Zone classification + keep-score, including the unreachable/not_found split."""
from datetime import timedelta

from server import zones

REF = zones.now_utc()


def _iso(days_ago):
    return (REF - timedelta(days=days_ago)).isoformat()


def test_green_active_and_watched():
    c = {"channel_status": "ok", "last_upload_at": _iso(5),
         "watch_6mo": 4, "watch_total": 12, "watch_last_at": _iso(10)}
    zone, default = zones.compute_zone(c, ref=REF)
    assert zone == "green" and default == "keep"


def test_red_dead_and_never_watched():
    c = {"channel_status": "ok", "last_upload_at": _iso(900),
         "watch_6mo": 0, "watch_total": 0}
    zone, default = zones.compute_zone(c, ref=REF)
    assert zone == "red" and default == "remove"


def test_yellow_active_never_watched():
    c = {"channel_status": "ok", "last_upload_at": _iso(10),
         "watch_6mo": 0, "watch_total": 0}
    zone, _ = zones.compute_zone(c, ref=REF)
    assert zone == "yellow"


def test_not_found_is_remove():
    zone, default = zones.compute_zone({"channel_status": "not_found"}, ref=REF)
    assert zone == "not_found" and default == "remove"


def test_unreachable_never_auto_removes():
    # A network failure must not be treated as a dead channel.
    c = {"channel_status": "unreachable", "watch_6mo": 0, "watch_total": 0}
    zone, default = zones.compute_zone(c, ref=REF)
    assert zone == "yellow" and default == "pending"
    # ...and if you used to watch it, it stays green
    c2 = {"channel_status": "unreachable", "watch_6mo": 3, "watch_total": 9}
    assert zones.compute_zone(c2, ref=REF)[0] == "green"


def test_saved_zone_preserved_on_restore():
    c = {"zone_saved": "green", "channel_status": "ok", "last_upload_at": _iso(900),
         "watch_6mo": 0, "watch_total": 0}
    # would compute red, but the restored colour wins
    assert zones.compute_zone(c, ref=REF)[0] == "green"


def test_saved_not_found_dropped_when_channel_proves_alive():
    # A saved "gone" must not stick once re-enrichment finds the channel live.
    c = {"zone_saved": "not_found", "enriched": True, "channel_status": "ok",
         "last_upload_at": _iso(5), "watch_6mo": 2, "watch_total": 5,
         "watch_last_at": _iso(10)}
    zone, _ = zones.compute_zone(c, ref=REF)
    assert zone == "green"


def test_keep_score_monotonic_with_engagement():
    base = {"channel_status": "ok", "last_upload_at": _iso(10)}
    low = zones.keep_score({**base, "watch_total": 1, "watch_6mo": 0, "watch_last_at": _iso(200)}, ref=REF)
    high = zones.keep_score({**base, "watch_total": 40, "watch_6mo": 12, "watch_last_at": _iso(5)}, ref=REF)
    assert high > low


def test_unreachable_not_definitely_drop():
    c = {"channel_status": "unreachable", "watch_total": 0, "watch_6mo": 0}
    assert zones.keep_score(c, ref=REF) >= 23
