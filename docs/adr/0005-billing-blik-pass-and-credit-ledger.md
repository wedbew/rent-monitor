# ADR 0005 — Stripe Checkout, BLIK pass and an append-only credit ledger

- **Status:** accepted (blueprint §3 "BLIK at launch", "Stripe webhook lifecycle") · **Date:** 2026-10-11 · **Ticket:** RM-31

## Decision
Card and BLIK from day one through Stripe Checkout and the Customer Portal. The 100 zł/month subscription may use BLIK
recurring; a one-off 30-day BLIK "Pro" pass covers customers whose bank does not support recurring BLIK (9 banks do).
Quota is a plan allowance per invoice period plus an append-only credit ledger; grants are keyed by Stripe invoice id so they
are idempotent by construction. `has_pro` fails closed 48 h after the period end. Stripe's own receipts are off; invoices
come from Fakturownia and KSeF.

## Consequences
- Webhook handling verifies the signature on the raw body, claims the event id first, and must tolerate adverse event order.
- Concurrency and property tests are mandatory for ledger, quota and pass stacking (`test_pass_parallel_stacks`, …).
- BLIK recurring needs a Stripe activation request (a long pole, #39) and a live test (gate 3).
- Money is `Decimal`/`NUMERIC` end to end; every billing PR waits for a human review.
