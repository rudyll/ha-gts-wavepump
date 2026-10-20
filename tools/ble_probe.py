#!/usr/bin/env python3
"""Standalone BLE probe for calibrating the GTS L20 wave pump.

Dev helper only — not part of the HA integration. It reuses the repo's
``protocol.py`` for framing so there is a single source of truth, but has no
Home Assistant dependency. Run it from a laptop within BLE range of the pump.

    pip install bleak
    python3 tools/ble_probe.py                 # scan + read-only probe
    python3 tools/ble_probe.py --address <MAC>  # skip scan
    python3 tools/ble_probe.py --set-power 50   # OPT-IN: writes to the pump

Read-only mode scans for GTS_WAVE20_*, connects, subscribes to notifications,
sends a heartbeat (interface 3) and a read-all-config (interface 2), and prints
the decoded/raw responses. Writes only happen with an explicit --set-* flag.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys
from pathlib import Path

from bleak import BleakClient, BleakScanner

_REPO = Path(__file__).resolve().parents[1]
_CC = _REPO / "custom_components" / "gts_wavepump"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


const = _load("gts_const", _CC / "const.py")
protocol = _load("gts_protocol", _CC / "protocol.py")


def _on_notify(_char, data: bytearray) -> None:
    raw = bytes(data)
    print(f"  <- {list(raw)}  (hex {raw.hex()})")
    try:
        iface, payload = protocol.parse_response(raw)
    except protocol.InvalidFrameError as err:
        print(f"     ! invalid frame: {err}")
        return
    print(f"     interface={iface} payload={list(payload)}")
    if iface == protocol.IFACE_HEARTBEAT:
        try:
            st = protocol.parse_heartbeat(raw)
            print(
                f"     heartbeat: sw={st.software_version} mode={st.current_mode} "
                f"power={st.current_power} temp={st.current_temp}C "
                f"period={st.current_period} err={st.error_code}"
            )
        except protocol.InvalidFrameError as err:
            print(f"     ! heartbeat decode failed: {err}")


async def _find_address() -> str | None:
    print(f"Scanning 10s for {const.NAME_PREFIX}* ...")
    devices = await BleakScanner.discover(timeout=10.0)
    for d in devices:
        if (d.name or "").startswith(const.NAME_PREFIX):
            print(f"Found {d.name} @ {d.address}")
            return d.address
    print("No GTS_WAVE20_* device found. Is the pump powered and in range?")
    return None


async def _send(client: BleakClient, label: str, frame: bytes) -> None:
    print(f"-> {label}: {list(frame)}")
    await client.write_gatt_char(const.UART_WRITE_CHAR_UUID, frame, response=False)
    await asyncio.sleep(1.5)  # give the pump time to notify back


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--address", help="BLE MAC/UUID; skips scanning")
    ap.add_argument("--set-power", type=int, metavar="N",
                    help="OPT-IN write: manual_power = N (0-100)")
    ap.add_argument("--set-field", nargs=2, type=int, metavar=("FIELD", "VALUE"),
                    help="OPT-IN write: arbitrary field = value")
    args = ap.parse_args()

    address = args.address or await _find_address()
    if not address:
        return

    async with BleakClient(address) as client:
        print(f"Connected: {client.is_connected}")
        await client.start_notify(const.UART_NOTIFY_CHAR_UUID, _on_notify)
        await asyncio.sleep(0.5)

        # --- read-only probes ---
        await _send(client, "heartbeat(3)", protocol.build_heartbeat())
        await _send(client, "read-all-config(2)", protocol.build_read_config())

        # --- opt-in writes (change the real pump!) ---
        if args.set_power is not None:
            await _send(client, f"write manual_power={args.set_power}",
                        protocol.build_write_field(
                            protocol.FIELD_MANUAL_POWER, args.set_power))
            await _send(client, "heartbeat(3)", protocol.build_heartbeat())
        if args.set_field is not None:
            field, value = args.set_field
            await _send(client, f"write field {field}={value}",
                        protocol.build_write_field(field, value))
            await _send(client, "heartbeat(3)", protocol.build_heartbeat())

        print("Listening 5s for any further notifications ...")
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
