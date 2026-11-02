// A sub-block of website tasks (four tasks, one menu), or the neutral practice for one menu.
// Emotion-specific behaviour comes only from step.params.flags and is identical for every menu;
// the faults themselves are applied inside the site engine (web/core/engine.js).
import { HCI } from '../hci.js';
import { clicked, esc, fmtClock, h, icon, show, sleep, toast } from '../ui.js';

function menuCard(p) {
  return `
    <div class="menu-card">
      <div class="menu-card-label">${icon('menu')}<b>${esc(p.menu_label)}</b></div>
      <p>${esc(p.menu_how)}</p>
    </div>`;
}

function intro(p) {
  const f = p.flags;
  if (p.practice) {
    return `
      <div class="eyebrow">Practice</div>
      <h1>Try this website menu</h1>
      <p class="lead">The menu of the <b>${esc(p.site_name)}</b> website will change from part to part. Here is the next one:</p>
      ${menuCard(p)}
      <p class="hint">You will do two practice tasks. There is no time pressure. Ask the researcher if anything is unclear.</p>
      <div class="actions"><button class="btn primary" id="go">Begin practice</button></div>`;
  }
  if (!p.first) {
    return `
      <div class="eyebrow">${esc(p.part)}</div>
      <h1>The menu changes</h1>
      <p class="lead">This time the website uses a different menu:</p>
      ${menuCard(p)}
      <div class="actions"><button class="btn primary" id="go">Begin</button></div>`;
  }
  const extra = [];
  if (f.evaluation_banner) extra.push('Your speed and accuracy are recorded and will be compared with other participants.');
  if (f.countdown) extra.push(`Each task has a time limit of ${p.timeout} seconds.`);
  if (f.reassurance) extra.push('There is no rush. Take all the time you need.');
  return `
    <div class="eyebrow">${esc(p.part)}</div>
    <h1>Website tasks</h1>
    <p class="lead">You'll now use the <b>${esc(p.site_name)}</b> website to complete short tasks. The website's menu changes between parts. This is the first:</p>
    ${menuCard(p)}
    <ol class="steps">
      <li>Read the task at the top of the screen.</li>
      <li>Use the <b>menu</b> of the website to find what you need.</li>
      <li>When you know the answer, click <b>Answer</b> and choose it.</li>
    </ol>
    ${extra.map((x) => `<p class="hint">${esc(x)}</p>`).join('')}
    <div class="actions"><button class="btn primary" id="go">Begin</button></div>`;
}

function celebrate(points) {
  const colors = ['#f5a524', '#3e63dd', '#1f9d6b', '#e5484d', '#8e4ec6'];
  const bits = Array.from({ length: 36 }, (_, i) => {
    const c = colors[i % colors.length];
    return `<i style="--x:${Math.random() * 100}vw;--d:${0.9 + Math.random() * 0.8}s;--r:${Math.random() * 720}deg;background:${c}"></i>`;
  }).join('');
  const el = h(`<div class="celebrate"><div class="confetti">${bits}</div><div class="reward">${icon('star', 'reward-star', true)}<b>Bonus unlocked!</b><span>+10 points · total ${points}</span></div></div>`);
  document.body.appendChild(el);
  return sleep(1700).then(() => el.remove());
}

export async function tasks(step) {
  const p = step.params;
  const f = p.flags;
  let el = await show(intro(p));
  await clicked(el, '#go');

  el = await show(`
    <div class="taskview">
      <div class="taskbar">
        <div class="tb-main">
          <span class="tb-chip">Task <b id="tn">1</b> of ${p.tasks.length}</span>
          <p class="tb-text" id="tt" data-aoi="task-text"></p>
        </div>
        <div class="tb-side">
          ${f.rewards ? `<span class="points" id="pts">${icon('star', 'pts-star', true)}<b>0</b></span>` : ''}
          ${f.countdown ? '<span class="timer" id="timer"></span>' : ''}
          <button class="btn primary" id="answer" data-log="answer">Answer</button>
        </div>
        ${f.evaluation_banner ? '<div class="eval"><span class="rec"></span>Recording performance · compared with other participants</div>' : ''}
        <div class="panel" id="panel" hidden>
          <div class="panel-q" id="pq"></div>
          <div class="opts" id="opts"></div>
          <p class="panel-err" id="perr" hidden></p>
          <div class="panel-actions">
            <button class="btn ghost" id="back" data-log="keep looking">Keep looking</button>
            <button class="btn primary" id="submit" data-log="submit" disabled>Submit answer</button>
          </div>
        </div>
      </div>
      <iframe id="site" class="site-frame" src="/core/site.html?site=${encodeURIComponent(p.site)}&menu=${encodeURIComponent(p.menu_id)}" title="Website"></iframe>
    </div>`, 'full');
  const $ = (s) => el.querySelector(s);
  const frame = $('#site');
  HCI.frame = frame;
  await new Promise((res) => frame.addEventListener('load', res, { once: true }));
  const engine = frame.contentWindow.SiteEngine;
  await engine.ready;
  engine.configure({ sabotage: f.sabotage });

  const snapTaskbar = () => {
    const els = [$('#tt'), $('#answer'), ...el.querySelectorAll('.opt'), $('#submit')].filter((x) => x && x.offsetParent);
    HCI.aoi('taskbar', els.map((x) => {
      const r = x.getBoundingClientRect();
      const id = x.dataset.aoi || x.dataset.log || (x.classList.contains('opt') ? `option:${x.dataset.i}` : x.id);
      return { id, x0: r.left / innerWidth, y0: r.top / innerHeight, x1: r.right / innerWidth, y1: r.bottom / innerHeight };
    }));
  };

  const started = [];
  let points = 0;

  const runTask = (task, n) => new Promise((resolve) => {
    let selected = null;
    let expired = false;
    let busy = false;
    let finished = false;
    const t0 = performance.now();
    $('#tn').textContent = n;
    $('#tt').textContent = task.question ? `${task.text} ${task.question}` : task.text;
    $('#pq').textContent = task.question || task.text;
    $('#opts').innerHTML = task.options.map((o, i) => `<button class="opt" data-i="${i}" data-log="option">${esc(o)}</button>`).join('');
    $('#submit').disabled = true;
    $('#perr').hidden = true;

    const openPanel = (open) => {
      $('#panel').hidden = !open;
      $('#answer').classList.toggle('active', open);
      HCI.log({ event: open ? 'answer_open' : 'answer_close' });
      requestAnimationFrame(snapTaskbar);
    };
    const finish = (outcome, extra = {}) => {
      if (finished) return;
      finished = true;
      clearInterval(tick);
      openPanel(false);
      resolve({ outcome, rt: (performance.now() - t0) / 1000, ...extra });
    };

    $('#answer').onclick = () => openPanel($('#panel').hidden);
    $('#back').onclick = () => openPanel(false);
    el.querySelectorAll('.opt').forEach((b) => {
      b.onclick = () => {
        selected = task.options[Number(b.dataset.i)];
        el.querySelectorAll('.opt').forEach((x) => x.classList.toggle('on', x === b));
        $('#submit').disabled = false;
        $('#perr').hidden = true;
      };
    });
    $('#submit').onclick = async () => {
      if (!selected || busy) return;
      if (f.sabotage && !expired && Math.random() < f.sabotage.answer_expire_prob) {
        expired = true;
        HCI.log({ event: 'sabotage_answer_expired' });
        selected = null;
        el.querySelectorAll('.opt').forEach((x) => x.classList.remove('on'));
        $('#submit').disabled = true;
        $('#perr').textContent = 'Your session has expired. Please select your answer again.';
        $('#perr').hidden = false;
        return;
      }
      busy = true;
      await HCI.flush();      // deliver every queued click / page view / mouse sample before the task is closed
      const r = await HCI.post('/api/task/answer', { task_id: task.id, answer: selected, t: HCI.now() });
      finish('answered', { correct: Boolean(r.correct) });
    };

    const tick = setInterval(() => {
      if (busy) return;
      const left = p.timeout - (performance.now() - t0) / 1000;
      const timer = $('#timer');
      if (timer) {
        timer.textContent = fmtClock(left);
        timer.classList.toggle('urgent', left <= 10);
      }
      if (left <= 0) finish('timeout');
    }, 200);

    engine.reset();
    HCI.ctx.task_id = task.id;
    HCI.post('/api/task/start', { task_id: task.id, t: HCI.now() });
    HCI.log({ event: 'task_start', detail: { n } });
    requestAnimationFrame(snapTaskbar);
  });

  for (const [i, task] of p.tasks.entries()) {
    started.push(task.id);
    const res = await runTask(task, i + 1);
    if (res.outcome === 'timeout') {
      await HCI.flush();
      await HCI.post('/api/task/close', { task_id: task.id, outcome: res.outcome, t: HCI.now() });
    }
    HCI.log({ event: 'task_end', detail: res });
    HCI.ctx.task_id = '';

    if (p.practice) {
      await toast(res.outcome === 'timeout' ? 'That is fine, on to the next one.' : 'Answer saved', 'neutral', 900);
    } else if (res.outcome === 'timeout') {
      await toast(f.negative_feedback ? "Time's up." : "Time's up. On to the next task.", f.negative_feedback ? 'bad' : 'neutral', 1300);
    } else if (f.negative_feedback) {
      if (!res.correct) await toast('Incorrect.', 'bad', 1300);
      else if (res.rt > p.timeout * 0.5) await toast('Correct, but slower than most participants.', 'warn', 1500);
      else await toast('Correct.', 'neutral', 900);
    } else if (f.rewards && res.correct && Math.random() < 0.7) {
      points += 10;
      const pts = $('#pts b');
      if (pts) pts.textContent = points;
      HCI.log({ event: 'reward', detail: { points } });
      await celebrate(points);
    } else {
      await toast('Answer saved', 'neutral', 700);
    }
  }

  HCI.frame = null;
  HCI.ctx.task_id = '';
  await show(`<h1 class="center">${p.practice ? 'Practice complete' : "That's the end of this part"}</h1><p class="lead center">${p.practice ? 'Thank you.' : 'Thank you. Please wait a moment…'}</p>`);
  await sleep(p.practice ? 1200 : 1500);
  return { started, points };
}
