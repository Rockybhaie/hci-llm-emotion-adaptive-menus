// Welcome + consent, the three background questions, the final question, debrief and end screens.
import { clicked, esc, icon, show } from '../ui.js';

export async function consent(step) {
  const text = await (await fetch('/shell/content/consent.html')).text();
  const el = await show(`
    <div class="eyebrow">${esc(step.params.title)}</div>
    <h1>Welcome, and thank you for taking part</h1>
    <ul class="facts">
      <li>${icon('clock')}<span><b>About 15 minutes.</b> You will ask a study assistant 5 questions and read its answers.</span></li>
      <li>${icon('shield')}<span><b>Anonymous.</b> You are identified only by a participant code. No video is saved.</span></li>
    </ul>
    <div class="doc">${text}</div>
    <div class="checks">
      <label class="check"><input type="checkbox" data-c> I have read the information above and agree to take part.</label>
      <label class="check"><input type="checkbox" data-c> I understand that taking part is voluntary and that I can stop at any time.</label>
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

export async function demographics() {
  const el = await show(`
    <div class="eyebrow">About you</div>
    <h1>Three quick questions</h1>
    <form class="form" id="f" autocomplete="off">
      <fieldset class="field"><legend>Age</legend><input class="input" type="number" name="age" min="16" max="99" inputmode="numeric" placeholder="Years"></fieldset>
      ${choice('programme', 'What do you study?', ['Computer Science / IT', 'Data Science / AI', 'Engineering', 'Business', 'Other'])}
      ${choice('study_confidence', 'How confident do you usually feel when learning a new topic?', ['Not at all', 'A little', 'Somewhat', 'Quite', 'Very'])}
    </form>
    <p class="error" id="err" hidden>Please answer every question.</p>
    <div class="actions"><button class="btn primary" id="go">Continue</button></div>`);
  return new Promise((resolve) => {
    el.querySelector('#go').addEventListener('click', () => {
      const data = Object.fromEntries(new FormData(el.querySelector('#f')));
      const age = Number(data.age);
      if (!data.programme || !data.study_confidence || !(age >= 16 && age <= 99)) {
        el.querySelector('#err').hidden = false;
        return;
      }
      resolve(data);
    });
  });
}

export async function final(step) {
  const looks = step.params.looks;
  const el = await show(`
    <div class="eyebrow">Last question</div>
    <h1>Which way of showing answers helped you most?</h1>
    <p class="lead">Think about all five answers you read.</p>
    <div class="pt-looks" id="looks">${looks.map((l) => `<button type="button" class="pt-look-opt" data-v="${l.id}">${icon(l.icon)}<span><b>${esc(l.label)}</b><small>${esc(l.hint)}</small></span></button>`).join('')}</div>
    <fieldset class="field" style="margin-top:18px"><legend>Anything else you would like to tell us? (optional)</legend>
      <textarea class="input" id="comment" rows="3" style="width:100%;height:auto;padding:10px 14px"></textarea></fieldset>
    <div class="actions"><button class="btn primary" id="go" disabled>Continue</button></div>`);
  let fav = null;
  el.querySelectorAll('[data-v]').forEach((b) => b.addEventListener('click', () => {
    fav = b.dataset.v;
    el.querySelectorAll('[data-v]').forEach((x) => x.classList.toggle('on', x === b));
    el.querySelector('#go').disabled = false;
  }));
  await clicked(el, '#go');
  return { favourite_look: fav, comment: el.querySelector('#comment').value.trim() };
}

export async function debrief() {
  const text = await (await fetch('/shell/content/debrief.html')).text();
  const el = await show(`
    <div class="eyebrow">Debrief</div>
    <h1>What this study was about</h1>
    <div class="doc">${text}</div>
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
