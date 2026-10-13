# Email and password authentication specification (RM-202, #201)

Status: **specification, not yet implemented** (implementation: #203 registration and verification, #204 login, #205 recovery and
change). Decision of record: [ADR 0013](adr/0013-email-password-auth.md). Product source: owner request on #201 and the design
prototype `design/v3/login.html` (its eight-character check is a demo, not a policy). Existing methods are unchanged: Google
([GOOGLE-AUTH-SPEC.md](GOOGLE-AUTH-SPEC.md), ADR 0010) and the email magic link.

All routes are under `/api/auth`, take JSON with `extra="forbid"`, and require `Origin == PUBLIC_APP_URL` when unsafe (existing
middleware). Responses never contain a password, a hash or a token.

## 1. Routes

| Route | Auth | Success | Notes |
|---|---|---|---|
| `POST /api/auth/register` `{email, password}` | none | 202 `{}` always | Stores a pending registration and mails a link. Same response for a new address, an address with an account, and a pending one |
| `POST /api/auth/register/verify` `{token}` | none | 200 `MeOut` + session cookie | Creates the verified account, its credential and the signup credits, signs in. Existing account for the address: no credential is attached (section 4) |
| `POST /api/auth/register/resend` `{email}` | none | 202 `{}` always | Re-mails a pending registration (new token replaces the old) |
| `POST /api/auth/login` `{email, password}` | none | 200 `MeOut` + session cookie | Generic failure for every cause |
| `POST /api/auth/password/forgot` `{email}` | none | 202 `{}` always | Mails a reset link when an account exists; never says whether it does |
| `POST /api/auth/password/reset` `{token, password}` | none | 204 | Sets the credential (also the first one on a Google or magic-link account), revokes every session, signs nobody in |
| `POST /api/auth/password/change` `{current_password, new_password}` | session | 204 | Revokes every session including the caller's and clears the cookie; the caller logs in again |

## 2. Password policy (NIST SP 800-63B style, no composition rules)

- Unicode NFKC-normalised, then 10 to 128 characters and at most 256 UTF-8 bytes (bounds the hashing work). Whitespace is kept.
- Rejected with 422 `WEAK_PASSWORD` and a machine reason (`too_short`, `too_long`, `common`, `contains_email`): a bundled
  blocklist of common passwords (size and source decided in #203, licence stated there), and a password containing the address's
  local part. Nothing else is required (no mandatory symbols or digits).
- The same policy applies on register, reset and change; login accepts up to the maximum and never reveals which rule failed.

## 3. Storage

| Item | Rule |
|---|---|
| Hash | `pwdlib[argon2]` Argon2id, random salt, PHC string in `user_credential.password_hash`. Defaults `memory 19456 KiB, time 2, parallelism 1` (OWASP minimum), in settings; raise after measuring on the VPS. `verify_and_update` rehashes on a successful login |
| `user_credential` | `user_id` PK, FK to `app_user` **ON DELETE CASCADE**, `password_hash`, `updated_at`. `GDPR[personal-data]` |
| `auth_token` | `token_hash` (SHA-256 hex) PK, `purpose` (`register`\|`reset`), `email`, `user_id` (reset only, nullable FK cascade), `password_hash` (register only), `expires_at`, `used_at`, `created_at`. One live row per (email, purpose); a new request marks the old one used. `GDPR[personal-data]` |
| TTL | register 24 h, reset 30 min (settings). Purged one day after expiry or use (`GDPR[retention]`, extends the existing job) |
| Logs and telemetry | never the password, hash or token; the existing Sentry scrubber already redacts token-like URL parts and emails |
| Mail | through the existing injectable Resend client and queue; the queued job carries a **token that is removed from the job row after sending** (as `send_magic_link`, L-011), and a failed send retries without re-issuing the token |

## 4. Account linking and takeover rules

1. Registering an address never creates an account. Only using the mailed link does, and only if no account exists for the address.
2. If an account exists when the register link is used (made meanwhile by Google, magic link or a parallel registration), nothing is
   attached and the response says to use "forgot password". The pending hash is discarded.
3. A reset link may set the first credential on an existing account: it proves the same mailbox control that a magic link already
   accepts as sign-in, and it is started by the account's owner. It never merges two accounts.
4. A later Google sign-in with the same address links only under ADR 0010 (Gmail or matching `hd`); otherwise it asks for the magic link.
5. Signup credits are granted only when the verified account is created, once per account across providers.

## 5. Abuse controls

| Route | Per address | Per IP | Other |
|---|---|---|---|
| register, resend, forgot | 5 per hour | 20 per hour | mail sends are the cost being protected |
| login | 10 per 15 min | 50 per 15 min | not a lockout: attempts above the limit get 429 `RATE_LIMITED`, the correct password still works after the window |
| reset, verify | 10 per hour | 30 per hour | tokens are 256-bit, guessing is not the threat; this bounds load |

Hashing concurrency is capped (2) with `asyncio.to_thread`. An unknown address on login still performs one dummy verification so
response time does not distinguish it. Rate-limit decisions use the existing atomic Postgres upsert (no Redis).

## 6. Problem codes (added to `rm_contracts.problems` and blueprint section 2)

| Code | HTTP | When |
|---|---|---|
| `INVALID_CREDENTIALS` | 401 | any login failure, identical for wrong password, unknown address, no credential |
| `WEAK_PASSWORD` | 422 | policy failure with `reason` |
| `AUTH_TOKEN_INVALID` | 401 | register or reset token unknown, used, expired or wrong purpose |
| `RATE_LIMITED` | 429 | existing |

## 7. Tests the implementation issues must add (real Postgres)

Registration to verification to login to an authenticated API call; concurrent registration and concurrent verification create one
account and grant credits once; existing-address collision attaches nothing; wrong password, unknown address and a Google-only account
look identical (body and status); throttle then recovery; input bounds; expired, replayed, wrong-purpose and concurrently consumed
tokens; reset and change revoke sessions within the one-second gate and sign nobody in; non-enumeration on register, resend and
forgot; no secret in responses, logs or queue payloads after sending; erasure removes credentials and tokens; the existing Google and
magic-link tests unchanged.

## 8. Not decided here (owner)

Signup allowance and its expiry (#43), the final password-blocklist source, whether to add a second factor later, and the production
UI (Phase 2, #44).
