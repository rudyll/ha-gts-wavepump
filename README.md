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

## What works today

| Entity | Control | Maps to |
| --- | --- | --- |
| `fan` | On/off + intensity % | `manual_power` (field 4) |
| `switch` | Reverse flow (optimistic) | `forward_or_reverse` (field 79) |

State (power, temperature, mode) is polled every 30 s via the heartbeat
(interface 3).

## How it works

Standard ISSC/Microchip transparent-UART GATT:

- Service `55535343-FE7D-4AE5-8FA9-9FAFD205E455`
- Write frames to `49535343-8841-43F4-A8D4-ECBE34729BB3`
- Receive responses as notifications on `49535343-1E4D-4BD9-BA61-23C647249616`

Frames are `[250, interface, ...data, checksum]`, `checksum = sum(preceding) %
255`. All framing/parsing lives in [`protocol.py`](custom_components/gts_wavepump/protocol.py)
(Home Assistant agnostic, unit-tested in [`tests/test_protocol.py`](tests/test_protocol.py)).

## Not yet calibrated (TODOs)

These need a hardware capture or a full-config read before they can be exposed
safely; they are marked `TODO(calibrate)` in the code:

- **manual_power** is confirmed 0–100 % (the app shows "功率: 65%"), but whether
  power `0` truly stops the pump or there is a separate on/off command (the app
  has a dedicated "关机" button) is unconfirmed.
- **manual_period** is a time in **seconds** (app shows 0.670S / 1.300S); the
  raw→seconds mapping is not yet captured, so no `number` entity is exposed yet.
- **manual_mode / current_mode**: 5 waveforms (恒定/脉动/正弦/乱流/涌浪 =
  constant/pulse/sine/turbulence/surge); the numeric↔name mapping is unconfirmed.
- **forward_or_reverse** value semantics (which value is forward vs. reverse)
  are assumed; the reverse switch is therefore optimistic.
- **software_version > 4** devices use the newer "Jc" field table; this
  skeleton targets the old "Zc" table. Jc structure is noted in `protocol.py`.
- Current temperature is reported in °C directly (not yet exposed as a sensor).

## Running the tests

```bash
python3 -m pytest tests/test_protocol.py -q
```

The protocol tests have no Home Assistant dependency.
