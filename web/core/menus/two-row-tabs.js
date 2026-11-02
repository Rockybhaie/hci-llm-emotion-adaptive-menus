// M9: always-visible two-row tab bar. Row 1 holds the six sections, row 2 the pages of the selected
// section. Nothing is ever hidden behind a hover or an overlay; the selected section stays selected
// after a page is chosen, so a second page in the same section costs one click.
export default function create(api) {
  const { site, esc, icon } = api;

  api.slots.nav.innerHTML = `
    <nav class="nav nav-tabs2" data-menu-root aria-label="Main menu">
      <ul class="nav-list tabs1">
        <li class="nav-li"><button class="nav-item nav-home" data-home>${icon('home')}Home</button></li>
        ${site.sections.map((s) => `
          <li class="nav-li"><button class="nav-item tab" data-section="${s.id}" aria-pressed="false">${esc(s.title)}</button></li>`).join('')}
      </ul>
      <div class="tabs2">
        <span class="tabs2-empty">Choose a section above to see its pages</span>
        ${site.sections.map((s) => `
          <div class="tabs2-row" data-section="${s.id}" hidden>
            ${s.pages.map((p) => `<button class="tab-page" data-page="${p.id}">${esc(p.title)}</button>`).join('')}
          </div>`).join('')}
      </div>
    </nav>`;
  const root = api.slots.nav.querySelector('.nav');
  const empty = root.querySelector('.tabs2-empty');

  function render(sid) {
    root.querySelectorAll('.tab').forEach((t) => {
      const on = t.dataset.section === sid;
      t.classList.toggle('open', on);
      t.setAttribute('aria-pressed', on);
    });
    root.querySelectorAll('.tabs2-row').forEach((row) => { row.hidden = row.dataset.section !== sid; });
    empty.hidden = sid != null;
  }

  function select(sid, reason) {
    render(sid);
    api.setOpen(sid, reason);
  }

  site.sections.forEach((s) => {
    api.item(root.querySelector(`.tab[data-section="${s.id}"]`), { id: `nav:${s.id}`, level: 'section', section: s.id },
      () => select(s.id, 'click'));
    root.querySelectorAll(`.tabs2-row[data-section="${s.id}"] .tab-page`).forEach((b) => {
      api.item(b, { id: `item:${s.id}/${b.dataset.page}`, level: 'page', section: s.id, page: b.dataset.page });
    });
  });
  api.item(root.querySelector('[data-home]'), { id: 'nav:home', level: 'home' });

  return {
    // "the menu closes unexpectedly" = the second row empties and no section stays selected
    collapse(reason) {
      if (api.open == null) return false;
      render(null);
      api.setOpen(null, reason);
      return true;
    },
    reset() {
      render(null);
      root.querySelectorAll('.current').forEach((el) => el.classList.remove('current'));
    },
    onPage(target) {
      root.querySelectorAll('.current').forEach((el) => el.classList.remove('current'));
      if (!target) return;
      root.querySelector(`.tab[data-section="${target.section}"]`)?.classList.add('current');
      root.querySelector(`[data-aoi="item:${target.section}/${target.page}"]`)?.classList.add('current');
    },
    openSection(sid) { select(sid, 'preview'); },
    plan(section, page) {
      const acts = [];
      if (api.open !== section) acts.push({ do: 'click', aoi: `nav:${section}`, wait: 150 });
      acts.push({ do: 'click', aoi: `item:${section}/${page}` });
      return acts;
    },
  };
}
