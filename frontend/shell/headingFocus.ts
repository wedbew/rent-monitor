/**
 * After a client navigation focus goes to the new page's `h1` (the browser does not do it for a single-page app).
 * The page may not have rendered its heading yet (its code loads lazily, #312), so the request waits here until a
 * `PageHeading` mounts and takes it. A request older than this is dropped: a heading that appears much later (a
 * slow load the person has moved on from) must not steal focus.
 */
const WAIT_MS = 10_000;
let requestedAt: number | null = null;

/** Focus the page heading now if there is one, otherwise as soon as one mounts. */
export function requestHeadingFocus(): void {
  const heading = document.querySelector<HTMLElement>("main h1");
  if (heading !== null) {
    requestedAt = null;
    heading.focus();
    return;
  }
  requestedAt = Date.now();
}

/** Called by a heading as it mounts: takes a pending request, if any. */
export function takeHeadingFocus(heading: HTMLElement | null): void {
  if (heading === null || requestedAt === null) return;
  if (Date.now() - requestedAt <= WAIT_MS && heading.closest("main") !== null) heading.focus();
  requestedAt = null;
}
