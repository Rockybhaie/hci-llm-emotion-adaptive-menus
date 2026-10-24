// Resting baseline: fixation cross on a mid-luminance background (no timer shown).
import { clicked, show, sleep } from '../ui.js';

export async function rest(step) {
  const el = await show(`
    <div class="eyebrow">Resting period</div>
    <h1>Take a moment to relax</h1>
    <p class="lead">Sit comfortably with your feet flat on the floor. Look at the cross in the middle of the screen and simply relax.</p>
    <p class="hint">This lasts about ${Math.round(step.params.duration / 60) || 1} minutes and moves on by itself. Please keep your hands still.</p>
    <div class="actions"><button class="btn primary" id="go">Start</button></div>`);
  await clicked(el, '#go');
  await show(`<div class="fixation" aria-label="Fixation cross"><span></span><span></span></div>`, 'rest');
  await sleep(step.params.duration * 1000);
  return { duration_s: step.params.duration };
}
