(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const fmt = (v, d) => { if (!Number.isFinite(v)) return ''; if (Math.abs(v) < 1e-12) return '0'; const a = Math.abs(v); if (a !== 0 && (a >= 1e5 || a < 1e-3)) return v.toExponential(1); return v.toFixed(d === undefined ? (a >= 100 ? 0 : a >= 10 ? 1 : 2) : d); };
  function nice(lo, hi, n) {
    if (!(hi > lo)) { hi = lo + 1; }
    const span = hi - lo, step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0))), r = step0 / mag;
    const step = (r < 1.5 ? 1 : r < 3 ? 2 : r < 7 ? 5 : 10) * mag;
    return { lo: Math.floor(lo / step) * step, hi: Math.ceil(hi / step) * step, step };
  }
  function line(el, o) {
    const W = el.clientWidth || 600, H = o.height || 260, m = { l: 56, r: o.y2 ? 56 : 16, t: 16, b: 38 };
    let xs = [], ys = [], ys2 = [];
    o.series.forEach(s => { s.x.forEach(v => xs.push(v)); (s.axis === 2 ? ys2 : ys).push(...s.y.filter(Number.isFinite)); });
    const X = nice(Math.min(...xs), Math.max(...xs), 6), Y = nice(o.ymin !== undefined ? o.ymin : Math.min(0, ...ys), Math.max(...ys), 5);
    const Y2 = o.y2 ? nice(o.y2min !== undefined ? o.y2min : Math.min(0, ...ys2), Math.max(...ys2), 5) : null;
    const sx = v => m.l + (v - X.lo) / (X.hi - X.lo) * (W - m.l - m.r);
    const sy = v => m.t + (1 - (v - Y.lo) / (Y.hi - Y.lo)) * (H - m.t - m.b);
    const sy2 = v => m.t + (1 - (v - Y2.lo) / (Y2.hi - Y2.lo)) * (H - m.t - m.b);
    let s = '';
    if (o.bands) o.bands.forEach(b => { s += '<rect x="' + sx(b.x0) + '" y="' + m.t + '" width="' + Math.max(0, sx(b.x1) - sx(b.x0)) + '" height="' + (H - m.t - m.b) + '" fill="' + b.color + '"/>' + (b.label ? '<text x="' + ((sx(b.x0) + sx(b.x1)) / 2) + '" y="' + (m.t + 12) + '" class="cl" text-anchor="middle">' + b.label + '</text>' : ''); });
    for (let v = Y.lo; v <= Y.hi + 1e-9; v += Y.step) s += '<line x1="' + m.l + '" x2="' + (W - m.r) + '" y1="' + sy(v) + '" y2="' + sy(v) + '" class="gl"/><text x="' + (m.l - 6) + '" y="' + (sy(v) + 4) + '" class="tl" text-anchor="end">' + fmt(v) + '</text>';
    if (Y2) for (let v = Y2.lo; v <= Y2.hi + 1e-9; v += Y2.step) s += '<text x="' + (W - m.r + 6) + '" y="' + (sy2(v) + 4) + '" class="tl">' + fmt(v) + '</text>';
    for (let v = X.lo; v <= X.hi + 1e-9; v += X.step) s += '<text x="' + sx(v) + '" y="' + (H - m.b + 16) + '" class="tl" text-anchor="middle">' + fmt(v) + '</text>';
    s += '<text x="' + ((W + m.l - m.r) / 2) + '" y="' + (H - 4) + '" class="al" text-anchor="middle">' + (o.xlabel || '') + '</text><text transform="translate(12 ' + (H / 2) + ') rotate(-90)" class="al" text-anchor="middle">' + (o.ylabel || '') + '</text>';
    if (o.y2) s += '<text transform="translate(' + (W - 8) + ' ' + (H / 2) + ') rotate(90)" class="al" text-anchor="middle">' + o.y2 + '</text>';
    o.series.forEach(se => {
      const f = se.axis === 2 ? sy2 : sy;
      let d = '';
      se.x.forEach((x, i) => { const y = se.y[i]; if (!Number.isFinite(y)) return; d += (d ? 'L' : 'M') + sx(x).toFixed(1) + ' ' + f(y).toFixed(1); });
      if (se.area && d) s += '<path d="' + d + 'L' + sx(se.x[se.x.length - 1]) + ' ' + f(Math.max(Y.lo, 0)) + 'L' + sx(se.x[0]) + ' ' + f(Math.max(Y.lo, 0)) + 'Z" fill="' + se.color + '" opacity=".18"/>';
      s += '<path d="' + d + '" fill="none" stroke="' + se.color + '" stroke-width="' + (se.width || 2.2) + '"' + (se.dash ? ' stroke-dasharray="6 4"' : '') + '/>';
      if (se.dots) se.x.forEach((x, i) => { if (Number.isFinite(se.y[i])) s += '<circle cx="' + sx(x) + '" cy="' + f(se.y[i]) + '" r="3.5" fill="' + se.color + '"/>'; });
    });
    let lg = '', lx = m.l + 8;
    o.series.filter(x => x.name).forEach(se => { lg += '<rect x="' + lx + '" y="' + (m.t + 4) + '" width="12" height="3" fill="' + se.color + '"/><text x="' + (lx + 16) + '" y="' + (m.t + 9) + '" class="lg">' + se.name + '</text>'; lx += 24 + se.name.length * 6.4; });
    s += lg + '<line class="xh" y1="' + m.t + '" y2="' + (H - m.b) + '" style="display:none"/>';
    el.innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" height="' + H + '" xmlns="' + NS + '">' + s + '</svg><div class="tip"></div>';
    const svg = el.querySelector('svg'), tip = el.querySelector('.tip'), xh = svg.querySelector('.xh');
    svg.addEventListener('mousemove', ev => {
      const r = svg.getBoundingClientRect(); const px = (ev.clientX - r.left) * W / r.width;
      if (px < m.l || px > W - m.r) { tip.style.display = 'none'; xh.style.display = 'none'; return; }
      const xv = X.lo + (px - m.l) / (W - m.l - m.r) * (X.hi - X.lo);
      let html = '<b>' + (o.xlabel || 'x') + ': ' + fmt(xv) + '</b>';
      o.series.filter(x => x.name).forEach(se => { let bi = 0, bd = Infinity; se.x.forEach((x, i) => { const d = Math.abs(x - xv); if (d < bd) { bd = d; bi = i; } }); html += '<br><span style="color:' + se.color + '">●</span> ' + se.name + ': ' + fmt(se.y[bi]); });
      tip.innerHTML = html; tip.style.display = 'block'; tip.style.left = Math.min(ev.clientX - r.left + 14, r.width - 170) + 'px'; tip.style.top = (ev.clientY - r.top + 10) + 'px';
      xh.setAttribute('x1', px); xh.setAttribute('x2', px); xh.style.display = '';
    });
    svg.addEventListener('mouseleave', () => { tip.style.display = 'none'; xh.style.display = 'none'; });
  }
  function bars(el, o) {
    const W = el.clientWidth || 600, H = o.height || 260, m = { l: 56, r: 16, t: 20, b: 46 };
    const Y = nice(0, Math.max(...o.values, 1e-9), 5), n = o.values.length, bw = (W - m.l - m.r) / n;
    const sy = v => m.t + (1 - (v - Y.lo) / (Y.hi - Y.lo)) * (H - m.t - m.b);
    let s = '';
    for (let v = Y.lo; v <= Y.hi + 1e-9; v += Y.step) s += '<line x1="' + m.l + '" x2="' + (W - m.r) + '" y1="' + sy(v) + '" y2="' + sy(v) + '" class="gl"/><text x="' + (m.l - 6) + '" y="' + (sy(v) + 4) + '" class="tl" text-anchor="end">' + fmt(v) + '</text>';
    o.values.forEach((v, i) => { const x = m.l + i * bw + bw * 0.18, w = bw * 0.64; s += '<rect x="' + x + '" y="' + sy(v) + '" width="' + w + '" height="' + Math.max(0, sy(0) - sy(v)) + '" rx="6" fill="' + o.colors[i % o.colors.length] + '"/><text x="' + (x + w / 2) + '" y="' + (sy(v) - 6) + '" class="bv" text-anchor="middle">' + fmt(v, 0) + (o.unit ? ' ' + o.unit : '') + '</text><text x="' + (x + w / 2) + '" y="' + (H - m.b + 18) + '" class="tl" text-anchor="middle">' + o.labels[i] + '</text>'; });
    s += '<text transform="translate(12 ' + (H / 2) + ') rotate(-90)" class="al" text-anchor="middle">' + (o.ylabel || '') + '</text>';
    el.innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" height="' + H + '">' + s + '</svg>';
  }
  function donut(el, items, colors) {
    const W = el.clientWidth || 520, H = 280, R = 105, r = 64, cx = 140, cy = 140;
    const tot = items.reduce((a, b) => a + b.kg, 0);
    let a0 = -Math.PI / 2, s = '';
    items.forEach((it, i) => {
      if (it.kg <= 0) return;
      const a1 = a0 + it.kg / tot * Math.PI * 2, large = a1 - a0 > Math.PI ? 1 : 0;
      const p = (rr, a) => (cx + rr * Math.cos(a)).toFixed(2) + ' ' + (cy + rr * Math.sin(a)).toFixed(2);
      s += '<path d="M' + p(R, a0) + 'A' + R + ' ' + R + ' 0 ' + large + ' 1 ' + p(R, a1) + 'L' + p(r, a1) + 'A' + r + ' ' + r + ' 0 ' + large + ' 0 ' + p(r, a0) + 'Z" fill="' + colors[i % colors.length] + '"><title>' + it.name + ': ' + fmt(it.kg, 0) + ' kg</title></path>';
      a0 = a1;
    });
    s += '<text x="' + cx + '" y="' + (cy - 4) + '" text-anchor="middle" class="dv">' + fmt(tot, 0) + '</text><text x="' + cx + '" y="' + (cy + 16) + '" text-anchor="middle" class="tl">kg take-off</text>';
    let ly = 26;
    items.forEach((it, i) => { if (it.kg <= 0) return; s += '<rect x="275" y="' + (ly - 9) + '" width="11" height="11" rx="2" fill="' + colors[i % colors.length] + '"/><text x="292" y="' + ly + '" class="lg2">' + it.name + '</text><text x="' + (W - 10) + '" y="' + ly + '" class="lg2" text-anchor="end">' + fmt(it.kg, 0) + ' kg · ' + (it.kg / tot * 100).toFixed(1) + ' %</text>'; ly += 24; });
    el.innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" height="' + H + '">' + s + '</svg>';
  }
  window.Charts = { line, bars, donut, fmt };
})();
