"""`python run.py check`: is everything ready for a real participant?

Checks packages, config, every task answer in every menu, the stimulus videos, the port and the browser.
"""

import importlib
import socket
from pathlib import Path

from . import browser, config, menus, paths, tasks

OK, WARN, FAIL = "ok", "warn", "fail"

# Assumed participant speeds for the planned length (docs/protocol.md). Timed parts use the config.
ASSUMED = {"intro_s": 240, "rating_sam_s": 25, "rating_emotions_s": 25, "rating_tlx_short_s": 20, "menu_rank_s": 20,
           "practice_per_menu_s": 75, "task_typical_s": 26, "task_feedback_s": 1.5, "first_subblock_intro_s": 20,
           "next_subblock_intro_s": 8, "debrief_s": 90, "booster_overhead_s": 5, "induction_intro_s": 15}


def _packages():
    out = []
    for mod, pip in (("fastapi", "fastapi"), ("uvicorn", "uvicorn"), ("pandas", "pandas"),
                     ("yaml", "pyyaml"), ("rich", "rich")):
        try:
            importlib.import_module(mod)
            out.append((f"package {pip}", OK, "installed"))
        except ImportError:
            out.append((f"package {pip}", FAIL, f"pip install {pip}"))
    return out


def _content(cfg, groups):
    """Every subset resolves (also in the boredom wording) and is solvable from each of the group's menus."""
    out = []
    n_tasks = cfg.experiment["session"]["tasks_per_subblock"]
    for gid in groups:
        g = cfg.group(gid)
        try:
            site = config.load_site(g["site"])
            task_cfg = config.load_tasks(g["tasks"])
            resolved = 0
            for subset in ("S1", "S2", "S3", "S4", "S5", "S6"):
                for variant in (None, "repetitive"):
                    for mid in g["menus"]:
                        block = tasks.build_subset(site, task_cfg, subset, variant, seed=1, menu_type=cfg.menu(mid)["type"])
                        if len(block) != n_tasks:
                            raise config.ConfigError(f"{gid} {subset} has {len(block)} tasks, expected {n_tasks}")
                        resolved += len(block)
            practice = tasks.build_subset(site, task_cfg, "P", seed=1)
            if len(practice) < 2 * len(g["menus"]):
                raise config.ConfigError(f"{gid} practice pool has {len(practice)} tasks, needs {2 * len(g['menus'])}")
            out.append((f"{gid} tasks", OK, f"{site['name']}: 6 subsets x 3 menus + practice pool, {resolved} task variants resolve"))
        except config.ConfigError as exc:
            out.append((f"{gid} tasks", FAIL, str(exc)))
    return out


def _videos(cfg, groups, lenient):
    required = {cfg.washout["video"]}
    optional = set()
    for gid in groups:
        for emo in cfg.group(gid)["emotions"]:
            e = cfg.emotions[emo]
            if e["induction"].get("video"):
                required.add(e["induction"]["video"])
            b = e["booster"]
            if b.get("video"):
                (optional if b["kind"] == "clip" else required).add(b["video"])
    out = []
    for v in sorted(required | optional):
        path = paths.VIDEOS / v
        if path.is_dir():
            n = len([p for p in path.iterdir() if p.suffix.lower() in (".mp4", ".webm")])
            exists, found = n > 0, f"{n} clips (playlist)"
        else:
            exists, found = path.exists(), "found"
        if exists:
            level, msg = OK, found
        elif v in optional:
            level, msg = WARN, "missing: a clearly marked placeholder screen is shown instead (see stimuli/README.md)"
        else:
            level, msg = (WARN if lenient else FAIL), "missing: see stimuli/README.md"
        out.append((f"video {v}", level, msg))
    return out


def _port(cfg):
    host, port = cfg.experiment["server"]["host"], cfg.experiment["server"]["port"]
    with socket.socket() as s:
        free = s.connect_ex((host, port)) != 0
    return [("port", OK if free else FAIL, f"{port} free" if free else f"{port} in use (another session running?)")]


def _browser(cfg):
    exe = browser.find(cfg.experiment.get("browser", "edge"))
    return [("browser", OK if exe else FAIL, Path(exe).name if exe else "install Microsoft Edge or Chrome")]


def estimate_minutes(cfg, gid):
    """(typical, worst-case) minutes for one session of group `gid`, from the config and ASSUMED speeds."""
    a, ex = ASSUMED, cfg.experiment
    t, sess = ex["timings"], ex["session"]
    n_tasks, n_menus = sess["tasks_per_subblock"], len(cfg.group(gid)["menus"])
    emotion_rating = a["rating_emotions_s"]
    both_ratings = a["rating_sam_s"] + emotion_rating

    def induction(emo):
        ind = cfg.emotions[emo]["induction"]
        if ind["kind"] == "film":
            clip = (ind.get("end") or 300) - ind.get("start", 0)
            return clip + (t["film_reflection"] if ind.get("reflection") else 0) + a["induction_intro_s"]
        if ind["kind"] == "briefing":
            return t["briefing_min_read"] + 10
        return t["induction"] + a["induction_intro_s"]

    def booster(emo):
        b = cfg.emotions[emo]["booster"]
        return b.get("duration", 35) + a["booster_overhead_s"]

    def total(worst):
        s = a["intro_s"] + t["baseline_rest"] + both_ratings + n_menus * a["practice_per_menu_s"]
        for i, emo in enumerate(cfg.group(gid)["emotions"]):
            if i:
                s += t["washout"] + 10 + both_ratings
            timeout = (cfg.emotions[emo].get("in_task") or {}).get("timeout", t["task_timeout"])
            per_task = (timeout if worst else a["task_typical_s"]) + a["task_feedback_s"]
            s += induction(emo) + both_ratings
            for sb in range(n_menus):
                s += n_tasks * per_task + (a["first_subblock_intro_s"] if sb == 0 else a["next_subblock_intro_s"])
                s += emotion_rating + a["rating_tlx_short_s"]
                if sb:
                    s += booster(emo)
            s += a["menu_rank_s"]
        return (s + a["debrief_s"]) / 60

    return round(total(False), 1), round(total(True), 1)


def _length(cfg, groups):
    out = []
    for gid in groups:
        typical, worst = estimate_minutes(cfg, gid)
        level = OK if worst <= 55 else WARN
        out.append((f"{gid} session length", level, f"about {typical:.0f} min typical, {worst:.0f} min if every task times out"))
    return out


def _menus(cfg):
    out = []
    for gid, g in cfg.groups.items():
        for mid in g["menus"]:
            m = cfg.menu(mid)
            site = config.load_site(g["site"])
            sections = [s["id"] for s in site["sections"]]
            lo, hi = menus.click_range(m["type"], sections)
            if not (paths.WEB / "core" / "menus" / f"{m['type']}.js").exists():
                out.append((f"menu {mid}", FAIL, f"web/core/menus/{m['type']}.js is missing"))
            else:
                out.append((f"menu {mid}", OK, f"{gid} {m['name']}: {lo}-{hi} clicks to any page"))
    return out


def run(groups=None, lenient=False):
    results = list(_packages())
    try:
        cfg = config.load()
    except config.ConfigError as exc:
        return results + [("config", FAIL, str(exc))]
    results.append(("config", OK, "config/*.yaml valid"))
    groups = groups or list(cfg.groups)
    results += _menus(cfg) + _content(cfg, groups) + _videos(cfg, groups, lenient) + _length(cfg, groups) \
        + _port(cfg) + _browser(cfg)
    return results
