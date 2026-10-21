# Changelog

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
