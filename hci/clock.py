"""The one master clock every stream is stamped with (seconds, monotonic).

pylsl's local_clock is used when available so LSL streams need no conversion
beyond their own time_correction(); otherwise perf_counter is used.
"""

try:
    from pylsl import local_clock as now
    SOURCE = "pylsl.local_clock"
except ImportError:  # pylsl is only needed for LSL devices
    from time import perf_counter as now
    SOURCE = "time.perf_counter"

__all__ = ["now", "SOURCE"]
