// After the three sub-blocks of an emotion block: rank the three menus just used, best first.
import { HCI } from '../hci.js';
import { clicked, esc, show } from '../ui.js';

export async function menu_rank(step) {
  const menus = step.params.menus;
  const el = await show(`
    <div class="eyebrow">About the menus</div>
    <h1>Which menu did you prefer?</h1>
    <p class="lead">You used three different menus in the last parts, in this order. Click them in order of preference, starting with the one you liked best.</p>
    <div class="rank-list">
      ${menus.map((m) => `
        <button class="rank-card" data-id="${m.id}">
          <span class="rank-pos">${m.position}</span>
          <span class="rank-name"><b>${esc(m.label)}</b><small>${['First', 'Second', 'Third'][m.position - 1]} menu you used</small></span>
          <span class="rank-badge" aria-live="polite"></span>
        </button>`).join('')}
    </div>
    <div class="actions split"><button class="btn ghost" id="reset">Start again</button><button class="btn primary" id="go" disabled>Continue</button></div>`);
  const ranks = {};
  const cards = [...el.querySelectorAll('.rank-card')];
  const go = el.querySelector('#go');
  const redraw = () => {
    cards.forEach((c) => {
      const r = ranks[c.dataset.id];
      c.classList.toggle('on', Boolean(r));
      c.querySelector('.rank-badge').textContent = r ? ['1st', '2nd', '3rd'][r - 1] : '';
    });
    go.disabled = Object.keys(ranks).length < menus.length;
  };
  cards.forEach((c) => c.addEventListener('click', () => {
    if (ranks[c.dataset.id]) return;
    ranks[c.dataset.id] = Object.keys(ranks).length + 1;
    HCI.log({ event: 'rating_click', item: c.dataset.id, detail: { rank: ranks[c.dataset.id] } });
    redraw();
  }));
  el.querySelector('#reset').addEventListener('click', () => {
    Object.keys(ranks).forEach((k) => delete ranks[k]);
    redraw();
  });
  await clicked(el, '#go');
  return { ranks };
}
