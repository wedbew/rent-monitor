# ADR 0013 — Email and password sign-in alongside Google and the magic link

- **Status:** accepted (owner decision, 2026-10-14) · **Date:** 2026-10-14 · **Ticket:** RM-202 (slice 1 of #201)
- **Supersedes:** ADR 0004 on "never passwords" only. Everything else in ADR 0004 stands (own sessions, hashed tokens, cookie
  attributes, Origin check, 404 for foreign resources, Google keyed by `sub`).
- **Keeps:** ADR 0010 (Google links or creates accounts only where Google is authoritative). Extends its rule to passwords.
- **Status of the text below:** specification. Nothing is implemented; implementation is slices 2+ of #201. Values marked
  *(proposed)* are the author's choice inside the owner's decision and can be changed in review before code lands.

## Context
ADR 0004 chose "no passwords" to avoid hashing, reset and leak surface. The owner has decided that users without a Google
account, or who prefer one, can register with an email address and a password. We still own no second auth runtime: this is
additive code in `rm_api.auth` using `pwdlib[argon2]` (named in blueprint §2 as the planned additive path).

## Decision

### Methods after this ADR
Google (primary, ADR 0010 rules) · email magic link · **email + password**. All three end in the same server-side session
(`user_session`, hashed 32-byte cookie). The three methods can coexist on one user.

### Account-linking rule (extends ADR 0010): never attach by email alone
- A password credential is attached to a user only by proving control of the mailbox with a single-use mailed token **or** by
  an already signed-in session of that user. A typed email address is never evidence.
- **No pre-hijacking.** `register` creates no `app_user`. It stores a *pending registration* (address, Argon2id hash, token
  hash, expiry). The user, identity, credit account and signup grant are created only when the verification token is
  consumed. If a user with that address already exists when the token is consumed, the password is **not** attached, nothing is
  signed in, and the response is the same 401 as an invalid token; the legitimate owner uses forgot-password (below).
- **Forgot-password may set a first password** on an existing account (Google-only or magic-link) because consuming the reset
  token proves the same thing a magic link proves. It revokes every session of that user.
- A Google sign-in never links to a password account by address unless ADR 0010 allows it; a password account never gives a
  Google identity anything.
- Free signup credits unlock only after the address is verified (verification token consumed). The idempotency key stays
  `signup:<user_id>`, so a user with Google and a password gets the grant once.

### Endpoints (all `POST`, Origin check applies, all under `/api/auth/password/`)
| Route | Auth | Success | Notes |
|---|---|---|---|
| `register` `{email, password}` | public | 202, empty body, always | Same answer whether the address is new, pending or already registered (no enumeration). Mail differs: new/pending → verification link; existing user → a notice with a sign-in / reset hint and no link that changes anything |
| `verify` `{token}` | public | 200 `MeOut` + session cookie | Single-use; creates the user and signs in |
| `resend` `{email}` | public | 202, always | Re-issues the verification token for a pending registration (invalidates the previous one); no-op otherwise |
| `login` `{email, password}` | public | 200 `MeOut` + session cookie | Unknown address, wrong password and no password credential give one 401 `INVALID_CREDENTIALS` after a dummy Argon2 verify (constant work). Correct password on a still-pending registration → 403 `EMAIL_NOT_VERIFIED` |
| `forgot` `{email}` | public | 202, always | Mails a reset link only if a user with a verified address exists |
| `reset` `{token, password}` | public | 204 | Sets the hash, **revokes all sessions** of the user (NOTIFY `user:<id>`), does not sign in |
| `change` `{current_password, new_password}` | session | 204 | If the user has no password yet, `current_password` must be omitted and the session must be younger than 15 min *(proposed)*, otherwise 401 `UNAUTHENTICATED` with a re-login hint; on success revokes **all other** sessions |

Existing `signout`, `signout-all`, `sessions` are unchanged. Links are `PUBLIC_APP_URL/login/verify#t=<token>` and
`PUBLIC_APP_URL/login/reset#t=<token>` (fragment, same reason as the magic link: scanners and proxies never see it); the page
requires a button press before the POST, so prefetching cannot consume the token.

### Password policy (NIST SP 800-63B style: length and denylist, no composition rules)
- NFKC-normalised before hashing and before the checks; whitespace is kept (no trimming).
- Minimum **10** characters *(proposed)*; maximum **128** characters **and** **256 UTF-8 bytes** (bounds Argon2 input and
  request size; rejected with a stable code, never truncated).
- No composition rules, no forced rotation, paste allowed.
- Rejected with 422 `PASSWORD_POLICY_VIOLATION` and a `reasons` list of stable keys (`too_short`, `too_long`, `too_many_bytes`,
  `common_password`, `contains_email`, `repeated_character`): a bundled denylist of the 10,000 most common passwords
  (case-insensitive, local file, **no network call and no password ever sent to a third party**), the address's local part,
  the product name, and a single repeated character. Breach-corpus checking (k-anonymity API) is deferred: L-017.
- The password never appears in logs, errors, `audit_event`, Sentry or job arguments. Contract fields use `SecretStr`.

### Argon2id *(proposed; OWASP "minimum" profile, measured on the VPS in slice 2 and adjusted)*
`pwdlib` Argon2id: memory **19 MiB** (`m=19456`), iterations **2**, parallelism **1**, 16-byte salt, 32-byte output. Hashes are
stored in the PHC string, so parameters can be raised later; `login` rehashes on success when the stored parameters are weaker
(`pwdlib.verify_and_update`). Hashing runs in `asyncio.to_thread` behind a process-wide semaphore of **2** *(proposed)* so a login
burst cannot exhaust the API container's memory (blueprint §1 matrix); a waiter times out after 5 s with 503 `NOT_READY`.
No pepper in this slice (a pepper needs a key-rotation story; not decided).

### Token lifetimes
All tokens: 32 random bytes, only SHA-256 stored, single use by one `UPDATE … WHERE used_at IS NULL AND expires_at > now()`.
| Token | Lifetime |
|---|---|
| Verification (register/resend) | **24 hours** *(proposed)*; pending registrations purged 1 day after expiry |
| Password reset | **30 minutes** |
| Magic link | 30 minutes (unchanged) |
| Session | 30 days, sliding (unchanged) |
Issuing a new token of a kind invalidates the older ones of that kind for the same address.

### Throttles (atomic `rate_limit` upsert, hashed keys, as RM-12; exceeding → 429 `RATE_LIMITED` + `Retry-After`)
| Action | Per address | Per IP |
|---|---|---|
| register + resend (shared bucket) | 5 / hour | 20 / hour |
| login (failed attempts only) | 10 / 15 min | 30 / 15 min |
| forgot | 3 / hour | 20 / hour |
| verify + reset token attempts | — | 20 / hour |
| change (wrong `current_password`) | 5 / 15 min per user | — |
No account lockout (a lockout lets anyone deny service to a victim); throttling plus uniform responses instead. The per-IP limits
depend on trusting the proxy (L-012). A throttled request is answered before any hashing.

### Error codes (added to `rm_contracts.problems` first, then the blueprint §2 table)
`INVALID_CREDENTIALS` 401 · `EMAIL_NOT_VERIFIED` 403 (exists) · `PASSWORD_POLICY_VIOLATION` 422 · `VERIFICATION_TOKEN_INVALID` 401 ·
`PASSWORD_RESET_TOKEN_INVALID` 401 · `CURRENT_PASSWORD_INVALID` 403 · `RATE_LIMITED` (exists) · `VALIDATION_ERROR` (exists, for
shape and size violations before the policy runs).

### Data and tags (implementation will tag these)
New tables in slice 2 (expand-only): `password_credential(user_id, hash, updated_at)` and `pending_registration(email, hash,
token_hash, expires_at)`. `GDPR[personal-data]` on both; erasure by cascade on `app_user` (pending rows by TTL purge);
`GDPR[retention]` in `rm_core.privacy.purge_expired`; `GDPR[processor]` Resend for the two new mails. The export (`GET /api/me/export`)
states that a password credential exists, never the hash.

## Consequences
- Resolves the "B2B customer wants passwords" path early; adds a reset flow, pending registrations, a denylist asset and
  Argon2 CPU/memory cost (bounded by the semaphore) to own.
- Adds one dependency in slice 2: `pwdlib[argon2]` for `rm-api` (justification in that PR; standard library has no Argon2).
- Anti-enumeration costs UX: "check your inbox" is shown even for addresses that exist.
- Blueprint §2 *Auth decision*, route map and error table, `docs/GOOGLE-AUTH-SPEC.md` and `CONTEXT.md` are updated with this ADR.
- Tests required in later slices, named now: pre-hijack (register for an existing address attaches nothing), constant-work login
  for unknown/known addresses, concurrent verify gives one user, reset revokes all sessions in a second process within 1 s
  (gate 7), no password in logs, policy boundaries (10/128 chars, 256 bytes, denylist), hash upgrade on login.
