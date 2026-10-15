const requestedId = new URLSearchParams(location.search).get('id') || 'p1';
const analysis = allProperties.find((p) => p.id === requestedId);
const title = document.querySelector('#analysis-title');

if (!analysis) {
  title.textContent = 'Nie znaleźliśmy tej analizy.';
  document.querySelector('#analysis-identity').textContent = 'Wróć do listy i wybierz mieszkanie, które chcesz sprawdzić.';
  document.querySelector('#analysis-kpis').hidden = true;
  document.querySelector('#analysis-modules').hidden = true;
  document.querySelector('#dcf-section').hidden = true;
  document.querySelector('#analysis-status').hidden = true;
} else {
  title.textContent = analysis.name;
  document.title = `${analysis.name} (${analysis.code}) — renti.tech`;
  document.querySelector('#crumb-code').textContent = analysis.code;
  document.querySelector('#analysis-eyebrow').textContent = `RAPORT DEAL-ANALYZER // ${analysis.code}`;
  document.querySelector('#analysis-identity').textContent = `${analysis.city} · ${analysis.meta} · Badanie: ${analysis.date}`;
  document.querySelector('#analysis-price').textContent = analysis.price;
  document.querySelector('#analysis-ppm2').textContent = `${analysis.pricePerM2} (Oferta sprzedaży)`;
  document.querySelector('#analysis-rent').textContent = analysis.status === 'ready' ? `${analysis.rent} zł` : analysis.rent;
  document.querySelector('#analysis-yield').textContent = analysis.status === 'ready' ? `${analysis.grossYield} / ${analysis.netYield}` : analysis.grossYield;
  document.querySelector('#analysis-admin').textContent = `Czynsz adm.: ${analysis.admin}`;
  document.querySelector('#analysis-maxbid').textContent = analysis.maxBid;
  document.querySelector('#analysis-spread').textContent = analysis.spreadAskVsMax;

  const status = document.querySelector('#analysis-status');
  status.textContent = analysis.statusText;
  status.classList.add(analysis.status);

  const note = document.querySelector('#analysis-note');
  note.textContent = analysis.note;
  if (analysis.status === 'attention') note.classList.add('warning');

  document.querySelector('#pi-listing').textContent = analysis.pricePerM2;
  document.querySelector('#pi-asking').textContent = analysis.askingMedianM2;
  document.querySelector('#pi-gus').textContent = analysis.gusTransM2;
  document.querySelector('#ocr-rooms').textContent = analysis.ocrRooms;
  document.querySelector('#ocr-capex').textContent = analysis.capex;
  document.querySelector('#ocr-admin').textContent = analysis.admin;

  const tbody = document.querySelector('#dcf-tbody');
  if (analysis.status !== 'ready') {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:24px; color:var(--amber);">Projekcja 10-letnia DCF wymaga potwierdzonej opłaty administracyjnej i zakończonego odczytu oferty.</td></tr>`;
  } else {
    let cumulative = 0;
    const baseRent = 2550;
    tbody.innerHTML = Array.from({ length: 10 }, (_, idx) => {
      const yr = idx + 1;
      const factor = Math.pow(1.03, idx);
      const gross = Math.round(baseRent * 11 * factor);
      const taxAndAdmin = Math.round(gross * 0.085 + 1400 * factor);
      const reserve = Math.round(1200 * factor);
      const noi = gross - taxAndAdmin - reserve;
      cumulative += noi;
      return `
        <tr>
          <td>Rok ${yr} (202${5 + yr > 9 ? '3' + (5 + yr - 10) : 6 + idx})</td>
          <td>${gross.toLocaleString('pl-PL')} zł</td>
          <td>-${taxAndAdmin.toLocaleString('pl-PL')} zł</td>
          <td>-${reserve.toLocaleString('pl-PL')} zł</td>
          <td style="color:var(--green); font-weight:600;">+${noi.toLocaleString('pl-PL')} zł</td>
          <td>${cumulative.toLocaleString('pl-PL')} zł</td>
        </tr>`;
    }).join('');
  }
}