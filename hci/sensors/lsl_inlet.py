"""Any device that publishes a Lab Streaming Layer stream (Shimmer, BITalino, Empatica bridges, ...).

Channel 0 must carry the value in microsiemens (GSR) or beats per minute (HR);
extra channels are kept as ch1, ch2, ...
"""

import threading

from .base import Sensor, SensorError

VALUE_COLUMN = {"gsr": "gsr_us", "hr": "hr_bpm"}


class LslSensor(Sensor):
    adapter = "lsl"
    dynamic_columns = True

    def _start(self):
        try:
            import pylsl
        except ImportError:
            raise SensorError("pylsl is not installed: pip install pylsl")
        name, stype = self.options.get("name"), self.options.get("type")
        prop, value = ("name", name) if name else ("type", stype)
        found = pylsl.resolve_byprop(prop, value, timeout=10)
        if not found:
            raise SensorError(f"No LSL stream with {prop}='{value}' found on the network")
        info = found[0]
        # proc_clocksync maps stamps onto this machine's local_clock, which is the master clock
        self.inlet = pylsl.StreamInlet(info, max_buflen=60, processing_flags=pylsl.proc_clocksync)
        n = info.channel_count()
        self.nominal_hz = info.nominal_srate() or None
        self.columns = ["t", VALUE_COLUMN[self.kind]] + [f"ch{i}" for i in range(1, n)]
        self.info = {"name": info.name(), "type": info.type(), "channels": n,
                     "rate_hz": self.nominal_hz, "source_id": info.source_id()}
        self.open_stream()
        self._thread = threading.Thread(target=self._run, name=f"lsl-{self.kind}", daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop_event.is_set():
            chunk, stamps = self.inlet.pull_chunk(timeout=0.5)
            for sample, ts in zip(chunk, stamps):
                self.emit([ts, *sample])


class LslGsr(LslSensor):
    kind = "gsr"


class LslHr(LslSensor):
    kind = "hr"
