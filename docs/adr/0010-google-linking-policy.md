# ADR 0010 - Google sign-in links or creates accounts only for addresses Google is authoritative for

- **Status:** accepted - **Date:** 2026-10-12 - **Decided by:** maintainer (owner decision D-13) - **Ticket:** RM-12
- **Amends:** blueprint section 2 *Auth decision*, rule 6; `docs/GOOGLE-AUTH-SPEC.md` section 3

## Context
The blueprint links a Google sign-in to an existing account with the same address whenever `email_verified` is true. Google's
documentation says it can vouch for an address only when it ends in `@gmail.com` or the token has an `hd` claim (a Google
Workspace account); for any other address it "is not authoritative" and recommends an extra check. Someone who controls a Google
account registered with an address on a domain they control, or one the real owner has lost, would otherwise take over an account
that holds credits and a subscription. The spec's first draft of option (b) had the `hd` condition backwards.

## Decision
- Auto-link and auto-create **only** when the address ends in `@gmail.com`, or the `hd` claim equals the address's own domain.
- For every other address, a Google sign-in without an existing Google identity for that `sub` is refused with 401
  `EMAIL_CONFIRMATION_REQUIRED`; nothing is created or linked, and the SPA offers the magic link. A returning `sub` is always let in
  (identity is the `sub`, never the address).
- `googlemail.com` and other aliases are not treated as `@gmail.com`; they use the magic link.

## Consequences
- Users with a Google account on a non-Gmail, non-Workspace address sign in by magic link (an extra step, once).
- A magic-link user and a later Google sign-in with the same address link only when Google is authoritative for it.
- No schema change. Tests cover refusal without side effects, Workspace `hd` matching, a mismatching `hd`, and returning users.
