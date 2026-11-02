// M2: persistent left sidebar. All six sections are always visible; click a section to unfold its
// pages (one section at a time), then click the page. The unfolded section stays unfolded after a
// page is chosen, so a second page in the same section costs one click.
export default function create(api) {
  const { site, esc, icon } = api;
  api.slots.side.hidden = false;
  document.body.classList.add('has-side');
  api.slots.side.innerHTML = `
    <nav class="side-nav" data-menu-root aria-label="Main menu">
      <button class="side-item side-home" data-home>${icon('home', 'side-icon')}<span>Home</span></button>
      <ul class="tree">
        ${site.sections.map((s) => `
          <li class="tree-sec" data-section="${s.id}">
            <button class="side-item tree-head" data-section="${s.id}" aria-expanded="false">${icon(s.icon, 'side-icon')}<span>${esc(s.title)}</span>${icon('chevron', 'chev')}</button>
            <ul class="tree-pages" hidden>
              ${s.pages.map((p) => `<li><button class="side-item tree-page" data-page="${p.id}">${esc(p.title)}</button></li>`).join('')}
            </ul>
          </li>`).join('')}
      </ul>
    </nav>`;
  const root = api.slots.side.querySelector('.side-nav');

  /** DOM only: unfold section `sid` (or none). */
  function render(sid) {
    root.querySelectorAll('.tree-sec').forEach((li) => {
      const on = li.dataset.section === sid;
      li.classList.toggle('open', on);
      li.querySelector('.tree-head').setAttribute('aria-expanded', on);
      li.querySelector('.tree-pages').hidden = !on;
    });
  }

  function unfold(sid, reason) {
    render(sid);
    api.setOpen(sid, reason);
  }

  root.querySelectorAll('.tree-sec').forEach((li) => {
    const sid = li.dataset.section;
    api.item(li.querySelector('.tree-head'), { id: `nav:${sid}`, level: 'section', section: sid }, () => {
      unfold(api.open === sid ? null : sid, api.open === sid ? 'toggle' : 'click');
    });
    li.querySelectorAll('.tree-page').forEach((b) => {
      api.item(b, { id: `item:${sid}/${b.dataset.page}`, level: 'page', section: sid, page: b.dataset.page });
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
    onPage(target) {
      root.querySelectorAll('.current').forEach((el) => el.classList.remove('current'));
      if (!target) return;
      root.querySelector(`[data-aoi="item:${target.section}/${target.page}"]`)?.classList.add('current');
    },
    openSection(sid) { unfold(sid, 'preview'); },
    plan(section, page) {
      const acts = [];
      if (api.open !== section) acts.push({ do: 'click', aoi: `nav:${section}`, wait: 200 });
      acts.push({ do: 'click', aoi: `item:${section}/${page}` });
      return acts;
    },
  };
}
