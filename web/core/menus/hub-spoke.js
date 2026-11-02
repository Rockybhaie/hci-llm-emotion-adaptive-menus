// M3: hub and spoke. Tabs for the six sections run along the top. Clicking one opens a hub of six
// large cards, one per page, over the content; clicking a card goes to the page. The hub stays open
// until a card is chosen, another tab is clicked, or the participant clicks away.
// Design idea: always two steps, with large forgiving targets (cards are at least 96 px tall).
export default function create(api) {
  const { site, esc, icon } = api;

  api.slots.nav.innerHTML = `
    <nav class="nav nav-hub" data-menu-root aria-label="Main menu">
      <ul class="nav-list">
        <li class="nav-li"><button class="nav-item nav-home" data-home>${icon('home')}Home</button></li>
        ${site.sections.map((s) => `
          <li class="nav-li" data-section="${s.id}"><button class="nav-item tab" data-section="${s.id}" aria-expanded="false">${esc(s.title)}</button></li>`).join('')}
      </ul>
      <div class="hub" hidden>
        ${site.sections.map((s) => `
          <section class="hub-section" data-section="${s.id}" hidden>
            <div class="hub-title">${icon(s.icon, 'hub-title-icon')}<span>${esc(s.title)}</span></div>
            <div class="hub-cards">
              ${s.pages.map((p) => `<button class="hub-card" data-page="${p.id}">${icon(s.icon, 'hub-card-icon')}<span>${esc(p.title)}</span></button>`).join('')}
            </div>
          </section>`).join('')}
      </div>
    </nav>`;
  const root = api.slots.nav.querySelector('.nav');
  const hub = root.querySelector('.hub');

  function render(sid) {
    root.querySelectorAll('.tab').forEach((t) => {
      const on = t.dataset.section === sid;
      t.classList.toggle('open', on);
      t.setAttribute('aria-expanded', on);
    });
    hub.hidden = sid == null;
    hub.querySelectorAll('.hub-section').forEach((el) => { el.hidden = el.dataset.section !== sid; });
  }

  function show(sid, reason) {
    render(sid);
    api.setOpen(sid, reason);
  }

  site.sections.forEach((s) => {
    api.item(root.querySelector(`.tab[data-section="${s.id}"]`), { id: `nav:${s.id}`, level: 'section', section: s.id }, () => {
      show(api.open === s.id ? null : s.id, api.open === s.id ? 'toggle' : 'click');
    });
    hub.querySelectorAll(`.hub-section[data-section="${s.id}"] .hub-card`).forEach((b) => {
      api.item(b, { id: `item:${s.id}/${b.dataset.page}`, level: 'page', section: s.id, page: b.dataset.page });
    });
  });
  api.item(root.querySelector('[data-home]'), { id: 'nav:home', level: 'home' });

  return {
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
    onCommit() {
      render(null);
      api.setOpen(null, 'select');
    },
    onPage(target) {
      root.querySelectorAll('.tab.current').forEach((el) => el.classList.remove('current'));
      if (target) root.querySelector(`.tab[data-section="${target.section}"]`)?.classList.add('current');
    },
    openSection(sid) { show(sid, 'preview'); },
    plan(section, page) {
      const acts = [];
      if (api.open !== section) acts.push({ do: 'click', aoi: `nav:${section}`, wait: 200 });
      acts.push({ do: 'click', aoi: `item:${section}/${page}` });
      return acts;
    },
  };
}
