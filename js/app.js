(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const F = window.Charts.fmt;
  const esc = s => String(s === undefined || s === null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const COL = { h2: '#4dd8ff', fc: '#5cff9d', bat: '#ffc24d', bus: '#c79bff', shaft: '#ff7a45', red: '#ff5d73', mu: '#8e9bc4' };
  const MASS_COL = ['#5b6b99', '#c79bff', '#ffc24d', '#5cff9d', '#2f9fd6', '#4dd8ff', '#ff7a45', '#ff9fd0', '#7ce0c3'];
  const SEG_COL = { taxi: 'rgba(140,150,190,.07)', takeoff: 'rgba(255,122,69,.10)', climb: 'rgba(92,255,157,.07)', cruise: 'rgba(77,216,255,.05)', descent: 'rgba(199,155,255,.08)', reserve: 'rgba(255,194,77,.08)', landing: 'rgba(140,150,190,.07)' };
  let worker, rid = 0; const pending = new Map();
  let presets = [], schema = null, cfg = null, last = null, sized = null, timer = null, view3d = false, runSeq = 0;
  const cache = {};

  function call(fn, ...args) {
    return new Promise((res, rej) => { const id = ++rid; pending.set(id, { res, rej }); worker.postMessage({ id, fn, args }); });
  }
  function busy(on, txt) { $('busy').style.display = on ? 'block' : 'none'; if (txt) $('busyTxt').textContent = txt; }
  const get = (o, p) => p.split('.').reduce((a, k) => (a === undefined || a === null ? undefined : a[k]), o);
  const set = (o, p, v) => { const ks = p.split('.'); let a = o; ks.slice(0, -1).forEach(k => { if (a[k] === undefined) a[k] = {}; a = a[k]; }); a[ks[ks.length - 1]] = v; };

  async function boot() {
    worker = new Worker('js/worker.js');
    worker.onmessage = e => {
      const m = e.data;
      if (m.type === 'progress') { $('bootTxt').textContent = m.text; return; }
      const p = pending.get(m.id); if (!p) return; pending.delete(m.id);
      m.ok ? p.res(m.data) : p.rej(new Error(m.error));
    };
    const base = location.href.replace(/[^/]*$/, '');
    const ver = await new Promise((res, rej) => { const id = ++rid; pending.set(id, { res, rej }); worker.postMessage({ id, fn: 'boot', base }); });
    presets = await call('presets');
    schema = await call('schema');
    $('preset').innerHTML = presets.map(p => '<option value="' + p.id + '">' + esc(p.name) + '</option>').join('');
    $('preset').addEventListener('change', () => loadPreset($('preset').value));
    document.querySelectorAll('#arch button').forEach(b => b.addEventListener('click', () => { cfg.architecture = b.dataset.a; syncArch(); renderForm(); schedule(); }));
    document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => openTab(t.dataset.t)));
    $('btnExport').addEventListener('click', () => download('h2volt_config.json', JSON.stringify(cfg, null, 1), 'application/json'));
    $('btnImport').addEventListener('click', () => $('fileIn').click());
    $('fileIn').addEventListener('change', e => { const f = e.target.files[0]; if (!f) return; const r = new FileReader(); r.onload = () => { try { cfg = JSON.parse(r.result); syncArch(); renderForm(); schedule(0); } catch (err) { alert('Invalid file: ' + err.message); } }; r.readAsText(f); e.target.value = ''; });
    $('tRun').addEventListener('click', runTrade);
    $('tPath').addEventListener('change', tradeDefaults);
    $('sRun').addEventListener('click', runSize);
    $('sApply').addEventListener('click', () => { if (!sized) return; cfg = JSON.parse(JSON.stringify(sized.config)); renderForm(); schedule(0); $('sApply').disabled = true; });
    $('vRun').addEventListener('click', runValidation);
    renderAbout(ver.version);
    $('boot').style.display = 'none';
    loadPreset(presets[0].id);
  }

  function loadPreset(id) {
    const p = presets.find(x => x.id === id);
    cfg = JSON.parse(JSON.stringify(p.config));
    $('pdesc').textContent = p.description;
    syncArch(); renderForm(); schedule(0);
  }
  function syncArch() { document.querySelectorAll('#arch button').forEach(b => b.classList.toggle('on', b.dataset.a === cfg.architecture)); }

  function renderForm() {
    const arch = cfg.architecture;
    $('form').innerHTML = schema.groups.filter(g => !g.arch || g.arch.includes(arch)).map(g => '<div class="grp" data-g="' + g.id + '"><h3>' + esc(g.label) + '<span>▾</span></h3><div class="body">' + g.fields.map(f => {
      const v = get(cfg, f.path);
      const inp = f.type === 'select' ? '<select data-p="' + f.path + '">' + f.options.map(o => '<option value="' + o[0] + '"' + (o[0] === v ? ' selected' : '') + '>' + esc(o[1]) + '</option>').join('') + '</select>' : '<input type="number" step="' + (f.step || 'any') + '" data-p="' + f.path + '" value="' + (v === undefined || v === null ? '' : v) + '">';
      return '<div class="fld"><label>' + esc(f.label) + '</label>' + inp + '<span class="u">' + esc(f.unit || '') + '</span></div>';
    }).join('') + '</div></div>').join('');
    $('form').querySelectorAll('.grp h3').forEach(h => h.addEventListener('click', () => h.parentElement.classList.toggle('closed')));
    $('form').querySelectorAll('[data-p]').forEach(el => el.addEventListener('change', () => { const v = el.tagName === 'SELECT' ? el.value : Number(el.value); if (el.tagName !== 'SELECT' && !Number.isFinite(v)) return; set(cfg, el.dataset.p, v); schedule(); }));
    tradeOptions();
  }

  function schedule(ms) { clearTimeout(timer); timer = setTimeout(run, ms === undefined ? 250 : ms); }

  async function run() {
    const seq = ++runSeq;
    busy(true, 'Flying the mission …');
    try {
      const r = await call('run', JSON.stringify(cfg));
      if (seq !== runSeq) return;
      last = r; Object.keys(cache).forEach(k => delete cache[k]);
      renderKpis(); renderMission(); renderEnergy(); renderFc();
      if (view3d && window.H2Scene) window.H2Scene.load(last);
      const t = document.querySelector('.tab.on').dataset.t;
      if (t === 'pr') runPR(); else if (t === 'arch') runArch();
    } catch (e) { $('flags').textContent = 'Error: ' + e.message; }
    finally { if (seq === runSeq) busy(false); }
  }

  function renderKpis() {
    const s = last.summary;
    const used = s.architecture === 'battery' ? F(s.battery_energy_used_kwh) + ' kWh' : F(s.h2_used_kg) + ' kg H₂';
    const items = [
      ['Range', s.feasible ? F(s.range_km, 0) + ' km' : '—', s.feasible ? (s.range_km / 1.852).toFixed(0) + ' NM' : (s.max_range_reason || 'not feasible')],
      ['Block time', F(s.block_time_min, 0) + ' min', 'incl. reserve & taxi'],
      ['Take-off mass', F(s.mtow_kg, 0) + ' kg', s.mtow_limit_kg > 0 ? (s.mtow_ok ? '✓ below ' : '✗ above ') + F(s.mtow_limit_kg, 0) + ' kg limit' : ''],
      ['Energy intensity', F(s.wh_per_pax_km, 0) + ' Wh', 'per passenger-km'],
      ['Energy used', used, F(s.source_energy_kwh, 0) + ' kWh at the source'],
      ['Peak power', F(s.peak_shaft_kw, 0) + ' kW', 'shaft · CL max ' + F(s.peak_cl, 2)],
    ];
    $('kpis').innerHTML = items.map(k => '<div class="kpi"><span>' + k[0] + '</span><b>' + k[1] + '</b><small>' + esc(k[2]) + '</small></div>').join('') + '<div class="kpi"><span>Status</span><b><span class="pill ' + (s.feasible && s.mtow_ok ? 'ok' : 'bad') + '">' + (s.feasible && s.mtow_ok ? 'FEASIBLE' : 'CHECK') + '</span></b><small>' + esc(s.architecture) + '</small></div>';
    const fl = s.flags.slice(); if (!s.mtow_ok) fl.push('take-off mass above the MTOW limit'); if (s.max_range_reason) fl.push(s.max_range_reason);
    $('flags').textContent = fl.length ? '⚠ ' + fl.join(' · ') : '';
  }

  function bands(xs, segs) { const out = []; let start = 0; for (let i = 1; i <= segs.length; i++) { if (i === segs.length || segs[i] !== segs[start]) { out.push({ x0: xs[start], x1: xs[i - 1], color: SEG_COL[segs[start]] || 'transparent', label: (xs[i - 1] - xs[start]) > (xs[xs.length - 1] - xs[0]) * 0.07 ? segs[start] : '' }); start = i; } } return out; }

  function renderMission() {
    const S = last.series; if (!S) return;
    const tmin = S.t.map(t => t / 60);
    Charts.line($('cAlt'), { series: [{ x: S.x_km, y: S.alt_m, name: 'altitude', color: COL.h2, area: true }], xlabel: 'ground distance [km]', ylabel: 'altitude [m]', bands: bands(S.x_km, S.seg), height: 230 });
    const ser = [{ x: tmin, y: S.p_shaft_kw, name: 'shaft', color: COL.shaft, width: 1.6, dash: true }];
    if (cfg.architecture !== 'battery') ser.push({ x: tmin, y: S.p_fc_kw, name: 'fuel cell', color: COL.fc, area: true });
    if (cfg.architecture !== 'fuelcell') ser.push({ x: tmin, y: S.p_bat_kw, name: 'battery', color: COL.bat, area: true });
    Charts.line($('cPow'), { series: ser, xlabel: 'time [min]', ylabel: 'power [kW]', bands: bands(tmin, S.seg), ymin: Math.min(0, ...S.p_bat_kw) });
    const st = [];
    if (cfg.architecture !== 'fuelcell') st.push({ x: tmin, y: S.soc.map(v => v * 100), name: 'battery SOC [%]', color: COL.bat });
    if (cfg.architecture !== 'battery') st.push({ x: tmin, y: S.h2_kg, name: 'H₂ on board [kg]', color: COL.h2, axis: cfg.architecture === 'hybrid' ? 2 : 1 });
    Charts.line($('cSto'), { series: st, xlabel: 'time [min]', ylabel: cfg.architecture === 'fuelcell' ? 'hydrogen [kg]' : 'state of charge [%]', y2: cfg.architecture === 'hybrid' ? 'hydrogen [kg]' : null, bands: bands(tmin, S.seg) });
    const ld = S.ld.map((v, i) => S.seg[i] === 'taxi' || S.seg[i] === 'takeoff' || S.seg[i] === 'landing' ? NaN : v);
    Charts.line($('cLD'), { series: [{ x: tmin, y: ld, name: 'L/D', color: COL.bus }], xlabel: 'time [min]', ylabel: 'L/D [–]', bands: bands(tmin, S.seg) });
    $('tSeg').innerHTML = '<table><tr><th>Segment</th><th>Time [min]</th><th>Distance [km]</th><th>Electric energy [kWh]</th><th>SOC end</th><th>H₂ used [kg]</th></tr>' + last.segments.map(r => '<tr><td>' + r.segment + '</td><td class="n">' + F(r.time_min, 1) + '</td><td class="n">' + F(r.dist_km, 1) + '</td><td class="n">' + F(r.energy_kwh, 1) + '</td><td class="n">' + (cfg.architecture === 'fuelcell' ? '–' : (r.soc_end * 100).toFixed(1) + ' %') + '</td><td class="n">' + F(r.h2_used_kg, 2) + '</td></tr>').join('') + '</table>';
  }

  function renderEnergy() {
    Charts.donut($('cMass'), last.mass, MASS_COL);
    const s = last.summary, etaP = cfg.propulsion.eta_propeller;
    const parts = [
      ['Fuel cell heat', s.h2_energy_kwh - s.fc_energy_kwh, '#2f9fd6'],
      ['Battery losses', s.battery_loss_kwh, '#ffc24d'],
      ['Motor, inverter, gearbox, aux.', s.electric_energy_kwh - s.shaft_energy_kwh, '#c79bff'],
      ['Propeller losses', s.shaft_energy_kwh * (1 - etaP), '#ff7a45'],
      ['Useful propulsive work', s.shaft_energy_kwh * etaP, '#5cff9d'],
    ].filter(p => p[1] > 1e-6);
    const tot = parts.reduce((a, p) => a + p[1], 0);
    $('eFlow').innerHTML = '<div class="desc">Source energy ' + F(tot, 0) + ' kWh (' + (s.h2_energy_kwh > 0 ? F(s.h2_energy_kwh, 0) + ' kWh hydrogen (LHV)' : '') + (s.h2_energy_kwh > 0 && s.battery_energy_used_kwh > 0 ? ' + ' : '') + (s.battery_energy_used_kwh > 0 ? F(s.battery_energy_used_kwh, 0) + ' kWh battery' : '') + ')</div><div class="ebar">' + parts.map(p => '<div style="width:' + (p[1] / tot * 100) + '%;background:' + p[2] + '" title="' + p[0] + ': ' + F(p[1], 1) + ' kWh">' + (p[1] / tot > 0.08 ? (p[1] / tot * 100).toFixed(0) + ' %' : '') + '</div>').join('') + '</div><div class="legend">' + parts.map(p => '<span><i style="background:' + p[2] + '"></i>' + p[0] + ' · ' + F(p[1], 1) + ' kWh</span>').join('') + '</div><div class="desc" style="margin-top:14px">Overall efficiency from source to propulsive work: <b style="color:#fff">' + (s.shaft_energy_kwh * etaP / tot * 100).toFixed(1) + ' %</b></div>';
  }

  function renderFc() {
    const c = last.fc_curve || [];
    if (!c.length) { $('cFcEta').innerHTML = '<div class="desc">No fuel cell in the battery architecture.</div>'; $('cFcV').innerHTML = ''; return; }
    Charts.line($('cFcEta'), { series: [{ x: c.map(p => p.load * 100), y: c.map(p => p.eta * 100), name: 'system efficiency', color: COL.fc, area: true }], xlabel: 'load [% of rated power]', ylabel: 'efficiency (LHV) [%]', ymin: 0 });
    Charts.line($('cFcV'), { series: [{ x: c.map(p => p.i), y: c.map(p => p.v_cell), name: 'cell voltage', color: COL.h2 }, { x: c.map(p => p.i), y: c.map(p => p.v_cell * p.i), name: 'power density [W/cm²]', color: COL.bat, axis: 2 }], xlabel: 'current density [A/cm²]', ylabel: 'cell voltage [V]', y2: 'power density [W/cm²]', ymin: 0 });
  }

  function openTab(t) {
    document.querySelectorAll('.tab').forEach(x => x.classList.toggle('on', x.dataset.t === t));
    document.querySelectorAll('.pane').forEach(x => x.classList.toggle('on', x.id === 'p-' + t));
    if (t === 'flight') start3d();
    if (t === 'pr') runPR();
    if (t === 'arch') runArch();
    if (t === 'mission' && last) renderMission();
    if (t === 'energy' && last) renderEnergy();
    if (t === 'fc' && last) renderFc();
  }

  function start3d() {
    if (!view3d) {
      view3d = window.H2Scene.init($('v3'));
      if (!view3d) return;
      window.H2Scene.onFrame = hud;
      window.H2Scene.onEnd = () => { $('bPlay').textContent = '▶ Play'; };
      $('bPlay').addEventListener('click', () => { if (window.H2Scene.isPlaying()) { window.H2Scene.pause(); $('bPlay').textContent = '▶ Play'; } else { window.H2Scene.play(); $('bPlay').textContent = '❚❚ Pause'; } });
      $('bSpeed').addEventListener('change', e => window.H2Scene.setSpeed(+e.target.value));
      $('bSeek').addEventListener('input', e => window.H2Scene.seek(e.target.value / 1000));
      if (last) window.H2Scene.load(last);
      setTimeout(() => { window.H2Scene.resize(); window.H2Scene.play(); $('bPlay').textContent = '❚❚ Pause'; }, 60);
    } else window.H2Scene.resize();
  }

  function hud(i, t) {
    const S = last.series; if (!S) return;
    const a = cfg.architecture;
    const h2max = Math.max(1e-9, last.summary.h2_kg);
    $('hud').innerHTML = '<div style="font-weight:800;margin-bottom:4px;color:#fff">' + S.seg[i].toUpperCase() + '</div>' +
      '<div class="r"><span>time</span><b>' + (t / 60).toFixed(1) + ' min</b></div><div class="r"><span>distance</span><b>' + S.x_km[i].toFixed(1) + ' km</b></div><div class="r"><span>altitude</span><b>' + S.alt_m[i].toFixed(0) + ' m</b></div><div class="r"><span>TAS</span><b>' + (S.tas[i] * 1.943844).toFixed(0) + ' kt</b></div><div class="r"><span>shaft power</span><b style="color:' + COL.shaft + '">' + S.p_shaft_kw[i].toFixed(0) + ' kW</b></div>' +
      (a !== 'battery' ? '<div class="r"><span>fuel cell</span><b style="color:' + COL.fc + '">' + S.p_fc_kw[i].toFixed(0) + ' kW · η ' + (S.eta_fc[i] * 100).toFixed(1) + ' %</b></div><div class="r"><span>H₂ on board</span><b style="color:' + COL.h2 + '">' + S.h2_kg[i].toFixed(1) + ' kg</b></div><div class="bar"><div style="width:' + Math.max(0, S.h2_kg[i] / h2max * 100) + '%;background:' + COL.h2 + '"></div></div>' : '') +
      (a !== 'fuelcell' ? '<div class="r"><span>battery</span><b style="color:' + COL.bat + '">' + S.p_bat_kw[i].toFixed(0) + ' kW</b></div><div class="r"><span>state of charge</span><b style="color:' + COL.bat + '">' + (S.soc[i] * 100).toFixed(1) + ' %</b></div><div class="bar"><div style="width:' + Math.max(0, S.soc[i] * 100) + '%;background:' + COL.bat + '"></div></div>' : '');
    $('bSeek').value = Math.round(window.H2Scene.progress() * 1000);
    $('bTime').textContent = (t / 60).toFixed(1) + ' / ' + (S.t[S.t.length - 1] / 60).toFixed(0) + ' min';
  }

  async function runPR() {
    if (cache.pr) return;
    busy(true, 'Payload–range …');
    try {
      const pr = await call('payload_range', JSON.stringify(cfg)); cache.pr = pr;
      Charts.line($('cPR'), { series: [{ x: pr.map(p => p.range_km), y: pr.map(p => p.payload_kg), name: 'payload', color: COL.h2, dots: true, area: true }], xlabel: 'range [km]', ylabel: 'payload [kg]', height: 340 });
    } catch (e) { $('cPR').textContent = e.message; } finally { busy(false); }
  }

  async function runArch() {
    if (cache.arch) return;
    busy(true, 'Comparing architectures …');
    try {
      const r = await call('compare', JSON.stringify(cfg)); cache.arch = r;
      const names = { battery: 'Battery', fuelcell: 'Fuel cell', hybrid: 'Hybrid' };
      Charts.bars($('cArch'), { values: r.rows.map(x => x.range_km), labels: r.rows.map(x => names[x.architecture]), colors: [COL.bat, COL.h2, COL.fc], unit: 'km', ylabel: 'range at ' + F(r.mtow_kg, 0) + ' kg [km]', height: 300 });
      $('tArch').innerHTML = '<table><tr><th>Architecture</th><th>Range</th><th>Battery</th><th>Hydrogen</th><th>Energy intensity</th><th>Status</th></tr>' + r.rows.map(x => '<tr><td>' + names[x.architecture] + '</td><td class="n">' + F(x.range_km, 0) + ' km</td><td class="n">' + F(x.battery_kwh || 0, 0) + ' kWh</td><td class="n">' + F(x.h2_kg || 0, 1) + ' kg</td><td class="n">' + (x.wh_per_pax_km ? F(x.wh_per_pax_km, 0) + ' Wh/pax-km' : '–') + '</td><td>' + (x.feasible ? '<span class="pass">OK</span>' : '<span class="fail">' + esc(x.reason || (x.flags || []).join('; ') || 'not feasible') + '</span>') + '</td></tr>').join('') + '</table>';
    } catch (e) { $('tArch').textContent = e.message; } finally { busy(false); }
  }

  function tradeOptions() {
    const a = cfg.architecture;
    const ok = s => !(s.path.startsWith('battery') && a === 'fuelcell') && !((s.path.startsWith('fuelcell') || s.path.startsWith('tank')) && a === 'battery');
    const cur = $('tPath').value;
    $('tPath').innerHTML = schema.sweeps.filter(ok).map(s => '<option value="' + s.path + '">' + esc(s.label) + '</option>').join('');
    if ([...$('tPath').options].some(o => o.value === cur)) $('tPath').value = cur;
    tradeDefaults();
  }
  function tradeDefaults() { const s = schema.sweeps.find(x => x.path === $('tPath').value); if (!s) return; $('tFrom').value = s.from; $('tTo').value = s.to; $('tN').value = s.n; }

  async function runTrade() {
    busy(true, 'Trade study …');
    try {
      const path = $('tPath').value, label = $('tPath').selectedOptions[0].textContent;
      const r = await call('sweep', JSON.stringify(cfg), path, +$('tFrom').value, +$('tTo').value, +$('tN').value);
      Charts.line($('cTrade'), { series: [{ x: r.map(p => p.value), y: r.map(p => p.feasible ? p.range_km : NaN), name: 'range [km]', color: COL.h2, dots: true, area: true }, { x: r.map(p => p.value), y: r.map(p => p.mtow_kg), name: 'take-off mass [kg]', color: COL.bus, dash: true, axis: 2 }], xlabel: label, ylabel: 'range [km]', y2: 'take-off mass [kg]', height: 340 });
    } catch (e) { $('cTrade').textContent = e.message; } finally { busy(false); }
  }

  async function runSize() {
    busy(true, 'Sizing loop …');
    try {
      const r = await call('size', JSON.stringify(cfg), +$('sTarget').value); sized = r;
      const s = r.result.summary, varName = r.variable === 'battery.energy_kwh' ? 'Battery energy' : 'Hydrogen mass', unit = r.variable === 'battery.energy_kwh' ? 'kWh' : 'kg';
      $('sOut').innerHTML = '<div class="kpis"><div class="kpi"><span>Result</span><b><span class="pill ' + (r.ok ? 'ok' : 'bad') + '">' + (r.ok ? 'SIZED' : 'NOT REACHABLE') + '</span></b><small>' + esc(r.reason || 'target ' + F(r.target_km, 0) + ' km') + '</small></div><div class="kpi"><span>' + varName + '</span><b>' + F(r.value, 1) + ' ' + unit + '</b><small>sized variable</small></div><div class="kpi"><span>Range</span><b>' + F(r.achievable_km, 0) + ' km</b><small>' + (r.ok ? 'meets target' : 'maximum achievable') + '</small></div><div class="kpi"><span>Take-off mass</span><b>' + F(s.mtow_kg, 0) + ' kg</b><small>' + (s.mtow_ok ? 'within limit' : 'above MTOW limit') + '</small></div></div>';
      $('sApply').disabled = false;
    } catch (e) { $('sOut').textContent = e.message; } finally { busy(false); }
  }

  async function runValidation() {
    busy(true, 'Validation (≈ 30 s) …'); $('vOut').innerHTML = '<div class="desc">Running …</div>';
    const t0 = performance.now();
    try {
      const r = await call('validate'); const ok = r.filter(x => x.ok).length;
      $('vOut').innerHTML = '<div class="kpis"><div class="kpi"><span>Checks passed</span><b class="' + (ok === r.length ? 'pass' : 'fail') + '">' + ok + ' / ' + r.length + '</b><small>Python engine in your browser</small></div><div class="kpi"><span>Run time</span><b>' + ((performance.now() - t0) / 1000).toFixed(1) + ' s</b></div></div><table><tr><th>Group</th><th>Check</th><th>Result</th><th>Detail</th><th>Reference</th></tr>' + r.map(x => '<tr><td>' + esc(x.group) + '</td><td>' + esc(x.name) + '</td><td class="' + (x.ok ? 'pass' : 'fail') + '">' + (x.ok ? 'PASS' : 'FAIL') + '</td><td>' + esc(x.detail) + '</td><td class="sub">' + esc(x.ref) + '</td></tr>').join('') + '</table>';
    } catch (e) { $('vOut').textContent = e.message; } finally { busy(false); }
  }

  function renderAbout(v) {
    $('about').innerHTML = '<h2>Model</h2><p class="desc">All physics runs in the Python package <code>h2volt</code> (Pyodide ' + esc(v) + ' in a background worker).</p><table>' +
      [['Atmosphere', 'ISA (ISO 2533), geopotential altitude, troposphere and lower stratosphere'],
       ['Aerodynamics', 'Parabolic drag polar CD = CD0 + CL²/(π·AR·e); lift balances weight·cos γ in climb and descent'],
       ['Mission', 'Time-stepped: taxi, take-off, climb (power-limited climb rate), cruise, descent, reserve hold, landing; maximum range by bisection on cruise distance'],
       ['Electric drive', 'Shaft power = thrust·V / η_prop; bus power = shaft / (η_gearbox·η_motor·η_inverter) + auxiliary load'],
       ['Battery', 'Equivalent circuit: open-circuit voltage vs. SOC, internal resistance from efficiency at peak power, Coulomb counting, minimum SOC reserve'],
       ['Fuel cell', 'PEM polarization curve (activation, ohmic, mass-transport losses); efficiency = V_cell / 1.2532 V (LHV); balance-of-plant and idle load; Faraday hydrogen flow'],
       ['Hydrogen tank', 'LH2 or 700-bar CGH2 via gravimetric index; usable fraction; hydrogen burn-off reduces mass'],
       ['Hybrid strategy', 'Fuel cell first, battery shaves peaks; battery recharged from fuel-cell headroom up to a target SOC'],
       ['Sizing', 'Energy storage sized for a target range including the mass snowball (heavier storage → more drag → more energy)']
      ].map(r => '<tr><td style="width:170px;color:#fff;font-weight:600">' + r[0] + '</td><td class="sub">' + r[1] + '</td></tr>').join('') + '</table><p class="desc" style="margin-top:12px">Conceptual-design accuracy: results are physics-based estimates for comparing configurations, not certified performance data.</p>';
  }

  function download(name, text, type) { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 400); }

  window.addEventListener('resize', () => { if (last) { const t = document.querySelector('.tab.on').dataset.t; if (t === 'mission') renderMission(); if (t === 'energy') renderEnergy(); if (t === 'fc') renderFc(); } });
  window.H2App = { get cfg() { return cfg; }, get last() { return last; }, call, openTab };
  boot().catch(e => { $('bootTxt').textContent = 'Could not start the Python engine: ' + e.message; });
})();
