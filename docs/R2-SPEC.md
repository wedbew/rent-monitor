# Object storage and backup specification: Cloudflare R2 (closes #140)

Status: specification for the ops work (#15) and release gate 6 (#37). *Confirmed* = run or read in this repository;
*inferred* = from vendor documentation or reasoning, not yet exercised. Credentials live only in the private `.env`; no
account id, key id, token or endpoint host is written into a committed file.

## 1. What is confirmed today

- The owner's R2 connection works: `scripts/check_r2_upload.py` uploaded a 55-byte object and read it back identically
  (B-005c, 2026-10-12). It used the bucket named `rent-monitor` and the account's default (non-jurisdiction) endpoint.
- **Not tested anywhere:** WAL-G against R2 (the blueprint says so), the nightly `rclone` copy, a restore, lifecycle rules,
  and tokens scoped below "account admin". RPO 5 min / RTO 1 h are targets, not measurements (L-014).
- `scripts/backup_drill.sh` proves only the local logical dump/restore path; it is not gate 6.

## 2. Buckets, prefixes and jurisdiction

| Item | Decision | Why |
|---|---|---|
| Backup bucket | `rentmonitor-backups` (the name already in the blueprint and `.env.example`), prefixes `wal/`, `base/`, `dump/` | one place to apply lifecycle and one token pair |
| Existing bucket `rent-monitor` | keep for connectivity checks (`connection-tests/`) and later non-backup exports | the owner's proven bucket; do not mix it with backups |
| Jurisdiction | **EU, set when the backup bucket is created; it cannot be changed afterwards** (*inferred* from Cloudflare's R2 jurisdiction feature) | backups contain personal data (`app_user`, sessions, snapshots); an EU-jurisdiction bucket pins storage to the EU. The endpoint then carries the jurisdiction (`<account>.eu.r2.cloudflarestorage.com`), so `AWS_ENDPOINT` differs from the blueprint's default form. `check_r2_upload.py --jurisdiction eu` already supports this |
| Region question | **decided (D-14, ADR 0011): EU jurisdiction** | counsel may also need it for the processor list (B-012) |

## 3. Credentials (least privilege)

- Two R2 API tokens scoped to the backup bucket only: `backup-writer` (Object Read and Write, lives in the VPS `.env`) and
  `restore-reader` (Object Read only, kept in the password manager, used on the restore box). A third token for
  `rent-monitor` may stay as is.
- R2 tokens cannot be limited to a prefix and cannot forbid deletes, so the writer can in principle delete backups.
  Mitigations: bucket lock / retention rules if available on the plan (*inferred*, verify), the offline `age` private key
  and the weekly dumps copied by the owner, and heartbeats that notice a missing nightly backup.
- Names in `.env`: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`; WAL-G reads the `AWS_*` forms
  derived from them (blueprint §4.2). `S3_ACCOUNT_ID` / `S3_API_KEY` are only read by the connectivity script: a Cloudflare API
  token is not an S3 secret; the script derives S3 credentials from it only if the token verifies.
- Rotate both tokens every 90 days and after any suspicion of exposure (*recommendation*); a rotation is: create new,
  update `.env`, restart the backup container, confirm a nightly success, delete the old token.

## 4. WAL-G and the nightly dump

- WAL-G in the Postgres image: `archive_mode=on`, `archive_command='wal-g wal-push %p'`, `archive_timeout=300` (gives the
  5-minute RPO target), `wal-g backup-push` nightly, encryption with `WALG_LIBSODIUM_KEY`, compression zstd (blueprint §4.7).
- Second copy: nightly `pg_dump` encrypted with `age` (public key in `BACKUP_AGE_RECIPIENT`, private key offline) copied with
  `rclone` and verified with `rclone check`. It is version independent and survives a WAL-G problem.
- **Retention must be reconciled (found while writing this):** the blueprint runs `wal-g delete retain FULL 7`, about 7 days
  of point-in-time restore, while the privacy design and `RUNBOOK-GDPR.md` state backups of 14 days / 56 days and the
  `erasure_log` is kept 70 days for that reason. **Decided (D-14, ADR 0011): WAL-G keeps 14 days (`retain FULL 14`)**, dumps keep
  14 daily + 8 weekly (`BACKUP_RETENTION_DAILY`, `BACKUP_RETENTION_WEEKLY`), so the longest copy is 56 days and the 70-day
  erasure window stays correct. The blueprint line is updated accordingly.
- Keys: `WALG_LIBSODIUM_KEY` and the `age` private key are stored offline and in the password manager. The blueprint sample
  value (`change-me-...`) is a placeholder and must never be used; without the key a backup is unreadable.

## 5. Restore drill and RPO/RTO

| Drill | How often | What it proves | Owner |
|---|---|---|---|
| Local logical dump/restore (`scripts/backup_drill.sh`) | each release | the dump/restore path and row counts | agent |
| WAL-G point-in-time restore on a fresh VPS, timed | before launch (gate 6, #37), then quarterly | RPO and RTO, key custody, `restore-reader` token works | **owner** |
| Re-erasure after restore | with every drill | `rm_core.reapply_erasures` removes users erased after the backup | agent + owner |

Success: restored database passes the invariant/ledger checks (`ledger_mismatches` is empty), the target timestamp is
within 5 minutes of the intended one, and the elapsed time is under 1 hour. Until a drill passes, RPO and RTO stay
**targets** and are described that way everywhere (L-014).

## 6. Failure handling and alerts

- Heartbeats and the alert catalogue are in `docs/OBSERVABILITY-SPEC.md` (nightly backup heartbeat, success and `/fail`).
- Also watched: `pg_stat_archiver.failed_count` increasing or `last_archived_time` older than 15 minutes (a host check
  that withholds the readiness heartbeat); R2 bucket size above 7 GB of the 10 GB free tier (blueprint); VPS clock skew (R2
  rejects signatures when the clock is off by more than about 15 minutes, so NTP must be on; *inferred* from S3 signing rules).
- A failed WAL push never blocks the database for long: PostgreSQL retries `archive_command`, but unarchived WAL fills the
  disk, so the disk alert in the catalogue is part of this design.

## 7. GDPR and legal

`GDPR[processor]`: Cloudflare stores encrypted backups that contain personal data. `GDPR[retention]`: 14 days for WAL and
daily dumps, 56 days for weekly dumps, lifecycle rules enforce it on the bucket. `GDPR[erasure]`: erased users are removed
from live data at once; backups age out; a restore re-applies erasures from the exported `erasure_log` hashes
(`docs/RUNBOOK-GDPR.md`). Open for counsel: the DPA with Cloudflare, the EU-jurisdiction choice (D-14), and the wording of the
backup retention in the privacy notice (B-012). No `LEGAL[...]` tag applies.

## 8. Test plan

- Unit: retention arithmetic (which dumps a 14/8 policy keeps) if implemented in Python; the backup script's argument and
  environment handling with a fake `rclone`/`wal-g` on the path.
- Integration (#15): the backup container against a **MinIO Testcontainer** (S3 compatible, no network): upload, `rclone check`,
  prune, and a restore of a small database; CI never talks to Cloudflare.
- The owner-run `scripts/check_r2_upload.py` stays the only live check; it is never run in CI.
- Gate 6 (#37): the timed WAL-G restore above.

## 9. Environment names and owner checklist

Names are already in `.env.example`: `R2_*`, `S3_*` (script only), `BACKUP_AGE_RECIPIENT`, `BACKUP_RETENTION_DAILY`,
`BACKUP_RETENTION_WEEKLY`, `WALG_S3_PREFIX`, `WALG_COMPRESSION_METHOD`, `WALG_LIBSODIUM_KEY`, `BETTERSTACK_HEARTBEAT_BACKUP_URL`.

1. Create `rentmonitor-backups` in the **EU jurisdiction** (decided, ADR 0011; it cannot be changed afterwards).
2. Create the `backup-writer` and `restore-reader` tokens; put the writer in the VPS `.env`, the reader in the password manager.
3. Generate the `age` key pair (`age-keygen`) and a 32-byte libsodium key; store both offline.
4. Set the bucket lifecycle rules to 14 d for `wal/`, `base/` and daily dumps, 56 d for weekly dumps.
5. Run the gate 6 drill on a fresh VPS before launch.
