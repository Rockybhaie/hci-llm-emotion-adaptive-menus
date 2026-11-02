// M7: hamburger drawer (mobile style) with drill-down navigation. Everything is hidden behind a menu button at the
// top left. Press it to slide a large drawer over the page; it first lists only the sections. Pressing a section
// slides to a second screen holding that section's pages (with a Back button); press a page. Closing the drawer
// returns it to the section list, so reaching any page always takes three presses.
export default function create(api) {
  const { site, esc, icon } = api;

  api.slots.nav.innerHTML = `
    <nav class="nav nav-drawer" data-menu-root aria-label="Main menu">
      <button class="hamburger" aria-expanded="false" aria-haspopup="true">${icon('menu')}<span>Menu</span></button>
      <button class="nav-item nav-home" data-home>${icon('home')}Home</button>
    </nav>`;
  api.slots.overlay.innerHTML = `
    <div class="drawer-wrap" hidden>
      <div class="drawer-backdrop"></div>
      <aside class="drawer" data-menu-root aria-label="Site menu">
        <div class="drawer-head"><span>Menu</span><button class="drawer-close" aria-label="Close menu">${icon('x')}</button></div>
        <div class="drill-views">
          <ul class="acc drill-root">
            ${site.sections.map((s) => `
              <li><button class="acc-head" data-section="${s.id}">${icon(s.icon, 'acc-icon')}<span>${esc(s.title)}</span>${icon('chevron', 'chev')}</button></li>`).join('')}
          </ul>
          ${site.sections.map((s) => `
            <div class="drill-view" data-section="${s.id}" hidden>
              <button class="drill-back" data-back>${icon('chevron', 'chev')}<span>${esc(s.title)}</span></button>
              <ul class="acc-pages">${s.pages.map((p) => `<li><button class="acc-page" data-page="${p.id}">${esc(p.title)}</button></li>`).join('')}</ul>
            </div>`).join('')}
        </div>
      </aside>
    </div>`;
  const bar = api.slots.nav.querySelector('.nav');
  const wrap = api.slots.overlay.querySelector('.drawer-wrap');
  const burger = bar.querySelector('.hamburger');
  const rootList = wrap.querySelector('.drill-root');
  const views = [...wrap.querySelectorAll('.drill-view')];
  let expanded = null;                       // the section whose page screen is showing, for plan()

  function show(sid) {
    expanded = sid;
    rootList.hidden = sid != null;
    views.forEach((v) => { v.hidden = v.dataset.section !== sid; });
    wrap.querySelector('.drawer-head span').textContent = 'Menu';
  }

  function setDrawer(on) {
    wrap.hidden = !on;
    burger.setAttribute('aria-expanded', on);
    burger.classList.toggle('open', on);
    if (!on) show(null);
  }

  api.item(burger, { id: 'nav:menu', level: 'control' }, () => {
    const on = api.open !== 'drawer';
    setDrawer(on);
    api.setOpen(on ? 'drawer' : null, on ? 'click' : 'toggle');
  });
  api.item(wrap.querySelector('.drawer-close'), { id: 'nav:close', level: 'control' }, () => {
    setDrawer(false);
    api.setOpen(null, 'close');
  });
  wrap.querySelectorAll('.acc-head').forEach((b) => {
    const sid = b.dataset.section;
    api.item(b, { id: `nav:${sid}`, level: 'section', section: sid }, () => show(sid));
  });
  views.forEach((v) => {
    const sid = v.dataset.section;
    api.item(v.querySelector('[data-back]'), { id: `nav:back:${sid}`, level: 'control' }, () => show(null));
    v.querySelectorAll('.acc-page').forEach((b) => {
      api.item(b, { id: `item:${sid}/${b.dataset.page}`, level: 'page', section: sid, page: b.dataset.page });
    });
  });
  api.item(bar.querySelector('[data-home]'), { id: 'nav:home', level: 'home' });

  return {
    collapse(reason) {
      if (api.open == null) return false;
      setDrawer(false);
      api.setOpen(null, reason);
      return true;
    },
    reset() { setDrawer(false); },
    onCommit() {
      setDrawer(false);
      api.setOpen(null, 'select');
    },
    plan(section, page) {
      const acts = [];
      if (api.open !== 'drawer') acts.push({ do: 'click', aoi: 'nav:menu', wait: 300 });
      if (expanded !== section) acts.push({ do: 'click', aoi: `nav:${section}`, wait: 150 });
      acts.push({ do: 'click', aoi: `item:${section}/${page}` });
      return acts;
    },
  };
}
