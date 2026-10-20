# Owner decisions for autonomous delivery — 2026-10-19

**State: delivery instructions consolidated.** This records direct owner replies in the current
conversation. Confirmed choices below are instructions, not proposals. Routine implementation/source/
versioned-policy choices are delegated. External approvals/configuration that were not evidenced stay
explicit external actions; they are not questions to repeat and not assumed approvals.

## Confirmed instructions

### Follow-up: existing R2 bucket approved — 2026-10-21

The owner explicitly accepts the existing private `rent-monitor` bucket and its default jurisdiction for product media: "i dont care about jurusdicationn in this case this is gouud enough". This supersedes the EU-jurisdiction requirement for product media in item 3 below, ADR 0014 and the interior execution prompt. It does not change the EU backup policy. Reuse the existing bucket/scoped object credentials, retain public access off, separate MEDIA_* application settings from backup settings, retain 30-day project/7-day abandoned-upload cleanup and account erasure. Do not require `rentmonitor-media`, ListBuckets/CreateBucket rights or a new token solely to satisfy the superseded policy. Update the endpoint validator and specifications, map the verified existing connection securely and run the complete media probe before resolving live readiness. B-025's owner decision is supplied; successful application/runtime verification remains implementation work. No further jurisdiction approval question is needed. See `docs/INTERIOR-POLAND-SOURCES-AND-FOLLOWUP-2026-10-21.md` for access research and the remaining #448–#451 handoff.

The numbered October 19 instructions below remain historical authority except where explicitly superseded above.

1. **Delegated implementation:** Claude may choose/document routine implementation, source selection
   and versioned analytical policies, create/split issues, and merge tested changes to `staging`.
   Continue independent work around external blockers. Existing boundaries remain: no destructive
   operations, weakened security, live customer payments or promotion to `main`.
2. **Fresh data:** do not copy POC datasets. Collect fresh data. POC repositories remain read-only
   requirements references, with no code/data/fixture import.
3. **Product media:** separate private **EU object storage**, never the backup bucket; ownership and
   metadata in Postgres. Store normalized, metadata-stripped images only. Report/project media expire
   after **30 days**; abandoned uploads after **7 days**. Account erasure removes media; existing backup
   expiry applies. Implement the architecture and lifecycle; activate an existing bucket only after
   verifying purpose and region. If provisioning is unavailable, implement/test the adapter and record
   the exact external provisioning action. This is explicit approval of the object-storage design
   proposed in the questionnaire; document the architecture decision without asking the same question.
4. **Paid provider tests:** up to **USD 5 total** across OCR/equipment/interior tests, **USD 0.50 per
   attempt**. These are cumulative batch limits, not per-worker/per-session allowances. Use one shared
   durable spend/reservation record across workers; count retries and ambiguous paid outcomes, retain
   existing monthly/provider controls, record actual usage and stop paid attempts at the limit.
   Do not automatically reanalyse historical reports. For conservative accounting include the prior
   ID4DACX canary's reported USD 0.0005845 in the batch total. Do not reset the allowance on restart.
5. **Paddle sandbox:** the owner says the product was already created in the sandbox dashboard via
   code and authorizes using the existing sandbox account to verify the integration. Inspect/reuse
   existing resources before creating duplicates. This is not live-mode payment authorization or
   evidence that product acceptance/accountant/legal review is complete.
6. **Confirmed gross pack prices:** **10 PLN for 1 report**, **40 PLN for 5 reports**, **70 PLN for
   10 reports**. The owner explicitly clarified the single-report price in the next question round.
7. **Payment/report failures:** the owner requests best-practice handling. Implement against the
   accepted ledger and payment contracts: no report grant from a redirect alone; verify signed
   provider events; idempotent grant/settlement; ambiguous checkout outcomes reconcile without blind
   duplicate purchase; failed audits release their report reservation and retries cannot double-charge.
   Preserve existing valid/degraded-report capture policy until a different policy is explicitly chosen.
   Test sandbox failure, abandonment, delayed/replayed events and audit failure separately. A failed
   report reservation is distinct from a provider payment refund; never invent a live refund action.
8. **Beta deployment:** Claude may deploy green staging to the existing beta VPS. The owner also
   requests transferring all missing application configuration there. Use secure app-scoped transfer
   mechanisms, never chat/log/commit secrets, preserve host-specific DB/origin/production values and
   validate using non-secret presence/health results. Record unavailable configuration by name, without
   blocking unrelated work. Permission to deploy does not authorize destructive operations, main
   promotion, insecure public exposure or arbitrary account/ruleset changes.
9. **Otodom operation:** validate filters/pagination with small probes first, then run the complete
   fresh bootstrap for all **727 locations** and nightly imports under existing throttle/request
   budgets. This is explicit collection authorization; no POC datasets may be copied. Record actual
   coverage and failures, not a completeness claim based only on catalogue cardinality.
10. **BDL financial-risk scope expanded:** the owner explicitly wants BDL demographics to inform
    financial assessment, including warnings about demographic decline and long-term investment risk.
    This supersedes the earlier assumption that BDL must remain permanently informational only.
    **Confirmed treatment:** calculate a separately visible **adverse scenario** showing effects on
    vacancy, rent growth and exit value, with a sourced long-term risk warning. Keep the base result
    separately visible and unchanged by this enrichment. Under the delegated analytical-policy
    authority, Claude must document/version the stress assumptions, source links, missing-data behavior
    and sensitivity bounds; a stress assumption is not an empirically proven causal forecast.
    Any quantitative integration must first document the approved modeling policy in ENGINE-SPEC/ADR,
    retain provenance and reproducibility, and keep all financial math in `apps/deal_analyzer` using
    Decimal with appropriate sensitivity/invariant tests. The scope change does not validate a causal
    coefficient or make an experimental location score equivalent to a property financial grade.
11. **Manual analysis:** required sale intent, whole ownership, asking price, area, room count and
    resolvable location. Unknown ownership blocks submission; optional fields remain unknown rather
    than zero. Drafts/uploads are free. A completed or degraded report consumes one credit, using
    existing failure-release, tenant isolation, idempotency and fractional/RENT rejection rules.
12. **Cancellation:** queued audits may be cancelled and release their reserved credit. Running
    audits cannot be cancelled and return **409**, then finish under existing settlement rules.
    Race tests must prove a cancel/start collision has one terminal outcome and one settlement.
13. **Interior beta:** first operation is one room photo → saved concept → optional generated image;
    Claude may choose a supported provider/model. It is **free for beta testers**, within the **same
    aggregate USD 5 provider-test budget**, not an additional allowance. Public paid generation remains
    disabled. Restrict beta operations to authorized testers, with durable job/budget/idempotency and
    original/generated separation; do not expose an unlimited free public generation endpoint.
14. **Signup allowance:** a newly verified account receives **3 free report credits**. Verification
    and duplicate-event handling must not grant them more than once.
15. **Purchased-credit expiry:** unused purchased credits expire **12 months after purchase**.
    Apply a documented calendar-month anniversary policy, show the actual expiry before purchase and
    in credit history, and test leap dates/time zones/lot ordering. Do not silently substitute 360 or
    365 days. Preserve refund/dispute/expiry and in-flight reservation consistency. Legal/accounting
    review remains an external sign-off; this is the owner's product-policy instruction.
16. **Paddle overlay CSP:** explicitly approved `style-src-attr 'unsafe-inline'` so the existing
    overlay can display. Do not relax script restrictions or unrelated directives. Configure only
    the required verified Paddle hosts and test the actual Caddy/checkout behavior. This is the
    specific security-policy exception approved by the owner, not blanket permission to weaken CSP.
17. **Required CI checks:** Claude may add existing frontend, browser-journey and visual jobs as
    required checks on `staging` and `main`, preserving every existing check/protection. Verify exact
    live check names and successful runs first; record before/after evidence. This does not authorize
    bypassing checks, weakening branch protection, arbitrary settings changes or merging into main.
18. **VPS drills:** bounded load and backup/restore drills are authorized on the beta VPS using
    synthetic providers and isolated disposable databases. Never overwrite/delete existing application
    data/volumes. Reserve resource/port/database ownership, avoid paid provider calls for synthetic load,
    and record actual memory/connection/restore results. A same-host disposable restore is not proof
    of the separate fresh-host gate unless that gate's exact environment/evidence is satisfied.

19. **Experimental BDL index:** publish the versioned experimental location index with sources,
    visible components, exclusions and limitations, alongside the adverse financial scenario. Claude
    selects source-verified metrics and documents coverage, freshness, peer/cohort, fiscal-comparability
    and scoring policies under the delegated authority; omit unresolved source variables, label proxies
    and withhold unsupported ranks. The base financial result stays separately visible and unchanged.
20. **Accuracy and POC comparisons:** the owner authorizes read-only comparison with POC reports for
    interim verification, while explicitly noting their prototype quality. Do not copy POC reports/
    datasets/code into this application or treat their answers as financial ground truth. Record any
    discrepancy, check it against the approved specification and fresh source inputs, and adjudicate
    it transparently. Build fresh hand-made regression examples and evaluation tooling now. As the
    integrated workflows are completed, deliver a proper testing strategy and expected-results template
    for testing, including input/source versions, scenario, expected result, tolerances, reviewer and
    evidence. Do not claim an owner-reviewed accuracy benchmark already exists; certification stays
    open until independently reviewed expected results are recorded. Do not repeatedly request a dataset.
21. **Finance source selection under delegation:** select and document a verifiable PL 10-year-yield
    source and research/version sourced CAPEX assumptions under item 1. Follow accepted engine behavior,
    freshness/provenance/fallback requirements and source-use constraints. Preserve the currently
    approved base exit-value formula; authority for the separate BDL adverse scenario is not authority
    to silently replace the base exit anchor or historical report assumptions. Unverifiable prices must
    remain explicitly unavailable/placeholder and cannot be certified by POC agreement.

## Configuration inventory supplied by the owner

The owner reports these **variable names**, not their values or verification results:

```text
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_S3_API
OPEN_ROUTER_API_KEY
BDL_API_KEY
GEMINI_API_KEY
GH_TOKEN
CLAUDE_CODE_OAUTH_TOKEN
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
MAIL_FROM
BETTERSTACK_SOURCE_TOKEN
BETTERSTACK_INGESTING_URL
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
SERVER_V1_USERNAME
SERVER_V1_PASSWORD
SERVER_V1_NAME
SERVER_V1_IPV4
SERVER_V1_IPV6
SERVER_USERNAME
SERVER_PASSWORD
SERVER_NAME
SERVER_IPV4
SERVER_IPV6
RESEND_API_KEY
RESEND_DKIM_TXT_DOMAINKEY
RESEND_SPF_CNAME_RSEND
RESEND_SPF_CNAME_SEND
RESEND_DMARC_CNAME_TXT
BETTERSTACK_TELEMETRY_API_TOKEN
BETTERSTACK_UPTIME_API_TOKEN
BETTERSTACK_DSN
BETTERSTACK_HOST
PADDLE_API_KEY
```

Use the current `.env.example`, typed settings, provider documentation and non-secret readiness checks
to build an explicit mapping. Names alone do not establish scopes, validity, provider mode, source
terms or configured runtime behavior. `OPEN_ROUTER_API_KEY` is an existing settings alias. Do not assume
`BETTERSTACK_DSN` is the browser application's DSN, `CLOUDFLARE_S3_API` is a bucket/endpoint/credential of
the required kind, or a Paddle API key is its separate webhook signing secret or public client token.
Verify before aliasing. The supplied list does not establish app media-bucket name/region/purpose,
Paddle webhook/client/price configuration, `VITE_*` build configuration, DB/queue settings or WAL-G
configuration. Discover what can be configured using existing authorized access; otherwise record
only missing variable/resource names and the exact external action.

For the authorized beta configuration transfer, use an app-scoped whitelist and a secure helper or
existing secret references; keep values inside the process/transport and out of model/tool output.
This is not authorization to inspect or dump the raw `.env`, copy it wholesale, or overwrite the
host's DB/password/origin settings. Do not deploy `GH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, server passwords,
unused model keys or infrastructure management tokens into API/worker/browser environments. A narrowly
needed deployment/monitoring helper may use its scoped credential internally. Never put secrets into
`VITE_*`; only explicitly public build values belong there. `SERVER_V1_*` names describe the old host,
not a reason to operate it. Preserve current-VPS target verification and least-privilege SSH access.

## External actions: tracked, not recurring owner questions

The owner answered the legal/accountant-status question with the key-name inventory. **No legal,
source-use, accountant or Paddle merchant/product-acceptance sign-off was supplied.** Credentials and
successful sandbox tests are not substitutes. Track those sign-offs under their existing issues and
keep paid public launch gated; continue authorized beta implementation, collection and verification.

Likewise, record unavailable resource provisioning, credentials/scopes, independently reviewed
expected results, real-device review, fresh-host restore evidence or manual main promotion as exact
external actions. First use available authorized interfaces and safe diagnostics; do not ask for a
secret, repeat settled product decisions, invent an approval or stop unrelated work.

For newly encountered uncertainty, use the delegated choice if reversible and within these boundaries,
document it and test it. If an action falls outside authorization, do not perform it: record the precise
external dependency and continue other ready work. If all safe work is exhausted, checkpoint it as
blocked/interrupted with resumable next commands; never claim the project is launch-ready.
