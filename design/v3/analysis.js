// Fixture report: render source values only; no financial calculations.
const requestedId = new URLSearchParams(location.search).get('id');
const analysis = allProperties.find(p => p.id === requestedId);
const title = document.querySelector('#analysis-title');
const report=document.querySelector('#report-content');
if(!analysis){
 title.textContent='Nie znaleźliśmy tej analizy.';
 document.querySelector('#analysis-identity').textContent='Wróć do listy i wybierz mieszkanie, które chcesz sprawdzić.';
 document.querySelector('.analysis-overview').hidden=true;
 document.querySelector('#analysis-status').hidden=true;
}else{
 title.textContent=analysis.name;document.title=`${analysis.name} — Renti`;
 document.querySelector('#analysis-identity').textContent=`${analysis.city} · ${analysis.meta}`;
 document.querySelector('#analysis-price').textContent=analysis.price;
 const status=document.querySelector('#analysis-status');status.textContent=analysis.statusText;status.classList.add(analysis.status);
 const note=document.querySelector('#analysis-note');note.textContent=analysis.status==='running'?analysis.note:analysis.caveat;
 if(analysis.status==='attention')note.classList.add('warning');
 if(analysis.status==='running'){
  report.innerHTML='<section class="next-step"><p class="eyebrow">MOŻESZ WRÓCIĆ PÓŹNIEJ</p><h2>Sprawdzamy ogłoszenie i kontekst najmu.</h2><p>Wynik znajdziesz w swoich analizach. Ponowne wklejanie linku nie jest potrzebne.</p><a class="secondary" href="analyses.html">Wróć do moich analiz →</a></section>';
 }else{
 const partial=analysis.status==='attention';
 report.innerHTML=`<section class="next-step"><p class="eyebrow">TWÓJ NASTĘPNY KROK</p><h2>${partial?'Ustal czynsz administracyjny.':'Sprawdź, co zostaje po kosztach.'}</h2><p>${partial?'Bez tej informacji wynik pozostaje niepełny. Zacznij od jednego pytania do sprzedającego.':'Przedział najmu to punkt wyjścia. Potwierdź opłaty i stan mieszkania, zanim ocenisz opłacalność.'}</p><button class="secondary" id="question-toggle" aria-expanded="false" aria-controls="seller-question">Pokaż pytanie do sprzedającego ↓</button><div class="seller-question" id="seller-question" hidden>${partial?'Jaka jest miesięczna opłata administracyjna? Proszę o zestawienie z podziałem na koszty stałe, fundusz remontowy i zaliczki na media.':'Czy mogę otrzymać aktualne zestawienie opłat administracyjnych oraz informację o planowanych remontach i funduszu remontowym?'}</div></section>
 <div class="report-grid"><section class="report-panel"><p class="eyebrow">01 — NAJEM</p><h2>Przychód przed kosztami</h2><div class="report-value">${analysis.rent}${partial?'':' zł'}<small>Najem dla właściciela / miesiąc</small></div><p>${partial?'Brak kompletnego szacunku. Nie zastępujemy brakujących danych zerem.':'Szacunek z cen ofertowych. Opłaty administracyjne i media są poza tą kwotą.'}</p><details><summary>Na czym opiera się szacunek?</summary><p>${analysis.quality} Zwróć uwagę na podobny metraż, liczbę pokoi, standard i lokalizację. Ten przykład nie zawiera listy porównywalnych ofert.</p></details></section>
 <section class="report-panel"><p class="eyebrow">02 — KOSZTY</p><h2>Co trzeba uwzględnić?</h2><dl class="facts"><div><dt>Czynsz administracyjny</dt><dd>${analysis.admin}</dd></div><div><dt>Remont</dt><dd>${analysis.capex}</dd></div><div><dt>Wynik po kosztach</dt><dd>Brak pełnego wyliczenia</dd></div></dl><details><summary>Dlaczego czynsz jest kosztem?</summary><p>Opłata dla wspólnoty lub spółdzielni jest kosztem utrzymania. Nie jest najmem dla właściciela. Ustal jej składniki i sposób rozliczania z najemcą.</p></details></section>
 <section class="report-panel"><p class="eyebrow">03 — ZAKUP</p><h2>Cena to początek rozmowy.</h2><div class="report-value">${analysis.price}<small>Cena ofertowa · nie transakcyjna</small></div><p>Cena z ogłoszenia nie potwierdza ceny sprzedaży. Zbiór transakcji i oferty muszą być oceniane osobno.</p><details><summary>Cena spełniająca Twój cel</summary><p>${analysis.maxBid}. Do ustalenia tej ceny potrzebne są kompletne koszty, cel i założenia inwestycji.</p></details></section>
 <section class="report-panel"><p class="eyebrow">04 — PEWNOŚĆ DANYCH</p><h2>Wiesz, czego jeszcze nie wiesz.</h2><dl class="facts"><div><dt>Podstawa najmu</dt><dd>Ceny ofertowe</dd></div><div><dt>Koszty remontu</dt><dd>Do weryfikacji</dd></div><div><dt>Ocena inwestycji</dt><dd>Nie nadano</dd></div></dl><details><summary>Źródła i ograniczenia</summary><p>Dane są fikcyjne. W tym przykładzie nie ma zweryfikowanych źródeł ani pełnych założeń. Gotowy szacunek najmu nie oznacza kompletnej oceny zakupu.</p></details></section></div><p class="report-footnote">Przykład projektu, bez pełnej wyceny. Nie obliczamy zwrotu ani rekomendacji zakupu z niekompletnych danych.</p>`;
 document.querySelector('#question-toggle').addEventListener('click',event=>{const q=document.querySelector('#seller-question');q.hidden=!q.hidden;event.currentTarget.setAttribute('aria-expanded',String(!q.hidden));event.currentTarget.textContent=q.hidden?'Pokaż pytanie do sprzedającego ↓':'Ukryj pytanie ↑';});
 }
}
