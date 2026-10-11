# Runbook: GDPR retention, erasure and access requests

Code: `rm_core/privacy.py`, nightly task `rm_worker/tasks/retention.py`. Retention periods are **proposed** defaults (settings
`RETENTION_*`, blocker B-012); counsel confirms them before launch. Tags: `GDPR[retention]`, `GDPR[erasure]`, `GDPR[personal-data]`.

## What is kept for how long (proposed)
| Data | Rule |
|---|---|
| `user_session` | deleted 7 days after `expires_at` |
| `login_token` | deleted 1 day after expiry or use |
| `listing_snapshot` | deleted after 30 days if no audit references it; otherwise the raw payload (may hold seller names/phones) is replaced by `{}` and the row stays |
| `audit_event` | deleted after 30 days; the audit `result` is kept until the account is erased |
| `erasure_log` | 70 days (longest backup 56 days + restore window); holds only `sha256(user_id)` |
| Invoices (Fakturownia) | kept for tax reasons; not erased by us |

The sweep runs nightly at 03:17 (queue `ops`, one at a time) and works in batches of 1,000 rows, each in its own short transaction.

## Erase an account (until the API endpoint exists, RM-82)
In a Python shell on the box (never against production from a laptop):
```python
async with session.begin():
    report = await rm_core.privacy.delete_account(session, user_id)
# report.stripe_customer_id -> delete that customer in the Stripe Dashboard/API (processor erasure)
```
One statement removes every tenant-owned row (FK cascade), and `erasure_log` records the hash. Calling it again is harmless.

## Access request (export)
`await rm_core.privacy.export_user_data(session, user_id)` returns one JSON-serialisable document with the profile,
identities, sessions (including IP and user agent), credit ledger, subscriptions, usage periods, audits with results, saved
listings and feature overrides. Token hashes and other tenants' data are never included. Send it to the requester by a
channel the owner verifies.

## After restoring a backup (re-delete erased users)
A restored backup can contain accounts that were erased after it was taken. Before reopening traffic:
1. **Before** the restore, export the current hashes: `psql -Atc "select user_hash from app.erasure_log" > erased.txt`
   (store it off the box; for a total host loss use the latest nightly copy of this list kept with the backups).
2. Restore, then run `rm_core.privacy.reapply_erasures(session, hashes_from_erased_txt)`; it deletes any user whose
   `sha256(id)` is in the list and logs it again.
3. Note the count in the incident log. Hashes older than 70 days are no longer needed because no backup is older than 56 days.
