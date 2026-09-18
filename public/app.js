/* Touchline web dashboard — talks to /api/analyze and /api/live (Vercel Python functions). */
'use strict';

const COLORS = { Attacker: '#6ee7b7', Midfielder: '#7ea9ff', Defender: '#c4a0ff', Goalkeeper: '#ffc978' };
const POSITIONS = ['Attacker', 'Midfielder', 'Defender', 'Goalkeeper'];
const TARGET = 'transfer_value_eur';

const state = {
  rows: [], metrics: null, warnings: [], model: null, usingDemo: true, lastCsvText: null,
  filters: { query: '', seasons: new Set(), positions: new Set(POSITIONS), club: '', minApps: 0 },
  charts: {}, dossierIndex: null, compareSelection: [],
};

const $ = (id) => document.getElementById(id);
const money = (v) => (v === null || v === undefined || Number.isNaN(v)) ? '\u2014' : `\u20ac${(v / 1e6).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}m`;
const pct = (v) => (v === null || v === undefined || Number.isNaN(v)) ? '\u2014' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;

/* ---------------- CSV export helpers ---------------- */
function csvEscape(v) {
  if (v === null || v === undefined) return '';
  let s = String(v);
  if (typeof v === 'string' && /^[=+\-@]/.test(s.trim())) s = "'" + s; // neutralize formula injection
  if (/[",\n]/.test(s)) s = '"' + s.replace(/"/g, '""') + '"';
  return s;
}
function downloadText(text, filename, type = 'text/csv') {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}
function exportCsv(rows, columns, filename) {
  const header = columns.map((c) => c.label).join(',');
  const body = rows.map((r) => columns.map((c) => csvEscape(r[c.key])).join(',')).join('\n');
  downloadText(header + '\n' + body, filename);
}

/* ---------------- Workspace switching ---------------- */
document.querySelectorAll('.ws-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.ws-btn').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    const isLive = btn.dataset.workspace === 'live';
    $('valuationView').style.display = isLive ? 'none' : '';
    $('liveView').style.display = isLive ? '' : 'none';
    $('valuationControls').style.display = isLive ? 'none' : '';
    $('liveControls').style.display = isLive ? '' : 'none';
  });
});

/* ---------------- Tabs ---------------- */
function wireTabs(barId, attr, panelPrefix) {
  document.querySelectorAll(`#${barId} .tab`).forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll(`#${barId} .tab`).forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      document.querySelectorAll(`[id^="${panelPrefix}"]`).forEach((p) => p.classList.remove('active'));
      $(panelPrefix + tab.dataset[attr]).classList.add('active');
    });
  });
}
wireTabs('tabBar', 'tab', 'panel-');
wireTabs('liveTabBar', 'livetab', 'live-');

/* ================= VALUATION WORKSPACE ================= */

async function runAnalysis(csvText) {
  state.lastCsvText = csvText;
  $('loadingState').style.display = '';
  $('loadingState').textContent = 'Validating data and evaluating held-out predictions\u2026';
  $('errorState').style.display = 'none';
  $('resultsWrap').style.display = 'none';
  try {
    const res = await fetch('/api/analyze', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ csv: csvText, strategy: $('strategySelect').value }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || 'Analysis failed.');
    state.rows = data.rows; state.metrics = data.metrics; state.warnings = data.warnings; state.model = data.model;
    $('loadingState').style.display = 'none';
    $('resultsWrap').style.display = '';
    initFiltersFromData();
    renderAll();
  } catch (err) {
    $('loadingState').style.display = 'none';
    $('errorState').style.display = '';
    $('errorState').textContent = err.message;
  }
}

function initFiltersFromData() {
  const seasons = [...new Set(state.rows.map((r) => r.season))].sort((a, b) => b - a);
  const seasonBox = $('seasonFilters');
  seasonBox.innerHTML = '';
  state.filters.seasons = new Set(seasons);
  seasons.forEach((s) => {
    const chip = document.createElement('button');
    chip.className = 'chip active'; chip.type = 'button'; chip.textContent = s;
    chip.addEventListener('click', () => {
      if (state.filters.seasons.has(s)) state.filters.seasons.delete(s); else state.filters.seasons.add(s);
      chip.classList.toggle('active');
      renderAll();
    });
    seasonBox.appendChild(chip);
  });

  const posBox = $('positionFilters');
  posBox.innerHTML = '';
  state.filters.positions = new Set(POSITIONS);
  POSITIONS.forEach((p) => {
    const chip = document.createElement('button');
    chip.className = 'chip active'; chip.type = 'button'; chip.textContent = p;
    chip.addEventListener('click', () => {
      if (state.filters.positions.has(p)) state.filters.positions.delete(p); else state.filters.positions.add(p);
      chip.classList.toggle('active');
      renderAll();
    });
    posBox.appendChild(chip);
  });

  const clubs = [...new Set(state.rows.map((r) => r.team))].sort();
  const clubSelect = $('clubFilter');
  clubSelect.innerHTML = '<option value="">All clubs</option>' + clubs.map((c) => `<option value="${c}">${c}</option>`).join('');
  state.filters.club = '';

  const scPosition = $('scPosition');
  scPosition.innerHTML = POSITIONS.map((p) => `<option value="${p}">${p}</option>`).join('');
}

function getFiltered() {
  const f = state.filters;
  const q = f.query.toLowerCase();
  return state.rows.filter((r) =>
    r.name.toLowerCase().includes(q) &&
    f.seasons.has(r.season) &&
    f.positions.has(r.position) &&
    r.appearances >= f.minApps &&
    (!f.club || r.team === f.club)
  );
}

function renderAll() {
  const demo = state.usingDemo;
  $('statusBadge').textContent = 'SCOUTING WORKSPACE / ' + (demo ? 'SYNTHETIC DEMO' : 'IMPORTED DATA \u00b7 SOURCE NOT VERIFIED');
  $('dataNotice').innerHTML = demo
    ? '<div class="notice warn">Demo mode: player names are real; statistics and market values are generated. These results do not describe today\u2019s Premier League.</div>'
    : '<div class="notice info">Imported values are source estimates, not objective fair prices. Predictions measure agreement with those estimates; source accuracy and freshness require verification.</div>';

  const filtered = getFiltered();
  renderKpis(filtered);
  renderOverview(filtered);
  renderTable(filtered);
  renderDossierOptions(filtered);
  renderCompareChips(filtered);
  renderDiagnostics();

  const playerCount = new Set(state.rows.map((r) => r.name)).size;
  $('sidebarStats').innerHTML = `${state.rows.length.toLocaleString()} rows \u00b7 ${playerCount.toLocaleString()} players`;
}

function renderKpis(filtered) {
  const m = state.metrics;
  const values = filtered.map((r) => r[TARGET]).sort((a, b) => a - b);
  const median = values.length ? values[Math.floor(values.length / 2)] : null;
  const improvement = m.baseline_mae_eur ? (1 - m.mae_eur / m.baseline_mae_eur) * 100 : null;
  $('kpiRow').innerHTML = [
    ['PLAYER-SEASONS IN VIEW', filtered.length.toLocaleString()],
    ['LISTED VALUE \u00b7 MEDIAN', money(median)],
    ['HELD-OUT ERROR \u00b7 MAE', money(m.mae_eur)],
    ['VS POSITION MEDIAN BASELINE', improvement === null ? '\u2014' : pct(improvement)],
  ].map(([label, value]) => `<div class="kpi"><div class="label">${label}</div><div class="value">${value}</div></div>`).join('');
}

function destroyChart(key) { if (state.charts[key]) { state.charts[key].destroy(); delete state.charts[key]; } }

function renderOverview(filtered) {
  const plotted = filtered.filter((r) => r.predicted_value_eur !== null && r.predicted_value_eur !== undefined);
  destroyChart('scatter');
  const scatterCtx = $('scatterChart').getContext('2d');
  if (!plotted.length) {
    state.charts.scatter = null;
  } else {
    const datasets = POSITIONS.filter((p) => plotted.some((r) => r.position === p)).map((p) => ({
      label: p,
      data: plotted.filter((r) => r.position === p).map((r) => ({ x: r[TARGET] / 1e6, y: r.predicted_value_eur / 1e6, name: r.name, season: r.season, team: r.team })),
      backgroundColor: COLORS[p],
      pointRadius: 5,
    }));
    const peak = Math.max(...plotted.map((r) => Math.max(r[TARGET], r.predicted_value_eur))) / 1e6 * 1.06;
    datasets.push({ label: 'Parity', type: 'line', data: [{ x: 0, y: 0 }, { x: peak, y: peak }], borderColor: '#62758c', borderDash: [5, 5], pointRadius: 0, borderWidth: 1.5 });
    state.charts.scatter = new Chart(scatterCtx, {
      type: 'scatter', data: { datasets },
      options: {
        plugins: { legend: { labels: { color: '#acbdd0' } }, tooltip: { callbacks: { label: (ctx) => ctx.raw.name ? `${ctx.raw.name} (${ctx.raw.season}, ${ctx.raw.team})` : 'Parity line' } } },
        scales: {
          x: { title: { display: true, text: 'Listed market value (\u20acm)', color: '#9aacc1' }, grid: { color: '#243043' }, ticks: { color: '#acbdd0' } },
          y: { title: { display: true, text: 'Held-out model estimate (\u20acm)', color: '#9aacc1' }, grid: { color: '#243043' }, ticks: { color: '#acbdd0' } },
        },
      },
    });
  }

  destroyChart('gap');
  const gapCtx = $('gapChart').getContext('2d');
  const top = [...plotted].sort((a, b) => Math.abs(b.gap_eur) - Math.abs(a.gap_eur)).slice(0, 10).sort((a, b) => a.gap_eur - b.gap_eur);
  state.charts.gap = new Chart(gapCtx, {
    type: 'bar',
    data: {
      labels: top.map((r) => `${r.name} \u00b7 ${r.season}`),
      datasets: [{ data: top.map((r) => r.gap_eur / 1e6), backgroundColor: top.map((r) => COLORS[r.position]) }],
    },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.raw >= 0 ? '+' : ''}${ctx.raw.toFixed(2)}m` } } },
      scales: {
        x: { title: { display: true, text: 'Estimate \u2212 listed value (\u20acm)', color: '#9aacc1' }, grid: { color: '#243043' }, ticks: { color: '#acbdd0' } },
        y: { grid: { display: false }, ticks: { color: '#acbdd0' } },
      },
    },
  });
}

function sortRows(rows, mode) {
  const copy = [...rows];
  if (mode === 'value_desc') copy.sort((a, b) => b[TARGET] - a[TARGET]);
  else if (mode === 'gap_pos') copy.sort((a, b) => (b.gap_eur ?? -Infinity) - (a.gap_eur ?? -Infinity));
  else if (mode === 'gap_neg') copy.sort((a, b) => (a.gap_eur ?? Infinity) - (b.gap_eur ?? Infinity));
  else if (mode === 'name') copy.sort((a, b) => a.name.localeCompare(b.name));
  return copy;
}

function renderTable(filtered) {
  const sorted = sortRows(filtered, $('sortSelect').value);
  const cols = [
    ['Name', 'name'], ['Team', 'team'], ['Position', 'position'], ['Season', 'season'], ['Age', 'age'],
    ['Apps', 'appearances'], ['Goals', 'goals'], ['Assists', 'assists'],
    ['Listed \u20ac', TARGET], ['Held-out estimate \u20ac', 'predicted_value_eur'], ['Gap %', 'gap_pct'],
  ];
  $('scoutTable').querySelector('thead').innerHTML = '<tr>' + cols.map((c) => `<th>${c[0]}</th>`).join('') + '</tr>';
  $('scoutTable').querySelector('tbody').innerHTML = sorted.map((r) => `<tr>
    <td>${r.name}</td><td>${r.team}</td><td>${r.position}</td><td>${r.season}</td><td>${r.age}</td>
    <td>${r.appearances}</td><td>${r.goals}</td><td>${r.assists}</td>
    <td>\u20ac${Math.round(r[TARGET]).toLocaleString()}</td>
    <td>${r.predicted_value_eur == null ? '\u2014' : '\u20ac' + Math.round(r.predicted_value_eur).toLocaleString()}</td>
    <td>${pct(r.gap_pct)}</td></tr>`).join('');
  $('exportTable').onclick = () => exportCsv(sorted, [
    { key: 'name', label: 'name' }, { key: 'team', label: 'team' }, { key: 'position', label: 'position' },
    { key: 'season', label: 'season' }, { key: 'age', label: 'age' }, { key: 'appearances', label: 'appearances' },
    { key: 'goals', label: 'goals' }, { key: 'assists', label: 'assists' }, { key: TARGET, label: TARGET },
    { key: 'predicted_value_eur', label: 'predicted_value_eur' }, { key: 'gap_pct', label: 'gap_pct' },
  ], 'scouting-analysis.csv');
}

function labelFor(r) { return `${r.name} \u00b7 ${r.season}/${String(r.season + 1).slice(-2)} \u00b7 ${r.team}`; }

function renderDossierOptions(filtered) {
  const select = $('dossierSelect');
  if (!filtered.length) {
    select.innerHTML = '';
    $('dossierBody').innerHTML = '<p class="hint">Broaden the sidebar filters to select a player.</p>';
    return;
  }
  select.innerHTML = filtered.map((r, i) => `<option value="${state.rows.indexOf(r)}">${labelFor(r)}</option>`).join('');
  select.onchange = () => renderDossier(Number(select.value));
  if (state.dossierIndex === null || !filtered.some((r) => state.rows.indexOf(r) === state.dossierIndex)) {
    state.dossierIndex = Number(select.value);
  }
  select.value = state.dossierIndex;
  renderDossier(state.dossierIndex);
}

function percentile(arr, value) {
  const below = arr.filter((v) => v < value).length;
  const equal = arr.filter((v) => v === value).length;
  return (100 * (below + 0.5 * equal)) / arr.length;
}

function renderDossier(idx) {
  state.dossierIndex = idx;
  const row = state.rows[idx];
  const body = $('dossierBody');
  const peers = state.rows.filter((r) => r.position === row.position && r.season === row.season);
  const features = ['goals', 'assists', 'appearances', 'age'];
  const values = features.map((f) => ({
    metric: f[0].toUpperCase() + f.slice(1),
    player: row[f],
    peerMedian: [...peers.map((p) => p[f])].sort((a, b) => a - b)[Math.floor(peers.length / 2)],
    percentile: percentile(peers.map((p) => p[f]), row[f]),
  }));
  const posWarning = ['Defender', 'Goalkeeper'].includes(row.position)
    ? '<div class="notice warn">This feature set lacks defensive and shot-stopping data. Treat this position\u2019s estimate with particular caution.</div>' : '';
  body.innerHTML = `
    <div class="dossier-header">${row.name}</div>
    <div class="dossier-sub">${row.team} \u00b7 ${row.position} \u00b7 ${row.age} years old \u00b7 ${row.appearances} appearances</div>
    <div class="dossier-metrics">
      <div class="kpi"><div class="label">LISTED VALUE</div><div class="value">${money(row[TARGET])}</div></div>
      <div class="kpi"><div class="label">HELD-OUT ESTIMATE</div><div class="value">${money(row.predicted_value_eur)}</div></div>
      <div class="kpi"><div class="label">MODEL GAP</div><div class="value">${pct(row.gap_pct)}</div></div>
    </div>
    <p class="hint">${row.predicted_value_eur == null ? 'This is an earliest-season training row. No forward prediction is available.' : `Prediction from validation fold ${row.fold}.`}</p>
    ${posWarning}
    <div class="panel-grid">
      <div><h4>Position &amp; season context</h4><canvas id="dossierChart" height="220"></canvas></div>
      <div><h4>Profile details</h4>
        <table><thead><tr><th>Metric</th><th>Player</th><th>Peer median</th><th>Percentile</th></tr></thead>
        <tbody>${values.map((v) => `<tr><td>${v.metric}</td><td>${v.player}</td><td>${v.peerMedian}</td><td>${v.percentile.toFixed(1)}</td></tr>`).join('')}</tbody></table>
        <p class="hint">Compared with ${peers.length} rows in the same position and season, including this player.</p>
      </div>
    </div>
    <button id="exportPlayer" class="btn-secondary">Export player report</button>`;
  destroyChart('dossier');
  state.charts.dossier = new Chart($('dossierChart').getContext('2d'), {
    type: 'bar',
    data: { labels: values.map((v) => v.metric), datasets: [{ data: values.map((v) => v.percentile), backgroundColor: '#6ee7b7' }] },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: { x: { min: 0, max: 100, grid: { color: '#243043' }, ticks: { color: '#acbdd0' } }, y: { grid: { display: false }, ticks: { color: '#acbdd0' } } },
    },
  });
  $('exportPlayer').onclick = () => exportCsv([row], Object.keys(row).map((k) => ({ key: k, label: k })), 'player-report.csv');
}

function renderCompareChips(filtered) {
  state.compareSelection = state.compareSelection.filter((i) => filtered.some((r) => state.rows.indexOf(r) === i));
  const box = $('compareChips');
  box.innerHTML = '';
  filtered.forEach((r) => {
    const idx = state.rows.indexOf(r);
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'chip' + (state.compareSelection.includes(idx) ? ' active' : '');
    chip.textContent = labelFor(r);
    chip.addEventListener('click', () => {
      if (state.compareSelection.includes(idx)) {
        state.compareSelection = state.compareSelection.filter((i) => i !== idx);
      } else if (state.compareSelection.length < 4) {
        state.compareSelection.push(idx);
      }
      renderCompareChips(getFiltered());
    });
    box.appendChild(chip);
  });
  renderCompareTable();
}

function renderCompareTable() {
  const table = $('compareTable');
  destroyChart('compare');
  if (!state.compareSelection.length) {
    table.innerHTML = '';
    return;
  }
  const rows = state.compareSelection.map((i) => state.rows[i]);
  const fields = [['Position', 'position'], ['Age', 'age'], ['Appearances', 'appearances'], ['Goals', 'goals'], ['Assists', 'assists'], ['Listed \u20ac', TARGET], ['Held-out estimate \u20ac', 'predicted_value_eur'], ['Gap %', 'gap_pct']];
  table.innerHTML = '<thead><tr><th></th>' + rows.map((r) => `<th>${labelFor(r)}</th>`).join('') + '</tr></thead><tbody>' +
    fields.map(([label, key]) => `<tr><td>${label}</td>` + rows.map((r) => `<td>${key === TARGET || key === 'predicted_value_eur' ? money(r[key]) : (key === 'gap_pct' ? pct(r[key]) : r[key])}</td>`).join('') + '</tr>').join('') + '</tbody>';
  state.charts.compare = new Chart($('compareChart').getContext('2d'), {
    type: 'bar',
    data: {
      labels: rows.map(labelFor),
      datasets: [
        { label: 'Listed', data: rows.map((r) => r[TARGET] / 1e6), backgroundColor: '#7ea9ff' },
        { label: 'Predicted', data: rows.map((r) => (r.predicted_value_eur ?? 0) / 1e6), backgroundColor: '#6ee7b7' },
      ],
    },
    options: { plugins: { legend: { labels: { color: '#acbdd0' } } }, scales: { x: { ticks: { color: '#acbdd0' } }, y: { title: { display: true, text: '\u20acm', color: '#9aacc1' }, grid: { color: '#243043' }, ticks: { color: '#acbdd0' } } } },
  });
}

function renderDiagnostics() {
  const m = state.metrics;
  $('diagKpis').innerHTML = [
    ['HELD-OUT RMSE', money(m.rmse_eur)],
    ['HELD-OUT R\u00b2', m.r2 === null ? 'Undefined' : m.r2.toFixed(3)],
    ['EVALUATED ROWS', `${m.n_test} / ${state.rows.length}`],
  ].map(([label, value]) => `<div class="kpi"><div class="label">${label}</div><div class="value">${value}</div></div>`).join('');

  const improvement = m.baseline_mae_eur ? (1 - m.mae_eur / m.baseline_mae_eur) * 100 : null;
  const notices = [];
  if (improvement !== null && improvement <= 0) notices.push('<div class="notice warn">The model does not outperform the simple position-median baseline on these validation splits.</div>');
  state.warnings.forEach((w) => notices.push(`<div class="notice warn">${w}</div>`));
  notices.push($('strategySelect').value === 'Player-held-out'
    ? '<div class="notice info">All seasons of each tested player stay outside that fold\u2019s training data. This estimates generalization to unseen players, not forecasting future seasons.</div>'
    : '<div class="notice info">Each season is tested using only earlier seasons. The earliest season is training-only.</div>');
  $('diagWarnings').innerHTML = notices.join('');

  destroyChart('posError');
  const evaluated = state.rows.filter((r) => r.predicted_value_eur !== null && r.predicted_value_eur !== undefined);
  const grouped = POSITIONS.map((p) => {
    const rows = evaluated.filter((r) => r.position === p);
    return { p, mae: rows.length ? rows.reduce((a, r) => a + r.absolute_error_eur, 0) / rows.length : 0, n: rows.length };
  }).filter((g) => g.n > 0);
  state.charts.posError = new Chart($('positionErrorChart').getContext('2d'), {
    type: 'bar',
    data: { labels: grouped.map((g) => g.p), datasets: [{ data: grouped.map((g) => g.mae / 1e6), backgroundColor: grouped.map((g) => COLORS[g.p]) }] },
    options: { plugins: { legend: { display: false } }, scales: { x: { ticks: { color: '#acbdd0' } }, y: { title: { display: true, text: 'Held-out MAE (\u20acm)', color: '#9aacc1' }, grid: { color: '#243043' }, ticks: { color: '#acbdd0' } } } },
  });

  $('foldsTable').innerHTML = '<thead><tr><th>Fold</th><th>Train rows</th><th>Test rows</th><th>MAE \u20ac</th></tr></thead><tbody>' +
    m.folds.map((f) => `<tr><td>${f.fold}</td><td>${f.train_rows}</td><td>${f.test_rows}</td><td>\u20ac${Math.round(f.mae_eur).toLocaleString()}</td></tr>`).join('') + '</tbody>';

  $('downloadSummary').onclick = () => downloadText(JSON.stringify(m, null, 2), 'evaluation-summary.json', 'application/json');
  $('downloadAll').onclick = () => exportCsv(state.rows, Object.keys(state.rows[0]).map((k) => ({ key: k, label: k })), 'held-out-predictions.csv');
  $('downloadTemplate').onclick = () => downloadText('player_id,name,position,team,season,age,appearances,goals,assists,transfer_value_eur,stats_as_of,valuation_date,value_source,data_kind\n', 'player-season-template.csv');
}

/* ---- Scenario lab (pure client-side, uses exported model coefficients) ---- */
function bindSlider(inputId, outId) { $(inputId).addEventListener('input', () => { $(outId).textContent = $(inputId).value; }); }
bindSlider('scAge', 'scAgeVal'); bindSlider('scApps', 'scAppsVal'); bindSlider('scGoals', 'scGoalsVal'); bindSlider('scAssists', 'scAssistsVal');

$('scenarioForm').addEventListener('submit', (e) => {
  e.preventDefault();
  const position = $('scPosition').value;
  const values = { age: Number($('scAge').value), appearances: Number($('scApps').value), goals: Number($('scGoals').value), assists: Number($('scAssists').value) };
  const listed = Number($('scListed').value) * 1e6;
  const result = $('scenarioResult');
  if (values.appearances === 0 && (values.goals || values.assists)) {
    result.innerHTML = '<div class="notice error">A player with zero appearances cannot have goals or assists.</div>';
    return;
  }
  const model = state.model;
  let predicted = model.intercept + (model.position[position] ?? 0);
  Object.entries(values).forEach(([feat, val]) => {
    const info = model.numeric[feat];
    if (info) predicted += info.coef * ((val - info.mean) / info.std);
  });
  predicted = Math.max(0, predicted);
  const peers = state.rows.filter((r) => r.position === position);
  const outside = Object.keys(values).filter((feat) => {
    const vals = peers.map((p) => p[feat]);
    return values[feat] < Math.min(...vals) || values[feat] > Math.max(...vals);
  });
  result.innerHTML = `
    <div class="kpi-row">
      <div class="kpi"><div class="label">SCENARIO ESTIMATE</div><div class="value">${money(predicted)}</div></div>
      <div class="kpi"><div class="label">VS YOUR COMPARISON VALUE</div><div class="value">${money(predicted - listed)}</div></div>
    </div>
    ${outside.length ? `<div class="notice warn">Outside observed same-position ranges: ${outside.join(', ')}. Extrapolation is unreliable.</div>` : ''}
    <p class="hint">No calibrated confidence interval is available. Average validation error is not an individual prediction interval.</p>`;
});

/* ---- Search / filter controls ---- */
$('searchInput').addEventListener('input', (e) => { state.filters.query = e.target.value; renderAll(); });
$('clubFilter').addEventListener('change', (e) => { state.filters.club = e.target.value; renderAll(); });
$('minAppsSlider').addEventListener('input', (e) => { state.filters.minApps = Number(e.target.value); $('minAppsValue').textContent = e.target.value; renderAll(); });
$('sortSelect').addEventListener('change', () => renderTable(getFiltered()));
$('strategySelect').addEventListener('change', () => { if (state.lastCsvText) runAnalysis(state.lastCsvText); });
$('runAnalysis').addEventListener('click', () => { if (state.lastCsvText) runAnalysis(state.lastCsvText); });

$('datasetSource').addEventListener('change', (e) => {
  if (e.target.value === 'upload') {
    $('csvUpload').style.display = '';
    $('csvUpload').click();
  } else {
    $('csvUpload').style.display = 'none';
    state.usingDemo = true;
    loadDemo();
  }
});
$('csvUpload').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => { state.usingDemo = false; runAnalysis(reader.result); };
  reader.readAsText(file);
});

function loadDemo() {
  fetch('data/sample_dataset.csv').then((r) => r.text()).then((text) => { state.usingDemo = true; runAnalysis(text); });
}

/* ================= LIVE FOOTBALL WORKSPACE ================= */

$('matchWindow').addEventListener('change', (e) => {
  const custom = e.target.value === 'custom';
  $('customStartWrap').style.display = custom ? '' : 'none';
  $('customEndWrap').style.display = custom ? '' : 'none';
});

function isoDate(d) { return d.toISOString().slice(0, 10); }

let lastMatches = [];
$('loadMatches').addEventListener('click', async () => {
  const today = new Date();
  let start, end;
  const mode = $('matchWindow').value;
  if (mode === 'past') { end = today; start = new Date(today); start.setDate(start.getDate() - 6); }
  else if (mode === 'next') { start = new Date(today); start.setDate(start.getDate() + 1); end = new Date(today); end.setDate(end.getDate() + 7); }
  else { start = new Date($('customStart').value); end = new Date($('customEnd').value); }
  if (!start.getTime() || !end.getTime()) { $('matchesResult').innerHTML = '<div class="notice warn">Select both a start and end date.</div>'; return; }
  $('matchesResult').innerHTML = '<div class="loading">Contacting football-data.org\u2026</div>';
  try {
    const res = await fetch(`/api/live?action=matches&start=${isoDate(start)}&end=${isoDate(end)}`);
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || 'Failed to load matches.');
    lastMatches = data.rows;
    const clubs = [...new Set(lastMatches.flatMap((m) => [m.home, m.away]))].sort();
    $('matchClubFilter').innerHTML = '<option>All clubs</option>' + clubs.map((c) => `<option>${c}</option>`).join('');
    renderMatches();
  } catch (err) {
    $('matchesResult').innerHTML = `<div class="notice error">${err.message}</div>`;
  }
});
$('matchClubFilter').addEventListener('change', renderMatches);
$('matchStatusFilter').addEventListener('change', renderMatches);

function renderMatches() {
  const club = $('matchClubFilter').value;
  const status = $('matchStatusFilter').value;
  const statusSets = {
    Finished: ['FINISHED', 'AWARDED'], Upcoming: ['SCHEDULED', 'TIMED'],
    'In progress': ['IN_PLAY', 'PAUSED', 'EXTRA_TIME', 'PENALTY_SHOOTOUT'],
    'Postponed / cancelled': ['POSTPONED', 'CANCELLED', 'SUSPENDED'],
  };
  const visible = lastMatches.filter((m) =>
    (club === 'All clubs' || m.home === club || m.away === club) &&
    (status === 'All statuses' || (statusSets[status] || []).includes(m.status))
  );
  if (!visible.length) { $('matchesResult').innerHTML = '<p class="hint">No matches in this range match the filters.</p>'; return; }
  $('matchesResult').innerHTML = `<div class="kpi-row"><div class="kpi"><div class="label">MATCHES IN VIEW</div><div class="value">${visible.length}</div></div>
    <div class="kpi"><div class="label">FINISHED</div><div class="value">${visible.filter((m) => m.status === 'FINISHED').length}</div></div></div>` +
    visible.map((m) => `<div class="match-card">
      <div class="match-row"><strong>${m.home}</strong><span class="score">${m.score}</span><strong>${m.away}</strong></div>
      <div class="match-meta">${new Date(m.utc_date).toUTCString().slice(0, 22)} UTC \u00b7 ${(m.status || '').replace('_', ' ')} \u00b7 Matchday ${m.matchday ?? '\u2014'}</div>
    </div>`).join('');
}

$('loadScorers').addEventListener('click', async () => {
  $('scorersResult').innerHTML = '<div class="loading">Contacting football-data.org\u2026</div>';
  try {
    const res = await fetch('/api/live?action=scorers');
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || 'Failed to load scorers.');
    window._scorers = data.rows;
    renderScorers();
  } catch (err) {
    $('scorersResult').innerHTML = `<div class="notice error">${err.message}</div>`;
  }
});
$('scorerSearch').addEventListener('input', renderScorers);
function renderScorers() {
  const rows = (window._scorers || []).filter((r) => r.name.toLowerCase().includes($('scorerSearch').value.toLowerCase()));
  if (!rows.length) { $('scorersResult').innerHTML = '<p class="hint">Load the latest available scorer data from your API account.</p>'; return; }
  $('scorersResult').innerHTML = `<div class="table-scroll"><table><thead><tr><th>Name</th><th>Team</th><th>Season</th><th>Position</th><th>Goals</th><th>Assists</th><th>Apps</th></tr></thead>
    <tbody>${rows.map((r) => `<tr><td>${r.name}</td><td>${r.team}</td><td>${r.season}</td><td>${r.position}</td><td>${r.goals ?? '\u2014'}</td><td>${r.assists ?? '\u2014'}</td><td>${r.appearances ?? '\u2014'}</td></tr>`).join('')}</tbody></table></div>`;
}

$('testConnection').addEventListener('click', async () => {
  $('testResult').innerHTML = '<div class="loading">Contacting football-data.org\u2026</div>';
  try {
    const res = await fetch('/api/live?action=test');
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || 'Connection failed.');
    $('testResult').innerHTML = `<div class="notice info">Connected to ${data.name}. Provider season: ${data.season_start ?? 'unknown'} to ${data.season_end ?? 'unknown'}.</div>`;
  } catch (err) {
    $('testResult').innerHTML = `<div class="notice error">${err.message}</div>`;
  }
});

/* ---------------- Boot ---------------- */
loadDemo();
