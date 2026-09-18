/* Touchline web dashboard — talks to /api/analyze and /api/live (Vercel Python functions).
   Obsidian HUD theme: emerald + cyan + gold. */
'use strict';

const COLORS = { Attacker: '#34d399', Midfielder: '#22d3ee', Defender: '#fbbf24', Goalkeeper: '#a78bfa' };
const POSITIONS = ['Attacker', 'Midfielder', 'Defender', 'Goalkeeper'];
const TARGET = 'transfer_value_eur';

/* Shared chart styling for the dark HUD */
const CHART_GRID = '#161f2c';
const CHART_TICK = '#8493a8';
const CHART_AXIS = '#7f8da3';
Chart.defaults.color = CHART_TICK;
Chart.defaults.font.family = "'JetBrains Mono', ui-monospace, monospace";
Chart.defaults.font.size = 11;

const state = {
  rows: [], metrics: null, warnings: [], model: null, usingDemo: true, lastCsvText: null,
  filters: { query: '', seasons: new Set(), positions: new Set(POSITIONS), club: '', minApps: 0 },
  charts: {}, dossierIndex: null, compareSelection: [],
};

const $ = (id) => document.getElementById(id);
const money = (v) => (v === null || v === undefined || Number.isNaN(v)) ? '\u2014' : `\u20ac${(v / 1e6).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}m`;
const pct = (v) => (v === null || v === undefined || Number.isNaN(v)) ? '\u2014' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* ================= CLUB IDENTITY ================= */
/* Stylized deterministic crests built from each club's authentic colours + monogram.
   These are generated badges (not official trademarked crests), so they stay self-contained,
   render instantly, and require no external image hosting. */
const CLUBS = {
  'Arsenal': ['ARS', '#EF0107', '#FFFFFF'],
  'Aston Villa': ['AVL', '#95BFE5', '#670E36'],
  'Bournemouth': ['BOU', '#DA291C', '#000000'],
  'AFC Bournemouth': ['BOU', '#DA291C', '#000000'],
  'Brentford': ['BRE', '#E30613', '#FBB800'],
  'Brighton & Hove Albion': ['BHA', '#0057B8', '#FFCD00'],
  'Brighton and Hove Albion': ['BHA', '#0057B8', '#FFCD00'],
  'Brighton': ['BHA', '#0057B8', '#FFCD00'],
  'Burnley': ['BUR', '#6C1D45', '#99D6EA'],
  'Chelsea': ['CHE', '#034694', '#FFFFFF'],
  'Crystal Palace': ['CRY', '#1B458F', '#C4122E'],
  'Everton': ['EVE', '#003399', '#FFFFFF'],
  'Fulham': ['FUL', '#000000', '#FFFFFF'],
  'Ipswich Town': ['IPS', '#3A64A3', '#DE2C37'],
  'Leeds United': ['LEE', '#FFCD00', '#1D428A'],
  'Leicester City': ['LEI', '#003090', '#FDBE11'],
  'Liverpool': ['LIV', '#C8102E', '#00B2A9'],
  'Luton Town': ['LUT', '#F78F1E', '#002D62'],
  'Manchester City': ['MCI', '#6CABDD', '#1C2C5B'],
  'Manchester United': ['MUN', '#DA291C', '#FBE122'],
  'Newcastle United': ['NEW', '#241F20', '#FFFFFF'],
  'Nottingham Forest': ['NFO', '#DD0000', '#FFFFFF'],
  'Sheffield United': ['SHU', '#EE2737', '#000000'],
  'Southampton': ['SOU', '#D71920', '#FFFFFF'],
  'Tottenham Hotspur': ['TOT', '#132257', '#FFFFFF'],
  'West Ham United': ['WHU', '#7A263A', '#1BB1E7'],
  'Wolverhampton Wanderers': ['WOL', '#FDB913', '#231F20'],
  'Wolves': ['WOL', '#FDB913', '#231F20'],
};
const IDENTITY_FALLBACK = ['#34d399', '#22d3ee', '#fbbf24', '#a78bfa', '#fb7185', '#60a5fa', '#f97316', '#4ade80'];

function hashStr(s) { let h = 0; for (let i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) | 0; } return Math.abs(h); }

function clubIdentity(team) {
  const known = CLUBS[team];
  if (known) return { code: known[0], primary: known[1], secondary: known[2] };
  const words = String(team || '?').replace(/[^A-Za-z ]/g, '').trim().split(/\s+/);
  const code = (words.length >= 2 ? words[0][0] + words[1][0] + (words[1][1] || words[0][1] || '') : (team || '??').slice(0, 3)).toUpperCase();
  const h = hashStr(team || 'x');
  return { code, primary: IDENTITY_FALLBACK[h % IDENTITY_FALLBACK.length], secondary: IDENTITY_FALLBACK[(h >> 3) % IDENTITY_FALLBACK.length] };
}

function crestSVG(team, size = 30) {
  const { code, primary, secondary } = clubIdentity(team);
  const id = 'g' + hashStr(team + primary);
  return `<svg class="crest" width="${size}" height="${size}" viewBox="0 0 40 44" role="img" aria-label="${esc(team)} badge">
    <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${primary}"/><stop offset="1" stop-color="${primary}" stop-opacity="0.72"/>
    </linearGradient></defs>
    <path d="M4 4 H36 V23 C36 33 28.5 39.5 20 42 C11.5 39.5 4 33 4 23 Z" fill="url(#${id})" stroke="${secondary}" stroke-width="2" stroke-linejoin="round"/>
    <path d="M4 15 H36" stroke="${secondary}" stroke-width="1.4" opacity="0.55"/>
    <text x="20" y="14" text-anchor="middle" font-family="'JetBrains Mono',monospace" font-size="8.5" font-weight="700" fill="${secondary}">${esc(code)}</text>
  </svg>`;
}

function avatarSVG(name, position, size = 34) {
  const initials = String(name || '?').split(/\s+/).map((w) => w[0]).filter(Boolean).slice(0, 2).join('').toUpperCase();
  const c = COLORS[position] || '#34d399';
  const id = 'a' + hashStr(name + position);
  return `<svg class="avatar" width="${size}" height="${size}" viewBox="0 0 40 40" role="img" aria-label="${esc(name)}">
    <defs><linearGradient id="${id}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="${c}" stop-opacity="0.9"/><stop offset="1" stop-color="${c}" stop-opacity="0.4"/>
    </linearGradient></defs>
    <rect width="40" height="40" rx="10" fill="#0b0f17" stroke="${c}" stroke-width="1.3"/>
    <rect width="40" height="40" rx="10" fill="url(#${id})" opacity="0.22"/>
    <text x="20" y="25" text-anchor="middle" font-family="'JetBrains Mono',monospace" font-size="13" font-weight="600" fill="${c}">${esc(initials)}</text>
  </svg>`;
}

function idCell(row) {
  return `<div class="id-cell">${crestSVG(row.team, 28)}
    <div class="id-text"><span class="id-name">${esc(row.name)}</span>
    <span class="id-meta">${esc(row.team)} · ${row.season}</span></div></div>`;
}

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
  $('loadingState').textContent = 'Validating data and evaluating held-out predictions';
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
    chip.style.setProperty('--chip', COLORS[p]);
    chip.addEventListener('click', () => {
      if (state.filters.positions.has(p)) state.filters.positions.delete(p); else state.filters.positions.add(p);
      chip.classList.toggle('active');
      renderAll();
    });
    posBox.appendChild(chip);
  });

  const clubs = [...new Set(state.rows.map((r) => r.team))].sort();
  const clubSelect = $('clubFilter');
  clubSelect.innerHTML = '<option value="">All clubs</option>' + clubs.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join('');
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
      pointHoverRadius: 7,
    }));
    const peak = Math.max(...plotted.map((r) => Math.max(r[TARGET], r.predicted_value_eur))) / 1e6 * 1.06;
    datasets.push({ label: 'Parity', type: 'line', data: [{ x: 0, y: 0 }, { x: peak, y: peak }], borderColor: '#4b5c72', borderDash: [5, 5], pointRadius: 0, borderWidth: 1.5 });
    state.charts.scatter = new Chart(scatterCtx, {
      type: 'scatter', data: { datasets },
      options: {
        plugins: { legend: { labels: { color: '#c2cddb', usePointStyle: true } }, tooltip: { callbacks: { label: (ctx) => ctx.raw.name ? `${ctx.raw.name} (${ctx.raw.season}, ${ctx.raw.team})` : 'Parity line' } } },
        scales: {
          x: { title: { display: true, text: 'Listed market value (\u20acm)', color: CHART_AXIS }, grid: { color: CHART_GRID }, ticks: { color: CHART_TICK } },
          y: { title: { display: true, text: 'Held-out model estimate (\u20acm)', color: CHART_AXIS }, grid: { color: CHART_GRID }, ticks: { color: CHART_TICK } },
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
      datasets: [{ data: top.map((r) => r.gap_eur / 1e6), backgroundColor: top.map((r) => COLORS[r.position]), borderRadius: 4 }],
    },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.raw >= 0 ? '+' : ''}${ctx.raw.toFixed(2)}m` } } },
      scales: {
        x: { title: { display: true, text: 'Estimate \u2212 listed value (\u20acm)', color: CHART_AXIS }, grid: { color: CHART_GRID }, ticks: { color: CHART_TICK } },
        y: { grid: { display: false }, ticks: { color: CHART_TICK } },
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
  const cols = ['Player', 'Position', 'Age', 'Apps', 'Goals', 'Assists', 'Listed \u20ac', 'Held-out estimate \u20ac', 'Gap %'];
  $('scoutTable').querySelector('thead').innerHTML = '<tr>' + cols.map((c) => `<th>${c}</th>`).join('') + '</tr>';
  $('scoutTable').querySelector('tbody').innerHTML = sorted.map((r) => {
    const gapCls = r.gap_pct == null ? '' : (r.gap_pct >= 0 ? 'pos-pos' : 'pos-neg');
    return `<tr>
    <td>${idCell(r)}</td>
    <td><span class="pos-tag" style="color:${COLORS[r.position]}">${r.position}</span></td>
    <td class="num">${r.age}</td><td class="num">${r.appearances}</td><td class="num">${r.goals}</td><td class="num">${r.assists}</td>
    <td class="num">\u20ac${Math.round(r[TARGET]).toLocaleString()}</td>
    <td class="num">${r.predicted_value_eur == null ? '\u2014' : '\u20ac' + Math.round(r.predicted_value_eur).toLocaleString()}</td>
    <td class="num ${gapCls}">${pct(r.gap_pct)}</td></tr>`;
  }).join('');
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
  select.innerHTML = filtered.map((r) => `<option value="${state.rows.indexOf(r)}">${esc(labelFor(r))}</option>`).join('');
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
    <div class="dossier-id">
      ${crestSVG(row.team, 52)}${avatarSVG(row.name, row.position, 52)}
      <div><div class="dossier-header">${esc(row.name)}</div>
      <div class="dossier-sub">${esc(row.team)} \u00b7 <span style="color:${COLORS[row.position]}">${row.position}</span> \u00b7 ${row.age} yrs \u00b7 ${row.appearances} apps</div></div>
    </div>
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
        <tbody>${values.map((v) => `<tr><td>${v.metric}</td><td class="num">${v.player}</td><td class="num">${v.peerMedian}</td><td class="num">${v.percentile.toFixed(1)}</td></tr>`).join('')}</tbody></table>
        <p class="hint">Compared with ${peers.length} rows in the same position and season, including this player.</p>
      </div>
    </div>
    <button id="exportPlayer" class="btn-secondary">Export player report</button>`;
  destroyChart('dossier');
  state.charts.dossier = new Chart($('dossierChart').getContext('2d'), {
    type: 'bar',
    data: { labels: values.map((v) => v.metric), datasets: [{ data: values.map((v) => v.percentile), backgroundColor: COLORS[row.position], borderRadius: 4 }] },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: { x: { min: 0, max: 100, grid: { color: CHART_GRID }, ticks: { color: CHART_TICK } }, y: { grid: { display: false }, ticks: { color: CHART_TICK } } },
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
  table.innerHTML = '<thead><tr><th></th>' + rows.map((r) => `<th>${idCell(r)}</th>`).join('') + '</tr></thead><tbody>' +
    fields.map(([label, key]) => `<tr><td>${label}</td>` + rows.map((r) => `<td class="num">${key === TARGET || key === 'predicted_value_eur' ? money(r[key]) : (key === 'gap_pct' ? pct(r[key]) : r[key])}</td>`).join('') + '</tr>').join('') + '</tbody>';
  state.charts.compare = new Chart($('compareChart').getContext('2d'), {
    type: 'bar',
    data: {
      labels: rows.map(labelFor),
      datasets: [
        { label: 'Listed', data: rows.map((r) => r[TARGET] / 1e6), backgroundColor: '#22d3ee', borderRadius: 4 },
        { label: 'Predicted', data: rows.map((r) => (r.predicted_value_eur ?? 0) / 1e6), backgroundColor: '#34d399', borderRadius: 4 },
      ],
    },
    options: { plugins: { legend: { labels: { color: '#c2cddb', usePointStyle: true } } }, scales: { x: { ticks: { color: CHART_TICK } }, y: { title: { display: true, text: '\u20acm', color: CHART_AXIS }, grid: { color: CHART_GRID }, ticks: { color: CHART_TICK } } } },
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
  state.warnings.forEach((w) => notices.push(`<div class="notice warn">${esc(w)}</div>`));
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
    data: { labels: grouped.map((g) => g.p), datasets: [{ data: grouped.map((g) => g.mae / 1e6), backgroundColor: grouped.map((g) => COLORS[g.p]), borderRadius: 4 }] },
    options: { plugins: { legend: { display: false } }, scales: { x: { ticks: { color: CHART_TICK } }, y: { title: { display: true, text: 'Held-out MAE (\u20acm)', color: CHART_AXIS }, grid: { color: CHART_GRID }, ticks: { color: CHART_TICK } } } },
  });

  $('foldsTable').innerHTML = '<thead><tr><th>Fold</th><th>Train rows</th><th>Test rows</th><th>MAE \u20ac</th></tr></thead><tbody>' +
    m.folds.map((f) => `<tr><td>${f.fold}</td><td class="num">${f.train_rows}</td><td class="num">${f.test_rows}</td><td class="num">\u20ac${Math.round(f.mae_eur).toLocaleString()}</td></tr>`).join('') + '</tbody>';

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
  $('matchesResult').innerHTML = '<div class="loading">Contacting football-data.org</div>';
  try {
    const res = await fetch(`/api/live?action=matches&start=${isoDate(start)}&end=${isoDate(end)}`);
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || 'Failed to load matches.');
    lastMatches = data.rows;
    const clubs = [...new Set(lastMatches.flatMap((m) => [m.home, m.away]))].sort();
    $('matchClubFilter').innerHTML = '<option>All clubs</option>' + clubs.map((c) => `<option>${esc(c)}</option>`).join('');
    renderMatches();
  } catch (err) {
    $('matchesResult').innerHTML = `<div class="notice error">${esc(err.message)}</div>`;
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
      <div class="match-row">
        <div class="match-side">${crestSVG(m.home, 30)}<strong>${esc(m.home)}</strong></div>
        <span class="score">${esc(m.score)}</span>
        <div class="match-side away">${crestSVG(m.away, 30)}<strong>${esc(m.away)}</strong></div>
      </div>
      <div class="match-meta">${new Date(m.utc_date).toUTCString().slice(0, 22)} UTC \u00b7 ${(m.status || '').replace('_', ' ')} \u00b7 Matchday ${m.matchday ?? '\u2014'}</div>
    </div>`).join('');
}

$('loadScorers').addEventListener('click', async () => {
  $('scorersResult').innerHTML = '<div class="loading">Contacting football-data.org</div>';
  try {
    const res = await fetch('/api/live?action=scorers');
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || 'Failed to load scorers.');
    window._scorers = data.rows;
    renderScorers();
  } catch (err) {
    $('scorersResult').innerHTML = `<div class="notice error">${esc(err.message)}</div>`;
  }
});
$('scorerSearch').addEventListener('input', renderScorers);
function renderScorers() {
  const rows = (window._scorers || []).filter((r) => r.name.toLowerCase().includes($('scorerSearch').value.toLowerCase()));
  if (!rows.length) { $('scorersResult').innerHTML = '<p class="hint">Load the latest available scorer data from your API account.</p>'; return; }
  $('scorersResult').innerHTML = `<div class="table-scroll"><table><thead><tr><th>Name</th><th>Team</th><th>Season</th><th>Position</th><th>Goals</th><th>Assists</th><th>Apps</th></tr></thead>
    <tbody>${rows.map((r) => `<tr><td>${esc(r.name)}</td><td><div class="id-cell">${crestSVG(r.team, 24)}<span>${esc(r.team)}</span></div></td><td>${r.season}</td><td>${esc(r.position)}</td><td class="num">${r.goals ?? '\u2014'}</td><td class="num">${r.assists ?? '\u2014'}</td><td class="num">${r.appearances ?? '\u2014'}</td></tr>`).join('')}</tbody></table></div>`;
}

$('testConnection').addEventListener('click', async () => {
  $('testResult').innerHTML = '<div class="loading">Contacting football-data.org</div>';
  try {
    const res = await fetch('/api/live?action=test');
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || 'Connection failed.');
    $('testResult').innerHTML = `<div class="notice info">Connected to ${esc(data.name)}. Provider season: ${data.season_start ?? 'unknown'} to ${data.season_end ?? 'unknown'}.</div>`;
  } catch (err) {
    $('testResult').innerHTML = `<div class="notice error">${esc(err.message)}</div>`;
  }
});

/* ---------------- Boot ---------------- */
loadDemo();
