// Design fixtures only. No network, financial computation, credit settlement or persistence.
const $ = (selector) => document.querySelector(selector);
const icon = (name, extra = '') => `<svg class="icon ${extra}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
document.querySelectorAll('svg.icon').forEach((element) => element.setAttribute('aria-hidden', 'true'));

const properties = [
  { id:'p1', city:'Poznań · Jeżyce', name:'Mieszkanie przy parku', meta:'42 m² · 2 pokoje', price:'425 000 zł', rent:'2 400–2 700', status:'ready', statusText:'Analiza gotowa', caveat:'Szacunek najmu z cen ofertowych.', date:'Dzisiaj', palette:['#dfe5da','#f3eee3','#99ab96'], note:'Możesz wrócić do szacunku najmu. Przed decyzją sprawdź koszty właściciela i założenia.', admin:'520 zł / mies.', capex:'Nie uwzględniono', quality:'Przykładowy szacunek na podstawie 24 ofert.', maxBid:'Nie obliczono w tym przykładzie' },
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

function building(p, index) {
  const [sky,wall,window] = p.palette;
  return `<svg viewBox="0 0 360 150" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Ilustracja poglądowa mieszkania"><rect width="360" height="150" fill="${sky}"/><circle cx="${index === 1 ? 55 : 290}" cy="30" r="37" fill="#ffffff" opacity=".24"/><path d="M72 150V30h180v120" fill="${wall}"/><path d="M65 30h195" stroke="${window}" stroke-width="5"/><path d="M78 39h168" stroke="#a49d8b" opacity=".4"/><path d="M93 60h31v42H93z M147 60h31v42h-31z M201 60h31v42h-31z M93 121h31v40H93z M147 121h31v40h-31z M201 121h31v40h-31z" fill="${window}"/><path d="M108 60v42 M162 60v42 M216 60v42 M93 80h31 M147 80h31 M201 80h31" stroke="${wall}" stroke-width="2"/><path d="M78 109h170 M78 115h170" stroke="#b2ab9a" stroke-width="1"/><path d="M285 150v-47" stroke="#6c7f67" stroke-width="3"/><ellipse cx="285" cy="98" rx="23" ry="35" fill="#94a18b"/><path d="M25 150v-30" stroke="#6c7f67" stroke-width="2"/><ellipse cx="25" cy="112" rx="13" ry="22" fill="#acb6a0"/><rect y="146" width="360" height="4" fill="#b9bba9"/></svg>`;
}
function card(p, index) {
  const hasRent = p.status === 'ready';
  return `<article class="property-card"><div class="property-top">${building(p,index)}<span class="status ${p.status}">${icon(statusIcon[p.status])}${p.statusText}</span></div><div class="property-body"><p class="property-location">${p.city}</p><h3>${p.name}</h3><p class="property-meta">${p.meta}</p><dl class="property-numbers"><div><dt>Cena z ogłoszenia</dt><dd>${p.price}</dd></div><div><dt>Najem dla właściciela / mies.</dt><dd>${p.rent}${hasRent?'<small>zł</small>':''}</dd></div></dl><p class="property-caveat ${p.status==='attention'?'warning':''}">${p.caveat}</p></div><div class="property-bottom"><span>${p.date}</span><button class="text-link" data-property="${p.id}" aria-label="${p.status==='running'?'Sprawdź postęp':'Zobacz podsumowanie'}: ${p.name}">${p.status==='running'?'Sprawdź postęp':'Zobacz podsumowanie'}${icon('arrow')}</button></div></article>`;
}
function announce(text) { $('#announcement').textContent = text; }
function openOverlay(dialog, trigger) {
  document.querySelectorAll('dialog[open]').forEach(d => d.close());
  overlayTrigger = trigger || document.activeElement;
  dialog.showModal();
}
document.querySelectorAll('dialog').forEach(dialog => {
  dialog.addEventListener('close', () => {
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
  $('#nav-count').textContent = firstUse ? '0' : '12';
  $('#credit-label').textContent = missingCredits ? 'Brak analiz w limicie' : '2 analizy do wykorzystania';
  $('#url-help > span').textContent = missingCredits ? 'Brak analiz w limicie · sprawdź dostęp przed rozpoczęciem' : '1 analiza z Twojego limitu · koszt potwierdzisz przed startem';
  $('#recent-title').textContent = firstUse ? 'Wszystko zaczyna się od jednego mieszkania' : 'Wróć do swoich mieszkań';
  $('#recent-caption').textContent = loading ? 'Ładujemy Twoje analizy…' : firstUse ? 'Nie musisz znać rynku na pamięć. Pomagamy uporządkować informacje.' : 'Ostatnie analizy. Najważniejsze rzeczy na pierwszy rzut oka.';
  if (loading) {
    $('#property-grid').innerHTML = Array.from({length:3},()=>'<div class="loading-placeholder" aria-hidden="true"><div class="skeleton image"></div><div class="skeleton"></div><div class="skeleton short"></div><div class="skeleton"></div></div>').join('');
  } else {
    const selected = currentFilter ? allProperties.filter(p => p.status === currentFilter) : properties;
    $('#property-grid').innerHTML = selected.map(card).join('');
  }
}

function showProperty(id, trigger) {
  const p = allProperties.find(item => item.id === id) || properties[0];
  $('#detail-content').innerHTML = `<p class="detail-location">${p.city}</p><h2 id="detail-title">${p.name}</h2><p class="property-meta">${p.meta}</p><span class="status detail-status ${p.status==='attention'?'amber':p.status==='ready'?'green':'neutral'}">${icon(statusIcon[p.status])}${p.statusText}</span><p class="detail-note ${p.status==='attention'?'warning':''}">${p.note}</p><dl class="facts"><div><dt>Cena z ogłoszenia</dt><dd>${p.price}<small>Cena ofertowa</small></dd></div><div><dt>Najem dla właściciela</dt><dd>${p.rent}${p.status==='ready'?' zł':''}<small>${p.status==='ready'?'Miesięcznie, przed podatkiem i kosztami':'Wynik niedostępny'}</small></dd></div><div><dt>Opłata administracyjna</dt><dd>${p.admin}<small>Koszt, nie przychód</small></dd></div></dl><details><summary>Co wiemy, a czego brakuje?</summary><p>${p.quality}</p><p>${p.status==='ready'?'Nie oceniono kosztów remontu ani ceny spełniającej cel zwrotu. „Analiza gotowa” oznacza zakończenie pracy, nie rekomendację zakupu.':'Uzupełnij brakujące dane przed oceną inwestycji. Brak wyniku nie oznacza zera.'}</p></details><details><summary>Koszty i cena spełniająca cel</summary><dl class="facts"><div><dt>Budżet remontu</dt><dd>${p.capex}</dd></div><div><dt>Cena spełniająca cel (Max Bid)</dt><dd>${p.maxBid}</dd></div></dl><p>W aplikacji te wartości pochodzą z silnika analitycznego. Cena spełniająca cel zależy od założeń i oczekiwanego zwrotu.</p></details><details><summary>Skąd pochodzą liczby?</summary><p>Dane przykładowe · październik 2026. Szacunek najmu oparty na ofertach, nie umowach najmu. Ceny transakcyjne nie są tu pokazane ani mieszane z ofertowymi.</p></details><p class="demo-note">Ilustracja interakcji na pulpicie. Pełny raport mieszkania będzie osobnym widokiem. Ten podgląd nie jest rzeczywistą wyceną.</p>`;
  openOverlay($('#detail-dialog'), trigger);
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
  const propertyButton = event.target.closest('[data-property]');
  if (propertyButton) { showProperty(propertyButton.dataset.property, document.querySelector('dialog[open]') ? overlayTrigger : propertyButton); return; }
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
      case 'example': showProperty('p1', trigger); break;
      case 'account': showAccount(trigger); break;
      case 'help': showModal('JAK TO DZIAŁA','Od ogłoszenia do zrozumienia.','<ol class="step-list"><li><div><strong>Wklej link do mieszkania na sprzedaż.</strong><span>Koszt potwierdzisz przed rozpoczęciem.</span></div></li><li><div><strong>Sprawdzimy ofertę i kontekst.</strong><span>Najem, koszty i dostępne dowody — w jednym miejscu.</span></div></li><li><div><strong>Zobacz podsumowanie. Pytaj o szczegóły.</strong><span>Założenia i źródła są dostępne, gdy ich potrzebujesz. Wynik pomaga ocenić ofertę; decyzja należy do Ciebie.</span></div></li></ol><p class="demo-note">To podgląd projektu. Analiza źródeł i zdjęć wymaga działającej usługi.</p>','<button class="primary" data-action="example">Zobacz przykład</button>', trigger); break;
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
