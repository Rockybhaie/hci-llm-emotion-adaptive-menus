// Menu plug-ins, selected by the `type` field of config/menus.yaml.
//
// A plug-in is a module whose default export is `create(api) -> controller`.
//
//   api         provided by web/core/engine.js (see the `api` object there):
//               site, params, slots {nav, side, overlay}, esc, icon,
//               item(el, meta, onSelect), select(meta, via, onSelect), setOpen(key, reason), open
//   controller  {
//     collapse(reason) -> boolean   // go back to the resting state; used by Escape, outside clicks and the
//                                   // "menu closes unexpectedly" fault. Must call api.setOpen(null, reason).
//     reset()                       // DOM only: task start, back to the resting state, nothing logged
//     onCommit(target)              // optional: a page/home was chosen, before it loads (close the menu)
//     onPage(target)                // optional: the page is now showing (highlight the current location)
//     plan(section, page) -> [{do, aoi, text?, key?, wait?}]   // how a person reaches the page from here
//     openSection(sid)              // optional, preview only
//   }
//
// Rules every menu follows (checked by tests/test_menus_browser.py):
//   * every interactive element is registered with api.item(), so hover/select/AOI logging is identical;
//   * no menu implements fault logic: dropped clicks, lag and the glitch live in the engine;
//   * a Home control (data-aoi="nav:home") is always visible;
//   * only api.setOpen() reports expansion, so menu_open / menu_close mean the same everywhere.

const TYPES = [
  'hover-dropdown', 'sidebar-tree', 'hub-spoke',
  'click-dropdown', 'mega-menu', 'search-first',
  'drawer', 'radial', 'two-row-tabs',
];

export function loadMenu(type) {
  if (!TYPES.includes(type)) throw new Error(`Unknown menu type "${type}"`);
  return import(`./${type}.js`);
}
