#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════
#  Subscription Sweep — one command to set everything up and launch.
#  Creates a virtualenv, installs deps, starts the local server, opens your
#  browser. Everything runs on your machine; nothing is uploaded anywhere.
# ════════════════════════════════════════════════════════════════════════
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
VENV=".venv"
PORT="${PORT:-8765}"
URL="http://127.0.0.1:${PORT}/"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "✗ Python 3 not found. Install it from https://python.org and re-run." >&2
  exit 1
fi

if [ ! -d "$VENV" ]; then
  echo "→ Creating virtual environment…"
  "$PYTHON" -m venv "$VENV"
fi

echo "→ Installing dependencies (first run only takes a moment)…"
"$VENV/bin/pip" install -q --disable-pip-version-check -r requirements.txt

echo "→ Opening ${URL}"
(
  sleep 1.5
  if command -v open >/dev/null 2>&1; then open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
  else echo "   Open ${URL} in your browser."
  fi
) &

echo "→ Subscription Sweep is running on ${URL}"
echo "  (Press Ctrl-C to stop.)"
exec "$VENV/bin/python" -m uvicorn server.app:app --host 127.0.0.1 --port "$PORT" --log-level warning
