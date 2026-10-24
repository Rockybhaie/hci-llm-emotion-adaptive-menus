// Talks to the local server: master-clock sync, batched logging, and the
// bridge the site iframe uses (window.HCI.site) so all data shares one timeline.

const queue = { events: [], mouse: [], aoi: [] };
let snapshotId = 0;
let lastMouse = 0;

export const HCI = {
  offset: 0,            // master clock = performance.now()/1000 + offset
  ctx: { task_id: '' }, // attached to every event
  frame: null,          // the task iframe, for coordinate conversion

  now() { return performance.now() / 1000 + this.offset; },

  async syncClock(rounds = 8) {
    let best = null;
    for (let i = 0; i < rounds; i++) {
      const t0 = performance.now();
      const { t } = await this.get('/api/clock');
      const t1 = performance.now();
      if (!best || t1 - t0 < best.rtt) best = { rtt: t1 - t0, offset: t - (t0 + t1) / 2000 };
    }
    this.offset = best.offset;
    this.log({ event: 'clock_sync', detail: { rtt_ms: +best.rtt.toFixed(2) } });
  },

  async get(url) {
    const r = await fetch(url, { cache: 'no-store' });
    return r.json();
  },

  async post(url, body = {}) {
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        return await r.json();
      } catch (e) {
        await new Promise((res) => setTimeout(res, 300 * (attempt + 1)));
      }
    }
    return { ok: false };
  },

  log(ev) {
    queue.events.push({ t: this.now(), task_id: this.ctx.task_id, source: 'shell', ...ev });
  },

  mouseAt(xNorm, yNorm) {
    const t = this.now();
    if (t - lastMouse < 1 / 60) return;
    lastMouse = t;
    queue.mouse.push([t, xNorm, yNorm]);
  },

  aoi(kind, rects) {
    queue.aoi.push({ t: this.now(), snapshot: ++snapshotId, kind, rects });
  },

  async flush() {
    if (!queue.events.length && !queue.mouse.length && !queue.aoi.length) return;
    const batch = { events: queue.events.splice(0), mouse: queue.mouse.splice(0), aoi: queue.aoi.splice(0) };
    const r = await this.post('/api/log', batch);
    if (!r.ok) {  // keep data if the server hiccuped
      queue.events.unshift(...batch.events);
      queue.mouse.unshift(...batch.mouse);
      queue.aoi.unshift(...batch.aoi);
    }
  },

  beacon() {
    const batch = { events: queue.events.splice(0), mouse: queue.mouse.splice(0), aoi: queue.aoi.splice(0) };
    navigator.sendBeacon('/api/log', JSON.stringify(batch));
  },
};

// Viewport-normalised coordinates (0..1) match Tobii's display-area coordinates in fullscreen kiosk mode.
function norm(x, y) {
  return [x / innerWidth, y / innerHeight];
}

function frameOffset() {
  const r = HCI.frame ? HCI.frame.getBoundingClientRect() : { left: 0, top: 0 };
  return [r.left, r.top];
}

// Bridge used by web/core/engine.js inside the iframe (same origin).
HCI.site = {
  log(ev) {
    const out = { ...ev, source: 'site' };
    if (ev.x != null) {
      const [ox, oy] = frameOffset();
      [out.x, out.y] = norm(ev.x + ox, ev.y + oy);
    }
    queue.events.push({ t: HCI.now(), task_id: HCI.ctx.task_id, ...out });
  },
  mouse(cx, cy) {
    const [ox, oy] = frameOffset();
    HCI.mouseAt(...norm(cx + ox, cy + oy));
  },
  aoi(kind, rects) {
    const [ox, oy] = frameOffset();
    HCI.aoi(kind, rects.map((r) => {
      const [x0, y0] = norm(r.x0 + ox, r.y0 + oy);
      const [x1, y1] = norm(r.x1 + ox, r.y1 + oy);
      return { id: r.id, x0, y0, x1, y1 };
    }));
  },
};

window.HCI = HCI;

setInterval(() => HCI.flush(), 1000);
setInterval(() => HCI.syncClock(4), 120000);
addEventListener('pagehide', () => HCI.beacon());
document.addEventListener('mousemove', (e) => HCI.mouseAt(...norm(e.clientX, e.clientY)), { passive: true });
document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-log]') || e.target.closest('button');
  const [x, y] = norm(e.clientX, e.clientY);
  HCI.log({ event: 'click', x, y, detail: { target: el ? (el.dataset.log || el.textContent.trim().slice(0, 40)) : e.target.tagName.toLowerCase() } });
}, true);
document.addEventListener('keydown', (e) => {
  if (!['Shift', 'Control', 'Alt', 'Meta'].includes(e.key)) HCI.log({ event: 'key', detail: { key: e.key.length === 1 ? 'char' : e.key } });
}, true);
