# RM-<issue>: integration handoff

- **State:** pending | reconciled (select one; template is not an actual handoff)
- **Lane / real issue / PR:**
- **Branch / base SHA / tested worker head SHA:**
- **Writer:** worker | integrator; transfer SHA/time and explicit acknowledgement
- **Owned implementation/test paths:**
- **Reserved shared code / contract producer / merged SHA:**
- **Runtime isolation:** database, ports, Compose project, coverage/artifact paths

## Shared documentation deltas

| File and section | Required factual change or explicit not-affected reason | Evidence and status |
|---|---|---|
| CONTEXT | | |
| STATUS | | |
| BLOCKERS | | |
| LIMITATIONS | | |
| README | | |
| CHANGELOG | | |
| BACKLOG / ROADMAP / feature specs | | |
| BLUEPRINT / ENGINE-SPEC / ADR / env example / privacy docs | | |

## Blockers, limitations and decisions

Use temporary issue-local keys until canonical integration. Name only affected issues and exact owner
action; distinguish offline implementation from blocked live validation. Link existing decisions rather
than asking again. Never supply guessed retention, pricing, weights or provider guarantees.

## Checks and integration work

- Exact worker commands/results (including SKIPPED):
- Generators/migrations and compatibility checks required after merging staging:
- Contract/source changes to preserve from other lanes:
- Next command / safe next independent task:

## Integrator reconciliation

- Final canonical sections/IDs and decisions linked:
- Integrated head SHA and actual rerun summaries:
- Remaining unresolved items (must be none for required same-PR docs before readiness):
