# Paddle sandbox setup: what is ready and what is next

Status on **2026-10-14**. Scope: the **sandbox** only (separate catalog, keys and webhook secret from live). Nothing here
touches live Paddle, and nothing is sellable yet. Spec: `docs/PADDLE-INTEGRATION.md`. Tracking: #220 (stays open), L-015, L-016.

## 1. State

| Item | State | Who |
|---|---|---|
| Sandbox API key in local `.env` (`PADDLE_API_KEY`, prefix `pdl_sdbx_`) | done, connection verified read-only by the agent through the Paddle plugin | owner |
| PLN and Poland | verified: PLN supported (minimum payment 265 minor units), sales to Poland allowed, Paddle calculates tax | agent |
| Three pack products | **created** (below), tax category `standard` is a placeholder | agent |
| Webhook destination | **created**, active, six events, no sensitive fields; the app answers 503 until billing is switched on, which is expected | agent |
| **Pack prices** | **waiting for you**: no price exists, none is guessed | owner decision (#43) |
| Webhook signing secret | **waiting for you**: copy it from the dashboard (never from chat) | owner |
| Default payment link (dashboard) | waiting for you | owner |
| Host `.env` Paddle block, billing switched on | after the prices and the secret | agent + owner (script) |
| End-to-end sandbox payments and refund | after the above | agent |

Sandbox objects (ids are not secrets):

| Pack | Product id |
|---|---|
| `reports_1` | `pro_01m4xyx82wz2ne3pt6z5mkrnjb` |
| `reports_5` | `pro_01m4xyx8b5xy08zbh0mrxdrfr8` |
| `reports_10` | `pro_01m4xyx8hhxbx1aad9dkmfkh1s` |

Notification destination: `ntfset_01m4xyx94tg6vh7xdr12ga05q6` -> `https://renti.tech/api/webhooks/paddle`, events
`transaction.completed`, `transaction.payment_failed`, `transaction.canceled`, `transaction.updated`,
`adjustment.created`, `adjustment.updated` (the six the app handles; no subscription events).

## 2. Your steps (in order)

1. **Decide the three gross prices in PLN** and tell the agent (a chat message is enough; also close the pricing item in #43).
   Recommended in `docs/PADDLE-INTEGRATION.md`: 10 / 40 / 70 PLN, i.e. `1000`, `4000`, `7000` grosze. Your earlier suggestion was
   5 / 40 / 70. Prices are tax-inclusive (`tax_mode internal`). The decision also covers the signup allowance (currently 3
   reports) and whether unused reports expire. Do not pay attention to the sandbox minimum: 2.65 PLN is far below any pack.
2. **Copy the webhook signing secret.** Paddle sandbox dashboard (`sandbox-vendors.paddle.com`) -> Developer tools ->
   Notifications -> the destination "Renti beta (renti.tech) - report pack payments" -> reveal the secret key (prefix
   `pdl_ntfset_`). Paste it into your **local** `.env` as `PADDLE_WEBHOOK_SECRET=...`. Do not paste it in a chat or an issue.
3. **Set the default payment link.** Dashboard -> Checkout -> Checkout settings -> Default payment link: `https://renti.tech`.
   Sandbox needs no domain approval, but Paddle still requires a default link before it returns a `checkout_url`.
4. **Check the tax category.** The three products use `standard` as a placeholder. In the dashboard confirm which category
   your Paddle account is allowed to use for this product (analysis reports delivered online) and tell the agent if it must
   change; the agent updates the products. Live needs the same decision in the product review (L-016) and the accountant (L-015).
5. **Optional, only if you want BLIK in the sandbox:** Dashboard -> Checkout -> Payment methods -> enable one-time BLIK
   (if offered for the sandbox). Cards alone are enough to prove the flow.

## 3. Agent steps (after your steps 1 and 2)

1. Create one **one-time PLN price** per product: `billing_cycle null`, `trial_period null`, `tax_mode internal`,
   `unit_price` as approved, `quantity 1..1`, name shown on invoices (for example "Renti - 5 reports").
2. Give you the three `pri_...` ids and the exact `.env` lines below (the price ids are not secrets).
3. After you ran the push script: run the env check on the host, `GET /api/billing/packs`, then the test matrix in section 5.

## 4. Switch it on (after prices and secret exist)

Add to your **local** `.env` (names are in `.env.example`; the agent fills the ids and amounts after your decision):

```
BILLING_PROVIDER=paddle
PADDLE_ENVIRONMENT=sandbox
PADDLE_API_KEY=...            # already there
PADDLE_WEBHOOK_SECRET=...     # step 2
PADDLE_PRICE_REPORTS_1=pri_...
PADDLE_PRICE_REPORTS_5=pri_...
PADDLE_PRICE_REPORTS_10=pri_...
PADDLE_APPROVED_AMOUNTS=reports_1=<grosze>,reports_5=<grosze>,reports_10=<grosze>
```

Then push them to the host without printing any value and restart the API and workers:

```
bash scripts/push_env_to_host.sh --restart BILLING_PROVIDER PADDLE_ENVIRONMENT PADDLE_API_KEY \
  PADDLE_WEBHOOK_SECRET PADDLE_PRICE_REPORTS_1 PADDLE_PRICE_REPORTS_5 PADDLE_PRICE_REPORTS_10 PADDLE_APPROVED_AMOUNTS
```

Expected: one `set NAME (N chars)` line per variable, `check_env: 0 error(s)`, `{"status":"ok"}`. The app refuses to enable
sales unless the three prices match the catalog snapshot and the approved amounts exactly (`billing_catalog`), and it refuses a live key
with `PADDLE_ENVIRONMENT=sandbox` (and the reverse). To switch off at any time: `BILLING_PROVIDER=disabled`, push, restart.

## 5. Test matrix (sandbox only; this is provider verification, not a real bank payment)

Test cards: `4242 4242 4242 4242` success; `4000 0038 0000 0446` 3DS; `4000 0000 0000 0002` declined. Any future expiry, any CVC.
Sandbox sends email only to the registered account domain, so use an address on it.

| # | Check | Expected |
|---|---|---|
| 1 | `GET /api/billing/packs` signed in | three packs, `enabled: true`, amounts equal the approved ones |
| 2 | `POST /api/billing/checkout` for each pack, open `checkout_url`, pay with the success card | purchase `granted`, report credits added once, ledger consistent |
| 3 | Replay the same webhook (dashboard -> Notifications -> replay) | no second grant |
| 4 | Declined card, then cancel a checkout | no grant, purchase `failed`/`canceled`, no credit |
| 5 | Admin refund of an unused pack (`POST /api/admin/billing/purchases/{id}/refund`) | refund requested, sandbox auto-approves (about every ten minutes), units taken back only after `adjustment.updated` approved |
| 6 | Refund of a pack whose reports were spent | manual-review response, billing hold, nothing clawed back |
| 7 | Invoice link for a granted purchase | Paddle document URL, short-lived, owner only |
| 8 | Polish consumer and a B2B buyer with a VAT id | documents show the expected tax treatment (accountant reviews, L-015) |

The agent runs 1-7 and records date, account type and result in `docs/STATUS.md` and `docs/LIMITATIONS.md` (level 3 evidence).
Item 8 needs the accountant.

## 6. Not part of the sandbox (live, later)

Live needs its own account approval, products, prices, key, webhook destination, secret and default payment link; domain approval is
manual there. It also needs the accountant's KSeF and settlement answer (L-015), Paddle's acceptance of the prepaid-report product
(L-016) and the privacy/legal items in `docs/PRE-DEPLOYMENT.md`. No live key goes on the host before that and before the repository is
private (`docs/PRE-DEPLOYMENT.md` section 0).

## 7. Security reminders

- Secrets live only in your local `.env` and the host `.env` (mode 600). Use `scripts/push_env_to_host.sh`; never paste a key or secret in chat.
- Use a key with only the permissions the spec lists (transactions read/write, prices and products read, adjustments read and, for refunds,
  write). Rotate it in the dashboard if it was ever shown anywhere.
- Never mix environments: `pdl_sdbx_` keys with `sandbox`, `pdl_live_` with `live`.
