# Security policy

## Threat model

Subscription Sweep is **local-first**. In the default mode it runs on `127.0.0.1`,
reads a file you chose, and makes outbound requests only to public YouTube pages.
There is no account, no API key and no telemetry.

If you run the **hosted** mode (`SWEEP_MODE=hosted`), it becomes a multi-user
service: each browser session is isolated by an `HttpOnly` cookie into its own
data directory, swept after 24h of inactivity. Raw watch history is never written
to disk — only derived per-channel aggregates and your keep/remove decisions.
See [`deploy/DEPLOY.md`](deploy/DEPLOY.md) and [`static/privacy.html`](static/privacy.html).

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Instead, open a
[private security advisory](https://github.com/MrCryptoHat/youtube-subscription-cleaner/security/advisories/new)
on GitHub, or email the maintainer listed on the GitHub profile. Include steps to
reproduce and the impact. You'll get an acknowledgement within a few days.

## Scope notes

- Imported files (Takeout exports, re-imported `decisions.json`) are treated as
  untrusted: channel titles/handles are HTML-escaped in the UI and unicode-escaped
  in generated HTML exports; channel URLs are constrained to `youtube.com`.
- Uploads are size-capped and zip expansion is bounded (member count + total bytes)
  to prevent decompression-bomb DoS.
- The local API pins the `Host` header (DNS-rebinding guard); override the allowlist
  with `SWEEP_ALLOWED_HOSTS` only if you understand the implication.
