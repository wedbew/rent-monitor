# Rule: frontend correctness (`frontend/`)

Decision of record: the 15 October 2026 audit (`frontend/docs/AUDIT-2026-10-15.md`, findings F01–F18, tracker #314).
Each defect it found came from one of a few habits: a primitive claimed a guarantee nobody tested, a state change
had more than one entry point, network data was cast instead of checked, copy and numbers were written inline,
and a green backend CI was taken as evidence for the SPA. This rule removes those habits. It applies to every PR
that touches `frontend/`, and to backend PRs that change a contract the SPA consumes.

`agents.md` §0 still holds: the SPA never computes finance (invariant 4). This rule does not relax any backend rule.

## 1. Evidence before claims (F01, F13)

- **Frontend checks run before every push**: `make fe-check` (or `make ci`, which includes it), plus
  `pnpm test:e2e` when a page, popup, form or stream changes. Paste the summary lines in the PR. GitHub does not
  run them yet (#296, L-031): a green PR on GitHub says nothing about the SPA. Never write "CI green" for frontend
  work unless the frontend lane exists and ran.
- A stage that did not run is **SKIPPED** in the PR, with the reason. Browser runs use their own `E2E_PORT`,
  `--output` and `E2E_COVERAGE_DIR`; results from a shared or reused server are not evidence.
- Coverage numbers are reported **with their scope** (today `api/**` only). Never quote a percentage as covering
  components, hooks or pages it does not measure.
- Browser claims name the engines and widths that ran (today Chromium 1280 and Pixel 390). Firefox, WebKit and
  real devices are "not run" until a lane runs them (#286, #311).

## 2. A shared primitive's promise is a tested contract (F04, F16)

- A comment or prop doc that promises behaviour ("ignores clicks while busy", "never throws", "falls back to —")
  is a contract. The PR that writes it adds a test that would fail without it, in the primitive's own test file.
- Busy controls: a busy submit must not submit by click, by Enter in a field, or by a second activation. The
  mutation handler also guards `isPending`. Test it with the request held pending (`ui/Button.test.tsx` is the model).
- Formatters never throw on bad input and never append a unit or suffix to a fallback (`nie obliczono m²` is a bug).
  Precision and similar arguments are bounded and validated.

## 3. One door for each session transition (F02, F03, F10)

- Every path to "signed out" goes through `endSession` (`shell/session.tsx`): `/api/me` answering 401, a 401
  from any request, a signal from another tab, and sign-out. Every change of **signed-in user id** first purges
  the previous person's state the same way. Never set the session query to `null` or to another user directly.
- Purging means: cancel queries and mutations, clear tenant queries, close streams and run tenant cleanups,
  **before** the new identity renders. Tenant query keys carry the user id.
- A late result (query, mutation, reconciliation, stream frame) from an earlier session never navigates, writes
  the cache or invalidates. Guard it with a session generation or the user id.
- Every `queryFn` passes TanStack's `signal` to the request. Every mutation and long-lived resource has an
  explicit cancel path.
- Show sign-out as done only after the server confirms revocation. On failure, hide tenant data, say the session
  may still be active, offer a retry and do not silently restore it.
- Tests: account A's cache, expiry or switch, then sign in as B: no A query, stream or navigation survives.

## 4. Never assert what the server did not confirm (F05)

- After an ambiguous failure (timeout, dropped connection), the UI says **unknown**. It never reports success
  from a heuristic (recent row, same listing, timestamp window). Only a server answer tied to *this* request,
  such as an idempotency or correlation key, proves acceptance.
- Never resubmit automatically a request that reserves credit or sends mail.
- Balances, credit outcomes and statuses come from the server; after a change, invalidate and re-read.

## 5. The transport boundary owns the whole response (F08, F11)

- A request's deadline covers headers **and** body. A body read or decode failure becomes a typed
  `TransportError` (`timeout`, `aborted`, `network`, `invalid-response`), never a raw `AbortError` or `SyntaxError`.
  Timers and listeners are released in `finally`, on success too.
- Network data is **untrusted**. Check every field a component consumes before narrowing its type. Generated
  types describe the contract; they validate nothing. No `as SomeType` on a response, problem body or report
  without a guard that checks what is read. Malformed data renders a controlled fallback and never throws during
  render.
- Tests cover a stalled body, a mid-body disconnect, invalid JSON, a pre-aborted caller signal and malformed
  problem/report fields.

## 6. Streams and live state end (F09)

- Every live view has an authoritative fallback: polling while the job is active, a liveness deadline for a
  stream that is connected but silent, and a stop on terminal state, unmount and sign-out. "Reconnecting" may
  not last forever.
- Tests: a stream that never connects, a silent open stream, a missing terminal frame, and a 401 during the stream.

## 7. Copy and numbers come from one place (F06, F07, F16)

- **User-visible text belongs in the typed Polish catalog** once #305 lands: full sentences, accessible names,
  hints, document titles and fallbacks. Until it lands, new copy goes in the feature's single copy module (one
  file per feature, no literals spread across JSX) so extraction is mechanical. Routes, enum codes, ids,
  diagnostics and user or provider content are never translated.
- Never build a sentence from translated fragments. Plurals use `Intl.PluralRules` with the full Polish forms
  (one, few, many, other).
- **Every displayed number goes through `api/format.ts`**: counts, percentages, retry times, progress and error
  counts too. Never write `${n}` or `${n}%` in user-visible text. Dates use the shared `Intl.DateTimeFormat`
  helpers (Europe/Warsaw).
- Money and ratios stay exact decimal strings to the formatter. Never `Number()`, `parseFloat` or arithmetic
  on them. Formatting is display only; no finance in TypeScript.

## 8. Forms announce errors the same way (F12)

- Client and server validation errors share one summary and announcement contract. Focus moves to the summary
  when the **result** becomes invalid, not when submit starts. Typing never steals focus.
- Every form has keyboard tests for blank input, a server 422, a repeated error and a general failure.

## 9. Release-path honesty (F14, F15, F17, F18)

- Do not claim the SPA is deployable until Caddy serves it with the real CSP, caching and deep-link fallback
  (#281). Never relax CSP to make a test pass.
- Unexpected client errors are reported only through the planned, redacted sink (#280). Never log emails, tokens,
  URL fragments or listing text.
- Routes are lazily loaded when measurement justifies it; the bundle budget is a check, not a README number (#312).
- A placeholder or dead end that a user can reach is listed in `docs/STATUS.md` and the issue, not hidden.

## 10. Audits and reviews are durable

- An audit or review is committed under `frontend/docs/` (or `docs/`), against a **named commit**, never left
  in a stash or a working tree. Each finding gets an issue, and the audit file records the mapping.
- A finding is closed only with source evidence **and** a named regression test, re-verified on the `staging`
  commit that contains the fix (see the audit's re-verification section).
- Before starting frontend work, read the open findings in the audit file. A PR that touches an area with an open
  finding must not make it worse and says in its body which findings it touches.

## PR checklist (frontend line in the template)

Tick the `Frontend` line only when all of these hold. Otherwise list the exceptions:
`make fe-check` (+ `pnpm test:e2e` when UI changed) summary pasted · primitive promises tested · session
transitions through `endSession` · queries pass `signal` · no unchecked cast of network data · numbers through
`api/format.ts` · copy in the catalog or copy module · audit findings touched named.

## Do not

- Disable, skip or loosen a lint rule, a test, the interaction gate or axe to get a frontend change through.
- Quote a local frontend run as GitHub evidence, or a mocked run as provider evidence.
- Add a dependency (validator, i18n framework) without the reason and its measured bundle cost in the PR body.
