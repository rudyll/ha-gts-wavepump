"""Constants for the GTS L20 wave pump integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "gts_wavepump"

# BLE advertising name prefix. Only devices whose name starts with this are
# ours, e.g. ``GTS_WAVE20_21000580``.
NAME_PREFIX = "GTS_WAVE20_"

# --- GATT (Microchip / ISSC transparent UART), §8 of the protocol doc -------

UART_SERVICE_UUID = "55535343-fe7d-4ae5-8fa9-9fafd205e455"
# We write control frames to this characteristic...
UART_WRITE_CHAR_UUID = "49535343-8841-43f4-a8d4-ecbe34729bb3"
# ...and receive response frames as notifications on this one.
UART_NOTIFY_CHAR_UUID = "49535343-1e4d-4bd9-ba61-23c647249616"

# How often the coordinator polls the heartbeat (interface 3).
UPDATE_INTERVAL = timedelta(seconds=30)

# Seconds to wait for a notification response after writing a frame.
RESPONSE_TIMEOUT = 5.0

# --- Value ranges -----------------------------------------------------------
#
# manual_power is a 0-100 percentage. The official WeChat mini-program shows
# "功率: 65%" on a 0-100 slider, so the 0-100 assumption is confirmed; what is
# still unconfirmed is whether 0 truly stops the pump or whether there is a
# separate on/off command (the app has a distinct "关机" button).
# TODO(calibrate): confirm 0 == off vs. a dedicated power/master off command.
POWER_MIN = 0
POWER_MAX = 100
# Power used when turning the pump on without an explicit percentage.
POWER_DEFAULT_ON = 100

# Observations from the official app, folded in to guide later calibration
# (not yet wired to entities in this skeleton):
#   - current_temp (heartbeat res[6]) is degrees Celsius directly (app: 34°C).
#   - manual_period is a time in SECONDS, not a step index (app: 0.670S /
#     1.300S on a slider). The raw->seconds mapping still needs a capture.
#   - manual_mode / current_mode selects one of 5 manual waveforms shown in the
#     app: 恒定 / 脉动 / 正弦 / 乱流 / 涌浪 (constant / pulse / sine / turbulence
#     / surge). Which numeric value maps to which is not yet confirmed.
# TODO(calibrate): capture these from hardware, then add number/select entities.

# forward_or_reverse (field 79): value semantics not yet confirmed from
# hardware. We treat 1 as "reverse" and 0 as "forward" as a placeholder.
# TODO(calibrate): confirm which value is forward vs reverse.
REVERSE_ON = 1
REVERSE_OFF = 0
