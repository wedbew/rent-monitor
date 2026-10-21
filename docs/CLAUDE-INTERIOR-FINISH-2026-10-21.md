# Claude: finish Architekt wnętrz through passing frontend E2E

Owner instruction: finish the interior feature; do not stop after the API slice or a green backend PR. Before continuing, verify the current implementation/checks, commit the relevant unstaged interior documentation, and continue through successful frontend end-to-end acceptance. Read `.agent/agents.md` and the full `CLAUDE-INTERIOR-PROMPT-2026-10-21.md`; this brief tightens completion criteria and supersedes dated progress summaries, not repository security/budget rules.

## Verified checkpoint — recheck before acting

Read-only verification on October 21:

- GitHub staging is `d7c4d0ef3ae973eb4af83e493b40e5c5903ed110`. #448 is closed and PR #455 is merged: projects/items, migration 0024, image normalization, immutable revisions, retention/deletion queue, worker sweep and exact server basket arithmetic exist.
- #453 / PR #454 is merged: the existing private default-jurisdiction `rent-monitor` bucket is approved and supported. STATUS/BLOCKERS record the complete local storage probe as passed. B-025 now says serving-host verification is agent work, with no new owner decision required.
- Your `rm-456-interior-routes` worktree at `/Users/marcin/Projects/rent-monitor/.claude/worktrees/rm-456` is clean at `54d5a61`, with 12 `/api/interior` operations, beta gating, tenant checks, protected image delivery, erasure wiring, smoke scenarios, API tests and generated contracts/fixtures. #456 is OPEN; no PR for that branch was visible when checked. Your reported background local CI result was not independently rerun here; collect it and confirm its exact commit.
- #449 catalogue, #450 generation and #451 frontend are OPEN. `frontend/routes.tsx:170` in your worktree still uses `pending("interior", "/app/interior")`. No interior browser journey was found under `frontend/e2e/journey`.
- PR #455 has a successful existing `frontend-journey` check, but `frontend`, `frontend-e2e` and `frontend-visual` were SKIPPED. That is existing application regression evidence, not interior feature acceptance. Ignore superseded failed PR-title attempts when evaluating the latest required head checks, but never call skipped frontend jobs passed.
- The root checkout remains older at `422f72f` with owner/interior docs and unrelated modifications. Do not pull/reset it blindly or switch another session's branch.

Re-read live issue/PR/head/check state first so you do not duplicate work completed since this checkpoint. Distinguish source inspection, reported local test results, actual CI results and provider evidence.

## Commit the interior documentation

The owner explicitly asks you to include the unstaged/untracked interior documentation in normal issue-scoped commits/PRs. Inspect and reconcile these paths against staging:

- `docs/CLAUDE-INTERIOR-PROMPT-2026-10-21.md`
- `docs/INTERIOR-RESEARCH-2026-10-21.md`
- `docs/INTERIOR-POLAND-SOURCES-AND-FOLLOWUP-2026-10-21.md`
- `docs/CLAUDE-INTERIOR-FINISH-2026-10-21.md` (this file)
- Interior-related hunks in `CONTEXT.md` and `docs/OWNER-DECISIONS-2026-10-19.md`.

The October 21 owner-decision addendum already exists in your newer worktree/staging; do not duplicate it or overwrite newer canonical content with the older root file. Port/reconcile only the still-missing documentation changes and commit explicit paths/owned hunks. The owner authorizes adopting these interior documents into your implementation handoff; follow checkout ownership rules. Do not stage unrelated `scripts/dev_stack.sh` or `docs/SESSION-REPORT-2026-10-11-to-18.md` changes merely because they are dirty. Never `git add -A`, discard dirty work or claim docs are committed without a commit SHA. Ensure committed document links resolve.

Correct outdated current-status wording while integrating: STATUS still calls the media settings EU-only even though the validator supports default/EU, and older slice rows describe missing projects/API after later rows implement them. Mark earlier slices as historical scope or reconcile their remaining gaps. Keep live verification limits explicit; do not erase limitation history.

## Finish the implementation

1. Collect the running #456 local CI outcome, fix failures, push/open its PR, monitor required checks/review and merge only under the existing staging authority. Continue after that merge.
2. Finish #449 with typed product/variant/offer provenance, fresh/expired price and stock states, exact server subtotals and bounded selection over actual provider candidates. Use the verified Polish-source research: webePartners merchant feeds or Convertiser's Products API, with Awin as another feed route. Do not wait exclusively for Amazon/IKEA, invent offers or treat generic search links as product matches. Verify existing account/feed access first. If acceptance/token/image permissions require the owner, record the exact external dependency and continue independent work; do not mark the live catalogue done from a fake.
3. Finish #450: durable concept/generation operation, worker progress, shared USD 5 reservation/accounting and USD 0.50 per-attempt bound, idempotency, crash/ambiguous-response reconciliation, queued-only cancellation and recovery/retry. Inspect remaining cumulative spend before any paid call. Preserve original normalized room media, revisions, selected products and a useful saved concept when image generation fails. Use product references only with the required image rights and supported provider capability. Public paid generation stays disabled; beta is restricted/free under the approved controls.
4. Finish #451: actual `/app/interior` project list/create/open, room and own-item upload, brief/preferences, genuine product cards/board and selections, immutable revision history, before/after, progress/errors/retry and reload. Follow the V2 design system, Polish i18n, decimal formatting, session cleanup, mobile/keyboard/accessibility rules. Keep original, real product photo, illustration and fixture/demo states explicit.
5. Complete B-025 after a deploy from green merged staging: securely map the approved existing connection to MEDIA_* on VPS-3, run the complete media probe there, then exercise a real authenticated API upload and image retrieval. Never print keys/raw signed URLs or customer photos. Use disposable synthetic media/projects and clean up only those resources. Confirm private/tenant access, sanitized image headers and preserved source image. Local storage success does not replace host/API proof. Record commit, runtime and sanitized probe/upload evidence; resolve B-025 only when the applicable evidence exists.
6. Reconcile the reported `seller_questions` fixture drift with a fresh authorized capture and current contracts. Add only the necessary sanitized fixture changes and regression coverage in an appropriate issue-scoped change. Do not hide drift by deleting captures, suppressing the comparator or claiming success when it skipped. If the reported drift cannot be reproduced, record the actual command/result and reason instead of modifying fixtures blindly.

## Definition of done: successful frontend end-to-end tests

The owner explicitly defines done as successfully passing frontend E2E for the usable interior feature. `make fe-check`, API-only tests, smoke counts, a green aggregate check or rendering the old unavailable page are insufficient.

Use Node 24.22.0 (already installed; activate it) and current repository commands. Add dedicated Playwright interior tests and interaction-registry entries. Run both the frontend interaction suite and the real-stack browser journey lane after the final changes. The real-stack tests must use the real API, migrations/Postgres, worker and project/storage integration; replace external paid/catalogue services only with clearly named deterministic fakes. Route-intercepted browser JSON tests alone are insufficient. Keep live-provider probes separate from deterministic E2E evidence.

The successful browser journey must prove:

1. Sign in as an entitled tester; open `/app/interior`; create a project and upload a room image; preview it through authenticated delivery. The feature does not remain an unavailable placeholder for that tester.
2. Save/edit a brief and own item, including optional photo/unknown price; find/select exact product variants and see real-provider-shaped photos, observed prices/freshness and server subtotals. Unknown prices/delivery stay explicit.
3. Save a revision; start a generation operation; observe progress to a persisted concept/output; inspect original versus generated states and history. Refresh/reopen and verify no second model call or duplicate operation/charge.
4. Exercise actionable failures: rejected upload, unavailable storage with project preserved, stale/missing catalogue offers, provider failure/budget exhaustion, and a safe retry/reconciliation. Verify repeated clicks cannot duplicate submission.
5. Verify denied beta access, another user's project/media/operation 404, sign-out/account switch cleanup and no prior-tenant content leakage.
6. Use relevant desktop/mobile viewports and light/dark baselines, keyboard interactions and accessibility checks, with all actionable controls in `frontend/e2e/interactions.ts`. Meet #284's full frontend DoD, not only the happy path.

Execute the repository-required backend/invariant/migration/security checks as applicable, `make fe-check`, frontend Playwright E2E, the real-stack journey suite and required visual checks. Repair defects and rerun affected checks until green. Inspect final GitHub frontend/E2E/journey/visual results for the final head; SKIPPED is not success. Do not weaken tests, coverage, fixture checks, feature controls or workflows to get a pass. If CI filtering skips a necessary suite, run it explicitly using an authorized existing execution path and provide the exact final-head evidence; change workflow settings only through the required approval process.

Record exact commands, final commit SHA, browser/viewport coverage, counts, pass/fail/skipped results and trace/report paths or CI URLs. Attach failure traces while fixing; do not present a prior report as evidence for a newer head. Include one permitted bounded live catalogue/generation check when access and remaining budget allow; inspect the actual output/reference correspondence. If a required live source/provider remains externally blocked, say that capability is incomplete even if deterministic tests pass.

Do not stop at “CI running”, “PR opened”, “backend finished” or “UI wired”. Continue the authorized implementation, checks, review, fixes and staging merges until the working interior journey passes these browser gates, or a concrete owner-only blocker prevents the affected step. Document any such blocker precisely, continue independent work and never claim full completion while required capability or E2E acceptance is missing. No promotion to main or destructive changes.

Final report must include: completed issue/PR/commit list; the committed interior-doc paths/SHA; meaningful frontend E2E and real-stack journey results for the final code; serving-host R2 and authenticated-upload evidence; catalogue/model verification status; remaining shared provider budget; and any exact owner-only action. Keep STATUS/LIMITATIONS/BLOCKERS/CONTEXT and relevant specs/runbooks aligned with that evidence.
