// Site engine shared by all three websites and all nine menus.
//
// The engine owns everything that must be identical across menus: page rendering, the
// event log, the area-of-interest (AOI) snapshots, the emotion-induction faults (lag, ignored
// clicks, a menu that collapses by itself) and the visit / backtrack bookkeeping.
// A menu is a plug-in (web/core/menus/*.js, see MENUS.md) that only draws itself and talks to
// the engine through the `api` object below. The engine never knows which menu it is running.
//
// Runs inside the participant shell's iframe (logs through parent.HCI.site) or standalone
// for preview (`/core/site.html?site=g2-store&menu=M5&debug`).
import { icon } from './icons.js';
import { loadMenu } from './menus/registry.js';

const params = new URLSearchParams(location.search);
const siteId = params.get('site');
const menuId = params.get('menu') || 'M1';
// `?record=1` (tests, dry runs) collects what would be logged in window.__events / window.__aoi.
const sink = params.has('record')
  ? { log: (e) => (window.__events ||= []).push({ ...e, t: performance.now() }), aoi: (kind, rects) => (window.__aoi ||= []).push({ kind, rects }), mouse() {} }
  : null;
const host = window.parent !== window && window.parent.HCI ? window.parent.HCI.site : sink;

const state = {
  site: null,
  menu: null,           // {id, type, name, label, how, params} from config/menus.yaml
  ctrl: null,           // the running menu plug-in
  current: null,        // null = home, else {section, page}
  open: null,           // key of whatever the menu has expanded, or null when it is at rest
  loading: false,
  sabotage: null,
  visited: new Set(['home']),   // locations visited in the current task (home counts: the task starts there)
  glitchArmed: false,
};
const timers = {};
const hovered = new Map();       // element -> {meta, t}
const $app = document.getElementById('app');

const rand = (a, b) => a + Math.random() * (b - a);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const chance = (key) => state.sabotage && Math.random() < (state.sabotage[key] || 0);
const isSection = (key) => Boolean(state.site.sections.find((s) => s.id === key));

// ------------------------------------------------------------------ logging
let debugPanel = null;
function log(event, fields = {}) {
  if (host) host.log({ event, ...fields });
  if (debugPanel) {
    const line = document.createElement('div');
    const where = [fields.section, fields.page].filter(Boolean).join('/');
    line.textContent = `${event}${fields.item ? ' ' + fields.item : where ? ' ' + where : ''}${fields.detail ? ' ' + JSON.stringify(fields.detail) : ''}`;
    debugPanel.prepend(line);
    while (debugPanel.children.length > 14) debugPanel.lastChild.remove();
  }
}

// ------------------------------------------------------------------ AOIs
// Every menu item carries data-aoi="nav:<id>" or "item:<section>/<page>". Hidden items have no
// layout box and are skipped, so the snapshot is exactly "what the participant could point at now".
const MENU_AOI = '[data-aoi^="nav:"], [data-aoi^="item:"]';
let lastSignature = '';

function rects(selector) {
  return [...document.querySelectorAll(selector)].map((el) => {
    const r = el.getBoundingClientRect();
    return { id: el.dataset.aoi, x0: r.left, y0: r.top, x1: r.right, y1: r.bottom };
  }).filter((r) => r.x1 > r.x0 && r.y1 > r.y0 && r.y1 > 0 && r.y0 < innerHeight && r.x1 > 0 && r.x0 < innerWidth);
}

function snapshotMenu(force = false) {
  const list = rects(MENU_AOI);
  const signature = list.map((r) => `${r.id}:${Math.round(r.x0)},${Math.round(r.y0)},${Math.round(r.x1)},${Math.round(r.y1)}`).join('|');
  if (!force && signature === lastSignature) return;
  lastSignature = signature;
  host?.aoi('menu', list);
}
function snapshotContent() { host?.aoi('content', rects('main [data-aoi]')); }

function flushHovers() {
  for (const [el, h] of hovered) {
    if (!el.isConnected || el.getClientRects().length === 0) {
      hovered.delete(el);
      log('item_hover_exit', { ...fieldsOf(h.meta), detail: { dwell_ms: Math.round(performance.now() - h.t), reason: 'hidden' } });
    }
  }
}

function scheduleSnapshot() {
  cancelAnimationFrame(timers.raf);
  timers.raf = requestAnimationFrame(() => { flushHovers(); snapshotMenu(); });
  clearTimeout(timers.snap);
  timers.snap = setTimeout(() => snapshotMenu(), 260);   // again after open/close animations settle
}

// ------------------------------------------------------------------ shell
function header(site) {
  const util = {
    'g2-store': `<span class="util">${icon('pin')} Deliver to <b>Home</b></span><span class="util cart">${icon('cart')}<span class="badge">0</span></span>`,
    'g1-portal': `<span class="util">${icon('bell')}</span><span class="util avatar"><span class="avatar-dot">AM</span>Alex Morgan</span>`,
    'g3-forum': `<span class="util">${icon('bell')}</span><span class="util avatar"><span class="avatar-dot">M</span>maple_42</span>`,
  }[site.id] || '';
  return `
    <header class="brandbar">
      <div class="brand">
        <span class="logo">${icon(site.brand_icon)}</span>
        <span class="brand-text"><span class="brand-name">${esc(site.name)}</span><span class="brand-tag">${esc(site.tagline)}</span></span>
      </div>
      <div class="utils">${util}</div>
    </header>`;
}

// ------------------------------------------------------------------ pages
function tile(name, iconName) {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) % 360;
  return `<div class="tile" style="--h:${h}">${icon(iconName, 'tile-icon')}</div>`;
}

function stars(value) {
  const full = Math.round(Number(value));
  return `<span class="stars" aria-label="${value} out of 5">${[1, 2, 3, 4, 5].map((i) => icon('star', i <= full ? 'star on' : 'star', true)).join('')}</span>`;
}

function renderProducts(page, section) {
  return `<div class="grid">${page.items.map((it) => {
    const v = it.values;
    const stock = v.Availability === 'In stock' ? 'ok' : 'low';
    return `
      <article class="card product" data-aoi="content:${it.id}">
        ${tile(it.name, section.icon)}
        <div class="product-body">
          <h3 class="product-name">${esc(it.name)}</h3>
          <div class="rating">${stars(v.Rating)}<span class="rating-num">${esc(v.Rating)}</span><span class="muted">(${esc(v.Reviews)})</span></div>
          <div class="price">${esc(v.Price)}</div>
          <div class="meta-row"><span class="chip chip-${stock}">${esc(v.Availability)}</span><span class="code">Item code ${esc(v['Item code'])}</span></div>
        </div>
      </article>`;
  }).join('')}</div>`;
}

function renderTable(page) {
  const cols = page.columns;
  return `
    <div class="card table-card">
      <table class="table">
        <thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead>
        <tbody>${page.items.map((it) => `
          <tr data-aoi="content:${it.id}">
            <td class="strong">${esc(it.name)}</td>
            ${cols.slice(1).map((c) => `<td class="${c === 'Reference' ? 'code' : ''}">${esc(it.values[c] ?? '')}</td>`).join('')}
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}

function renderThreads(page) {
  return `<div class="card threads">${page.items.map((it) => {
    const v = it.values;
    return `
      <article class="thread" data-aoi="content:${it.id}">
        <div class="votes">${icon('up', 'vote-icon')}<span>${esc(v.Votes)}</span></div>
        <div class="thread-body">
          <h3 class="thread-title">${esc(it.name)}</h3>
          <div class="thread-meta"><span class="chip flair">${esc(v.Flair)}</span><span>by <b>${esc(v.Author)}</b></span><span>·</span><span>${esc(v.Posted)}</span></div>
        </div>
        <div class="replies">${icon('message')}<span>${esc(v.Replies)}</span><small>replies</small></div>
      </article>`;
  }).join('')}</div>`;
}

function renderHome(site) {
  const h = site.home;
  return `
    <section class="hero">
      <h1>${esc(h.headline)}</h1>
      <p>${esc(h.sub)}</p>
    </section>
    <section class="highlights">
      ${h.highlights.map(([ic, title, text]) => `
        <div class="card highlight">${icon(ic, 'hl-icon')}<div><div class="hl-title">${esc(title)}</div><div class="muted">${esc(text)}</div></div></div>`).join('')}
    </section>
    <section class="overview">
      <h2>Explore</h2>
      <div class="overview-grid">
        ${site.sections.map((s) => `
          <div class="overview-item">${icon(s.icon, 'ov-icon')}<div><div class="ov-title">${esc(s.title)}</div><div class="muted">${s.pages.slice(0, 3).map((p) => esc(p.title)).join(' · ')} …</div></div></div>`).join('')}
      </div>
    </section>`;
}

function findPage(sid, pid) {
  const section = state.site.sections.find((s) => s.id === sid);
  return { section, page: section?.pages.find((p) => p.id === pid) };
}

function renderMain() {
  const main = document.querySelector('main');
  const site = state.site;
  if (!state.current) {
    main.innerHTML = `<div class="crumbs">Home</div>${renderHome(site)}`;
  } else {
    const { section, page } = findPage(state.current.section, state.current.page);
    const body = { products: renderProducts, table: renderTable, threads: renderThreads }[site.layout](page, section);
    main.innerHTML = `
      <div class="crumbs">Home <span>›</span> ${esc(section.title)} <span>›</span> <b>${esc(page.title)}</b></div>
      <header class="page-head"><h1>${esc(page.title)}</h1><p class="muted">${esc(page.intro)}</p></header>
      ${body}`;
  }
  main.classList.remove('enter');
  void main.offsetWidth;
  main.classList.add('enter');
  requestAnimationFrame(snapshotContent);
}

// ------------------------------------------------------------------ menu state + faults
// The menu reports what it has expanded through setOpen(); menu_open / menu_close are emitted here,
// identically for every menu. `key` is a section id for menus that expand one section at a time,
// or the name of the panel ('drawer', 'radial', 'search', 'browse').

/** One glitch per navigation attempt (with probability menu_glitch_prob), fired once the menu is expanded. */
function armAttempt() {
  state.glitchArmed = Boolean(chance('menu_glitch_prob'));
  maybeGlitch();
}

function maybeGlitch() {
  if (!state.glitchArmed || state.open == null || timers.glitch) return;
  state.glitchArmed = false;
  const key = state.open;
  timers.glitch = setTimeout(() => {
    timers.glitch = null;
    if (state.open === key) {
      log('sabotage_menu_glitch', { section: isSection(key) ? key : '', detail: { panel: key } });
      state.ctrl.collapse('glitch');
    }
  }, rand(500, 1200));
}

function setOpen(key, reason = '') {
  const prev = state.open;
  if (prev === key) return;
  if (timers.glitch) {                 // the participant acted before the glitch fired: keep it for later
    clearTimeout(timers.glitch);
    timers.glitch = null;
    state.glitchArmed = true;
  }
  state.open = key;
  if (prev != null) {
    log('menu_close', { section: isSection(prev) ? prev : '', detail: { reason: key == null ? reason : 'switch', panel: prev, state: 'closed' } });
  }
  if (key != null) {
    log('menu_open', { section: isSection(key) ? key : '', detail: { trigger: reason, panel: key, from: prev ?? undefined, state: `open:${key}` } });
    maybeGlitch();
  }
  scheduleSnapshot();
}

// ------------------------------------------------------------------ items, selection, navigation
function fieldsOf(meta) {
  return { item: meta.id, section: meta.section || '', page: meta.page || '' };
}

/**
 * Register one menu item. The engine logs hover enter/exit and selection and applies the faults;
 * `onSelect` is only used for items that expand something (level 'section' or 'control').
 * meta = {id, level: 'section' | 'page' | 'home' | 'control', section?, page?}
 */
function item(el, meta, onSelect) {
  el.dataset.aoi = meta.id;
  el.addEventListener('mouseenter', () => {
    hovered.set(el, { meta, t: performance.now() });
    log('item_hover_enter', fieldsOf(meta));
  });
  el.addEventListener('mouseleave', () => {
    const h = hovered.get(el);
    hovered.delete(el);
    log('item_hover_exit', { ...fieldsOf(meta), detail: { dwell_ms: h ? Math.round(performance.now() - h.t) : undefined } });
  });
  el.addEventListener('click', () => select(meta, 'click', onSelect));
}

function select(meta, via, onSelect) {
  const commit = meta.level === 'page' || meta.level === 'home';
  if (commit) {
    if (state.loading) {
      log('click_while_loading', { section: meta.section, page: meta.page });
      return;
    }
    if (chance('drop_click_prob')) {        // the committing click is silently ignored
      log('sabotage_click_dropped', { ...fieldsOf(meta), detail: { target: meta.level, via } });
      return;
    }
  }
  log('item_select', { ...fieldsOf(meta), detail: { level: meta.level, via } });
  if (commit) navigate(meta.level === 'home' ? null : { section: meta.section, page: meta.page }, via);
  else onSelect?.();
}

async function navigate(target, via) {
  state.ctrl.onCommit?.(target);
  if (chance('lag_prob')) {
    const ms = Math.round(rand(state.sabotage.lag_min_ms, state.sabotage.lag_max_ms));
    log('sabotage_lag', { section: target?.section, page: target?.page, detail: { ms } });
    state.loading = true;
    document.body.classList.add('loading');
    await sleep(ms);
    document.body.classList.remove('loading');
    state.loading = false;
  }
  state.current = target;
  window.scrollTo(0, 0);
  renderMain();
  const key = target ? `${target.section}/${target.page}` : 'home';
  const seen = state.visited.has(key);
  state.visited.add(key);
  log(target ? 'page_view' : 'home_view', { section: target?.section, page: target?.page, detail: { via } });
  // A backtrack is a navigation to a location already visited earlier in the same task
  // (home counts as visited, because every task starts there).
  if (seen) log('backtrack', { section: target?.section || '', page: target?.page || '', detail: { to: key } });
  state.ctrl.onPage?.(target);
  armAttempt();
}

function bindGlobal() {
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && state.open != null) state.ctrl.collapse('escape');
  });
  document.addEventListener('click', (e) => {
    if (state.open != null && !e.target.closest('[data-menu-root]')) state.ctrl.collapse('outside');
  });
  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-aoi]');
    log('click', { x: e.clientX, y: e.clientY, detail: { target: el ? el.dataset.aoi : e.target.tagName.toLowerCase() } });
  }, true);
  document.addEventListener('mousemove', (e) => host?.mouse(e.clientX, e.clientY), { passive: true });
  let scrollTimer;
  addEventListener('scroll', () => {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      log('scroll', { detail: { y: Math.round(scrollY) } });
      snapshotContent();
      snapshotMenu();
    }, 200);
  }, { passive: true });
  addEventListener('resize', () => { snapshotMenu(true); snapshotContent(); });
}

// ------------------------------------------------------------------ the object menus talk to
const api = {
  site: null,
  params: {},
  slots: {},
  esc,
  icon,
  item,
  select,
  setOpen,
  log,
  /** key of whatever the menu has expanded, or null */
  get open() { return state.open; },
  /** true once the page is showing (menus may highlight the current location) */
  get current() { return state.current; },
};

// ------------------------------------------------------------------ public API (shell + tests)
let resolveReady;
const ready = new Promise((r) => { resolveReady = r; });

window.SiteEngine = {
  ready,
  configure(opts = {}) {
    state.sabotage = opts.sabotage || null;
    armAttempt();
  },
  /** Start a task: home page, menu at rest, visit history cleared. */
  reset() {
    clearTimeout(timers.glitch);
    timers.glitch = null;
    state.loading = false;
    document.body.classList.remove('loading');
    state.ctrl.reset();
    setOpen(null, 'reset');
    state.current = null;
    state.visited = new Set(['home']);
    window.scrollTo(0, 0);
    renderMain();
    armAttempt();
    scheduleSnapshot();
  },
  menu: () => ({ ...state.menu }),
  /** Every on-screen menu item right now, as {id, x0, y0, x1, y1} in iframe pixels. */
  menuRects: () => rects(MENU_AOI),
  menuState: () => ({ open: state.open, current: state.current }),
  /** Actions that reach (section, page) from the menu's current state; used by tests and dry runs. */
  plan: (section, page) => state.ctrl.plan(section, page),
};

async function boot() {
  const site = await (await fetch(`/sites/${siteId}/site.json`)).json();
  const menus = await (await fetch('/api/menus')).json();
  state.site = site;
  state.menu = menus[menuId];
  if (!state.menu) throw new Error(`Unknown menu ${menuId}`);
  document.title = `${site.name} · ${site.tagline}`;
  document.getElementById('theme').href = `/sites/${siteId}/theme.css`;
  document.documentElement.dataset.layout = site.layout;
  document.body.dataset.menu = menuId;
  document.body.dataset.menuType = state.menu.type;
  $app.innerHTML = `
    <div class="top">${header(site)}<div class="nav-slot" id="nav-slot"></div></div>
    <div class="body-wrap">
      <aside class="side-slot" id="side-slot" hidden></aside>
      <div class="content-col">
        <div class="loader" aria-hidden="true"><div class="loader-bar"></div><div class="spinner"></div></div>
        <main class="main"></main>
        <footer class="footer">© ${new Date().getFullYear()} ${esc(site.name)} · Help · Privacy · Accessibility</footer>
      </div>
    </div>
    <div class="overlay-slot" id="overlay-slot"></div>`;
  $app.removeAttribute('aria-busy');
  api.site = site;
  api.params = state.menu.params || {};
  api.slots = {
    nav: document.getElementById('nav-slot'),
    side: document.getElementById('side-slot'),
    overlay: document.getElementById('overlay-slot'),
  };

  const top = document.querySelector('.top');
  const syncTop = () => document.documentElement.style.setProperty('--top-h', `${top.offsetHeight}px`);
  new ResizeObserver(syncTop).observe(top);
  syncTop();

  if (params.has('debug')) {
    debugPanel = document.createElement('div');
    debugPanel.className = 'debug-panel';
    document.body.appendChild(debugPanel);
  }

  const { default: factory } = await loadMenu(state.menu.type);
  state.ctrl = factory(api);
  new MutationObserver(scheduleSnapshot).observe($app, {
    subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'hidden', 'style', 'aria-expanded'],
  });
  bindGlobal();
  if (!host && params.get('page')) {            // preview only: deep-link a page
    const [section, page] = params.get('page').split('/');
    state.current = { section, page };
    state.visited.add(`${section}/${page}`);
  }
  renderMain();
  if (!host && params.get('open')) state.ctrl.openSection?.(params.get('open'));
  snapshotMenu(true);
  armAttempt();
  resolveReady();
}

boot();
