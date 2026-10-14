// Local design interactions only. No uploads, AI calls, financial math or storage.
(() => {
  const recent = document.querySelector('#dashboard-recent');
  if (recent) recent.innerHTML = properties.map(p => `<a class="recent-row" href="analysis.html?id=${p.id}"><span class="recent-row-icon">${icon('files')}</span><span><strong>${p.name}</strong><small>${p.city} · ${p.date}</small></span><span class="status ${p.status}">${p.statusText}</span>${icon('arrow')}</a>`).join('');

  const tabs = [...document.querySelectorAll('.method-tab')];
  function selectTab(tab, focus = false) {
    tabs.forEach(item => {
      const selected = item === tab;
      item.setAttribute('aria-selected', String(selected));
      item.tabIndex = selected ? 0 : -1;
      document.getElementById(item.getAttribute('aria-controls')).hidden = !selected;
    });
    document.querySelector('#analysis-preflight').hidden = true;
    if (focus) tab.focus();
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectTab(tab));
    tab.addEventListener('keydown', event => {
      const targets = {ArrowRight:(index + 1) % tabs.length, ArrowLeft:(index + tabs.length - 1) % tabs.length, Home:0, End:tabs.length - 1};
      if (event.key in targets) {event.preventDefault(); selectTab(tabs[targets[event.key]], true);}
    });
  });

  const uploads = new Map();
  const allowed = new Set(['image/jpeg','image/png','image/webp']);
  document.querySelectorAll('[data-uploader]').forEach(container => {
    const input = container.querySelector('input');
    const status = container.querySelector('.upload-status');
    const grid = container.querySelector('.upload-previews');
    let entries = [];
    uploads.set(container, () => entries.length);
    function render() {
      grid.replaceChildren();
      entries.forEach(entry => {
        const figure = document.createElement('figure');
        const image = document.createElement('img');
        image.src = entry.url; image.alt = entry.file.name;
        const caption = document.createElement('figcaption');
        caption.textContent = entry.file.name;
        const remove = document.createElement('button');
        remove.type = 'button'; remove.className = 'remove-photo';
        remove.textContent = 'Usuń'; remove.setAttribute('aria-label', `Usuń zdjęcie: ${entry.file.name}`);
        remove.addEventListener('click', () => {
          URL.revokeObjectURL(entry.url); entries = entries.filter(item => item !== entry);
          render(); status.textContent = `Zdjęcia: ${entries.length} / 25.`; input.focus();
        });
        image.addEventListener('error', () => {
          URL.revokeObjectURL(entry.url); entries = entries.filter(item => item !== entry); figure.remove();
          status.textContent = `Nie można odczytać zdjęcia. Wybierz poprawny plik. Zdjęcia: ${entries.length} / 25.`;
          container.dispatchEvent(new Event('photoschange', {bubbles:true}));
        });
        figure.append(image, caption, remove); grid.append(figure);
      });
      container.dispatchEvent(new Event('photoschange', {bubbles:true}));
    }
    input.addEventListener('change', () => {
      const errors = [];
      for (const file of input.files) {
        if (!allowed.has(file.type)) {errors.push('Wybierz JPG, PNG lub WebP.'); continue;}
        if (file.size > 10 * 1024 * 1024) {errors.push('Maksymalny rozmiar zdjęcia to 10 MB.'); continue;}
        if (entries.length >= 25) {errors.push('Możesz dodać maksymalnie 25 zdjęć.'); break;}
        if (entries.some(e => e.file.name === file.name && e.file.size === file.size && e.file.lastModified === file.lastModified)) continue;
        entries.push({file, url:URL.createObjectURL(file)});
      }
      render(); input.value = '';
      status.textContent = [...new Set(errors), `Zdjęcia: ${entries.length} / 25.`].join(' ');
    });
    // Keep previews working when restored from the back/forward cache.
    window.addEventListener('pagehide', event => {if (!event.persisted) entries.forEach(e => URL.revokeObjectURL(e.url));});
  });

  function reveal(selector) {
    const result = document.querySelector(selector);
    result.hidden = false; result.focus();
    result.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
  }
  document.querySelector('#offer-url-form')?.addEventListener('submit', event => {
    event.preventDefault();
    const field = document.querySelector('#offer-url');
    const error = document.querySelector('#offer-url-error');
    let valid = false;
    try {const url = new URL(field.value.trim());valid = url.protocol === 'https:' && ['otodom.pl','www.otodom.pl'].includes(url.hostname) && /^\/pl\/oferta\/[^/]+\/?$/.test(url.pathname) && !url.username && !url.password && !url.port;} catch {}
    error.hidden = valid;
    field.setAttribute('aria-invalid', String(!valid));
    if (!valid) {error.textContent = 'Wklej pełny link https do oferty na otodom.pl/pl/oferta/…'; field.focus(); return;}
    document.querySelector('#preflight-summary').textContent = 'Link ma poprawny format. Nie pobraliśmy treści ogłoszenia.';
    reveal('#analysis-preflight');
  });
  document.querySelector('#offer-url')?.addEventListener('input', event => {event.target.removeAttribute('aria-invalid'); document.querySelector('#offer-url-error').hidden = true; document.querySelector('#analysis-preflight').hidden = true;});
  document.querySelector('#manual-form')?.addEventListener('input', () => {document.querySelector('#analysis-preflight').hidden = true; document.querySelector('#manual-error').hidden = true;});
  document.querySelector('#manual-form')?.addEventListener('photoschange', () => {document.querySelector('#analysis-preflight').hidden = true;});
  document.querySelector('#interior-form')?.addEventListener('photoschange', () => {document.querySelector('#interior-result').hidden = true;});
  document.querySelector('#interior-form')?.addEventListener('input', () => {document.querySelector('#interior-result').hidden = true;});
  document.querySelector('#manual-form')?.addEventListener('submit', event => {
    event.preventDefault();
    const data = new FormData(event.target);
    const error = document.querySelector('#manual-error');
    if (data.get('ownership') === 'fraction') {error.textContent = 'Udział w nieruchomości nie kwalifikuje się do analizy inwestycyjnej. Wybierz ofertę całego mieszkania.';error.hidden = false;return;}
    const container = event.target.querySelector('[data-uploader]');
    if (!uploads.get(container)()) {error.textContent = 'Dodaj przynajmniej jedno zdjęcie mieszkania.';error.hidden = false;return;}
    error.hidden = true;
    document.querySelector('#preflight-summary').textContent = `${data.get('name')} · ${data.get('city')} · ${data.get('area')} m² · pokoje: ${data.get('rooms')} · zdjęcia: ${uploads.get(container)()}. ${data.get('admin') === '' ? 'Opłata administracyjna pozostaje nieznana.' : 'Opłatę administracyjną oznaczono jako koszt.'}`;
    reveal('#analysis-preflight');
  });
  document.querySelector('#interior-form')?.addEventListener('submit', event => {
    event.preventDefault();
    const container = event.target.querySelector('[data-uploader]');
    if (!uploads.get(container)()) {container.querySelector('.upload-status').textContent = 'Dodaj przynajmniej jedno zdjęcie, aby przejść przez przykład.';container.querySelector('input').focus();return;}
    const room = event.target.elements.room.selectedOptions[0].textContent;
    const style = event.target.elements.style.selectedOptions[0].textContent;
    document.querySelector('#interior-summary').textContent = `${room} · ${style}. Poniżej przykładowa struktura planu; projekt i wizualizacje AI nie zostały wygenerowane.`;
    reveal('#interior-result');
  });
  const advice = {
    light:['Światło i jasność','Odsłoń okna, fotografuj przy równym świetle dziennym i unikaj mieszania barw lamp. Nie rozjaśniaj zdjęcia tak, aby ukryć stan mieszkania.'],
    furniture:['Meble i porządek','Usuń drobne przedmioty i zbędne dekoracje, uporządkuj przewody, ustaw krzesła równo. Zachowaj rzeczywisty układ i wyposażenie oferty.'],
    framing:['Kadr i perspektywa','Trzymaj aparat poziomo i pokaż połączenia między pomieszczeniami. Unikaj skrajnie szerokiego kąta, który zmienia odbiór proporcji.']
  };
  document.querySelector('#listing-form')?.addEventListener('submit', event => {
    event.preventDefault();
    const data = new FormData(event.target);
    const location = [data.get('city'),data.get('district')].filter(Boolean).join(' · ');
    const rental = data.get('type') === 'rent';
    document.querySelector('#listing-description').value = `Mieszkanie ${rental ? 'na wynajem' : 'na sprzedaż'} · ${data.get('area')} m² · ${location}\n\nOferuję mieszkanie w lokalizacji: ${location}.\nPowierzchnia: ${data.get('area')} m².\nLiczba pokoi: ${data.get('rooms')}.\nCena ofertowa: ${data.get('price')} zł${rental ? ' / miesiąc' : ''}.\n\n${data.get('features').trim() || '[Uzupełnij potwierdzone informacje o układzie, stanie i wyposażeniu.]'}\n\n[Uzupełnij pozostałe opłaty, dostępność i warunki oferty przed publikacją.]`;
    const grid = document.querySelector('#photo-advice');grid.replaceChildren();
    const selected = data.getAll('issues');
    (selected.length ? selected : Object.keys(advice)).forEach(key => {
      const article = document.createElement('article');const heading = document.createElement('h3');const body = document.createElement('p');
      heading.textContent = advice[key][0];body.textContent = advice[key][1];article.append(heading,body);grid.append(article);
    });
    document.querySelector('#copy-status').textContent = '';
    reveal('#listing-result');
  });
  document.querySelector('#photo-brightness')?.addEventListener('input', event => {
    document.querySelector('#brightness-value').textContent = `${event.target.value}%`;
    document.querySelector('#listing-images').closest('[data-uploader]').style.setProperty('--photo-brightness', `${event.target.value}%`);
  });
  document.querySelector('#copy-description')?.addEventListener('click', async () => {
    const description = document.querySelector('#listing-description');
    try {await navigator.clipboard.writeText(description.value);document.querySelector('#copy-status').textContent = 'Opis skopiowany.';}
    catch {description.focus();description.select();document.querySelector('#copy-status').textContent = 'Zaznaczono opis. Skopiuj go skrótem klawiaturowym.';}
  });
})();
