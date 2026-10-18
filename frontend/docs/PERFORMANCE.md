# Frontend performance diagnostics (lab, 16 October 2026)

Evidence for `#286` item 3 ("LCP/INP/CLS lab numbers recorded as diagnostics"; the bundle budget is enforced
separately by `check-dist.mjs`, initial JS 167.9 of 200 kB gzip on `staging` at the time of writing).

**What these numbers are.** One developer machine (Apple silicon), Chromium 1280 px and Pixel 7 at 390 px with 4x CPU
throttling, the production build served by `vite preview`, the API answered from the fixture scenarios (no network, no
backend latency). Largest Contentful Paint and layout shifts come from `PerformanceObserver`; "slowest interaction" is
the longest `event` timing entry (a click) in the run, an INP proxy over one or two interactions, not the 75th percentile
of real visits. **They are diagnostics: they show whether something got badly slower, and say nothing about what a
visitor on a real network and device experiences.** No threshold is enforced on them.

Reproduce: `cd frontend && pnpm perf` (writes `test-results/perf/<project>.json`; set `PERF_OUT` to move it).

## Two runs on `staging` 80cde5f (values in ms; CLS unitless)

| Page         | Project       | LCP run A | LCP run B | CLS (A / B)   | Slowest interaction (A / B) |
| ------------ | ------------- | --------- | --------- | ------------- | --------------------------- |
| Pulpit       | desktop       | 84        | 68        | 0 / 0         | 40 / 40                     |
| Pulpit       | phone, 4x CPU | 228       | 224       | 0 / 0         | 48 / 32                     |
| Moje analizy | desktop       | 368       | 372       | 0 / 0.001     | 40 / 40                     |
| Moje analizy | phone, 4x CPU | 508       | 504       | 0.001 / 0.001 | 56 / 48                     |
| Nowa analiza | desktop       | 368       | 372       | 0 / 0         | 48 / 40                     |
| Nowa analiza | phone, 4x CPU | 500       | 492       | 0 / 0         | 56 / 56                     |
| Raport       | desktop       | 392       | 384       | 0.018 / 0.018 | 48 / 48                     |
| Raport       | phone, 4x CPU | 544       | 540       | 0 / 0         | 48 / 56                     |

Reading: every page paints its largest element under 0.6 s in this setup and the slowest click is under 60 ms. The one
non-zero shift is the report on desktop (0.018, under the 0.1 "good" line): a small movement while the report sections
render. It is recorded, not investigated further; a real-network run could differ in both directions.

## Run after the artifact fix, 2026-10-16 (Chromium 156.0.8078.4, Apple M4 Pro, Node 24.22.0, one worker)

The first two runs above were made before `pnpm perf` wrote one artifact per page and project and aggregated them with
validation (`perf-aggregate.mjs`, `test/perf-aggregate.test.ts`): workers used to overwrite one project file with their own
partial results. A run now fails unless all four pages are measured exactly once in both projects, and writes
`test-results/perf/summary.json` with the commit, whether the tree was dirty, Node, browser version and machine. Run on the
`rm-334-work` branch (staging `77e227e` plus the visual-lane changes; the dirty flag was true while the tree held them).
A run with `--workers=4` produced the same eight artifacts, none lost.

| Page         | Project       | LCP | CLS   | Slowest interaction |
| ------------ | ------------- | --- | ----- | ------------------- |
| Pulpit       | desktop       | 84  | 0     | 32                  |
| Moje analizy | desktop       | 372 | 0.001 | 48                  |
| Nowa analiza | desktop       | 368 | 0     | 40                  |
| Raport       | desktop       | 388 | 0.018 | 48                  |
| Pulpit       | phone, 4x CPU | 232 | 0     | 48                  |
| Moje analizy | phone, 4x CPU | 544 | 0.001 | 56                  |
| Nowa analiza | phone, 4x CPU | 512 | 0     | 48                  |
| Raport       | phone, 4x CPU | 620 | 0.037 | 40                  |

The report on the phone showed a layout shift of 0.037 in this run and 0 in the earlier two: single runs vary, still under
0.1. Lab proxies only; no threshold was set from them.

## Not covered (still open under #286)

Field data (real devices and networks), Firefox and WebKit timings, the journey against the VPS-3 deployment, and the
real iOS Safari and Android Chrome checks.
