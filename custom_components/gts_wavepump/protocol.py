"""GTS L20 wave pump wire protocol.

This module is deliberately Home Assistant agnostic: it only knows how to
build request frames and parse response frames for the GTS透传串口 (ISSC/
Microchip UART) application-layer protocol. It has no I/O and no HA imports,
so it can be unit-tested on its own.

Frame format (request and response share it)::

    [0]    [1]        [2 .. n-2]   [n-1]
    0xFA   interface  payload      checksum

``checksum = sum(all preceding bytes) % 255``. A response is accepted when its
last byte equals that checksum *or* equals 255 (the firmware's "no error"
placeholder).

See ``docs/gts-l20-protocol.md`` for the full reverse-engineering notes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

# --- Frame constants --------------------------------------------------------

HEADER = 0xFA  # 250, fixed first byte of every frame
NO_ERROR = 0xFF  # 255, placeholder the firmware may send instead of a checksum

# --- Interface ids (§4 of the protocol doc) ---------------------------------

IFACE_WRITE_CONFIG = 1  # write a single config field: payload = [field, value]
IFACE_READ_CONFIG = 2  # read all config in one shot
IFACE_HEARTBEAT = 3  # heartbeat / status poll, response len 10
IFACE_PROVISION = 4  # BLE-only Wi-Fi provisioning (unused for local control)
IFACE_SET_TIME = 6  # push current time
IFACE_OTA = 9  # firmware OTA
IFACE_READ_CONFIG_V2 = 10  # TLV config read (software_version > 4)

# --- Field numbers, old "Zc" table (software_version <= 4) ------------------
#
# The newer "Jc" table (software_version > 4) splits manual_power / manual_
# period into 1..6 banks and gives every field its own req/res id. It is left
# as a TODO below; this skeleton targets the old Zc table first.

FIELD_MASTER_OR_SLAVE = 1
FIELD_MANUAL_OR_AUTO = 2
FIELD_MANUAL_MODE = 3
FIELD_MANUAL_POWER = 4  # intensity
FIELD_MANUAL_PERIOD = 5
# auto_m/auto_p/auto_t for the 24 curve segments occupy 6..78
FIELD_FORWARD_OR_REVERSE = 79
FIELD_COMMUNICATION_CHANNEL = 80

# --- Version-dependent field tables -----------------------------------------
#
# Extracted verbatim from the official app's app-service.js (`Zc=`, `Jc=`).
# A single-field config write goes over interface 1 (IFACE_WRITE_CONFIG) as
# [250, 1, id, value, checksum]; the `id` comes from Zc for software_version
# <= 4 and from Jc[field].req for software_version > 4. Confirmed on hardware
# (software_version 17 uses the Jc ids).

# software_version > this uses the new Jc table.
NEW_TABLE_MIN_VERSION = 4

# Zc (old) name -> interface-1 id. Only the fields we use are listed.
ZC_FIELD_IDS = {
    "master_or_slave": 1,
    "manual_or_auto": 2,
    "manual_mode": 3,
    "manual_power": 4,
    "manual_period": 5,
    "forward_or_reverse": 79,
    "communication_channel": 80,
}

# Jc (new) name -> interface-1 req id. Power/period are split into per-mode
# banks 1,2,3,4,6 (there is no bank 5). Only the fields we use are listed.
JC_FIELD_REQ = {
    "master_or_slave": 1,
    "manual_or_auto": 2,
    "manual_mode": 3,
    "manual_power_1": 4,
    "manual_period_1": 5,
    "manual_power_2": 6,
    "manual_period_2": 7,
    "manual_power_3": 8,
    "manual_period_3": 9,
    "manual_power_4": 10,
    "manual_period_4": 11,
    "manual_power_6": 12,
    "manual_period_6": 13,
    "forward_or_reverse": 87,
    "communication_channel": 88,
    "feed_time": 89,
    "light_on": 90,
}

# cu (config-v2) name -> TLV field id, used for interface-10 writes on
# software_version > 10 devices (app-service.js `cu=`, buildDeviceConfigFieldReqV2).
# A config-v2 write frame is [250, 10, id, value, checksum].
CU_FIELD_IDS = {
    "master_or_slave": 1,
    "manual_or_auto": 2,
    "manual_mode": 3,
    "manual_power_1": 4,
    "manual_period_1": 5,
    "manual_power_2": 6,
    "manual_period_2": 7,
    "manual_power_3": 8,
    "manual_period_3": 9,
    "manual_power_4": 10,
    "manual_period_4": 11,
    "manual_power_6": 12,
    "manual_period_6": 13,
    "forward_or_reverse": 86,
    "communication_channel": 87,
    "feed_time": 88,
    "light_on": 89,
}

# Devices with software_version > this use config-v2 (interface 10) for writes.
CONFIG_V2_MIN_VERSION = 10


def uses_config_v2(software_version: int | None) -> bool:
    """True if this device uses config-v2 (interface 10) writes (sw > 10)."""
    return software_version is not None and software_version > CONFIG_V2_MIN_VERSION


def build_config_v2_write(name: str, value: int) -> bytes:
    """Build an interface-10 (config-v2) single-field write."""
    try:
        cid = CU_FIELD_IDS[name]
    except KeyError as err:
        raise InvalidFrameError(f"field {name!r} has no config-v2 id") from err
    return build_frame(IFACE_READ_CONFIG_V2, [cid, value])


# Water-flow waveforms (manual_mode / current_mode values). 5 is "feed", 7 is
# "off" and are not selectable power banks.
MANUAL_MODES = (1, 2, 3, 4, 6)
# Special manual_mode values that are actions rather than waveforms.
MODE_FEED = 5
MODE_OFF = 7
MODE_NAMES = {
    1: "constant",
    2: "pulse",
    3: "sine",
    4: "turbulence",
    5: "feed",
    6: "surge",
    7: "off",
}

# manual_or_auto values.
MANUAL_OR_AUTO_MANUAL = 1
MANUAL_OR_AUTO_TIDE = 2
# forward_or_reverse values.
FLOW_DIRECT = 1
FLOW_REVERSE = 2


def uses_new_table(software_version: int | None) -> bool:
    """True if this software_version uses the Jc table (sw > 4)."""
    return software_version is not None and software_version > NEW_TABLE_MIN_VERSION


def power_field_name(manual_mode: int | None, software_version: int | None) -> str:
    """Name of the active manual-power field for the given mode/version.

    On new-table devices the live power lives in ``manual_power_<manual_mode>``
    (banks 1/2/3/4/6); on old devices there is a single ``manual_power``.
    """
    if not uses_new_table(software_version):
        return "manual_power"
    mode = manual_mode if manual_mode in MANUAL_MODES else MANUAL_MODES[0]
    return f"manual_power_{mode}"


def resolve_field_id(name: str, software_version: int | None) -> int:
    """Interface-1 id for a config field name, per software_version."""
    table = JC_FIELD_REQ if uses_new_table(software_version) else ZC_FIELD_IDS
    try:
        return table[name]
    except KeyError as err:
        raise InvalidFrameError(
            f"field {name!r} has no id for software_version={software_version}"
        ) from err


def build_config_write(name: str, value: int, software_version: int | None) -> bytes:
    """Build an interface-1 write for a named config field."""
    return build_write_field(resolve_field_id(name, software_version), value)


# Jc (new) name -> response byte offset in a read-all-config (interface 2)
# response. For sw > 4 the config reply is indexed by these `res` ids
# (app-service.js: `r[field] = e[Jc[field].res]`).
JC_FIELD_RES = {
    "master_or_slave": 2,
    "manual_or_auto": 3,
    "manual_mode": 4,
    "manual_power_1": 5,
    "manual_period_1": 6,
    "manual_power_2": 7,
    "manual_period_2": 8,
    "manual_power_3": 9,
    "manual_period_3": 10,
    "manual_power_4": 11,
    "manual_period_4": 12,
    "manual_power_6": 13,
    "manual_period_6": 14,
    "forward_or_reverse": 87,
    "communication_channel": 88,
    "feed_time": 89,
    "light_on": 90,
}

# Zc (old) read-all order: value for Kc[i] sits at response byte i+2
# (app-service.js: `for(s=2..) r[Kc[s-2]] = e[s]`). Only leading fields listed.
ZC_READ_ORDER = (
    "master_or_slave",
    "manual_or_auto",
    "manual_mode",
    "manual_power",
    "manual_period",
)


def parse_config(frame: Sequence[int], software_version: int | None) -> dict[str, int]:
    """Parse a read-all-config (interface 2) response into {name: value}.

    Only the fields this integration uses are extracted; missing/short frames
    yield a partial dict rather than raising on individual fields.
    """
    interface, _payload = parse_response(frame)
    if interface != IFACE_READ_CONFIG:
        raise InvalidFrameError(f"not a config frame (interface={interface})")
    result: dict[str, int] = {}
    if uses_new_table(software_version):
        for name, idx in JC_FIELD_RES.items():
            if idx < len(frame):
                result[name] = frame[idx]
    else:
        for i, name in enumerate(ZC_READ_ORDER):
            idx = i + 2
            if idx < len(frame):
                result[name] = frame[idx]
    return result


# --- manual_period <-> seconds ---------------------------------------------
# The heartbeat current_period and the per-mode manual_period banks are stored
# in hundredths of a second (raw 67 == 0.67 s, matching the app's "0.670S").
# TODO(calibrate): confirm the exact min/max of the raw period range.
PERIOD_SCALE = 100


def period_to_seconds(raw: int) -> float:
    """Convert a raw period value to seconds."""
    return raw / PERIOD_SCALE


def seconds_to_period(seconds: float) -> int:
    """Convert seconds to a raw period value."""
    return round(seconds * PERIOD_SCALE)


def period_field_name(manual_mode: int | None, software_version: int | None) -> str:
    """Name of the active manual-period field for the given mode/version."""
    if not uses_new_table(software_version):
        return "manual_period"
    mode = manual_mode if manual_mode in MANUAL_MODES else MANUAL_MODES[0]
    return f"manual_period_{mode}"


class InvalidFrameError(ValueError):
    """Raised when a received frame is malformed or fails validation."""


@dataclass(frozen=True)
class HeartbeatStatus:
    """Decoded heartbeat (interface 3) response."""

    software_version: int
    current_mode: int
    current_power: int
    current_temp: int
    current_period: int
    error_code: int
    raw: bytes


def checksum(data: Sequence[int]) -> int:
    """Return ``sum(data) % 255`` — the protocol checksum of ``data``.

    Mirrors ``Xc = e => { let t=0; for (...) t+=e[n]; return t%255 }``.
    """
    return sum(data) % 255


def build_frame(interface: int, payload: Sequence[int] = ()) -> bytes:
    """Build a full frame ``[250, interface, *payload, checksum]``."""
    body = [HEADER, interface, *payload]
    return bytes([*body, checksum(body)])


def build_write_field(field: int, value: int) -> bytes:
    """Build an interface-1 write for a single config ``field`` = ``value``."""
    return build_frame(IFACE_WRITE_CONFIG, [field, value])


def build_read_config() -> bytes:
    """Build an interface-2 read-all-config request."""
    return build_frame(IFACE_READ_CONFIG)


def build_heartbeat() -> bytes:
    """Build an interface-3 heartbeat/status request."""
    return build_frame(IFACE_HEARTBEAT)


def is_checksum_valid(frame: Sequence[int]) -> bool:
    """Return True if ``frame`` has a valid trailing checksum (or 255)."""
    if len(frame) < 3:
        return False
    last = frame[-1]
    return last == NO_ERROR or last == checksum(frame[:-1])


def parse_response(frame: Sequence[int]) -> tuple[int, bytes]:
    """Validate a generic response and return ``(interface, payload)``.

    ``payload`` is the bytes between the interface id and the trailing
    checksum. Raises :class:`InvalidFrameError` on a bad header, short frame,
    or failed checksum.
    """
    if len(frame) < 3:
        raise InvalidFrameError(f"frame too short: {bytes(frame)!r}")
    if frame[0] != HEADER:
        raise InvalidFrameError(f"bad header {frame[0]:#x}, expected 0xFA")
    if not is_checksum_valid(frame):
        raise InvalidFrameError(f"checksum failed: {bytes(frame)!r}")
    return frame[1], bytes(frame[2:-1])


def parse_heartbeat(frame: Sequence[int]) -> HeartbeatStatus:
    """Parse an interface-3 heartbeat response (see §6 of the protocol doc).

    Layout: ``res[2]`` error code, ``res[3]`` software_version,
    ``res[4]`` current_mode, ``res[5]`` current_power, ``res[6]`` current_temp,
    ``res[7]`` current_period.
    """
    interface, _payload = parse_response(frame)
    if interface != IFACE_HEARTBEAT:
        raise InvalidFrameError(
            f"not a heartbeat frame (interface={interface})"
        )
    if len(frame) < 8:
        raise InvalidFrameError(f"heartbeat too short: {bytes(frame)!r}")
    return HeartbeatStatus(
        error_code=frame[2],
        software_version=frame[3],
        current_mode=frame[4],
        current_power=frame[5],
        current_temp=frame[6],
        current_period=frame[7],
        raw=bytes(frame),
    )
