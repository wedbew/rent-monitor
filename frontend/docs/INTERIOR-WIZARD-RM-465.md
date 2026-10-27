# Interior workspace — RM-465

Requested by the owner on 2026-10-26. Source review against `staging` commit `0046147`;
implementation and browser evidence are local working-tree evidence until merged.

Delivery tracking: #466 consolidates this implementation and the owner's mobile/stepper/custom-style
refinements into one PR targeting `staging`; #465 remains the original implementation issue.

The portrait journeys are registered inside `interior.spec.ts`'s serial suite. Its deliberate storage-outage
case stops the shared S3 test store, so it must finish before the mobile uploads start. Keeping the
registration in `interior-mobile.ts` (not a separately discovered spec) prevents cross-file interference;
all upload and outage assertions remain in place.
The corrected suite passed all nine interior journeys locally on 2026-10-27 against a disposable
API/Postgres/S3-test-store stack with fake model/catalogue providers, including the outage case followed
by all six generated-portrait uploads (1.9 minutes). The disposable stack was removed after validation.

## Design and flow

The reference is `design/v2/interior.html` and its design principles: quiet forest/neutral surfaces,
clear hierarchy, visible boundaries, 44 px controls, no decorative motion. The previous project page
stacked every backend operation into a single long column. The replacement uses four focused steps:
room photo, direction, optional furniture, and versions/visualizations. A compact project summary stays
beside the active step on desktop; navigation becomes a compact strip on mobile.

All tools remain available through the full-view toggle. Both view and current step are URL parameters,
so reload and shared project links retain that layout without storing tenant data in local storage.
Panels remain mounted while hidden to preserve drafts. Moving between steps does not submit anything.
Saving preferences is explicit; a dirty brief disables forward progression from that step and saving a
revision in every view. Existing immutable versions can still be rendered with their original brief.

## Backend capability review

| Capability           | Confirmed contract / behavior                                                                                                        | UI treatment                                                                      |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| Projects             | `ProjectCreate`: name and one of seven room types; tenant-scoped repositories                                                        | Existing create/list/delete flow retained                                         |
| Room photo           | JPEG/PNG/WebP; 10 MB; minimum 200 px each side; normalized copy, original retained on device; at most five uploads                   | Bounded preview, upload errors and replacement explanation retained               |
| Direction            | `Brief`: editable style (80 chars), exact decimal budget, up to ten keep entries, notes (2,000 chars)                                | Style selector with ten suggestions and a custom name; optional unspecified style |
| Own furniture        | Name required; quantity, price, URL, photo optional                                                                                  | Optional furniture step, same create/edit/delete/photo controls                   |
| Catalogue            | Provider-backed search, category and maximum price; demo source explicitly labeled; exact variant selection                          | Optional furniture step, no invented merchant connection                          |
| Product board        | Quantity, offer refresh/removal, server-calculated basket with unknown/stale lines separate                                          | Existing board and totals retained                                                |
| Revisions            | Immutable photo digest, brief, furniture, refreshed offers and server basket                                                         | Explicit snapshot before generation; blocked while the brief is dirty             |
| Generation           | POST requires a saved revision; per-click idempotency UUID; one active operation; polling, cancellation while queued, explicit retry | Existing generation hooks and payment protections retained                        |
| Access and retention | Closed beta; foreign resources return 404; project expiry not extended by editing                                                    | Existing beta, not-found and expiry behavior retained                             |

Source: `packages/rm_contracts/interior.py`, `packages/rm_contracts/generation.py`,
`services/rm_api/interior.py`, `packages/rm_core/interior_prompt.py`, and the existing frontend hooks.

The model prompt preserves camera position, walls, windows, doors, floor, ceiling and proportions.
It changes furnishing/decor. Style, keep entries and notes reach the prompt; the budget is only a
comparison limit for the product basket. A wizard setting cannot turn that budget into a model spending
constraint or authorize architectural changes. Those would require a separate backend contract.

## Configuration

`frontend/features/interior/configuration.ts` owns the default step, default view, step order and enabled
style suggestions. `frontend/i18n/interior.ts` owns all labels, hints and preset values. The style selector
offers these suggestions, an unspecified choice and “Własny styl”, which reveals a custom name field.
The custom name is required only for that choice (80-character server limit); unknown saved names reopen
as custom without losing their value. Switching choices preserves the unsaved custom draft. The active
style is persisted as the existing plain `Brief.style` value only when the person saves preferences.
Custom styles belong to this project's brief; no account-wide style library is introduced. Server provider,
model, attempt budget, estimate and deadline remain settings in `rm_core.settings`; they are not exposed
as client-side billing controls. No dependency, API, migration, legal tag or processor was added.

## Validation

`frontend/e2e/interior.spec.ts` retains all earlier operation checks in full view and adds the keyboard
wizard journey: step focus, style selection, custom style, dirty-brief gating, retained drafts, saved
payload, full-view toggle and reload without a generation request. The interaction registry inventories
the guided photo, brief and furniture states in addition to the existing full-view states, with axe.
Visual tests cover the photo and direction steps in both themes at desktop and mobile widths.

Final local evidence on 2026-10-26:

| Check                                                                    | Result                                                                                                                                      |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `make fe-check`                                                          | Passed: API generation check, types, lint, CSS lint, formatting, 67 unit-test files / 1,069 tests, build, bundle limits, fixture comparison |
| Full `pnpm test:e2e`, isolated port 4381 and output/coverage directories | 740 passed, 54 skipped; 309/309 registered interactions and popups asserted                                                                 |
| Pinned Linux visual lane, `--grep interior`                              | 20 passed when updating, then 20 passed comparing the final baselines; light/dark, 1280 px desktop and 390 px mobile                        |
| `git diff --check`                                                       | Passed                                                                                                                                      |

Earlier runs that overlapped builds were discarded: the lanes share `frontend/dist`, so another build
can delete a chunk while a browser is using it. Run build-producing lanes sequentially unless their build
directories are also isolated; separate ports and result directories alone are insufficient. The final full browser run above had no overlapping
build. A stale Vitest module cache was cleared with `vitest --clearCache` before the successful checks.

Mocked browser tests verify UI/API behavior against named scenarios, not a live image model or merchant. Real-stack journey execution
and Firefox/WebKit verification must be stated separately; updating the journey's full-view setup does
not constitute executing it. Existing release/provider limitations remain in `docs/LIMITATIONS.md`.

Context: §10 adds this guide; no architecture or phase change. Legal / GDPR: no production tags changed; existing
image-processing, personal-data and retention paths remain in use.

## Mobile portrait follow-up, 2026-10-26

The owner supplied an OLX/Otodom image for a real upload check. The downloaded file is a 900 × 1200
portrait JPEG. It remains a local review input; neither the photograph nor real-photo screenshots are
added to the repository's fixtures or visual baselines.

`frontend/e2e/journey/interior-mobile.ts`, registered by `interior.spec.ts`, creates and erases a throwaway beta account, uploads
through the file chooser, requires HTTP 201, checks authenticated image delivery against the returned
SHA-256 digest and confirms the photo survives reload. It saves the brief and a revision and captures
every wizard step in light/dark at 320, 390 and 768 px. Each capture checks axe and page overflow.
The optional `INTERIOR_ROOM_PHOTO` selects a local 900 × 1200 photo; otherwise the browser creates a
portrait PNG so CI requires no network access or third-party media. No image generation is requested.

The review exposed overlapping step labels at 320 px. The added touch-target bounds assertion failed
before the fix. Compact Polish labels now fit phone/tablet navigation; desktop keeps the fuller labels.
The repeated rail eyebrow is hidden at these widths to leave more room for the active step.

For the owner's photo, the local stack is an isolated Compose project with Postgres 17, the real API
and upload normalization, production boto3 storage against `adobe/s3mock:4.7.0`, and the ops worker.
It uses local test settings without loading `.env`. The catalogue is demo data; the image provider is
configured offline and is never called. This verifies a real upload/store/read path, not a live R2 bucket,
merchant, image model or physical mobile device. The test-only source is tagged `LEGAL[images]` and
`GDPR[erasure]`; no production processing or retention behavior changes.

Local results: six real-upload journeys passed with the owner's photograph (both themes at all three
widths), yielding 24 full-page screenshots. All 24 captures passed axe, page-overflow and step-label
bounds assertions. `make fe-check` passed after the fix (67 files, 1,069 tests and all static/build gates).
The source photo and rendered review images stay outside Git, under the chat's local artifact directory.
The generated-image fallback also passed the 320 px real-stack test without `INTERIOR_ROOM_PHOTO`.
After the mobile fix, the full mocked browser suite passed again: 740 passed, 54 skipped, 309/309
registered interactions asserted. The pinned visual lane passed 20 update checks and then 20 baseline
comparisons. The disposable upload stack was removed after verification.

## Mobile toolbar correction

Owner review identified an oversized text label in the mobile theme control. At widths up to 760 px,
`ThemeControl` now renders only the sun/moon icon in a 44 × 44 px target, retaining its localized
accessible name and native tooltip. Public headers release the old fixed-width text slot as well.
The desktop rail retains its text label.

`e2e/shell.spec.ts` adds the regression `mobile theme control uses only its icon without crowding the
header`: app/public headers at 320, 390 and 640 px must have an icon-only button, a 44 px target,
working keyboard activation and no overlapping header controls. It failed on the previous control.
Canonical `.agent/rules/frontend.md` §11 now requires visible crowding/clipping to be fixed automatically
within the authorized UI work, followed by a specific regression assertion and rendered review.

## Full-width mobile wizard

Owner correction: nested horizontal padding was reducing the useful form width. At up to 760 px the
wizard now cancels the shell's horizontal inset, spans the viewport, and keeps one 8 px content gutter
(or the device's larger safe-area inset). Single-column wizard sections and cards have no horizontal
padding, decorative frames or desktop form-width caps. The desktop layout is unchanged.

The shell exposes its existing horizontal gutter as `--content-inline-padding`, letting the wizard
cancel the exact inherited value without guessing a viewport width. `.agent/rules/frontend.md` §12
records the full-width requirement, single-gutter policy, safe-area handling and automatic correction.
`e2e/interior.spec.ts` checks actual wizard edges and primary field insets at 320, 390, 640 and 760 px,
in guided and full-tools views. This regression failed before the padding fix.

Post-correction evidence: `make fe-check` passed (1,069 tests); the updated theme-name/tooltip unit test
passed; the four toolbar/gutter browser regressions passed. All six real-upload journeys passed again
with the owner's photo, producing refreshed light/dark captures at 320/390/768 px. The full mocked
browser suite passed: 744 passed, 54 skipped, 309/309 registered interactions asserted. The upload
stack was removed after use. Rendered review artifacts show the icon-only header and flat full-width form.
All 56 mobile visual comparisons passed in the pinned Linux image, using a private Docker `dist`
volume independent of the native browser build. One earlier visual update timed out waiting for the
market free-account label; its isolated update and the complete 56-test comparison passed with fewer
workers. No timeout, assertion or accessibility requirement was weakened.

## Matching toolbar and connected stepper

The mobile navigation trigger now uses the shared `IconButton` with a hamburger icon, accessible name,
tooltip and expanded state. It shares the theme control's 44 × 44 px size, border radius and alignment.
The stepper replaces mixed icons, repeated visible “Krok” captions and large active cards with numbered
circles and connecting lines. Mobile is a compact horizontal track; desktop is a vertical sequence with
descriptions. The active number is filled and its label emphasized; no uncompleted step is marked done.
The full-tools control stays available as a subdued secondary action. Full-width mobile gutters remain.

The toolbar regression now checks both icon buttons' dimensions and top edge. A new numbered-stepper
regression checks four visible numbers, horizontal/vertical alignment, the current-step announcement,
and a mobile navigation area no taller than 160 px. Both regressions failed against the previous UI.
Review captures cover light/dark at 320/390/1280 px; keyboard navigation and existing project actions
continue through the same handlers. Canonical frontend rule §11 also requires matching adjacent
mobile toolbar controls.

Validation for this refinement: `make fe-check` passed (1,069 tests); the six targeted toolbar,
stepper-alignment and full-width regressions passed. The full mocked browser suite passed 746 tests,
with 54 existing skips and 309/309 registered interactions asserted. New local review captures show
both themes at 320/390/1280 px. No backend, provider, money calculation or generation behavior changed.
Pinned-image visual verification also passed: all 56 mobile comparisons and 10 desktop-interior
comparisons after refreshing the affected baselines. The visual build used its own Docker `dist` volume.

## Owner refinement: custom style selection

The four palette cards and always-visible free-text style field have been replaced by a labeled selector.
It offers ten configurable suggestions, “Bez określonego stylu” and “Własny styl”. Custom appears near
the top of the list so it is immediately discoverable. Selecting it reveals “Nazwa własnego stylu”;
the user can describe further details in the existing notes field. All text remains in the Polish catalog.

Saving validates a nonblank custom name and sends the trimmed text through the existing `Brief.style`
contract. A suggestion sends its configured value, and choosing no style clears the saved value.
Switching to a suggestion hides the custom field but retains its draft until reload. Previously saved
names outside the suggestion list reopen as custom. Unsaved-style changes retain the wizard's existing
forward/revision protection. No global custom-style library, API or schema change is needed for this flow.

Regression cases in `e2e/interior.spec.ts` cover keyboard selection, custom validation, draft switching,
reload, clearing, every suggestion's saved value and an existing arbitrary custom name. The interaction
inventory includes the custom form state; visual baselines include the open list and custom form in
both themes at 390/1280 px. These are local Chromium checks with the mocked API, not a live generation run.

Final custom-style validation (completed 2026-10-26; recorded 2026-10-27): `make fe-check` passed
(67 files / 1,069 tests), the full mocked browser suite passed 752 cases with 54 existing skips and
306/306 interaction coverage. The custom-form inventory waits for the select menu to finish closing;
six concurrent repeated checks passed after that synchronization fix. Pinned interior visual comparisons
passed all 20 cases; after placing the custom choice near the top, the four affected project cases were
refreshed and compared again successfully. The open selector and custom form were visually inspected
in both themes at 390/1280 px. Review copies are saved in the chat's `interior-styles` artifact directory.
