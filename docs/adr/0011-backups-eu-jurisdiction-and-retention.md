# ADR 0011 - Backups: EU jurisdiction and WAL-G retention of 14 days

- **Status:** accepted - **Date:** 2026-10-12 - **Decided by:** maintainer (owner decision D-14) - **Ticket:** RM-171
- **Amends:** blueprint section 4.7 (`wal-g delete retain FULL 7`), section 4.2 endpoint form; `docs/R2-SPEC.md`

## Context
Backups hold personal data (users, sessions, snapshots). A Cloudflare R2 bucket's jurisdiction is fixed at creation. The
blueprint kept WAL-G for 7 full backups, while the privacy design (`RUNBOOK-GDPR.md`) promises backups of 14 days / 56 days and
sizes the 70-day `erasure_log` on it.

## Decision
- The backup bucket `rentmonitor-backups` is created in the **EU jurisdiction**. The endpoint therefore carries the jurisdiction
  (`<account>.eu.r2.cloudflarestorage.com`); `AWS_ENDPOINT` and `scripts/check_r2_upload.py --jurisdiction eu` use it.
- WAL-G keeps **14 days** (`wal-g delete retain FULL 14`); daily dumps 14, weekly dumps 8 (56 days), as already documented.

## Consequences
- Extra storage is cents per month; the retention now matches what the privacy notice will say.
- The owner creates the bucket with the EU jurisdiction before the first real backup; an existing default-jurisdiction bucket
  (`rent-monitor`) stays for connectivity checks only.
