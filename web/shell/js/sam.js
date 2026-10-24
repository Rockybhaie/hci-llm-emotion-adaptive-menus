// Self-Assessment Manikin (Bradley & Lang, 1994), redrawn as SVG.
// Five figures per dimension over a 9-point scale (figures sit on points 1, 3, 5, 7, 9).

const INK = 'currentColor';

function body(scale = 1, extra = '') {
  return `
    <g transform="translate(40 92) scale(${scale}) translate(-40 -92)">
      ${extra}
      <path d="M20 92c0-26 8-42 20-42s20 16 20 42Z" fill="var(--sam-fill)" stroke="${INK}" stroke-width="2.2" stroke-linejoin="round"/>
      <circle cx="40" cy="29" r="17" fill="var(--sam-fill)" stroke="${INK}" stroke-width="2.2"/>
    </g>`;
}

function valence(i) {
  const curve = (i - 2) * 5;          // -10 (frown) .. +10 (smile)
  return `<svg viewBox="0 0 80 96">${body(1)}
    <circle cx="33.5" cy="25" r="1.9" fill="${INK}"/><circle cx="46.5" cy="25" r="1.9" fill="${INK}"/>
    <path d="M31 ${36 - curve / 4}Q40 ${36 + curve} 49 ${36 - curve / 4}" fill="none" stroke="${INK}" stroke-width="2.2" stroke-linecap="round"/></svg>`;
}

function arousal(i) {
  const burst = i === 0 ? '' : `<path d="${star(40, 66, 8 + i * 5.5, 4 + i * 2.2, 10)}" fill="var(--sam-accent)" opacity="${0.25 + i * 0.12}"/>`;
  const eyes = i === 0
    ? `<path d="M30 26h7M43 26h7" stroke="${INK}" stroke-width="2.2" stroke-linecap="round"/>`
    : `<circle cx="33.5" cy="25" r="${1.6 + i * 0.45}" fill="${INK}"/><circle cx="46.5" cy="25" r="${1.6 + i * 0.45}" fill="${INK}"/>`;
  const mouth = `<ellipse cx="40" cy="37" rx="${2 + i * 0.9}" ry="${1 + i * 0.9}" fill="none" stroke="${INK}" stroke-width="2"/>`;
  const core = i === 0 ? '' : `<path d="${star(40, 70, 3 + i * 2.2, 1.5 + i, 8)}" fill="${INK}"/>`;
  return `<svg viewBox="0 0 80 96">${body(1)}${burst}${core}${eyes}${mouth}</svg>`;
}

function dominance(i) {
  const s = 0.55 + i * 0.12;
  return `<svg viewBox="0 0 80 96">${body(s)}
    <g transform="translate(40 92) scale(${s}) translate(-40 -92)">
      <circle cx="33.5" cy="25" r="1.9" fill="${INK}"/><circle cx="46.5" cy="25" r="1.9" fill="${INK}"/>
      <path d="M33 36h14" stroke="${INK}" stroke-width="2.2" stroke-linecap="round"/>
    </g></svg>`;
}

function star(cx, cy, outer, inner, points) {
  let d = '';
  for (let k = 0; k < points * 2; k++) {
    const r = k % 2 ? inner : outer;
    const a = (Math.PI * k) / points - Math.PI / 2;
    d += `${k ? 'L' : 'M'}${(cx + r * Math.cos(a)).toFixed(1)} ${(cy + r * Math.sin(a)).toFixed(1)}`;
  }
  return `${d}Z`;
}

export const SAM_DIMENSIONS = [
  { key: 'valence', draw: valence, left: 'Unhappy', right: 'Happy', prompt: 'How pleasant or unpleasant do you feel?' },
  { key: 'arousal', draw: arousal, left: 'Calm', right: 'Excited', prompt: 'How calm or excited do you feel?' },
  { key: 'dominance', draw: dominance, left: 'Controlled', right: 'In control', prompt: 'How much in control do you feel?' },
];

export function samRow(dim) {
  const figures = [0, 1, 2, 3, 4].map((i) => `<div class="sam-fig" style="grid-column:${i * 2 + 1}">${dim.draw(i)}</div>`).join('');
  const dots = Array.from({ length: 9 }, (_, i) =>
    `<button type="button" class="sam-dot" data-v="${i + 1}" aria-label="${i + 1} of 9"><span></span></button>`).join('');
  return `
    <div class="sam" data-key="${dim.key}">
      <div class="sam-prompt">${dim.prompt}</div>
      <div class="sam-grid">${figures}</div>
      <div class="sam-grid dots">${dots}</div>
      <div class="sam-ends"><span>${dim.left}</span><span>${dim.right}</span></div>
    </div>`;
}
