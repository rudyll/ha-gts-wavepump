# Changelog

## Unreleased — App-unit headroom correction

- Separate raw0–99 from newer-firmware App nonzero raw+20 (max119). Calculate gain in App units and dynamic headroom from the full daily peak; integer step1, zeros retained,100% exact restore, no peak clipping. Legacy<=4 display remains raw with99 ceiling.
- Fresh-read and reject external tidal edits before curve/storm writes. Require explicitapp_percent storm service basis and block ambiguous legacy persisted gains until explicit recovery. Update paired blueprints/instances before enabling; HA fan percentage compatibility retained.
-75 tests/41subtests, paired native HA validation and three-baseline template-to-service simulations passed. No installation or physical-flow acceptance. See docs/app-power-gain.md.

## 0.7.0 — 2026-10-26

- Extend the tidal gain entity from10–100% to10–200%.100% preserves the tuned
  daily curve; values above100 add relative weather gain rather than weakening
  normal conditions first. Entity unique ID and storage key stay unchanged.
- Keep the immutable24-hour baseline for repeated updates, restart and retry;
 100% restores it exactly. Reject invalid requested or persisted gain values.
- Keep the existing raw power cap99 on scaled segments. This is a software bound,
  not a measured safe flow limit; clipped peaks no longer preserve exact ratios.
  Gain percentages do not establish proportional physical water flow.
- Add storm_gain: transient peak/gap targets from the original current-hour daily
  baseline, with raw cap and expected-run-mode/clock/overlay/off/feed guards.
  Preload bounded power/period before mode selection; confirm heartbeat and attempt
  safe stop on failure after possible output change. Distinguish confirmed stop/
  recovery required from unconfirmed stop in command_error. Config-v2 firmware only.
  No daily-curve rewrite or compounded weather gain; manual banks keep setpoints.
- Clarify the entity label as tidal gain.71 tests and41 subtests passed with
  simulated transport/storage; no gain or storm hardware test is claimed.
- Upgrade: install then restart/reload the integration at an approved time. Do
  not delete overlay storage or recapture a boosted curve as your normal curve.
  Weather blueprints require a separate import/update and entity-capability check.
  Use the separate baseline-relative storm blueprint; existing fixed-setpoint
  drafts retain their old semantics. Confirm pump/HA clocks agree; no pump-clock
  readback exists. A failed storm command can stop the pump and needs inspection.
  This release does not activate any weather automation or change gain by itself.

## 0.6.2

- Serialize complete BLE operations. A later stop supersedes unfinished starts
  and curve writes; failed or cancelled restarts attempt a confirmed safe stop
  rather than leaving the temporary manual power running.
- Validate response framing/interface and echoed legacy writes; require config
  or heartbeat readback for commands. Discard timed-out/cancelled connections.
- Save the original full tidal curve and pending intensity before writing.
  Partial-write retry and HA restart retain the same baseline; 100% restores it.
  Full schedule replacement is blocked until the intensity overlay is cleared.
- Expose command errors and pending recovery in entity attributes.
- Upgrade: restart HA after installing. A failed curve write needs an explicit
  intensity retry (or 100% restore); do not delete HA storage to clear it.
  Existing damaged baselines cannot be reconstructed automatically. Unsupported
  firmware/short curves fail closed. HA telemetry is not a physical flow test.

- Fix the incomplete tide-mode restart in 0.6.1: after a dedicated off command,
  setting the run mode to tide alone could leave the pump stopped. A plain
  `fan.turn_on` now starts a manual waveform at the default power before
  returning to tide. When no in-memory off/on history exists, use the pump's
  retained run mode, including after an HA restart or native feeding. Explicit
  percentage control still selects manual mode.
- Add command-sequence regression tests for tide restart, manual operation,
  explicit percentage overrides, and BLE write failure.


## 0.6.1

- Fix: `fan.turn_on` now **resumes the previous run mode** instead of always
  forcing manual. Turning the pump off then on (e.g. a feeding automation that
  pauses the pump) keeps it in **tide** mode instead of dropping the tidal
  schedule. `turn_off` remembers the mode; `set_percentage`/`turn_on` with an
  explicit percentage still mean manual.

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
