# Architekt wnętrz: verification and implementation recommendation

Verified 2026-10-21 (Europe/Warsaw). Current checkout: `staging`, `422f72f`.
Research and handoff for #284; no feature implementation, deployment or infrastructure provisioning is claimed.

## Confirmed current state

| Area | Evidence | Result |
|---|---|---|
| Frontend | `frontend/routes.tsx:170`, `frontend/shell/navigation.ts:57–62` | `/app/interior` renders `PendingPage`; navigation marks it unavailable. This is an unfinished feature, not merely a hidden working screen. |
| Backend | Current `packages/`, `services/`, `apps/` search; `rm_core.seed`, `rm_core.ledger` | Reserved `redesign` flag (off) and credit-cost entry exist; no implemented interior project/generation journey was found. |
| Media | `packages/rm_core/media.py`, `docs/LIMITATIONS.md` L-051 | Tenant-scoped manifest metadata exists. No application R2 binary adapter/configuration was found; metadata alone is not an image store. |
| Issue | Live GitHub read of #284, OPEN | UI acceptance includes original/generated labels, operation progress/errors/retry and cost. Older scope/cost blockers must be reconciled with the October 19 owner decisions. |
| Existing R2 | Fresh authorized upload/read-back using `scripts/check_r2_upload.py` | PASS for bucket `rent-monitor`, default jurisdiction endpoint. 43 bytes read back exactly. This verifies existing object read/write credentials, not product media readiness. |
| Product R2 | `.env.example`, typed settings, Compose and name-only private configuration checks | No configured product bucket name was found. EU jurisdiction, private access, purpose, delete permission, lifecycle and deployed runtime access remain unverified. This does not prove no such bucket exists in the account. |

The first fresh probe failed before any object request: it expects `S3_ACCOUNT_ID` or `R2_ACCOUNT_ID`, while the configured name is `CLOUDFLARE_ACCOUNT_ID`. A temporary, process-only adapter mapped that account name and reran the existing probe with the existing explicit R2 S3 keys. No `.env` or application file was changed; no secret value was emitted. The initial sandbox dependency download also failed on DNS; the network-enabled retry succeeded. Neither failure establishes missing/invalid credentials.

Probe artifact retained, as the existing checker specifies:

- Key: `connection-tests/20261020T221830Z-0cc8783876164c6b913d985bb763bbdd.txt`.
- SHA-256: `671ef488d4acdb28ebc793ab62f8677d6746ce3efd3b4d46928a569892a1ac74`.
- The key uses UTC; its date is October 20, while the verification date in Warsaw is October 21.
- No delete, browser upload, public-access, EU-bucket or VPS-runtime test was performed.

## POC comparison: requirements, not reusable implementation

Read-only reference: `/Users/marcin/Projects/otodom-rent-report`, HEAD `00ab3f9` during inspection; this differs from the older pin in `CONTEXT.md`. Relevant files were `apps/deal-analyzer/src/deal_analyzer/redesign.py`, `frontend/server/redesign.ts` and `frontend/src/lib/redesign.ts`. No files/data were copied or imported.

Useful requirements: select one photographed room, preserve geometry and user constraints, keep source and output distinct, save the concept even if image generation fails, retain history, distinguish unknown dimensions and ambiguous room identity.

Observed limitations:

1. The LLM supplies rough new/used PLN ranges and confidence. These are explicitly unverified estimates, not seller quotes; confidence cannot validate them.
2. Product discovery is a name encoded into Allegro/OLX/Vinted search URLs. It does not resolve a product ID, variant, seller, availability, image or observed offer price.
3. Image generation receives the room photograph and a text description; it does not receive retrieved product reference images. A generated sofa cannot be claimed to be a particular purchasable SKU.
4. Artifacts use local report files; a Node wrapper launches a Python subprocess and guards generation with a process-local boolean. This is not durable multi-worker job coordination or tenant isolation.
5. Price ranges/totals use floats. New returned/persisted money must use Decimal/NUMERIC and remain server-calculated under this repository's rules.

## What large companies publicly document

| Company | Documented approach | Lesson for this application |
|---|---|---|
| IKEA Kreativ | Room reconstruction/erasing plus catalogue-linked 3D furniture that can be placed, swapped and rotated. [IKEA announcement](https://www.ikea.com/us/en/newsroom/corporate-news/ikea-launches-new-ai-powered-digital-experience-empowering-customers-to-create-lifelike-room-designs-pub58c94890/), [Polish support](https://support.home-design.ikea.com/hc/pl-pl/articles/360038999793-Co-mog%C4%99-zaprojektowa%C4%87-w-mojej-przestrzeni) | Product identity and geometry come from catalogue assets. Using an IKEA shopping tool does not grant external catalogue/API or 3D-asset access. |
| Wayfair Decorify/Muse | Decorify generates a room, then visually matches similar products from its catalogue. Muse connects inspiration to catalogue browsing. [Engineering description](https://www.aboutwayfair.com/careers/tech-blog/spatial-an-evolution-in-computing), [Muse engineering interview](https://www.aboutwayfair.com/category/tech-innovation/inside-muse-a-q-a-with-shrenik-sadalgi-director-of-software-engineering) | Generation followed by similarity matching is useful inspiration, but is not evidence that the pictured item equals the offer. |
| Amazon shopping assistant | Product catalogue knowledge, multiple models and retrieval support recommendations. The Rufus article records its May 13, 2026 rename to Alexa for Shopping. [Amazon description](https://www.aboutamazon.com/news/retail/amazon-rufus-ai-assistant-personalized-shopping-features) | Ground recommendations in retrieved product records; keep prices and stock in the structured commerce layer. This is a design inference, not access to Amazon's internal system. |

## Source access and image rights

**Amazon:** current official Creators API documents SearchItems, GetItems, GetVariations and image URLs. Poland has marketplace-specific configuration. Access requires the appropriate accepted Associates account and API onboarding; no access was verified here. [API reference](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference), [registration prerequisites](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/onboarding/register-for-creators-api), [marketplace configuration](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/concepts/common-request-headers-and-parameters).

The Polish program policy's IP licence clause (h) prohibits storing/caching product advertising images, permits image-link caching up to 24 hours and limits caching of other product content. Therefore Amazon product images must not automatically be ingested into R2. Verify permitted display, refresh, comparison, attribution and derivative/generative usage for the actual integration; API access alone does not grant those additional rights. [Polish policies](https://affiliate-program.amazon.pl/help/operating/policies).

**IKEA:** this research did not establish an openly usable official Polish product-price/image API or licensed feed for this application. Do not present community reverse-engineered endpoints as a supported partnership. Verify access with IKEA/a licensed supplier; retain a provider seam and a visible unavailable state until actual access is established. A first-party merchant/manufacturer feed with explicit image reuse and generation rights may be a better first live source. No IKEA, Amazon or other catalogue integration was exercised.

## Recommended design

Use a bounded product-selection agent inside the existing Python worker. It can interpret the brief and rank tool-returned candidates; it cannot invent commercial fields, browse arbitrary URLs or buy anything. Begin with typed provider search and product/offer lookups. Add embeddings/reranking only when measured retrieval quality warrants it; Postgres remains the source of application state.

Workflow: room photo → design brief → retrieve products → validate exact variant/offer → user selection → revalidate price/stock → save immutable design revision → optional reference-conditioned render. Keep a real-product board with merchant images alongside the visualization. The board is the dependable representation of selected items; a generative render remains an illustration unless identity fidelity has separately been demonstrated. Exact room placement would require appropriate 3D assets/geometry and is a larger capability.

Each offer needs provider/product/variant/seller identity, source URL, observed price and currency, VAT/delivery/discount conditions when known, availability, checked-at/expiry timestamps, dimensions and their source, image source and usage policy. Separate catalogue product identity from an expiring seller offer. Show unavailable/stale/conditional quotes honestly; show known-item subtotal and missing items, never label an incomplete basket as a complete renovation budget. Checkout can change prices.

R2 should hold permitted normalized source-room images and generated output, with metadata/ownership in Postgres. Approved policy already exists: separate private EU product storage; 30-day project/report media; 7-day abandoned uploads; account erasure. Do not ask the owner to decide these again. Python's S3 client fits the existing architecture; introducing Workers, a Node service or another database is unnecessary. [Python example](https://developers.cloudflare.com/r2/examples/aws/boto3/), [EU endpoint rules](https://developers.cloudflare.com/r2/reference/data-location/).

Prefer same-origin authenticated upload/delivery for the first slice. This avoids exposing credentials and avoids a browser-to-R2 CORS dependency. If direct uploads are justified, use constrained short-lived presigned PUT URLs, finalization validation and exact allowed origins. Presigning is not authorization for subsequent users and does not itself configure CORS. [Presigned URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/), [CORS](https://developers.cloudflare.com/r2/buckets/cors/).

## Remaining verification and action

The existing R2 connection requires no owner action to prove basic read/write. Product storage still needs discovery/provisioning and application integration. Automatically reuse or provision an authorized private EU product bucket if existing access permits; otherwise request only the exact unavailable bucket/token/runtime setting. Never repurpose the verified default-jurisdiction test bucket on the strength of this check.

No owner-only provisioning failure has been established yet, so this audit does not invent a new BLOCKERS entry. Claude must record a blocker if its concrete discovery/provisioning attempt establishes one. The implementation prompt is [CLAUDE-INTERIOR-PROMPT-2026-10-21.md](CLAUDE-INTERIOR-PROMPT-2026-10-21.md).
