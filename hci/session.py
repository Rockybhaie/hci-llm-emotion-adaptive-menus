"""One participant's session: the step plan, live state, and everything written to disk.

The browser only renders steps; the server is the source of truth for which step
is current, what each block's condition is, and what the correct answers are.
"""

import collections
import datetime as dt
import json
import platform
import random
import shutil
import threading

from . import __version__, counterbalance, paths, sensors, tasks
from .clock import SOURCE as CLOCK_SOURCE
from .clock import now
from .config import ConfigError, load_site, load_tasks
from .storage import SessionStore

AROUSAL = {"high": 0.85, "low": 0.15}
NEUTRAL_AROUSAL = 0.3
SENSOR_SLOTS = ("eye_tracker", "gsr", "hr")
VIDEO_EXTENSIONS = (".mp4", ".webm")


class SessionExists(Exception):
    pass


class Session:
    def __init__(self, cfg, group_id, participant, *, mock=False, fast=False, pilot=False,
                 resume=False, data_root=None):
        self.cfg = cfg
        self.group_id = group_id
        self.participant = participant
        self.mock, self.fast, self.pilot = mock, fast, pilot
        self.group = cfg.group(group_id)
        self.site = load_site(self.group["site"])
        self.task_cfg = load_tasks(self.group["tasks"])
        self.number = counterbalance.participant_number(participant)
        self.plan = counterbalance.assign(participant, self.group["emotions"])

        root = data_root or (paths.PILOT if pilot else paths.DATA)
        self.folder = root / group_id / participant
        previous = None
        if (self.folder / "session.json").exists():
            if not resume:
                raise SessionExists(
                    f"{paths.rel(self.folder)} already exists. Use another participant ID, "
                    f"or --resume to continue an interrupted session.")
            previous = json.loads((self.folder / "session.json").read_text(encoding="utf-8"))

        self.warnings = collections.deque(maxlen=8)
        self.rng = random.Random(self.number * 7919 + sum(map(ord, group_id)))
        self.blocks = self._build_blocks()
        self.steps = self._build_steps()
        self.store = SessionStore(self.folder)
        self.context = sensors.SensorContext()
        self.sensors = {}
        self.done = threading.Event()
        self._lock = threading.RLock()
        self.active_task = None
        self.client_info = {}
        self.calibration = {}
        self.induction_results = {}
        self.completed = set()
        self.withdrawn = False
        self.current = 0
        self.status = "created"
        self.t_zero = now()
        self.wall_zero = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        if previous:
            self._restore(previous)

    # ------------------------------------------------------------------ plan
    def _build_blocks(self):
        blocks = []
        for i, b in enumerate(self.plan["blocks"], start=1):
            emo = self.cfg.emotions[b["emotion"]]
            in_task = emo.get("in_task") or {}
            variant = in_task.get("task_variant")
            resolved = tasks.build_block(self.site, self.task_cfg, b["task_set"], variant,
                                         seed=self.number * 100 + i)
            blocks.append({"no": i, "emotion": b["emotion"], "task_set": b["task_set"], "variant": variant or "",
                           "arousal": AROUSAL[emo["arousal"]], "induction": emo["induction"],
                           "in_task": in_task, "tasks": resolved})
        return blocks

    def _video(self, name):
        """URL of a clip, or a list of URLs when `name` is a folder (played as a playlist)."""
        path = paths.VIDEOS / name
        if path.is_dir():
            clips = sorted(p for p in path.iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS)
            if clips:
                return [f"/stimuli/{name.rstrip('/')}/{p.name}" for p in clips]
        elif path.exists():
            return f"/stimuli/{name}"
        if not (self.mock or self.pilot):
            raise ConfigError(f"Missing stimulus video stimuli/videos/{name} (see stimuli/README.md)")
        self.warn(f"stimuli/videos/{name} missing, showing a placeholder")
        return None

    def _rating(self, tag, block=None, tlx=False):
        q = self.cfg.experiment["questionnaires"]
        items = list(q["emotion_items"])
        self.rng.shuffle(items)
        instruments = ["sam", "emotions"] + (["tlx"] if tlx else [])
        return dict(type="rating", phase="rating", block=block,
                    params={"tag": tag, "instruments": instruments, "emotion_items": items,
                            "scale": q["emotion_scale"]})

    def _induction(self, block):
        ind = block["induction"]
        kind = ind["kind"]
        t = lambda key: self.cfg.timing(key, self.fast)
        params = {"kind": kind, "part": block["no"] * 2 - 1}
        if kind in ("mist", "copying"):
            params["duration"] = t("induction")
        elif kind == "breathing":
            params.update(duration=t("induction"), video=self._video(ind["video"]))
        elif kind == "film":
            params.update(video=self._video(ind["video"]), start=ind.get("start", 0), end=ind.get("end"),
                          reflection=t("film_reflection") if ind.get("reflection") else 0,
                          max_duration=t("induction") if self.fast else None,
                          placeholder=t("induction"))
        elif kind == "briefing":
            params.update(message=ind["message"], min_read=t("briefing_min_read"))
        else:
            raise ConfigError(f"Unknown induction kind '{kind}'")
        return dict(type="induction", phase="induction", block=block["no"], params=params)

    def _tasks_step(self, block):
        in_task = block["in_task"]
        timeout = in_task.get("timeout", self.cfg.experiment["timings"]["task_timeout"])
        if self.fast:
            timeout = max(10, round(timeout / self.cfg.experiment["fast_divisor"] * 2))
        flags = {k: in_task.get(k, False) for k in
                 ("countdown", "evaluation_banner", "negative_feedback", "reassurance", "rewards")}
        flags["sabotage"] = in_task.get("sabotage") or None
        return dict(type="tasks", phase="tasks", block=block["no"], params={
            "block": block["no"], "part": block["no"] * 2, "site": self.site["id"], "site_name": self.site["name"],
            "duration": self.cfg.timing("task_block", self.fast), "timeout": timeout,
            "flags": flags, "tasks": [tasks.client_view(x) for x in block["tasks"]]})

    def _build_steps(self):
        exp = self.cfg.experiment
        t = lambda key: self.cfg.timing(key, self.fast)
        eye_enabled = self._adapter("eye_tracker") != "none"
        steps = [
            dict(type="welcome", phase="welcome", params={"title": exp["study_title"]}),
            dict(type="consent", phase="consent", params={}),
            dict(type="demographics", phase="demographics", params={}),
        ]
        if eye_enabled:
            c = exp["calibration"]
            steps.append(dict(type="calibration", phase="calibration", params={
                "points": c["points"], "validation_points": c["validation_points"],
                "max_error": c["max_error"], "max_attempts": c["max_attempts"]}))
        steps += [
            dict(type="rest", phase="baseline", params={"duration": t("baseline_rest")}),
            self._rating("baseline"),
        ]
        for i, block in enumerate(self.blocks):
            if i:
                steps += [dict(type="washout", phase="washout", params={
                              "video": self._video(self.cfg.washout["video"]), "duration": t("washout")}),
                          self._rating("post_washout")]
            n = block["no"]
            steps += [self._induction(block), self._rating(f"post_induction_{n}", n),
                      self._tasks_step(block), self._rating(f"post_tasks_{n}", n, tlx=True)]
        manipulations = sorted({b["induction"]["kind"] for b in self.blocks} |
                               {"sabotage" for b in self.blocks if b["in_task"].get("sabotage")} |
                               {"evaluation" for b in self.blocks if b["in_task"].get("evaluation_banner")} |
                               {"rewards" for b in self.blocks if b["in_task"].get("rewards")})
        steps += [dict(type="debrief", phase="debrief", params={"manipulations": manipulations}),
                  dict(type="end", phase="end", params={})]
        for i, s in enumerate(steps):
            s["index"] = i
            s.setdefault("block", None)
        return steps

    def _adapter(self, slot):
        return "mock" if self.mock and self.cfg.devices[slot]["adapter"] != "none" else \
            self.cfg.devices[slot]["adapter"]

    def emotion_of(self, step):
        if step["phase"] in ("baseline", "washout") or (step["phase"] == "rating" and not step["block"]):
            return "neutral"
        if step["block"]:
            return self.blocks[step["block"] - 1]["emotion"]
        return ""

    # --------------------------------------------------------------- sensors
    def start_sensors(self):
        sync = _LazyStream(self.store, "clock_sync", ["t", "stream", "adapter", "offset_s"])
        for slot in SENSOR_SLOTS:
            adapter = self._adapter(slot)
            options = self.cfg.devices[slot].get(adapter) or {}
            sensor = sensors.create(slot, adapter, options, self.store, self.context, sync)
            if sensor is None:
                continue
            sensor.start()
            self.sensors[slot] = sensor

    def wait_for_samples(self, timeout):
        """Raise if any sensor has produced nothing after `timeout` seconds."""
        deadline = now() + timeout
        while now() < deadline:
            if all(s.samples > 0 for s in self.sensors.values()):
                return
            threading.Event().wait(0.2)
        silent = [f"{slot} ({s.adapter})" for slot, s in self.sensors.items() if s.samples == 0]
        raise sensors.SensorError(f"No data from: {', '.join(silent)}")

    def stop_sensors(self):
        for s in self.sensors.values():
            s.stop()

    def eye(self):
        return self.sensors.get("eye_tracker")

    # --------------------------------------------------------------- helpers
    def warn(self, msg):
        self.warnings.append((dt.datetime.now().strftime("%H:%M:%S"), msg))

    def _t(self, value):
        return float(value) if isinstance(value, (int, float)) else now()

    def _marker(self, step, event, t):
        self.store.write("markers", [f"{t:.4f}", step["index"], step["type"], step["phase"],
                                     step["block"] or "", self.emotion_of(step), event])

    def _q(self, t, tag, step, instrument, item, value):
        self.store.write("questionnaires", [f"{t:.4f}", tag, step["block"] or "", self.emotion_of(step),
                                            instrument, item, value])

    def step(self):
        return self.steps[self.current]

    # ------------------------------------------------------------------- API
    def client_session(self):
        public = [{"index": s["index"], "type": s["type"], "params": s["params"]} for s in self.steps]
        return {"steps": public, "current": self.current, "fast": self.fast, "mock": self.mock,
                "title": self.cfg.experiment["study_title"]}

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
            if step["phase"] in ("induction", "tasks", "rating") and step["block"]:
                self.context.arousal = self.blocks[step["block"] - 1]["arousal"]
            elif step["phase"] in ("baseline", "washout"):
                self.context.arousal = NEUTRAL_AROUSAL
            if self.status == "created":
                self.status = "running"
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
            self._q(t, "consent", step, "consent", "agreed", int(bool(data.get("agreed"))))
            if not data.get("agreed"):
                self.warn("Participant declined consent")
        elif kind == "demographics":
            for k, v in data.items():
                self._q(t, "demographics", step, "demographics", k, v)
        elif kind == "rating":
            tag = step["params"]["tag"]
            for instrument in ("sam", "emotions", "tlx"):
                for item, value in (data.get(instrument) or {}).items():
                    self._q(t, tag, step, instrument, item, value)
        elif kind == "calibration":
            self.calibration = data
            if data.get("status") != "success":
                self.warn(f"Eye-tracker calibration weak (error {data.get('error')})")
        elif kind == "debrief":
            retain = data.get("retain_data") or ""
            self._q(t, "debrief", step, "debrief", "retain_data", retain)
            if retain == "withdraw":
                self.withdrawn = True
                self.warn("Participant withdrew: their data will be deleted at the end")
        elif kind == "induction":
            self.induction_results[f"block_{step['block']}"] = {"kind": step["params"]["kind"], **data}
        elif kind == "tasks":
            self._close_active("time_up", t)
            block = self.blocks[step["block"] - 1]
            started = set(data.get("started", []))
            for task in block["tasks"]:
                if task["id"] not in started:
                    self._task_row(block, task, None, None, "not_reached", "", {})

    # tasks -------------------------------------------------------------
    def _find_task(self, task_id):
        block = self.blocks[self.step()["block"] - 1]
        for task in block["tasks"]:
            if task["id"] == task_id:
                return block, task
        raise KeyError(task_id)

    def task_start(self, task_id, t=None):
        with self._lock:
            self._close_active("abandoned", self._t(t))
            block, task = self._find_task(task_id)
            self.active_task = {"block": block, "task": task, "t_start": self._t(t),
                                "counts": collections.Counter(), "pages": []}
            return {"ok": True}

    def task_answer(self, task_id, answer, t=None):
        with self._lock:
            a = self.active_task
            if not a or a["task"]["id"] != task_id:
                return {"ok": False}
            correct = answer == a["task"]["answer"]
            a["counts"]["answer_attempts"] += 1
            self._close_active("correct" if correct else "incorrect", self._t(t), answer)
            return {"ok": True, "correct": correct}

    def task_close(self, task_id, outcome, t=None):
        with self._lock:
            if self.active_task and self.active_task["task"]["id"] == task_id:
                self._close_active(outcome, self._t(t))
            return {"ok": True}

    def _close_active(self, outcome, t, answer=""):
        a = self.active_task
        if not a:
            return
        self.active_task = None
        self._task_row(a["block"], a["task"], a["t_start"], t, outcome, answer, a["counts"])

    def _task_row(self, block, task, t0, t1, outcome, answer, counts):
        self.store.write("tasks", {
            "block": block["no"], "emotion": block["emotion"], "task_set": block["task_set"],
            "variant": block["variant"], "task_id": task["id"], "type": task["type"],
            "target_pages": ";".join(task["targets"]),
            "t_start": "" if t0 is None else f"{t0:.4f}", "t_end": "" if t1 is None else f"{t1:.4f}",
            "duration_s": "" if t0 is None else f"{t1 - t0:.3f}", "outcome": outcome,
            "answer": answer, "correct_answer": task["answer"],
            **{k: counts.get(k, 0) for k in ("clicks", "menu_opens", "page_views", "wrong_pages",
                                             "sabotage_events", "answer_attempts")}})

    def _count(self, ev):
        a = self.active_task
        if not a or ev.get("task_id") != a["task"]["id"]:
            return
        name = ev.get("event", "")
        c = a["counts"]
        if name == "click":
            c["clicks"] += 1
        elif name == "menu_open":
            c["menu_opens"] += 1
        elif name == "page_view":
            c["page_views"] += 1
            page = f"{ev.get('section')}/{ev.get('page')}"
            if ev.get("page") and page not in a["task"]["targets"]:
                c["wrong_pages"] += 1
        elif name.startswith("sabotage_"):
            c["sabotage_events"] += 1
            if name == "sabotage_answer_expired":
                c["answer_attempts"] += 1

    # behavioural log -----------------------------------------------------
    def log(self, batch):
        with self._lock:
            step = self.step()
            for ev in batch.get("events", []):
                detail = ev.get("detail")
                self.store.write("events", [
                    f"{self._t(ev.get('t')):.4f}", step["index"], step["block"] or "", ev.get("task_id", ""),
                    ev.get("source", "shell"), ev.get("event", ""), ev.get("section", ""), ev.get("page", ""),
                    ev.get("item", ""), _r(ev.get("x")), _r(ev.get("y")),
                    json.dumps(detail, ensure_ascii=False) if detail not in (None, "") else ""])
                self._count(ev)
            mouse = batch.get("mouse", [])
            for t, x, y in mouse:
                self.store.write("mouse", [f"{t:.4f}", _r(x), _r(y)])
            if mouse:
                self.context.mouse = (mouse[-1][1], mouse[-1][2])
            for snap in batch.get("aoi", []):
                rows = snap.get("rects") or [{"id": "", "x0": "", "y0": "", "x1": "", "y1": ""}]
                for r in rows:
                    self.store.write("aoi", [f"{self._t(snap.get('t')):.4f}", snap.get("snapshot", ""),
                                             snap.get("kind", ""), r["id"], _r(r["x0"]), _r(r["y0"]),
                                             _r(r["x1"]), _r(r["y1"])])
        return {"ok": True}

    # calibration -----------------------------------------------------------
    def calibrate(self, action, payload):
        eye = self.eye()
        if eye is None:
            return {"ok": False, "error": "no eye tracker"}
        if action == "start":
            eye.calibration_start()
            return {"ok": True}
        if action == "point":
            return {"ok": eye.calibration_point(payload["x"], payload["y"])}
        if action == "compute":
            return {"ok": True, **eye.calibration_compute()}
        if action == "stop":
            eye.calibration_stop()
            return {"ok": True}
        if action == "validate":
            if eye.adapter == "mock":
                return {"ok": True, "error": 0.012, "samples": 60}
            gaze = [g for g in eye.gaze_since(payload["t0"]) if g[0] <= payload["t1"]]
            if not gaze:
                return {"ok": True, "error": None, "samples": 0}
            err = sum(((x - payload["x"]) ** 2 + (y - payload["y"]) ** 2) ** 0.5 for _, x, y in gaze) / len(gaze)
            return {"ok": True, "error": round(err, 4), "samples": len(gaze)}
        return {"ok": False, "error": f"unknown action {action}"}

    # ------------------------------------------------------------ lifecycle
    def abort(self, reason="researcher abort"):
        with self._lock:
            if self.done.is_set():
                return
            step = self.step()
            self._marker(step, f"abort: {reason}", now())
            self.warn(f"Session aborted ({reason})")
            if reason == "consent declined":
                self.withdrawn = True
            self.finish("declined" if reason == "consent declined" else "aborted")

    def finish(self, status):
        with self._lock:
            if self.done.is_set():
                return
            self._close_active("aborted" if status == "aborted" else "time_up", now())
            self.status = status
            self.t_end = now()
            self.stop_sensors()
            self._save()
            self.store.close()
        if self.withdrawn:
            # consent declined or withdrawn at debrief: keep nothing
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
        self.t_zero = prev["clock"]["t_zero"]
        self.wall_zero = prev["started"]
        self.calibration = prev.get("calibration", {})
        self.induction_results = prev.get("inductions", {})
        self.status = "running"
        self.warn(f"Resumed at step {self.current} ({self.steps[self.current]['type']})")
        self._marker(self.step(), "resumed", now())

    def _save(self):
        self.store.write_json("session", {
            "study": self.cfg.experiment["study_title"], "platform_version": __version__,
            "group": self.group_id, "participant": self.participant, "site": self.site["id"],
            "emotions": self.group["emotions"], "plan": self.plan,
            "blocks": [{k: b[k] for k in ("no", "emotion", "task_set", "variant")} for b in self.blocks],
            "flags": {"mock": self.mock, "fast": self.fast, "pilot": self.pilot},
            "status": self.status, "started": self.wall_zero,
            "clock": {"source": CLOCK_SOURCE, "t_zero": self.t_zero,
                      "note": "All 't' columns use this clock (seconds). t_zero = session start."},
            "devices": {slot: {"adapter": s.adapter, **s.info, "samples": s.samples, "error": s.error}
                        for slot, s in self.sensors.items()},
            "client": self.client_info, "calibration": self.calibration, "inductions": self.induction_results,
            "progress": {"current": self.current, "completed_steps": sorted(self.completed),
                         "total_steps": len(self.steps)},
            "duration_s": round(getattr(self, "t_end", now()) - self.t_zero, 1),
            "host": {"os": platform.platform(), "python": platform.python_version()},
        })

    def snapshot(self):
        step = self.step()
        return {"group": self.group_id, "participant": self.participant, "status": self.status,
                "step": self.current, "steps": len(self.steps), "type": step["type"], "phase": step["phase"],
                "block": step["block"], "emotion": self.emotion_of(step),
                "elapsed": now() - self.t_zero, "task": self.active_task["task"]["id"] if self.active_task else None,
                "sensors": {slot: s.status() for slot, s in self.sensors.items()},
                "warnings": list(self.warnings), "flags": {"mock": self.mock, "fast": self.fast, "pilot": self.pilot},
                "folder": "(deleted)" if self.withdrawn and self.done.is_set()
                else str(paths.rel(self.folder))}


class _LazyStream:
    """Only creates the CSV once something is written (clock_sync stays absent for mock sensors)."""

    def __init__(self, store, name, columns):
        self.store, self.name, self.columns = store, name, columns

    def write(self, row):
        self.store.stream(self.name, self.columns).write(row)


def _r(v, nd=5):
    return round(v, nd) if isinstance(v, float) else ("" if v is None else v)
