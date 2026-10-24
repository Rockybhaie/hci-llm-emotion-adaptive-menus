import collections
import threading

from ..clock import now


class SensorError(Exception):
    pass


class SensorContext:
    """What a sensor may know about the running session (mock sensors use it to look realistic)."""

    def __init__(self):
        self.arousal = 0.3          # 0..1, set from the current phase
        self.mouse = (0.5, 0.5)     # last pointer position, viewport-normalised


class Sensor:
    """One recorder thread writing one CSV. Subclasses define `kind`, `adapter`, `columns`, `_start`, `_stop`."""

    kind = ""        # gaze | gsr | hr (also the CSV file name)
    adapter = ""
    columns = ["t"]
    nominal_hz = None
    flush_s = 0.5
    dynamic_columns = False   # True: the adapter learns its columns on connect and calls open_stream()

    def __init__(self, options, store, context, sync_stream=None):
        self.options = options or {}
        self.context = context
        self.store = store
        self.sync = sync_stream
        self.stream = None
        self.info = {}
        self.error = None
        self.samples = 0
        self._recent = collections.deque(maxlen=4096)
        self._stop_event = threading.Event()

    # -- lifecycle -------------------------------------------------------
    def start(self):
        if not self.dynamic_columns:
            self.open_stream()
        self._start()

    def open_stream(self):
        self.stream = self.store.stream(self.kind, self.columns, flush_s=self.flush_s)

    def stop(self):
        self._stop_event.set()
        try:
            self._stop()
        except Exception as exc:  # never let shutdown lose the rest of the data
            self.error = f"stop failed: {exc}"

    def _start(self):
        raise NotImplementedError

    def _stop(self):
        pass

    # -- data ------------------------------------------------------------
    def emit(self, row):
        self.stream.write(row)
        self.samples += 1
        self._recent.append((row[0], row))

    def recent(self, since):
        return [r for t, r in list(self._recent) if t >= since]

    def log_offset(self, offset):
        if self.sync is not None:
            self.sync.write([now(), self.kind, self.adapter, f"{offset:.6f}"])

    def status(self):
        t = now()
        window = [ts for ts, _ in list(self._recent) if ts >= t - 5]
        last = self._recent[-1][0] if self._recent else None
        return {
            "kind": self.kind, "adapter": self.adapter, "samples": self.samples,
            "hz": len(window) / 5.0, "last_age": None if last is None else t - last,
            "error": self.error,
        }


class EyeSensor(Sensor):
    kind = "gaze"
    columns = ["t", "device_ts", "left_x", "left_y", "left_valid", "right_x", "right_y", "right_valid",
               "left_pupil", "left_pupil_valid", "right_pupil", "right_pupil_valid"]

    # Calibration hooks. Points are display-area coordinates (0..1).
    def calibration_start(self):
        pass

    def calibration_point(self, x, y):
        return True

    def calibration_compute(self):
        return {"status": "success"}

    def calibration_stop(self):
        pass

    def gaze_since(self, since):
        """[(t, x, y)] averaged over valid eyes, for validation."""
        out = []
        for r in self.recent(since):
            xs = [v for v, ok in ((r[2], r[4]), (r[5], r[7])) if ok and v == v]
            ys = [v for v, ok in ((r[3], r[4]), (r[6], r[7])) if ok and v == v]
            if xs and ys:
                out.append((r[0], sum(xs) / len(xs), sum(ys) / len(ys)))
        return out
