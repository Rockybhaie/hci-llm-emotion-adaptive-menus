// Welcome, consent, demographics, debrief and end screens.
import { clicked, esc, icon, show } from '../ui.js';

const SITE_KIND = { 'g1-portal': 'university student portals', 'g2-store': 'online shops', 'g3-forum': 'online forums' };

export async function welcome(step) {
  const el = await show(`
    <div class="eyebrow">${esc(step.params.title)}</div>
    <h1>Welcome, and thank you for taking part</h1>
    <p class="lead">Everything in this session is guided on screen. Simply follow the instructions as they appear.</p>
    <ul class="facts">
      <li>${icon('clock')}<span><b>About 40 minutes</b> with short pauses between parts</span></li>
      <li>${icon('shield')}<span><b>Anonymous</b>: you are identified only by a participant code</span></li>
      <li>${icon('users')}<span><b>The researcher is nearby</b> if you need anything at all</span></li>
    </ul>
    <p class="hint">Please sit comfortably, about an arm's length from the screen, and try to keep your head fairly still.</p>
    <div class="actions"><button class="btn primary" id="go">Begin</button></div>`);
  await clicked(el, '#go');
}

export async function consent() {
  const text = await (await fetch('/shell/content/consent.html')).text();
  const el = await show(`
    <div class="eyebrow">Participant information</div>
    <h1>Before we start</h1>
    <div class="doc">${text}</div>
    <div class="checks">
      <label class="check"><input type="checkbox" data-c> I have read and understood the information above.</label>
      <label class="check"><input type="checkbox" data-c> I understand that taking part is voluntary and that I can stop at any time without giving a reason.</label>
      <label class="check"><input type="checkbox" data-c> I agree to take part and for my anonymised data to be used for research.</label>
    </div>
    <div class="actions split">
      <button class="btn ghost" id="no">I do not want to take part</button>
      <button class="btn primary" id="yes" disabled>I agree</button>
    </div>`);
  const boxes = [...el.querySelectorAll('[data-c]')];
  const yes = el.querySelector('#yes');
  boxes.forEach((b) => b.addEventListener('change', () => { yes.disabled = !boxes.every((x) => x.checked); }));
  return new Promise((resolve) => {
    yes.addEventListener('click', () => resolve({ agreed: true }));
    el.querySelector('#no').addEventListener('click', () => resolve({ agreed: false }));
  });
}

function choice(name, label, options) {
  return `
    <fieldset class="field">
      <legend>${label}</legend>
      <div class="pills">${options.map((o) => `<label class="pill"><input type="radio" name="${name}" value="${esc(o)}"><span>${esc(o)}</span></label>`).join('')}</div>
    </fieldset>`;
}

export async function demographics(step, session) {
  const site = session.steps.find((s) => s.type === 'tasks')?.params.site;
  const kind = SITE_KIND[site] || 'websites like this';
  const el = await show(`
    <div class="eyebrow">About you</div>
    <h1>A few quick questions</h1>
    <p class="lead">These help us describe the group of people who took part.</p>
    <form class="form" id="f" autocomplete="off">
      <fieldset class="field"><legend>Age</legend><input class="input" type="number" name="age" min="18" max="99" inputmode="numeric" placeholder="Years"></fieldset>
      ${choice('gender', 'Gender', ['Woman', 'Man', 'Non-binary', 'Prefer not to say'])}
      ${choice('handedness', 'Which hand do you use the mouse with?', ['Right', 'Left'])}
      ${choice('vision', 'Are you wearing glasses or contact lenses right now?', ['No', 'Glasses', 'Contact lenses'])}
      ${choice('computer_hours', 'On a typical day, how many hours do you use a computer?', ['Less than 1', '1–3', '3–6', 'More than 6'])}
      ${choice('site_familiarity', `How often do you use ${kind}?`, ['Never', 'Rarely', 'Monthly', 'Weekly', 'Daily'])}
      ${choice('caffeine_2h', 'Have you had coffee, tea or an energy drink in the last 2 hours?', ['Yes', 'No'])}
    </form>
    <p class="error" id="err" hidden>Please answer every question.</p>
    <div class="actions"><button class="btn primary" id="go">Continue</button></div>`);
  return new Promise((resolve) => {
    el.querySelector('#go').addEventListener('click', () => {
      const data = Object.fromEntries(new FormData(el.querySelector('#f')));
      const keys = ['age', 'gender', 'handedness', 'vision', 'computer_hours', 'site_familiarity', 'caffeine_2h'];
      const age = Number(data.age);
      if (keys.some((k) => !data[k]) || !(age >= 18 && age <= 99)) {
        el.querySelector('#err').hidden = false;
        return;
      }
      resolve(data);
    });
  });
}

const DEBRIEF_POINTS = {
  mist: 'The arithmetic task was designed to be very hard. Its time limit adjusted itself to stay just beyond your speed, and the "average participant" marker was not real.',
  evaluation: 'Your results were not actually compared with other participants.',
  sabotage: 'The slow pages, ignored clicks, menus closing by themselves and "session expired" messages were deliberate. Nothing was wrong with the website or with how you used it.',
  briefing: 'The speed bonus was part of the study design: every participant receives the same compensation.',
  copying: 'The copying task was intentionally repetitive.',
  film: 'The video clips were chosen because they reliably bring on particular moods.',
  rewards: 'The bonus points were part of the study design and were not linked to a real prize.',
  breathing: 'The breathing exercise was used to help you relax.',
};

export async function debrief(step) {
  const text = await (await fetch('/shell/content/debrief.html')).text();
  const points = step.params.manipulations.map((m) => DEBRIEF_POINTS[m]).filter(Boolean);
  const el = await show(`
    <div class="eyebrow">Debrief</div>
    <h1>What this study was really about</h1>
    <div class="doc">${text}
      ${points.length ? `<h3>In your session</h3><ul>${points.map((p) => `<li>${esc(p)}</li>`).join('')}</ul>` : ''}
    </div>
    <fieldset class="field">
      <legend>Now that you know the full purpose, may we keep and use your data?</legend>
      <div class="pills">
        <label class="pill"><input type="radio" name="retain" value="yes"><span>Yes, you may use my data</span></label>
        <label class="pill"><input type="radio" name="retain" value="withdraw"><span>No, please delete my data</span></label>
      </div>
    </fieldset>
    <div class="actions"><button class="btn primary" id="go" disabled>Finish</button></div>`);
  let value = null;
  el.querySelectorAll('[name=retain]').forEach((r) => r.addEventListener('change', () => {
    value = r.value;
    el.querySelector('#go').disabled = false;
  }));
  await clicked(el, '#go');
  return { retain_data: value };
}

export async function end() {
  await show(`
    <div class="done-mark">${icon('check')}</div>
    <h1 class="center">Thank you!</h1>
    <p class="lead center">You're all done. Please let the researcher know you have finished.</p>`);
}

export async function declined() {
  await show(`
    <h1 class="center">Thank you for your time</h1>
    <p class="lead center">You have chosen not to take part. Nothing has been kept. Please let the researcher know.</p>`);
}

