// M5: hover or click a section to open one wide panel showing all of its pages, in two columns.
import { createTopbar } from './topbar.js';

export default (api) => createTopbar(api, { hover: true, leaveClose: true, panel: 'mega', cls: 'mega' });
