# V3 — Adres

13 October 2026 · Interactive Phase 2 design exploration, not a shipped app.

[Home](main-view.html) · [Login](login.html) · [My analyses](analyses.html) · [Market](market.html) · [Report](analysis.html?id=p2)

Run from the repository root:

```sh
python3 -m http.server 8766 --bind 127.0.0.1 --directory design
```

Open http://127.0.0.1:8766/v3/main-view.html or http://127.0.0.1:8766/v3/login.html.

Light is the default even when the operating system is dark. The explicit theme choice persists across V3 pages. Use the theme control in the desktop sidebar/header or mobile header. Mobile Menu also provides a login-preview link.

## Direction

V2's precise geometry and task-oriented navigation, brought into daylight: mineral whites, forest green, architectural drafting, a doorway wordmark, and Polish modernist residential imagery. See [principles](design-principles.md) and [V2 review](v2-review.md).

Login borrows the split composition, fine frame and image/copy balance from the supplied ArtCraft reference. Brand, wording, imagery and implementation are RentMonitor's own. Validation, password visibility, registration mode, Google explanation and password-recovery dialog are interactive demonstrations. No credential or email is transmitted, logged or stored. Login does not authenticate; the explicitly labeled sample-dashboard link navigates without authentication.

The report extends V2's scaffold with a next-step panel, seller question, rent/cost/purchase/evidence sections and native detail disclosures. Ready, incomplete, running and unknown-ID states are distinct. No investment return is invented or calculated. Offer and transaction prices remain separate; administrative fees remain costs.

All files are isolated in `design/v3/`. V1, V2, `frontend/` and backend contracts are unchanged. No package dependency is added. Data and commercial allowances are fictional inherited design fixtures. Only the appearance preference is persisted.

## Verification

In the local browser on 13 October 2026:

- Inspected V2's live home, URL validation and credit-confirmation dialog before implementing V3; reviewed V2 source and stored desktop render.
- Checked all five V3 pages at 320, 768 and 1440 px; home and login also visually reviewed at 390 px. No horizontal overflow or visible controls outside the viewport was found. Home was rechecked at 1440 px after an asynchronous viewport update.
- Reviewed light and dark home/login visually, plus the market and incomplete report.
- Verified theme switching and persistence across navigation; Polish city search (`lodz` → one result); clarification filter → three results; report seller-question expansion; all five home review states; URL credit confirmation and URL preservation.
- Verified login empty-email error, show/hide password, registration mode, Google preview feedback and password-recovery feedback.
- All seven JS files pass `node --check`. `git diff --check` passes. No browser warnings or errors were observed.

Native dialogs and reduced-motion CSS are retained. Formal screen-reader, full contrast audit, reduced-motion emulation and user-task research have not been performed. Backend tests were not run for this isolated design artifact. Production needs real auth/API integration and approved commercial copy.

[Home desktop](main-view-desktop.jpg) · [Home mobile](main-view-mobile.jpg) · [Home dark](main-view-dark.jpg) · [Login light](login-desktop.jpg) · [Login dark](login-dark.jpg) · [Login mobile](login-mobile.jpg) · [Report](analysis-page.jpg)

## Renti identity

V3 now uses **Renti**, the name associated with renti.tech, across headers, page titles and branded captions. The revised single wordmark replaces the detached R and temporary doorway mark. [Brand notes and reusable SVG assets](renti-brand.md) describe the custom filled lettering, window detail and theme variants. Historical design notes above retain the project name used when the direction was created.
