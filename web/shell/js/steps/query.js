// One query in the learning portal: Ask -> answer in its starting look -> read (the look may switch when the
// server's adaptation rule fires, or on request) -> Done -> two ratings + one quiz question.
import { renderLook } from '/genui/render.js';
import { HCI } from '../hci.js';
import { esc, h, icon, show, sleep } from '../ui.js';

const SWATCH = ['#2b4fa3', '#2e7d5b', '#c4563e', '#a86f0a', '#7a5ba8', '#3f7f9f'];
const MENU = [['Dashboard', 'home'], ['Calendar', 'calendar'], ['Grades', 'chart'], ['Library', 'book']];

function portal(p) {
  const po = p.portal;
  const courses = po.courses || [];
  const initials = po.student_name.split(' ').map((s) => s[0]).join('');
  const ci = courses.findIndex((c) => c.subject === p.query.subject);
  const subjectColor = ci >= 0 ? SWATCH[ci % SWATCH.length] : '#a3a7b0';
  const li = (label, ic, on = false) => `<li class="${on ? 'on' : ''}">${icon(ic)}${esc(label)}</li>`;
  return `
  <div class="portal">
    <header class="pt-top">
      <div class="pt-brand"><span class="pt-crest">${esc(po.university[0])}</span><span class="pt-wordmark">${esc(po.university)}</span></div>
      <span class="pt-sep"></span><span class="pt-area">Student Portal</span>
      <div class="pt-search">${icon('search')}<span>Search courses, people, pages</span><kbd>Ctrl K</kbd></div>
      <div class="pt-user">${icon('bell')}
        <div class="pt-me"><span class="pt-avatar">${esc(initials)}</span><span><b>${esc(po.student_name)}</b><small>${esc(po.programme || '')}</small></span></div>
      </div>
    </header>
    <div class="pt-body">
      <aside class="pt-side">
        <div class="pt-group"><div class="pt-group-t">Menu</div><ul class="pt-nav">${MENU.map(([t, ic]) => li(t, ic)).join('')}</ul></div>
        <div class="pt-group"><div class="pt-group-t">My courses</div><ul class="pt-nav">${courses.map((c, i) => `
          <li><span class="pt-swatch" style="background:${SWATCH[i % SWATCH.length]}"></span><span class="pt-course-row"><b>${esc(c.code)}</b><span>${esc(c.title)}</span></span></li>`).join('')}</ul></div>
        <div class="pt-group"><div class="pt-group-t">Tools</div><ul class="pt-nav">${li('Study assistant', 'sparkles', true)}</ul></div>
        ${po.term ? `<div class="pt-term">${esc(po.term)}</div>` : ''}
      </aside>
      <main class="pt-main" id="main">
        <section class="pt-assistant">
          <div class="pt-crumbs">Tools ${icon('chevron')} Study assistant</div>
          <div class="pt-head">
            <div><h1>Study assistant</h1><p>Ask about anything in your courses or studies.</p></div>
            <div class="pt-progress">Question <b>${p.position}</b> of ${p.total}
              <div class="pt-pips">${Array.from({ length: p.total }, (_, i) => `<i class="${i + 1 < p.position ? 'done' : i + 1 === p.position ? 'now' : ''}"></i>`).join('')}</div></div>
          </div>
          <div class="pt-ask" data-aoi="ui:ask">
            ${p.query.subject ? `<span class="pt-subject"><i style="background:${subjectColor}"></i>${esc(p.query.subject)}</span>` : ''}
            <div class="pt-input">${esc(p.query.query)}</div>
            <button class="btn primary" id="ask" data-log="ask">Ask</button>
          </div>
          <div class="pt-answer" id="answer-card" hidden>
            <div class="pt-toolbar" id="toolbar">
              <span class="pt-from"><span class="pt-from-i">${icon('sparkles')}</span>Assistant</span>
              <span class="pt-look" id="look-chip"></span>
              <span class="pt-spacer"></span>
              <button class="btn ghost" id="diff" data-log="show differently" data-aoi="ui:show-differently">${icon('refresh')}Show this differently</button>
              <button class="btn primary" id="done" data-log="done" data-aoi="ui:done" disabled>${icon('check')}I'm done</button>
            </div>
            <div class="pt-answer-body">
              <div id="prompt-slot"></div>
              <div id="answer"></div>
            </div>
          </div>
        </section>
      </main>
    </div>
  </div>`;
}

function lookMeta(p, id) {
  return p.looks.find((l) => l.id === id) || { id, label: id, icon: 'file', hint: '' };
}

export async function query(step) {
  const p = step.params;
  const q = p.query;
  const el = await show(portal(p), 'full');
  const $ = (s) => el.querySelector(s);
  const main = $('#main');
  HCI.ctx.look = '';

  const asked = new Promise((res) => $('#ask').addEventListener('click', res, { once: true }));

  // ---- first-query tip ---------------------------------------------------------------------------------
  if (p.first) {
    const r = $('#ask').getBoundingClientRect();
    const tip = h(`<div class="pt-tip" style="width:300px;left:${Math.max(16, r.right + 12 - 300)}px;top:${r.bottom + 14}px">
      Ask the assistant with this button. Read the answer, use <b>Show this differently</b> any time, and press <b>I'm done</b> when you have read it.</div>`);
    document.body.appendChild(tip);
    HCI.log({ event: 'tip_shown' });
    await Promise.race([sleep(p.first_tip * 1000), asked]);
    tip.remove();
  }

  // ---- Ask -------------------------------------------------------------------------------------------
  await asked;
  $('#ask').disabled = true;
  HCI.log({ event: 'ask' });
  const card = $('#answer-card');
  card.hidden = false;
  $('#answer').innerHTML = `<div class="pt-generating"><div class="pt-generating-t"><span class="spinner"></span>Writing an answer for you…</div>
    <div class="pt-skel w1"></div><div class="pt-skel w2"></div><div class="pt-skel w3"></div><div class="pt-skel w4"></div></div>`;
  $('#toolbar').style.visibility = 'hidden';
  await sleep(p.generating * 1000);
  $('#toolbar').style.visibility = '';

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
    if (reason !== 'initial') main.scrollTo({ top: 0, behavior: 'smooth' });
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
