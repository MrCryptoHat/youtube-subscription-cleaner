#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════
#  Actually unsubscribe from the channels you marked "remove".
#  Reads data/decisions.json (export it from the app first), opens a browser,
#  you sign in to YouTube once, and it clicks through the removals for you.
#  Safe to stop and re-run — it skips what's already done.
# ════════════════════════════════════════════════════════════════════════
set -euo pipefail
cd "$(dirname "$0")"

VENV=".venv"
if [ ! -d "$VENV" ]; then
  echo "✗ Run ./start.sh first to set things up." >&2
  exit 1
fi

if [ ! -f "data/decisions.json" ]; then
  echo "✗ data/decisions.json not found." >&2
  echo "  Open the app (./start.sh), finish sorting, and click \"Export my list\" first." >&2
  exit 1
fi

# Playwright (and its browser) is installed lazily — only this step needs it.
echo "→ Making sure Playwright + browser are installed (first run downloads ~150MB)…"
"$VENV/bin/pip" install -q --disable-pip-version-check "playwright>=1.40"
"$VENV/bin/python" -m playwright install chromium

exec "$VENV/bin/python" scripts/unsubscribe.py "$@"
