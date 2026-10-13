// Shared fictional fixtures and property summaries come from main-view.js.
const analysesFilter = document.querySelector('#analyses-filter');
const analysesGrid = document.querySelector('#analyses-grid');
const analysesSearch = document.querySelector('#analyses-search');
const fold = text => text.toLocaleLowerCase('pl').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/ł/g,'l');
function renderAnalyses() {
  const query = fold(analysesSearch.value.trim());
  const selected = allProperties.filter(p => (analysesFilter.value === 'all' || p.status === analysesFilter.value) && fold(`${p.name} ${p.city}`).includes(query));
  analysesGrid.innerHTML = selected.map(card).join('');
  const labels = {all:'Wszystkie analizy',ready:'Gotowe analizy',attention:'Do wyjaśnienia',running:'W trakcie'};
  document.querySelector('#analyses-count').textContent = `${labels[analysesFilter.value]} · ${selected.length}`;
  document.querySelector('#analyses-empty').hidden = selected.length > 0;
}
analysesFilter.addEventListener('change',renderAnalyses);
analysesSearch.addEventListener('input',renderAnalyses);
document.querySelector('#clear-search').addEventListener('click',()=>{
  analysesSearch.value=''; analysesFilter.value='all'; renderAnalyses(); analysesSearch.focus();
});
renderAnalyses();
