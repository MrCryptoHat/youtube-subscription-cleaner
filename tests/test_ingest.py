"""Ingestion: file sniffing, parsing, zip expansion + safety, URL sanitization."""
import io
import json
import zipfile

from server import ingest


def test_subscriptions_csv_language_agnostic():
    # headers in another language + reordered columns — sniff by shape, not name
    text = ("Идентификатор канала,URL,Название\n"
            "UCaaaaaaaaaaaaaaaaaaaaaa,https://www.youtube.com/channel/UCaaaaaaaaaaaaaaaaaaaaaa,Альфа\n")
    rows = ingest.parse_subscriptions_csv(text)
    assert len(rows) == 1
    assert rows[0]["channel_id"] == "UCaaaaaaaaaaaaaaaaaaaaaa"
    assert rows[0]["title"] == "Альфа"


def test_classify_subscriptions(subs_csv):
    kind, rows = ingest.classify_file("subscriptions.csv", subs_csv)
    assert kind == "subscriptions"
    assert {r["channel_id"] for r in rows} == {"UCaaaaaaaaaaaaaaaaaaaaaa", "UCbbbbbbbbbbbbbbbbbbbbbb"}


def test_classify_watch_json(watch_json):
    kind, events = ingest.classify_file("watch-history.json", watch_json)
    assert kind == "watch"
    assert all(cid == "UCaaaaaaaaaaaaaaaaaaaaaa" for cid, _ in events)
    assert len(events) == 2


def test_iter_files_expands_zip(takeout_zip):
    names = [n for n, _ in ingest.iter_files("takeout.zip", takeout_zip)]
    assert any("subscriptions" in n for n in names)
    assert any("watch-history" in n for n in names)


def test_url_sanitization_rejects_non_youtube():
    assert ingest.safe_channel_url("javascript:alert(1)", "UCxxxxxxxxxxxxxxxxxxxxxx") \
        == "https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx"
    assert ingest.safe_channel_url("https://evil.example/youtube.com/channel/x", "UCxxxxxxxxxxxxxxxxxxxxxx") \
        == "https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx"
    good = "https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx"
    assert ingest.safe_channel_url(good, "UCxxxxxxxxxxxxxxxxxxxxxx") == good


def test_zip_member_count_cap(monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(6):
            z.writestr(f"f{i}.csv", b"a" * 100)
    monkeypatch.setattr(ingest, "MAX_ZIP_MEMBERS", 3)
    out = list(ingest.iter_files("x.zip", buf.getvalue()))
    assert len(out) <= 3


def test_zip_total_bytes_cap(monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(5):
            z.writestr(f"f{i}.csv", b"a" * 1000)
    monkeypatch.setattr(ingest, "MAX_TOTAL_BYTES", 2000)
    out = list(ingest.iter_files("x.zip", buf.getvalue()))
    assert len(out) <= 2


def test_build_library_aggregates_watch():
    subs = [{"channel_id": "UCaaaaaaaaaaaaaaaaaaaaaa", "url": "", "title": "Alpha"}]
    from datetime import datetime, timezone
    events = [("UCaaaaaaaaaaaaaaaaaaaaaa", datetime(2026, 5, 1, tzinfo=timezone.utc)),
              ("UCaaaaaaaaaaaaaaaaaaaaaa", datetime(2026, 5, 2, tzinfo=timezone.utc))]
    lib = ingest.build_library(subs, events)
    ch = lib["channels"][0]
    assert ch["watch_total"] == 2


def test_decisions_export_roundtrip():
    export = {
        "to_remove": [{"channel_id": "UCaaaaaaaaaaaaaaaaaaaaaa", "title": "A",
                       "url": "https://www.youtube.com/channel/UCaaaaaaaaaaaaaaaaaaaaaa", "zone": "red"}],
        "to_keep": [{"channel_id": "UCbbbbbbbbbbbbbbbbbbbbbb", "title": "B",
                     "url": "https://www.youtube.com/channel/UCbbbbbbbbbbbbbbbbbbbbbb", "zone": "green"}],
        "pending": [],
    }
    assert ingest.looks_like_decisions_export(export)
    rows = ingest.parse_decisions_export(export)
    by_id = {r["channel_id"]: r for r in rows}
    assert by_id["UCaaaaaaaaaaaaaaaaaaaaaa"]["decision"] == "remove"
    assert by_id["UCaaaaaaaaaaaaaaaaaaaaaa"]["zone"] == "red"
    assert by_id["UCbbbbbbbbbbbbbbbbbbbbbb"]["decision"] == "keep"


def test_classify_decisions_not_mistaken_for_csv():
    body = json.dumps({"to_remove": [], "to_keep": [], "pending": []}).encode()
    kind, _ = ingest.classify_file("decisions.json", body)
    assert kind == "decisions"
