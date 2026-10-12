# Stripe integration specification (closes #127)

Status: specification, **awaiting owner review** (billing is a human-review area). It is the contract that billing (#14),
the VAT invoice work (#26) and disputes/refunds (#27) are implemented from; blueprint §3 *Stripe webhook lifecycle*,
*BLIK at launch* and *VAT invoices* stay the spec of record and are not repeated. *Confirmed* = in the blueprint with a source
or in the merged code; *inferred* = from vendor documentation or reasoning, to verify in the sandbox. The owner's local notes
are in `docs/STRIPE-INTEGRATION.md` (gitignored); no key, id or webhook secret is written into a committed file.

## 0. Preconditions (blockers)

- **B-003:** the CLI account has live access only; the owner grants sandbox access (`stripe login --project-name rent-monitor`).
  Agents use test mode only, never `--live`. No Stripe resource exists yet.
- **BLIK recurring activation** (`blik_payments` and `blik_recurring_payments`) is a Stripe-side request with lead time (#39). Card
  and the 30-day pass work without it.
- **D-03 VAT presentation** of the 100 zł price and the invoice treatment come from the accountant (#41). Prices are created in the
  sandbox first; final prices wait for D-03.

## 1. Catalog (names and purpose; ids live only in `.env` and the `plan` table)

| Product | Price | Mode | Env name | Purpose |
|---|---|---|---|---|
| RentMonitor Pro (monthly) | 100 PLN recurring, monthly | subscription | `STRIPE_PRICE_PRO_MONTHLY` | card or BLIK recurring, automatic renewal |
| RentMonitor Pro 30 days | 100 PLN one-time | payment | `STRIPE_PRICE_PRO_PASS_30D` | BLIK or card pass for banks without recurring BLIK |

- **Tidy-up needed:** `.env.example` also has `STRIPE_PRICE_ID_PRO`, documented as "same as `STRIPE_PRICE_PRO_MONTHLY`". Two names for
  one value will drift; the spec keeps `STRIPE_PRICE_PRO_MONTHLY` and `make seed` stores it on the `pro` plan row, so
  `STRIPE_PRICE_ID_PRO` is dropped in the billing PR.
- Tax behaviour (inclusive or exclusive) and whether Stripe Tax is used are D-03 and the accountant's call. Invoicing is done by
  Fakturownia, so the app does not use Stripe Tax or Stripe's invoice PDF as the legal document.
- Money rules: Stripe sends integer minor units; they are converted to `Decimal` at the boundary and never held as `float`.

## 2. Checkout, Portal and Dashboard settings

- **Checkout** is created server-side by the API for an authenticated user: `client_reference_id = user_id`, `customer` reused
  if `stripe_customer` exists, `metadata.product` = `pro_monthly` or `pro_pass_30d`, `tax_id_collection.enabled = true`,
  `locale = pl`, success/cancel URLs from `PUBLIC_APP_URL` only. BLIK needs `currency = pln`. Card and BLIK are offered on both
  modes; a recurring-BLIK failure (`recurring_not_supported_by_bank`) sends the user to the pass.
- **Paywall disclosure** (recurring BLIK mandate text, blueprint "Paywall disclosure") is shown before the redirect.
- **Customer Portal:** payment-method update (card and BLIK), cancel at period end, invoice history; no plan switching (one plan).
- **Dashboard:** Smart Retries on, "if all retries fail" = cancel the subscription (produces `customer.subscription.deleted`);
  Stripe's own receipt and invoice emails off (one document set; *inferred* to verify which emails the account sends).
- **Retry window vs grace (decision needed):** our grace is 7 days (`PAST_DUE_GRACE_DAYS`). Stripe's Smart Retries can be set to retry
  for 1 week up to 2 months (*inferred*). If Stripe keeps retrying for longer, a user loses Pro on day 7 while the subscription is
  still alive and may pay on day 12. Recommendation: set the retry window to **1 week** so final failure and `deleted` land at
  the end of the grace; otherwise state plainly that Pro ends on day 7 and a late payment restores it at once through `invoice.paid`.
- **Refunds and disputes** (#27): policy is the owner's. Spec default: a refund of the latest invoice or pass ends the matching
  period; a dispute marks the user `payment_issue` and keeps Pro until resolved. Both are decisions to confirm, not blueprint text.

## 3. Webhook endpoint (`POST /api/webhooks/stripe`)

1. Read the **raw body**; verify `Stripe-Signature` with `STRIPE_WEBHOOK_SECRET` (default 300 s tolerance) **before** any parsing;
   bad signature: 400 `INVALID_STRIPE_SIGNATURE`, nothing stored. The route is exempt from the Origin check (`/api/webhooks/`).
2. Claim the event: `INSERT INTO stripe_event (id, ...) ON CONFLICT DO NOTHING`; a conflict means duplicate, answer 200 without work.
3. Per-subscription serialisation by `pg_advisory_xact_lock(hashtextextended(subscription_id))`; for every subscription event
   **re-retrieve** the subscription from Stripe and write that current state, so a late `updated` cannot beat a newer `deleted`.
4. Allowance is granted only on `invoice.paid`, keyed by the invoice id (`usage_period.source_invoice_id` unique).
5. Allow-list of subscribed events: `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
   `checkout.session.async_payment_failed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`,
   `customer.subscription.deleted`, plus `charge.refunded` and `charge.dispute.created` with #27. Anything else is stored as `ignored`.
6. Return 200 after the transaction commits; any error returns 500 so Stripe retries. Handlers are idempotent, so a replay is safe.
7. **API version:** the account and the endpoint are pinned to `STRIPE_API_VERSION` (`2026-09-30.endive`) and every client call
   sends it. The SDK is pinned **exactly** and a unit test asserts it matches that version; which SDK release defaults to it is
   unconfirmed (ADR 0007 is still *proposed*, owner decision D-02). Use `context7` for the SDK surface when #14 starts.
8. Shapes that changed since `2025-03-31.basil`: `current_period_start/end` are on subscription items; an invoice's subscription is at
   `invoice.parent.subscription_details.subscription`.

## 4. State machine and entitlement

Unchanged from blueprint §3 and merged in `rm_core.entitlements`: Pro for `active`/`trialing` until `current_period_end + 48 h`
(fail closed), for `past_due` until `grace_until`, and for a covering `pass` period; everything else falls back to credits.
Pass stacking: two paid passes for one user extend to 60 days sequentially under a per-user advisory lock. A pass with
`payment_status != paid` grants nothing until `async_payment_succeeded`. A nightly `reconcile_subscriptions` re-reads every live
subscription from Stripe (#25).

## 5. Sandbox runbook (test mode only)

1. Owner: `stripe login --project-name rent-monitor`, then select the sandbox. Verify with `stripe config --list` and a read-only call.
2. Create the product and the two prices; put the price ids in the private `.env`; enable Portal, Smart Retries, the email settings.
3. `stripe listen --forward-to localhost:8000/api/webhooks/stripe` prints the signing secret for `STRIPE_WEBHOOK_SECRET`.
4. Test clocks (`scripts/stripe_clock_customer.py`) advance a customer through renewal and failed renewal without waiting a month.
5. Cards: Stripe's documented test cards for success, decline, 3-D Secure and attach-then-fail renewal; BLIK uses Stripe's documented test codes.
6. Reset: delete the test customers/clocks; the sandbox can be cleared from the Dashboard. Never point any of this at live keys.
7. Guard: the app refuses an `sk_live_` key unless `APP_ENV=production`, and tests refuse any Stripe key at all (fakes only).

## 6. Test plan

| Test (blueprint §4.6) | Level |
|---|---|
| `test_webhook_replay`, `test_webhook_out_of_order`, `test_webhook_concurrent_duplicate`, `test_subscription_events_adverse_order` | integration (Postgres) with a fake Stripe client and signed payloads |
| `test_grace_period`, `test_pass_grants_30_days`, `test_pass_unpaid_ignored`, `test_pass_parallel_stacks` | integration; time passed as a clock argument |
| `test_vat_invoice_idempotent` | integration with a fake Fakturownia client (#26) |
| signature verification on the raw body, tolerance, malformed and oversized bodies | unit |
| `test_blik_offered_in_checkout` | `e2e` marker, sandbox only, never in default CI |
| money and concurrency | `hypothesis` property tests for ledger/quota remain; add webhook ordering properties |

Release gates 2 (billing concurrency) and 3 (live BLIK recurring) use these tests plus one real sandbox run; gate 3 needs the activation.

## 7. GDPR and legal

`GDPR[processor]`: Stripe receives email, name, billing details and NIP. `GDPR[erasure]`: `delete_account` returns
`stripe_customer_id`; the caller deletes the customer at Stripe (already in `rm_core.privacy`). Invoices stay in Fakturownia for tax
reasons (retention per the accountant). `LEGAL[tax-invoice]` applies to the VAT invoice code (#26). No legal conclusion is drawn here.

## 8. Environment names and open items

Names in `.env.example`: `STRIPE_SECRET_KEY` (test mode only; use a restricted key limited to Checkout, Customers, Subscriptions,
Invoices, Billing Portal), `STRIPE_WEBHOOK_SECRET`, `STRIPE_API_VERSION`, `STRIPE_PRICE_PRO_MONTHLY`, `STRIPE_PRICE_PRO_PASS_30D`
(and the duplicate to drop). Agent tooling for Stripe needs Agent-tagged keys from 2026-10-31 (roadmap calendar).

Open decisions for the owner: D-02 SDK pin; D-03 VAT presentation and price tax behaviour; retry window vs 7-day grace (section 2);
refund and dispute policy (section 2); who emails the invoice (see `docs/RESEND-SPEC.md`); BLIK recurring activation (#39).
