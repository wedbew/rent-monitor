# ADR 0014 - Product media in a private EU object store

- **Status:** accepted - **Date:** 2026-10-21 - **Decided by:** owner (OWNER-DECISIONS-2026-10-19, media architecture) - **Ticket:** RM-447, #284
- **Amends:** blueprint "all state lives in Postgres"; narrow exception for image bytes only

## Context
The interior tool and report galleries need room photos, permitted product reference images and generated renders.
Postgres `bytea` for images would bloat backups and WAL; the backup bucket must stay separate from user media.

## Decision
- Image **bytes** live in a private Cloudflare R2 bucket in the **EU jurisdiction**, separate from the backup bucket and its
  credentials (`MEDIA_*` settings, scoped token: Object Read & Write on that bucket only). Ownership, state, digests and
  retention live in Postgres; Postgres stays the source of truth.
- The endpoint must be `https://<account>.eu.r2.cloudflarestorage.com`; settings reject any other form.
- Delivery is an authenticated same-origin API route. Buckets stay private; no public URL, no wildcard CORS. Direct browser
  PUT is not used in the first slice.
- Keys are `u/<user>/<purpose>/<uuid>` built only by `rm_core.object_store.media_key`.
- Retention: project and report images 30 days, abandoned uploads 7 days, removal with the account. A DB-driven cleanup job
  deletes objects and rows; a reconciler removes orphans in either direction. Bucket lifecycle rules are a backstop only.
- Write order: row first, object second; the reconciler deletes rows whose object never arrived and objects without a row.
- The client is boto3 with explicit timeouts, bounded retries and thread offload, behind an injectable `ObjectStore`.

## Consequences
- New dependency `boto3` (maintained S3 SDK; the standard library has no SigV4 client). Imported lazily.
- The owner creates the bucket and token (B-025); live storage stays off until `scripts/probe_media_store.py` passes.
- Not a RPO/RTO claim: media is not covered by the DB backup drill.
