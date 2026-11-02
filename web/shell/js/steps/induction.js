// Emotion inductions that run before a task block. See docs/emotion-induction.md.
import { HCI } from '../hci.js';
import { clicked, esc, notice, show, sleep, unlockAfter } from '../ui.js';
import { film } from './film.js';

// ---------------------------------------------------------------- stress: MIST
// Montreal Imaging Stress Task (Dedovic et al., 2005): mental arithmetic with a
// time limit that tightens after success, single-digit answers, a rigged
// "you vs average" bar and negative feedback.
function problem() {
  for (;;) {
    const level = 1 + Math.floor(Math.random() * 3);
    const n = level + 1;
    const nums = Array.from({ length: n }, () => Math.floor(Math.random() * (level === 1 ? 10 : 30)));
    const ops = Array.from({ length: n - 1 }, () => ['+', '−', '×', '÷'][Math.floor(Math.random() * 4)]);
    const expr = nums.map((x, i) => (i ? `${ops[i - 1]} ${x}` : `${x}`)).join(' ');
    const js = expr.replace(/−/g, '-').replace(/×/g, '*').replace(/÷/g, '/');
    if (js.includes('/ 0')) continue;
    const value = Function(`return (${js})`)();
    if (Number.isInteger(value) && value >= 0 && value <= 9) return { expr, answer: value, level };
  }
}

export async function mist(p) {
  if (p.quick) {
    await notice('Another round of mental arithmetic');
  } else {
    const el = await show(`
      <div class="eyebrow">Part ${p.part}</div>
      <h1>Mental arithmetic</h1>
      <p class="lead">Solve each sum in your head and click the answer (always a single digit, 0–9) before the time bar runs out.</p>
      <p class="hint">Most people get at least 80% right. Your performance is shown at the top of the screen and will be reviewed by the researcher.</p>
      <div class="actions"><button class="btn primary" id="go">Start</button></div>`);
    await clicked(el, '#go');
  }
  const view = await show(`
    <div class="mist">
      <div class="perf">
        <div class="perf-bar"><i class="perf-avg" style="left:82%"><b>Average</b></i><i class="perf-you" id="you" style="left:50%"><b>You</b></i></div>
      </div>
      <div class="mist-q" id="q"></div>
      <div class="mist-time"><div id="bar"></div></div>
      <div class="mist-fb" id="fb">&nbsp;</div>
      <div class="dial">${[...Array(10).keys()].map((d) => `<button class="digit" data-d="${d}">${d}</button>`).join('')}</div>
      <div class="mist-warn" id="warn" hidden>Your performance is below the average of other participants. Please try harder — the researcher will review your results.</div>
    </div>`, 'full');
  const $ = (s) => view.querySelector(s);
  let limit = 5000;
  let streakOk = 0;
  let streakBad = 0;
  const history = [];
  const stats = { trials: 0, correct: 0, timeouts: 0 };
  const end = performance.now() + p.duration * 1000;
  let lastWarn = performance.now();

  while (performance.now() < end) {
    const pr = problem();
    $('#q').textContent = pr.expr;
    $('#fb').innerHTML = '&nbsp;';
    $('#fb').className = 'mist-fb';
    const bar = $('#bar');
    bar.style.transition = 'none';
    bar.style.width = '100%';
    void bar.offsetWidth;
    bar.style.transition = `width ${limit}ms linear`;
    bar.style.width = '0%';
    const t0 = performance.now();
    const response = await new Promise((resolve) => {
      const timer = setTimeout(() => resolve(null), limit);
      view.querySelectorAll('.digit').forEach((b) => {
        b.onclick = () => { clearTimeout(timer); resolve(Number(b.dataset.d)); };
      });
    });
    view.querySelectorAll('.digit').forEach((b) => { b.onclick = null; });
    const rt = Math.round(performance.now() - t0);
    const correct = response === pr.answer;
    stats.trials += 1;
    if (correct) stats.correct += 1;
    if (response === null) stats.timeouts += 1;
    HCI.log({ event: 'mist_trial', detail: { expr: pr.expr, answer: pr.answer, response, correct, rt_ms: rt, limit_ms: Math.round(limit) } });

    history.push(correct);
    const recent = history.slice(-10);
    const acc = recent.filter(Boolean).length / recent.length;
    $('#you').style.left = `${Math.max(4, Math.min(96, acc * 70))}%`;   // rigged: never reaches the average marker
    $('#fb').textContent = response === null ? 'Time out' : correct ? 'Correct' : 'Incorrect';
    $('#fb').className = `mist-fb ${correct ? 'ok' : 'bad'}`;

    if (correct) { streakOk += 1; streakBad = 0; } else { streakBad += 1; streakOk = 0; }
    if (streakOk >= 3) { limit = Math.max(1500, limit * 0.9); streakOk = 0; }
    if (streakBad >= 3) { limit = Math.min(8000, limit * 1.1); streakBad = 0; }

    if (performance.now() - lastWarn > 40000) {
      lastWarn = performance.now();
      $('#warn').hidden = false;
      HCI.log({ event: 'mist_warning' });
      setTimeout(() => { $('#warn').hidden = true; }, 5000);
    }
    await sleep(650);
  }
  return { ...stats, final_limit_ms: Math.round(limit) };
}

// ---------------------------------------------------------------- calm: breathing
export async function breathing(p) {
  if (p.quick) {
    await notice('Take a moment to breathe along with the circle');
  } else {
    const el = await show(`
      <div class="eyebrow">Part ${p.part}</div>
      <h1>Relax and breathe</h1>
      <p class="lead">Watch the scenery and breathe along with the circle: breathe in slowly as it grows, and out as it shrinks.</p>
      <p class="hint">This lasts about ${Math.round(p.duration / 60) || 1} minutes and moves on by itself.</p>
      <div class="actions"><button class="btn primary" id="go">Start</button></div>`);
    await clicked(el, '#go');
  }
  const view = await show(`
    <div class="breathe">
      <div class="calm-bg"></div>
      <video class="clip" muted playsinline></video><video class="clip" muted playsinline></video>
      <div class="breath"><div class="breath-circle"></div><div class="breath-text" id="bt">Breathe in</div></div>
    </div>`, 'dark');
  const stopClips = playlist(view, [].concat(p.video || []));
  const end = performance.now() + p.duration * 1000;
  let phase = 0;
  while (performance.now() < end) {
    view.querySelector('#bt').textContent = phase % 2 ? 'Breathe out' : 'Breathe in';
    view.querySelector('.breath').classList.toggle('out', phase % 2 === 1);
    phase += 1;
    await sleep(Math.min(5000, Math.max(0, end - performance.now())));
  }
  stopClips();
  return { breaths: Math.floor(phase / 2), clips: [].concat(p.video || []).length };
}

/** Loop through `clips` on two stacked <video> elements, cross-fading 1.2 s before each clip ends. */
function playlist(view, clips) {
  if (!clips.length) return () => {};
  const [a, b] = view.querySelectorAll('video.clip');
  let i = 0;
  let current = a;
  let stopped = false;
  const start = (el, src) => {
    el.src = src;
    el.play().catch(() => {});
    el.classList.add('on');
  };
  const advance = () => {
    if (stopped) return;
    const next = current === a ? b : a;
    i = (i + 1) % clips.length;
    start(next, clips[i]);
    current.classList.remove('on');
    current = next;
  };
  [a, b].forEach((el) => el.addEventListener('timeupdate', () => {
    if (el === current && el.duration && el.duration - el.currentTime < 1.2 && !el.dataset.fading) {
      el.dataset.fading = '1';
      advance();
      setTimeout(() => { delete el.dataset.fading; }, 2000);
    }
  }));
  start(a, clips[0]);
  return () => { stopped = true; a.pause(); b.pause(); };
}

// ---------------------------------------------------------------- boredom: copying
// Monotonous transcription (van Tilburg & Igou, 2012: copying references about concrete).
const LINES = [
  'ASTM C39: compressive strength of cylindrical concrete specimens, sample 14, mix B-3.',
  'Water-cement ratio 0.45, slump 75 mm, curing period 28 days at 23 degrees.',
  'ASTM C143: slump of hydraulic-cement concrete, batch 7, ambient temperature 21 degrees.',
  'Aggregate grading: 20 mm maximum, fineness modulus 2.7, moisture content 3.1 percent.',
  'ASTM C231: air content of freshly mixed concrete by the pressure method, sample 9.',
  'Cement type I, content 350 kg per cubic metre, fly ash replacement 20 percent.',
  'Cylinder 100 by 200 mm, capped with sulphur mortar, load rate 0.25 MPa per second.',
  'ASTM C192: making and curing concrete test specimens in the laboratory, set 4.',
  'Fine aggregate: natural sand, specific gravity 2.63, absorption 1.2 percent.',
  'Coarse aggregate: crushed limestone, specific gravity 2.71, absorption 0.6 percent.',
  'ASTM C78: flexural strength using simple beam with third-point loading, beam 3.',
  'Admixture: water reducer at 400 ml per 100 kg of cement, added with mixing water.',
  'Mixing sequence: aggregates, half the water, cement, remaining water, 3 minutes total.',
  'ASTM C138: density, yield and air content of concrete by gravimetric method, sample 2.',
  'Curing tank water temperature 23 plus or minus 2 degrees, saturated with lime.',
  'Specimens demoulded after 24 hours and labelled with batch number and date.',
  'ASTM C496: splitting tensile strength of cylindrical concrete specimens, set 6.',
  'Compressive strength at 7 days: 24.6 MPa; at 28 days: 35.2 MPa; mean of three.',
  'Coefficient of variation within batch below 4 percent, results accepted.',
  'ASTM C511: mixing rooms, moist cabinets and water storage tanks, inspection 2.',
];

export async function copying(p) {
  if (p.quick) {
    await notice('Please copy a few more lines');
  } else {
    const el = await show(`
      <div class="eyebrow">Part ${p.part}</div>
      <h1>Copying task</h1>
      <p class="lead">Copy each line of text into the box exactly as it appears, then press Enter for the next line.</p>
      <p class="hint">Keep going until the task ends by itself.</p>
      <div class="actions"><button class="btn primary" id="go">Start</button></div>`);
    await clicked(el, '#go');
  }
  const view = await show(`
    <div class="copy">
      <div class="copy-count" id="n">Line 1</div>
      <div class="copy-src" id="src"></div>
      <input class="input copy-in" id="in" autocomplete="off" spellcheck="false">
      <div class="copy-hint">Press Enter when the line is copied.</div>
    </div>`);
  const input = view.querySelector('#in');
  const norm = (s) => s.trim().replace(/\s+/g, ' ').toLowerCase();
  let i = 0;
  let errors = 0;
  const setLine = () => {
    view.querySelector('#src').textContent = LINES[i % LINES.length];
    view.querySelector('#n').textContent = `Line ${i + 1}`;
    input.value = '';
    input.focus();
  };
  setLine();
  const timeUp = sleep(p.duration * 1000);
  input.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    const ok = norm(input.value) === norm(LINES[i % LINES.length]);
    HCI.log({ event: 'copy_line', detail: { line: i + 1, ok, chars: input.value.length } });
    if (ok) {
      i += 1;
      setLine();
    } else {
      errors += 1;
      input.classList.remove('shake');
      void input.offsetWidth;
      input.classList.add('shake');
    }
  });
  await timeUp;
  input.disabled = true;
  return { lines_completed: i, errors };
}

// ---------------------------------------------------------------- frustration: goal framing
const BRIEFINGS = {
  speed_bonus: {
    title: 'Speed round',
    body: `In the next part you will complete tasks on a website.
           <b>Work as quickly and accurately as you can.</b>
           The fastest participants in this study will receive a bonus, so every second counts.`,
  },
};

async function briefing(p) {
  const b = BRIEFINGS[p.message];
  const el = await show(`
    <div class="eyebrow">Part ${p.part}</div>
    <h1>${esc(b.title)}</h1>
    <p class="lead">${b.body}</p>
    <div class="actions"><button class="btn primary" id="go">I'm ready</button></div>`);
  unlockAfter(el.querySelector('#go'), p.min_read);
  await clicked(el, '#go');
  return {};
}

export async function induction(step) {
  const p = step.params;
  switch (p.kind) {
    case 'mist': return mist(p);
    case 'breathing': return breathing(p);
    case 'copying': return copying(p);
    case 'briefing': return briefing(p);
    case 'film': return film(p, {
      title: 'Video clip',
      text: 'Please watch the following clip carefully, as you would at home. Please don\'t look away from the screen.',
    });
    default: throw new Error(`unknown induction ${p.kind}`);
  }
}
