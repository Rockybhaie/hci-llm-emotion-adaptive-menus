// M4: click a section to open its list; it stays open until a page is chosen or the participant clicks
// away (no hover, no auto-close). Larger targets are the design idea (params.item_height_px).
import { createTopbar } from './topbar.js';

export default (api) => {
  document.documentElement.style.setProperty('--dd-item-h', `${api.params.item_height_px || 56}px`);
  return createTopbar(api, { hover: false, leaveClose: false, panel: 'list', cls: 'click' });
};
