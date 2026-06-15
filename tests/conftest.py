import io
import zipfile

import pytest


@pytest.fixture
def subs_csv() -> bytes:
    return (
        "Channel Id,Channel Url,Channel Title\n"
        "UCaaaaaaaaaaaaaaaaaaaaaa,https://www.youtube.com/channel/UCaaaaaaaaaaaaaaaaaaaaaa,Alpha\n"
        "UCbbbbbbbbbbbbbbbbbbbbbb,https://www.youtube.com/channel/UCbbbbbbbbbbbbbbbbbbbbbb,Beta\n"
    ).encode()


@pytest.fixture
def watch_json() -> bytes:
    import json
    data = [
        {"header": "YouTube", "title": "Watched X",
         "titleUrl": "https://www.youtube.com/watch?v=1",
         "subtitles": [{"name": "Alpha", "url": "https://www.youtube.com/channel/UCaaaaaaaaaaaaaaaaaaaaaa"}],
         "time": "2026-05-01T10:00:00.000Z"},
        {"header": "YouTube", "title": "Watched Y",
         "titleUrl": "https://www.youtube.com/watch?v=2",
         "subtitles": [{"name": "Alpha", "url": "https://www.youtube.com/channel/UCaaaaaaaaaaaaaaaaaaaaaa"}],
         "time": "2026-05-02T10:00:00.000Z"},
    ]
    return json.dumps(data).encode()


@pytest.fixture
def takeout_zip(subs_csv, watch_json) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Takeout/YouTube/subscriptions/subscriptions.csv", subs_csv)
        z.writestr("Takeout/YouTube/history/watch-history.json", watch_json)
    return buf.getvalue()
