// Apply the saved appearance before styles paint. Light is the first-visit default.
// Storage can be unavailable in private browsing or when opening local files.
(() => {
  const root = document.documentElement;
  const storageKey = 'renti-v2-theme';
  let saved;
  try { saved = localStorage.getItem(storageKey); } catch {}
  root.dataset.theme = saved === 'dark' ? 'dark' : 'light';

  document.addEventListener('DOMContentLoaded', () => {
    const buttons = document.querySelectorAll('.theme-toggle');
    function sync() {
      const dark = root.dataset.theme === 'dark';
      buttons.forEach(button => {
        // A fixed accessible name makes aria-pressed describe the dark-mode state.
        button.setAttribute('aria-pressed', String(dark));
        button.querySelector('span').textContent = dark ? 'Tryb jasny' : 'Tryb ciemny';
        button.querySelector('use')?.setAttribute('href', dark ? '#i-sun' : '#i-moon');
      });
    }
    buttons.forEach(button => button.addEventListener('click', () => {
      root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(storageKey, root.dataset.theme); } catch {}
      sync();
    }));
    sync();
    window.addEventListener('storage', event => {
      if (event.key === storageKey || event.key === null) {
        root.dataset.theme = event.newValue === 'dark' ? 'dark' : 'light';
        sync();
      }
    });
  });
})();
