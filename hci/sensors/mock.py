"""Simulated sensors for dry runs. Signals react to the phase's arousal so merged data looks plausible."""

import math
import random
import threading
import time

from ..clock import now
from .base import EyeSensor, Sensor


class _Loop(Sensor):
    def _start(self):
        self.rng = random.Random(7)
        self._thread = threading.Thread(target=self._run, name=f"mock-{self.kind}", daemon=True)
        self._thread.start()

    def _run(self):
        period = 1.0 / self.nominal_hz
        nxt = time.perf_counter()
        while not self._stop_event.is_set():
            self.emit(self.sample(now()))
            nxt += period
            time.sleep(max(0.0, nxt - time.perf_counter()))


class MockEye(_Loop, EyeSensor):
    adapter = "mock"
    nominal_hz = 60

    def sample(self, t):
        mx, my = self.context.mouse
        x = min(1, max(0, mx + self.rng.gauss(0, 0.02)))
        y = min(1, max(0, my + self.rng.gauss(0, 0.02)))
        blink = self.rng.random() < 0.01
        pupil = 3.2 + 0.8 * self.context.arousal + self.rng.gauss(0, 0.05)
        v = 0 if blink else 1
        nan = float("nan")
        return [t, int(t * 1e6), x if v else nan, y if v else nan, v, x if v else nan, y if v else nan, v,
                pupil if v else nan, v, pupil if v else nan, v]


class MockGsr(_Loop):
    kind = "gsr"
    adapter = "mock"
    nominal_hz = 32
    columns = ["t", "gsr_us"]

    def _start(self):
        self.level, self.scr = 4.0, 0.0
        super()._start()

    def sample(self, t):
        a = self.context.arousal
        self.level += (2.5 + 6 * a - self.level) * 0.002 + self.rng.gauss(0, 0.003)
        if self.rng.random() < (0.002 + 0.01 * a):        # skin conductance response
            self.scr += self.rng.uniform(0.2, 0.8)
        self.scr *= 0.985
        return [t, round(self.level + self.scr, 4)]


class MockHr(_Loop):
    kind = "hr"
    adapter = "mock"
    nominal_hz = 1
    flush_s = 0
    columns = ["t", "hr_bpm", "rr_ms"]

    def sample(self, t):
        bpm = 68 + 18 * self.context.arousal + 3 * math.sin(t / 7) + self.rng.gauss(0, 1.2)
        return [t, round(bpm), round(60000 / bpm)]
