# ADR 0014 - Product media in a private object store

- **Status:** accepted, amended 2026-10-21 (default jurisdiction approved, RM-453) - **Date:** 2026-10-21 - **Decided by:** owner (OWNER-DECISIONS-2026-10-19, media architecture) - **Ticket:** RM-447, #284
- **Amends:** blueprint "all state lives in Postgres"; narrow exception for image bytes only

## Context
The interior tool and report galleries need room photos, permitted product reference images and generated renders.
Postgres `bytea` for images would bloat backups and WAL; the backup bucket must stay separate from user media.

## Decision
- Image **bytes** live in a private Cloudflare R2 bucket with its own `MEDIA_*` settings, apart from the backup settings.
  **Amendment (owner, 2026-10-21):** the existing private `rent-monitor` bucket on the **default jurisdiction** is accepted for
  product media ("good enough"); this supersedes the original EU-bucket requirement for media only. The EU backup policy
  (ADR 0011) is unchanged. Credentials are object-scoped; ListBuckets/CreateBucket rights are not needed. Ownership, state, digests and
  retention live in Postgres; Postgres stays the source of truth.
- The endpoint must match `https://<32-hex account>[.eu].r2.cloudflarestorage.com` exactly (default or EU); settings reject any
  other host, scheme, port, userinfo, path or query.
- Delivery is an authenticated same-origin API route. Buckets stay private; no public URL, no wildcard CORS. Direct browser
  PUT is not used in the first slice.
- Keys are `u/<user>/<purpose>/<uuid>` built only by `rm_core.object_store.media_key`.
- Retention: project and report images 30 days, abandoned uploads 7 days, removal with the account. A DB-driven cleanup job
  deletes objects and rows; a reconciler removes orphans in either direction. Bucket lifecycle rules are a backstop only.
- Write order: row first, object second; the reconciler deletes rows whose object never arrived and objects without a row.
- The client is boto3 with explicit timeouts, bounded retries and thread offload, behind an injectable `ObjectStore`.

## Consequences
- New dependency `boto3` (maintained S3 SDK; the standard library has no SigV4 client). Imported lazily.
- `scripts/map_media_env.py` fills empty `MEDIA_*` from the existing R2 connection without printing values;
  `scripts/probe_media_store.py` must pass locally and on the serving host before live uploads are enabled (B-025).
- Not a RPO/RTO claim: media is not covered by the DB backup drill.
