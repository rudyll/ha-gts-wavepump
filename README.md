# GTS L20 Wave Pump — Home Assistant (local BLE)

A Home Assistant custom integration for the **狗头鲨 (Goutousha) GTS L20** wave
pump, controlled **locally over Bluetooth Low Energy**. No vendor cloud, no
Aliyun MQTT, no API keys.

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
**+ Add integration → GTS L20 Wave Pump**.

## Entities

| Entity | Control / reading | Maps to |
| --- | --- | --- |
| `fan` | On/off + intensity % | active `manual_power` bank |
| `select` Run mode | Manual / Tide | `manual_or_auto` |
| `select` Wave mode | Constant/Pulse/Sine/Turbulence/Surge | `manual_mode` |
| `number` Wave period | Seconds | active `manual_period` bank |
| `number` Feed time | Seconds | `feed_time` |
| `number` Communication channel | Channel id (config) | `communication_channel` |
| `button` Feed | Feed now | `manual_mode` = 5 |
| `switch` Reverse flow | Direct / reverse | `forward_or_reverse` |
| `binary_sensor` Light | On / off (read-only) | `light_on` (2=on/1=off) |
| `sensor` Temperature | °C | heartbeat `current_temp` |
| `sensor` Flow mode | Running waveform | heartbeat `current_mode` |
| `sensor` Firmware version | `software_version` (diagnostic) | heartbeat |

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
- The 24-segment **tidal curve** editor is not exposed yet.

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

- **On/off** writes power 0 instead of the app's dedicated 关机 command.
- **Period** raw min/max not pinned down (a generous range is used).
- The **24-segment tidal curve** editor, **feed** scheduling and **light** are
  not exposed.
- The real device's UART characteristics are swapped vs. the Microchip
  convention; the integration resolves write/notify by GATT property at connect.

## Running the tests

```bash
python3 -m pytest tests/test_protocol.py -q
```

The protocol tests have no Home Assistant dependency.
