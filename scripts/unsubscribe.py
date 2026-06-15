#!/usr/bin/env python3
"""
Actually unsubscribe — drives a real browser with Playwright.

Reads data/decisions.json (the list you exported from the app), opens a
Chromium window with a persistent profile (so you sign in to YouTube once),
and for each channel marked "remove": Subscribed → Unsubscribe → Confirm.

Language-agnostic by design:
  * forces the YouTube UI to English (?hl=en) so button text is predictable,
  * still recognises a dozen common languages as a fallback,
  * locates elements by structure / stable ids (#confirm-button, the last
    item in the subscribe menu), not by translated labels,
  * NEVER clicks a button it can't positively identify as "Subscribed" — so
    it can't accidentally subscribe you to anything. Unsure → skip.

Safe to stop (Ctrl-C) and re-run: progress is logged to data/unsub-log.json
and already-done channels are skipped.

    ./unsubscribe.sh                 # or: .venv/bin/python scripts/unsubscribe.py

Options (env vars):
    LIMIT=10        only the first 10 (good for a test run)
    HEADLESS=1      no visible window (not recommended for the first run)
    DELAY_MIN=0.5   min seconds between channels
    DELAY_MAX=1.2   max seconds between channels
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, Page

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / "data" / "decisions.json"
LOG_FILE = ROOT / "data" / "unsub-log.json"
PROFILE_DIR = ROOT / ".cache" / "playwright-profile"

LIMIT = int(os.environ.get("LIMIT", "0")) or None
HEADLESS = os.environ.get("HEADLESS") == "1"
DELAY_MIN = float(os.environ.get("DELAY_MIN", "0.5"))
DELAY_MAX = float(os.environ.get("DELAY_MAX", "1.2"))

# Words that mean "you are subscribed" / "subscribe" across common UI languages.
# Lowercased, matched as substrings against the header button text + aria-label.
SUBSCRIBED_WORDS = [
    "subscribed", "вы подписаны", "подписки", "abonniert", "abonné", "suscrito",
    "inscrito", "iscritto", "geabonneerd", "подписка оформлена", "subskrybujesz",
    "登録済み", "구독중", "已订阅", "已訂閱", "abonelik",
]
SUBSCRIBE_WORDS = [
    "subscribe", "подписаться", "abonnieren", "s'abonner", "suscribirse",
    "inscrever", "iscriviti", "abonneren", "subskrybuj", "チャンネル登録", "구독",
    "订阅", "訂閱", "abone ol",
]
GONE_PHRASES = [
    "this channel does not exist", "this page isn't available",
    "this account has been terminated", "no longer available",
    "канала не существует", "страница недоступна", "аккаунт был заблокирован",
]

# Structural selectors — these don't depend on language.
HEADER_BTN = "yt-subscribe-button-view-model button"
MENU_ITEMS = "tp-yt-paper-listbox yt-list-item-view-model, ytd-menu-popup-renderer yt-list-item-view-model, yt-list-item-view-model"
CONFIRM_BTN = "yt-confirm-dialog-renderer #confirm-button button, yt-confirm-dialog-renderer #confirm-button"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_log() -> dict:
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"started_at": now_iso(), "results": {}}


def save_log(log: dict) -> None:
    log["updated_at"] = now_iso()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def matches(text: str, words: list[str]) -> bool:
    t = text.lower()
    return any(w in t for w in words)


def ensure_logged_in(page: Page, wait_minutes: int = 10) -> None:
    page.goto("https://www.youtube.com/?hl=en", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    if page.locator("#avatar-btn, ytd-topbar-menu-button-renderer #avatar-btn").count() > 0:
        print("✓ Signed in to YouTube", flush=True)
        return

    print("\n" + "=" * 70, flush=True)
    print("Please SIGN IN to YouTube in the window that just opened.", flush=True)
    print(f"Waiting up to {wait_minutes} min — I'll continue automatically once you're in.", flush=True)
    print("=" * 70, flush=True)
    deadline = time.time() + wait_minutes * 60
    last = 0
    while time.time() < deadline:
        time.sleep(4)
        try:
            if page.locator("#avatar-btn").count() > 0:
                print("✓ Signed in — continuing", flush=True)
                return
        except Exception:
            pass
        if time.time() - last > 30:
            print(f"  …waiting for sign-in ({int(deadline - time.time())}s left)", flush=True)
            last = time.time()
    print("ERROR: timed out waiting for sign-in", file=sys.stderr)
    sys.exit(1)


def unsubscribe_channel(page: Page, url: str) -> tuple[str, str]:
    sep = "&" if "?" in url else "?"
    try:
        page.goto(f"{url}{sep}hl=en", wait_until="domcontentloaded", timeout=20000)
    except PWTimeout:
        return "error", "navigation timeout"

    try:
        page.wait_for_selector(HEADER_BTN, timeout=6000, state="visible")
    except PWTimeout:
        body = page.locator("body").inner_text()[:800].lower()
        for p in GONE_PHRASES:
            if p in body:
                return "channel_unavailable", f"page says: {p!r}"
        return "not_subscribed", "no subscribe button found"

    btn = page.locator(HEADER_BTN).first
    try:
        label = (btn.inner_text() + " " + (btn.get_attribute("aria-label") or "")).strip()
    except Exception as e:
        return "error", f"couldn't read button: {e}"

    # SAFETY: only proceed if we positively recognise "subscribed".
    if matches(label, SUBSCRIBED_WORDS):
        pass
    elif matches(label, SUBSCRIBE_WORDS):
        return "not_subscribed", f"button says subscribe: {label!r}"
    else:
        return "unknown_state", f"unrecognised button: {label!r}"  # skip, never risk subscribing

    try:
        btn.click()
    except Exception as e:
        return "error", f"menu open failed: {e}"

    # The subscribe menu's LAST item is always "Unsubscribe" (after the
    # notification options). Order is stable across languages.
    try:
        page.wait_for_selector(MENU_ITEMS, timeout=3500, state="visible")
    except PWTimeout:
        return "error", "subscribe menu didn't open"
    items = page.locator(MENU_ITEMS)
    try:
        items.last.click()
    except Exception as e:
        return "error", f"unsubscribe item click failed: {e}"

    # Confirm dialog — #confirm-button is the affirmative one (never cancel).
    try:
        page.wait_for_selector(CONFIRM_BTN, timeout=3500, state="visible")
        page.locator(CONFIRM_BTN).first.click()
    except PWTimeout:
        return "error", "confirm dialog not found"
    except Exception as e:
        return "error", f"confirm click failed: {e}"

    time.sleep(0.4)
    try:
        new_label = (page.locator(HEADER_BTN).first.inner_text() or "").strip()
        if matches(new_label, SUBSCRIBE_WORDS):
            return "ok", ""
        return "ok", f"unsubscribed (button now {new_label!r})"
    except Exception:
        return "ok", "unsubscribed (verify skipped)"


def main() -> int:
    if not DECISIONS.exists():
        print(f"ERROR: {DECISIONS} not found — export your list from the app first.", file=sys.stderr)
        return 1
    payload = json.loads(DECISIONS.read_text(encoding="utf-8"))
    to_remove = payload.get("to_remove", [])
    if not to_remove:
        print("Nothing to remove — your to_remove list is empty.")
        return 0
    if LIMIT:
        to_remove = to_remove[:LIMIT]
        print(f"LIMIT={LIMIT} → processing {len(to_remove)} channels")

    log = load_log()
    results = log.setdefault("results", {})
    DONE = ("ok", "channel_unavailable", "not_subscribed")
    todo = [c for c in to_remove if results.get(c["channel_id"], {}).get("status") not in DONE]

    print(f"To remove: {len(to_remove)}   already done: {len(to_remove) - len(todo)}   left: {len(todo)}")
    if not todo:
        print("All done already.")
        return 0

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=HEADLESS,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        ensure_logged_in(page)

        ok = err = skip = 0
        for i, ch in enumerate(todo, 1):
            cid = ch["channel_id"]
            title = ch.get("title", cid)
            url = ch.get("url") or f"https://www.youtube.com/channel/{cid}"
            print(f"[{i:>4}/{len(todo)}] {title[:48]:<48} ", end="", flush=True)

            status, detail = unsubscribe_channel(page, url)
            results[cid] = {"title": title, "url": url, "status": status, "detail": detail, "at": now_iso()}
            save_log(log)

            if status == "ok":
                ok += 1; print("✓ unsubscribed")
            elif status in ("not_subscribed", "channel_unavailable"):
                skip += 1; print(f"⊘ skip ({status})")
            elif status == "unknown_state":
                skip += 1; print(f"⊘ skip (couldn't read button — left as is)")
            else:
                err += 1; print(f"✗ {detail}")

            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

        print("\n─── Done ───")
        print(f"  unsubscribed: {ok}")
        print(f"  skipped:      {skip}")
        print(f"  errors:       {err}")
        print(f"  log: {LOG_FILE}")
        try:
            ctx.close()
        except Exception:
            pass
    return 0 if err == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
