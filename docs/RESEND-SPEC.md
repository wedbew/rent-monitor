# Transactional email specification: Resend (closes #133)

Status: specification, **awaiting owner review** (sign-in and billing emails are human-review areas). The magic-link
mailer already exists in the open auth PR (#147); dunning, reminders and invoice emails come with #25 and #14. *Confirmed*
= covered by a test in #147; *inferred* = from Resend documentation or reasoning, untested against the live service.
The owner's local notes (`docs/RESEND-INTEGRATION.md`, gitignored) hold the account details; no key, DNS record or
recipient address is written into a committed file.

## 1. Wiring (confirmed in #147)

- Settings: `RESEND_API_KEY` is a `SecretStr` (its repr never shows it; a test guards that) and `MAIL_FROM`. The local
  default sender is Resend's onboarding address, which can only deliver to the account owner.
- The API never sends mail. It defers a Procrastinate job by name (`rm_worker.tasks.email.send_magic_link`, queue `ops`); the
  worker builds a `Mailer` (`ResendMailer` with a key, `LogMailer` without) behind a small protocol, so tests use a fake and
  CI never touches the network.
- `ResendMailer` calls `POST https://api.resend.com/emails` with an `Authorization: Bearer` header and an `Idempotency-Key`
  derived from recipient and link, 10 s total / 5 s connect timeout, no hidden retries.
- **Errors are classified.** Network errors, 429 and 5xx are `TransientMailError`; any other 4xx (bad key, unverified
  domain, invalid address) and an unsafe configuration are `PermanentMailError`. The job retries only transient errors, 4
  attempts at 9, 27 and 81 s, which all fit inside the link's 30 minutes. A permanent error fails at once.
- **Production guards:** with `APP_ENV=production` the worker refuses to send without a key and refuses the onboarding sender.
  Development with no key logs the link (one line, `APP_ENV=development` only) so sign-in can be tested without Resend.

## 2. Message catalog

| Message | Trigger | When built | Notes |
|---|---|---|---|
| Magic link | `POST /api/auth/email/start` | #147 (done) | pl, text + minimal HTML, one link, no images or tracking; valid 30 minutes, once |
| Payment failed (dunning) | `invoice.payment_failed`, first time per period | #14 / #25 | blueprint sketch `send_dunning_email(user_id, invoice_id)`; mentions the 7-day grace and a link to the Portal |
| Pass expiring | 3 days before a BLIK pass ends | #25 | one email with a new pay link; skipped if the user already has a newer period |
| Invoice | KSeF number received | Fakturownia or us, **owner decision** | blueprint §3 says the task "emails the invoice"; if Fakturownia sends it, we send nothing |

Rules for every message: Polish first, English later; plain text and HTML in one message; links built only from
`PUBLIC_APP_URL`; no open or click tracking; the subject never contains the amount or the listing; the footer states
why the user received it. No marketing or newsletter mail exists, so no unsubscribe flow or consent is needed for the
messages above (they are service messages; counsel confirms, B-012). Stripe's own receipt and invoice emails are turned
off in the Dashboard so the customer gets one document set (blueprint §3, an *inference* to verify in the account).

## 3. Abuse and privacy

- No account enumeration: `email/start` answers 204 whether or not the address exists (confirmed).
- Limits: 5 per hour per address and 20 per hour per IP through one atomic counter (confirmed); a dunning email is sent
  once per grace period, keyed by the invoice id.
- Header injection: addresses are validated by a strict pattern with no whitespace, quotes or angle brackets before they
  reach the provider (confirmed), and the message body is HTML-escaped.
- The magic-link token is stored hashed in `login_token`, but the raw token and the address sit in the job arguments until
  the job is removed (L-011); finished and failed `ops` jobs are deleted after 24 hours (#157).
- Bounces and complaints (section 4) never reveal to the requester whether an address is suppressed.

## 4. Delivery feedback (to build with #25)

- Resend webhook `POST /api/webhooks/resend`: events `email.bounced` and `email.complained`. The signature (Svix headers
  `svix-id`, `svix-timestamp`, `svix-signature`) is verified on the **raw body** before parsing, with a replay window of five
  minutes, as for Stripe (*inferred*: Resend signs webhooks with Svix; confirm in the account). The route is exempt from
  the Origin check, which already exempts `/api/webhooks/`.
- A table `mail_suppression(address_hash, reason, created_at)` stores a SHA-256 of the address; hard bounces and complaints
  suppress further sends to it. A suppressed user can still sign in with Google; the magic-link page says the address
  cannot receive mail and offers Google, without confirming a suppression to anyone else.
- Retention: suppression rows are kept 1 year (a hash, not the address); erasure by account deletion removes nothing here
  because the hash cannot be linked back, which is the point (`GDPR[retention]`, `GDPR[erasure]`).

## 5. GDPR and legal

`GDPR[processor]`: Resend receives the recipient address and the message body (the magic link, the dunning text).
`GDPR[personal-data]`: the address in the job arguments and the mail body. Retention: jobs 24 hours; Resend's own log
retention is a vendor setting to check (DPA, B-012). No `LEGAL[...]` tag applies. Wording of the privacy notice is for counsel.

## 6. Domain and deliverability checklist (owner; depends on B-005)

1. Verify a sending domain in Resend, preferably a subdomain such as `mail.<domain>`, so the apex domain's reputation is
   separate. Resend gives the DNS records to add.
2. SPF and DKIM as Resend instructs; a DMARC record starting at `p=none` with a report address, moving to `quarantine` after
   a few clean weeks (*recommendation*).
3. Set `MAIL_FROM` to an address on that domain and a reply-to the owner reads. Until then production refuses to send.
4. Volume: Resend Free allows 3,000 emails/month and 100/day (blueprint cost table); a magic link per sign-in plus a few
   dunning and reminder emails stays far below that. Alert at 70 % of the daily or monthly cap.
5. Warm-up is not needed at this volume; watch bounce rate and complaints in the first weeks.

What changes from the local sender: the onboarding address delivers only to the account owner, so local testing works
for exactly one recipient. Everything else needs the verified domain.

## 7. Test plan

- Done in #147: message content and escaping, idempotency key stability, the production guards, provider error
  classification and that the key never appears in an error, the retry policy (permanent never, transient 9/27/81 s,
  give up after 4), single use / expiry / replay / rate limits / enumeration of the link itself.
- To add: the dunning and reminder templates with a fake mailer; webhook signature, replay and out-of-order handling; the
  suppression table; the 70 % volume alert.
- E2E (owner, sandbox only, once the domain is verified): send to Resend's test addresses and confirm delivery.

## 8. Environment names and open items

Names exist in `.env.example`: `RESEND_API_KEY`, `MAIL_FROM`. Planned: `RESEND_WEBHOOK_SECRET` (with the webhook, #25).

1. Resend key validity and delivery are untested (B-004); a first real send needs the key and a recipient the account allows.
2. Verified domain and DNS (B-005).
3. Decide who sends the invoice email: Fakturownia or us (section 2).
4. Keep production and development keys separate and rotate a key at once if it may have been exposed.
