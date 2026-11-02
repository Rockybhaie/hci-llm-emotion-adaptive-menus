// Film-clip inductions (Gross & Levenson, 1995) and the neutral washout clip.
import { HCI } from '../hci.js';
import { clicked, esc, fmtClock, show, sleep } from '../ui.js';

export async function playClip(src, { maxDuration, placeholder, start = 0, end = null }) {
  const t0 = performance.now();
  if (!src) {
    // Dry runs without the video files: a neutral placeholder of the right length.
    const el = await show(`<div class="placeholder"><div class="ph-tag">PLACEHOLDER</div><div>The video for this part is not installed yet.</div><small id="pc"></small></div>`, 'dark');
    const end = performance.now() + placeholder * 1000;
    while (performance.now() < end) {
      el.querySelector('#pc').textContent = fmtClock((end - performance.now()) / 1000);
      await sleep(250);
    }
    const result = { watched_s: placeholder, ended: true, placeholder: true };
    HCI.log({ event: 'video_end', detail: result });
    return result;
  }
  const el = await show(`<div class="film"><video src="${src}" playsinline preload="auto"></video></div>`, 'dark');
  const video = el.querySelector('video');
  video.volume = 1;
  const result = await new Promise((resolve) => {
    const done = (ended) => resolve({ watched_s: +((performance.now() - t0) / 1000).toFixed(1), ended });
    video.addEventListener('ended', () => done(true), { once: true });
    if (end) video.addEventListener('timeupdate', () => { if (video.currentTime >= end) done(true); });
    video.addEventListener('error', () => {
      HCI.post('/api/warn', { message: `Video failed to play: ${src}` });
      done(false);
    }, { once: true });
    if (maxDuration) setTimeout(() => done(false), maxDuration * 1000);
    if (start) video.currentTime = start;
    video.play().catch(() => {
      HCI.post('/api/warn', { message: 'Autoplay blocked; video could not start' });
      done(false);
    });
  });
  video.pause();
  HCI.log({ event: 'video_end', detail: { src, ...result } });
  return result;
}

export async function film(p, copy) {
  const el = await show(`
    <div class="eyebrow">Part ${p.part}</div>
    <h1>${esc(copy.title)}</h1>
    <p class="lead">${esc(copy.text)}</p>
    <p class="hint">Please make sure you can hear the sound. The study continues by itself when the clip ends.</p>
    <div class="actions"><button class="btn primary" id="go">Play the clip</button></div>`);
  await clicked(el, '#go');
  const result = await playClip(p.video, { maxDuration: p.max_duration, placeholder: p.placeholder, start: p.start, end: p.end });
  if (p.reflection) {
    await show(`<div class="reflect"><p>Please take a moment to think about the clip you just watched.</p></div>`, 'dark');
    await sleep(p.reflection * 1000);
  }
  return result;
}

export async function washout(step) {
  const p = step.params;
  const el = await show(`
    <div class="eyebrow">Short break</div>
    <h1>Time for a short break</h1>
    <p class="lead">Next is a calm, neutral video. Just sit back, relax and watch.</p>
    <div class="actions"><button class="btn primary" id="go">Play</button></div>`);
  await clicked(el, '#go');
  return playClip(p.video, { maxDuration: p.duration, placeholder: p.duration });
}
