// M1: the phase-1 menu. Hover (or click) a section in the bar to open a list of its pages.
// Opens after a 150 ms intent delay, closes 400 ms after the pointer leaves, on Escape, outside click or selection.
import { createTopbar } from './topbar.js';

export default (api) => createTopbar(api, { hover: true, leaveClose: true, panel: 'list', cls: 'hover' });
