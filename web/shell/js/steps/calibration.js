// Tobii calibration (collected through the server's tobii_research session) + a quick validation.
import { HCI } from '../hci.js';
import { clicked, show, sleep } from '../ui.js';

async function moveDot(dot, [x, y]) {
  dot.classList.remove('shrink');
  dot.style.left = `${x * 100}%`;
  dot.style.top = `${y * 100}%`;
  await sleep(750);
}

async function runOnce(p, field, dot) {
  await HCI.post('/api/calibration/start');
  for (const pt of p.points) {
    await moveDot(dot, pt);
    dot.classList.add('shrink');
    await sleep(350);
    await HCI.post('/api/calibration/point', { x: pt[0], y: pt[1] });
  }
  const result = await HCI.post('/api/calibration/compute');
  await HCI.post('/api/calibration/stop');

  const errors = [];
  for (const pt of p.validation_points) {
    await moveDot(dot, pt);
    await sleep(400);
    const t0 = HCI.now();
    await sleep(900);
    const t1 = HCI.now();
    const v = await HCI.post('/api/calibration/validate', { x: pt[0], y: pt[1], t0, t1 });
    if (v.error != null) errors.push(v.error);
  }
  const error = errors.length ? errors.reduce((a, b) => a + b, 0) / errors.length : null;
  return { computed: result.status, error, points_validated: errors.length };
}

export async function calibration(step) {
  const p = step.params;
  let el = await show(`
    <div class="eyebrow">Setup</div>
    <h1>Eye-tracker calibration</h1>
    <p class="lead">A dot will move around the screen. Follow it with your eyes and look at its centre until it moves again.</p>
    <p class="hint">Keep your head still. This takes about 30 seconds.</p>
    <div class="actions"><button class="btn primary" id="go">Start calibration</button></div>`);
  await clicked(el, '#go');

  let attempt = 0;
  let res;
  while (attempt < p.max_attempts) {
    attempt += 1;
    el = await show(`<div class="calib"><div class="dot"><i></i></div></div>`, 'dark');
    const dot = el.querySelector('.dot');
    await sleep(600);
    res = await runOnce(p, el, dot);
    HCI.log({ event: 'calibration_attempt', detail: { attempt, ...res } });
    if (res.computed === 'success' && res.error != null && res.error <= p.max_error) break;
    if (attempt < p.max_attempts) {
      el = await show(`
        <h1>Let's try that once more</h1>
        <p class="lead">Follow the dot closely with your eyes and keep your head as still as you can.</p>
        <div class="actions"><button class="btn primary" id="go">Try again</button></div>`);
      await clicked(el, '#go');
    }
  }
  const ok = res.computed === 'success' && res.error != null && res.error <= p.max_error;
  await show(`<h1 class="center">Calibration complete</h1><p class="lead center">Thank you. Let's continue.</p>`);
  await sleep(1400);
  return { status: ok ? 'success' : 'weak', error: res.error, attempts: attempt };
}
