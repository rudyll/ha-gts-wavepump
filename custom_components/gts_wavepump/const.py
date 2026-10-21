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

# The reverse-engineered doc lists a primary (ISSC 49535343-*) and a backup
# (FFF0/FFF1/FFF2) UART. On real hardware the roles of the two ISSC
# characteristics turned out not to match the doc (the documented notify
# characteristic had no notify property), so instead of trusting fixed UUIDs we
# resolve the write/notify characteristics at connect time by their actual GATT
# properties, trying these candidates in order. Roles are included both ways
# because the two ISSC characteristics can be swapped between devices.
NOTIFY_CHAR_CANDIDATES = [
    "49535343-1e4d-4bd9-ba61-23c647249616",
    "49535343-8841-43f4-a8d4-ecbe34729bb3",
    "0000fff2-0000-1000-8000-00805f9b34fb",
    "0000fff1-0000-1000-8000-00805f9b34fb",
]
WRITE_CHAR_CANDIDATES = [
    "49535343-8841-43f4-a8d4-ecbe34729bb3",
    "49535343-1e4d-4bd9-ba61-23c647249616",
    "0000fff1-0000-1000-8000-00805f9b34fb",
    "0000fff2-0000-1000-8000-00805f9b34fb",
]

# How often the coordinator polls the heartbeat (interface 3).
UPDATE_INTERVAL = timedelta(seconds=30)

# Seconds to wait for a notification response after writing a frame.
RESPONSE_TIMEOUT = 5.0

# --- Value ranges -----------------------------------------------------------
#
# manual_power raw value. We map the HA fan percentage 1:1 onto this raw value.
# NOTE: on new-table devices (software_version > 4) the official app DISPLAYS
# current_power + 20 (app-service.js: `software_version>4 && t!==0 && t+=20`),
# so our raw percentage reads ~20 lower than the app's number, and the real raw
# ceiling may be ~80 rather than 100.
# TODO(calibrate): confirm the raw max and whether to apply the +20 display
#   offset so HA matches the app's percentage.
POWER_MIN = 0
# Manual power slider in the app is 0..99 (min 0 on sw>=10). The app's home
# status card displays current_power + 20, but the slider we mirror uses the
# raw value, so HA percentage == raw power.
POWER_MAX = 99
# Power used when turning the pump on without an explicit percentage.
POWER_DEFAULT_ON = 80

# Confirmed from app-service.js (see protocol.py for the field tables):
#   - current_temp (heartbeat res[6]) is degrees Celsius directly.
#   - manual_period is a time in SECONDS (app slider shows 0.670S / 1.300S);
#     raw->seconds mapping still needs a capture before exposing a number.
#   - current_mode/manual_mode: 1=constant 2=pulse 3=sine 4=turbulence 5=feed
#     6=surge 7=off; selectable water banks are {1,2,3,4,6}.
#   - manual_or_auto: 1=manual, 2=tide(auto). Manual power only takes effect in
#     manual mode, so the fan forces manual mode when setting intensity.

# light_on (field 90): 2=on, 1=off.
# Confirmed by diffing the raw config while toggling the wired-controller light.
LIGHT_ON = 2
LIGHT_OFF = 1

# Water-flow waveform options for the manual_mode select (value -> slug).
# Modes 5 (feed) and 7 (off) are not user-selectable waveforms.
WATER_MODE_OPTIONS = {
    1: "constant",
    2: "pulse",
    3: "sine",
    4: "turbulence",
    6: "surge",
}

# Run-mode select (manual_or_auto): value -> slug.
RUN_MODE_OPTIONS = {
    1: "manual",
    2: "tide",
}

# feed_time (minutes) range for the number entity (app's instant-feed duration).
FEED_TIME_MIN = 1
FEED_TIME_MAX = 60

# manual_period raw range for the number entity (seconds = raw / 100).
# TODO(calibrate): confirm the true raw min/max.
PERIOD_RAW_MIN = 1
PERIOD_RAW_MAX = 250

# communication_channel range (diagnostic number).
CHANNEL_MIN = 0
CHANNEL_MAX = 15
