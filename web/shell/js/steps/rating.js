// Self-report: SAM (valence/arousal/dominance), six emotion ratings, raw NASA-TLX.
import { HCI } from '../hci.js';
import { SAM_DIMENSIONS, samRow } from '../sam.js';
import { esc, show } from '../ui.js';

const EMOTION_LABEL = { stressed: 'Stressed', calm: 'Calm', frustrated: 'Frustrated', bored: 'Bored', happy: 'Happy', sad: 'Sad' };

const TLX = [
  { key: 'mental', title: 'Mental demand', text: 'How mentally demanding were the tasks?', low: 'Very low', high: 'Very high' },
  { key: 'physical', title: 'Physical demand', text: 'How physically demanding were the tasks?', low: 'Very low', high: 'Very high' },
  { key: 'temporal', title: 'Time pressure', text: 'How hurried or rushed was the pace?', low: 'Very low', high: 'Very high' },
  { key: 'performance', title: 'Performance', text: 'How successful were you at doing what you were asked?', low: 'Perfect', high: 'Failure' },
  { key: 'effort', title: 'Effort', text: 'How hard did you have to work to reach your level of performance?', low: 'Very low', high: 'Very high' },
  { key: 'frustration', title: 'Frustration', text: 'How insecure, discouraged, irritated, stressed or annoyed were you?', low: 'Very low', high: 'Very high' },
];

/** Shows one page; resolves with {key: value} once every row has an answer and Continue is pressed. */
async function page(html, rowSelector, buttonSelector, readValue) {
  const el = await show(html);
  const rows = [...el.querySelectorAll(rowSelector)];
  const answers = {};
  const go = el.querySelector('#go');
  rows.forEach((row) => {
    row.querySelectorAll(buttonSelector).forEach((btn) => btn.addEventListener('click', () => {
      row.querySelectorAll(buttonSelector).forEach((b) => b.classList.toggle('on', b === btn));
      answers[row.dataset.key] = readValue(btn);
      HCI.log({ event: 'rating_click', item: row.dataset.key, detail: { value: answers[row.dataset.key] } });
      row.classList.add('answered');
      go.disabled = Object.keys(answers).length < rows.length;
    }));
  });
  go.disabled = true;
  await new Promise((r) => go.addEventListener('click', r, { once: true }));
  return answers;
}

function samPage() {
  return page(`
    <div class="eyebrow">How you feel</div>
    <h1>How are you feeling right now?</h1>
    <p class="lead">Choose the point on each scale that best matches how you feel at this moment. You can pick a figure or a point between two figures.</p>
    ${SAM_DIMENSIONS.map(samRow).join('')}
    <div class="actions"><button class="btn primary" id="go">Continue</button></div>`,
  '.sam', '.sam-dot', (b) => Number(b.dataset.v));
}

function emotionPage(items, scale) {
  const rows = items.map((key) => `
    <div class="likert" data-key="${key}">
      <div class="likert-label">${esc(EMOTION_LABEL[key] || key)}</div>
      <div class="likert-scale">${Array.from({ length: scale }, (_, i) => `<button type="button" class="seg" data-v="${i + 1}">${i + 1}</button>`).join('')}</div>
    </div>`).join('');
  return page(`
    <div class="eyebrow">How you feel</div>
    <h1>Right now, how much do you feel…</h1>
    <p class="lead">1 = not at all, ${scale} = extremely.</p>
    <div class="likert-head"><span></span><span class="likert-ends"><span>Not at all</span><span>Extremely</span></span></div>
    ${rows}
    <div class="actions"><button class="btn primary" id="go">Continue</button></div>`,
  '.likert', '.seg', (b) => Number(b.dataset.v));
}

function tlxPage() {
  const rows = TLX.map((q) => `
    <div class="tlx" data-key="${q.key}">
      <div class="tlx-title">${q.title}</div>
      <div class="tlx-text">${q.text}</div>
      <div class="tlx-scale">${Array.from({ length: 21 }, (_, i) => `<button type="button" class="tick${i % 2 ? '' : ' major'}" data-v="${i * 5}" aria-label="${i * 5}"></button>`).join('')}</div>
      <div class="tlx-ends"><span>${q.low}</span><span>${q.high}</span></div>
    </div>`).join('');
  return page(`
    <div class="eyebrow">About the tasks</div>
    <h1>Thinking about the website tasks you just did…</h1>
    <p class="lead">Click on each scale at the point that best matches your experience.</p>
    ${rows}
    <div class="actions"><button class="btn primary" id="go">Continue</button></div>`,
  '.tlx', '.tick', (b) => Number(b.dataset.v));
}

export async function rating(step) {
  const p = step.params;
  const out = {};
  for (const inst of p.instruments) {
    if (inst === 'sam') out.sam = await samPage();
    if (inst === 'emotions') out.emotions = await emotionPage(p.emotion_items, p.scale);
    if (inst === 'tlx') out.tlx = await tlxPage();
  }
  return out;
}
