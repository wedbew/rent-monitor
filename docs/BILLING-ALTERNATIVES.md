# Billing alternatives: Stripe, Paddle and Lemon Squeezy

> **Follow-up, owner 2026-10-13:** pilot direction is now one-time Paddle packs of 1, 5 and 10 reports,
> without subscriptions. See [PADDLE-INTEGRATION.md](PADDLE-INTEGRATION.md) for the implementation
> design, pricing recommendation and remaining decisions. The comparison below preserves the original
> research; its subscription/pass recommendation is superseded for the pilot.

**Researched:** 2026-10-13. **Status:** recommendation for review, not an accepted architecture change.
The accepted contract remains [BLUEPRINT.md](BLUEPRINT.md), [STRIPE-SPEC.md](STRIPE-SPEC.md) and
[ADR 0005](adr/0005-billing-blik-pass-and-credit-ledger.md). This research was requested by the owner;
it does not authorise a provider migration or amend existing product requirements.
Vendor facts below were checked against primary sources on this date. Product fit and Polish settlement
treatment remain unverified; see L-015/L-016 in [LIMITATIONS.md](LIMITATIONS.md).

## Recommendation

**Evaluate Paddle first.** For a small RentMonitor launch, paying more per sale is likely preferable to
building and operating customer invoicing and KSeF automation. Proposed offering: 100 PLN monthly card
subscription plus a 100 PLN one-time 30-day pass payable by BLIK or card. Paddle documents BLIK for
Polish buyers paying in PLN on one-time purchases, **not subscriptions**. This preserves a BLIK purchase
path but changes the blueprint's recurring-BLIK requirement. Its deferred capture can take up to ten
minutes: an authorised checkout must not grant access before payment completes.
[Paddle BLIK documentation](https://developer.paddle.com/concepts/payment-methods/blik/).

This recommendation is conditional on Paddle accepting the actual product, an accountant approving
the settlement workflow, and the owner accepting card-only automatic renewal. If automatic BLIK
renewal is essential, keep ordinary Stripe plus a Polish invoicing provider. Lemon Squeezy is a secondary
candidate if BLIK can be dropped; its published payment list does not include BLIK and subscriptions
support cards, Apple Pay, Google Pay and PayPal.
[Lemon Squeezy payment methods](https://docs.lemonsqueezy.com/help/checkout/payment-methods).

For an even smaller paid pilot, consider **Paddle passes only**: no subscription renewal, dunning or
grace-period workflow initially. That reduces product scope and recurring revenue convenience, so it
is a separate proposal, not a replacement already decided.

## What the repository actually contains

Confirmed from the checkout, not from a live provider account:

- `docs/STATUS.md` lists billing as spec only, with sandbox access pending (B-003).
- The blueprint's VAT flow includes buyer classification, a durable `vat_invoice` outbox, Fakturownia
  creation, KSeF status polling, invoice email, failure alerts and corrective invoices for refunds.
  API-created invoice submission and duplicate recovery still need trial-account evidence.
- `packages/rm_core/db/models.py` already has Stripe-specific customer, event and price fields;
  `entitlements.py` implements period/pass access; `seed.py` and `privacy.py` also refer to Stripe.
  `services/rm_api/billing_erasure.py` is a seam awaiting the real billing implementation.
- No working checkout/webhook/Fakturownia integration was found in `services/` or `packages/`.
  Switching now avoids migrating paying subscribers, but still requires schema and privacy changes.

The blueprint's description of this as “one background task” understates operations: retries after
ambiguous timeouts, KSeF rejection, corrections, retention, reconciliation and support remain ongoing
responsibilities. Fakturownia itself is not mandated; it is the chosen way to implement the seller's
invoicing obligations. Another provider or an accountant-operated workflow can serve that role.

Two spec discrepancies also need resolution before implementing billing: the blueprint route is
`/api/billing/webhook`, while STRIPE-SPEC uses `/api/webhooks/stripe`; the blueprint acknowledges and
queues events, while STRIPE-SPEC §3 mixes transaction processing with acknowledgement. Provider
selection should produce one consistent endpoint and durable asynchronous processing contract.

## KSeF: distinguish the two transactions

The Ministry of Finance states that mandatory issuance began 1 February 2026 for businesses exceeding
200 million PLN gross sales in 2024, and 1 April 2026 for other taxpayers. A temporary exception for
monthly invoice-documented sales up to 10,000 PLN gross runs through the end of 2026. Consumer
invoices are outside mandatory issuance. Foreign issuers without a Polish establishment, or without
an involved Polish fixed establishment, also have exclusions. Receiving invoices has a separate
obligation from 1 February 2026. These are scope rules, not confirmation of RentMonitor's eligibility.
[Ministry of Finance: mandatory KSeF scope](https://ksef.podatki.gov.pl/informacje-ogolne-ksef-20/zakres-obowiazkowego-ksef/).

| Transaction | Ordinary Stripe | Merchant of record (MoR) |
|---|---|---|
| Customer buys software access | RentMonitor is the seller; payment processing does not transfer invoice responsibility | Customer buys from the MoR, which handles the customer sale |
| Customer invoice and sales VAT | RentMonitor's workflow and accountant | MoR's customer billing and tax workflow |
| RentMonitor records revenue and settlement | Stripe payout reconciliation plus own sales documents | Reconcile MoR settlement, fees, refunds and supplier/self-billing documents |

Paddle bundles customer billing and tax handling. Lemon Squeezy also describes itself as the entity
selling to the customer and handling sales tax. This changes who issues the customer invoice; it does
not make the Polish business disappear.
[Paddle pricing and included services](https://www.paddle.com/pricing),
[Lemon Squeezy MoR model](https://www.lemonsqueezy.com/reporting/merchant-of-record).

**Inference:** if the customer sale is genuinely made by a qualifying foreign MoR, RentMonitor should
not need its own per-customer Fakturownia → KSeF pipeline for that sale. This is not evidence that Paddle
or Lemon Squeezy submits Polish KSeF invoices. Their contracting entity and RentMonitor's separate
supplier transaction must be assessed. Selling to a foreign customer alone is not a blanket KSeF exemption
for a Polish issuer.

Paddle says it supplies a reverse invoice for each payout. Ask the accountant whether the contract's
self-billing arrangement, counterpart VAT identifiers and document acceptance meet Polish rules, and
whether KSeF issuance or an exclusion applies. Confirm revenue recognition, VAT/VAT-UE or reverse-charge
reporting where applicable, fees, corrections and FX. Do not assume net cash received equals taxable
revenue or that the vendor's generic “no action needed” statement settles Polish requirements.
[Paddle reverse invoices](https://www.paddle.com/help/manage/get-paid/do-i-need-to-invoice-paddle-for-my-payout).

Under either approach, own accounting, income tax, applicable KSeF receipt duties and privacy obligations
remain. The accountant must also validate VAT status, service classification and any cash-register
treatment. Absence of a NIP is not sufficient proof that a buyer is a consumer; the existing classification
shortcut needs review if RentMonitor remains the direct seller.

## Comparison and economics

| Option | Published fee basis | Polish purchase fit | Assessment |
|---|---|---|---|
| Stripe Payments + Billing + Fakturownia | Standard EEA card 1.5% + 1 PLN; Billing 0.7%; BLIK 1.6% + 1 PLN | Recurring BLIK documented, account activation/bank coverage still need evidence | Lowest processing cost; most invoice operations remain ours |
| Paddle MoR | 5% + US$0.50 per checkout transaction | PLN one-time BLIK; no BLIK subscriptions | Preferred evaluation candidate |
| Lemon Squeezy MoR | 5% + US$0.50; +1.5% non-US transactions; +0.5% subscriptions; +1.5% PayPal | Poland supported for bank payouts; no documented BLIK | Useful if BLIK is optional; Polish recurring sales incur more than headline fee |
| Stripe Managed Payments MoR | +3.5% on top of processing; Billing charged separately | Published Managed Payments method list does not include BLIK | Investigate if retaining Stripe matters; Polish seller access/product acceptance not verified |
| Polar MoR | New Starter accounts: 5% + US$0.50; +1.5% non-US cards | BLIK not verified in this research | Secondary shortlist, no clear advantage for the required Polish flow |

Sources: [Stripe Poland pricing](https://stripe.com/en-pl/pricing),
[Stripe recurring BLIK](https://docs.stripe.com/payments/blik/recurring-payments),
[Paddle pricing](https://www.paddle.com/pricing),
[Lemon Squeezy fees](https://docs.lemonsqueezy.com/help/getting-started/fees),
[Lemon Squeezy supported countries](https://docs.lemonsqueezy.com/help/getting-started/supported-countries),
[Stripe Managed Payments fees](https://support.stripe.com/questions/managed-payments-pricing?locale=en-GB),
[Managed Payments methods](https://docs.stripe.com/payments/managed-payments/how-it-works),
[Polar current fees](https://polar.sh/docs/merchant-of-record/fees).

Illustration only, **assuming** US$1 = 4 PLN to translate fixed fees; this is not a current FX quote.
For a 100 PLN gross checkout: Stripe standard EEA card subscription ≈ 3.20 PLN; Paddle ≈ 7 PLN;
Lemon Squeezy non-US card subscription ≈ 9 PLN; Stripe Managed Payments card subscription ≈ 6.70 PLN;
Polar Starter non-US card ≈ 8.50 PLN. Stripe's configured post-payment invoice adds 0.4% to a one-time
payment (the blueprint's pass cost omits this): BLIK pass ≈ 3 PLN when enabled.

These are transaction-fee illustrations, not total cost quotes. Excluded: provider-plan cost for
Fakturownia, accounting, payout/FX charges, refunds/disputes and engineering/support. Lemon Squeezy
also lists 1% bank payout fees outside the US. At 100 standard-card renewals/month, the illustrated
Paddle premium over ordinary Stripe is about 380 PLN/month, before avoided invoice costs. That is a
useful budget for deciding whether managing our own invoice pipeline is worthwhile.

At 23% VAT, 100 PLN gross contains approximately 18.70 PLN VAT, leaving 81.30 PLN before fees;
this scenario is not confirmation of the applicable rate. MoR payouts are after withheld customer tax
and fees. Keep the advertised **100 PLN total** for Polish consumers: verify tax-inclusive configuration
and B2B handling in checkout rather than creating a 100 PLN tax-exclusive price that becomes 123 PLN.
[Paddle tax-inclusive pricing](https://www.paddle.com/help/sell/tax/do-you-support-tax-inclusiveexclusive-pricing).

PayU/Przelewy24 or Stripe Payment Links may simplify taking payment, but changing the payment interface
alone does not transfer seller invoicing responsibility. A tiny direct-sales pilot could use manual
invoicing through an accountant's existing tool, with a documented reconciliation and correction process;
this reduces initial automation, not the underlying duties.

## Product approval is a prerequisite

Paddle's AUP restricts investment/financial advice and business or investment opportunities.
Lemon Squeezy permits SaaS but restricts regulated real-estate services and content without appropriate
IP rights. **Unverified:** whether either accepts RentMonitor's particular offering. Request written
assessment using representative reports showing yield, IRR, Max Bid and rankings, plus the data sources
and rights basis. Do not hide features or assume a disclaimer establishes eligibility.
[Paddle AUP](https://www.paddle.com/help/start/intro-to-paddle/what-am-i-not-allowed-to-sell-on-paddle),
[Lemon Squeezy prohibited products](https://docs.lemonsqueezy.com/help/getting-started/prohibited-products).

## Proposed implementation after a decision

Use one provider initially. Keep Python, Postgres, Procrastinate, the credit ledger and entitlement
rules. Build a small provider boundary rather than a multi-provider routing platform.

1. Create checkout server-side for the authenticated user; keep product, price and user association
   trusted. Use the provider's customer portal and invoice links.
2. Verify signatures over the raw body; persist and deduplicate events; acknowledge after durable
   storage, then process in the billing worker. Keep locks, replay safety and reconciliation.
3. For Paddle, use `transaction.completed` as the proposed paid-grant trigger, keyed uniquely by
   provider + transaction id. Map renewals and passes separately; subscription-created/active and
   browser success alone must not issue paid allowance. Validate zero-value/trial, refund, dispute,
   late-event and canceled-subscription behavior before finalising the event mapping.
   [Paddle transaction completion](https://developer.paddle.com/webhooks/transactions/transaction-completed/),
   [signature verification](https://developer.paddle.com/webhooks/about/signature-verification/).
4. Replace Stripe-specific identifiers through an expand/contract migration; review `source_invoice_id`,
   customer/event models, seed, settings, problem codes, API exemptions and account-erasure integration.
   Retain Decimal money, tenant isolation, offline clients and concurrency/property tests.
5. Omit the application's customer-invoice/KSeF outbox only once the accountant confirms the MoR flow.
   Retain settlement reconciliation and any own-business invoicing outside the product application.
6. Revise processor/controller inventory, privacy notice, deletion/retention paths, checkout seller
   disclosure, refund support and invoice access. A MoR may act as an independent controller for sales;
   do not mechanically copy Stripe's GDPR role description.

Before acceptance, demonstrate in the sandbox: Polish 100 PLN total, buyer NIP on a B2B invoice,
card renewal, one-time BLIK completion/failure, duplicate/out-of-order webhooks, pass stacking, expiry,
refund and correction, cancellation, reconciliation and erasure. Obtain a sample settlement/reverse
invoice and payout terms (schedule, threshold, currency, reserves and fees). No vendor account was
created or contacted during this research.

If approved, supersede ADR 0005 and minimally update blueprint §2–§4, STRIPE-SPEC, billing/VAT/refund
issues (#14/#26/#27), BLIK activation (#39), accountant review (#41), STATUS/BLOCKERS and release gates.
Replace Stripe/Fakturownia-specific gates with equivalent payment and accounting evidence; do not
drop money/concurrency checks. Until then this document is a proposal and the accepted specs remain intact.
