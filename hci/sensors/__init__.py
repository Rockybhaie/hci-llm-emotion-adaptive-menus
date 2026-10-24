"""Sensor adapters. `create()` picks one from config/devices.yaml."""

from .base import EyeSensor, Sensor, SensorContext, SensorError

ADAPTERS = {
    "eye_tracker": {
        "tobii": ("tobii", "TobiiEye"),
        "mock": ("mock", "MockEye"),
    },
    "gsr": {
        "shimmer": ("shimmer", "ShimmerGsr"),
        "lsl": ("lsl_inlet", "LslGsr"),
        "serial": ("serial_line", "SerialGsr"),
        "mock": ("mock", "MockGsr"),
    },
    "hr": {
        "polar_h10": ("polar_h10", "PolarH10"),
        "lsl": ("lsl_inlet", "LslHr"),
        "serial": ("serial_line", "SerialHr"),
        "mock": ("mock", "MockHr"),
    },
}


def create(slot, adapter, options, store, context, sync_stream=None):
    """Build the sensor for one slot (eye_tracker | gsr | hr); returns None for 'none'."""
    if adapter == "none":
        return None
    if adapter == "unset":
        raise SensorError(f"Choose the {slot} adapter in config/devices.yaml (or run with --mock)")
    try:
        module_name, cls_name = ADAPTERS[slot][adapter]
    except KeyError:
        choices = ", ".join([*ADAPTERS[slot], "none"])
        raise SensorError(f"Unknown {slot} adapter '{adapter}'. Choose one of: {choices}")
    import importlib
    module = importlib.import_module(f"{__name__}.{module_name}")
    return getattr(module, cls_name)(options, store, context, sync_stream)


__all__ = ["create", "ADAPTERS", "Sensor", "EyeSensor", "SensorContext", "SensorError"]
