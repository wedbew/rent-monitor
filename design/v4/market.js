const cities = {
  poznan: {
    name: 'Poznań',
    gusM2: '9 640 zł/m²', askM2: '11 450 zł/m²', yieldAvg: '6,45%',
    tiers: {
      m1: { label: 'Kawalerki · 22–34 m²', rent: '1 850–2 150 zł', count: '92' },
      m2: { label: '2 pokoje · 35–50 m²', rent: '2 400–2 700 zł', count: '124' },
      m3: { label: '3 pokoje · 51–68 m²', rent: '3 100–3 550 zł', count: '68' }
    }
  },
  warszawa: {
    name: 'Warszawa',
    gusM2: '15 420 zł/m²', askM2: '17 890 zł/m²', yieldAvg: '5,62%',
    tiers: {
      m1: { label: 'Kawalerki · 22–34 m²', rent: '2 450–2 900 zł', count: '210' },
      m2: { label: '2 pokoje · 35–50 m²', rent: '3 000–3 600 zł', count: '286' },
      m3: { label: '3 pokoje · 51–68 m²', rent: '4 100–4 900 zł', count: '154' }
    }
  },
  wroclaw: {
    name: 'Wrocław',
    gusM2: '11 380 zł/m²', askM2: '13 120 zł/m²', yieldAvg: '6,10%',
    tiers: {
      m1: { label: 'Kawalerki · 22–34 m²', rent: '2 050–2 350 zł', count: '115' },
      m2: { label: '2 pokoje · 35–50 m²', rent: '2 600–3 000 zł', count: '168' },
      m3: { label: '3 pokoje · 51–68 m²', rent: '3 300–3 850 zł', count: '79' }
    }
  },
  gdansk: {
    name: 'Gdańsk',
    gusM2: '11 750 zł/m²', askM2: '13 600 zł/m²', yieldAvg: '6,18%',
    tiers: {
      m1: { label: 'Kawalerki · 22–34 m²', rent: '2 000–2 350 zł', count: '88' },
      m2: { label: '2 pokoje · 35–50 m²', rent: '2 550–2 950 zł', count: '142' },
      m3: { label: '3 pokoje · 51–68 m²', rent: '3 400–3 900 zł', count: '61' }
    }
  },
  krakow: {
    name: 'Kraków',
    gusM2: '13 210 zł/m²', askM2: '15 480 zł/m²', yieldAvg: '5,74%',
    tiers: {
      m1: { label: 'Kawalerki · 22–34 m²', rent: '2 100–2 450 zł', count: '134' },
      m2: { label: '2 pokoje · 35–50 m²', rent: '2 650–3 100 zł', count: '195' },
      m3: { label: '3 pokoje · 51–68 m²', rent: '3 500–4 150 zł', count: '91' }
    }
  },
  katowice: {
    name: 'Katowice',
    gusM2: '7 420 zł/m²', askM2: '8 650 zł/m²', yieldAvg: '7,35%',
    tiers: {
      m1: { label: 'Kawalerki · 22–34 m²', rent: '1 550–1 800 zł', count: '64' },
      m2: { label: '2 pokoje · 35–50 m²', rent: '1 950–2 350 zł', count: '98' },
      m3: { label: '3 pokoje · 51–68 m²', rent: '2 500–2 950 zł', count: '44' }
    }
  }
};

const select = document.querySelector('#city-select');
const content = document.querySelector('#city-content');
const dialog = document.querySelector('#general-dialog');
let currentTier = 'm2';
let trigger;

function renderCity() {
  const city = cities[select.value];
  const tier = city.tiers[currentTier];
  content.innerHTML = `
    <div class="city-estimate">
      <p class="eyebrow">${city.name} · ${tier.label}</p>
      <strong>${tier.rent}</strong>
      <span>Przedział czynszu dla właściciela / miesiąc (Q25–Q75)</span>
      <div class="city-kpi-strip">
        <div><span>Mediana GUS BDL (Transakcje)</span><b>${city.gusM2}</b></div>
        <div><span>Mediana Ofert Sprzedaży</span><b>${city.askM2}</b></div>
        <div><span>Średni Gross Yield</span><b style="color:var(--green);">${city.yieldAvg}</b></div>
      </div>
    </div>
    <div class="city-context">
      <h2>Jak interpretować ten przedział?</h2>
      <p class="city-basis">To orientacyjny poziom najmu z aktywnych ogłoszeń (bez czynszu administracyjnego i mediów). Służy do szybkiej kalibracji oczekiwań przed uruchomieniem pełnego modelu DCF dla konkretnego adresu.</p>
      <details open>
        <summary>Zakres próby i separacja źródeł (price-intel)</summary>
        <dl class="facts">
          <div><dt>Próbka aktywnych ofert najmu</dt><dd>${tier.count} ogłoszeń</dd></div>
          <div><dt>Podstawa czynszu</dt><dd>Ceny ofertowe (Otodom)</dd></div>
          <div><dt>Ceny zakupu GUS BDL</dt><dd>Osobny rejestr aktów notarialnych</dd></div>
        </dl>
      </details>
    </div>`;
}

select.addEventListener('change', renderCity);
document.querySelectorAll('.tier-pill').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tier-pill').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    currentTier = btn.dataset.tier;
    renderCity();
  });
});

document.addEventListener('click', (event) => {
  if (event.target.closest('[data-close]')) { dialog.close(); return; }
  const action = event.target.closest('[data-action]');
  if (!action) return;
  trigger = action;
  const account = action.dataset.action === 'account';
  document.querySelector('#modal-eyebrow').textContent = account ? 'KONTO INWESTORA' : 'METODOLOGIA RADARU';
  document.querySelector('#modal-content').innerHTML = account
    ? '<h2 id="modal-title">Anna Kowalska</h2><p class="overlay-intro">Przeglądanie radaru 727 miast jest bezpłatne i nie zużywa pakietu analiz.</p>'
    : '<h2 id="modal-title">Skąd pochodzą dane miejskie?</h2><p class="overlay-intro">Moduł <code>otodom-city-report</code> agreguje stawki najmu w podziale na metraże, a moduł <code>price-intel</code> zestawia je z cenami transakcyjnymi GUS BDL bez ich wzajemnego mieszania.</p>';
  dialog.showModal();
});
renderCity();