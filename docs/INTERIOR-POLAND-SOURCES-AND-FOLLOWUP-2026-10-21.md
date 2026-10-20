# Interior follow-up: existing R2, remaining slices and Polish product sources

Owner clarification and research, 2026-10-21, Europe/Warsaw. This is a handoff, not a claim that configuration, code fixes, provider access or deployment have been completed in this research session.

## Decision supplied: reuse `rent-monitor`

The owner explicitly approves the existing private `rent-monitor` bucket and default jurisdiction. Do not ask for a new EU bucket. Preserve public access off, separate application MEDIA_* settings from backups, tenant authorization, normalization, 30/7-day retention and erasure. This supersedes the earlier EU product-media requirement, not the EU backup policy. The decision is recorded in the October 21 addendum to `OWNER-DECISIONS-2026-10-19.md`.

Read-only GitHub verification: staging `47a43e67c7d846091aa79e7aa56f7194215917b2` contains MEDIA_* settings whose `_media_endpoint_is_eu` validator accepts only `.eu.r2.cloudflarestorage.com`. B-025 currently requests a new EU bucket. Issues #448, #449, #450 and #451 are OPEN. This local checkout is older and lacks the new object-store/probe files. The implementation report supplied by the owner describes a merged seam and seven unit tests; this research session did not independently rerun those tests or verify every merge check.

**Next change for Claude:** reuse `rm_core.object_store`, amend the validator to support the actual default R2 endpoint as well as EU, retaining strict HTTPS/host validation. Add tests proving both allowed endpoints work and untrusted/malformed hosts do not. Do not remove endpoint validation. Use explicit media settings, securely populated from the existing verified connection:

| Media setting | Existing source |
|---|---|
| `MEDIA_S3_ENDPOINT` | Verified `CLOUDFLARE_S3_API` endpoint URL |
| `MEDIA_BUCKET` | `rent-monitor` |
| `MEDIA_ACCESS_KEY_ID` | Existing `R2_ACCESS_KEY_ID` credential, privately mapped |
| `MEDIA_SECRET_ACCESS_KEY` | Existing `R2_SECRET_ACCESS_KEY` credential, privately mapped |

Use authorized secret-safe configuration helpers/transport; never read or display private values to the model. Preserve nonempty settings rather than overwriting them blindly. Run `uv run python scripts/probe_media_store.py` on the correct implementation checkout and then the actual serving runtime. The full probe must verify own-object PUT/HEAD/GET/hash, anonymous denial, own-object DELETE and absence. An upload-only success does not establish delete or runtime access. Resolve B-025 after the required live evidence; until then record that the owner decision is supplied and only configuration/probe work remains. No ListBuckets/CreateBucket privilege is required for ordinary image operations. Do not repeat previously denied creation attempts or request a token with account-wide rights.

Update ADR 0014, `.env.example`, BLOCKERS, STATUS, LIMITATIONS and other affected documentation in the implementation PR. Do not silently change policy only in code.

## Remaining work and how to continue

| Item | What remains | Dependency / acceptance |
|---|---|---|
| #448 projects/uploads | Contracts, migration, owned repository, normalized upload, briefs/revisions, retention and project API | Continue immediately with fakes; live acceptance requires the corrected settings and storage probe. Include invalid upload, tenant isolation, retry/orphan cleanup and erasure tests. |
| #449 catalogue/offers | Real provider, product/variant/offer identity, freshness, price/image provenance and bounded candidate selection | A fake seam is useful for implementation, but a live provider needs approved access. Prefer the sources below; do not wait exclusively for IKEA/Amazon. |
| #450 generation | Durable operation, shared USD 5 reservations, per-attempt USD 0.50 cap, reconciliation, queued-only cancellation | Uses #448/#449 contracts. Verify remaining cumulative budget; no paid test is justified by assuming this session spent zero. Keep selected products/concept when rendering fails. |
| #451 frontend | Project list, photo upload, brief, real product board, revisions, before/after, progress/retry/history | Build against merged contracts; preserve unavailable states only for genuinely blocked capabilities. Require current unit/type/build/accessibility/interaction/visual/e2e evidence. |
| Node/frontend evidence | Current shell is Node 22.15.0, but **Node 24.22.0 is already installed** under `/Users/marcin/.nvm/versions/node/v24.22.0/bin/node`; `frontend/.node-version` specifies 24.22.0 | Select the installed runtime, verify node/pnpm, then run the required frontend checks for the actual implementation. No owner installation action is needed. A skipped job is not frontend evidence. |
| Dirty checkout | `CONTEXT.md`, `scripts/dev_stack.sh` and this session's research/prompt files must be preserved | No blind pull, reset or whole-tree stash/delete. Use the assigned clean implementation checkout/worktree, reconcile owned documentation explicitly and leave unrelated changes alone. |

## Recommended product-access routes

These are verified documentation/program routes, **not authenticated product-data tests**. No account was created, terms accepted, token obtained or vendor message sent. Catalogue coverage, quotas, exact offer fields and image reuse rights remain to be verified for an approved account. Recommendation: try one Polish furniture merchant feed via webePartners first; use Convertiser if an interactive multi-merchant API is more suitable. A feed plus our own bounded search is sufficient for the first production slice; a public live-search API is not mandatory.

### 1. webePartners: practical first furniture source

Its official tools page documents XML feeds containing product images, descriptions and prices, category downloads and an API key for automation. A public Meble Pumo partner program is present; the network also lists Lectus24, Edinos and Fabryka Form. Those listings establish program availability, not that each merchant's feed is already accessible to this app.

Access steps: register a publisher account and declare `renti.tech`/the actual promotional surface, apply to a suitable furniture/home advertiser, obtain accepted-program XML access or the account's supported API route, then request a sample feed and usage terms. Confirm that the specific selected merchant supplies a feed with stable IDs, PLN prices, merchant URLs and image URLs. Registration and API existence alone do not prove merchant acceptance or feed completeness.

Sources: [publisher onboarding](https://webepartners.pl/wydawca/), [XML/API tools](https://webepartners.pl/en/tools/), [Meble Pumo program](https://panel.webepartners.pl/merchantprograms/landingpage?sid=189), [other furniture program examples](https://webepartners.pl/blog/programy-partnerskie-ranking/).

### 2. Convertiser: documented searchable Products API

The official API documents `POST /publisher/products/v2/` with filters for title/brand/category/currency, numeric price filters, updated-at, pagination and offer/feed IDs. Authentication uses **`Authorization: Token …`**, not an assumed Bearer scheme.

Access steps: register a publisher account, verify email, add the actual website/promotional surface and confirm eligible furniture/home campaigns with the account manager. Generate a personal token in Account Settings → API Tokens, keep it server-side, then make one bounded authorized query for PLN furniture. Confirm which campaigns/products the account can access and inspect real response shape before implementing an adapter; the docs contain loosely specified schema sections. Test exact variant resolution, price conditions, timestamp meaning and images. Do not assume a timestamp is a fresh seller check.

Sources: [registration](https://help.convertiser.com/pl/kb/rejestracja-konta/), [token setup](https://docs.convertiser.com/guides/authentication), [product search v2](https://docs.convertiser.com/products-api/reference/products/v2-create), [API summary](https://docs.convertiser.com/products-api/reference).

### 3. Awin: broader advertiser feeds

Use an approved publisher account and suitable Polish home/furniture advertiser. Toolbox → Create-a-Feed lets the publisher select language, advertiser feed, columns and compression, then obtain a download URL. The **product-feed key differs from the Publisher API key**. An advertiser can omit products or supply incomplete/stale fields; handle that explicitly. Specific Polish merchant coverage was not verified in an authenticated account.

Sources: [feed access](https://success.awin.com/articles/en_US/Knowledge/How-can-I-access-a-Product-Feed), [Create-a-Feed](https://help.awin.com/developers/docs/downloading-feeds-using-create-a-feed), [approval/freshness caveats](https://help.awin.com/developers/docs/faqs-for-publishers).

### Sources to avoid making the first dependency

- **Allegro public offer search:** the official API team's July 23, 2026 response states that new access to `GET /offers/listing` can no longer be obtained. Do not tell the owner that ordinary app registration or User-Agent verification unlocks it. An already approved integration or another explicitly supported commercial arrangement would need separate verification. [Official support response](https://github.com/allegro/allegro-api/issues/13771).
- **Amazon Poland:** requires accepted marketplace-specific Associates/Creators API access. Do not treat its image URLs as permission to cache them in R2 or use them as generation references. [Onboarding](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/onboarding/register-for-creators-api), [Polish image/cache restrictions](https://affiliate-program.amazon.pl/help/operating/policies).
- **IKEA:** no authorized official public Polish catalogue feed/API was established. Request a supported partnership/asset route if IKEA is essential; do not make an unofficial endpoint the reliability foundation.
- **Seller APIs** for a store platform are generally access to an authorized merchant's catalogue, not a public index of every merchant. A direct merchant XML/CSV/JSON feed can be excellent when the merchant grants access and the required image rights.

## Price reliability and image permission checklist for the first approved source

Verify a small current sample spanning at least three relevant furniture/decor categories and several size/colour variants. Record source URL, product/variant/seller identity, PLN gross/conditional price, quantity basis, availability, delivery exclusions, fetch time, feed update time and expiry. Compare sample records with current merchant pages using authorized access. Do not claim a full live quote when a feed is only updated periodically. Present unknowns explicitly and revalidate before render/selection confirmation where source capabilities permit.

Obtain the applicable permission for (a) displaying remote product images, (b) caching normalized copies in R2 for a stated period and (c) submitting references to an image provider and generating derived room images. These are separate uses; affiliate-feed access does not by itself establish all three. Until derivative use is verified, real-product cards/board may work while those assets are excluded from generation. No automated training use is needed.

Ask the chosen provider/merchant, without sending this automatically:

> Budujemy renti.tech: użytkownik wybiera meble do projektu wnętrza, widzi zdjęcia i aktualne ceny oraz przechodzi do sklepu. Czy możemy otrzymać feed/API dla polskiego rynku z identyfikatorem produktu i wariantu, ceną brutto PLN, dostępnością, wymiarami oraz adresami zdjęć? Prosimy też o warunki aktualizacji i limitów oraz potwierdzenie uprawnień do wyświetlania zdjęć, przechowywania znormalizowanych kopii do 30 dni i przekazywania ich jako referencji do generowania wizualizacji pomieszczenia przez zewnętrznego dostawcę AI. Prosimy o osobne wskazanie, które z tych zastosowań są dozwolone.

## Copyable continuation brief for Claude

Owner approves `rent-monitor` with default jurisdiction. Do not create another bucket or ask again about EU. Reuse the merged object-store seam, correct the EU-only endpoint validator with tests, securely map MEDIA_* to the existing verified R2 connection, update ADR 0014/policy docs and run the full `probe_media_store.py` locally and from the serving runtime. Resolve B-025 only with probe evidence; missing bucket-admin permissions do not block object I/O. Continue #448 → #449/#450 → #451 under the existing dependencies, preserving dirty checkout work. Node 24.22.0 is installed; activate it and run frontend checks instead of treating Node 22 as an owner blocker. Start catalogue access with a Polish furniture merchant feed through webePartners or the documented Convertiser Products API; Awin is another feed route. Do not rely on new Allegro public-search approval, unofficial IKEA APIs or Amazon image caching. Build/test independent work while publisher/merchant approval is pending; request only the concrete account acceptance/feed/token or image permission that cannot be obtained with existing authorized access. No paid image call without verifying remaining shared budget. Report implemented, fake-integrated and provider-verified evidence separately. The full quality/security/budget acceptance remains in `CLAUDE-INTERIOR-PROMPT-2026-10-21.md`.
