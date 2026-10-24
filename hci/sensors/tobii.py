"""Tobii Pro eye tracker (Nano, Fusion, Spark, ...) via the official tobii_research SDK."""

import threading

from ..clock import now
from .base import EyeSensor, SensorError


class TobiiEye(EyeSensor):
    adapter = "tobii"
    nominal_hz = 60

    def _start(self):
        try:
            import tobii_research as tr
        except ImportError:
            raise SensorError("tobii-research is not installed: pip install tobii-research")
        self.tr = tr
        trackers = tr.find_all_eyetrackers()
        wanted = self.options.get("serial")
        if wanted:
            trackers = [t for t in trackers if t.serial_number == wanted]
        if not trackers:
            raise SensorError("No Tobii eye tracker found. Check the USB cable and close Eye Tracker Manager.")
        self.et = trackers[0]
        freq = self.options.get("frequency")
        if freq:
            self.et.set_gaze_output_frequency(freq)
        self.nominal_hz = self.et.get_gaze_output_frequency()
        self.info = {"model": self.et.model, "serial": self.et.serial_number,
                     "firmware": self.et.firmware_version, "frequency_hz": self.nominal_hz}
        self._sync_clock()
        self._sync_thread = threading.Thread(target=self._resync, name="tobii-sync", daemon=True)
        self._sync_thread.start()
        self._calibration = None
        self.et.subscribe_to(tr.EYETRACKER_GAZE_DATA, self._on_gaze, as_dictionary=True)

    def _sync_clock(self):
        # Tobii stamps samples with its own system clock (microseconds); bracket a read with the master clock.
        best = None
        for _ in range(5):
            a = now()
            s = self.tr.get_system_time_stamp() / 1e6
            b = now()
            if best is None or b - a < best[0]:
                best = (b - a, (a + b) / 2 - s)
        self.offset = best[1]
        self.log_offset(self.offset)

    def _resync(self):
        while not self._stop_event.wait(30):
            self._sync_clock()

    def _on_gaze(self, g):
        lx, ly = g["left_gaze_point_on_display_area"]
        rx, ry = g["right_gaze_point_on_display_area"]
        self.emit([
            g["system_time_stamp"] / 1e6 + self.offset, g["device_time_stamp"],
            lx, ly, int(g["left_gaze_point_validity"]), rx, ry, int(g["right_gaze_point_validity"]),
            g["left_pupil_diameter"], int(g["left_pupil_validity"]),
            g["right_pupil_diameter"], int(g["right_pupil_validity"]),
        ])

    def _stop(self):
        if getattr(self, "et", None):
            self.et.unsubscribe_from(self.tr.EYETRACKER_GAZE_DATA, self._on_gaze)

    # -- calibration -----------------------------------------------------
    def calibration_start(self):
        self._calibration = self.tr.ScreenBasedCalibration(self.et)
        self._calibration.enter_calibration_mode()

    def calibration_point(self, x, y):
        status = self._calibration.collect_data(x, y)
        if status != self.tr.CALIBRATION_STATUS_SUCCESS:   # Tobii recommends one retry
            status = self._calibration.collect_data(x, y)
        return status == self.tr.CALIBRATION_STATUS_SUCCESS

    def calibration_compute(self):
        result = self._calibration.compute_and_apply()
        ok = result.status == self.tr.CALIBRATION_STATUS_SUCCESS
        return {"status": "success" if ok else "failure", "points": len(result.calibration_points)}

    def calibration_stop(self):
        if self._calibration is not None:
            self._calibration.leave_calibration_mode()
            self._calibration = None
