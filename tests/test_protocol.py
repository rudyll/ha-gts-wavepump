"""Unit tests for the HA-agnostic GTS wave pump protocol layer.

The protocol module has no Home Assistant dependency, but it lives inside a
package whose ``__init__`` does import HA. We therefore load ``protocol.py``
directly by file path so the tests run with nothing but the stdlib + pytest.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_PROTOCOL_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "gts_wavepump"
    / "protocol.py"
)
_spec = importlib.util.spec_from_file_location("gts_protocol", _PROTOCOL_PATH)
protocol = importlib.util.module_from_spec(_spec)
# Register before exec so dataclass introspection can find the module.
sys.modules[_spec.name] = protocol
_spec.loader.exec_module(protocol)


def test_checksum_is_sum_mod_255():
    assert protocol.checksum([250, 1, 4, 50]) == 50  # 305 % 255
    assert protocol.checksum([250, 3]) == 253
    assert protocol.checksum([]) == 0


def test_build_write_manual_power_frame():
    # The canonical example from the task: manual_power = 50.
    frame = protocol.build_write_field(protocol.FIELD_MANUAL_POWER, 50)
    assert list(frame) == [250, 1, 4, 50, 50]


def test_build_heartbeat_frame():
    frame = protocol.build_heartbeat()
    assert list(frame) == [250, 3, 253]


def test_build_read_config_frame():
    frame = protocol.build_read_config()
    assert frame[0] == protocol.HEADER
    assert frame[1] == protocol.IFACE_READ_CONFIG
    assert protocol.is_checksum_valid(frame)


def test_parse_response_round_trip():
    frame = protocol.build_write_field(protocol.FIELD_FORWARD_OR_REVERSE, 1)
    interface, payload = protocol.parse_response(frame)
    assert interface == protocol.IFACE_WRITE_CONFIG
    assert list(payload) == [protocol.FIELD_FORWARD_OR_REVERSE, 1]


def test_parse_response_accepts_255_placeholder():
    # Last byte 255 ("no error") is valid regardless of the real checksum.
    frame = [250, 1, 4, 50, 255]
    interface, payload = protocol.parse_response(frame)
    assert interface == 1
    assert list(payload) == [4, 50]


def test_parse_heartbeat_decodes_status():
    # res: [250, 3, err=0, sw=5, mode=2, power=60, temp=25, period=10, 0, cs]
    body = [250, 3, 0, 5, 2, 60, 25, 10, 0]
    frame = bytes([*body, protocol.checksum(body)])
    status = protocol.parse_heartbeat(frame)
    assert status.error_code == 0
    assert status.software_version == 5
    assert status.current_mode == 2
    assert status.current_power == 60
    assert status.current_temp == 25
    assert status.current_period == 10
    assert status.raw == frame


def test_parse_rejects_bad_header():
    with pytest.raises(protocol.InvalidFrameError):
        protocol.parse_response([0x00, 3, 253])


def test_parse_rejects_bad_checksum():
    with pytest.raises(protocol.InvalidFrameError):
        protocol.parse_response([250, 1, 4, 50, 99])


def test_parse_heartbeat_rejects_wrong_interface():
    frame = protocol.build_write_field(protocol.FIELD_MANUAL_POWER, 50)
    with pytest.raises(protocol.InvalidFrameError):
        protocol.parse_heartbeat(frame)


def test_uses_new_table_boundary():
    assert protocol.uses_new_table(17) is True
    assert protocol.uses_new_table(5) is True
    assert protocol.uses_new_table(4) is False
    assert protocol.uses_new_table(None) is False


def test_resolve_field_id_old_vs_new():
    # manual_power: Zc id 4; forward_or_reverse: Zc 79 vs Jc req 87.
    assert protocol.resolve_field_id("manual_power", 3) == 4
    assert protocol.resolve_field_id("forward_or_reverse", 3) == 79
    assert protocol.resolve_field_id("forward_or_reverse", 17) == 87


def test_power_field_name_banks():
    # Old device: single manual_power.
    assert protocol.power_field_name(6, 3) == "manual_power"
    # New device: per-mode bank; surge (mode 6) -> manual_power_6.
    assert protocol.power_field_name(6, 17) == "manual_power_6"
    # Unknown/invalid mode falls back to the first valid bank.
    assert protocol.power_field_name(5, 17) == "manual_power_1"
    assert protocol.power_field_name(None, 17) == "manual_power_1"


def test_build_config_write_resolves_by_version():
    # surge power bank on a new device -> req id 12.
    frame = protocol.build_config_write("manual_power_6", 40, 17)
    assert list(frame) == [250, 1, 12, 40, (250 + 1 + 12 + 40) % 255]
    # same logical field on an old device uses Zc manual_power id 4.
    frame_old = protocol.build_config_write("manual_power", 40, 3)
    assert list(frame_old) == [250, 1, 4, 40, (250 + 1 + 4 + 40) % 255]


def test_resolve_field_id_unknown_raises():
    with pytest.raises(protocol.InvalidFrameError):
        protocol.resolve_field_id("manual_power_5", 17)  # no bank 5
