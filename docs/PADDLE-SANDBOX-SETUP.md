# Paddle sandbox setup: remaining owner steps (slice of #220)

Spec: `docs/PADDLE-INTEGRATION.md` (sections 1, 5, 8). This file lists only what is left to do by hand. It holds no prices,
keys, secrets or ids; those live in your private `.env` and on the host.

**State reported in #248 (by the owner, not re-verified by an agent, which has no Paddle access):** in the *sandbox* account
three pack products (1, 5 and 10 reports) and one webhook notification destination are created. No prices exist yet.
Everything below stays in the sandbox: never paste a `pdl_live_...` key, never mix environments (`PADDLE_ENVIRONMENT=sandbox`).

## Owner decisions still needed

1. **Pack prices** (gross PLN, one-time): open decision in `CONTEXT.md` section 9 / #43 (recommended 10/40/70 PLN, owner
   suggested 5/40/70). No default exists in code on purpose.
2. **Webhook secret**: shown once by Paddle when the destination is created (or via *Reveal secret*). Only you can copy it.

## Steps

1. **Prices.** Developer Tools -> Catalog (sandbox). For each of the three products add one price: one-time (no billing
   cycle), currency PLN, tax mode *tax-inclusive* (D-03), quantity limits 1..1. Note the three `pri_...` ids.
2. **API key.** Developer Tools -> Authentication -> new API key. Permissions per `PADDLE-INTEGRATION.md` section 2:
   read products/prices/adjustments, write transactions, write adjustments. Starts with `pdl_sdbx_`.
3. **Client token** (public, for Phase 2 checkout): same page, *Client-side tokens*.
4. **Destination.** Developer Tools -> Notifications. Confirm the destination URL ends in `/api/webhooks/paddle` and is HTTPS
   (the host has no domain/TLS yet, so deliveries will fail until DNS and a certificate exist, B-005; use the simulator
   or a tunnel meanwhile). Subscribed events must be exactly: `transaction.completed`, `transaction.payment_failed`,
   `transaction.canceled`, `transaction.updated`, `adjustment.created`, `adjustment.updated`. No subscription events.
5. **BLIK.** Checkout settings: enable one-time BLIK, set the default payment link (`PADDLE-INTEGRATION.md` section 8).
6. **Local `.env`** (names from `.env.example`; the file is never committed):
   `BILLING_PROVIDER=paddle`, `PADDLE_ENVIRONMENT=sandbox`, `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_CLIENT_TOKEN`,
   `PADDLE_PRICE_REPORTS_1`, `PADDLE_PRICE_REPORTS_5`, `PADDLE_PRICE_REPORTS_10`, `PADDLE_APPROVED_AMOUNTS`
   (`reports_1=<grosze>,reports_5=<grosze>,reports_10=<grosze>`, must equal the prices from step 1).
   No `KEY=value  # comment` lines (Compose reads the comment as the value).
7. **Check locally:** `uv run python scripts/check_env.py --env-file .env --private` must report `0 error(s)`.
8. **Push to the host** (values travel over SSH stdin and are never printed):

   ```bash
   scripts/push_env_to_host.sh BILLING_PROVIDER PADDLE_ENVIRONMENT PADDLE_API_KEY PADDLE_WEBHOOK_SECRET \
     PADDLE_CLIENT_TOKEN PADDLE_PRICE_REPORTS_1 PADDLE_PRICE_REPORTS_5 PADDLE_PRICE_REPORTS_10 PADDLE_APPROVED_AMOUNTS
   ```

   It backs the host file up to `.env.bak`, replaces existing names in place and keeps mode 600. Then restart per
   `docs/RUNBOOK-DEPLOY.md` section 1.
9. **Evidence.** Run a sandbox checkout for each pack (card, then BLIK), a refund, and record date, account type and result
   in `docs/STATUS.md` and `docs/LIMITATIONS.md` (level 3). Simulator callbacks are provider verification, not a bank payment.
   #220 stays open until this is done and the accountant/Paddle acceptance items (L-015, L-016) are answered.

## Rotation and cleanup

Rotating the destination secret: set the new value as `PADDLE_WEBHOOK_SECRET` and the old one as
`PADDLE_WEBHOOK_SECRET_PREVIOUS` until Paddle stops sending with the old secret, then remove the previous one.
