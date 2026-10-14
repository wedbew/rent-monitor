// renti.tech V3 — Canonical Fixtures & UI Controller
const $ = (selector) => document.querySelector(selector);
const icon = (name, extra = '') => `<svg class="icon ${extra}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
document.querySelectorAll('svg.icon').forEach((el) => el.setAttribute('aria-hidden', 'true'));

const properties = [
  {
    id: 'p1', code: 'ID4CpHB', city: 'Poznań · Jeżyce', name: 'Mieszkanie przy parku Sołackim',
    meta: '42 m² · 2 pokoje · 2/4 piętro', price: '425 000 zł', pricePerM2: '10 119 zł/m²',
    rent: '2 400–2 700', grossYield: '7,20%', netYield: '5,68%',
    status: 'ready', statusText: 'Analiza gotowa',
    caveat: 'Szacunek najmu z 24 ofert lokalnych. Czynsz adm. potwierdzony: 520 zł/mies.',
    date: 'Dzisiaj, 10:42',
    admin: '520 zł / mies.', capex: '18 500 zł (odświeżenie)',
    maxBid: '412 000 zł', spreadAskVsMax: '-3,1% poniżej ceny ofertowej',
    gusTransM2: '9 640 zł/m² (Q2 2026)', askingMedianM2: '10 450 zł/m² (Wrzesień 2026)',
    ocrRooms: 'Salon z aneksem (21,4 m²), Sypialnia (11,8 m²), Łazienka (4,6 m²), Hol (4,2 m²) · układ rozkładowy',
    note: 'Oferta bliska progu Max Bid (412 000 zł przy zakładanym 7,0% YOC). Przed decyzją zweryfikuj stan instalacji elektrycznej w budynku.'
  },
  {
    id: 'p2', code: 'ID9XkL2', city: 'Wrocław · Krzyki', name: 'Dwa pokoje z balkonem (ul. Powstańców)',
    meta: '48 m² · 2 pokoje · 3/5 piętro', price: '590 000 zł', pricePerM2: '12 292 zł/m²',
    rent: 'Brak danych', grossYield: 'Wstrzymano', netYield: 'Brak czynszu adm.',
    status: 'attention', statusText: 'Do wyjaśnienia',
    caveat: 'Brakuje opłaty administracyjnej w treści oferty. Nie przyjmujemy 0 zł.',
    date: 'Wczoraj',
    admin: 'Brak danych (krytyczne)', capex: '24 000 zł (szacunek AI Vision)',
    maxBid: 'Wstrzymano do uzupełnienia kosztów', spreadAskVsMax: 'Wymaga weryfikacji',
    gusTransM2: '11 420 zł/m² (Q2 2026)', askingMedianM2: '12 650 zł/m² (Wrzesień 2026)',
    ocrRooms: '2 pokoje + osobna kuchnia · wykryto rzut z podpisem dewelopera',
    note: 'Zapytaj sprzedającego o pełną zaliczkę do wspólnoty (z ogrzewaniem). Bez niej nie wyliczamy przepływów netto ani Max Bid.'
  },
  {
    id: 'p3', code: 'ID7MmQ9', city: 'Warszawa · Mokotów', name: 'Jasne mieszkanie na Służewie',
    meta: '35 m² · 2 pokoje · 1/10 piętro', price: '620 000 zł', pricePerM2: '17 714 zł/m²',
    rent: 'W trakcie', grossYield: 'Liczenie…', netYield: 'W trakcie',
    status: 'running', statusText: 'W trakcie',
    caveat: 'Pobieramy komparatory najmu dla Służewa i analizujemy 14 zdjęć (AI Vision).',
    date: 'Przed chwilą',
    admin: 'W trakcie odczytu', capex: 'Trwa klasyfikacja standardu',
    maxBid: 'W trakcie obliczeń DCF', spreadAskVsMax: 'W trakcie',
    gusTransM2: '15 890 zł/m² (Q2 2026)', askingMedianM2: '17 950 zł/m² (Wrzesień 2026)',
    ocrRooms: 'Trwa wektoryzacja rzutu (Layout OCR)…',
    note: 'Analiza trwa. Możesz zamknąć ten widok — wynik zapisze się automatycznie w Twojej przestrzeni.'
  }
];

const archive = [
  { id: 'p4', code: 'ID2GdW1', city: 'Gdańsk · Wrzeszcz', name: 'Mieszkanie przy al. Grunwaldzkiej', meta: '44 m² · 2 pokoje', price: '510 000 zł', pricePerM2: '11 590 zł/m²', rent: '2 600–2 900', grossYield: '6,47%', status: 'ready', date: '9 października' },
  { id: 'p5', code: 'ID5PzL8', city: 'Poznań · Łazarz', name: 'Dwa pokoje w zrewitalizowanej kamienicy', meta: '46 m² · 2 pokoje', price: '410 000 zł', pricePerM2: '8 913 zł/m²', rent: '2 200–2 500', grossYield: '6,88%', status: 'ready', date: '8 października' },
  { id: 'p6', code: 'ID8LdS3', city: 'Łódź · Śródmieście', name: 'Mieszkanie z osobną kuchnią przy Piotrkowskiej', meta: '40 m² · 2 pokoje', price: '315 000 zł', pricePerM2: '7 875 zł/m²', rent: '1 900–2 200', grossYield: '7,81%', status: 'ready', date: '7 października' },
  { id: 'p7', code: 'ID3WrO4', city: 'Wrocław · Ołbin', name: 'Mieszkanie blisko Placu Grunwaldzkiego', meta: '39 m² · 2 pokoje', price: '455 000 zł', pricePerM2: '11 667 zł/m²', rent: 'Brak danych', grossYield: 'Wstrzymano', status: 'attention', date: '6 października' },
  { id: 'p8', code: 'ID6KtL5', city: 'Katowice · Ligota', name: 'Dwa pokoje przy Parku Zadole', meta: '50 m² · 2 pokoje', price: '375 000 zł', pricePerM2: '7 500 zł/m²', rent: '2 000–2 300', grossYield: '6,88%', status: 'ready', date: '5 października' },
  { id: 'p9', code: 'ID1KrP9', city: 'Kraków · Podgórze', name: 'Mieszkanie z loggią blisko Wisły', meta: '43 m² · 2 pokoje', price: '560 000 zł', pricePerM2: '13 023 zł/m²', rent: '2 500–2 800', grossYield: '5,68%', status: 'ready', date: '4 października' },
  { id: 'p10', code: 'ID4SzC2', city: 'Szczecin · Centrum', name: 'Kawalerka na drugim piętrze', meta: '29 m² · 1 pokój', price: '295 000 zł', pricePerM2: '10 172 zł/m²', rent: 'Brak danych', grossYield: 'Wstrzymano', status: 'attention', date: '3 października' },
  { id: 'p11', code: 'ID9ByB7', city: 'Bydgoszcz · Bielawy', name: 'Mieszkanie przy UKW', meta: '38 m² · 2 pokoje', price: '310 000 zł', pricePerM2: '8 158 zł/m²', rent: '1 800–2 100', grossYield: '7,55%', status: 'ready', date: '2 października' },
  { id: 'p12', code: 'ID2TrM6', city: 'Toruń · Mokre', name: 'Dwa pokoje na spokojnej ulicy', meta: '45 m² · 2 pokoje', price: '350 000 zł', pricePerM2: '7 778 zł/m²', rent: '1 900–2 200', grossYield: '7,03%', status: 'ready', date: '1 października' },
].map((p) => ({ ...properties[p.status === 'ready' ? 0 : 1], ...p }));

const allProperties = [...properties, ...archive];
const statusIcon = { ready: 'check', attention: 'alert', running: 'clock' };
let previewState = 'returning';
let currentFilter = null;
let overlayTrigger = null;

function card(p) {
  const hasRent = p.status === 'ready';
  return `
    <article class="property-card">
      <div class="property-top">
        <span class="property-id-tag">${p.code || 'OTODOM'} · ${p.pricePerM2 || ''}</span>
        <span class="status ${p.status}">${icon(statusIcon[p.status])}${p.statusText}</span>
      </div>
      <div class="property-body">
        <p class="property-location">${p.city}</p>
        <h3>${p.name}</h3>
        <p class="property-meta">${p.meta}</p>
        <dl class="property-numbers">
          <div>
            <dt>Cena ofertowa</dt>
            <dd>${p.price}</dd>
          </div>
          <div>
            <dt>Najem właściciela / mies.</dt>
            <dd>${p.rent}${hasRent ? '<small>zł</small>' : ''}</dd>
          </div>
        </dl>
        <div class="property-yield-row">
          <span>Szacowany Gross Yield:</span>
          <strong>${p.grossYield || '—'}</strong>
        </div>
        <p class="property-caveat ${p.status === 'attention' ? 'warning' : ''}">${p.caveat}</p>
      </div>
      <div class="property-bottom">
        <span>${p.date}</span>
        <a class="card-cta" href="analysis.html?id=${p.id}" aria-label="${p.status === 'running' ? 'Sprawdź postęp' : 'Zobacz analizę'}: ${p.name}">
          ${p.status === 'running' ? 'Sprawdź postęp' : 'Otwórz raport'}
          ${icon('arrow', 'small')}
        </a>
      </div>
    </article>`;
}

function announce(text) {
  const el = $('#announcement');
  if (el) el.textContent = text;
}

function openOverlay(dialog, trigger) {
  if (!dialog) return;
  document.querySelectorAll('dialog[open]').forEach((d) => d.close());
  overlayTrigger = trigger || document.activeElement;
  dialog.showModal();
}

document.querySelectorAll('dialog').forEach((dialog) => {
  dialog.addEventListener('close', () => {
    if (dialog.id === 'navigation-dialog') return;
    if (!document.querySelector('dialog[open]') && overlayTrigger?.isConnected) overlayTrigger.focus();
  });
  dialog.addEventListener('click', (e) => {
    if (e.target.closest('[data-close]')) dialog.close();
    if (e.target === dialog) {
      const r = dialog.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close();
    }
  });
});

function renderHome() {
  if (!$('#property-grid')) return;
  const firstUse = previewState === 'empty';
  const loading = previewState === 'loading';
  const missingCredits = previewState === 'no-credits';
  $('#activity').hidden = firstUse || loading;
  $('#service-notice').hidden = previewState !== 'unavailable';
  $('#empty-state').hidden = !firstUse;
  $('#property-grid').hidden = firstUse;
  $('#all-button').hidden = firstUse || loading;
  $('#filter-bar').hidden = !currentFilter || firstUse || loading;
  $('#credit-label').textContent = missingCredits ? '0 analiz w limicie' : '2 analizy w limicie';
  $('#url-help > span').textContent = missingCredits
    ? 'Brak analiz w limicie · sprawdź dostęp przed rozpoczęciem'
    : '1 analiza z Twojego limitu · koszt potwierdzisz przed startem';

  if (loading) {
    $('#property-grid').innerHTML = Array.from({ length: 3 }, () =>
      '<div class="loading-placeholder" aria-hidden="true"><div class="skeleton image"></div><div class="skeleton"></div><div class="skeleton short"></div><div class="skeleton"></div></div>'
    ).join('');
  } else {
    const selected = currentFilter ? allProperties.filter((p) => p.status === currentFilter) : properties;
    $('#property-grid').innerHTML = selected.map(card).join('');
  }
}

function showModal(eyebrow, title, body, actions = '', trigger) {
  $('#modal-eyebrow').textContent = eyebrow;
  $('#modal-content').innerHTML = `<h2 id="modal-title">${title}</h2>${body}${actions ? `<div class="dialog-actions">${actions}</div>` : ''}`;
  openOverlay($('#general-dialog'), trigger);
}

function showCommandPalette(trigger) {
  const items = allProperties.slice(0, 6).map((p) =>
    `<a class="cmd-item" href="analysis.html?id=${p.id}">
      <span><strong>${p.name}</strong> · ${p.city}</span>
      <small>${p.price}</small>
    </a>`
  ).join('');
  showModal(
    'SZYBKA NAWIGACJA (⌘K)',
    'Przejdź do analizy lub miasta',
    `<p class="overlay-intro">Wybierz ostatnio badane mieszkanie lub przejdź bezpośrednio do radaru 727 miast.</p>
     <div class="cmd-list">
       <a class="cmd-item" href="market.html"><span><strong>Radar 727 miast Polski</strong> · Porównanie stawek najmu i GUS BDL</span><small>RYNEK ↗</small></a>
       ${items}
     </div>`,
    '<button class="secondary" data-close>Zamknij (Esc)</button>',
    trigger
  );
}

function showAccount(trigger) {
  const noCredits = previewState === 'no-credits';
  showModal(
    'KONTO INWESTORA · RENTI.TECH',
    'Anna Kowalska',
    `<p class="overlay-intro">Subskrypcja: Deal Desk Pro · Rozliczenia za analizy głębokie (AI Vision + DCF).</p>
     <dl class="facts">
       <div><dt>Dostępne analizy w puli</dt><dd>${noCredits ? '0' : '2'}</dd></div>
       <div><dt>Analizy w toku</dt><dd>${previewState === 'empty' ? '0' : '1'}</dd></div>
       <div><dt>Otwieranie zapisanych raportów</dt><dd>Bezpłatne (0 kredytów)</dd></div>
     </dl>
     <p class="demo-note">Podgląd projektu V3: żadne operacje płatnicze nie są wykonywane.</p>`,
    '<button class="secondary" data-close>Wróć do pracy</button>',
    trigger
  );
}

function confirmSubmission(trigger) {
  if (previewState === 'no-credits') {
    showModal('LIMIT ANALIZ', 'Wykorzystano dostępne analizy.', '<p class="overlay-intro">Twój link pozostaje w polu. Otwieranie wcześniejszych 12 analiz oraz Radar 727 miast pozostają w pełni dostępne.</p>', '<button class="secondary" data-close>Wróć do linku</button>', trigger);
    return;
  }
  if (previewState === 'unavailable') {
    showModal('PRZERWA TECHNICZNA', 'Otodom chwilowo nie odpowiada.', '<p class="overlay-intro">Zachowaliśmy Twój link w polu. Nie pobieramy analizy z limitu.</p>', '<button class="secondary" data-close>Wróć do pulpitu</button>', trigger);
    return;
  }
  showModal(
    'POTWIERDZENIE URUCHOMIENIA SILNIKA',
    'Uruchomić deal-analyzer dla tej oferty?',
    `<p class="overlay-intro">Silnik pobierze ogłoszenie, wykona OCR rzutu mieszkania, sprawdzi stawki najmu w okolicy oraz zestawi ceny GUS BDL.</p>
     <div class="confirm-cost"><span>Koszt operacji</span><strong class="mono">1 analiza z limitu (pozostanie: 1)</strong></div>
     <p class="city-basis">Jeśli ogłoszenie nie zawiera opłaty administracyjnej, raport wyraźnie oznaczy brak danych i nie podstawi fałszywego zera.</p>`,
    '<button class="secondary" data-close>Anuluj</button><button class="primary" id="start-preview">Potwierdź i analizuj</button>',
    trigger
  );
}

document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    showCommandPalette(document.activeElement);
  }
});

document.addEventListener('click', (event) => {
  const filterButton = event.target.closest('[data-filter]');
  if (filterButton) {
    currentFilter = filterButton.dataset.filter;
    const labels = {
      ready: 'FILTR: GOTOWE ANALIZY · 8 MIESZKAŃ',
      attention: 'FILTR: DO WYJAŚNIENIA · 3 MIESZKANIA',
      running: 'FILTR: W TRAKCIE ANALIZY · 1 MIESZKANIE'
    };
    $('#filter-label').textContent = labels[currentFilter];
    renderHome();
    announce(labels[currentFilter]);
    return;
  }
  const action = event.target.closest('[data-action]');
  if (action) {
    const trigger = document.querySelector('dialog[open]') ? overlayTrigger : action;
    switch (action.dataset.action) {
      case 'example': location.href = 'analysis.html?id=p1'; break;
      case 'account': showAccount(trigger); break;
      case 'cmd': showCommandPalette(trigger); break;
      case 'help':
        showModal(
          'METODOLOGIA RENTI.TECH',
          'Inwarianty analityczne platformy',
          `<ol class="step-list">
            <li><div><strong>Nigdy nie mieszamy cen ofertowych z transakcyjnymi.</strong><span>Rejestr GUS BDL (akt notarialny) i bieżące oferty (Cenogram / Otodom) są zawsze prezentowane w osobnych wierszach.</span></div></li>
            <li><div><strong>Brak danych ≠ 0 zł.</strong><span>Brak opłaty do wspólnoty blokuje wyliczenie pozornego zysku netto i wyświetla ostrzeżenie.</span></div></li>
            <li><div><strong>Model 10-letni DCF i Max Bid.</strong><span>Wyliczamy maksymalną cenę zakupu przy zadanym docelowym zwrocie (YOC) i uwzględnieniu nakładów CAPEX.</span></div></li>
          </ol>`,
          '<button class="primary" data-action="example">Zobacz pełny raport (Poznań)</button>',
          trigger
        );
        break;
    }
  }
  if (event.target.closest('#start-preview')) {
    showModal('ZADANIE W KOLEJCE', 'Analiza została rozpoczęta.', '<p class="overlay-intro">Przetwarzamy zdjęcia przez AI Vision oraz pobieramy komparatory najmu. Status sprawdzisz na karcie oferty.</p>', '<button class="primary" data-close>Wróć do pulpitu</button>', overlayTrigger);
    announce('Analiza rozpoczęta.');
  }
});

if ($('#analysis-form')) {
  $('#analysis-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const input = $('#listing-url');
    let valid = false;
    try {
      const url = new URL(input.value.trim());
      valid = url.protocol === 'https:' && ['otodom.pl', 'www.otodom.pl'].includes(url.hostname) && /^\/pl\/oferta\/[^/]+\/?$/.test(url.pathname);
    } catch {}
    if (!valid) {
      input.setAttribute('aria-invalid', 'true');
      $('#url-error').textContent = 'Wklej prawidłowy link do oferty sprzedaży, np. https://www.otodom.pl/pl/oferta/mieszkanie-ID4CpHB';
      $('#url-error').hidden = false;
      input.focus();
      return;
    }
    input.removeAttribute('aria-invalid');
    $('#url-error').hidden = true;
    confirmSubmission($('#analysis-form button[type="submit"]'));
  });
  $('#listing-url').addEventListener('input', () => {
    $('#listing-url').removeAttribute('aria-invalid');
    $('#url-error').hidden = true;
  });
  $('#reset-filter')?.addEventListener('click', () => {
    currentFilter = null;
    renderHome();
    announce('Pokazano trzy ostatnie analizy.');
  });
  $('#home-nav')?.addEventListener('click', () => {
    currentFilter = null;
    renderHome();
    window.scrollTo({ top: 0, behavior: 'instant' });
  });
  $('#preview-state')?.addEventListener('change', (event) => {
    previewState = event.target.value;
    currentFilter = null;
    renderHome();
  });
  renderHome();
}