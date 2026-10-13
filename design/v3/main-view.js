// Design fixtures only. No network, financial computation, credit settlement or persistence.
const $ = (selector) => document.querySelector(selector);
const icon = (name, extra = '') => `<svg class="icon ${extra}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
document.querySelectorAll('svg.icon').forEach((element) => element.setAttribute('aria-hidden', 'true'));

const properties = [
  { id:'p1', city:'Poznań · Jeżyce', name:'Mieszkanie przy parku', meta:'42 m² · 2 pokoje', price:'425 000 zł', rent:'2 400–2 700', status:'ready', statusText:'Analiza gotowa', caveat:'Szacunek z ofert. Koszty i remont wymagają weryfikacji.', date:'Dzisiaj', palette:['#dfe5da','#f3eee3','#99ab96'], note:'Możesz wrócić do szacunku najmu. Przed decyzją sprawdź koszty właściciela i założenia.', admin:'520 zł / mies.', capex:'Nie uwzględniono', quality:'Przykładowy szacunek na podstawie 24 ofert.', maxBid:'Nie obliczono w tym przykładzie' },
  { id:'p2', city:'Wrocław · Krzyki', name:'Dwa pokoje z balkonem', meta:'48 m² · 2 pokoje', price:'590 000 zł', rent:'Brak danych', status:'attention', statusText:'Do wyjaśnienia', caveat:'Brakuje opłaty administracyjnej. Wynik niepełny.', date:'Wczoraj', palette:['#e6d8c8','#f8ede0','#b5a08b'], note:'Zapytaj sprzedającego o opłatę administracyjną. Bez niej nie pokażemy wiarygodnego wyniku po kosztach.', admin:'Brak danych', capex:'Ceny katalogowe są wstępne', quality:'Niepełne dane. Brak ostatecznej oceny inwestycji.', maxBid:'Brak danych' },
  { id:'p3', city:'Warszawa · Mokotów', name:'Jasne mieszkanie na Służewie', meta:'35 m² · 2 pokoje', price:'620 000 zł', rent:'W trakcie', status:'running', statusText:'W trakcie', caveat:'Sprawdzamy ogłoszenie i kontekst najmu.', date:'Przed chwilą', palette:['#dde3e5','#eaf0ed','#8b9c9f'], note:'Analiza trwa. Możesz zamknąć ten panel i wrócić później. Nie musisz ponownie wklejać linku.', admin:'W trakcie', capex:'W trakcie', quality:'Wyniki pojawią się po zakończeniu analizy.', maxBid:'W trakcie' },
];
// Each fixture appears once; home counters and the full list share the same cohort.
const archive = [
  {id:'p4',city:'Gdańsk · Wrzeszcz',name:'Mieszkanie przy alei',meta:'44 m² · 2 pokoje',price:'510 000 zł',rent:'2 600–2 900',status:'ready',date:'9 października'},
  {id:'p5',city:'Poznań · Łazarz',name:'Dwa pokoje w kamienicy',meta:'46 m² · 2 pokoje',price:'410 000 zł',rent:'2 200–2 500',status:'ready',date:'8 października'},
  {id:'p6',city:'Łódź · Śródmieście',name:'Mieszkanie z osobną kuchnią',meta:'40 m² · 2 pokoje',price:'315 000 zł',rent:'1 900–2 200',status:'ready',date:'7 października'},
  {id:'p7',city:'Wrocław · Ołbin',name:'Mieszkanie blisko centrum',meta:'39 m² · 2 pokoje',price:'455 000 zł',rent:'Brak danych',status:'attention',date:'6 października'},
  {id:'p8',city:'Katowice · Ligota',name:'Dwa pokoje przy lesie',meta:'50 m² · 2 pokoje',price:'375 000 zł',rent:'2 000–2 300',status:'ready',date:'5 października'},
  {id:'p9',city:'Kraków · Podgórze',name:'Mieszkanie z loggią',meta:'43 m² · 2 pokoje',price:'560 000 zł',rent:'2 500–2 800',status:'ready',date:'4 października'},
  {id:'p10',city:'Szczecin · Centrum',name:'Kawalerka na drugim piętrze',meta:'29 m² · 1 pokój',price:'295 000 zł',rent:'Brak danych',status:'attention',date:'3 października'},
  {id:'p11',city:'Bydgoszcz · Bielawy',name:'Mieszkanie przy uczelni',meta:'38 m² · 2 pokoje',price:'310 000 zł',rent:'1 800–2 100',status:'ready',date:'2 października'},
  {id:'p12',city:'Toruń · Mokre',name:'Dwa pokoje na spokojnej ulicy',meta:'45 m² · 2 pokoje',price:'350 000 zł',rent:'1 900–2 200',status:'ready',date:'1 października'},
].map(p => ({...properties[p.status === 'ready' ? 0 : 1], ...p}));
const allProperties = [...properties, ...archive];
const statusIcon = {ready:'check',attention:'alert',running:'clock'};
let previewState = 'returning';
let currentFilter = null;
let overlayTrigger = null;

function card(p, index) {
  const hasRent = p.status === 'ready';
  return `<article class="property-card"><div class="property-top"><span class="property-symbol" aria-hidden="true">${p.id.slice(1).padStart(2,"0")}</span><span class="status ${p.status}">${icon(statusIcon[p.status])}${p.statusText}</span></div><div class="property-body"><p class="property-location">${p.city}</p><h3>${p.name}</h3><p class="property-meta">${p.meta}</p><dl class="property-numbers"><div><dt>Cena z ogłoszenia</dt><dd>${p.price}</dd></div><div><dt>Najem dla właściciela / mies.</dt><dd>${p.rent}${hasRent?'<small>zł</small>':''}</dd></div></dl><p class="property-caveat ${p.status==='attention'?'warning':''}">${p.caveat}</p></div><div class="property-bottom"><span>${p.date}</span><a class="text-link" href="analysis.html?id=${p.id}" aria-label="${p.status==='running'?'Sprawdź postęp':'Zobacz analizę'}: ${p.name}">${p.status==='running'?'Sprawdź postęp':'Zobacz analizę'}${icon('arrow')}</a></div></article>`;
}
function announce(text) { $('#announcement').textContent = text; }
function openOverlay(dialog, trigger) {
  document.querySelectorAll('dialog[open]').forEach(d => d.close());
  overlayTrigger = trigger || document.activeElement;
  dialog.showModal();
}
document.querySelectorAll('dialog').forEach(dialog => {
  dialog.addEventListener('close', () => {
    if (dialog.id === 'navigation-dialog') return;
    // When switching overlays, allow the newly opened native dialog to retain focus.
    if (!document.querySelector('dialog[open]') && overlayTrigger?.isConnected) overlayTrigger.focus();
  });
  dialog.addEventListener('click', e => {
    if (e.target.closest('[data-close]')) dialog.close();
    if (e.target === dialog) {
      const r = dialog.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close();
    }
  });
});

function renderHome() {
  const firstUse = previewState === 'empty';
  const loading = previewState === 'loading';
  const missingCredits = previewState === 'no-credits';
  $('#activity').hidden = firstUse || loading;
  $('#service-notice').hidden = previewState !== 'unavailable';
  $('#empty-state').hidden = !firstUse;
  $('#property-grid').hidden = firstUse;
  $('#all-button').hidden = firstUse || loading;
  $('#filter-bar').hidden = !currentFilter || firstUse || loading;
  $('#credit-label').textContent = missingCredits ? 'Brak analiz w limicie' : '2 analizy do wykorzystania';
  $('#url-help > span').textContent = missingCredits ? 'Brak analiz w limicie · sprawdź dostęp przed rozpoczęciem' : '1 analiza z Twojego limitu · koszt potwierdzisz przed startem';
  $('#recent-title').textContent = firstUse ? 'Wszystko zaczyna się od jednego mieszkania' : 'Na Twoim radarze';
  $('#recent-caption').textContent = loading ? 'Ładujemy Twoje analizy…' : firstUse ? 'Nie musisz znać rynku na pamięć. Pomagamy uporządkować informacje.' : 'Ostatnie analizy. Najważniejsze rzeczy na pierwszy rzut oka.';
  if (loading) {
    $('#property-grid').innerHTML = Array.from({length:3},()=>'<div class="loading-placeholder" aria-hidden="true"><div class="skeleton image"></div><div class="skeleton"></div><div class="skeleton short"></div><div class="skeleton"></div></div>').join('');
  } else {
    const selected = currentFilter ? allProperties.filter(p => p.status === currentFilter) : properties;
    $('#property-grid').innerHTML = selected.map(card).join('');
  }
}

function showModal(eyebrow, title, body, actions = '', trigger) {
  $('#modal-eyebrow').textContent = eyebrow;
  $('#modal-content').innerHTML = `<h2 id="modal-title">${title}</h2>${body}${actions ? `<div class="dialog-actions">${actions}</div>` : ''}`;
  openOverlay($('#general-dialog'), trigger);
}
function showAccount(trigger) {
  const noCredits = previewState==='no-credits';
  showModal('MOJE KONTO','Wiesz, z czego korzystasz.',`<p class="overlay-intro">Anna Kowalska · przykładowe konto</p><dl class="facts"><div><dt>Dostępne analizy</dt><dd>${noCredits?'0':'2'}</dd></div><div><dt>Analizy w toku</dt><dd>${previewState==='empty'?'0':'1'}</dd></div></dl><p class="overlay-intro">Otwarcie wcześniejszego wyniku nie zużywa kolejnej analizy. W aplikacji limit i rozliczenia zawsze pochodzą z Twojego konta.</p><p class="demo-note">Plan, cenę i opcje dostępu pokażemy po zatwierdzeniu oferty. Ten podgląd nie uruchamia płatności.</p>`,'<button class="secondary" data-close>Wróć do pulpitu</button>',trigger);
}
function confirmSubmission(trigger) {
  if (previewState==='no-credits') {
    showModal('DOSTĘP DO ANALIZ','Wykorzystano dostępne analizy.','<p class="overlay-intro">Twój link pozostaje w polu. W aplikacji w tym miejscu sprawdzisz dostępne opcje konta przed ponownym uruchomieniem analizy.</p><p class="demo-note">Cennik i limity wymagają zatwierdzenia. Płatności nie są częścią podglądu.</p>','<button class="secondary" data-close>Wróć do linku</button>',trigger);
    return;
  }
  if (previewState==='unavailable') {
    showModal('CHWILOWA PRZERWA','Nie możemy teraz pobrać ogłoszenia.','<p class="overlay-intro">Link został w polu. Nie rozpoczynamy analizy i nie zużywamy limitu. Spróbuj ponownie po przywróceniu dostępu.</p>','<button class="secondary" data-close>Wróć do pulpitu</button>',trigger);
    return;
  }
  showModal('ZANIM ZACZNIEMY','Sprawdźmy to mieszkanie.','<p class="overlay-intro">Przeanalizujemy ogłoszenie sprzedaży, zdjęcia i dostępny kontekst rynku.</p><div class="confirm-cost"><span>Koszt analizy</span><strong>1 analiza z limitu</strong></div><p class="city-basis">Masz 2 dostępne analizy. Nieudana lub odrzucona analiza zwalnia rezerwację. Wynik z ograniczonymi danymi może zużyć analizę — pokażemy te ograniczenia.</p><p class="demo-note">Tryb projektu: link nie zostanie wysłany. Poniższy przycisk pokazuje wyłącznie przykład stanu po rozpoczęciu.</p>','<button class="secondary" data-close>Wróć do linku</button><button class="primary" id="start-preview">Rozpocznij podgląd</button>',trigger);
}
document.addEventListener('click', event => {
  const filterButton = event.target.closest('[data-filter]');
  if (filterButton) {
    currentFilter = filterButton.dataset.filter;
    const labels = {ready:'Gotowe analizy · 8 mieszkań',attention:'Do wyjaśnienia · 3 mieszkania',running:'W trakcie analizy · 1 mieszkanie'};
    $('#filter-label').textContent = labels[currentFilter];
    renderHome(); announce(labels[currentFilter]); return;
  }
  const action = event.target.closest('[data-action]');
  if (action) {
    const trigger = document.querySelector('dialog[open]') ? overlayTrigger : action;
    switch(action.dataset.action) {
      case 'example': location.href = 'analysis.html?id=p1'; break;
      case 'account': showAccount(trigger); break;
      case 'help': showModal('JAK TO DZIAŁA','Od ogłoszenia do zrozumienia.','<ol class="step-list"><li><div><strong>Wklej link do mieszkania na sprzedaż.</strong><span>Koszt potwierdzisz przed rozpoczęciem.</span></div></li><li><div><strong>Sprawdzimy ofertę i kontekst.</strong><span>Najem, koszty i dostępne dowody — w jednym miejscu.</span></div></li><li><div><strong>Otwórz analizę. Pytaj o szczegóły.</strong><span>Założenia i źródła są dostępne, gdy ich potrzebujesz. Wynik pomaga ocenić ofertę; decyzja należy do Ciebie.</span></div></li></ol><p class="demo-note">To podgląd projektu. Analiza źródeł i zdjęć wymaga działającej usługi.</p>','<button class="primary" data-action="example">Zobacz przykład</button>', trigger); break;
    }
  }
  if (event.target.closest('#start-preview')) {
    showModal('PRZYKŁAD POSTĘPU','Analiza została rozpoczęta.','<p class="overlay-intro">Sprawdzamy ogłoszenie i kontekst rynku. Możesz wrócić do pulpitu; tam znajdziesz postęp.</p><p class="demo-note">To wyłącznie demonstracja. Nie wysłaliśmy linku, nie zmieniliśmy limitu i nie uruchomiliśmy zadania.</p>','<button class="primary" data-close>Wróć do pulpitu</button>',overlayTrigger);
    announce('Przykładowy stan: analiza rozpoczęta.');
  }
});
if ($('#analysis-form')) {
$('#analysis-form').addEventListener('submit', event => {
  event.preventDefault();
  const input = $('#listing-url');
  let valid = false;
  try { const url = new URL(input.value.trim()); valid = url.protocol==='https:' && ['otodom.pl','www.otodom.pl'].includes(url.hostname) && /^\/pl\/oferta\/[^/]+\/?$/.test(url.pathname) && !url.username && !url.password && !url.port; } catch { /* Show the field error below. */ }
  if (!valid) {
    input.setAttribute('aria-invalid','true');
    $('#url-error').textContent = 'Wklej pełny link do ogłoszenia, np. https://www.otodom.pl/pl/oferta/nazwa-ID123.html';
    $('#url-error').hidden = false; input.focus(); return;
  }
  input.removeAttribute('aria-invalid'); $('#url-error').hidden = true;
  confirmSubmission($('#analysis-form button[type="submit"]'));
});
$('#listing-url').addEventListener('input', () => { $('#listing-url').removeAttribute('aria-invalid'); $('#url-error').hidden=true; });
$('#reset-filter').addEventListener('click', () => { currentFilter=null; renderHome(); announce('Pokazano trzy ostatnie analizy.'); $('#all-button').focus(); });
$('#home-nav').addEventListener('click', () => { currentFilter=null; renderHome(); window.scrollTo({top:0,behavior:'instant'}); });
$('#preview-state').addEventListener('change',event => { previewState=event.target.value; currentFilter=null; renderHome(); announce(`Stan podglądu: ${event.target.selectedOptions[0].textContent}`); });
renderHome();
}
