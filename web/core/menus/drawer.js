// M7: hamburger drawer (mobile style). Everything is hidden behind a menu button at the top left.
// Press it to slide a drawer in from the left, press a section to unfold its pages (one at a time),
// press a page. Closing the drawer forgets which section was unfolded, so reaching any page always
// takes three presses.
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
        <ul class="acc">
          ${site.sections.map((s) => `
            <li class="acc-sec" data-section="${s.id}">
              <button class="acc-head" data-section="${s.id}" aria-expanded="false">${icon(s.icon, 'acc-icon')}<span>${esc(s.title)}</span>${icon('chevron', 'chev')}</button>
              <ul class="acc-pages" hidden>${s.pages.map((p) => `<li><button class="acc-page" data-page="${p.id}">${esc(p.title)}</button></li>`).join('')}</ul>
            </li>`).join('')}
        </ul>
      </aside>
    </div>`;
  const bar = api.slots.nav.querySelector('.nav');
  const wrap = api.slots.overlay.querySelector('.drawer-wrap');
  const burger = bar.querySelector('.hamburger');
  let expanded = null;                       // the unfolded accordion section, for plan()

  function setDrawer(on) {
    wrap.hidden = !on;
    burger.setAttribute('aria-expanded', on);
    burger.classList.toggle('open', on);
    if (!on) {
      expanded = null;
      wrap.querySelectorAll('.acc-sec').forEach((li) => {
        li.classList.remove('open');
        li.querySelector('.acc-pages').hidden = true;
        li.querySelector('.acc-head').setAttribute('aria-expanded', false);
      });
    }
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
  wrap.querySelectorAll('.acc-sec').forEach((li) => {
    const sid = li.dataset.section;
    api.item(li.querySelector('.acc-head'), { id: `nav:${sid}`, level: 'section', section: sid }, () => {
      const wasOpen = li.classList.contains('open');
      wrap.querySelectorAll('.acc-sec').forEach((o) => {
        const on = o === li && !wasOpen;
        o.classList.toggle('open', on);
        o.querySelector('.acc-pages').hidden = !on;
        o.querySelector('.acc-head').setAttribute('aria-expanded', on);
      });
      expanded = wasOpen ? null : sid;
    });
    li.querySelectorAll('.acc-page').forEach((b) => {
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
