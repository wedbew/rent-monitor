# Paddle integration — pilot report packs

**Date:** 2026-10-13. **State:** implementation specification; no Paddle integration implemented or
provider account verified by this document. Owner-selected pilot direction: one-time purchases of
**1, 5 or 10 reports**, without subscriptions. Technical defaults and recommended prices below are
proposals. See [billing research](BILLING-ALTERNATIVES.md) and limitations L-015/L-016.

This is the pilot billing design. The subscription/pass sections in [BLUEPRINT.md](BLUEPRINT.md),
[STRIPE-SPEC.md](STRIPE-SPEC.md) and ADR 0005 describe the earlier direction; their non-billing
invariants still apply. Before billing code merges, reconcile those contracts and record an ADR with
the implementation issue number. This file does not claim launch readiness or accountant approval.

## 1. Products and pricing

Sell software-generated reports, not transferable money, vouchers, brokerage or investment services.
Explain the actual yield/IRR/Max Bid/ranking features to Paddle during onboarding; a description alone
does not establish product acceptance. Paddle restricts investment advice and stored value. Obtain
written product approval, including prepaid report entitlements and data-rights information.
[Paddle acceptable-use policy](https://www.paddle.com/help/start/intro-to-paddle/what-am-i-not-allowed-to-sell-on-paddle).

| Internal code | Checkout label | Reports granted | Owner's suggested gross price | Recommended gross price |
|---|---|---:|---:|---:|
| `reports_1` | 1 raport | 1 | 5 PLN | **10 PLN** |
| `reports_5` | 5 raportów | 5 | 40 PLN | **40 PLN** |
| `reports_10` | 10 raportów | 10 | 70 PLN | **70 PLN** |

Recommendation: 10/40/70 PLN, with per-report prices 10/8/7 PLN. At 5 PLN for one report, five individual
purchases cost 25 PLN, cheaper than the 40 PLN five-pack; ten cost 50 PLN, cheaper than the 70 PLN ten-pack.
**Final catalog prices require the owner's choice; do not provision recommended prices as approved.**

Paddle publishes 5% + US$0.50 per checkout transaction and invites sellers of products below US$10
to discuss bespoke pricing. All proposed packs are low-value purchases; confirm the actual account fee
and any minimum before launch. [Paddle pricing](https://www.paddle.com/pricing).

Illustration using **assumed** US$1 = 4 PLN and 23% customer VAT, not a current exchange-rate quote or
confirmed tax treatment. Approximate amount after customer VAT and headline fee, before AI, payout,
refund, accounting and support costs:

| Gross paid | Illustrative fee | Remaining before operating costs | Remaining per report |
|---:|---:|---:|---:|
| 5 PLN / 1 report | 2.25 PLN | 1.82 PLN | 1.82 PLN |
| 10 PLN / 1 report | 2.50 PLN | 5.63 PLN | 5.63 PLN |
| 40 PLN / 5 reports | 4.00 PLN | 28.52 PLN | 5.70 PLN |
| 70 PLN / 10 reports | 5.50 PLN | 51.41 PLN | 5.14 PLN |

Do not assess margin from infrastructure alone: per-report AI cost remains unmeasured (L-003). Keep
AI spend caps; measure successful, degraded and failed report costs before changing pack discounts.

### Proposed pilot product rules

- One report entitlement buys one **standard `deal_audit`** for one sale listing. Existing report views,
  downloads and retries of the same API request do not spend another entitlement. A deliberately new
  analysis of a listing is another report; use the audit endpoint's idempotency rules to distinguish it.
- Packs add together. Suggested default: unused reports do not expire. No renewal, monthly allowance,
  Pro membership, 30-day access period, proration, trial or subscription customer portal.
- Reserve one unit when the audit is accepted. Capture on the existing successful terminal statuses,
  including `succeeded_degraded`; disclose missing inputs. Release on failure, rejection or cancellation,
  preserving RENT and fractional-ownership invariants. Engine success rules are not changed here.
- Analyst/redesign extras remain outside this pilot proposal. The current ledger charges analyst audits
  two units; never advertise “one report” while silently spending two. Reject unsupported feature requests
  before reservation. Paid standard reports must not require `is_pro`.
- The current setting grants three signup reports. That makes a one-report purchase unnecessary for
  many pilot users. Recommendation: make the paid pilot signup grant **0** and show a sample report instead;
  owner decision required. Preserve existing granted credits, and do not change this setting silently.
- Report availability, account closure, unused entitlements and consumer withdrawal/refund terms must
  be described consistently in checkout and the app. Support requests cannot be denied solely by an
  automated “used pack” rule; Paddle/consumer obligations take precedence over product defaults.

## 2. Paddle catalog and environment

Use **Paddle Billing**, separate sandbox/live catalogs. Prefer three catalog products, each with one
one-time PLN price: transparent invoice labels and a simple internal pack mapping. Product tax category
must match the service and be confirmed during onboarding. Price fields: `billing_cycle: null`,
`trial_period: null`, `tax_mode: "internal"`, `unit_price.currency_code: "PLN"`, string minor-unit amount,
`quantity.minimum = quantity.maximum = 1`. For the recommended prices, the amounts would be `"1000"`,
`"4000"`, `"7000"`; these are illustrative until approved. Changing a price creates a new catalog version;
keep old price mappings to recognise historical payments. [Create a price](https://developer.paddle.com/api-reference/prices/create-price/).

Proposed names (add to `rm_core.settings`, `.env.example`, deployment secrets and blueprint §4.2 only
in the implementation change; no real credentials here):

| Setting | Source / default |
|---|---|
| `BILLING_PROVIDER` | `disabled` locally; `paddle` after configuration |
| `PADDLE_ENVIRONMENT` | `sandbox` locally; `live` only in production |
| `PADDLE_API_KEY` | Secret API key from the selected environment; least required permissions |
| `PADDLE_WEBHOOK_SECRET` | Secret belonging to that notification destination |
| `PADDLE_CLIENT_TOKEN` | Public client-side token for future Paddle.js checkout; never the API key |
| `PADDLE_PRICE_REPORTS_1` | Selected environment's approved `pri_...` id |
| `PADDLE_PRICE_REPORTS_5` | Selected environment's approved `pri_...` id |
| `PADDLE_PRICE_REPORTS_10` | Selected environment's approved `pri_...` id |

Use `https://sandbox-api.paddle.com` for sandbox and `https://api.paddle.com` for live, selected from
the enum, not an arbitrary URL setting. Bearer API key, `Paddle-Version: 1`. `PUBLIC_APP_URL` remains
the only source of app redirects. Validate all three prices against catalog snapshots before enabling
sales. Startup in disabled mode must work without any Paddle credentials. Refuse mixed environments;
test suites use fakes and never accept live credentials.

Implement an injectable async `PaddleClient` using the existing `httpx` dependency. Proposed timeouts:
connect 3 s, overall request 10 s; bounded retries for reads (429/5xx, honour Retry-After). No blind retry
of transaction/refund creation after an ambiguous timeout. Minimum methods: create/get/list transaction,
get price/product, list/get adjustments, create full refund, get transaction invoice link. Add customer
methods only if necessary; the pilot can let Checkout create the buyer record and store its id after payment.
API keys need transaction/price/product/adjustment read, transaction write, and adjustment write only
if app-driven refunds are included. Catalog provisioning may be done in Dashboard with a separate key.

## 3. Checkout and API contract

Proposed routes (register schemas with `ConfigDict(extra="forbid")`, typed responses and problem codes
before implementation; regenerate OpenAPI):

| Route | Authentication | Contract |
|---|---|---|
| `GET /api/billing/packs` | session | Active codes, report counts, gross PLN prices and catalog version |
| `POST /api/billing/checkout` | verified session + same-origin check | `{pack_code}` plus `Idempotency-Key` UUID; returns purchase id, transaction id and checkout URL |
| `GET /api/billing/purchases` | session | Paginated own purchases and grant/refund state; no raw payload |
| `GET /api/billing/purchases/{id}` | session | Own purchase status, granted units and processing state |
| `GET /api/billing/purchases/{id}/invoice` | session | Short-lived invoice URL obtained on demand from Paddle |
| `POST /api/webhooks/paddle` | Paddle signature only | Durable event receipt; exempt exactly this path from Origin/session checks |

Foreign purchase ids return 404. Rate-limit checkout creation per user; recommended starting limit
5/minute and 20/hour. Browser-supplied amounts, report counts, price ids, user ids, discount ids or
redirect URLs are never accepted. Quantity is one pack; pack size is not Checkout quantity. Disable
discounts, quantity changes and upsells for the pilot and validate the completed transaction regardless
of UI restrictions. Buyer name/address/NIP belong in Paddle checkout, not in our request logs.

Checkout sequence:

1. Validate verified user, active catalog and idempotency key. Insert a durable `billing_purchase` with
   server-generated UUID, catalog/version/count/price snapshot and a random high-entropy checkout-binding
   token (store its hash). Unique `(user_id, request_key)`; same key with another pack returns 409.
2. Commit the purchase intent before the network call. Claim creation with a short transaction/lease so
   concurrent requests cannot create multiple transactions. Never hold a DB row lock across HTTP.
3. `POST /transactions` with an automatically collected one-time item. Conceptual request:

   ```json
   {
     "items": [{"price_id": "pri_SELECTED_SERVER_SIDE", "quantity": 1}],
     "collection_mode": "automatic",
     "currency_code": "PLN",
     "custom_data": {"purchase_id": "SERVER_UUID", "binding": "SERVER_RANDOM_TOKEN"}
   }
   ```

   Save `data.id` and `data.checkout.url` against the purchase; never match accounts by buyer email.
   A draft transaction may collect buyer details in Checkout. No recurring price or subscription id is
   valid for a report pack. [Create a transaction](https://developer.paddle.com/api-reference/transactions/create-transaction/).
4. Return the existing transaction on repeated requests. If creation times out after Paddle might have
   accepted it, set `creation_unknown`, return a recoverable processing response, and reconcile before
   another POST. Use verified webhook binding or a bounded paginated transaction scan to recover it;
   do not assume Paddle filters by custom data or supports an undocumented idempotency header.
   Never replace an unknown attempt automatically. Multiple matching transactions require support review.
5. In Phase 2, open the returned transaction with Paddle.js `Paddle.Checkout.open({transactionId})`, or
   use its checkout URL. The URL relies on an approved **default payment-link page on our domain that
   loads Paddle.js**; it is not a standalone hosted payment page requiring no app work. Configure a
   `/pay` page and success page with the correct environment/client token, authorised domains and CSP.
   No frontend files are changed in Phase 1. [Default payment link](https://developer.paddle.com/build/transactions/default-payment-link/),
   [open Checkout](https://developer.paddle.com/paddle-js/methods/paddle-checkout-open/).
6. Browser success means “payment processing”; poll our purchase endpoint with backoff until credited,
   failed or review-required. Never grant or launch an audit from a browser callback. BLIK authorisation
   may precede completed capture by up to ten minutes. [BLIK](https://developer.paddle.com/concepts/payment-methods/blik/).

Missing webhook delivery must not prompt another payment. Show the purchase reference and support path.
If the user deletes their account while payment is pending, late completion enters refund/manual review;
it cannot recreate the user or grant to an account matched by email.

## 4. Persistence and ledger changes

> **Slice 2 built (RM-216):** `report_credit_lot` and `report_credit_allocation`, lot-aware `reserve`/`settle`, the fixed lock order and a lot check in the nightly job. `billing_pack`, `billing_purchase`, `billing_event`, `billing_adjustment` and `refund_revoke` arrive with #217-#219. A frozen lot stays in the balance but cannot be spent.

Keep the existing `credit_account`/append-only `credit_ledger`; expose a public `grant_paid_reports`
service using `CreditReason.topup`, not an admin adjustment or direct balance mutation. The pilot creates
no Subscription or UsagePeriod. Report balances are integer units; money snapshots use Decimal/NUMERIC
or validated integer minor units converted at the boundary. UTC timestamps only.

Proposed schema, all in `app` through Alembic:

| Table | Required fields / constraints |
|---|---|
| `billing_pack` | composite PK (code, catalog version, environment); reports CHECK in (1,5,10); product/price ids; currency PLN; positive gross amount; active; unique environment+price id; at most one active version per code/environment; immutable sold version |
| `billing_purchase` | UUID PK; nullable retained account reference; original owner pseudonymous accounting reference; request key; pack/version/count/price snapshots; binding hash; provider transaction id UNIQUE per environment; customer id; provider status; local processing state; grant ledger id UNIQUE; paid/granted/refunded timestamps; retry lease and sanitized error code |
| `billing_event` | environment+event_id UNIQUE; notification id for diagnostics; type/occurred_at/received_at; bounded JSONB payload; pending/processed/ignored/review/failed; attempts, lease, sanitized error; indexes for pending work |
| `report_credit_lot` | grant source/key UNIQUE; optional purchase FK UNIQUE; user FK; granted, available, reserved, consumed, revoked nonnegative counters; CHECK sum equals granted; freeze state; FIFO timestamp |
| `report_credit_allocation` | audit id + lot id UNIQUE; units; reserved/captured/released/revoked state; FKs and indexes for in-flight/refund queries |
| `billing_adjustment` | environment+adjustment id UNIQUE; purchase FK; action/status; related reversal id; original-currency totals; applied revoked units; consumed-units review count; timestamps and processing state |

Lots track provenance for refunding one pack without taking credits from another purchase or from signup
grants. They are not a second balance authority: total spendable lot units must equal `credit_account.balance`
(frozen available units are included in that balance but excluded from reservations). Ledger sums must also
equal that balance. Materialise lots for **all** grants, including signup/admin/release semantics, not only
Paddle topups. Releases restore the original allocation rather than creating a new grant lot.

Migration: inspect existing rows, preserve ledger history, and backfill current non-paid balances with
explicit migration lots; record prior consumption separately instead of fabricating historical purchase
provenance. Active reservations need allocations before enabling pack refunds. Block activation if old
subscription/pass periods or unclassified paid credits exist; migrate them explicitly rather than ignore
them. Do not drop Stripe tables/columns or modify historical ledger rows in the first migration.

All credit operations use one consistent per-user lock order: advisory user lock → credit_account → lots
in FIFO order → audit/allocation or purchase/adjustment rows as applicable. Update `reserve`,
`record_reservation`, `settle`, signup grants, admin adjustments and the reconciler together; no code path
may lock an audit first and then wait for this user lock. A standard report reserves one available unit;
capture moves reserved → consumed, failure moves reserved → available. Both ledger and lot/allocation
updates commit atomically. Existing invariant/concurrency tests remain.

## 5. Webhook receipt and payment grant

Subscribe to `transaction.completed`, `transaction.payment_failed`, `transaction.canceled`,
`transaction.updated`, `adjustment.created` and `adjustment.updated`. Do not subscribe to subscription
events for the pilot. Use completed transactions for grants; other transaction notifications request a
fresh read rather than overwrite newer state.

Receipt handler:

1. Limit raw body to a proposed 256 KiB, no body transforms. Verify `Paddle-Signature`: `ts` and any `h1`
   values, HMAC-SHA256 of `timestamp + ':' + raw_body`, constant-time comparison, destination secret.
   Apply a 5-second timestamp tolerance (Paddle SDK default) and synchronized server clock; test future
   and old signatures, malformed headers and secret rotation. Parse JSON only after verification.
   [Paddle signature verification](https://developer.paddle.com/webhooks/about/signature-verification/).
2. Insert by **event id**, not notification id. Commit event and durable worker enqueue together where
   supported; otherwise the pending-event sweeper is the guaranteed recovery path. Return 200 after
   durable receipt, including duplicates; database/storage failure returns 5xx. Target <1 second local
   handling and stay within Paddle's five-second acknowledgement window. Do not call Paddle here.
   [Webhook delivery](https://developer.paddle.com/webhooks/about/respond-to-webhooks/).
3. A billing worker claims pending rows with a lease/`SKIP LOCKED`, retrieves the current transaction and
   adjustments, then applies effects under per-user and per-purchase serialization. Retry transient errors
   with backoff; alert permanent validation errors and exhausted retries. Claims recover after worker death.

Before granting, require: correct environment; locally linked transaction or verified binding recovery;
current `status == completed`; exactly one known price at quantity one; original catalog version;
PLN total equal to the approved gross snapshot; no unexpected discount, recurring item or subscription;
verified original payment and current adjustment state; live account. Validate provider price/product
and purchased units from the server snapshot, never `custom_data.reports`. A mismatch is `review`,
grants zero, and alerts support to resolve the paid customer fairly.

Atomic application: ensure account → insert grant ledger with key `paddle:{environment}:{txn_id}:grant`
and delta 1/5/10 → update cached balance → create lot → mark purchase granted → mark event processed.
Unique transaction, ledger key and purchase lot enforce exactly-once effects across webhook and
reconciliation workers. If fully refunded before the grant arrives, record the payment and full reversal
together with net zero available units; a stale completed event cannot resurrect reversed credits.

Do not regress a completed transaction on a late payment-failed event: failed attempts can be followed
by successful payment. Invoice visibility is not a grant prerequisite once payment is validated.

## 6. Refunds, chargebacks and credits already used

Recommended pilot support workflow: full-pack refunds for wholly unused packs, no automated partial
cash refunds. This is an operational default, subject to Paddle and consumer rules; staff can escalate
used/partially-used packs. Freeze the requested purchase lot under the user lock before requesting a
refund; keep unrelated packs spendable. If it has consumed or reserved units, enter manual review.

Create a durable refund intent before calling Paddle. Request `POST /adjustments` with
`action: "refund"`, `type: "full"`, transaction id and a plain support reason; persist the returned
adjustment id. A pending request is not a completed refund. Apply only verified approved adjustment
effects; rejected requests unfreeze the lot. Ambiguous network results are reconciled by listing
adjustments before retrying creation. [Create an adjustment](https://developer.paddle.com/api-reference/adjustments/create-adjustment/).

Provider-initiated refunds/disputes cannot be ignored because our normal unused-pack policy failed:

- Full approved refund or chargeback revokes that purchase's still-available units with an append-only
  negative ledger entry. Add `CreditReason.refund_revoke` through a safe enum migration. Never make
  the cached balance negative or delete a grant/reservation row.
- Reserved units cannot be spent twice or silently made free. Mark the original lot reversed. If the
  in-flight report fails, the usual release is paired atomically with a revocation of the released units;
  if it succeeds, record consumed units requiring review. Do not automatically remove completed reports.
- Already consumed units become an explicit **billing review**, not a negative balance or a claim that
  the user owes cash. Block new report reservations for that account until staff resolves/write-offs the
  review with an audit record. Existing reports remain readable; prevent buying more packs while the
  account is blocked, rather than accepting payments it cannot use.
- Chargeback warnings freeze the affected lot and alert support; confirmed reversal clears the freeze
  and restores only entitlements actually revoked, once. Never re-grant the original pack in full.
- Partial refunds, tax-only refunds and unusual credits require manual unit allocation: do not floor,
  round or derive report counts from the money ratio. A tax-only correction does not remove reports.
  Persist the adjustment and block the affected lot until reviewed; do not mutate other packs.

Recompute applied effects from current related adjustments, with unique effect keys and cumulative
revocation capped at the original grant. Refund + chargeback cannot revoke the same units twice;
chargeback reversals restore only their own net effects. Paddle's adjustment actions include
`chargeback`, `chargeback_reverse` and warning/reversal variants; map them from the verified schema,
not Stripe event names. [Adjustment updates](https://developer.paddle.com/webhooks/adjustments/adjustment-updated/).

## 7. Invoices, KSeF, privacy and accounting

Paddle is the customer-facing seller/MoR. Let it collect billing details and issue customer documents;
offer invoice access by retrieving `GET /transactions/{transaction_id}/invoice` after ownership checks,
not by storing a permanently public invoice URL. Do not issue another RentMonitor customer invoice
for the same MoR sale. [Transaction invoice API](https://developer.paddle.com/api-reference/transactions/get-transaction-invoice/).

No per-customer Fakturownia integration is proposed for the pilot, **conditional on accountant review**.
The MoR model does not remove our own accounting or applicable KSeF obligations. Obtain and assess
Paddle's reverse invoice/self-billing agreement, contracting entity/VAT identifiers, fees, refunds,
settlement currencies and reconciliation. See the researched legal scope and primary sources in
[BILLING-ALTERNATIVES.md](BILLING-ALTERNATIVES.md#ksef-distinguish-the-two-transactions).

New fields/payloads require `GDPR[personal-data]`, applicable provider role tags and `LEGAL[tax-invoice]`
at corresponding actions. Review Paddle's controller/processor roles and DPA; avoid blanket assumptions.
Suggested raw billing payload retention: 30 days, then purge/minimise; accountant approves retained
accounting-record periods before launch. Retain sanitized event ids and processing effects for replay
deduplication. Never log raw payload, binding tokens, API keys, NIP, email or buyer addresses.

Privacy deletion must not cascade away legally retained accounting records or refund evidence.
Separate/pseudonymise retained purchase ownership from active user data; restrict staff access and
define the erasure path. Remove account access and unused lots under the same lock as payments; retain
minimal original-owner reference for late-payment refund handling. Do not resurrect a deleted account.
Adapt `privacy.py`, `billing_erasure.py`, `/me` and retention jobs; no promise that deletion erases Paddle's
legally retained invoices. Show Paddle as seller and where invoice/refund support lives in the purchase UI.

## 8. Reliability and operator runbook

Proposed defaults: pending event sweep every minute; stalled event/grant alert at 15 minutes; daily
ledger/lot balance check; payment reconciliation hourly with a persisted cursor and overlap. Fetch
transactions and adjustments with pagination, deduplicate by provider ids, and reuse the same apply
function as webhooks. Recover completed payments missed during outages, not just existing local grants.
Keep a checkpoint/backfill command for an outage longer than the overlap; record provider event/history
retention limits before choosing a lookback. `creation_unknown` never automatically expires into a retry.

Monitor pending age, grant latency, invalid signatures, catalog mismatches, unknown bindings, failed
jobs, frozen lots, accounting-review units and ledger/lot mismatches. IDs only in alerts. Billing jobs use
their own existing billing/maintenance worker lane so audits cannot starve payment grants. Refund
commands require explicit purchase/account linkage, reason and idempotent request record; no live
operations are authorised by this specification.

Sandbox setup: complete product review preparation; create catalog and public token; register default
payment-link page; enable one-time BLIK; register the six events on an HTTPS test endpoint; store
environment-matched secrets privately; inspect catalog with read-only calls. Test all three packs,
Polish B2C and B2B documents, refunds and settlement samples. Sandbox callbacks/simulators are provider
verification, not evidence of a real bank payment. Owner records live onboarding and payment evidence
separately when authorised; no live key or provider change was made for this document.

## 9. Implementation slices and acceptance tests

Implement against an issue, branch from staging, with money-PR review and the repository's migration
gates. Read relevant local endpoint/migration skills before coding. Proposed slices:

1. Catalog/settings/client and offline fake; approved price snapshots; disabled-mode startup.
2. Schema and lot/allocation ledger changes; signup/admin compatibility and migration checks.
3. Checkout intent/idempotency and own-purchase APIs; fake provider only.
4. Signed durable webhook receipt, grant worker and reconciliation; offline journey tests.
5. Refund/adjustment review, invoice access and GDPR/retention changes.
6. Sandbox evidence and accountant/product acceptance; Phase 2 checkout UI separately.

| Required test | Expected proof |
|---|---|
| `test_paddle_pack_catalog` | Exactly 1/5/10 units, one-time PLN prices, approved snapshots; no recurring product |
| `test_paddle_checkout_idempotent` | Concurrent same key creates one attempt; different payload conflicts; no buyer-controlled amounts |
| `test_paddle_create_timeout_recovery` | Lost creation response recovers the existing transaction; no blind second payment |
| `test_paddle_raw_signature` | Modified bytes/invalid timestamp/header/secret rejected before persistence |
| `test_paddle_webhook_durable_receipt` | DB failure returns 5xx; committed pending row survives failed enqueue and worker death |
| `test_paddle_duplicate_grant` | Parallel duplicate events, different events for same transaction and reconcile race grant once |
| `test_paddle_binding_and_catalog` | Forged association, wrong environment/price/count/currency/discount/recurring item grants zero |
| `test_paddle_blik_pending` | Authorisation/paid/browser callback grants zero; completed capture grants expected units |
| `test_report_pack_consumption` | Standard success spends one; failures/rejections release; no Pro gate; views do not spend |
| `test_report_pack_last_credit_race` | Two concurrent audits with one unit accept only one reservation |
| `test_pack_refund_provenance` | One pack refund cannot revoke signup or another pack; repeated adjustment is a no-op |
| `test_pack_refund_in_flight` | Failure after reversal releases-and-revokes atomically; success records review; balance nonnegative |
| `test_refund_before_payment_event` | Fully reversed transaction arriving before/after completed cannot regain credits |
| `test_adjustment_overlap_and_reversal` | Refund/chargeback net effects bounded by grant; reversal restores only revoked units |
| `test_paddle_purchase_tenant_and_erasure` | Foreign ids 404; deletion vs completion cannot recreate account; retention respected |
| `test_paddle_reconciliation` | Missing payment/adjustment delivery recovered; paginated cursor/overlap safe |
| `test_pack_ledger_properties` | Hypothesis grant/reserve/settle/refund permutations preserve ledger, balance, lot and allocation invariants |
| `test_paddle_pack_checkout_sandbox` (`e2e`) | All packs, BLIK pending/completion, card, invoice/NIP and refund behavior against sandbox |

Run meaningful offline integration tests with real Postgres 17, `uv run pytest -m "not e2e"`, invariant
tests, migration tests/squawk, lint/types and OpenAPI checks before pushing implementation. Document
exact evidence in STATUS; do not weaken existing money or engine invariants to simplify packs.

## 10. Decisions to close before paid launch

- Owner: select final 1/5/10 prices (recommended 10/40/70 PLN), signup grant and non-expiring-unit policy.
- Paddle: approve actual product/data use/prepaid entitlements; confirm low-value fee, payout minimum,
  timing/currency/reserves, BLIK activation and sandbox/live separation.
- Accountant: approve customer and reverse-invoice workflow, KSeF treatment, tax category and retention.
- Support/product: approve unused-pack refund default, review process for partial/used reversals and terms.
- Engineering: complete authenticated report journey, ledger provenance, sandbox evidence and launch gates.

Update billing issues #14/#26/#27 and #39 (recurring BLIK no longer a pilot dependency), #41, STATUS,
BLOCKERS, blueprint routes/schema/env/tests and ADR 0005 successor in the implementation PR. Preserve
existing delivery evidence; replace subscription-specific gates with pack purchase/reversal/accounting
proof. This spec introduces no frontend implementation, provider resources, secrets or runtime changes.
