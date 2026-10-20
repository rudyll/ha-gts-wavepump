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

# TODO(jc-table): add the Jc field map (manual_power_1..6, manual_period_1..6,
# per-field req/res ids) for software_version > 4. Structure lives in
# app-service.js at the `Jc=` definition (offset ~285612). Until then, devices
# reporting software_version > 4 are handled on a best-effort basis with Zc.


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
