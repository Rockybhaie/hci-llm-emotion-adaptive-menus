// Small DOM helpers shared by every step.
import { icon } from '/core/icons.js';

export { icon };

export const $stage = () => document.getElementById('stage');
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export function h(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

/** Replace the stage with new content, with a soft fade. `mode` = card | full | dark. */
export async function show(html, mode = 'card') {
  const stage = $stage();
  stage.classList.add('leaving');
  await sleep(160);
  document.body.dataset.mode = mode;
  stage.innerHTML = '';
  const el = typeof html === 'string' ? h(mode === 'card' ? `<section class="card">${html}</section>` : html) : html;
  stage.appendChild(el);
  stage.classList.remove('leaving');
  return el;
}

/** Resolve when the element matching `selector` inside `root` is clicked. */
export function clicked(root, selector) {
  return new Promise((resolve) => {
    root.querySelector(selector).addEventListener('click', (e) => resolve(e), { once: true });
  });
}

/** A primary button that unlocks after `seconds` (shows a countdown). */
export function unlockAfter(button, seconds) {
  if (!seconds) return;
  const label = button.textContent;
  button.disabled = true;
  let left = seconds;
  button.textContent = `${label} (${left})`;
  const iv = setInterval(() => {
    left -= 1;
    if (left <= 0) {
      clearInterval(iv);
      button.disabled = false;
      button.textContent = label;
    } else {
      button.textContent = `${label} (${left})`;
    }
  }, 1000);
}

export function toast(text, tone = 'neutral', ms = 1400) {
  const el = h(`<div class="toast toast-${tone}">${esc(text)}</div>`);
  document.body.appendChild(el);
  requestAnimationFrame(() => el.classList.add('in'));
  return sleep(ms).then(async () => {
    el.classList.remove('in');
    await sleep(250);
    el.remove();
  });
}

export function fmtClock(s) {
  s = Math.max(0, Math.ceil(s));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}
