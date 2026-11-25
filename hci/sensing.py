"""Starts, watches and stops the session's sensors (config/devices.yaml).

Default setup (no special hardware): the laptop webcam feeds
  eye_tracker: webcam   EyeTrax gaze estimation  -> gaze.csv     (calibrated in the session's calibration step)
  emotion:     yolo     YOLO11n facial emotion   -> emotion.csv
GSR / heart rate stay available as adapters but default to `none`.
"""

import time

from . import paths, sensors
from .config import _yaml
from .sensors import SensorContext, SensorError

SLOTS = ("eye_tracker", "emotion", "gsr", "hr")
AROUSAL = {"high": 0.8, "low": 0.2}


def load_devices():
    return _yaml(paths.CONFIG / "devices.yaml")


def planned(devices=None, mode="config"):
    """{slot: adapter} that a session would start. mode: config | mock | off."""
    devices = devices if devices is not None else load_devices()
    if mode == "off":
        return {}
    out = {}
    for slot in SLOTS:
        adapter = (devices.get(slot) or {}).get("adapter", "none")
        if mode == "mock" and adapter != "none":
            adapter = "mock"
        if adapter != "none":
            out[slot] = adapter
    return out


class Sensing:
    def __init__(self, store, mode="config", devices=None):
        self.devices = devices if devices is not None else load_devices()
        self.context = SensorContext()
        self.store = store
        self.plan = planned(self.devices, mode)
        self.sensors = {}
        self.started = False

    @property
    def gaze(self):
        return self.sensors.get("eye_tracker")

    @property
    def emotion(self):
        return self.sensors.get("emotion")

    def needs_calibration(self):
        return "eye_tracker" in self.plan

    def start(self):
        camera = self.devices.get("camera") or {}
        sync = self.store.stream("clock_sync", ["t", "kind", "adapter", "offset_s"]) if "eye_tracker" in self.plan \
            and self.plan["eye_tracker"] == "tobii" else None
        try:
            for slot, adapter in self.plan.items():
                options = dict((self.devices.get(slot) or {}).get(adapter) or {})
                options.setdefault("camera", camera)
                s = sensors.create(slot, adapter, options, self.store, self.context, sync)
                s.start()
                self.sensors[slot] = s
            self._wait_for_samples(float(self.devices.get("startup_timeout", 15)))
        except Exception:
            self.stop()
            raise
        self.started = True

    def _wait_for_samples(self, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if all(s.samples > 0 for s in self.sensors.values()):
                return
            time.sleep(0.1)
        silent = [f"{slot} ({s.adapter})" for slot, s in self.sensors.items() if s.samples == 0]
        raise SensorError(f"No data within {timeout:.0f} s from: {', '.join(silent)}")

    def stop(self):
        for s in list(self.sensors.values())[::-1]:
            s.stop()

    def set_phase(self, emotion_arousal):
        self.context.arousal = AROUSAL.get(emotion_arousal, 0.3)

    def status(self):
        rows = []
        for slot, s in self.sensors.items():
            st = s.status()
            st["slot"] = slot
            if slot == "eye_tracker" and hasattr(s, "calibrated"):
                st["note"] = "calibrated" if s.calibrated else "not calibrated yet"
            rows.append(st)
        return rows

    def live(self):
        out = {}
        if self.emotion is not None:
            out["emotion"] = getattr(self.emotion, "live", None)
        if self.gaze is not None:
            out["gaze"] = getattr(self.gaze, "live", None)
        return out

    def info(self):
        return {slot: {"adapter": s.adapter, **s.info} for slot, s in self.sensors.items()}
