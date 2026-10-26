# GTS Wave Pump — Home Assistant (local BLE)

**English** | [简体中文](README.zh-CN.md)

A Home Assistant custom integration for **狗头鲨 (Goutousha) GTS** wave pumps —
**L20 and L40** — controlled **locally over Bluetooth Low Energy**. A local,
cloud-free replacement for the GTS Aqua app: no vendor cloud, no Aliyun MQTT, no
API keys. Both models share the same BLE protocol and are auto-discovered
(`GTS_WAVE20_*` / `GTS_WAVE40_*`), with the model shown on the device.

The pump exposes no local network service on Wi-Fi (Wi-Fi is used only to reach
the vendor's Aliyun MQTT broker), so local control is BLE-only. The BLE link
stays advertised and connectable while the pump is running and online.

> Protocol source: reverse-engineered from the official app and documented in
> [`docs/gts-l20-protocol.md`](docs/gts-l20-protocol.md). Nothing here talks to
> the vendor cloud.

## Requirements

- Home Assistant with the **Bluetooth** integration configured.
- A Bluetooth adapter on the HA host **or** an **ESP32 BLE proxy** (ESPHome
  `bluetooth_proxy`) within radio range of the aquarium. Only the ESP32
  firmware (if you use a proxy) is ever compiled — the integration itself is
  plain Python and needs no build step.
- `bleak-retry-connector` (declared in the manifest; HA installs it
  automatically).

## Installation

Copy the integration into your HA config:

```
config/custom_components/gts_wavepump/
```

Restart Home Assistant, then go to **Settings → Devices & services**. Pumps are
auto-discovered over Bluetooth (advertised name `GTS_WAVE20_<serial>`, e.g.
`GTS_WAVE20_21000580`); confirm the discovery, or add one manually via
**+ Add integration → GTS Wave Pump**. Or install via HACS as a custom
repository (`https://github.com/rudyll/ha-gts-wavepump`, category Integration).

## Entities

| Entity | Control / reading | Maps to |
| --- | --- | --- |
| `fan` | On/off + intensity % | active `manual_power` bank |
| `select` Run mode | Manual / Tide | `manual_or_auto` |
| `select` Wave mode | Constant/Pulse/Sine/Turbulence/Surge | `manual_mode` |
| `select` Role | Main / Slave (multi-pump) | `master_or_slave` |
| `number` Wave period | Seconds | active `manual_period` bank |
| `number` Tidal intensity | Overlay %: scale the whole tidal curve | `auto_p` × factor |
| `number` Feed time | Minutes | `feed_time` |
| `number` Communication channel | Channel id (config) | `communication_channel` |
| `button` Feed | Feed now | `manual_mode` = 5 |
| `switch` Light | On / off | `light_on` (2=on/1=off) |
| `switch` Feed timer 1/2/3 | Enable/disable a feeding slot | feed-slot enable |
| `sensor` Temperature | °C | heartbeat `current_temp` |
| `sensor` Flow mode | Running waveform | heartbeat `current_mode` |
| `sensor` Tidal schedule | 24-segment curve (read-only, in attributes) | `auto_m/p/t` |
| `sensor` Feed schedule | 3 feeding slots (read-only, in attributes) | feed slots |
| `sensor` Signal strength | BLE RSSI from the nearest adapter/proxy | Bluetooth |
| `sensor` Firmware version | `software_version` (diagnostic) | heartbeat |

There is also a `gts_wavepump.set_tidal_schedule` service (target the fan
entity) that writes the whole tidal curve at once — a list of up to 24
`{mode, power, period}` segments — via a single config-v2 frame, so automations
can reshape the day's schedule. UI and entity names are localized (English and
简体中文, following the HA language).

Live status is polled every 30 s: the heartbeat (interface 3) gives mode /
power / temperature / period, and a full config read (interface 2) populates the
selects, numbers and switch. Protocol field tables (`Zc`/`Jc`) are version-aware
(`software_version > 4` uses the new `Jc` table); verified on hardware with
software_version 17.

Notes:
- Setting intensity or a waveform **forces manual mode** (the pump leaves its
  tidal schedule), mirroring how direct control works in the app.
- **On/off** uses the app's real commands: off is `manual_mode` = 7 (关机),
  on restores a waveform at the set power. Mode 5 is **feed** (the Feed button).
- The **tidal curve** is read-only as a sensor and writable in bulk via the
  `set_tidal_schedule` service; there is no per-segment editor UI (use the app
  for visual editing, or the service from automations).
- **Tidal intensity / gain** scales the existing24-segment daily curve from an
  immutable persisted baseline:100% restores the original exactly, below100
  attenuates for acclimation and above100 adds weather gain (source candidate
  range10–200%, not deployed/released). Each result remains capped by the existing
  raw power limit99; this is a software bound, not a tank-specific safe flow limit.
  Hourly waveforms stay unchanged; peaks flatten where clipping occurs. Gain is
  computed from the original, never from a previously scaled curve, including
  retry/restart. Only effective in tide mode. The currently released0.6.2 entity
  still limits the overlay to100%; no device or HA update is implied here.

## How it works

Standard ISSC/Microchip transparent-UART GATT:

- Service `55535343-FE7D-4AE5-8FA9-9FAFD205E455`
- Write frames to `49535343-8841-43F4-A8D4-ECBE34729BB3`
- Receive responses as notifications on `49535343-1E4D-4BD9-BA61-23C647249616`

Frames are `[250, interface, ...data, checksum]`, `checksum = sum(preceding) %
255`. All framing/parsing lives in [`protocol.py`](custom_components/gts_wavepump/protocol.py)
(Home Assistant agnostic, unit-tested in [`tests/test_protocol.py`](tests/test_protocol.py)).

## Confirmed from the app (app-service.js)

The `Zc`/`Jc` field tables, mode map and value semantics were extracted from the
official app and verified on hardware:

- **manual_power** raw 0–99 (the app's home card displays raw + 20; HA uses the
  raw value, matching the manual slider). On new firmware the live power is a
  per-mode bank `manual_power_<manual_mode>` (banks 1/2/3/4/6).
- **manual_period** = raw / 100 seconds (raw 67 == 0.67 s).
- **mode** 1=constant 2=pulse 3=sine 4=turbulence 5=feed 6=surge 7=off;
  **manual_or_auto** 1=manual 2=tide; **forward_or_reverse** 1=direct 2=reverse.

## Remaining TODOs

- **Scheduled feeding**: the three slots can be enabled/disabled from HA; their
  times are read-only (set them in the app — the per-slot time write ids are a
  vendor hot-update feature not present in the shipped APK).
- **Period** raw min/max not pinned down (a generous range is used).
- **Reverse** (`forward_or_reverse`) is intentionally not exposed: the L20
  firmware removed the reverse feature and the app does not offer it.
- The real device's UART characteristics are swapped vs. the Microchip
  convention; the integration resolves write/notify by GATT property at connect.

## Running the tests

```bash
python3 -m pytest tests/test_protocol.py -q
```

The protocol tests have no Home Assistant dependency.
