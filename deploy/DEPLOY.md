# Hosting Subscription Sweep (multi-user instance)

The same codebase runs in two modes. `SWEEP_MODE=hosted` turns on per-browser-session
isolation: every visitor gets an `HttpOnly` cookie and an isolated data directory under
`$SWEEP_DATA_DIR/sessions/<sid>/`, swept automatically after `SWEEP_SESSION_TTL_HOURS`
of inactivity. The Playwright unsubscribe step is hidden (it needs the user's own
machine); hosted users get the manual page, the AI-agent brief and the JSON exports.

## Runbook (Debian/Ubuntu VPS, Caddy)

1. Create a user and clone:

   ```bash
   sudo useradd -r -m -d /opt/subscription-sweep -s /usr/sbin/nologin sweep
   sudo -u sweep git clone https://github.com/MrCryptoHat/youtube-subscription-cleaner /opt/subscription-sweep
   ```

2. Virtualenv + deps:

   ```bash
   cd /opt/subscription-sweep
   sudo -u sweep python3 -m venv .venv
   sudo -u sweep .venv/bin/pip install -r requirements.txt
   ```

3. systemd unit — edit `deploy/subscription-sweep.service` (domain in
   `SWEEP_ALLOWED_HOSTS` is **required**: it's the DNS-rebinding guard), then:

   ```bash
   sudo cp deploy/subscription-sweep.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now subscription-sweep
   ```

4. Caddy — edit the domain in `deploy/Caddyfile`, merge it into `/etc/caddy/Caddyfile`,
   `sudo systemctl reload caddy`. (nginx instead? Set `client_max_body_size 250m;` and
   proxy to `127.0.0.1:8765`.)

5. Smoke-test isolation: open the site in two different browsers, import two different
   files — each must see only its own data. Then `curl -s https://<domain>/api/status`
   should show `"mode": "hosted"`.

## Knobs (env)

| Variable | Default (hosted) | Meaning |
|---|---|---|
| `SWEEP_MODE` | `local` | `hosted` enables sessions, TTL sweeper, tighter limits |
| `SWEEP_DATA_DIR` | `<repo>/data` | state root; sessions live in `sessions/` under it |
| `SWEEP_SESSION_TTL_HOURS` | 24 | inactivity before a session dir is deleted |
| `SWEEP_MAX_UPLOAD_MB` | 250 | upload cap (mirror it at the proxy) |
| `SWEEP_FETCH_CONCURRENCY` | 4 | global concurrent fetches to YouTube |
| `SWEEP_MAX_ENRICH_SESSIONS` | 2 | sessions enriching at once (others queue) |
| `SWEEP_CACHE_TTL_DAYS` | 7 | shared channel-info cache TTL (`not_found`: 24 h) |
| `SWEEP_IMPORTS_PER_HOUR` | 60 | per-session upload throttle |
| `SWEEP_ALLOWED_HOSTS` | localhost | **set to your domain** |

## Notes

- **HTTPS is mandatory.** The session cookie is `Secure`, so over plain http the
  browser never sends it back and every request starts a new empty session (data
  appears to vanish). The Caddyfile gives you automatic TLS; if you terminate TLS
  elsewhere, keep it. (For local hosted-mode testing only, `SWEEP_COOKIE_SECURE=0`
  relaxes this — never in production.)
- **One worker only.** Per-session stores and enrichment threads are in-process.
  The app is I/O-bound; one worker comfortably serves a niche free tool.
- **Privacy page** is served at `/privacy` and linked from the welcome screen.
  Keep it accurate if you change retention settings.
- Raw watch-history events are never written to disk — only per-channel aggregates
  (see `ingest.build_library`), so a leaked session dir contains derived counts,
  not a browsing log.
- Updating: `git pull && systemctl restart subscription-sweep`. Sessions survive
  restarts (state is on disk; an interrupted enrichment resumes on next request).
