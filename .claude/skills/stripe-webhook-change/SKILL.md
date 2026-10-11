---
name: stripe-webhook-change
description: Change Stripe webhook, Checkout, pass, entitlement or VAT-outbox behaviour with idempotency, ordering and test-clock evidence. Human approval required.
---

**Sensitive area: comment on the PR and wait for a human before merging.** Use `context7` for current Stripe SDK/API shapes (pinned `STRIPE_API_VERSION`); sandbox keys only.

- Verify the signature on the **raw body** before parsing; claim the event id (`stripe_event` PK) in the same transaction as side effects; handlers re-retrieve the object under a per-subscription lock (blueprint §3, §4.5 c).
- Allowance only on `invoice.paid` keyed by invoice id; passes stack under a per-user advisory lock; `has_pro` fails closed 48 h after period end.
- Required tests (blueprint §4.6): signature, replay, out-of-order, grace period, concurrent duplicate, adverse order, pass stacking/parallel, VAT idempotency. Add hypothesis/concurrency tests, not only happy paths.
- Local proof: `stripe listen`, test clock advance, failed-renewal card, `stripe events resend`; paste results in the PR.
- Money is `Decimal`/`NUMERIC`; tag `LEGAL[tax-invoice]` / `GDPR[processor]` where applicable.
