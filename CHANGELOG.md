# Changelog

## 0.6.0

- **Role** (`select` 主从机): switch the pump between main and slave for
  multi-pump sync (`master_or_slave`). Verified on hardware.
- **Signal strength** (`sensor` 信号强度, diagnostic): BLE RSSI from the nearest
  adapter/proxy, with the source adapter/proxy in an attribute — handy for
  checking Bluetooth-proxy coverage.

## 0.5.0

- **Tidal intensity overlay** (`number` 潮汐强度): scale the whole 24-segment
  tidal curve by a percentage (10–100%) for e.g. coral acclimation — lowers the
  day's flow proportionally and restores exactly at 100%, without changing each
  hour's waveform or relative power. Scales from a persisted baseline (drift-
  free); only takes effect in tide (auto) mode.
- Tidal writes are chunked to single-field config-v2 frames (the pump only
  applies the first field of a multi-field frame), fixing full-curve writes via
  `set_tidal_schedule` too.

## 0.4.1

- Each feed-timer switch (定时组 1/2/3) now exposes its slot's `time` (HH:MM) and
  `duration_min` as attributes, so the schedule is visible on the switch itself.

## 0.4.0

- **Scheduled-feeding slot toggles**: three `switch` entities (定时组 1/2/3) to
  enable/disable the pump's timed-feeding slots. The config-v2 write ids were
  found by probing and verified on hardware. Slot times are still set in the
  app (read-only here via the Feed schedule sensor).

## 0.3.0

Support the whole GTS wave-pump line, not just the L20 — a local replacement for
the GTS Aqua app across models.

- **L40 support**: discovery now matches `GTS_WAVE*` (L20 `GTS_WAVE20_*` and L40
  `GTS_WAVE40_*`), which share the same BLE protocol. The model (L20 / L40) is
  detected from the advertised name and shown on the device.
- Integration renamed to "GTS Wave Pump" (generic).

## 0.2.0

First HACS release. Local BLE control of the GTS L20 wave pump, verified on
hardware (software_version 17), with no vendor cloud.

Entities:
- `fan` — on/off (关机 via manual_mode 7) and intensity.
- `select` — run mode (manual / tide) and wave mode (constant / pulse / sine /
  turbulence / surge).
- `number` — wave period (seconds), instant-feed time (minutes), communication
  channel.
- `switch` — light.
- `button` — feed now.
- `sensor` — temperature, running flow mode, firmware version, tidal schedule
  (24 segments, read-only), feed schedule (3 slots, read-only).
- Service `gts_wavepump.set_tidal_schedule` to write the whole tidal curve.

Notes:
- Writes use config-v2 (interface 10) on `software_version > 10` devices.
- UART write/notify characteristics are resolved by GATT property (they are
  swapped vs. the Microchip convention on this hardware).
- English and Simplified Chinese translations.

Known limitations:
- Scheduled feeding (3 slots) is read-only; the per-slot write protocol is a
  hot-update feature not present in the shipped APK.
- Reverse flow is not exposed (removed in the L20 firmware).
- A few value ranges (period min/max, power display offset) are approximate.
