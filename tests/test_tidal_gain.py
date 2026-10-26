"""Relative gain from the immutable daily curve; fake BLE/storage only."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import unittest
from test_reliability import Number,Store,control

class GainTests(unittest.IsolatedAsyncioTestCase):
 def make(self,powers=None):
  Store.saved={}
  powers=powers or [20,40,60]*8
  c=SimpleNamespace(hass=None,data=SimpleNamespace(tidal=[SimpleNamespace(power=p)for p in powers]),device=SimpleNamespace(address='gain',operations=control.OperationGate()),async_request_refresh=AsyncMock())
  async def write(values):c.data.tidal=[SimpleNamespace(power=p)for p in values]
  c.device.async_write_tidal_powers=AsyncMock(side_effect=write)
  return Number(c),c,powers
 async def test_above_100_increases_existing_curve(self):
  n,c,base=self.make();await n.async_set_native_value(120)
  self.assertEqual([s.power for s in c.data.tidal],[24,48,72]*8)
  self.assertEqual(n._baseline,base)
 async def test_no_compounding_repeated_weather_and_exact_normal_restore(self):
  n,c,base=self.make();await n.async_set_native_value(130);await n.async_set_native_value(130)
  self.assertEqual([s.power for s in c.data.tidal],[26,52,78]*8)
  await n.async_set_native_value(110);self.assertEqual([s.power for s in c.data.tidal],[22,44,66]*8)
  await n.async_set_native_value(100);self.assertEqual([s.power for s in c.data.tidal],base);self.assertFalse(n.has_baseline)
 async def test_upper_segments_clipped_to_existing_raw_limit_and_zeros_stay_zero(self):
  n,c,base=self.make([0,5,50,60,90,99]*4);await n.async_set_native_value(200)
  self.assertEqual([s.power for s in c.data.tidal],[0,10,99,99,99,99]*4)
  await n.async_set_native_value(100);self.assertEqual([s.power for s in c.data.tidal],base)
 async def test_restart_uses_saved_base_not_boosted_curve(self):
  n,c,base=self.make();await n.async_set_native_value(130)
  other=Number(c);await other.async_set_native_value(120)
  self.assertEqual([s.power for s in c.data.tidal],[24,48,72]*8)
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
  self.assertEqual([s.power for s in c.data.tidal],[26,52,78]*8)
 async def test_invalid_gain_never_writes_or_persists(self):
  for bad in [9,201,True,None,'130',float('nan'),float('inf')]:
   n,c,_=self.make()
   with self.subTest(value=bad):
    with self.assertRaises(ValueError):await n.async_set_native_value(bad)
    c.device.async_write_tidal_powers.assert_not_awaited();self.assertEqual(Store.saved,{})
 async def test_invalid_saved_gain_refuses_writes(self):
  for bad in [0,201,True,'130',float('nan')]:
   n,c,base=self.make();Store.saved[n._store.key]={'baseline':base,'value':bad,'pending':None}
   with self.subTest(value=bad):
    with self.assertRaisesRegex(ValueError,"invalid saved tidal gain"):await n.async_set_native_value(120)
    c.device.async_write_tidal_powers.assert_not_awaited()
 def test_entity_exposes_gain_range(self):self.assertEqual(Number._attr_native_max_value,200)
