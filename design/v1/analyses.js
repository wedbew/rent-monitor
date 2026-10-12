// Shared fictional fixtures and property summaries come from main-view.js.
const analysesFilter = document.querySelector('#analyses-filter');
const analysesGrid = document.querySelector('#analyses-grid');
function renderAnalyses() {
  const selected = allProperties.filter(p => analysesFilter.value === 'all' || p.status === analysesFilter.value);
  analysesGrid.innerHTML = selected.map(card).join('');
  const labels = {all:'Wszystkie analizy',ready:'Gotowe analizy',attention:'Do wyjaśnienia',running:'W trakcie'};
  document.querySelector('#analyses-count').textContent = `${labels[analysesFilter.value]} · ${selected.length}`;
}
analysesFilter.addEventListener('change',renderAnalyses);
renderAnalyses();
