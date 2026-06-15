"""
Keyless channel enrichment — no Google API key required.

For each channel we pull two public, unauthenticated sources:

  1. RSS feed  https://www.youtube.com/feeds/videos.xml?channel_id=UC…
     -> date of the most recent upload (the "is this channel alive" signal)

  2. Channel page  https://www.youtube.com/channel/UC…?hl=en
     -> avatar (og:image), title, description, @handle, subscriber count

We force English (hl=en + Accept-Language) so the subscriber string is
parseable ("16.5M subscribers") regardless of the user's locale.

Everything runs on the stdlib (urllib + ThreadPoolExecutor) so the project has
no scraping dependencies. Enrichment is best-effort and degrades gracefully:
if a fetch fails we keep whatever Takeout already gave us (at minimum the name).
"""
from __future__ import annotations

import random
import re
import socket
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from . import cache as channel_cache
from . import config
from .zones import now_utc

# One global gate on outbound YouTube traffic — shared by every enrichment run
# in the process, so concurrent (hosted) sessions can't multiply the pressure
# coming from a single IP.
_FETCH_SEM = threading.BoundedSemaphore(config.FETCH_CONCURRENCY)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
PAGE_URL = "https://www.youtube.com/channel/{}?hl=en&gl=US"
ATOM = "{http://www.w3.org/2005/Atom}"
YT_NS = "{http://www.youtube.com/xml/schemas/2015}"

GONE_PHRASES = (
    "this channel does not exist",
    "this account has been terminated",
    "this page isn't available",
    "this page isnt available",
    "channel does not exist",
)


def _fetch(url: str, timeout: int = 15) -> tuple[int, str]:
    """Return (status, text). status 0 on network error, 404 on missing."""
    req = urllib.request.Request(url, headers=HEADERS)
    with _FETCH_SEM:
        if config.HOSTED:
            time.sleep(random.uniform(0.05, 0.35))   # jitter: don't look like a burst
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return resp.status, resp.read().decode(charset, errors="replace")
            except urllib.error.HTTPError as e:
                if e.code == 429:                      # rate limited — back off
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return e.code, ""
            except (urllib.error.URLError, TimeoutError, ConnectionError, socket.timeout):
                # socket.timeout is TimeoutError on 3.10+, but a distinct OSError on 3.9
                time.sleep(0.6 * (attempt + 1))
    return 0, ""


def _parse_rss(xml_text: str) -> tuple[str | None, str | None]:
    """Return (channel_title, last_upload_iso)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None, None
    title_el = root.find(f"{ATOM}title")
    title = title_el.text if title_el is not None else None
    last = None
    for entry in root.findall(f"{ATOM}entry"):
        pub = entry.find(f"{ATOM}published")
        if pub is not None and pub.text:
            if last is None or pub.text > last:
                last = pub.text
    return title, last


# Force hl=en, so the count is always English ("54.1K subscribers"). It shows
# up as a quoted JSON string in several layouts (subscriberCountText.simpleText,
# the newer metadata "content", accessibility labels) — match the string itself.
_SUBS_RE = re.compile(r'"([0-9][0-9.,]*\s?[KMB]?)\s+subscribers?"')
_OG_IMAGE_RE = re.compile(r'<meta property="og:image" content="([^"]+)"')
_OG_TITLE_RE = re.compile(r'<meta property="og:title" content="([^"]+)"')
_OG_DESC_RE = re.compile(r'<meta property="og:description" content="([^"]*)"')
_HANDLE_RE = re.compile(r'"canonicalBaseUrl":"/(@[\w.\-]+)"')
_HANDLE_RE2 = re.compile(r'youtube\.com/(@[\w.\-]+)"')
_COUNTRY_RE = re.compile(r'"country":"([A-Z]{2})"')


def _parse_subs(text: str) -> int | None:
    m = _SUBS_RE.search(text)
    if not m:
        return None
    s = m.group(1).replace(" ", "").replace(",", "").strip().upper()
    mult = 1
    if s.endswith("K"):
        mult, s = 1_000, s[:-1]
    elif s.endswith("M"):
        mult, s = 1_000_000, s[:-1]
    elif s.endswith("B"):
        mult, s = 1_000_000_000, s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return None


def _html_unescape(s: str) -> str:
    import html as _html
    return _html.unescape(s)


def enrich_channel(cid: str) -> dict:
    """Fetch and parse everything we can for one channel id.

    "not_found" is reserved for positive evidence the channel is gone (an HTTP
    404 or YouTube's own "terminated / does not exist" page). A network failure,
    rate-limit or unparseable response yields "unreachable" with enriched=False
    instead, so the channel is retried later and is NEVER auto-removed on the
    strength of a bad connection.
    """
    out: dict = {
        "enriched": True,
        "enriched_at": now_utc().isoformat(),
        "channel_status": "ok",
        "last_upload_at": None,
        "thumbnail": None,
        "description": None,
        "handle": None,
        "subscribers": None,
        "videos": None,
        "country": None,
        "topics": [],
    }

    def unreachable() -> dict:
        out["channel_status"] = "unreachable"
        out["enriched"] = False           # retry on the next enrichment pass
        return out

    # 1. RSS — last upload date + channel title
    rss_status, rss_text = _fetch(RSS_URL.format(cid))
    rss_title = None
    if rss_status == 200 and rss_text:
        rss_title, last = _parse_rss(rss_text)
        out["last_upload_at"] = last

    # 2. Channel page — avatar, title, description, handle, subs
    page_status, page_text = _fetch(PAGE_URL.format(cid))
    if page_status == 404:
        out["channel_status"] = "not_found"
        return out
    if page_status == 200 and page_text:
        low = page_text[:6000].lower()
        if any(p in low for p in GONE_PHRASES):
            out["channel_status"] = "not_found"
            return out
        if m := _OG_IMAGE_RE.search(page_text):
            out["thumbnail"] = _html_unescape(m.group(1))
        if m := _OG_TITLE_RE.search(page_text):
            out["title"] = _html_unescape(m.group(1))
        if m := _OG_DESC_RE.search(page_text):
            out["description"] = _html_unescape(m.group(1))
        out["subscribers"] = _parse_subs(page_text)
        if m := (_HANDLE_RE.search(page_text) or _HANDLE_RE2.search(page_text)):
            out["handle"] = m.group(1)
        if m := _COUNTRY_RE.search(page_text):
            out["country"] = m.group(1)
    else:
        # 0 (network error), 429, 5xx, … — no evidence the channel is gone.
        if rss_title:
            out["title"] = rss_title      # RSS answered: the channel exists
        else:
            return unreachable()

    if rss_title and not out.get("title"):
        out["title"] = rss_title

    # Page answered 200 but nothing parseable (consent wall, layout change…) and
    # RSS gave no title either: we genuinely don't know — retry later rather than
    # declaring the channel gone.
    if not out.get("title") and not out.get("thumbnail"):
        return unreachable()

    # No uploads ever surfaced (channel exists but has no public videos)?
    if out["last_upload_at"] is None and out["channel_status"] == "ok":
        out["channel_status"] = "no_uploads"

    return out


def enrich_channel_cached(cid: str) -> dict:
    """enrich_channel through the shared cross-user cache. A channel's public
    data is identical for everyone, so popular channels are fetched once per
    TTL no matter how many libraries contain them."""
    hit = channel_cache.shared().get(cid)
    if hit is not None:
        return dict(hit)               # copy — callers merge/mutate the result
    result = enrich_channel(cid)
    channel_cache.shared().put(cid, result)   # put() ignores "unreachable"
    return result


def enrich_library(
    channels: list[dict],
    *,
    progress_cb: Callable[[int, int, dict], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    on_result: Callable[[dict], None] | None = None,
    max_workers: int = 8,
) -> None:
    """Enrich every not-yet-enriched channel in place, concurrently.

    progress_cb(done, total, channel) is called after each completion.
    on_result(channel) lets the caller persist incrementally.
    should_stop() lets the caller cancel.
    """
    todo = [c for c in channels if not c.get("enriched")]
    total = len(todo)
    if total == 0:
        return
    by_id = {c["channel_id"]: c for c in todo}
    done = 0

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(enrich_channel_cached, c["channel_id"]): c["channel_id"] for c in todo}
        for fut in as_completed(futures):
            cid = futures[fut]
            channel = by_id[cid]
            try:
                result = fut.result()
                # don't let an enrichment 'title' wipe a good Takeout title with empty
                if not result.get("title"):
                    result.pop("title", None)
                channel.update(result)
            except Exception as e:  # never let one channel kill the run
                channel.update({"enriched": True, "channel_status": "error", "enrich_error": str(e)[:200]})
            done += 1
            if on_result:
                on_result(channel)
            if progress_cb:
                progress_cb(done, total, channel)
            if should_stop and should_stop():
                pool.shutdown(wait=False, cancel_futures=True)
                return
