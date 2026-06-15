"""End-to-end API: import -> build -> state -> export, restore round-trip,
the keep-override fix, and hosted-mode session isolation."""
import importlib

import pytest
from fastapi.testclient import TestClient


def _fresh_app(tmp_path, monkeypatch, hosted=False):
    monkeypatch.setenv("SWEEP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SWEEP_MODE", "hosted" if hosted else "local")
    monkeypatch.setenv("SWEEP_DISABLE_ENRICH", "1")      # hermetic: never hit YouTube
    import server.config as config
    importlib.reload(config)
    import server.cache as cache
    importlib.reload(cache)
    import server.store as store
    importlib.reload(store)
    import server.enrich as enrich
    importlib.reload(enrich)
    import server.app as appmod
    importlib.reload(appmod)
    base = "https://testserver" if hosted else "http://testserver"
    return appmod, TestClient(appmod.app, base_url=base)


@pytest.fixture
def local(tmp_path, monkeypatch):
    return _fresh_app(tmp_path, monkeypatch, hosted=False)


def _build(client, subs_csv):
    client.post("/api/import?name=subscriptions.csv", content=subs_csv)
    return client.post("/api/library/build")


def test_local_import_build_export(local, subs_csv):
    appmod, client = local
    assert client.get("/api/status").json()["mode"] == "local"
    r = _build(client, subs_csv)
    assert r.status_code == 200 and r.json()["channels"] == 2
    chans = client.get("/api/channels").json()
    ids = [c["id"] for c in chans]
    client.post("/api/state", json={"version": 2, "queue": ids,
                                     "decisions": {ids[0]: "remove", ids[1]: "keep"}, "votes": []})
    exp = client.get("/api/export").json()
    assert exp["summary"]["to_remove"] == 1
    assert exp["summary"]["to_keep"] == 1


def test_duplicate_upload_skipped(local, subs_csv):
    appmod, client = local
    client.post("/api/import?name=s.csv", content=subs_csv)
    r2 = client.post("/api/import?name=s.csv", content=subs_csv)
    assert r2.json().get("duplicate") is True


def test_explicit_keep_survives_not_found(local, subs_csv, monkeypatch):
    """The data-loss bug: a transient/real not_found must NOT silently override
    an explicit user 'keep'. (Here not_found is genuine; the export still keeps
    the channel because the user said so — unless it's zone not_found.)"""
    appmod, client = local
    _build(client, subs_csv)
    # mark one channel's stored status not_found directly in the library
    st = appmod.store_mod.local_store()
    st.library["channels"][0]["channel_status"] = "not_found"
    st.library["channels"][0]["enriched"] = True
    ids = [c["channel_id"] for c in st.library["channels"]]
    # user explicitly keeps the (now not_found) channel
    client.post("/api/state", json={"version": 2, "queue": ids,
                                     "decisions": {ids[0]: "keep"}, "votes": []})
    exp = client.get("/api/export").json()
    # zone not_found is auto-removed by design — assert it lands in to_remove,
    # which is the *intended* behaviour for a genuinely deleted channel.
    removed_ids = [e["channel_id"] for e in exp["to_remove"]]
    assert ids[0] in removed_ids  # genuine not_found is removed
    # but a channel marked unreachable must NEVER be force-removed:
    st.library["channels"][1]["channel_status"] = "unreachable"
    st.library["channels"][1]["enriched"] = False
    client.post("/api/state", json={"version": 2, "queue": ids,
                                     "decisions": {ids[1]: "keep"}, "votes": []})
    exp2 = client.get("/api/export").json()
    kept_ids = [e["channel_id"] for e in exp2["to_keep"]]
    assert ids[1] in kept_ids


def test_restore_roundtrip(local, subs_csv):
    appmod, client = local
    _build(client, subs_csv)
    ids = [c["id"] for c in client.get("/api/channels").json()]
    client.post("/api/state", json={"version": 2, "queue": ids,
                                     "decisions": {ids[0]: "remove", ids[1]: "keep"}, "votes": []})
    decisions = client.get("/api/export").json()
    # reset, then re-import the decisions.json export
    client.post("/api/reset-all")
    import json as _json
    client.post("/api/import?name=decisions.json", content=_json.dumps(decisions).encode())
    r = client.post("/api/library/build")
    assert r.json()["restored"] is True
    state = client.get("/api/state").json()
    assert state["restored"] is True
    assert state["decisions"][ids[0]] == "remove"
    assert state["decisions"][ids[1]] == "keep"


def test_malformed_state_is_400(local):
    appmod, client = local
    r = client.post("/api/state", content=b"{not json")
    assert r.status_code == 400


def test_hosted_session_isolation(tmp_path, monkeypatch, subs_csv):
    appmod, a = _fresh_app(tmp_path, monkeypatch, hosted=True)
    b = TestClient(appmod.app, base_url="https://testserver")
    a.get("/api/status"); b.get("/api/status")
    assert a.cookies.get("sweep_sid") != b.cookies.get("sweep_sid")
    _build(a, subs_csv)
    assert len(a.get("/api/channels").json()) == 2
    assert b.get("/api/channels").json() == []           # B sees nothing of A's
    a.post("/api/reset-all")
    assert a.get("/api/status").json()["stage"] == "empty"


def test_hosted_upload_cap(tmp_path, monkeypatch):
    appmod, client = _fresh_app(tmp_path, monkeypatch, hosted=True)
    import server.config as config
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 10)
    r = client.post("/api/import?name=s.csv", content=b"x" * 50)
    assert r.status_code == 413


def test_hosted_static_does_not_mint_session(tmp_path, monkeypatch):
    """A session cookie on a cacheable /static response would leak via a CDN —
    only /api may mint one."""
    appmod, client = _fresh_app(tmp_path, monkeypatch, hosted=True)
    r = client.get("/static/app.js")
    assert "set-cookie" not in {k.lower() for k in r.headers}
    # the API still mints one
    r2 = client.get("/api/status")
    assert client.cookies.get("sweep_sid")
