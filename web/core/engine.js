// Site engine shared by all three websites.
// The standard drop-down menu is the ONLY way to move between pages, so every
// navigation in the data is a menu interaction. Runs inside the participant
// shell's iframe (logs through parent.HCI.site) or standalone for preview.
import { icon } from './icons.js';

const params = new URLSearchParams(location.search);
const siteId = params.get('site');
const host = window.parent !== window && window.parent.HCI ? window.parent.HCI.site : null;

const HOVER_OPEN_MS = 150;
const LEAVE_CLOSE_MS = 400;

const state = {
  site: null,
  current: null,        // null = home, else {section, page}
  open: null,           // id of the open section
  hovered: null,
  loading: false,
  sabotage: null,
};
const timers = {};
const $app = document.getElementById('app');

function log(event, fields = {}) {
  if (host) host.log({ event, ...fields });
  else if (params.has('debug')) console.debug('[site]', event, fields);
}

const rand = (a, b) => a + Math.random() * (b - a);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const chance = (key) => state.sabotage && Math.random() < (state.sabotage[key] || 0);

// ------------------------------------------------------------------ AOIs
function rects(selector) {
  return [...document.querySelectorAll(selector)].map((el) => {
    const r = el.getBoundingClientRect();
    return { id: el.dataset.aoi, x0: r.left, y0: r.top, x1: r.right, y1: r.bottom };
  }).filter((r) => r.x1 > r.x0 && r.y1 > r.y0 && r.y1 > 0 && r.y0 < innerHeight);
}
function snapshotMenu() { host?.aoi('menu', rects('.nav [data-aoi]')); }
function snapshotContent() { host?.aoi('content', rects('main [data-aoi]')); }

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

function nav(site) {
  const sections = site.sections.map((s) => `
    <li class="nav-li" data-section="${s.id}">
      <button class="nav-item" data-section="${s.id}" data-aoi="nav:${s.id}" aria-expanded="false" aria-haspopup="true">
        ${esc(s.title)}${icon('chevron', 'chev')}
      </button>
      <div class="dropdown" role="menu" hidden>
        ${s.pages.map((p) => `<button class="dd-item" role="menuitem" data-section="${s.id}" data-page="${p.id}" data-aoi="item:${s.id}/${p.id}">${esc(p.title)}</button>`).join('')}
      </div>
    </li>`).join('');
  return `
    <nav class="nav" aria-label="Main menu">
      <ul class="nav-list">
        <li class="nav-li"><button class="nav-item nav-home" data-home data-aoi="nav:home">${icon('home')}Home</button></li>
        ${sections}
      </ul>
    </nav>`;
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

// ------------------------------------------------------------------ menu
function setOpen(sid, reason) {
  if (state.open === sid) return;
  const prev = state.open;
  clearTimeout(timers.glitch);
  document.querySelectorAll('.nav-li[data-section]').forEach((li) => {
    const on = li.dataset.section === sid;
    li.classList.toggle('open', on);
    li.querySelector('.nav-item').setAttribute('aria-expanded', on);
    li.querySelector('.dropdown').hidden = !on;
  });
  state.open = sid;
  state.hovered = null;
  if (sid) {
    log(prev ? 'menu_switch' : 'menu_open', { section: sid, detail: { trigger: reason, from: prev || undefined } });
    if (chance('menu_glitch_prob')) {
      timers.glitch = setTimeout(() => {
        if (state.open === sid) {
          log('sabotage_menu_glitch', { section: sid });
          setOpen(null, 'glitch');
        }
      }, rand(500, 1200));
    }
  } else if (prev) {
    log('menu_close', { section: prev, detail: { reason } });
  }
  requestAnimationFrame(snapshotMenu);
}

async function navigate(target, via) {
  if (state.loading) {
    log('click_while_loading', { section: target?.section, page: target?.page });
    return;
  }
  setOpen(null, 'select');
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
  log(target ? 'page_view' : 'home_view', { section: target?.section, page: target?.page, detail: { via } });
}

function dropped(what, fields) {
  if (!chance('drop_click_prob')) return false;
  log('sabotage_click_dropped', { ...fields, detail: { target: what } });
  return true;
}

function bindMenu() {
  const navEl = document.querySelector('.nav');
  navEl.querySelectorAll('.nav-li[data-section]').forEach((li) => {
    const sid = li.dataset.section;
    const btn = li.querySelector('.nav-item');
    btn.addEventListener('mouseenter', () => {
      clearTimeout(timers.hover);
      timers.hover = setTimeout(() => setOpen(sid, state.open ? 'hover-switch' : 'hover'), state.open ? 0 : HOVER_OPEN_MS);
    });
    btn.addEventListener('mouseleave', () => clearTimeout(timers.hover));
    btn.addEventListener('click', () => {
      if (dropped('section', { section: sid })) return;
      setOpen(state.open === sid ? null : sid, state.open === sid ? 'toggle' : 'click');
    });
    li.addEventListener('mouseenter', () => clearTimeout(timers.leave));
    li.addEventListener('mouseleave', () => {
      clearTimeout(timers.leave);
      timers.leave = setTimeout(() => state.open === sid && setOpen(null, 'leave'), LEAVE_CLOSE_MS);
    });
  });
  navEl.querySelectorAll('.dd-item').forEach((item) => {
    const fields = { section: item.dataset.section, page: item.dataset.page };
    item.addEventListener('mouseenter', () => {
      const key = `${fields.section}/${fields.page}`;
      if (state.hovered !== key) {
        state.hovered = key;
        log('menu_hover', fields);
      }
    });
    item.addEventListener('click', () => {
      if (dropped('item', fields)) return;
      log('menu_select', fields);
      navigate(fields, 'menu');
    });
  });
  navEl.querySelector('[data-home]').addEventListener('click', () => {
    if (dropped('home', {})) return;
    log('menu_select', { detail: { target: 'home' } });
    navigate(null, 'home');
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && state.open) setOpen(null, 'escape');
  });
  document.addEventListener('click', (e) => {
    if (state.open && !e.target.closest('.nav')) setOpen(null, 'outside');
  });
}

function bindLogging() {
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
    }, 200);
  }, { passive: true });
  addEventListener('resize', () => { snapshotMenu(); snapshotContent(); });
}

// ------------------------------------------------------------------ API
let resolveReady;
const ready = new Promise((r) => { resolveReady = r; });

window.SiteEngine = {
  ready,
  configure(opts = {}) {
    state.sabotage = opts.sabotage || null;
  },
  reset() {
    clearTimeout(timers.glitch);
    state.loading = false;
    document.body.classList.remove('loading');
    setOpen(null, 'reset');
    state.current = null;
    window.scrollTo(0, 0);
    renderMain();
    requestAnimationFrame(snapshotMenu);
  },
};

async function boot() {
  const site = await (await fetch(`/sites/${siteId}/site.json`)).json();
  state.site = site;
  document.title = `${site.name} · ${site.tagline}`;
  document.getElementById('theme').href = `/sites/${siteId}/theme.css`;
  document.documentElement.dataset.layout = site.layout;
  $app.innerHTML = `
    <div class="top">${header(site)}${nav(site)}</div>
    <div class="loader" aria-hidden="true"><div class="loader-bar"></div><div class="spinner"></div></div>
    <main class="main"></main>
    <footer class="footer">© ${new Date().getFullYear()} ${esc(site.name)} · Help · Privacy · Accessibility</footer>`;
  $app.removeAttribute('aria-busy');
  bindMenu();
  bindLogging();
  if (!host && params.get('page')) {            // preview only: deep-link a page / open a menu
    const [section, page] = params.get('page').split('/');
    state.current = { section, page };
  }
  renderMain();
  if (!host && params.get('open')) setOpen(params.get('open'), 'preview');
  snapshotMenu();
  resolveReady();
}

boot();
