"""`python run.py check`: is everything ready for a real participant?"""

import importlib
import socket
import tempfile
import time
from pathlib import Path

from . import browser, config, content, paths
from .storage import SessionStore

OK, WARN, FAIL = "ok", "warn", "fail"


def _packages(sensors):
    needed = [("fastapi", "fastapi"), ("uvicorn", "uvicorn"), ("pandas", "pandas"), ("yaml", "pyyaml"),
              ("rich", "rich")]
    if sensors:
        needed += [("cv2", "opencv-python"), ("mediapipe", "mediapipe"), ("onnxruntime", "onnxruntime"),
                   ("eyetrax", "eyetrax (pip install --no-deps eyetrax)")]
    out = []
    for mod, pip in needed:
        try:
            importlib.import_module(mod)
            out.append((f"package {pip.split()[0]}", OK, "installed"))
        except ImportError:
            out.append((f"package {pip.split()[0]}", FAIL, f"pip install {pip}"))
    return out


def _content(cfg):
    out = []
    for q in cfg.queries:
        try:
            data = content.validate(q, cfg.looks)
            prov = data.get("provenance") or {}
            status = prov.get("status", "unknown")
            level = OK if status in ("reviewed", "frozen") else WARN
            out.append((f"answers {q}", level,
                        f"{data['type']}: {len(cfg.looks)} looks valid · content status: {status}"
                        + ("" if level == OK else " (have the team review it, then set status: reviewed)")))
        except config.ConfigError as exc:
            out.append((f"answers {q}", FAIL, str(exc)))
    return out


def _models(cfg):
    out = []
    for slot, key in (("camera", "face_landmarker"), ("emotion", None)):
        if slot == "camera":
            p = (cfg.devices.get("camera") or {}).get(key, "models/face_landmarker.task")
        else:
            p = ((cfg.devices.get("emotion") or {}).get("yolo") or {}).get("model", "models/emotion_yolo11n_cls.onnx")
        path = paths.ROOT / p
        out.append((f"model {Path(p).name}", OK if path.exists() else FAIL,
                    "found" if path.exists() else f"missing: {p} (see models/README.md)"))
    return out


def _port(cfg):
    host, port = cfg.study["server"]["host"], cfg.study["server"]["port"]
    with socket.socket() as s:
        free = s.connect_ex((host, port)) != 0
    return [("port", OK if free else FAIL, f"{port} free" if free else f"{port} in use (another session running?)")]


def _browser(cfg):
    exe = browser.find(cfg.study.get("browser", "edge"))
    return [("browser", OK if exe else FAIL, Path(exe).name if exe else "install Microsoft Edge or Chrome")]


def _sensors(cfg, mock):
    from .sensing import Sensing, planned
    plan = planned(cfg.devices, mode="mock" if mock else "config")
    if not plan:
        return [("sensors", WARN, "none configured in config/devices.yaml")]
    with tempfile.TemporaryDirectory(prefix="hci-check-") as tmp:
        store = SessionStore(Path(tmp))
        sensing = Sensing(store, mode="mock" if mock else "config", devices=cfg.devices)
        try:
            sensing.start()
            before = {slot: s.samples for slot, s in sensing.sensors.items()}
            time.sleep(3.0)
            rows = [(slot, OK, f"{s.adapter}: {(s.samples - before[slot]) / 3.0:.0f} Hz")
                    for slot, s in sensing.sensors.items()]
        except Exception as exc:
            rows = [("sensors", FAIL, f"{type(exc).__name__}: {exc}")]
        finally:
            sensing.stop()
            store.close()
    return rows


def run(sensors=True, mock=False):
    results = list(_packages(sensors and not mock))
    try:
        cfg = config.load()
    except config.ConfigError as exc:
        return results + [("config", FAIL, str(exc))]
    results.append(("config", OK, "config/genui.yaml + devices.yaml valid"))
    results += _content(cfg) + _models(cfg) + _port(cfg) + _browser(cfg)
    if sensors:
        results += _sensors(cfg, mock)
    return results
