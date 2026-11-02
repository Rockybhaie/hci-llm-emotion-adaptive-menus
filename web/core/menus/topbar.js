// Shared implementation of the three "section bar + panel" menus:
//   M1 hover drop-down and M4 click drop-down with large targets.
// They differ only in how the panel opens/closes (hover vs click) and in target size.
//
// opts = {
//   hover:      open on pointer hover (after an intent delay) as well as on click
//   leaveClose: close shortly after the pointer leaves the section + panel
//   panel:      'list'
//   cls:        CSS modifier
// }
export function createTopbar(api, opts) {
  const { site, params, esc, icon } = api;
  const timers = {};

  const list = (s) => `
      <div class="dropdown" role="menu" hidden>
        ${s.pages.map((p) => `<button class="dd-item" role="menuitem" data-section="${s.id}" data-page="${p.id}">${esc(p.title)}</button>`).join('')}
      </div>`;

  api.slots.nav.innerHTML = `
    <nav class="nav nav-${opts.cls}" data-menu-root aria-label="Main menu">
      <ul class="nav-list">
        <li class="nav-li"><button class="nav-item nav-home" data-home>${icon('home')}Home</button></li>
        ${site.sections.map((s) => `
          <li class="nav-li" data-section="${s.id}">
            <button class="nav-item" data-section="${s.id}" aria-expanded="false" aria-haspopup="true">${esc(s.title)}${icon('chevron', 'chev')}</button>
            ${list(s)}
          </li>`).join('')}
      </ul>
    </nav>`;
  const root = api.slots.nav.querySelector('.nav');

  /** DOM only: show the panel of section `sid` (or none). */
  function render(sid) {
    root.querySelectorAll('.nav-li[data-section]').forEach((li) => {
      const on = li.dataset.section === sid;
      li.classList.toggle('open', on);
      li.querySelector('.nav-item').setAttribute('aria-expanded', on);
      li.querySelector('.dropdown').hidden = !on;
    });
  }

  function open(sid, reason) {
    render(sid);
    api.setOpen(sid, reason);
  }

  function collapse(reason) {
    if (api.open == null) return false;
    render(null);
    api.setOpen(null, reason);
    return true;
  }

  root.querySelectorAll('.nav-li[data-section]').forEach((li) => {
    const sid = li.dataset.section;
    const btn = li.querySelector('.nav-item');
    api.item(btn, { id: `nav:${sid}`, level: 'section', section: sid }, () => {
      open(api.open === sid ? null : sid, api.open === sid ? 'toggle' : 'click');
    });
    if (opts.hover) {
      btn.addEventListener('mouseenter', () => {
        clearTimeout(timers.hover);
        const switching = api.open != null;
        timers.hover = setTimeout(() => open(sid, switching ? 'hover-switch' : 'hover'), switching ? 0 : params.hover_open_ms);
      });
      btn.addEventListener('mouseleave', () => clearTimeout(timers.hover));
    }
    if (opts.leaveClose) {
      li.addEventListener('mouseenter', () => clearTimeout(timers.leave));
      li.addEventListener('mouseleave', () => {
        clearTimeout(timers.leave);
        timers.leave = setTimeout(() => api.open === sid && collapse('leave'), params.leave_close_ms);
      });
    }
    li.querySelectorAll('.dd-item').forEach((b) => {
      api.item(b, { id: `item:${sid}/${b.dataset.page}`, level: 'page', section: sid, page: b.dataset.page });
    });
  });
  api.item(root.querySelector('[data-home]'), { id: 'nav:home', level: 'home' });

  return {
    collapse,
    reset() {
      clearTimeout(timers.hover);
      clearTimeout(timers.leave);
      render(null);
    },
    onCommit() {
      clearTimeout(timers.hover);
      clearTimeout(timers.leave);
      render(null);
      api.setOpen(null, 'select');
    },
    openSection(sid) { open(sid, 'preview'); },
    plan(section, page) {
      const acts = [];
      if (opts.hover) acts.push({ do: 'hover', aoi: `nav:${section}`, wait: params.hover_open_ms + 200 });
      else if (api.open !== section) acts.push({ do: 'click', aoi: `nav:${section}`, wait: 200 });
      acts.push({ do: 'click', aoi: `item:${section}/${page}` });
      return acts;
    },
  };
}
