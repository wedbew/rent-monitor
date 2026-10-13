# ADR 0013 - Email and password sign-in alongside Google and magic links

- **Status:** accepted - **Date:** 2026-10-14 - **Decided by:** maintainer (owner request, #201) - **Ticket:** RM-202
- **Supersedes:** the "never passwords" sentence of [ADR 0004](0004-google-first-auth-own-sessions.md) and blueprint section 2
  *Auth decision* ("Hard call: no passwords"). Everything else in ADR 0004 and ADR 0010 stands.

## Context
The owner asked for email and password registration and login next to Google sign-in (design prototype `design/v3/login.html`).
Magic links and Google stay. Passwords bring the work the blueprint avoided: hashing, recovery, throttling, enumeration and
account-takeover risks. This ADR fixes the rules so the three implementation issues (#203, #204, #205) cannot diverge.
The full contract is [`docs/PASSWORD-AUTH-SPEC.md`](../PASSWORD-AUTH-SPEC.md).

## Decision
- **Library:** `pwdlib[argon2]` (the additive path the blueprint named), Argon2id, unique random salt per hash, parameters in
  settings with a documented default, `verify_and_update` rehashes on login when parameters change. No plaintext or reversible
  storage, ever.
- **Proof of mailbox control before any account exists.** Registration creates *no account*: it stores a single-use pending
  registration (the Argon2id hash, never the password) and mails a link. The account, the credential and the signup credits appear
  only when that link is used. An attacker who registers someone else's address therefore gets nothing.
- **Never attach a credential by email alone (extends ADR 0010).** If an account already exists for the address when the link is
  used, the password is **not** attached; the person is told to use "forgot password". Recovery is the only path that sets a
  password on an existing account, and it requires the same mailbox proof, started by the account's owner.
- **Tokens:** 256-bit random, purpose-bound (`register`, `reset`), SHA-256 at rest, expiring, consumed atomically
  (`UPDATE ... WHERE used_at IS NULL AND expires_at > now() RETURNING`), at most one live token per address and purpose.
  Links carry the token in the URL fragment, as the magic link does.
- **No enumeration:** register, resend and forgot always answer 202 with the same body; unknown address, existing account and
  pending registration are indistinguishable by body, status or (within the throttle) timing. Login answers one generic
  `INVALID_CREDENTIALS` and performs a dummy hash for unknown addresses.
- **Throttling, not lockout:** per address and per IP through the existing atomic `rate_limit` upsert; a throttle never locks an
  account, so it cannot be used to deny service to its owner. Hashing runs off the event loop under a small concurrency cap.
- **Sessions:** a password reset or change revokes every session of the user (the existing revoke-all path and its NOTIFY, so cached
  principals drop within the one-second gate) and signs nobody in; the user logs in again.
- **Credits:** granted only when a verified account is created, once per account across all providers (the existing idempotent
  `ensure_credit_account`). The allowance value stays the owner's decision (#43).

## Consequences
- New tables (expand-only): `user_credential`, `auth_token`. Both are `GDPR[personal-data]`; credentials cascade on account erasure,
  tokens are purged one day after expiry or use (retention job extended in #203).
- New problem codes `INVALID_CREDENTIALS`, `WEAK_PASSWORD`, `AUTH_TOKEN_INVALID`.
- CONTEXT, the blueprint and the Google spec are updated in this PR; the production UI is Phase 2 (#44) and uses design v3 as context only.
- The old statement "nothing to hash, reset or leak" is gone: password storage is now an owned risk (L-019).
