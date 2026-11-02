// M5: mega-menu. One "All pages" button in the bar (no per-section buttons, no hover). Clicking it opens a single
// full-width panel that shows every section as a headed column with all of its pages at once, so nothing has to be
// chosen or unfolded first: open the panel, scan, click the page. Closes on selection, Escape or an outside click.
export default function create(api) {
  const { site, esc, icon } = api;

  api.slots.nav.innerHTML = `
    <nav class="nav nav-mega" data-menu-root aria-label="Main menu">
      <ul class="nav-list">
        <li class="nav-li"><button class="nav-item nav-home" data-home>${icon('home')}Home</button></li>
        <li class="nav-li mega-li">
          <button class="nav-item mega-btn" aria-expanded="false" aria-haspopup="true">${icon('grid')}All pages${icon('chevron', 'chev')}</button>
          <div class="dropdown mega" role="menu" hidden>
            <div class="mega-grid">
              ${site.sections.map((s) => `
                <div class="mega-col" data-section="${s.id}">
                  <div class="mega-head">${icon(s.icon, 'mega-icon')}<span>${esc(s.title)}</span></div>
                  ${s.pages.map((p) => `<button class="mega-item" role="menuitem" data-section="${s.id}" data-page="${p.id}">${esc(p.title)}</button>`).join('')}
                </div>`).join('')}
            </div>
          </div>
        </li>
      </ul>
    </nav>`;
  const root = api.slots.nav.querySelector('.nav');
  const li = root.querySelector('.mega-li');
  const btn = li.querySelector('.mega-btn');
  const panel = li.querySelector('.dropdown');

  function render(on) {
    li.classList.toggle('open', on);
    btn.setAttribute('aria-expanded', on);
    panel.hidden = !on;
  }

  api.item(btn, { id: 'nav:all', level: 'control' }, () => {
    const on = api.open !== 'mega';
    render(on);
    api.setOpen(on ? 'mega' : null, on ? 'click' : 'toggle');
  });
  panel.querySelectorAll('.mega-item').forEach((b) => {
    api.item(b, { id: `item:${b.dataset.section}/${b.dataset.page}`, level: 'page', section: b.dataset.section, page: b.dataset.page });
  });
  api.item(root.querySelector('[data-home]'), { id: 'nav:home', level: 'home' });

  return {
    collapse(reason) {
      if (api.open == null) return false;
      render(false);
      api.setOpen(null, reason);
      return true;
    },
    reset() { render(false); },
    onCommit() {
      render(false);
      api.setOpen(null, 'select');
    },
    openSection() { render(true); api.setOpen('mega', 'preview'); },
    plan(section, page) {
      const acts = [];
      if (api.open !== 'mega') acts.push({ do: 'click', aoi: 'nav:all', wait: 200 });
      acts.push({ do: 'click', aoi: `item:${section}/${page}` });
      return acts;
    },
  };
}
