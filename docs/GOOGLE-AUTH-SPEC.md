# Google sign-in and session specification (RM-12, closes #130)

Status: implemented in RM-12 and **awaiting owner review** (auth is a human-review area, `rules/pull-requests.md`).
Spec of record is blueprint §2 *Auth decision*; this file records what was built from it, where it differs, and the
decisions only the owner can make. Confirmed = covered by a named test in `tests/`; inferred = reasoning, not yet
exercised against live Google.

## 1. Flow

1. The SPA loads Google Identity Services and receives a signed ID token (`credential`) from the button or One Tap.
   Callback mode only, so there is no redirect URI and **no client secret on the server** (`GOOGLE_CLIENT_SECRET` is
   unused by this path).
2. `POST /api/auth/google {credential}` (Origin must equal `PUBLIC_APP_URL`).
3. The server verifies the token, finds or creates the user, creates a session, ensures the credit account and sets the
   session cookie. The response is `MeOut` (id, email, name, avatar_url, role, email_verified).
4. Email is the second method: `POST /api/auth/email/start` then `POST /api/auth/email/verify` (section 5).

## 2. Verification rules (confirmed: `tests/unit/test_google_verifier.py`, `test_auth.py`)

| Rule | Result |
|---|---|
| Signature by a published Google key, `RS256` only (`alg=none` and unknown algorithms refused) | else 401 `INVALID_GOOGLE_TOKEN` |
| `aud` equals `GOOGLE_CLIENT_ID`; `iss` is `accounts.google.com` or `https://accounts.google.com`; not expired (10 s skew) | else 401 `INVALID_GOOGLE_TOKEN` |
| Claims bounded and typed: `sub` 1-255, `email` 3-254, `name` ≤ 200, `picture` ≤ 500; unknown claims ignored | else 401 `INVALID_GOOGLE_TOKEN` |
| `email_verified` true (or the string `"true"`) | else 401 `GOOGLE_EMAIL_UNVERIFIED`; no row is created |
| Google's certificates unreachable and none cached, or `GOOGLE_CLIENT_ID` empty | 503 `NOT_READY` (not the caller's fault) |

Certificates come from `https://www.googleapis.com/oauth2/v1/certs` over the shared `httpx` client (5 s timeout, 64 KB
cap), cached for the `Cache-Control` max-age (60 s to 24 h), refreshed once on an unknown key id, and the last good set
is served if a refresh fails. One fetch for any number of concurrent callers.

## 3. Identity model and linking policy (confirmed: `test_google_links_existing_email`)

- A Google user is keyed by `(provider='google', subject=sub)`, **never by email**. A returning `sub` whose email changed
  is still the same user.
- A first Google sign-in with a verified email joins the existing user with that address (one user, two identities) or
  creates one. An unverified email never links and never creates.
- Creation and linking are single atomic statements, so eight concurrent first sign-ins make one user, one identity and
  one credit grant.
- The avatar URL is stored only if it is `https` and ≤ 500 characters.

**Owner decision needed (D-13, not blocking):** a second Google `sub` that carries the same verified email also joins
that user (blueprint behaviour, covered by tests). For addresses on non-Gmail domains, Google's guarantee about the
address is weaker than for `@gmail.com`. Options: (a) keep the blueprint behaviour; (b) auto-link only when the token
has no `hd` claim or the address is `@gmail.com`, otherwise require a magic-link confirmation first. Recommendation: (a)
for launch, revisit if abuse appears. Not implemented as (b) because it changes the blueprint.

## 4. Sessions (confirmed: `tests/integration/test_auth.py`)

- Cookie `rm_session`, `__Host-rm_session` in production (the prefix is added by code; do not put it in
  `SESSION_COOKIE_NAME`). `HttpOnly; Secure; SameSite=Lax; Path=/`, no `Domain`, 30 days. Secure is off only when
  `APP_ENV=development` (plain http).
- 32 random bytes; Postgres stores only the SHA-256. IP (≤ 45) and user agent (≤ 300) are stored for the session list.
- `current_principal` resolves the cookie through a 30 s in-process cache, then Postgres (unexpired session joined to its
  user). The expiry slides by 30 days at most once a day, on a cache miss.
- Sign-out deletes the row; sign-out-everywhere deletes all rows of the user. Both `NOTIFY session_revoked` (payload
  `token:<hash>` or `user:<id>`); each API process holds one `LISTEN` connection and drops the cached principals.
  **Gate 7 evidence:** with the principal cached in a second process, revocation is seen there in under 1 s
  (`test_sign_out_everywhere_evicts_cached_sessions_in_all_processes`). If the listener connection drops, the cache is
  flushed on reconnect (`test_a_dropped_listener_connection_flushes_the_cache_on_reconnect`) and the stated worst case
  is the 30 s TTL.
- `GET /api/auth/sessions` lists the caller's own sessions (max 50) and marks the current one.
- Unsafe methods on `/api/*` need `Origin == PUBLIC_APP_URL`, otherwise 403 `ORIGIN_NOT_ALLOWED`; `/api/webhooks/`
  is exempt because Stripe authenticates by signature.

## 5. Magic link (confirmed)

- `start`: always 204 (no account enumeration). Limits through one atomic upsert: 5 per hour per address, 20 per hour per
  IP, then 429 `RATE_LIMITED` with `Retry-After` (15 concurrent requests for one address give exactly 5 successes). The
  link is `PUBLIC_APP_URL/login/email#t=<token>`: a fragment, so servers, proxies and mail scanners never see it.
- The token is 32 random bytes; only its SHA-256 is stored; valid 30 minutes; single use by one
  `UPDATE ... WHERE used_at IS NULL AND expires_at > now() RETURNING` (ten concurrent verifies give one 200 and nine 401).
- The mail is a Procrastinate job deferred **by name** from the API (`rm_worker.tasks.email.send_magic_link`, queue `ops`,
  4 attempts at 9, 27 and 81 s, **transient errors only** (network, 429, 5xx); a bad key, an unverified domain or the
  onboarding sender in production fails at once, so a dead link is never retried and the token does not linger). Live delivery is untested until the Resend key and domain are verified (B-004).
  In production the worker refuses to send without a key or from the Resend onboarding sender.

## 6. Signup grant

`ensure_credit_account(..., verified=True)` runs on every successful sign-in and grants `FREE_SIGNUP_CREDITS` (3) exactly
once per user, across Google and email identities (idempotency key `signup:<user_id>`).

## 7. Where this differs from the blueprint

| Blueprint | Built | Why |
|---|---|---|
| `google.oauth2.id_token` over `requests` | `google.auth.jwt.decode` with certificates fetched by `httpx` | `requests` is banned in `services/` (CONTEXT G4) and blocks the event loop; also lets tests inject keys with no network |
| Rate-limit key `ml:email:<address>` | SHA-256 of `<scope>:<subject>` | the table would otherwise hold addresses and IPs; rows purged after one day |
| Pool opened at API startup | Job queue opens on first use | startup must not hang when Postgres is down (`/readyz` reports it) |
| Cookie name `__Host-rm_session` everywhere | prefix in production only | `__Host-` requires HTTPS; local development is plain http |

New problem codes (added to blueprint §2 error table): `UNAUTHENTICATED`, `RATE_LIMITED`, `ORIGIN_NOT_ALLOWED`; the
existing `INVALID_GOOGLE_TOKEN`, `GOOGLE_EMAIL_UNVERIFIED`, `MAGIC_LINK_INVALID` are now listed there too.

## 8. GDPR and legal tags

`GDPR[processor]` Google (token, email, name, picture) and Resend (recipient and link); `GDPR[personal-data]`
`app_user`, `auth_identity`, `user_session` (ip, user agent), `login_token`, and the request-scoped `Principal`;
`GDPR[retention]` sessions 7 days after expiry, login tokens 1 day after use or expiry, rate-limit rows 1 day after their
window (all in `rm_core.privacy.purge_expired`); `GDPR[erasure]` by cascade on `app_user`. No `LEGAL[...]` tags apply.
Register: L-011 (token in job arguments), L-012 (client IP behind the proxy).

## 9. Owner checklist (nothing here blocks local work)

1. Google Cloud console: authorised JavaScript origins for the real domain and `http://localhost`; consent screen to
   "In production" one week before launch (blueprint §5). Details are in the owner's local handoff notes.
2. A Resend key and a verified sending domain for real delivery (B-004, B-005); until then production refuses to send.
3. Decide D-13 above.
4. Deploy: make uvicorn trust the proxy (L-012) before relying on the per-IP limit.
