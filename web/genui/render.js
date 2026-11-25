// Generative-UI block renderer. An answer "look" is a list of blocks (content/queries/*.yaml, and later the
// LLM agent's output); this turns it into DOM. Charts and diagrams are inline SVG/HTML: offline, no libraries.
// Every block carries data-aoi="block:<look>:<n>:<type>" so its on-screen rectangle can be logged.

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
const fmt = (v, f) => (f === '0.00' ? Number(v).toFixed(2) : Number.isInteger(v) ? String(v) : String(+Number(v).toFixed(2)));

const svgIcon = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const TONE = {
  tip: ['Tip', svgIcon('<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z"/>')],
  note: ['Note', svgIcon('<circle cx="12" cy="12" r="9"/><path d="M12 16v-5M12 8h.01"/>')],
  analogy: ['Think of it like this', svgIcon('<path d="M17 2l3 3-3 3M4 11V9a4 4 0 0 1 4-4h12M7 22l-3-3 3-3M20 13v2a4 4 0 0 1-4 4H4"/>')],
  warning: ['Watch out', svgIcon('<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01"/>')],
};

// ------------------------------------------------------------------ charts
const W = 640;
const H = 300;
const M = { l: 56, r: 18, t: 18, b: 54 };

/** A y-axis from 0 that fits `v`: about 4-6 round ticks ({yMax, ticks}). */
function niceAxis(v, integer = false) {
  if (v <= 0) return { yMax: 1, ticks: 1 };
  const raw = v / 5;
  const p = 10 ** Math.floor(Math.log10(raw));
  let step = [1, 2, 2.5, 5, 10].map((m) => m * p).find((x) => x >= raw);
  if (integer) step = Math.max(1, Math.ceil(step));
  const ticks = Math.ceil(v / step);
  return { yMax: step * ticks, ticks };
}

function axes(xLabel, yLabel, yMax, yTicks = 4, fmtY = (v) => fmt(v)) {
  const ih = H - M.t - M.b;
  let g = '';
  for (let i = 0; i <= yTicks; i++) {
    const v = (yMax / yTicks) * i;
    const y = M.t + ih - (v / yMax) * ih;
    g += `<line class="gx-grid" x1="${M.l}" x2="${W - M.r}" y1="${y}" y2="${y}"/><text class="gx-tick" x="${M.l - 8}" y="${y + 4}" text-anchor="end">${fmtY(v)}</text>`;
  }
  g += `<line class="gx-axis" x1="${M.l}" x2="${W - M.r}" y1="${H - M.b}" y2="${H - M.b}"/>`;
  if (xLabel) g += `<text class="gx-label" x="${(M.l + W - M.r) / 2}" y="${H - 8}" text-anchor="middle">${esc(xLabel)}</text>`;
  if (yLabel) g += `<text class="gx-label" transform="translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)" text-anchor="middle">${esc(yLabel)}</text>`;
  return g;
}

function barChart(b) {
  const vals = b.values;
  const { yMax, ticks } = niceAxis(Math.max(...vals) * 1.12);
  const iw = W - M.l - M.r;
  const ih = H - M.t - M.b;
  const slot = iw / vals.length;
  const bw = Math.min(64, slot * 0.62);
  let g = axes(b.x_label, b.y_label, yMax, ticks, (v) => fmt(v, b.value_format));
  vals.forEach((v, i) => {
    const x = M.l + slot * i + (slot - bw) / 2;
    const h = (v / yMax) * ih;
    const y = M.t + ih - h;
    const tone = b.highlight == null ? '' : i === b.highlight ? ' hi' : ' lo';
    g += `<rect class="gx-bar${tone}" x="${x}" y="${y}" width="${bw}" height="${h}" rx="3"/>`;
    g += `<text class="gx-val" x="${x + bw / 2}" y="${y - 6}" text-anchor="middle">${fmt(v, b.value_format)}</text>`;
    g += `<text class="gx-cat" x="${x + bw / 2}" y="${H - M.b + 18}" text-anchor="middle">${esc(b.categories[i])}</text>`;
  });
  return g;
}

function xyScale(points, b) {
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const { yMax, ticks } = niceAxis(Math.max(...ys) * 1.1);
  const iw = W - M.l - M.r;
  const ih = H - M.t - M.b;
  return {
    yMax,
    ticks,
    sx: (x) => M.l + ((x - x0) / (x1 - x0 || 1)) * iw,
    sy: (y) => M.t + ih - (y / yMax) * ih,
    xTicks: [...new Set(xs)].slice(0, 12),
  };
}

function lineChart(b) {
  const all = b.series.flatMap((s) => s.points);
  const s = xyScale(all, b);
  let g = axes(b.x_label, b.y_label, s.yMax, s.ticks);
  s.xTicks.forEach((x) => { g += `<text class="gx-tick" x="${s.sx(x)}" y="${H - M.b + 18}" text-anchor="middle">${fmt(x)}</text>`; });
  b.series.forEach((ser, k) => {
    const d = ser.points.map((p, i) => `${i ? 'L' : 'M'}${s.sx(p[0]).toFixed(1)} ${s.sy(p[1]).toFixed(1)}`).join('');
    g += `<path class="gx-line s${k}${ser.dashed ? ' dashed' : ''}" d="${d}"/>`;
    if (!ser.dashed && b.series.length === 1) ser.points.forEach((p) => { g += `<circle class="gx-dot s${k}" cx="${s.sx(p[0])}" cy="${s.sy(p[1])}" r="3.5"/>`; });
  });
  return g;
}

/** HTML legend above the plot, one entry per named series (never overlaps the data). */
function legend(series) {
  if (!series || series.length < 2) return '';
  return `<div class="gx-legend">${series.map((ser, k) => `<span><i class="s${k}${ser.dashed ? ' dashed' : ''}"></i>${esc(ser.name || '')}</span>`).join('')}</div>`;
}

function scatterChart(b) {
  const all = b.series.flatMap((s) => s.points);
  const s = xyScale(all, b);
  let g = axes(b.x_label, b.y_label, s.yMax, s.ticks);
  b.series.forEach((ser, k) => ser.points.forEach((p) => { g += `<circle class="gx-dot s${k}" cx="${s.sx(p[0])}" cy="${s.sy(p[1])}" r="5"/>`; }));
  if (b.fit) g += `<line class="gx-fit" x1="${s.sx(b.fit[0][0])}" y1="${s.sy(b.fit[0][1])}" x2="${s.sx(b.fit[1][0])}" y2="${s.sy(b.fit[1][1])}"/>`;
  return g;
}

function quartiles(values) {
  const v = [...values].sort((a, b) => a - b);
  const med = (a) => (a.length % 2 ? a[(a.length - 1) / 2] : (a[a.length / 2 - 1] + a[a.length / 2]) / 2);
  const half = Math.floor(v.length / 2);
  return { v, q1: med(v.slice(0, half)), q2: med(v), q3: med(v.slice(v.length % 2 ? half + 1 : half)) };
}

function histogram(b) {
  const bw = b.bin_width || 1;
  const lo = Math.floor(Math.min(...b.values) / bw) * bw;
  const hi = Math.floor(Math.max(...b.values) / bw) * bw + bw;
  const nb = Math.round((hi - lo) / bw);
  const counts = Array(nb).fill(0);
  b.values.forEach((x) => { counts[Math.min(nb - 1, Math.floor((x - lo) / bw))] += 1; });
  const { yMax, ticks } = niceAxis(Math.max(...counts) + 0.5, true);
  const iw = W - M.l - M.r;
  const ih = H - M.t - M.b;
  const sx = (x) => M.l + ((x - lo) / (hi - lo)) * iw;
  let g = axes(b.x_label, b.y_label, yMax, ticks);
  counts.forEach((c, i) => {
    const x = sx(lo + i * bw);
    const h = (c / yMax) * ih;
    if (c) g += `<rect class="gx-bar" x="${x + 1}" y="${M.t + ih - h}" width="${sx(lo + bw) - sx(lo) - 2}" height="${h}" rx="2"/>`;
  });
  for (let x = lo; x <= hi; x += bw * Math.max(1, Math.round(nb / 14))) {
    g += `<text class="gx-tick" x="${sx(x)}" y="${H - M.b + 18}" text-anchor="middle">${fmt(x)}</text>`;
  }
  (b.markers || []).forEach((mk, k) => {             // dashed line + a legend entry at the top right
    const x = sx(mk.value);
    const ly = M.t + 6 + k * 20;
    g += `<line class="gx-marker m${k}" x1="${x}" x2="${x}" y1="${M.t}" y2="${H - M.b}"/>`;
    g += `<line class="gx-marker m${k}" x1="${W - M.r - 150}" x2="${W - M.r - 126}" y1="${ly}" y2="${ly}"/>`;
    g += `<text class="gx-marker-label m${k}" x="${W - M.r - 120}" y="${ly + 4}">${esc(mk.label)}</text>`;
  });
  return g;
}

function boxPlot(b) {
  const { v, q1, q2, q3 } = quartiles(b.values);
  const iqr = q3 - q1;
  const loF = q1 - 1.5 * iqr;
  const hiF = q3 + 1.5 * iqr;
  const inside = v.filter((x) => x >= loF && x <= hiF);
  const outliers = v.filter((x) => x < loF || x > hiF);
  const lo = Math.floor(Math.min(...v));
  const hi = Math.ceil(Math.max(...v));
  const iw = W - M.l - M.r;
  const sx = (x) => M.l + ((x - lo) / (hi - lo || 1)) * iw;
  const cy = 120;
  let g = `<line class="gx-axis" x1="${M.l}" x2="${W - M.r}" y1="220" y2="220"/>`;
  for (let x = lo; x <= hi; x += Math.max(1, Math.round((hi - lo) / 12))) {
    g += `<line class="gx-grid" x1="${sx(x)}" x2="${sx(x)}" y1="40" y2="220"/><text class="gx-tick" x="${sx(x)}" y="238" text-anchor="middle">${x}</text>`;
  }
  g += `<line class="gx-whisker" x1="${sx(Math.min(...inside))}" x2="${sx(q1)}" y1="${cy}" y2="${cy}"/>`;
  g += `<line class="gx-whisker" x1="${sx(q3)}" x2="${sx(Math.max(...inside))}" y1="${cy}" y2="${cy}"/>`;
  [Math.min(...inside), Math.max(...inside)].forEach((x) => { g += `<line class="gx-whisker" x1="${sx(x)}" x2="${sx(x)}" y1="${cy - 18}" y2="${cy + 18}"/>`; });
  g += `<rect class="gx-box" x="${sx(q1)}" y="${cy - 34}" width="${sx(q3) - sx(q1)}" height="68" rx="4"/>`;
  g += `<line class="gx-median" x1="${sx(q2)}" x2="${sx(q2)}" y1="${cy - 34}" y2="${cy + 34}"/>`;
  g += `<text class="gx-val" x="${sx(q2)}" y="${cy - 42}" text-anchor="middle">median ${fmt(q2)}</text>`;
  g += `<text class="gx-tick" x="${sx(q1)}" y="${cy + 52}" text-anchor="middle">Q1 ${fmt(q1)}</text><text class="gx-tick" x="${sx(q3)}" y="${cy + 52}" text-anchor="middle">Q3 ${fmt(q3)}</text>`;
  outliers.forEach((x) => {
    const edge = sx(x) > W - M.r - 50 ? 'end' : sx(x) < M.l + 50 ? 'start' : 'middle';
    g += `<circle class="gx-outlier" cx="${sx(x)}" cy="${cy}" r="6"/><text class="gx-val" x="${sx(x)}" y="${cy - 14}" text-anchor="${edge}">outlier ${fmt(x)}</text>`;
  });
  if (b.x_label) g += `<text class="gx-label" x="${(M.l + W - M.r) / 2}" y="${H - 18}" text-anchor="middle">${esc(b.x_label)}</text>`;
  return g;
}

function chart(b) {
  const draw = { bar: barChart, line: lineChart, scatter: scatterChart, histogram, box: boxPlot }[b.kind];
  return `<figure class="gx-chart">
    ${b.title ? `<figcaption>${esc(b.title)}</figcaption>` : ''}${legend(b.series)}
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(b.title || b.kind)}">${draw(b)}</svg>
  </figure>`;
}

// ------------------------------------------------------------------ diagrams
function network(b) {
  const layers = b.layers;
  const w = 560;
  const h = 240;
  const colX = (i) => 60 + (i * (w - 120)) / (layers.length - 1);
  const rowY = (n, j) => h / 2 + (j - (n - 1) / 2) * 44;
  let g = '';
  layers.forEach((n, i) => {
    if (i + 1 < layers.length) {
      for (let a = 0; a < n; a++) for (let c = 0; c < layers[i + 1]; c++) {
        g += `<line class="gx-edge" x1="${colX(i)}" y1="${rowY(n, a)}" x2="${colX(i + 1)}" y2="${rowY(layers[i + 1], c)}"/>`;
      }
    }
  });
  layers.forEach((n, i) => {
    for (let a = 0; a < n; a++) g += `<circle class="gx-neuron l${i === 0 ? 'in' : i === layers.length - 1 ? 'out' : 'hid'}" cx="${colX(i)}" cy="${rowY(n, a)}" r="15"/>`;
    if (b.labels?.[i]) g += `<text class="gx-tick" x="${colX(i)}" y="${h + 22}" text-anchor="middle">${esc(b.labels[i])}</text>`;
  });
  return `<figure class="gx-chart gx-diagram"><svg viewBox="0 0 ${w} ${h + 34}">${g}</svg>${b.caption ? `<figcaption class="gx-caption">${esc(b.caption)}</figcaption>` : ''}</figure>`;
}

const ARROW = '<svg class="gx-flow-arrow" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function flow(b) {
  const nodes = b.nodes.map((n, i) => `<div class="gx-flow-node"><span class="gx-flow-n">${i + 1}</span>${esc(n)}</div>`);
  return `<div class="gx-flow${b.loop ? ' loop' : ''}">${nodes.join(ARROW)}${b.loop ? `<div class="gx-flow-repeat">${svgIcon('<path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5"/>')}Repeat many times</div>` : ''}</div>`;
}

/** Nodes around an ellipse joined by arrows: a process that loops (e.g. blood through the heart). */
function cycle(b) {
  const w = 640;
  const h = 330;
  const cx = w / 2;
  const cy = h / 2;
  const rx = 228;
  const ry = 120;
  const n = b.nodes.length;
  const boxes = b.nodes.map((label, i) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    const bw = Math.max(84, String(label).length * 7.6 + 30);
    return { label, x: cx + rx * Math.cos(a), y: cy + ry * Math.sin(a), hw: bw / 2, hh: 18 };
  });
  const exit = (p, dx, dy) => {                     // point where a ray from the box centre leaves the box
    const t = Math.min(dx ? (p.hw + 7) / Math.abs(dx) : Infinity, dy ? (p.hh + 7) / Math.abs(dy) : Infinity);
    return [p.x + dx * t, p.y + dy * t];
  };
  let g = '<defs><marker id="gx-ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="gx-cycle-ah" d="M1 1l8 4-8 4" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>';
  boxes.forEach((p, i) => {
    const q = boxes[(i + 1) % n];
    const len = Math.hypot(q.x - p.x, q.y - p.y);
    const [dx, dy] = [(q.x - p.x) / len, (q.y - p.y) / len];
    const [x1, y1] = exit(p, dx, dy);
    const [x2, y2] = exit(q, -dx, -dy);
    const mx = (x1 + x2) / 2;
    const my = (y1 + y2) / 2;
    const ol = Math.hypot(mx - cx, my - cy) || 1;
    const bend = 16;
    g += `<path class="gx-cycle-edge" d="M${x1.toFixed(1)} ${y1.toFixed(1)} Q${(mx + ((mx - cx) / ol) * bend).toFixed(1)} ${(my + ((my - cy) / ol) * bend).toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}" marker-end="url(#gx-ah)"/>`;
  });
  boxes.forEach((p, i) => {
    g += `<rect class="gx-cycle-node${i === 0 ? ' first' : ''}" x="${p.x - p.hw}" y="${p.y - p.hh}" width="${p.hw * 2}" height="${p.hh * 2}" rx="8"/>`;
    g += `<text class="gx-cycle-label" x="${p.x}" y="${p.y + 4.5}" text-anchor="middle">${esc(p.label)}</text>`;
  });
  if (b.center) g += `<text class="gx-cycle-center" x="${cx}" y="${cy + 5}" text-anchor="middle">${esc(b.center)}</text>`;
  return `<figure class="gx-chart gx-diagram"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(b.center || 'cycle')}">${g}</svg>${b.caption ? `<figcaption class="gx-caption">${esc(b.caption)}</figcaption>` : ''}</figure>`;
}

/** Phases laid out on a day/week scale (e.g. a two-week study plan). */
function timeline(b) {
  const cols = `grid-template-columns: repeat(${b.total}, 1fr)`;
  const scale = Array.from({ length: b.total }, (_, i) => `<span>${i + 1}</span>`).join('');
  const rows = b.items.map((it, k) => `
    <div class="gx-tl-row">
      <div class="gx-tl-what"><b>${esc(it.label)}</b>${it.text ? `<small>${inline(it.text)}</small>` : ''}</div>
      <div class="gx-tl-track" style="${cols}"><span class="gx-tl-bar t${k % 4}" style="grid-column:${it.from} / ${it.to + 1}">${it.from === it.to ? `${esc(b.unit || '')} ${it.from}` : `${esc(b.unit || '')} ${it.from}–${it.to}`}</span></div>
    </div>`).join('');
  return `<div class="gx-tl">
    <div class="gx-tl-row gx-tl-head"><div class="gx-tl-what">${esc(b.unit || '')}</div><div class="gx-tl-scale" style="${cols}">${scale}</div></div>
    ${rows}</div>`;
}

function tree(b) {
  return `<div class="gx-tree">
    <div class="gx-tree-root">${esc(b.root)}</div>
    <div class="gx-tree-branches">${b.branches.map((br) => `
      <div class="gx-tree-branch">
        <div class="gx-tree-label">${esc(br.label)}</div>
        <div class="gx-tree-leaves">${br.leaves.map((l) => `<span class="gx-chip">${esc(l)}</span>`).join('')}</div>
      </div>`).join('')}
    </div>
  </div>`;
}

// ------------------------------------------------------------------ blocks
function block(b) {
  switch (b.type) {
    case 'heading': return `<h2 class="gx-h">${inline(b.text)}</h2>`;
    case 'paragraph': return `<p class="gx-p">${inline(b.text)}</p>`;
    case 'bullets': return `<ul class="gx-ul">${b.items.map((i) => `<li>${inline(i)}</li>`).join('')}</ul>`;
    case 'steps': return `<ol class="gx-steps">${b.items.map((s, i) => `
      <li><span class="gx-step-n">${i + 1}</span><div><div class="gx-step-t">${inline(s.title)}</div><div class="gx-step-x">${inline(s.text)}</div></div></li>`).join('')}</ol>`;
    case 'table': return `<div class="gx-table-wrap">${b.caption ? `<div class="gx-caption">${esc(b.caption)}</div>` : ''}<table class="gx-table">
      <thead><tr>${b.columns.map((c) => `<th>${inline(c)}</th>`).join('')}</tr></thead>
      <tbody>${b.rows.map((r) => `<tr>${r.map((c, i) => `<td${i === 0 ? ' class="gx-strong"' : ''}>${inline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    case 'chart': return chart(b);
    case 'callout': {
      const [label, ic] = TONE[b.tone || 'note'];
      return `<div class="gx-callout tone-${b.tone || 'note'}"><span class="gx-callout-i" aria-hidden="true">${ic}</span><div><div class="gx-callout-t">${inline(b.title || label)}</div><div class="gx-callout-x">${inline(b.text)}</div></div></div>`;
    }
    case 'example': return `<div class="gx-example">
      <div class="gx-example-t">${inline(b.title)}</div>
      ${b.setup ? `<p class="gx-p">${inline(b.setup)}</p>` : ''}
      <ol class="gx-example-steps">${b.steps.map((s) => `<li>${inline(s)}</li>`).join('')}</ol>
      <div class="gx-example-r"><span>Result</span>${inline(b.result)}</div></div>`;
    case 'formula': return `<div class="gx-formula">${inline(b.expression)}${b.where ? `<div class="gx-where">${b.where.map(([s, m]) => `<span><b>${esc(s)}</b> ${esc(m)}</span>`).join('')}</div>` : ''}</div>`;
    case 'cards': return `<div class="gx-cards">${b.items.map((c) => `<div class="gx-card"><div class="gx-card-t">${inline(c.title)}</div><div class="gx-card-x">${inline(c.text)}</div></div>`).join('')}</div>`;
    case 'diagram': return { network, flow, tree, cycle, timeline }[b.kind](b);
    default: return `<p class="gx-p">[unsupported block: ${esc(b.type)}]</p>`;
  }
}

/** Render one look (array of blocks) into a new element. */
export function renderLook(blocks, look) {
  const el = document.createElement('div');
  el.className = `gx-answer look-${look}`;
  el.innerHTML = blocks.map((b, i) => `<div class="gx-block" data-aoi="block:${look}:${i + 1}:${b.type}${b.kind ? '-' + b.kind : ''}">${block(b)}</div>`).join('');
  return el;
}
