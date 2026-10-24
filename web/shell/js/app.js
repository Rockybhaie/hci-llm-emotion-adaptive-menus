// Runs the session step by step. The server decides which step is current,
// so a page reload simply continues where the participant was.
import { HCI } from './hci.js';
import { show } from './ui.js';
import * as steps from './steps/index.js';

const $progress = document.getElementById('progress');

function guardKeys() {
  addEventListener('keydown', (e) => {
    const k = e.key.toLowerCase();
    if (e.ctrlKey && e.shiftKey && k === 'q') {
      e.preventDefault();
      stop();
      return;
    }
    const blocked = e.key === 'F5' || e.key === 'F11' || (e.ctrlKey && ['r', 'w', 'p', 's', 'f', 'u', '+', '-', '='].includes(k))
      || (e.altKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight'));
    if (blocked) e.preventDefault();
  });
  addEventListener('contextmenu', (e) => e.preventDefault());
  addEventListener('wheel', (e) => { if (e.ctrlKey) e.preventDefault(); }, { passive: false });
}

async function stop() {
  HCI.log({ event: 'researcher_stop' });
  await HCI.flush();
  await HCI.post('/api/abort', { reason: 'Ctrl+Shift+Q' });
  await show(`<h1>Session stopped</h1><p class="lead">The data recorded so far has been saved.</p>`);
}

function clientInfo() {
  return {
    screenWidth: screen.width, screenHeight: screen.height, innerWidth, innerHeight,
    devicePixelRatio, userAgent: navigator.userAgent, language: navigator.language,
    fullscreen: innerWidth === screen.width && innerHeight === screen.height,
  };
}

async function main() {
  guardKeys();
  const session = await HCI.get('/api/session');
  if (session.error) {
    await show(`<h1>No session running</h1><p class="lead">Start one from the terminal with <code>python run.py session …</code></p>`);
    return;
  }
  document.title = session.title;
  await HCI.syncClock();
  await HCI.post('/api/client-info', clientInfo());
  addEventListener('resize', () => HCI.post('/api/client-info', clientInfo()));

  const total = session.steps.length - 1;
  for (let i = session.current; i < session.steps.length; i++) {
    const step = session.steps[i];
    $progress.style.width = `${(i / total) * 100}%`;
    const started = await HCI.post('/api/step/start', { index: i, t: HCI.now() });
    if (!started.ok) {
      location.reload();   // out of sync with the server: reload picks up its current step
      return;
    }
    HCI.log({ event: 'step', detail: { index: i, type: step.type } });
    if (step.type === 'end') {
      await steps.end(step, session);
      await HCI.flush();
      return;
    }
    const data = (await steps[step.type](step, session)) || {};
    await HCI.flush();
    await HCI.post('/api/step/complete', { index: i, t: HCI.now(), data });
    if (step.type === 'consent' && !data.agreed) {
      await HCI.post('/api/abort', { reason: 'consent declined' });
      await steps.declined();
      return;
    }
  }
}

main();
