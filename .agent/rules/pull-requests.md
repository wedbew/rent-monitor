# Rule: every PR uses the template and its checklist

The template is `.github/pull_request_template.md`; GitHub fills it in automatically, and agents opening a PR with
`gh pr create` must pass `--body-file` built from it (never an empty or free-form body). Git flow itself
(branch names, title format, no direct pushes) is `agents.md` §6.

## Sections — all required

| Section | What goes in it |
|---|---|
| `Closes #<issue>` | The GitHub issue; `RM-n` in the title maps to issue `#n` |
| What changed | One paragraph, and the blueprint section(s) implemented |
| How it was tested | Named tests added or changed, plus the pytest summary line actually run (`uv run pytest -m "not e2e" -q`) |
| Definition of done | Every box ticked or struck through with a reason; never delete a line |
| Deviations from the blueprint | `None`, or what and why; a real deviation also needs the maintainer's approval and an ADR (`rules/architecture.md`) |

The two last checklist items map to rules: **Legal / GDPR** (`rules/legal-tags.md`) and **Context** (`rules/context.md`).

## Checklist semantics

- Title: `type(RM-<issue>): subject`, ≤ 72 chars; the `pr-title` workflow enforces it.
- Invariants: no `invariant` test deleted, skipped, `xfail`ed or weakened. If you believe one is wrong, stop and ask.
- Money: `Decimal` / `NUMERIC`; all financial math stays in `apps/deal-analyzer`.
- Tenancy: tenant-owned queries go through a `Principal`-scoped repository; foreign resources return 404.
- Migrations: expand-only; the contract step is a later PR. `pytest tests/migrations` and `squawk` pass.
- Golden `DealAnalysis` snapshots unchanged, or every diff explained under the section it affects.
- New dependency: name it and say why in the PR body (`agents.md` §4).

## Authoring

1. Target `staging`, never `main`. Open as draft until the local checks (`make lint types test`) pass.
2. Keep one concern per PR. Tick only what you verified; unverified boxes stay unticked with a note.
3. End agent-authored PR bodies with the attribution line the tool requires.
4. Never merge your own PR.

## Do not

- Remove or reword template sections to make a PR look complete.
- Paste secrets, real emails or customer data into a PR body.
- Claim a test passed without the summary line from a run you did.
