"""Command-sequence regressions using the real fan class and simulated BLE I/O.

Load its class AST to avoid importing Home Assistant in this stdlib-only test.
This checks control logic, not HA registration or physical pump behaviour.
Run: python3 -m unittest discover -s tests -p test_fan.py -v
"""
from __future__ import annotations

import ast
import importlib.util
from enum import IntFlag
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1] / "custom_components/gts_wavepump"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


protocol = load_module("fan_test_protocol", ROOT / "protocol.py")
const = load_module("fan_test_const", ROOT / "const.py")


class Entity:
    def __init__(self, coordinator):
        self.coordinator = coordinator


class FanEntity:
    pass


class Features(IntFlag):
    SET_SPEED = 1
    TURN_ON = 2
    TURN_OFF = 4


def load_fan():
    source = ast.parse((ROOT / "fan.py").read_text())
    cls = next(node for node in source.body
               if isinstance(node, ast.ClassDef) and node.name == "GtsWavePumpFan")
    isolated = ast.Module(body=[ast.ImportFrom(module="__future__", names=[
        ast.alias(name="annotations")], level=0), cls], type_ignores=[])
    ast.fix_missing_locations(isolated)
    namespace = dict(protocol=protocol, GtsWavePumpEntity=Entity,
                     FanEntity=FanEntity, FanEntityFeature=Features,
                     POWER_DEFAULT_ON=const.POWER_DEFAULT_ON,
                     POWER_MIN=const.POWER_MIN, POWER_MAX=const.POWER_MAX)
    exec(compile(isolated, str(ROOT / "fan.py"), "exec"), namespace)
    return namespace["GtsWavePumpFan"]


Fan = load_fan()


class FanTests(unittest.IsolatedAsyncioTestCase):
    def make_fan(self, run_mode=protocol.MANUAL_OR_AUTO_TIDE, sw=17):
        device = SimpleNamespace(address="test-pump", async_write_named=AsyncMock())
        coordinator = SimpleNamespace(device=device, async_request_refresh=AsyncMock(),
            data=SimpleNamespace(software_version=sw, current_mode=3,
                current_power=55, config={"manual_or_auto": run_mode}))
        return Fan(coordinator), coordinator

    async def test_tide_off_on_restarts_before_returning_to_tide(self):
        for sw, field in [(17, "manual_power_1"), (3, "manual_power")]:
            with self.subTest(sw=sw):
                fan, c = self.make_fan(sw=sw)
                await fan.async_turn_off()
                self.assertEqual(c.device.async_write_named.await_args.args,
                                 ("manual_mode", protocol.MODE_OFF, sw))
                c.data.current_mode = protocol.MODE_OFF
                c.data.current_power = 0
                self.assertFalse(fan.is_on)
                c.device.async_write_named.reset_mock()
                await fan.async_turn_on()
                self.assertEqual([call.args for call in c.device.async_write_named.await_args_list], [
                    ("manual_or_auto", protocol.MANUAL_OR_AUTO_MANUAL, sw),
                    ("manual_mode", 1, sw),
                    (field, const.POWER_DEFAULT_ON, sw),
                    ("manual_or_auto", protocol.MANUAL_OR_AUTO_TIDE, sw)])
                self.assertEqual(c.async_request_refresh.await_count, 2)
                # Commands alone must not invent running telemetry.
                self.assertFalse(fan.is_on)

    async def test_retained_tide_resumes_after_reload_or_native_feed(self):
        for mode in [protocol.MODE_OFF, protocol.MODE_FEED]:
            with self.subTest(mode=mode):
                fan, c = self.make_fan()
                c.data.current_mode = mode
                c.data.current_power = 0
                await fan.async_turn_on()
                self.assertEqual(c.device.async_write_named.await_count, 4)
                self.assertEqual(c.device.async_write_named.await_args.args,
                                 ("manual_or_auto", protocol.MANUAL_OR_AUTO_TIDE, 17))

    async def test_manual_off_on_does_not_switch_to_tide(self):
        fan, c = self.make_fan(run_mode=protocol.MANUAL_OR_AUTO_MANUAL)
        await fan.async_turn_off()
        c.data.current_mode = protocol.MODE_OFF
        c.device.async_write_named.reset_mock()
        await fan.async_turn_on()
        self.assertEqual(c.device.async_write_named.await_count, 3)
        self.assertNotIn(("manual_or_auto", protocol.MANUAL_OR_AUTO_TIDE, 17),
                         [call.args for call in c.device.async_write_named.await_args_list])

    async def test_explicit_percentage_overrides_remembered_tide(self):
        fan, c = self.make_fan()
        await fan.async_turn_off()
        c.data.current_mode = protocol.MODE_OFF
        c.device.async_write_named.reset_mock()
        await fan.async_turn_on(percentage=30)
        self.assertEqual([call.args for call in c.device.async_write_named.await_args_list], [
            ("manual_or_auto", protocol.MANUAL_OR_AUTO_MANUAL, 17),
            ("manual_mode", 1, 17), ("manual_power_1", 30, 17)])

    async def test_failed_restart_propagates_without_refresh(self):
        fan, c = self.make_fan()
        fan._run_mode_before_off = protocol.MANUAL_OR_AUTO_TIDE
        c.device.async_write_named.side_effect = OSError("BLE unavailable")
        with self.assertRaises(OSError):
            await fan.async_turn_on()
        c.async_request_refresh.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
