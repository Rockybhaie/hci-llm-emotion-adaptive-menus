"""One participant's Generative-UI session: the step plan, live state, adaptation and everything written to disk.

The browser only renders steps. The server decides which step is current, keeps the correct quiz answers,
runs the adaptation rule on the emotion stream and writes every file.
"""

import collections
import csv
import datetime as dt
import hashlib
import json
import platform
import random
import shutil
import threading

from . import __version__, adapt, content, counterbalance, paths
from .clock import SOURCE as CLOCK_SOURCE
from .clock import now
from .config import ConfigError
from .storage import SNAPSHOT, SessionStore

DEFAULT_VIEWPORT = (1920, 1080)


class SessionExists(Exception):
    pass


class QueryState:
    """Everything that happens while one answer is on screen."""

    def __init__(self, step, adapter, attempt):
        self.step = step
        self.query_id = step["query_id"]
        self.adapter = adapter
        self.attempt = attempt
        self.t_answer = None          # first answer shown
        self.looks = []               # [look, t_start, reason, adaptation_id]
        self.adaptations = []         # dicts, see storage.SCHEMAS["adaptations"]
        self.pending = None           # adaptation id awaiting Keep / Go back


class Session:
    def __init__(self, cfg, participant, *, fast=False, pilot=False, resume=False, data_root=None,
                 sensor_plan=None):
        self.cfg = cfg
        self.participant = participant
        self.fast, self.pilot = fast, pilot
        self.sensor_plan = dict(sensor_plan or {})
        self.number = counterbalance.participant_number(participant)
        self.plan = counterbalance.assign(participant, cfg.queries, cfg.looks)
        self.queries = {q: content.validate(q, cfg.looks) for q in cfg.queries}

        root = data_root or (paths.PILOT if pilot else paths.DATA)
        self.folder = root / participant
        previous = None
        if (self.folder / "session.json").exists():
            if not resume:
                raise SessionExists(f"{paths.rel(self.folder)} already exists. Use another participant ID, "
                                    f"or --resume to continue an interrupted session.")
            previous = json.loads((self.folder / "session.json").read_text(encoding="utf-8"))

        self.warnings = collections.deque(maxlen=8)
        self.rng = random.Random(self.number * 7919)
        self.steps = self._build_steps()
        self.store = SessionStore(self.folder)
        self.sensing = None
        self.done = threading.Event()
        self._lock = threading.RLock()
        self.client_info = {}
        self.calibration = {}
        self.completed = set()
        self.attempts = collections.Counter()
        self.active = None            # QueryState of the query on screen
        self.adapt_seq = 0
        self.withdrawn = False
        self.current = 0
        self.status = "created"
        self.t_zero = now()
        self.wall_zero = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        if previous:
            self._restore(previous)

    # ------------------------------------------------------------------ plan
    def _looks_meta(self):
        return [{"id": k, **v} for k, v in self.cfg.study["looks"].items()]

    def _build_steps(self):
        st = self.cfg.study
        t = lambda key: self.cfg.timing(key, self.fast)
        steps = [
            dict(type="consent", phase="consent", params={"title": st["study_title"], "app": st["app"]}),
            dict(type="demographics", phase="demographics", params={}),
        ]
        if "eye_tracker" in self.sensor_plan:
            steps.append(dict(type="calibration", phase="calibration", params=st["calibration"]))
        steps.append(dict(type="rest", phase="baseline", params={"duration": t("baseline")}))
        order = self.plan["order"]
        for i, q in enumerate(order):
            steps.append(dict(type="query", phase="query", query_id=q, params={
                "position": i + 1, "total": len(order), "first": i == 0,
                "query": content.client_view(q, self.cfg.looks), "start_look": self.plan["start_looks"][q],
                "looks": self._looks_meta(), "app": st["app"], "pilot": self.pilot,
                "read_min": t("read_min"), "generating": t("generating"), "first_tip": t("first_tip"),
                "prompt": self.cfg.adaptation["prompt"], "poll_ms": self.cfg.adaptation["poll_ms"]}))
        steps += [dict(type="final", phase="final", params={"looks": self._looks_meta()}),
                  dict(type="debrief", phase="debrief", params={}),
                  dict(type="end", phase="end", params={})]
        for i, s in enumerate(steps):
            s["index"] = i
            s.setdefault("query_id", "")
        return steps

    def step(self):
        return self.steps[self.current]

    # ------------------------------------------------------------------ sensors
    def attach_sensing(self, sensing):
        self.sensing = sensing

    def emotion_sensor(self):
        return self.sensing.emotion if self.sensing is not None else None

    def _emotion_recent(self, since):
        s = self.emotion_sensor()
        if s is None or not s.columns:
            return []
        return adapt.rows_as_dicts(s.columns, s.recent(since))

    def _emotion_between(self, t0, t1):
        """Emotion rows from emotion.csv (complete history, unlike the in-memory buffer)."""
        path = self.folder / "emotion.csv"
        s = self.emotion_sensor()
        if s is not None and s.stream is not None:
            with s.stream._lock:
                if not s.stream._file.closed:
                    s.stream._file.flush()
        if not path.exists():
            return []
        with open(path, encoding="utf-8", newline="") as f:
            return [r for r in csv.DictReader(f) if r.get("t") and t0 <= float(r["t"]) <= t1]

    # ------------------------------------------------------------------ helpers
    def warn(self, msg):
        self.warnings.append((dt.datetime.now().strftime("%H:%M:%S"), msg))

    def _t(self, value):
        return float(value) if isinstance(value, (int, float)) else now()

    def _marker(self, step, event, t):
        self.store.write("markers", [f"{t:.4f}", step["index"], step["type"], step["phase"], step["query_id"], event])

    def _q(self, t, tag, query_id, instrument, item, value):
        self.store.write("questionnaires", [f"{t:.4f}", tag, query_id, instrument, item, value])

    def _viewport(self):
        return (self.client_info.get("innerWidth") or DEFAULT_VIEWPORT[0],
                self.client_info.get("innerHeight") or DEFAULT_VIEWPORT[1])

    # ------------------------------------------------------------------ API: session flow
    def client_session(self):
        public = [{"index": s["index"], "type": s["type"], "params": s["params"]} for s in self.steps]
        return {"steps": public, "current": self.current, "fast": self.fast, "pilot": self.pilot,
                "title": self.cfg.study["study_title"]}

    def set_client_info(self, info):
        self.client_info = info
        if info.get("innerWidth") and info.get("screenWidth") and \
                abs(info["innerWidth"] - info["screenWidth"]) > 2 and not self.pilot:
            self.warn("Browser is not fullscreen: gaze coordinates will not line up with the page")
        self._save()

    def step_start(self, index, t=None):
        with self._lock:
            if index != self.current:
                return {"ok": False, "current": self.current}
            step = self.step()
            t = self._t(t)
            self._marker(step, "start", t)
            if self.status == "created":
                self.status = "running"
            if step["type"] == "query":
                self.attempts[index] += 1
                adapter = adapt.QueryAdapter(self.cfg.adaptation, self.cfg.looks, step["params"]["start_look"],
                                             random.Random(self.number * 1000 + index * 10 + self.attempts[index]))
                self.active = QueryState(step, adapter, self.attempts[index])
                if self.attempts[index] > 1:
                    self.warn(f"Query {step['query_id']} restarted (attempt {self.attempts[index]})")
            if step["type"] == "end":
                self.completed.add(index)
                self._marker(step, "end", t)
                self.finish("complete")
            return {"ok": True}

    def step_complete(self, index, data=None, t=None):
        with self._lock:
            if index != self.current:
                return {"ok": False, "current": self.current}
            step = self.step()
            t = self._t(t)
            self._record(step, data or {}, t)
            self._marker(step, "end", t)
            self.completed.add(index)
            self.current += 1
            self._save()
            return {"ok": True, "current": self.current}

    def _record(self, step, data, t):
        kind = step["type"]
        if kind == "consent":
            self._q(t, "consent", "", "consent", "agreed", int(bool(data.get("agreed"))))
        elif kind == "demographics":
            for k, v in data.items():
                self._q(t, "demographics", "", "demographics", k, v)
        elif kind == "calibration":
            self.calibration = data
            if data.get("status") != "success":
                self.warn(f"Gaze calibration weak (error {data.get('error')})")
        elif kind == "query":
            self._finish_query(step, data, t)
        elif kind == "final":
            for k in ("favourite_look", "comment"):
                if data.get(k) not in (None, ""):
                    self._q(t, "final", "", "final", k, str(data[k])[:500])
        elif kind == "debrief":
            retain = data.get("retain_data") or ""
            self._q(t, "debrief", "", "debrief", "retain_data", retain)
            if retain == "withdraw":
                self.withdrawn = True
                self.warn("Participant withdrew: their data will be deleted at the end")

    # ------------------------------------------------------------------ API: inside a query
    def _query(self, query_id):
        a = self.active
        return a if a is not None and a.query_id == query_id else None

    def query_look(self, query_id, look, reason, adaptation_id="", t=None):
        """The browser reports every look it puts on screen (initial, auto, manual, back)."""
        with self._lock:
            a = self._query(query_id)
            if a is None or look not in self.cfg.looks:
                return {"ok": False}
            t = self._t(t)
            if reason == "initial":
                a.t_answer = t
            a.looks.append([look, t, reason, adaptation_id or ""])
            self.store.write("looks", [f"{t:.4f}", query_id, look, reason, adaptation_id or ""])
            return {"ok": True}

    def _new_adaptation(self, a, trigger, to, snap, t):
        self.adapt_seq += 1
        rec = {"adaptation_id": f"A{self.adapt_seq:03d}", "t": t, "trigger": trigger,
               "from_look": a.adapter.current, "to_look": to, "n_auto_before": a.adapter.n_auto,
               "response": "chosen" if trigger == "manual" else "", "response_t": "", "response_s": "",
               **{f"before_{k}": snap.get(k, "") for k in SNAPSHOT}}
        a.adaptations.append(rec)
        a.adapter.switched(to, t, auto=trigger == "auto")
        return rec

    def adapt_poll(self, query_id):
        """Called by the browser every few hundred ms while an answer is being read."""
        with self._lock:
            a = self._query(query_id)
            if a is None or a.pending is not None or a.t_answer is None:
                return {"switch": None}
            t = now()
            samples = self._emotion_recent(t - self.cfg.adaptation["window"] - 1)
            to, snap = a.adapter.should_switch(samples, t)
            if to is None:
                return {"switch": None}
            rec = self._new_adaptation(a, "auto", to, snap, t)
            a.pending = rec["adaptation_id"]
            return {"switch": {"id": rec["adaptation_id"], "to": to, "from": rec["from_look"]}}

    def adapt_manual(self, query_id, to):
        with self._lock:
            a = self._query(query_id)
            if a is None or to not in self.cfg.looks or to == a.adapter.current:
                return {"ok": False}
            t = now()
            snap = adapt.snapshot([s for s in self._emotion_recent(t - self.cfg.adaptation["window"]) if s],
                                  self.cfg.adaptation)
            rec = self._new_adaptation(a, "manual", to, snap, t)
            return {"ok": True, "id": rec["adaptation_id"]}

    def adapt_resolve(self, adaptation_id, response, t=None):
        """Keep / Go back / none (prompt timed out) for an automatic switch."""
        with self._lock:
            a = self.active
            if a is None:
                return {"ok": False}
            rec = next((r for r in a.adaptations if r["adaptation_id"] == adaptation_id), None)
            if rec is None or response not in ("keep", "back", "none"):
                return {"ok": False}
            t = self._t(t)
            rec.update(response=response, response_t=f"{t:.4f}", response_s=round(t - rec["t"], 3))
            if response == "back":
                a.adapter.switched(rec["from_look"], t, auto=False)
            if a.pending == adaptation_id:
                a.pending = None
            return {"ok": True}

    def pilot_frown(self, seconds=6.0):
        if not self.pilot or self.sensing is None:
            return {"ok": False, "error": "only in --pilot sessions with sensors"}
        self.sensing.context.force_negative_until = now() + seconds
        self.warn(f"Simulated frown for {seconds:.0f} s")
        return {"ok": True}

    # ------------------------------------------------------------------ end of a query
    def _finish_query(self, step, data, t_done):
        a = self.active
        self.active = None
        if a is None or a.query_id != step["query_id"]:
            return
        q = self.queries[a.query_id]
        t_done = float(data.get("t_done") or t_done)
        ratings = data.get("ratings") or {}
        satisfaction = ratings.get("satisfaction", "")
        preferred = ratings.get("preferred", "") or ""
        quiz_answer = data.get("quiz_answer", "")
        quiz_correct = int(quiz_answer == q["quiz"]["answer"]) if quiz_answer else ""

        intervals = []
        for i, (look, t0, reason, aid) in enumerate(a.looks):
            t1 = a.looks[i + 1][1] if i + 1 < len(a.looks) else t_done
            intervals.append((look, t0, max(t0, t1), reason, aid))
        per_look = collections.OrderedDict()
        for look, t0, t1, *_ in intervals:
            per_look[look] = per_look.get(look, 0.0) + (t1 - t0)

        rows = self._emotion_between(a.t_answer or t_done, t_done)
        snap = adapt.snapshot(rows, self.cfg.adaptation)
        val_look, dom_look = [], []
        for look in per_look:
            look_rows = [r for (lk, t0, t1, *_) in intervals if lk == look
                         for r in rows if t0 <= float(r["t"]) <= t1]
            s = adapt.snapshot(look_rows, self.cfg.adaptation)
            val_look.append(f"{look}:{s['valence']}")
            dom_look.append(f"{look}:{s['dominant']}")

        final_look = intervals[-1][0] if intervals else ""
        self.store.write("interactions", {
            "participant": self.participant, "position": step["params"]["position"], "query_id": a.query_id,
            "query_type": q["type"], "attempt": a.attempt, "start_look": step["params"]["start_look"],
            "looks_seen": ">".join(lk for lk, *_ in intervals), "final_look": final_look, "n_looks": len(per_look),
            "n_auto": sum(r["trigger"] == "auto" for r in a.adaptations),
            "n_manual": sum(r["trigger"] == "manual" for r in a.adaptations),
            "n_kept": sum(r["response"] in ("keep", "none") for r in a.adaptations if r["trigger"] == "auto"),
            "n_back": sum(r["response"] == "back" for r in a.adaptations),
            "t_answer": "" if a.t_answer is None else f"{a.t_answer:.4f}", "t_done": f"{t_done:.4f}",
            "reading_s": "" if a.t_answer is None else round(t_done - a.t_answer, 2),
            "time_per_look": ";".join(f"{k}:{v:.1f}" for k, v in per_look.items()),
            "satisfaction": satisfaction, "preferred_look": preferred,
            "quiz_answer": quiz_answer, "quiz_correct": quiz_correct,
            "emotion_samples": snap["samples"], "face_fraction": snap["face_fraction"],
            "valence": snap["valence"], "arousal": snap["arousal"], "dominant_emotion": snap["dominant"],
            "negative_fraction": snap["negative_fraction"],
            "valence_per_look": ";".join(val_look), "dominant_per_look": ";".join(dom_look)})

        for rec in a.adaptations:
            on_new = next((t1 - t0 for (lk, t0, t1, reason, aid) in intervals if aid == rec["adaptation_id"]), "")
            self.store.write("adaptations", {
                "participant": self.participant, "query_id": a.query_id, "query_type": q["type"],
                "attempt": a.attempt, **rec, "t": f"{rec['t']:.4f}",
                "response": rec["response"] or "none",
                "time_on_new_look_s": "" if on_new == "" else round(on_new, 2), "final_look": final_look,
                "satisfaction": satisfaction, "preferred_look": preferred, "quiz_correct": quiz_correct})

        for item, value in (("satisfaction", satisfaction), ("preferred_look", preferred),
                            ("quiz_answer", quiz_answer), ("quiz_correct", quiz_correct)):
            self._q(t_done, f"query_{step['params']['position']}", a.query_id, "query", item, value)

    # ------------------------------------------------------------------ API: behaviour log
    def log(self, batch):
        with self._lock:
            step = self.step()
            look = self.active.adapter.current if self.active is not None else ""
            for ev in batch.get("events", []):
                detail = ev.get("detail")
                self.store.write("events", [
                    f"{self._t(ev.get('t')):.4f}", step["index"], step["query_id"], ev.get("look", look),
                    ev.get("source", "shell"), ev.get("event", ""), ev.get("item", ""),
                    _r(ev.get("x")), _r(ev.get("y")),
                    json.dumps(detail, ensure_ascii=False) if detail not in (None, "") else ""])
            mouse = batch.get("mouse", [])
            for t, x, y in mouse:
                self.store.write("mouse", [f"{t:.4f}", _r(x), _r(y)])
            if mouse and self.sensing is not None:
                self.sensing.context.mouse = (mouse[-1][1], mouse[-1][2])
            for snap in batch.get("aoi", []):
                rows = snap.get("rects") or [{"id": "", "x0": "", "y0": "", "x1": "", "y1": ""}]
                for r in rows:
                    self.store.write("aoi", [f"{self._t(snap.get('t')):.4f}", snap.get("snapshot", ""),
                                             snap.get("kind", ""), r["id"], _r(r["x0"]), _r(r["y0"]),
                                             _r(r["x1"]), _r(r["y1"])])
        return {"ok": True}

    # ------------------------------------------------------------------ lifecycle
    def abort(self, reason="researcher abort"):
        with self._lock:
            if self.done.is_set():
                return
            self._marker(self.step(), f"abort: {reason}", now())
            self.warn(f"Session aborted ({reason})")
            if reason == "consent declined":
                self.withdrawn = True
            self.finish("declined" if reason == "consent declined" else "aborted")

    def finish(self, status):
        with self._lock:
            if self.done.is_set():
                return
            self.status = status
            self.t_end = now()
            if self.sensing is not None:
                self.sensing.stop()
            self._save()
            self.store.close()
        if self.withdrawn:
            shutil.rmtree(self.folder, ignore_errors=True)
            self.status = "withdrawn" if status == "complete" else status
            self.warn("All data for this participant was deleted")
        else:
            try:
                from .export import merge_session
                merge_session(self.folder)
            except Exception as exc:
                self.warn(f"merged.csv could not be built: {exc}")
        self.done.set()

    def _restore(self, prev):
        if prev.get("plan") != self.plan:
            raise ConfigError("Cannot resume: the counterbalancing plan no longer matches session.json")
        self.completed = set(prev["progress"]["completed_steps"])
        self.current = min(set(range(len(self.steps))) - self.completed, default=len(self.steps) - 1)
        self.attempts = collections.Counter({int(k): v for k, v in prev.get("attempts", {}).items()})
        self.adapt_seq = prev.get("adaptations", 0)
        self.t_zero = prev["clock"]["t_zero"]
        self.wall_zero = prev["started"]
        self.calibration = prev.get("calibration", {})
        self.status = "running"
        self.warn(f"Resumed at step {self.current} ({self.steps[self.current]['type']})")
        self._marker(self.step(), "resumed", now())

    def _content_info(self):
        out = {}
        for q in self.cfg.queries:
            raw = (content.CONTENT / f"{q}.yaml").read_bytes()
            out[q] = {"sha1": hashlib.sha1(raw).hexdigest()[:12], **(self.queries[q].get("provenance") or {})}
        return out

    def _save(self):
        self.store.write_json("session", {
            "study": self.cfg.study["study_title"], "platform_version": __version__,
            "participant": self.participant, "plan": self.plan,
            "flags": {"fast": self.fast, "pilot": self.pilot}, "status": self.status, "started": self.wall_zero,
            "clock": {"source": CLOCK_SOURCE, "t_zero": self.t_zero,
                      "note": "All 't' columns use this clock (seconds). t_zero = session start."},
            "sensors": self.sensing.info() if self.sensing is not None else {},
            "adaptation_rule": self.cfg.adaptation, "content": self._content_info(),
            "client": self.client_info, "calibration": self.calibration,
            "progress": {"current": self.current, "completed_steps": sorted(self.completed),
                         "total_steps": len(self.steps)},
            "attempts": {str(k): v for k, v in self.attempts.items()}, "adaptations": self.adapt_seq,
            "duration_s": round(getattr(self, "t_end", now()) - self.t_zero, 1),
            "host": {"os": platform.platform(), "python": platform.python_version()},
        })

    def snapshot(self):
        step = self.step()
        live = (self.sensing.live().get("emotion") if self.sensing is not None else None) or {}
        a = self.active
        return {"participant": self.participant, "status": self.status, "step": self.current,
                "steps": len(self.steps), "type": step["type"], "phase": step["phase"],
                "query": f"{step['params'].get('position')}/{step['params'].get('total')} {step['query_id']}"
                if step["type"] == "query" else "",
                "look": a.adapter.current if a is not None else "",
                "switches": len(a.adaptations) if a is not None else 0,
                "emotion": live, "elapsed": now() - self.t_zero,
                "sensors": self.sensing.status() if self.sensing is not None else [],
                "warnings": list(self.warnings), "flags": {"fast": self.fast, "pilot": self.pilot},
                "folder": "(deleted)" if self.withdrawn and self.done.is_set() else paths.rel(self.folder)}


def _r(v, nd=5):
    return round(v, nd) if isinstance(v, float) else ("" if v is None else v)
