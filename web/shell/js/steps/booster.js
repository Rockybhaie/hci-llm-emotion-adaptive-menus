// Boosters: 30-45 s re-cues of the induced state, shown before sub-blocks 2 and 3.
// They reuse the induction activities in their `quick` form (no instructions to read) so the
// participant is back in the state quickly. See docs/emotion-induction.md.
import { HCI } from '../hci.js';
import { clicked, esc, notice, show, sleep, unlockAfter } from '../ui.js';
import { breathing, copying, mist } from './induction.js';
import { playClip } from './film.js';

// Frustration: the speed-bonus reminder with a fixed, unfavourable "current rank" (explained at debrief).
async function speedReminder(p) {
  const el = await show(`
    <div class="eyebrow">Speed round</div>
    <h1>Keep your pace up</h1>
    <p class="lead">A reminder: the fastest participants in this study receive a bonus.</p>
    <div class="rank">
      <div class="rank-place">${p.rank.place}<small> of ${p.rank.of}</small></div>
      <div class="rank-text">Your current ranking. You are about ${p.rank.behind_s} seconds per task slower than the leaders.</div>
    </div>
    <div class="actions"><button class="btn primary" id="go">Continue</button></div>`);
  unlockAfter(el.querySelector('#go'), p.min_read);
  await Promise.race([clicked(el, '#go'), sleep(p.duration * 1000)]);
  return { rank: p.rank.place };
}

// Joy / sadness: a short clip, with a marked placeholder until the file is supplied; then, if configured, quiet reflection.
async function clip(p) {
  await notice('A short clip follows', 1800);
  const result = await playClip(p.video, { maxDuration: p.duration, placeholder: p.duration });
  if (p.reflection) {
    await show(`<div class="reflect"><p>Please take a moment to think about what you just saw.</p></div>`, 'dark');
    await sleep(p.reflection * 1000);
  }
  return result;
}

export async function booster(step) {
  const p = { ...step.params, quick: true };
  HCI.log({ event: 'booster_start', detail: { kind: p.kind } });
  let result;
  switch (p.kind) {
    case 'mist': result = await mist(p); break;
    case 'breathing': result = await breathing(p); break;
    case 'copying': result = await copying(p); break;
    case 'speed_reminder': result = await speedReminder(p); break;
    case 'clip': result = await clip(p); break;
    default: throw new Error(`unknown booster ${p.kind}`);
  }
  HCI.log({ event: 'booster_end', detail: { kind: p.kind } });
  return result || {};
}
