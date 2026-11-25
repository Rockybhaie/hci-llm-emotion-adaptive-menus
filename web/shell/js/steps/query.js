// One query in the "Arrow" AI chat app: the question is pre-filled in the composer -> send -> the answer appears
// in its starting look -> read (the look may switch when the server's adaptation rule fires, or on request) ->
// Done -> two ratings + one quiz question.
import { renderLook } from '/genui/render.js';
import { HCI } from '../hci.js';
import { esc, h, icon, show, sleep } from '../ui.js';

/** The Arrow wordmark (the team's logo): a brush stroke, "ARROW", and an arrow. Drawn in currentColor. */
export const WORDMARK = `<svg class="ar-wordmark" viewBox="0 22 800 76" role="img" aria-label="Arrow">
  <path d="M4 61.5C40 60 92 62.5 150 60.5" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" opacity=".55"/>
  <path d="M10 60C52 59.5 98 61 146 59.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity=".35"/>
  <text x="166" y="88" textLength="276" lengthAdjust="spacingAndGlyphs" fill="currentColor"
    font-family="'Segoe UI Variable Display','Segoe UI',Arial,sans-serif" font-size="84" font-weight="800">ARROW</text>
  <path d="M462 60H736" stroke="currentColor" stroke-width="4"/>
  <path d="M724 44 794 60 724 76 736 60Z" fill="currentColor"/></svg>`;

/** The arrow on its own, for the assistant's avatar. */
const GLYPH = '<svg class="ar-glyph" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M13.5 7 21.5 12l-8 5 2.2-5Z" fill="currentColor"/></svg>';

function chatApp(p) {
  const app = p.app;
  const initials = app.user_name.split(' ').map((s) => s[0]).join('');
  const first = app.user_name.split(' ')[0];
  return `
  <div class="ar">
    <aside class="ar-side">
      <div class="ar-brand">${WORDMARK}<span class="ar-side-i">${icon('sidebar')}</span></div>
      <button class="ar-new" tabindex="-1">${icon('compose')}New chat</button>
      <div class="ar-search">${icon('search')}Search chats</div>
      <div class="ar-group">Today</div>
      <ul class="ar-chats"><li class="on" id="chat-title">New chat</li></ul>
      <div class="ar-group">Previous 7 days</div>
      <ul class="ar-chats">${(app.recent_chats || []).map((c) => `<li>${esc(c)}</li>`).join('')}</ul>
      <div class="ar-me"><span class="ar-avatar">${esc(initials)}</span><span><b>${esc(app.user_name)}</b><small>${esc(app.plan || '')}</small></span></div>
    </aside>
    <section class="ar-main">
      <header class="ar-top">
        <span class="ar-model">${esc(app.model || app.name)}${icon('chevron')}</span>
        <span class="ar-progress"><span>Question <b>${p.position}</b> of ${p.total}</span>
          <span class="ar-pips">${Array.from({ length: p.total }, (_, i) => `<i class="${i + 1 < p.position ? 'done' : i + 1 === p.position ? 'now' : ''}"></i>`).join('')}</span></span>
      </header>
      <main class="ar-scroll" id="main">
        <div class="ar-thread" id="thread">
          <div class="ar-hello" id="hello">${WORDMARK}<h1>Good to see you, ${esc(first)}</h1><p>What would you like to learn today?</p></div>
          <div class="ar-turn" id="answer-card" hidden>
            <div class="ar-toolbar" id="toolbar">
              <span class="ar-who"><span class="ar-bot">${GLYPH}</span>${esc(app.name)}</span>
              <span class="ar-look" id="look-chip"></span>
              <span class="ar-spacer"></span>
              <button class="btn ghost" id="diff" data-log="show differently" data-aoi="ui:show-differently">${icon('refresh')}Show this differently</button>
              <button class="btn primary" id="done" data-log="done" data-aoi="ui:done" disabled>${icon('check')}I'm done</button>
            </div>
            <div id="prompt-slot"></div>
            <div id="answer"></div>
          </div>
        </div>
      </main>
      <footer class="ar-dock">
        <div class="ar-composer" data-aoi="ui:ask">
          <div class="ar-input" id="input">${esc(p.query.query)}</div>
          <div class="ar-composer-row">
            ${p.query.subject ? `<span class="ar-topic">${icon('book')}${esc(p.query.subject)}</span>` : ''}
            <span class="ar-spacer"></span>
            <button class="ar-send" id="ask" data-log="ask" aria-label="Send">${icon('arrowUp')}</button>
          </div>
        </div>
        <div class="ar-note">${esc(app.name)} gives AI-generated answers.</div>
      </footer>
    </section>
  </div>`;
}

function lookMeta(p, id) {
  return p.looks.find((l) => l.id === id) || { id, label: id, icon: 'file', hint: '' };
}

export async function query(step) {
  const p = step.params;
  const q = p.query;
  const el = await show(chatApp(p), 'full');
  const $ = (s) => el.querySelector(s);
  const main = $('#main');
  HCI.ctx.look = '';

  const asked = new Promise((res) => $('#ask').addEventListener('click', res, { once: true }));

  // ---- first-query tip (above the send button) ---------------------------------------------------------
  if (p.first) {
    const r = $('#ask').getBoundingClientRect();
    const tip = h(`<div class="ar-tip" style="width:300px;left:${Math.max(16, r.right + 14 - 300)}px">
      Send the question with this button. Read the answer, use <b>Show this differently</b> any time, and press <b>I'm done</b> when you have read it.</div>`);
    document.body.appendChild(tip);
    tip.style.top = `${r.top - tip.offsetHeight - 14}px`;
    HCI.log({ event: 'tip_shown' });
    await Promise.race([sleep(p.first_tip * 1000), asked]);
    tip.remove();
  }

  // ---- Ask: the question becomes a user message, the composer empties ---------------------------------
  await asked;
  $('#ask').disabled = true;
  HCI.log({ event: 'ask' });
  $('#hello').remove();
  $('#chat-title').textContent = q.query.length > 30 ? `${q.query.slice(0, 28)}…` : q.query;
  const input = $('#input');
  input.textContent = `Message ${p.app.name}`;
  input.classList.add('empty');
  const card = $('#answer-card');
  card.before(h(`<div class="ar-user" data-aoi="ui:question"><div class="ar-bubble">${esc(q.query)}</div></div>`));
  card.hidden = false;
  $('#answer').innerHTML = `<div class="ar-thinking"><div class="ar-thinking-t"><span class="ar-pulse"></span>Thinking…</div>
    <div class="ar-skel w1"></div><div class="ar-skel w2"></div><div class="ar-skel w3"></div><div class="ar-skel w4"></div></div>`;
  $('#toolbar').classList.add('pending');
  await sleep(p.generating * 1000);
  $('#toolbar').classList.remove('pending');

  // ---- looks -----------------------------------------------------------------------------------------
  let current = null;
  const seen = [];
  const snapAoi = () => {
    const els = [...el.querySelectorAll('[data-aoi]')].filter((x) => x.offsetParent);
    HCI.aoi('block', els.map((x) => {
      const r = x.getBoundingClientRect();
      return { id: x.dataset.aoi, x0: r.left / innerWidth, y0: r.top / innerHeight, x1: r.right / innerWidth, y1: r.bottom / innerHeight };
    }).filter((r) => r.y1 > 0 && r.y0 < 1));
  };
  let scrollTimer;
  main.addEventListener('scroll', () => {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => { HCI.log({ event: 'scroll', detail: { y: Math.round(main.scrollTop) } }); snapAoi(); }, 200);
  }, { passive: true });
  addEventListener('resize', snapAoi);

  function setLook(look, reason, adaptationId = '') {
    current = look;
    HCI.ctx.look = look;
    if (!seen.includes(look)) seen.push(look);
    const m = lookMeta(p, look);
    $('#look-chip').innerHTML = `${icon(m.icon)}Shown as: ${esc(m.label)}`;
    const ans = $('#answer');
    ans.innerHTML = '';
    ans.appendChild(renderLook(q.looks[look], look));
    if (reason !== 'initial') main.scrollTo({ top: Math.max(0, card.offsetTop - 12), behavior: 'smooth' });
    HCI.log({ event: reason === 'initial' ? 'answer_shown' : `look_${reason}`, item: look, detail: adaptationId ? { id: adaptationId } : undefined });
    HCI.post('/api/query/look', { query_id: q.id, look, reason, adaptation_id: adaptationId, t: HCI.now() });
    requestAnimationFrame(() => requestAnimationFrame(snapAoi));
  }

  setLook(p.start_look, 'initial');
  const readUntil = performance.now() + p.read_min * 1000;
  setTimeout(() => { $('#done').disabled = false; }, p.read_min * 1000);

  // ---- automatic switch + Keep / Go back -------------------------------------------------------------
  let promptOpen = false;
  let pickerOpen = false;
  let finished = false;

  async function autoSwitch(sw) {
    promptOpen = true;
    const from = current;
    setLook(sw.to, 'auto', sw.id);
    const slot = $('#prompt-slot');
    slot.innerHTML = `<div class="pt-prompt" data-aoi="ui:prompt">${icon('sparkles')}
      <p>We changed how this answer is shown. Keep this view or go back?</p>
      <button class="btn primary" id="keep" data-log="keep">Keep this view</button>
      <button class="btn ghost" id="back" data-log="go back">Go back</button>
      <div class="pt-prompt-bar" id="pbar"></div></div>`;
    const bar = slot.querySelector('#pbar');
    bar.animate([{ transform: 'scaleX(1)' }, { transform: 'scaleX(0)' }], { duration: p.prompt * 1000, easing: 'linear', fill: 'forwards' });
    HCI.log({ event: 'prompt_shown', item: sw.to, detail: { id: sw.id, from } });
    requestAnimationFrame(snapAoi);
    const response = await Promise.race([
      new Promise((res) => slot.querySelector('#keep').addEventListener('click', () => res('keep'), { once: true })),
      new Promise((res) => slot.querySelector('#back').addEventListener('click', () => res('back'), { once: true })),
      sleep(p.prompt * 1000).then(() => 'none'),
    ]);
    slot.innerHTML = '';
    HCI.log({ event: `prompt_${response}`, detail: { id: sw.id } });
    await HCI.post('/api/adapt/resolve', { id: sw.id, response, t: HCI.now() });
    if (response === 'back') setLook(from, 'back', sw.id);
    requestAnimationFrame(snapAoi);
    promptOpen = false;
  }

  (async function poll() {
    while (!finished) {
      await sleep(p.poll_ms);
      if (finished || promptOpen || pickerOpen) continue;
      const r = await HCI.post('/api/adapt/poll', { query_id: q.id });
      if (r && r.switch && !finished) await autoSwitch(r.switch);
    }
  }());

  // ---- Show this differently -------------------------------------------------------------------------
  $('#diff').addEventListener('click', async () => {
    if (promptOpen || pickerOpen) return;
    pickerOpen = true;
    HCI.log({ event: 'picker_open' });
    const others = p.looks.filter((l) => l.id !== current);
    const ov = h(`<div class="pt-overlay"><div class="pt-dialog">
      <h2>Show this answer differently</h2><p class="sub">Choose how you would like to see it.</p>
      <div class="pt-looks">${others.map((l) => `<button class="pt-look-opt" data-look="${l.id}" data-log="look ${l.id}">${icon(l.icon)}<span><b>${esc(l.label)}</b><small>${esc(l.hint)}</small></span></button>`).join('')}</div>
      <div class="actions"><button class="btn ghost" id="cancel" data-log="cancel">Cancel</button></div></div></div>`);
    document.body.appendChild(ov);
    const choice = await new Promise((res) => {
      ov.querySelectorAll('.pt-look-opt').forEach((b) => b.addEventListener('click', () => res(b.dataset.look)));
      ov.querySelector('#cancel').addEventListener('click', () => res(null));
      ov.addEventListener('click', (e) => { if (e.target === ov) res(null); });
    });
    ov.remove();
    HCI.log({ event: 'picker_close', item: choice || '' });
    if (choice) {
      const r = await HCI.post('/api/adapt/manual', { query_id: q.id, to: choice });
      if (r.ok) setLook(choice, 'manual', r.id);
    }
    pickerOpen = false;
  });

  // ---- Done -> ratings + quiz ------------------------------------------------------------------------
  await new Promise((res) => $('#done').addEventListener('click', res, { once: true }));
  while (promptOpen) await sleep(100);
  finished = true;
  const tDone = HCI.now();
  HCI.log({ event: 'done', detail: { read_s: +((performance.now() - readUntil) / 1000 + p.read_min).toFixed(1) } });

  const seenMeta = seen.map((id) => lookMeta(p, id));
  const ov = h(`<div class="pt-overlay"><div class="pt-dialog">
    <h2>Quick questions</h2><p class="sub">About the answer you just read.</p>
    <div class="pt-q">How satisfied are you with this answer?</div>
    <div class="pt-scale" data-k="satisfaction">${[1, 2, 3, 4, 5, 6, 7].map((n) => `<button class="seg" data-v="${n}">${n}</button>`).join('')}</div>
    <div class="pt-scale-ends"><span>Not at all</span><span>Completely</span></div>
    ${seenMeta.length > 1 ? `<div class="pt-q">You saw this answer in ${seenMeta.length} ways. Which helped you most?</div>
      <div class="pt-looks" data-k="preferred">${seenMeta.map((l) => `<button class="pt-look-opt" data-v="${l.id}">${icon(l.icon)}<span><b>${esc(l.label)}</b><small>${esc(l.hint)}</small></span></button>`).join('')}</div>` : ''}
    <div class="pt-q"><small>Quick check</small>${esc(q.quiz.question)}</div>
    <div class="pt-opts" data-k="quiz">${q.quiz.options.map((o) => `<button class="opt" data-v="${esc(o)}">${esc(o)}</button>`).join('')}</div>
    <div class="actions"><button class="btn primary" id="submit" disabled>Continue</button></div></div></div>`);
  document.body.appendChild(ov);
  const answers = {};
  const need = ['satisfaction', 'quiz', ...(seenMeta.length > 1 ? ['preferred'] : [])];
  ov.querySelectorAll('[data-k]').forEach((group) => {
    group.querySelectorAll('[data-v]').forEach((b) => b.addEventListener('click', () => {
      group.querySelectorAll('[data-v]').forEach((x) => x.classList.toggle('on', x === b));
      answers[group.dataset.k] = b.dataset.v;
      HCI.log({ event: 'rating_click', item: group.dataset.k, detail: { value: b.dataset.v } });
      ov.querySelector('#submit').disabled = !need.every((k) => answers[k] != null);
    }));
  });
  await new Promise((res) => ov.querySelector('#submit').addEventListener('click', res, { once: true }));
  ov.remove();
  HCI.ctx.look = '';
  return {
    ratings: { satisfaction: Number(answers.satisfaction), preferred: answers.preferred || (seen.length === 1 ? seen[0] : '') },
    quiz_answer: answers.quiz, t_done: tDone,
  };
}
