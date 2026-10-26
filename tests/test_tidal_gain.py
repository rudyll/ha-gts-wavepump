"""Relative gain from the immutable daily curve; fake BLE/storage only."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import unittest
from test_reliability import Number,Store,control

class GainTests(unittest.IsolatedAsyncioTestCase):
 def make(self,powers=None):
  Store.saved={}
  powers=powers or [20,40,60]*8
  c=SimpleNamespace(hass=None,data=SimpleNamespace(software_version=17,tidal=[SimpleNamespace(power=p)for p in powers]),device=SimpleNamespace(address='gain',operations=control.OperationGate()),async_request_refresh=AsyncMock())
  c.device.async_read_config=AsyncMock(side_effect=lambda sw:({},c.data.tidal))
  async def write(values):c.data.tidal=[SimpleNamespace(power=p)for p in values]
  c.device.async_write_tidal_powers=AsyncMock(side_effect=write)
  return Number(c),c,powers
 async def test_above_100_increases_existing_curve(self):
  n,c,base=self.make();await n.async_set_native_value(120)
  self.assertEqual([s.power for s in c.data.tidal],[28,52,76]*8)
  self.assertEqual(n._baseline,base)
 async def test_no_compounding_repeated_weather_and_exact_normal_restore(self):
  n,c,base=self.make();await n.async_set_native_value(130);await n.async_set_native_value(130)
  self.assertEqual([s.power for s in c.data.tidal],[32,58,84]*8)
  await n.async_set_native_value(110);self.assertEqual([s.power for s in c.data.tidal],[24,46,68]*8)
  await n.async_set_native_value(100);self.assertEqual([s.power for s in c.data.tidal],base);self.assertFalse(n.has_baseline)
 async def test_no_peak_clipping_and_zeros_stay_zero(self):
  n,c,base=self.make([0,5,50,60,90,99]*4)
  with self.assertRaises(ValueError):await n.async_set_native_value(101)
  c.device.async_write_tidal_powers.assert_not_awaited()
  self.assertEqual(n.native_max_value,100)
  n,c,base=self.make([0,60]*12);await n.async_set_native_value(148)
  self.assertEqual([s.power for s in c.data.tidal],[0,98]*12)
  with self.assertRaises(ValueError):await n.async_set_native_value(149)
  await n.async_set_native_value(100);self.assertEqual([s.power for s in c.data.tidal],base)
 async def test_restart_uses_saved_base_not_boosted_curve(self):
  n,c,base=self.make();await n.async_set_native_value(130)
  other=Number(c);await other.async_set_native_value(120)
  self.assertEqual([s.power for s in c.data.tidal],[28,52,76]*8)
  await other.async_set_native_value(100);self.assertEqual([s.power for s in c.data.tidal],base)
 async def test_failed_boost_retry_does_not_capture_partial_result(self):
  n,c,base=self.make()
  async def partial(values):
   c.data.tidal=[SimpleNamespace(power=p if i<12 else base[i])for i,p in enumerate(values)]
   raise OSError('partial write')
  c.device.async_write_tidal_powers=AsyncMock(side_effect=partial)
  with self.assertRaises(OSError):await n.async_set_native_value(130)
  async def write(values):c.data.tidal=[SimpleNamespace(power=p)for p in values]
  c.device.async_write_tidal_powers=AsyncMock(side_effect=write)
  other=Number(c);await other.async_set_native_value(130)
  self.assertEqual([s.power for s in c.data.tidal],[32,58,84]*8)
 async def test_invalid_gain_never_writes_or_persists(self):
  for bad in [9,10001,True,None,'130',float('nan'),float('inf')]:
   n,c,_=self.make()
   with self.subTest(value=bad):
    with self.assertRaises(ValueError):await n.async_set_native_value(bad)
    c.device.async_write_tidal_powers.assert_not_awaited();self.assertEqual(Store.saved,{})
 async def test_invalid_saved_gain_refuses_writes(self):
  for bad in [0,10001,True,'130',float('nan')]:
   n,c,base=self.make();Store.saved[n._store.key]={'baseline':base,'value':bad,'pending':None}
   with self.subTest(value=bad):
    with self.assertRaisesRegex(ValueError,"invalid saved tidal gain"):await n.async_set_native_value(120)
    c.device.async_write_tidal_powers.assert_not_awaited()
 def test_entity_exposes_gain_range(self):self.assertEqual(Number._attr_native_max_value,10000)

 async def test_external_curve_and_legacy_units_refuse_writes(self):
  n,c,base=self.make();await n.async_set_native_value(120)
  c.data.tidal[0].power=33;c.device.async_write_tidal_powers.reset_mock()
  with self.assertRaisesRegex(ValueError,'external tidal'):await n.async_set_native_value(100)
  c.device.async_write_tidal_powers.assert_not_awaited()
  n,c,base=self.make();Store.saved[n._store.key]={'baseline':base,'value':120,'pending':None}
  with self.assertRaisesRegex(ValueError,'legacy raw gain'):await n.async_set_native_value(100)
  c.device.async_write_tidal_powers.assert_not_awaited()

 async def test_fresh_curve_overrides_stale_coordinator_before_first_gain(self):
  n,c,_=self.make([60]*24)
  c.device.async_read_config=AsyncMock(return_value=({},[SimpleNamespace(power=80)for _ in range(24)]))
  with self.assertRaises(ValueError):await n.async_set_native_value(120)
  c.device.async_write_tidal_powers.assert_not_awaited()

 async def test_legacy_firmware_retains_unshifted_units_and99_cap(self):
  n,c,_=self.make([60]*24);c.data.software_version=3
  self.assertEqual(n.native_max_value,165)
  await n.async_set_native_value(150)
  self.assertEqual([v.power for v in c.data.tidal],[90]*24)
  self.assertEqual(n.extra_state_attributes['max_app_output_percent'],99)
  await n.async_set_native_value(100)
  self.assertEqual([v.power for v in c.data.tidal],[60]*24)
