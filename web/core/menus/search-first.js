// M6: search-first. A type-ahead search box over all 36 page titles, with a Browse button as the
// fallback (Browse > section > page). Typing replaces pointing.
//   Search : click the box, type part of a page title, press Enter (first suggestion) or click a suggestion.
//   Browse : click Browse, click a section to unfold its pages, click the page.
// Matching is on page titles only (not on item names), case-insensitive: exact title first, then
// titles starting with the query, then words starting with it, then any substring.
export default function create(api) {
  const { site, params, esc, icon } = api;
  const pages = site.sections.flatMap((s) => s.pages.map((p) => ({ section: s.id, sectionTitle: s.title, page: p.id, title: p.title })));

  api.slots.nav.innerHTML = `
    <nav class="nav nav-search" data-menu-root aria-label="Main menu">
      <button class="nav-item nav-home" data-home>${icon('home')}Home</button>
      <div class="searchbox">
        ${icon('search', 'search-icon')}
        <input class="search-input" type="text" placeholder="Search for a page (for example: ${esc(pages[3].title)})" autocomplete="off" spellcheck="false" aria-label="Search pages">
        <div class="suggest" role="listbox" hidden></div>
      </div>
      <div class="browse-wrap">
        <button class="nav-item browse-btn" aria-expanded="false" aria-haspopup="true">${icon('menu')}Browse${icon('chevron', 'chev')}</button>
        <div class="dropdown browse" hidden>
          ${site.sections.map((s) => `
            <div class="br-sec" data-section="${s.id}">
              <button class="br-head" data-section="${s.id}" aria-expanded="false">${icon(s.icon, 'br-icon')}<span>${esc(s.title)}</span>${icon('chevron', 'chev')}</button>
              <div class="br-pages" hidden>${s.pages.map((p) => `<button class="br-page" data-page="${p.id}">${esc(p.title)}</button>`).join('')}</div>
            </div>`).join('')}
        </div>
      </div>
    </nav>`;
  const root = api.slots.nav.querySelector('.nav');
  const input = root.querySelector('.search-input');
  const suggest = root.querySelector('.suggest');
  const browse = root.querySelector('.browse');
  const browseBtn = root.querySelector('.browse-btn');
  let results = [];
  let active = 0;
  let queryTimer;

  const metaOf = (r) => ({ id: `item:${r.section}/${r.page}`, level: 'page', section: r.section, page: r.page });

  function search(query) {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    const scored = [];
    pages.forEach((p, i) => {
      const t = p.title.toLowerCase();
      let score = null;
      if (t === q) score = 0;
      else if (t.startsWith(q)) score = 1;
      else if (t.split(/[\s&/-]+/).some((w) => w.startsWith(q))) score = 2;
      else if (t.includes(q)) score = 3;
      if (score !== null) scored.push([score, i, p]);
    });
    return scored.sort((a, b) => a[0] - b[0] || a[1] - b[1]).slice(0, params.max_results || 7).map((x) => x[2]);
  }

  function renderSuggest() {
    results = search(input.value);
    active = 0;
    if (!input.value.trim()) {
      suggest.hidden = true;
      suggest.innerHTML = '';
      return;
    }
    suggest.hidden = false;
    suggest.innerHTML = results.length
      ? results.map((r, i) => `<button class="sg-item${i === 0 ? ' active' : ''}" role="option" data-i="${i}"><span class="sg-title">${esc(r.title)}</span><span class="sg-sec">${esc(r.sectionTitle)}</span></button>`).join('')
      : `<div class="sg-none">No page titles match “${esc(input.value.trim())}”. Try Browse.</div>`;
    suggest.querySelectorAll('.sg-item').forEach((b) => api.item(b, metaOf(results[Number(b.dataset.i)])));
  }

  function setBrowse(on) {
    browse.hidden = !on;
    browseBtn.setAttribute('aria-expanded', on);
    browseBtn.classList.toggle('open', on);
    if (!on) {
      root.querySelectorAll('.br-sec').forEach((el) => {
        el.classList.remove('open');
        el.querySelector('.br-pages').hidden = true;
        el.querySelector('.br-head').setAttribute('aria-expanded', false);
      });
    }
  }

  function showSearch() {
    renderSuggest();
    if (!suggest.hidden) {
      setBrowse(false);
      api.setOpen('search', 'type');
    } else if (api.open === 'search') {
      api.setOpen(null, 'clear');
    }
  }

  api.item(input, { id: 'nav:search', level: 'control' }, showSearch);
  input.addEventListener('input', () => {
    showSearch();
    clearTimeout(queryTimer);
    queryTimer = setTimeout(() => api.log('search_query', { detail: { query: input.value, n_results: results.length, chars: input.value.length } }), params.debounce_ms || 250);
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!results.length) return;
      e.preventDefault();
      active = (active + (e.key === 'ArrowDown' ? 1 : results.length - 1)) % results.length;
      suggest.querySelectorAll('.sg-item').forEach((b, i) => b.classList.toggle('active', i === active));
    } else if (e.key === 'Enter' && results.length) {
      e.preventDefault();
      api.select(metaOf(results[active]), 'enter');
    }
  });

  api.item(browseBtn, { id: 'nav:browse', level: 'control' }, () => {
    const on = api.open !== 'browse';
    setBrowse(on);
    if (on) suggest.hidden = true;
    api.setOpen(on ? 'browse' : null, on ? 'click' : 'toggle');
  });
  root.querySelectorAll('.br-sec').forEach((el) => {
    const sid = el.dataset.section;
    api.item(el.querySelector('.br-head'), { id: `nav:${sid}`, level: 'section', section: sid }, () => {
      const wasOpen = el.classList.contains('open');
      root.querySelectorAll('.br-sec').forEach((o) => {
        const on = o === el && !wasOpen;
        o.classList.toggle('open', on);
        o.querySelector('.br-pages').hidden = !on;
        o.querySelector('.br-head').setAttribute('aria-expanded', on);
      });
    });
    el.querySelectorAll('.br-page').forEach((b) => {
      api.item(b, { id: `item:${sid}/${b.dataset.page}`, level: 'page', section: sid, page: b.dataset.page });
    });
  });
  api.item(root.querySelector('[data-home]'), { id: 'nav:home', level: 'home' });

  function clearAll() {
    clearTimeout(queryTimer);
    input.value = '';
    results = [];
    suggest.hidden = true;
    suggest.innerHTML = '';
    setBrowse(false);
  }

  return {
    // "the menu closes unexpectedly" = the suggestion list / browse list disappears (the typed text stays)
    collapse(reason) {
      if (api.open == null) return false;
      suggest.hidden = true;
      setBrowse(false);
      api.setOpen(null, reason);
      return true;
    },
    reset: clearAll,
    onCommit() {
      clearAll();
      api.setOpen(null, 'select');
    },
    plan(section, page) {
      const title = pages.find((p) => p.section === section && p.page === page).title;
      return [
        { do: 'click', aoi: 'nav:search', wait: 100 },
        { do: 'key', key: 'Control+a', wait: 30 },              // replace anything already typed
        { do: 'type', text: title, wait: 200 },
        { do: 'click', aoi: `item:${section}/${page}` },
      ];
    },
  };
}
