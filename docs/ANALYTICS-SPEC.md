# Product analytics specification: Umami (closes #143)

Status: specification for the Phase 2 frontend (#44, N-30 / #72). No code ships in Phase 1. Facts marked *verified* were
read from the script Umami serves on 2026-10-12; everything else is a design decision for review. The owner's local
setup notes are in `docs/UMAMI-INTEGRATION.md` (gitignored); the website id is public in page HTML by design but is
never written into a committed file, only the env name.

## 1. Loading

- One `<script defer>` tag added by the SPA shell, only when `VITE_UMAMI_WEBSITE_ID` is non-empty; with it empty the
  loader does nothing, so local development and preview builds send no events.
- `src` is `VITE_UMAMI_SCRIPT_URL` (default `https://cloud.umami.is/script.js`), `data-website-id` is the id.
- `data-domains="<production host>"`: only that host counts, so localhost, previews and staging are never recorded
  (*verified*: the script supports `data-domains`).
- `data-do-not-track="true"`: a visitor's Do Not Track setting wins (*verified*).
- `data-exclude-search="true"` **and** `data-exclude-hash="true"` (*verified* attributes): see section 3, the magic-link token sits in the URL fragment and must never reach analytics.
- No analytics script on the API or in any Phase 1 service.

## 2. CSP and Caddy (decided: option 1, L-010)

The script is loaded from `cloud.umami.is` but posts events to **`https://gateway.umami.is/api/send`** (*verified*).
The blueprint CSP allows only `https://cloud.umami.is` in `connect-src`, so the browser would block every event.

| Option | `connect-src` | Cost |
|---|---|---|
| 1. Allow the gateway (**decided by the owner, 2026-10-12**) | `'self' https://cloud.umami.is https://gateway.umami.is ...` | one more third-party host in the policy |
| 2. Proxy through our domain | `'self' ...` unchanged; a Caddy path forwards `/api/send` (set `data-host-url`, *verified* attribute) | one more route to maintain; survives most ad blockers |

The owner chose option 1. It is applied to the blueprint and the Caddy config together with the frontend (Phase 2); nothing changes now. The Caddy smoke test (#15) should
assert that the served CSP contains the host of the chosen option.

## 3. Events

Automatic pageviews stay on. Custom events use `data-umami-event` attributes or `umami.track(name, props)` from one small
`track()` wrapper, so the allow-list below is enforced in one place:

| Event | Properties (all optional) | When |
|---|---|---|
| `audit_started` | `source` (`paste`, `saved`) | the user submits a listing |
| `audit_finished` | `status` (`succeeded`, `degraded`, `failed`), `grade` (A-E, N) | the result page opens |
| `upgrade_clicked` | `placement` (`paywall`, `settings`, `banner`) | the user opens Checkout |
| `signed_in` | `method` (`google`, `email`) | after sign-in |
| `market_viewed` | `tier` (`free`, `pro`) | the yield radar opens |

**Never sent, in properties or URLs:** email, user id, name, listing URL, listing id, address, price, notes, or any free
text. The wrapper drops unknown properties and anything longer than 40 characters. The magic-link
token lives in the URL fragment (`/login/email#t=...`) and Umami records the fragment unless told not to, so
`data-exclude-hash="true"` is **mandatory**, and `data-exclude-search="true"` keeps query strings out too. A unit test of
the shell asserts both attributes are present (section 6).

## 4. Consent and notice

*What the script does (verified):* it sets no cookies and reads and writes browser `localStorage` (its opt-out switch).
The cookie and analytics notice (N-30, #72) must say that product analytics are collected, name Umami Cloud as the
processor, say what is and is not recorded (section 3), and explain how to opt out. Whether a consent banner rather than
a notice is required, and the exact wording, is for counsel to confirm (`GDPR[consent]`, `GDPR[processor]`, B-012); this
document draws no legal conclusion. Opt-out for visitors: Do Not Track, and `localStorage.setItem('umami.disabled', 1)` (*verified* key)
exposed as a "turn off analytics" link on the privacy page.

## 5. Budget and limits

Umami Cloud Hobby (blueprint cost table): 100,000 events per month, one website, 6-month retention. The SPA stays far
below this by sending the five events above plus pageviews only. If the limit is reached Umami stops recording; the app is
unaffected. Revisit the plan when monthly events exceed 70,000.

## 6. Test plan

- Loader unit test: no script tag and no network call when the id is empty; the tag has the expected attributes when set,
  including `data-exclude-hash` and `data-exclude-search` (token safety).
- `track()` unit tests: unknown event names and properties are dropped; long strings are cut; personal-data-looking
  values (an `@`, a URL) are rejected.
- Caddy smoke (#15): CSP contains the chosen option's hosts; CI never loads the real script.
- Manual (owner, once a domain exists): open a page on the production host and confirm one pageview in the dashboard.

## 7. Owner checklist

1. Put the website id in the private `.env` as `VITE_UMAMI_WEBSITE_ID` and keep `VITE_UMAMI_SCRIPT_URL` as in `.env.example`.
2. Decide the CSP option (section 2), recorded under L-010.
3. When the domain exists, set `data-domains` and confirm the first pageview.
4. Confirm the notice wording with counsel (B-012).
