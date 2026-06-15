"""Export builders — especially the <script> XSS escape regression."""
import json

from server import exports

PAYLOAD = {
    "exported_at": "2026-06-10T00:00:00+00:00",
    "to_remove": [
        {"channel_id": "UCaaaaaaaaaaaaaaaaaaaaaa", "title": "Normal Channel",
         "handle": "@normal", "url": "https://www.youtube.com/channel/UCaaaaaaaaaaaaaaaaaaaaaa", "zone": "red"},
    ],
    "to_keep": [], "pending": [],
}


def test_unsubscribe_json_shape():
    out = exports.build_unsubscribe_json(PAYLOAD)
    assert out["count"] == 1
    assert out["channels"][0]["channel_id"] == "UCaaaaaaaaaaaaaaaaaaaaaa"


def test_agent_brief_lists_channels():
    md = exports.build_agent_brief(PAYLOAD)
    assert "Normal Channel" in md
    assert "UCaaaaaaaaaaaaaaaaaaaaaa" in md


def test_unsubscribe_html_escapes_script_breakout():
    evil = {"to_remove": [{"channel_id": "UCaaaaaaaaaaaaaaaaaaaaaa",
                           "title": "</script><script>alert(document.domain)</script>",
                           "url": None}], "to_keep": [], "pending": []}
    html = exports.build_unsubscribe_html(evil)
    # the raw breakout must NOT appear; it must be unicode-escaped inside the data blob
    assert "</script><script>alert" not in html
    assert "\\u003c/script" in html


def test_unsubscribe_html_rejects_bad_url():
    evil = {"to_remove": [{"channel_id": "UCaaaaaaaaaaaaaaaaaaaaaa", "title": "X",
                           "url": "javascript:alert(1)"}], "to_keep": [], "pending": []}
    html = exports.build_unsubscribe_html(evil)
    assert "javascript:alert" not in html
    assert "youtube.com/channel/UCaaaaaaaaaaaaaaaaaaaaaa" in html
