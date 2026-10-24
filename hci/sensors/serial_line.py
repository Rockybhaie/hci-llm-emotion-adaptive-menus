"""Arduino / Grove style sensors that print one reading per line over USB serial."""

import threading

from ..clock import now
from .base import Sensor, SensorError


def make_serial_sensor(kind, value_column):
    class SerialSensor(Sensor):
        adapter = "serial"
        columns = ["t", value_column, "raw"]

        def _start(self):
            try:
                from serial import Serial
            except ImportError:
                raise SensorError("pyserial is not installed: pip install pyserial")
            port, baud = self.options.get("port"), self.options.get("baud", 115200)
            try:
                self.port = Serial(port, baud, timeout=0.5)
            except Exception as exc:
                raise SensorError(f"Cannot open serial port {port}: {exc}")
            self.info = {"port": port, "baud": baud}
            self._thread = threading.Thread(target=self._run, name=f"serial-{kind}", daemon=True)
            self._thread.start()

        def _run(self):
            while not self._stop_event.is_set():
                line = self.port.readline().decode("ascii", "ignore").strip()
                if not line:
                    continue
                try:
                    value = float(line.split(",")[0])
                except ValueError:
                    continue
                self.emit([now(), value, line])

        def _stop(self):
            if getattr(self, "port", None):
                self.port.close()

    SerialSensor.kind = kind
    return SerialSensor


SerialGsr = make_serial_sensor("gsr", "gsr_us")
SerialHr = make_serial_sensor("hr", "hr_bpm")
