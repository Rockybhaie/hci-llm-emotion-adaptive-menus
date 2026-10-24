"""Polar H10 chest strap: heart rate + RR intervals over the standard BLE Heart Rate Service."""

import asyncio
import threading

from ..clock import now
from .base import Sensor, SensorError

HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"


def parse_heart_rate(data: bytes):
    """Bluetooth Heart Rate Measurement characteristic -> (bpm, [rr_ms, ...])."""
    flags = data[0]
    i = 1
    if flags & 0x01:
        bpm = int.from_bytes(data[i:i + 2], "little")
        i += 2
    else:
        bpm = data[i]
        i += 1
    if flags & 0x08:            # energy expended field present
        i += 2
    rr = []
    if flags & 0x10:
        while i + 1 < len(data):
            rr.append(round(int.from_bytes(data[i:i + 2], "little") / 1024 * 1000))
            i += 2
    return bpm, rr


class PolarH10(Sensor):
    kind = "hr"
    adapter = "polar_h10"
    nominal_hz = 1
    flush_s = 0
    columns = ["t", "hr_bpm", "rr_ms"]

    def _start(self):
        try:
            import bleak  # noqa: F401
        except ImportError:
            raise SensorError("bleak is not installed: pip install bleak")
        self._ready = threading.Event()
        self._thread = threading.Thread(target=lambda: asyncio.run(self._main()), name="polar-h10", daemon=True)
        self._thread.start()
        if not self._ready.wait(25):
            raise SensorError(self.error or "Polar H10 did not connect. Wet the strap electrodes and check Bluetooth.")
        if self.error:
            raise SensorError(self.error)

    async def _main(self):
        from bleak import BleakClient, BleakScanner
        try:
            address = self.options.get("address")
            if address:
                device = await BleakScanner.find_device_by_address(address, timeout=15)
            else:
                device = await BleakScanner.find_device_by_filter(
                    lambda d, ad: bool(d.name) and "Polar H10" in d.name, timeout=15)
            if device is None:
                raise SensorError("No Polar H10 found nearby (is it worn? the strap only wakes on skin contact)")
            async with BleakClient(device) as client:
                self.info = {"name": device.name, "address": device.address}
                await client.start_notify(HR_MEASUREMENT, self._on_data)
                self._ready.set()
                while not self._stop_event.is_set() and client.is_connected:
                    await asyncio.sleep(0.2)
                if client.is_connected:
                    await client.stop_notify(HR_MEASUREMENT)
                else:
                    self.error = "Polar H10 disconnected"
        except Exception as exc:
            self.error = str(exc)
            self._ready.set()

    def _on_data(self, _sender, data):
        bpm, rr = parse_heart_rate(bytes(data))
        self.emit([now(), bpm, ";".join(map(str, rr))])
