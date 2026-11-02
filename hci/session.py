"""One participant's session: the step plan, live state, and everything written to disk.

The browser only renders steps; the server is the source of truth for which step is current,
what each sub-block's condition is, and what the correct answers are.

Structure of a session (see README.md):

  welcome, consent, demographics, baseline rest, mood rating
  practice x 3 (one per menu, neutral)
  emotion block 1: induction, mood rating,
                   sub-block 1 (menu A), mood+workload rating,
                   booster, sub-block 2 (menu B), mood+workload rating,
                   booster, sub-block 3 (menu C), mood+workload rating,  menu ranking
  washout video, mood rating
  emotion block 2: the same with the group's other emotion
  debrief, end

Every row written during a step is labelled with that step's phase, emotion block, sub-block and menu.
"""

import collections
import datetime as dt
import json
import math
import platform
import random
import shutil
import threading

from . import __version__, counterbalance, paths, tasks
from .clock import SOURCE as CLOCK_SOURCE
from .clock import now
from .config import ConfigError, load_site, load_tasks
from .storage import SessionStore

VIDEO_EXTENSIONS = (".mp4", ".webm")
FLAG_KEYS = ("countdown", "evaluation_banner", "negative_feedback", "reassurance", "rewards")
DEFAULT_VIEWPORT = (1920, 1080)


class SessionExists(Exception):
    pass


class Session:
    def __init__(self, cfg, group_id, participant, *, fast=False, pilot=False, resume=False, data_root=None):
        self.cfg = cfg
        self.group_id = group_id
        self.participant = participant
        self.fast, self.pilot = fast, pilot
        self.group = cfg.group(group_id)
        self.site = load_site(self.group["site"])
        self.task_cfg = load_tasks(self.group["tasks"])
        self.number = counterbalance.participant_number(participant)
        self.plan = counterbalance.assign(participant, self.group["emotions"], self.group["menus"])

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
        self.emotion_of_block = {b["no"]: b["emotion"] for b in self.plan["blocks"]}
        self.steps = self._build_steps()
        self.store = SessionStore(self.folder)
        self.done = threading.Event()
        self._lock = threading.RLock()
        self.active_task = None
        self.client_info = {}
        self.induction_results = {}
        self.completed = set()
        self.started = set()
        self.attempts = {}
        self.withdrawn = False
        self.current = 0
        self.status = "created"
        self.t_zero = now()
        self.wall_zero = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        if previous:
            self._restore(previous)

    # ------------------------------------------------------------------ helpers
    def _t(self, value):
        return float(value) if isinstance(value, (int, float)) else now()

    def _dur(self, seconds):
        """A configured duration, shortened in --fast dry runs."""
        return max(3, round(seconds / self.cfg.experiment["fast_divisor"])) if self.fast else seconds

    def timing(self, key):
        return self.cfg.timing(key, self.fast)

    def warn(self, msg):
        self.warnings.append((dt.datetime.now().strftime("%H:%M:%S"), msg))

    def menu_type(self, menu_id):
        return self.cfg.menu(menu_id)["type"] if menu_id else ""

    def emotion_of(self, step):
        if step["phase"] in ("baseline", "washout", "practice") or (step["phase"] == "rating" and not step["emotion_block"]):
            return "neutral"
        if step["emotion_block"]:
            return self.emotion_of_block[step["emotion_block"]]
        return ""

    def step(self):
        return self.steps[self.current]

    def label(self, step):
        """The label columns shared by every file: phase, emotion_block, emotion, sub_block, menu_id, menu_type."""
        return [step["phase"], step["emotion_block"] or "", self.emotion_of(step), step["sub_block"] or "",
                step["menu_id"], self.menu_type(step["menu_id"])]

    # ------------------------------------------------------------------ media
    def _video(self, name, optional=False):
        """URL of a clip, or a list of URLs when `name` is a folder (played as a playlist)."""
        path = paths.VIDEOS / name
        if path.is_dir():
            clips = sorted(p for p in path.iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS)
            if clips:
                return [f"/stimuli/{name.rstrip('/')}/{p.name}" for p in clips]
        elif path.exists():
            return f"/stimuli/{name}"
        if not (optional or self.pilot):
            raise ConfigError(f"Missing stimulus video stimuli/videos/{name} (see stimuli/README.md)")
        self.warn(f"stimuli/videos/{name} missing, showing a placeholder")
        return None

    # ------------------------------------------------------------------ plan
    def _rating(self, tag, emotion_block=None, sub_block=None, menu_id="", instruments=("sam", "emotions")):
        q = self.cfg.experiment["questionnaires"]
        items = list(q["emotion_items"])
        self.rng.shuffle(items)
        return dict(type="rating", phase="rating", emotion_block=emotion_block, sub_block=sub_block, menu_id=menu_id,
                    params={"tag": tag, "instruments": list(instruments), "emotion_items": items, "scale": q["emotion_scale"]})

    def _induction(self, block_no):
        emotion = self.emotion_of_block[block_no]
        ind = self.cfg.emotions[emotion]["induction"]
        kind = ind["kind"]
        params = {"kind": kind, "part": block_no * 2 - 1}
        if kind in ("mist", "copying"):
            params["duration"] = self.timing("induction")
        elif kind == "breathing":
            params.update(duration=self.timing("induction"), video=self._video(ind["video"]))
        elif kind == "film":
            params.update(video=self._video(ind["video"]), start=ind.get("start", 0), end=ind.get("end"),
                          reflection=self.timing("film_reflection") if ind.get("reflection") else 0,
                          max_duration=self.timing("induction") if self.fast else None,
                          placeholder=self.timing("induction"))
        elif kind == "briefing":
            params.update(message=ind["message"], min_read=self.timing("briefing_min_read"))
        else:
            raise ConfigError(f"Unknown induction kind '{kind}'")
        return dict(type="induction", phase="induction", emotion_block=block_no, sub_block=None, menu_id="", params=params)

    def _booster(self, block_no, sub_block):
        emotion = self.emotion_of_block[block_no]
        b = self.cfg.emotions[emotion]["booster"]
        kind = b["kind"]
        params = {"kind": kind, "duration": self._dur(b.get("duration", 35))}
        if kind == "breathing":
            params["video"] = self._video(b["video"])
        elif kind == "clip":
            params.update(video=self._video(b["video"], optional=True),
                          reflection=self._dur(b["reflection"]) if b.get("reflection") else 0)
        elif kind == "speed_reminder":
            params["min_read"] = self.timing("booster_min_read")
            params["rank"] = self._fake_rank(block_no, sub_block)
        elif kind not in ("mist", "copying"):
            raise ConfigError(f"Unknown booster kind '{kind}'")
        return dict(type="booster", phase="booster", emotion_block=block_no, sub_block=sub_block, menu_id="", params=params)

    @staticmethod
    def _fake_rank(block_no, sub_block):
        """The 'current rank' shown in the frustration booster: fixed and unfavourable (debriefed at the end)."""
        return {"place": 13 + sub_block, "of": 18, "behind_s": 6 + 3 * sub_block}

    def _flags(self, in_task, timeout):
        flags = {k: in_task.get(k, False) for k in FLAG_KEYS}
        flags["sabotage"] = in_task.get("sabotage") or None
        return flags

    def _task_params(self, tasks_resolved, menu_id, timeout, flags):
        menu = self.cfg.menu(menu_id)
        return {"site": self.site["id"], "site_name": self.site["name"], "menu_id": menu_id,
                "menu_label": menu["label"], "menu_how": menu["how"], "timeout": timeout, "flags": flags,
                "tasks": [tasks.client_view(x) for x in tasks_resolved]}

    def _practice_step(self, menu_id, pool_idx):
        menu_index = self.group["menus"].index(menu_id)
        pool = tasks.build_subset(self.site, self.task_cfg, "P", seed=self.number * 31 + menu_index,
                                  menu_type=self.menu_type(menu_id))
        chosen = [pool[i] for i in pool_idx][: self.cfg.experiment["session"]["practice_tasks_per_menu"]]
        timeout = self._dur(self.cfg.experiment["timings"]["practice_task_timeout"]) if self.fast \
            else self.cfg.experiment["timings"]["practice_task_timeout"]
        params = self._task_params(chosen, menu_id, timeout, self._flags({}, timeout))
        params.update(practice=True, part="Practice")
        return dict(type="practice", phase="practice", emotion_block=None, sub_block=None, menu_id=menu_id,
                    params=params, tasks_full=chosen, subset="P")

    def _tasks_step(self, block, sub):
        emotion = block["emotion"]
        in_task = self.cfg.emotions[emotion].get("in_task") or {}
        variant = in_task.get("task_variant")
        menu_id = sub["menu"]
        resolved = tasks.build_subset(self.site, self.task_cfg, sub["subset"], variant,
                                      seed=self.number * 1000 + block["no"] * 10 + sub["sub_block"],
                                      menu_type=self.menu_type(menu_id))
        n = self.cfg.experiment["session"]["tasks_per_subblock"]
        if len(resolved) != n:
            raise ConfigError(f"Subset {sub['subset']} has {len(resolved)} tasks, expected {n}")
        timeout = in_task.get("timeout", self.cfg.experiment["timings"]["task_timeout"])
        if self.fast:
            timeout = max(10, round(timeout / self.cfg.experiment["fast_divisor"] * 2))
        params = self._task_params(resolved, menu_id, timeout, self._flags(in_task, timeout))
        params.update(practice=False, part=f"Part {block['no'] * 2}", sub_block=sub["sub_block"],
                      first=sub["sub_block"] == 1)
        return dict(type="tasks", phase="tasks", emotion_block=block["no"], sub_block=sub["sub_block"], menu_id=menu_id,
                    params=params, tasks_full=resolved, subset=sub["subset"], variant=variant or "")

    def _menu_rank(self, block):
        menus = [{"id": s["menu"], "label": self.cfg.menu(s["menu"])["label"], "position": s["sub_block"]}
                 for s in block["sub_blocks"]]
        return dict(type="menu_rank", phase="menu_rank", emotion_block=block["no"], sub_block=None, menu_id="",
                    params={"menus": menus})

    def _build_steps(self):
        exp = self.cfg.experiment
        steps = [
            dict(type="welcome", phase="welcome", params={"title": exp["study_title"]}),
            dict(type="consent", phase="consent", params={}),
            dict(type="demographics", phase="demographics", params={}),
            dict(type="rest", phase="baseline", params={"duration": self.timing("baseline_rest")}),
            self._rating("baseline"),
        ]
        for p in self.plan["practice"]:
            steps.append(self._practice_step(p["menu"], p["pool"]))
        manipulations = {"menus"}
        for i, block in enumerate(self.plan["blocks"]):
            n = block["no"]
            emotion = block["emotion"]
            cfg_e = self.cfg.emotions[emotion]
            if i:
                steps += [dict(type="washout", phase="washout", params={
                              "video": self._video(self.cfg.washout["video"]), "duration": self.timing("washout")}),
                          self._rating("post_washout")]
            steps += [self._induction(n), self._rating(f"post_induction_{n}", n)]
            for sub in block["sub_blocks"]:
                s = sub["sub_block"]
                if s > 1:
                    steps.append(self._booster(n, s))
                steps += [self._tasks_step(block, sub),
                          self._rating(f"subblock_{n}_{s}", n, s, sub["menu"], ("emotions", "tlx_short"))]
            steps.append(self._menu_rank(block))
            in_task = cfg_e.get("in_task") or {}
            manipulations |= {cfg_e["induction"]["kind"], cfg_e["booster"]["kind"]}
            if in_task.get("sabotage"):
                manipulations.add("sabotage")
            if in_task.get("evaluation_banner"):
                manipulations.add("evaluation")
            if in_task.get("rewards"):
                manipulations.add("rewards")
        steps += [dict(type="debrief", phase="debrief", params={"manipulations": sorted(manipulations)}),
                  dict(type="end", phase="end", params={})]
        for i, s in enumerate(steps):
            s["index"] = i
            s.setdefault("emotion_block", None)
            s.setdefault("sub_block", None)
            s.setdefault("menu_id", "")
        return steps

    # ------------------------------------------------------------------ writing
    def _marker(self, step, event, t):
        self.store.write("markers", [f"{t:.4f}", step["index"], step["type"], *self.label(step), event])

    def _q(self, t, tag, step, instrument, item, value):
        self.store.write("questionnaires", [f"{t:.4f}", tag, *self.label(step), instrument, item, value])

    # ------------------------------------------------------------------- API
    def client_session(self):
        public = [{"index": s["index"], "type": s["type"], "params": s["params"]} for s in self.steps]
        return {"steps": public, "current": self.current, "fast": self.fast,
                "title": self.cfg.experiment["study_title"]}

    def set_client_info(self, info):
        self.client_info = info
        if info.get("innerWidth") and info.get("screenWidth") and \
                abs(info["innerWidth"] - info["screenWidth"]) > 2 and not self.pilot:
            self.warn("Browser is not fullscreen: the layout (and menu positions) will differ from other participants")
        self._save()

    def step_start(self, index, t=None):
        with self._lock:
            if index != self.current:
                return {"ok": False, "current": self.current}
            step = self.step()
            t = self._t(t)
            self.started.add(index)
            self._marker(step, "start", t)
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
            for instrument in ("sam", "emotions", "tlx", "tlx_short"):
                for item, value in (data.get(instrument) or {}).items():
                    self._q(t, tag, step, instrument, item, value)
        elif kind == "menu_rank":
            for menu_id, rank in (data.get("ranks") or {}).items():
                self._q(t, f"menu_rank_{step['emotion_block']}", step, "menu_rank", menu_id, rank)
        elif kind == "debrief":
            retain = data.get("retain_data") or ""
            self._q(t, "debrief", step, "debrief", "retain_data", retain)
            if retain == "withdraw":
                self.withdrawn = True
                self.warn("Participant withdrew: their data will be deleted at the end")
        elif kind in ("induction", "booster"):
            self.induction_results[f"{kind}_{step['index']}"] = {"kind": step["params"]["kind"], **data}
        elif kind in ("tasks", "practice"):
            self._close_active("abandoned", t)
            started = set(data.get("started", []))
            for task in step["tasks_full"]:
                if task["id"] not in started:
                    self._task_row(step, task, None, None, "not_reached", "", {}, 0.0)

    # tasks -------------------------------------------------------------
    def _find_task(self, task_id):
        step = self.step()
        for task in step.get("tasks_full", []):
            if task["id"] == task_id:
                return step, task
        raise KeyError(task_id)

    def task_start(self, task_id, t=None):
        with self._lock:
            self._close_active("abandoned", self._t(t))
            step, task = self._find_task(task_id)
            self.active_task = {"step": step, "task": task, "t_start": self._t(t), "counts": collections.Counter(),
                                "mouse_last": None, "mouse_path": 0.0}
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
        self._task_row(a["step"], a["task"], a["t_start"], t, outcome, answer, a["counts"], a["mouse_path"])

    def _viewport(self):
        w = self.client_info.get("innerWidth") or DEFAULT_VIEWPORT[0]
        h = self.client_info.get("innerHeight") or DEFAULT_VIEWPORT[1]
        return w, h

    def _task_row(self, step, task, t0, t1, outcome, answer, counts, mouse_path_norm):
        w, h = self._viewport()
        row = {
            "phase": step["phase"], "emotion_block": step["emotion_block"] or "", "emotion": self.emotion_of(step),
            "sub_block": step["sub_block"] or "", "menu_id": step["menu_id"], "menu_type": self.menu_type(step["menu_id"]),
            "subset": step.get("subset", ""), "attempt": self.attempts.get(step["index"], 1),
            "variant": step.get("variant", ""), "task_id": task["id"], "type": task["type"],
            "target_pages": ";".join(task["targets"]),
            "t_start": "" if t0 is None else f"{t0:.4f}", "t_end": "" if t1 is None else f"{t1:.4f}",
            "duration_s": "" if t0 is None else f"{t1 - t0:.3f}", "outcome": outcome,
            "correct": int(outcome == "correct"), "answer": answer, "correct_answer": task["answer"],
            "shortest_clicks": task.get("shortest_clicks", ""), "shortest_steps": task.get("shortest_steps", ""),
            "mouse_path_px": round(mouse_path_norm, 1) if t0 is not None else "",
            **{k: counts.get(k, 0) for k in ("clicks", "menu_clicks", "menu_opens", "page_views", "wrong_pages",
                                             "backtracks", "sabotage_events", "answer_attempts")}}
        self.store.write("tasks", row)

    def _count(self, ev):
        a = self.active_task
        if not a or ev.get("task_id") != a["task"]["id"]:
            return
        name = ev.get("event", "")
        c = a["counts"]
        if name == "click" and ev.get("source") == "site":
            c["clicks"] += 1
            target = (ev.get("detail") or {}).get("target", "") if isinstance(ev.get("detail"), dict) else ""
            if str(target).startswith(("nav:", "item:")):
                c["menu_clicks"] += 1
        elif name == "menu_open":
            c["menu_opens"] += 1
        elif name == "page_view":
            c["page_views"] += 1
            page = f"{ev.get('section')}/{ev.get('page')}"
            if ev.get("page") and page not in a["task"]["targets"]:
                c["wrong_pages"] += 1
        elif name == "backtrack":
            c["backtracks"] += 1
        elif name.startswith("sabotage_"):
            c["sabotage_events"] += 1
            if name == "sabotage_answer_expired":
                c["answer_attempts"] += 1

    def _mouse_path(self, samples):
        """Add the on-screen distance (pixels) of new mouse samples to the running task."""
        a = self.active_task
        if not a:
            return
        w, h = self._viewport()
        for t, x, y in samples:
            if t < a["t_start"]:
                continue
            last = a["mouse_last"]
            if last is not None:
                a["mouse_path"] += math.hypot((x - last[0]) * w, (y - last[1]) * h)
            a["mouse_last"] = (x, y)

    # behavioural log -----------------------------------------------------
    def log(self, batch):
        with self._lock:
            step = self.step()
            label = self.label(step)
            phase, emotion_block, emotion, sub_block, menu_id, menu_type = label
            for ev in batch.get("events", []):
                detail = ev.get("detail")
                self.store.write("events", [
                    f"{self._t(ev.get('t')):.4f}", step["index"], phase, emotion_block, emotion, sub_block, menu_id, menu_type,
                    ev.get("task_id", ""), ev.get("source", "shell"), ev.get("event", ""), ev.get("section", ""),
                    ev.get("page", ""), ev.get("item", ""), _r(ev.get("x")), _r(ev.get("y")),
                    json.dumps(detail, ensure_ascii=False) if detail not in (None, "") else ""])
                self._count(ev)
            mouse = batch.get("mouse", [])
            for t, x, y in mouse:
                self.store.write("mouse", [f"{t:.4f}", _r(x), _r(y)])
            self._mouse_path(mouse)
            for snap in batch.get("aoi", []):
                rows = snap.get("rects") or [{"id": "", "x0": "", "y0": "", "x1": "", "y1": ""}]
                for r in rows:
                    self.store.write("aoi", [f"{self._t(snap.get('t')):.4f}", snap.get("snapshot", ""),
                                             snap.get("kind", ""), r["id"], _r(r["x0"]), _r(r["y0"]),
                                             _r(r["x1"]), _r(r["y1"]), phase, sub_block, menu_id])
        return {"ok": True}

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
            self._close_active("aborted" if status == "aborted" else "abandoned", now())
            self.status = status
            self.t_end = now()
            self._save()
            self.store.close()
        if self.withdrawn:
            # consent declined or withdrawn at debrief: keep nothing
            shutil.rmtree(self.folder, ignore_errors=True)
            self.status = "withdrawn" if status == "complete" else status
            self.warn("All data for this participant was deleted")
        else:
            try:
                from .export import merge_session, subblock_summary
                subblock_summary(self.folder)
                merge_session(self.folder)
            except Exception as exc:
                self.warn(f"merged.csv / subblocks.csv could not be built: {exc}")
        self.done.set()

    def _restore(self, prev):
        if prev.get("plan") != self.plan:
            raise ConfigError("Cannot resume: the counterbalancing plan no longer matches session.json")
        self.completed = set(prev["progress"]["completed_steps"])
        self.started = set(prev["progress"].get("started_steps", []))
        self.attempts = {int(k): v for k, v in prev["progress"].get("attempts", {}).items()}
        self.current = min(set(range(len(self.steps))) - self.completed, default=len(self.steps) - 1)
        self.t_zero = prev["clock"]["t_zero"]
        self.wall_zero = prev["started"]
        self.induction_results = prev.get("inductions", {})
        self.status = "running"
        if self.current in self.started:      # the interrupted step starts over: its first attempt stays in the files
            self.attempts[self.current] = self.attempts.get(self.current, 1) + 1
        step = self.step()
        where = f"{step['type']}" + (f", emotion block {step['emotion_block']}" if step["emotion_block"] else "") \
            + (f", sub-block {step['sub_block']} ({step['menu_id']})" if step["sub_block"] else "")
        self.warn(f"Resumed at step {self.current} ({where})")
        self._marker(step, "resumed", now())

    def _save(self):
        self.store.write_json("session", {
            "study": self.cfg.experiment["study_title"], "platform_version": __version__,
            "group": self.group_id, "participant": self.participant, "site": self.site["id"],
            "emotions": self.group["emotions"], "menus": self.group["menus"], "plan": self.plan,
            "flags": {"fast": self.fast, "pilot": self.pilot},
            "status": self.status, "started": self.wall_zero,
            "clock": {"source": CLOCK_SOURCE, "t_zero": self.t_zero,
                      "note": "All 't' columns use this clock (seconds). t_zero = session start."},
            "client": self.client_info, "inductions": self.induction_results,
            "progress": {"current": self.current, "completed_steps": sorted(self.completed),
                         "started_steps": sorted(self.started), "attempts": self.attempts,
                         "total_steps": len(self.steps)},
            "duration_s": round(getattr(self, "t_end", now()) - self.t_zero, 1),
            "host": {"os": platform.platform(), "python": platform.python_version()},
        })
        self.store.write_json("plan", self.plan)
        (self.folder / "plan.txt").write_text(counterbalance.describe(self.plan) + "\n", encoding="utf-8")

    def snapshot(self):
        step = self.step()
        menu = self.cfg.menus.get(step["menu_id"]) if step["menu_id"] else None
        return {"group": self.group_id, "participant": self.participant, "status": self.status,
                "step": self.current, "steps": len(self.steps), "type": step["type"], "phase": step["phase"],
                "emotion_block": step["emotion_block"], "sub_block": step["sub_block"], "menu_id": step["menu_id"],
                "menu_name": menu["name"] if menu else "", "emotion": self.emotion_of(step),
                "elapsed": now() - self.t_zero, "task": self.active_task["task"]["id"] if self.active_task else None,
                "plan": counterbalance.describe(self.plan),
                "warnings": list(self.warnings), "flags": {"fast": self.fast, "pilot": self.pilot},
                "folder": "(deleted)" if self.withdrawn and self.done.is_set() else str(paths.rel(self.folder))}


def _r(v, nd=5):
    return round(v, nd) if isinstance(v, float) else ("" if v is None else v)
