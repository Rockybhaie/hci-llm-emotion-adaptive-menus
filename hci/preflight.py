"""`python run.py check`: is everything ready for a real participant?"""

import importlib
import socket
import tempfile
import time
from pathlib import Path

from . import browser, config, paths, sensors, tasks
from .storage import SessionStore

OK, WARN, FAIL = "ok", "warn", "fail"


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
    out = []
    for gid in groups:
        g = cfg.group(gid)
        try:
            site = config.load_site(g["site"])
            task_cfg = config.load_tasks(g["tasks"])
            n = 0
            for s in ("A", "B"):
                for variant in (None, "repetitive"):
                    n += len(tasks.build_block(site, task_cfg, s, variant))
            out.append((f"{gid} site + tasks", OK, f"{site['name']}: {n} task variants resolve"))
        except config.ConfigError as exc:
            out.append((f"{gid} site + tasks", FAIL, str(exc)))
    return out


def _videos(cfg, groups, mock):
    needed = {cfg.washout["video"]}
    for gid in groups:
        for emo in cfg.group(gid)["emotions"]:
            video = cfg.emotions[emo]["induction"].get("video")
            if video:
                needed.add(video)
    out = []
    for v in sorted(needed):
        path = paths.VIDEOS / v
        if path.is_dir():
            n = len([p for p in path.iterdir() if p.suffix.lower() in (".mp4", ".webm")])
            exists, found = n > 0, f"{n} clips (playlist)"
        else:
            exists, found = path.exists(), "found"
        level = OK if exists else (WARN if mock else FAIL)
        out.append((f"video {v}", level, found if exists else "missing — see stimuli/README.md"))
    return out


def _port(cfg):
    host, port = cfg.experiment["server"]["host"], cfg.experiment["server"]["port"]
    with socket.socket() as s:
        free = s.connect_ex((host, port)) != 0
    return [("port", OK if free else FAIL, f"{port} free" if free else f"{port} in use (another session running?)")]


def _browser(cfg):
    exe = browser.find(cfg.experiment.get("browser", "edge"))
    return [("browser", OK if exe else FAIL, Path(exe).name if exe else "install Microsoft Edge or Chrome")]


def _devices(cfg, mock):
    out = []
    timeout = cfg.devices.get("startup_timeout", 15)
    with tempfile.TemporaryDirectory(prefix="hci-check-") as tmp:
        store = SessionStore(Path(tmp))
        ctx = sensors.SensorContext()
        for slot in ("eye_tracker", "gsr", "hr"):
            adapter = cfg.devices[slot]["adapter"]
            if mock and adapter != "none":
                adapter = "mock"
            if adapter == "none":
                out.append((slot, WARN, "disabled (adapter: none)"))
                continue
            try:
                sensor = sensors.create(slot, adapter, cfg.devices[slot].get(adapter), store, ctx)
                sensor.start()
                deadline = time.time() + timeout
                while sensor.samples == 0 and time.time() < deadline and not sensor.error:
                    time.sleep(0.2)
                first = sensor.samples
                time.sleep(3.0)
                hz = (sensor.samples - first) / 3.0
                sensor.stop()
                if sensor.samples == 0:
                    out.append((slot, FAIL, f"{adapter}: connected but no samples in {timeout}s"))
                else:
                    extra = ", ".join(f"{k}={v}" for k, v in sensor.info.items())
                    out.append((slot, OK, f"{adapter}: {hz:.0f} Hz {extra}".strip()))
            except sensors.SensorError as exc:
                out.append((slot, FAIL, str(exc)))
            except Exception as exc:
                out.append((slot, FAIL, f"{adapter}: {type(exc).__name__}: {exc}"))
        store.close()
    return out


def run(groups=None, mock=False, devices=True):
    results = list(_packages())
    try:
        cfg = config.load()
    except config.ConfigError as exc:
        return results + [("config", FAIL, str(exc))]
    results.append(("config", OK, "config/*.yaml valid"))
    groups = groups or list(cfg.groups)
    results += _content(cfg, groups) + _videos(cfg, groups, mock) + _port(cfg) + _browser(cfg)
    if devices:
        results += _devices(cfg, mock)
    return results
