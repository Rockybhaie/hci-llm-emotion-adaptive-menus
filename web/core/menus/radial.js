// M8: radial (pie) menu. A round button opens a circle of six sector wedges, one per section. Moving
// onto a sector (or clicking it) fans its six pages out into an outer ring; clicking a page goes there.
// Spatial and gesture-like: the sectors and pages always sit at the same angles.
//   inner ring  r0..r1 : sections (the centre is a Close button)
//   outer ring  r1..r2 : the pages of the section under the pointer
export default function create(api) {
  const { site, params, esc, icon } = api;
  const r0 = params.inner_radius_px || 70;
  const r1 = params.mid_radius_px || 150;
  const r2 = params.outer_radius_px || 235;
  const GAP = 1.4;                                   // degrees between wedges
  const STEP = 360 / site.sections.length;
  const pad = 14;
  const timers = {};
  let ringFor = null;

  api.slots.nav.innerHTML = `
    <nav class="nav nav-radial" data-menu-root aria-label="Main menu">
      <button class="radial-btn" aria-expanded="false" aria-haspopup="true"><span class="radial-dot">${icon('grid')}</span><span>Menu</span></button>
      <button class="nav-item nav-home" data-home>${icon('home')}Home</button>
    </nav>`;
  api.slots.overlay.innerHTML = `
    <div class="radial-wrap" hidden>
      <div class="radial-backdrop"></div>
      <div class="radial" data-menu-root>
        <svg viewBox="${-(r2 + pad)} ${-(r2 + pad)} ${2 * (r2 + pad)} ${2 * (r2 + pad)}" role="menu" aria-label="Site menu">
          <g class="sectors"></g>
          <g class="ring"></g>
          <g class="centre" tabindex="0" role="button" aria-label="Close menu"><circle r="${r0 - 6}"></circle><text class="centre-label" text-anchor="middle" dy=".35em">Close</text></g>
        </svg>
      </div>
    </div>`;
  const bar = api.slots.nav.querySelector('.nav');
  const wrap = api.slots.overlay.querySelector('.radial-wrap');
  const btn = bar.querySelector('.radial-btn');
  const sectorsG = wrap.querySelector('.sectors');
  const ringG = wrap.querySelector('.ring');

  const NS = 'http://www.w3.org/2000/svg';
  const pt = (r, deg) => [r * Math.cos((deg * Math.PI) / 180), r * Math.sin((deg * Math.PI) / 180)];
  const centreAngle = (i) => -90 + i * STEP;           // first sector straight up

  function wedgePath(inner, outer, a0, a1) {
    const [x0, y0] = pt(outer, a0);
    const [x1, y1] = pt(outer, a1);
    const [x2, y2] = pt(inner, a1);
    const [x3, y3] = pt(inner, a0);
    return `M${x0.toFixed(1)} ${y0.toFixed(1)} A${outer} ${outer} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)} L${x2.toFixed(1)} ${y2.toFixed(1)} A${inner} ${inner} 0 0 0 ${x3.toFixed(1)} ${y3.toFixed(1)}Z`;
  }

  function lines(text, max) {
    const out = [];
    let cur = '';
    text.split(' ').forEach((w) => {
      if (cur && (cur + ' ' + w).length > max) { out.push(cur); cur = w; } else cur = cur ? `${cur} ${w}` : w;
    });
    if (cur) out.push(cur);
    return out;
  }

  function wedge(inner, outer, i, label, cls, maxChars) {
    const g = document.createElementNS(NS, 'g');
    g.setAttribute('class', `wedge ${cls}`);
    g.setAttribute('tabindex', '0');
    g.setAttribute('role', 'menuitem');
    const c = centreAngle(i);
    const path = document.createElementNS(NS, 'path');
    path.setAttribute('d', wedgePath(inner, outer, c - STEP / 2 + GAP, c + STEP / 2 - GAP));
    const [tx, ty] = pt((inner + outer) / 2, c);
    const text = document.createElementNS(NS, 'text');
    text.setAttribute('text-anchor', 'middle');
    const ls = lines(label, maxChars);
    ls.forEach((l, k) => {
      const t = document.createElementNS(NS, 'tspan');
      t.setAttribute('x', tx.toFixed(1));
      t.setAttribute('y', (ty + (k - (ls.length - 1) / 2) * 14.5 + 4.5).toFixed(1));
      t.textContent = l;
      text.appendChild(t);
    });
    g.append(path, text);
    return g;
  }

  site.sections.forEach((s, i) => {
    const g = wedge(r0, r1, i, s.title, 'sec', 11);
    sectorsG.appendChild(g);
    const show = () => showRing(s.id);
    api.item(g, { id: `nav:${s.id}`, level: 'section', section: s.id }, show);
    g.addEventListener('mouseenter', () => { clearTimeout(timers.ring); timers.ring = setTimeout(show, 90); });
    g.addEventListener('mouseleave', () => clearTimeout(timers.ring));
    g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') g.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
  });

  function showRing(sid) {
    if (ringFor === sid) return;
    ringFor = sid;
    ringG.innerHTML = '';
    sectorsG.querySelectorAll('.wedge').forEach((g) => g.classList.toggle('on', g.dataset.aoi === `nav:${sid}`));
    if (!sid) return;
    const section = site.sections.find((x) => x.id === sid);
    section.pages.forEach((p, i) => {
      const g = wedge(r1 + 4, r2, i, p.title, 'page', 13);
      ringG.appendChild(g);
      api.item(g, { id: `item:${sid}/${p.id}`, level: 'page', section: sid, page: p.id });
      g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') g.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
    });
  }

  function setMenu(on) {
    wrap.hidden = !on;
    btn.setAttribute('aria-expanded', on);
    btn.classList.toggle('open', on);
    if (!on) {
      clearTimeout(timers.ring);
      ringFor = null;
      ringG.innerHTML = '';
      sectorsG.querySelectorAll('.wedge').forEach((g) => g.classList.remove('on'));
    }
  }

  api.item(btn, { id: 'nav:menu', level: 'control' }, () => {
    const on = api.open !== 'radial';
    setMenu(on);
    api.setOpen(on ? 'radial' : null, on ? 'click' : 'toggle');
  });
  const centre = wrap.querySelector('.centre');
  api.item(centre, { id: 'nav:close', level: 'control' }, () => {
    setMenu(false);
    api.setOpen(null, 'close');
  });
  centre.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') centre.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
  api.item(bar.querySelector('[data-home]'), { id: 'nav:home', level: 'home' });

  return {
    // "the menu closes unexpectedly" = the radial menu dismisses itself
    collapse(reason) {
      if (api.open == null) return false;
      setMenu(false);
      api.setOpen(null, reason);
      return true;
    },
    reset() { setMenu(false); },
    onCommit() {
      setMenu(false);
      api.setOpen(null, 'select');
    },
    plan(section, page) {
      const acts = [];
      if (api.open !== 'radial') acts.push({ do: 'click', aoi: 'nav:menu', wait: 250 });
      acts.push({ do: 'hover', aoi: `nav:${section}`, wait: 300 }, { do: 'click', aoi: `item:${section}/${page}` });
      return acts;
    },
  };
}
