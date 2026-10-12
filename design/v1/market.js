// Fictional market fixtures. No network requests or financial calculations.
const cities = {
  poznan: {name:'Poznań',rent:'2 400–2 700 zł',count:'124'},
  warszawa: {name:'Warszawa',rent:'3 000–3 600 zł',count:'286'},
  wroclaw: {name:'Wrocław',rent:'2 600–3 000 zł',count:'168'},
};
const select = document.querySelector('#city-select');
const content = document.querySelector('#city-content');
const dialog = document.querySelector('#general-dialog');
let trigger;
document.querySelectorAll('svg.icon').forEach(icon => icon.setAttribute('aria-hidden','true'));
function renderCity() {
  const city = cities[select.value];
  content.innerHTML = `<div class="city-estimate"><p>${city.name} · 2 pokoje · 35–50 m²</p><strong>${city.rent}</strong><span>Najem dla właściciela / miesiąc</span><p class="market-period">Ceny ofertowe · wrzesień 2026 · dane przykładowe</p></div><div class="city-context"><h2>Co mówi Ci ten przedział?</h2><p class="city-basis">Orientacyjny poziom najmu z ofert. Opłaty administracyjne i media są poza tą kwotą. To kontekst dla miasta, a nie wycena konkretnego mieszkania.</p><details><summary>Zakres i źródło danych</summary><dl class="facts"><div><dt>Okres obserwacji</dt><dd>Wrzesień 2026</dd></div><div><dt>Oferty w przykładzie</dt><dd>${city.count}</dd></div><div><dt>Podstawa</dt><dd>Ceny ofertowe</dd></div></dl><p>Wszystkie wartości w podglądzie są fikcyjne. W produkcji pokażemy źródło, datę zbioru, pokrycie i ograniczenia otrzymane z API. Ceny transakcyjne pozostają osobnym zbiorem.</p></details></div>`;
}
select.addEventListener('change',renderCity);
document.addEventListener('click',event => {
  if(event.target.closest('[data-close]')) {dialog.close();return;}
  const action = event.target.closest('[data-action]');
  if(!action) return;
  trigger = action;
  const account = action.dataset.action === 'account';
  document.querySelector('#modal-eyebrow').textContent = account ? 'MOJE KONTO' : 'JAK TO DZIAŁA';
  document.querySelector('#modal-content').innerHTML = account
    ? '<h2 id="modal-title">Wiesz, z czego korzystasz.</h2><p class="overlay-intro">Anna Kowalska · przykładowe konto</p><dl class="facts"><div><dt>Dostępne analizy</dt><dd>2</dd></div><div><dt>Analizy w toku</dt><dd>1</dd></div></dl><p class="demo-note">Przeglądanie rynku nie uruchamia analizy ogłoszenia. Plan i rozliczenia wymagają zatwierdzonej oferty.</p>'
    : '<h2 id="modal-title">Miasto daje kontekst.</h2><p class="overlay-intro">Wybierz miasto, zobacz orientacyjny poziom najmu i rozwiń źródła, gdy potrzebujesz więcej informacji. Konkretne mieszkanie sprawdzisz na pulpicie po wklejeniu linku.</p><p class="demo-note">Ten projekt korzysta wyłącznie z przykładowych danych.</p>';
  dialog.showModal();
});
dialog.addEventListener('close',()=>trigger?.focus());
dialog.addEventListener('click',event=>{
  if(event.target!==dialog)return;
  const r=dialog.getBoundingClientRect();
  if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();
});
renderCity();
