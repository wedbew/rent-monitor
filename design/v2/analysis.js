// Navigation scaffold only: the full analytic report is intentionally not rendered.
const requestedId = new URLSearchParams(location.search).get('id');
const analysis = allProperties.find(p => p.id === requestedId);
const title = document.querySelector('#analysis-title');
if (!analysis) {
  title.textContent = 'Nie znaleźliśmy tej analizy.';
  document.querySelector('#analysis-identity').textContent = 'Wróć do listy i wybierz mieszkanie, które chcesz sprawdzić.';
  document.querySelector('.analysis-overview').hidden = true;
  document.querySelector('.report-design-note').hidden = true;
  document.querySelector('#analysis-status').hidden = true;
} else {
  title.textContent = analysis.name;
  document.title = `${analysis.name} — renti.tech`;
  document.querySelector('#analysis-identity').textContent = `${analysis.city} · ${analysis.meta}`;
  document.querySelector('#analysis-price').textContent = analysis.price;
  const status = document.querySelector('#analysis-status');
  status.textContent = analysis.statusText;
  status.classList.add(analysis.status);
  const note = document.querySelector('#analysis-note');
  note.textContent = analysis.status === 'running' ? analysis.note : analysis.caveat;
  if (analysis.status === 'attention') note.classList.add('warning');
}
