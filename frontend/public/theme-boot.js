// Applies the saved appearance before the first paint. It is an external file (not an inline script) so the CSP
// stays free of `unsafe-inline`. Light is the first-visit default, even when the system prefers dark; only the two
// known values are accepted; storage can be blocked (private mode, site data off) and must not break rendering.
(function () {
  var theme;
  try {
    theme = localStorage.getItem("renti-theme");
  } catch {
    theme = null;
  }
  document.documentElement.dataset.theme = theme === "dark" ? "dark" : "light";
})();
