"""Shimmer3 GSR+ over Bluetooth serial via pyshimmer.

Configure the unit in Shimmer Consensys first (GSR + PPG enabled, ~128 Hz); this
adapter only streams. GSR is converted to microsiemens with the Shimmer3 GSR+
feedback-resistor table. Written against pyshimmer's API and untested without
hardware: verify in the lab dry run.
"""

from ..clock import now
from .base import Sensor, SensorError

# Shimmer3 GSR+ feedback resistors (ohms) for range bits 0-3.
FEEDBACK_OHMS = [40.2e3, 287e3, 1.0e6, 3.3e6]


def gsr_raw_to_microsiemens(raw):
    rng = (raw >> 14) & 0x03
    adc = raw & 0x3FFF
    volts = adc * 3.0 / 4095
    if volts <= 0.5:
        return float("nan")
    resistance = FEEDBACK_OHMS[rng] / (volts / 0.5 - 1)
    return 1e6 / resistance


class ShimmerGsr(Sensor):
    kind = "gsr"
    adapter = "shimmer"
    nominal_hz = 128
    columns = ["t", "gsr_us", "gsr_raw", "ppg_raw"]

    def _start(self):
        try:
            from pyshimmer import DEFAULT_BAUDRATE, EChannelType, ShimmerBluetooth
            from serial import Serial
        except ImportError:
            raise SensorError("pyshimmer is not installed: pip install pyshimmer")
        port = self.options.get("port")
        try:
            self._serial = Serial(port, DEFAULT_BAUDRATE)
        except Exception as exc:
            raise SensorError(f"Cannot open Shimmer port {port}: {exc}")
        self._ch = EChannelType
        self._shim = ShimmerBluetooth(self._serial)
        self._shim.initialize()
        self.info = {"port": port, "device": self._shim.get_device_name()}
        self._shim.add_stream_callback(self._on_packet)
        self._shim.start_streaming()

    def _on_packet(self, pkt):
        t = now()
        raw = pkt[self._ch.GSR_RAW] if self._ch.GSR_RAW in pkt.channels else None
        ppg = pkt[self._ch.INTERNAL_ADC_13] if self._ch.INTERNAL_ADC_13 in pkt.channels else ""
        if raw is None:
            self.error = "GSR channel not enabled on the Shimmer (enable it in Consensys)"
            return
        self.emit([t, round(gsr_raw_to_microsiemens(raw), 4), raw, ppg])

    def _stop(self):
        if getattr(self, "_shim", None):
            self._shim.stop_streaming()
            self._shim.shutdown()
