# QA environment: journeys, pictures, evidence

One place for how QA (a person or the QA agent) runs the real stack, drives it, and keeps evidence. Lanes and their
reasons: `docs/FRONTEND-PLAN.md` section 4. Every provider in this stack is a named fake; nothing here says anything
about Otodom, OpenRouter, Paddle or a real report (evidence class: fake provider data).

## 1. Start, run, stop

| Step                     | Command (repo root) | Result                                                                                                         |
| ------------------------ | ------------------- | -------------------------------------------------------------------------------------------------------------- |
| Stack up                 | `make qa-up`        | API, workers, Postgres, `s3mock` from `deploy/compose.e2e.yml`; the SPA is served by `vite preview` on `:4173` |
| Journeys                 | `make qa-journey`   | `frontend/e2e/journey/**` on the real stack                                                                    |
| Pixel baselines          | `make qa-visual`    | the pinned-image visual lane CI runs                                                                           |
| What was left to look at | `make qa-evidence`  | every picture, video and trace of the last run                                                                 |
| Stack down               | `make qa-down`      |                                                                                                                |

Node must match `frontend/.node-version` (corepack `pnpm`). The mocked lane (`pnpm test:e2e`) and `pnpm ux` need no stack.

## 2. Writing a journey

Import `test` and `expect` from `./fixtures` (never from `@playwright/test`) in `e2e/journey/`:

- **Guard (automatic):** the test fails on an uncaught page error or a console error. A failed `/api` request the
  journey provokes on purpose (a wrong password) is allowed; any other error you provoke is declared with
  `allowErrors(/pattern/)`, and the pattern must match, so an allowance cannot outlive its purpose.
- **`shot("name")`:** a numbered full-page picture (`01-name.png`) in the test's output directory, attached to the report.
  Take one at each state a reader needs to see: the form, the waiting state, the result, the failure.
- **`a11y(include?)`:** axe (WCAG 2.2 AA tags) on the current state. Call it on each new screen, not once per test.
- **Seeding:** `scripts/e2e_session.py` inside the api container (`create`, `plant-listing`, `plant-market`, ...);
  clean up in `afterAll`. Never log in through a shortcut that the product does not have.

## 3. Evidence rules

- A picture is evidence only after someone has looked at it. Open the `shot()` files (or `pnpm ux` output in
  `ux-out/`) and say what you saw: layout, copy, numbers with unit and period.
- A failed journey keeps a trace (`pnpm exec playwright show-trace <trace.zip>`), a video and a screenshot.
- CI uploads `frontend/test-results` as `frontend-journey-evidence` for every journey run, pass or fail (7 days).
- Report a result as "journey X passed against the fake-provider stack, evidence <path>", never as live-provider proof.

## 4. Driving the stack interactively (QA agent)

`.mcp.json` registers the Playwright MCP (`@playwright/mcp`, pinned, headless, isolated profile, output in
`frontend/test-results/mcp`). It may open only `http://localhost:4173` and `http://localhost:8000`. Use it to explore a
state, read the console and take pictures before writing the journey that keeps it; do not point it at a deployed host
or use real credentials. Reload the MCP servers after pulling this file.

## 5. Still open

No Lighthouse lane on the real stack, no HAR capture and no mail catcher (the sign-up journey reads its token with
`register-token`, not from a mailbox). Register each in `docs/LIMITATIONS.md` if QA depends on it.
