# Market data artifacts

Machine-readable records of how the Otodom rental corpus was seeded and what it covers. Counts, paths and states
only; no listing content, no seller data.

| File | What it is | How it is made |
|---|---|---|
| `otodom-catalogue-v1.json` | The place catalogue (787 gmina-level places Otodom lists for flats), with the sitemap's SHA-256 and fetch time, the rule, a reconciliation against the owner's stated 727 (it does not and cannot claim identity with that list, L-092), the catalogue checksum and one census record per place (offers at probe time, pages) | `uv run python scripts/seed_catalogue.py discover --out docs/market/otodom-catalogue-v1.json` (1 request per second, resumable with `--cache`); seeded with `... apply --file ...` |
| coverage manifests | The state of the corpus over time: per place `complete_nonempty`, `complete_empty`, `running`, `partial`, `blocked`, `failed`, `pending`, `disabled`; pages read against expected; offers stored; last successful refresh | `uv run python scripts/market_manifest.py --out docs/market/coverage-<date>.json` (added with the run they describe) |

A place counts as covered only after a published run proved it (a valid empty search counts, a blocked, partial or
pending one never does). A regenerated catalogue with a different checksum is a **new version**, never an edit of
version 1. Rules and limits: `docs/OTODOM-NIGHTLY-IMPORT.md`, L-050 (resolved), L-091, L-092 in `docs/LIMITATIONS.md`.
