"""Legacy unit tests for the sensor adapter files (hci/sensors/). The adapters are kept in the repository
unchanged but are NOT used by this app (sensors are handled elsewhere); these tests only guard the files."""

from hci.sensors.polar_h10 import parse_heart_rate
from hci.sensors.shimmer import gsr_raw_to_microsiemens


def test_polar_heart_rate_parsing():
    # flags: uint8 HR + RR present; HR 72; RR 1024/1024 s and 512/1024 s
    data = bytes([0x10, 72, 0x00, 0x04, 0x00, 0x02])
    assert parse_heart_rate(data) == (72, [1000, 500])
    # uint16 HR, no RR
    assert parse_heart_rate(bytes([0x01, 0x2C, 0x01])) == (300, [])


def test_shimmer_gsr_conversion_is_positive():
    raw = (1 << 14) | 2000   # range 1, mid-scale ADC
    assert gsr_raw_to_microsiemens(raw) > 0
