# Rule: tag legally sensitive features and GDPR-relevant code

Some features may be legally risky (Otodom scraping and EU database rights, analysing listing URLs, downloading and
analysing listing photos with a vision LLM) or process personal data (GDPR / RODO). **We still ship them.** The rule is
that every such action is *tagged*, in code and at runtime, so legal review, a takedown or a kill-switch can find
and act on it quickly. A tag means "needs legal attention", not "illegal". Never state in code, docs or PRs that a
feature is or is not lawful — that is for counsel (blueprint §5, `limitations.md`).

## Tag grammar (greppable, one line, directly above the code it covers)

```python
# LEGAL[scraping]: fetches Otodom _next/data; ToS + EU database-right exposure (RM-123)
# LEGAL[images]: downloads listing photos and sends them to OpenRouter vision (RM-123)
# GDPR[personal-data]: stores email, name, avatar_url (RM-45)
```

Format: `LEGAL[<area>]` or `GDPR[<category>]`, then `:` and a short factual reason, then `(RM-<issue>)`.
In SQL / Alembic use `-- LEGAL[...]`; in TS/YAML use the language's comment with the same token; in Pydantic or
SQLAlchemy models also put it in the column/field `comment=` or `description=` when it is personal data.

| Tag | Use for |
|---|---|
| `LEGAL[scraping]` | Any fetch of Otodom / Moniter / other third-party pages or APIs; `curl_cffi` impersonation; host throttle and circuit breaker; `listing_snapshot` storage and its 6 h cross-tenant sharing |
| `LEGAL[url-analysis]` | Accepting and resolving user-supplied listing URLs / IDs (`AuditCreate.listing_ref`, `OTODOM_REF_RE`) |
| `LEGAL[images]` | Downloading, resizing, caching or OCR/vision-analysing listing photos and floor plans; sending them to a third party |
| `LEGAL[third-party-data]` | Re-using GUS BDL, Cenogram, Moniter, Nominatim data: licence / attribution / redistribution limits |
| `LEGAL[republication]` | Anything that shows or exports third-party content to users or other tenants (reports, Markdown views, API results containing snapshot fields) |
| `LEGAL[tax-invoice]` | VAT invoices, KSeF, corrective invoices (accountant-owned treatment) |
| `GDPR[personal-data]` | Columns, fields, logs or payloads holding personal data: email, name, avatar, IP, user agent, session, Google `sub`, NIP / buyer data, seller names or phones inside raw listing payloads |
| `GDPR[processor]` | Sending personal data to a processor or sub-processor: Google, Stripe, Resend, Fakturownia, OpenRouter, Better Stack (errors via the Sentry SDK), Umami, OVH, Cloudflare R2 |
| `GDPR[retention]` | Retention / deletion jobs and TTLs: sessions, login tokens, snapshots, `audit_event`, backups (14 d / 56 d) |
| `GDPR[erasure]` | Account deletion, cascade paths, export / access-request code, backup-restore re-deletion handling |
| `GDPR[consent]` | Cookies, analytics events, marketing email, anything needing consent or a notice |

New area? Add a row here and to `rm_core.legal` in the same PR; do not invent tags ad hoc.

## Runtime tagging

Each tagged *action* (not every helper) also carries its tags at runtime, so they appear in logs, audit history and
can later drive a flag:

- A single registry `packages/rm_core/legal.py` defines `LegalTag` (`StrEnum`) with the values above
  (`scraping`, `images`, …) — the code comments and the enum must use the same names.
- Tagged pipeline stages bind `legal_tags=[...]` in structlog and include it in the `audit_event.payload` for the
  stage (fetch → `scraping`, vision → `images`, ocr → `images`, etc.).
- Tagged features keep their own feature flag (`feature_flag`, blueprint §3) or settings switch where practical, default
  **on**, so a legal decision can disable one capability without a deploy. Adding the flag is not a reason to hide the
  feature or change its behaviour.
- Never log personal data values; log ids and tag names.

## During migration, refactor and re-engineering

Re-implementing POC behaviour (fetchers on `curl_cffi`, engine, importers) or deleting `frontend/server/*.ts`. The POC carries no
tags, so use `CONTEXT.md` §6 as the hot-spot list:

1. Before you touch a file, `grep -rnE "LEGAL\[|GDPR\[" <path>` to see existing tags. Tags move with the code; never
   drop one in a refactor.
2. While you are in the file, tag every untagged site that matches the table, even if your ticket is unrelated.
   It is a drive-by exception to "no scope creep"; keep it to comment/`comment=` additions.
3. Code deleted or replaced → the replacement carries the same tags. Say in the PR body if a tagged feature is removed.
4. New table or column holding personal data → tag it, and state its retention and erasure path (cascade on
   `app_user`, TTL job, or "kept for tax reasons" with the reason).
5. New third-party call that receives personal data or listing images → tag `GDPR[processor]` / `LEGAL[images]`.

## PR checklist

The PR body has a **Legal / GDPR** line: tags added, changed or removed, and any untagged-but-suspect code you
found and did not touch. Surfaced uncertainty goes to `docs/LIMITATIONS.md` (see `limitations.md`). Inventory command:

```bash
grep -rnE "(LEGAL|GDPR)\[" --include='*.py' --include='*.sql' --include='*.ts' --include='*.tsx' --include='*.yml' packages services apps migrations scripts frontend deploy
```

## Do not

- Remove, skip or disable a feature because it is tagged; tagging is how we keep it while managing the risk.
- Put legal conclusions, advice or "this is legal/illegal" claims in tags.
- Weaken an invariant or tenant isolation to satisfy a tag.
- Include real personal data in tags, fixtures or logs.
