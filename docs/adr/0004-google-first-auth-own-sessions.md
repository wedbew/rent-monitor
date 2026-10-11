# ADR 0004 — Google-first sign-in with own sessions in Postgres

- **Status:** accepted (blueprint §2 "Auth decision") · **Date:** 2026-10-11 · **Ticket:** RM-31

## Decision
Sign-in is Google ID-token verification (`google-auth`) first, an email magic link second, and never passwords. Sessions are
ours: only the SHA-256 of the token is stored, cookies are `HttpOnly; Secure; SameSite=Lax`, unsafe methods require
`Origin == PUBLIC_APP_URL`. Only Google-verified emails unlock free credits. Foreign resources return 404, not 403.

## Consequences
- Nothing to reset or leak; no second auth runtime. Cookies work with `EventSource`.
- We own session revocation (sign-out-everywhere must evict within 1 s through `NOTIFY`, gate 7) and abuse controls.
- Google's token verification must use an `httpx`-based transport (the lint rule bans `requests`).
- Personal data (email, name, avatar, Google `sub`) is tagged `GDPR[personal-data]`; Google is a processor (`GDPR[processor]`).
