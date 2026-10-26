"""Actual storm helper/fan methods with simulated banks, BLE and clocks."""
import asyncio
from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import AsyncMock
from test_fan import Fan,protocol,control,load_module
storm=load_module('gts_storm_plan',Path(__file__).resolve().parents[1]/'custom_components/gts_wavepump/storm.py')

class PlanTests(unittest.TestCase):
 def test_daily_gain_not_compounded_with_weather(self):
  p=storm.storm_target([60]*24,12,150,130,99)
  self.assertEqual((p.power,p.weather_power),(90,78))
 def test_night_zero_and_cap(self):
  p=storm.storm_target([6]*24,0,150,130,80);self.assertEqual(p.power,9)
  p=storm.storm_target([60]*24,12,150,130,80);self.assertEqual(p.power,80);self.assertTrue(p.clipped)
  with self.assertRaises(ValueError):storm.storm_target([0]*24,0,150,130,80)
  with self.assertRaises(ValueError):storm.storm_target([60]*24,0,150,130,65)
 def test_original_baseline_required_when_weather_is_scaled(self):
  self.assertEqual(storm.daily_baseline(None,[60]*24,100),[60]*24)
  with self.assertRaises(ValueError):storm.daily_baseline(None,[78]*24,130)
  self.assertEqual(storm.daily_baseline([60]*24,[78]*24,130),[60]*24)
 def test_bad_values_never_create_a_plan(self):
  for baseline in [None,[],[1]*23,[True]*24,[-1]*24,[100]*24]:
   with self.subTest(baseline=baseline):
    with self.assertRaises(ValueError):storm.storm_target(baseline,0,150,130,80)
  for hour in [-1,24,True,'0']:
   with self.assertRaises(ValueError):storm.storm_target([6]*24,hour,150,130,80)
  for gain in [99,201,True,float('nan'),float('inf'),None]:
   with self.assertRaises(ValueError):storm.storm_target([6]*24,0,gain,130,80)
  for weather in [50,None,float('nan'),True]:
   with self.assertRaises(ValueError):storm.storm_target([6]*24,0,150,weather,80)
  with self.assertRaises(ValueError):storm.storm_target([6]*24,0,120,130,80)
  for cap in [0,100,True,80.5]:
   with self.assertRaises(ValueError):storm.storm_target([6]*24,0,150,130,cap)

class ServiceTests(unittest.IsolatedAsyncioTestCase):
 def make(self,base=None,gain=130,run='tide',hour=12,sw=17):
  self.hour=hour;self.writes=[];self.outputs=[];self.fail_field=None;self.cancel_field=None;self.stop_after_power=False;self.mismatch=False;self.status_reads=0
  base=[60]*24 if base is None else base
  curve=[protocol.TidalSegment(3,min(99,round(p*gain/100)),10)for p in base]
  self.config={'manual_or_auto':2 if run=='tide'else 1,'manual_mode':3}
  for mode in protocol.MANUAL_MODES:
   self.config[protocol.power_field_name(mode,sw)]=99
   self.config[protocol.period_field_name(mode,sw)]=55
  self.status=SimpleNamespace(software_version=sw,error_code=0,current_mode=3,current_power=curve[hour].power)
  self.overlay=SimpleNamespace(_baseline=list(base)if gain!=100 else None,_attr_native_value=gain,_pending=None,_load_operation=AsyncMock())
  async def read_status():
   self.status_reads+=1
   d=vars(self.status).copy()
   if self.mismatch and self.status_reads>1:d['current_power']+=1
   return SimpleNamespace(**d)
  async def write(field,value,software):
   device.operations.check();self.writes.append((field,value,software))
   if field==self.fail_field:raise OSError('simulated write failure')
   if field==self.cancel_field:raise asyncio.CancelledError()
   self.config[field]=value
   if self.config['manual_or_auto']==1:
    mode=self.config['manual_mode'];self.status.current_mode=mode
    self.status.current_power=self.config.get(protocol.power_field_name(mode,software),99)
   self.outputs.append(self.status.current_power)
   if self.stop_after_power and field==protocol.power_field_name(6,software):device.operations.request_stop()
  device=SimpleNamespace(address='fixture',operations=control.OperationGate(),command_error=None,
   async_get_status=AsyncMock(side_effect=read_status),async_read_config=AsyncMock(side_effect=lambda sw:(dict(self.config),list(curve))),
   async_write_named=AsyncMock(side_effect=write),async_emergency_stop=AsyncMock())
  c=SimpleNamespace(device=device,tidal_overlay=self.overlay,data=SimpleNamespace(software_version=sw),async_request_refresh=AsyncMock())
  Fan.async_storm_gain.__globals__.update(storm=storm,dt_util=SimpleNamespace(now=lambda:SimpleNamespace(hour=self.hour)))
  return Fan(c),c,curve
 async def apply(self,fan,**kw):
  await fan.async_storm_gain(gain=kw.pop('gain',150),power_ceiling=kw.pop('power_ceiling',80),wave_mode=kw.pop('wave_mode','surge'),expected_run_mode=kw.pop('expected_run_mode','tide'),clock_confirmed=kw.pop('clock_confirmed',True),**kw)
 async def test_preload_banks_before_switch_no_old_high_spike(self):
  fan,c,curve=self.make();await self.apply(fan)
  self.assertEqual(self.writes,[(protocol.power_field_name(6,17),80,17),(protocol.period_field_name(6,17),10,17),('manual_mode',6,17),('manual_or_auto',1,17)])
  self.assertTrue(all(p<=80 for p in self.outputs));self.assertEqual(c.device.command_error,None)
  self.assertEqual([x.power for x in curve],[78]*24);self.overlay._load_operation.assert_awaited_once()
 async def test_night_and_daily_wave_and_gap(self):
  fan,c,_=self.make(base=[6]*24,hour=0);await self.apply(fan,wave_mode='daily')
  self.assertEqual(self.writes[0],(protocol.power_field_name(3,17),9,17));self.assertTrue(max(self.outputs)<=9)
  self.writes=[];self.config['manual_or_auto']=1
  await self.apply(fan,gain=130,wave_mode='daily',expected_run_mode='manual')
  self.assertEqual(self.writes[0],(protocol.power_field_name(3,17),8,17))
 async def test_hour_resolved_after_waiting_for_operation_lock(self):
  fan,c,_=self.make(base=[6]+[60]*23,hour=12)
  entered=asyncio.Event();release=asyncio.Event()
  async def block():
   async with c.device.operations.hold():entered.set();await release.wait()
  held=asyncio.create_task(block());await entered.wait();task=asyncio.create_task(self.apply(fan))
  await asyncio.sleep(0);self.hour=0;release.set();await held;await task
  self.assertEqual(self.writes[0][1],9)
 async def test_stopped_feeding_or_wrong_owner_mode_cannot_start(self):
  for change in [('current_mode',7),('current_mode',5),('current_power',0),('error_code',1)]:
   fan,c,_=self.make();setattr(self.status,*change)
   with self.assertRaises(ValueError):await self.apply(fan)
   self.assertEqual(self.writes,[])
  fan,c,_=self.make(run='manual')
  with self.assertRaises(ValueError):await self.apply(fan)
  self.assertEqual(self.writes,[])
 async def test_clock_legacy_pending_missing_and_zero_fail_before_writes(self):
  for case in ['clock','legacy','pending','missing','zero','attenuation','cap']:
   fan,c,_=self.make(sw=3 if case=='legacy'else 17,base=[0]*24 if case=='zero'else None,gain=50 if case=='attenuation'else 130)
   if case=='pending':self.overlay._pending={}
   if case=='missing':self.overlay._baseline=None
   with self.subTest(case=case):
    with self.assertRaises(ValueError):await self.apply(fan,clock_confirmed=case!='clock',power_ceiling=65 if case=='cap'else 80)
    self.assertEqual(self.writes,[])
 async def test_preparation_failure_does_not_switch_or_stop_existing_tide(self):
  fan,c,_=self.make();self.fail_field=protocol.power_field_name(6,17)
  with self.assertRaises(OSError):await self.apply(fan)
  self.assertEqual(len(self.writes),1);c.device.async_emergency_stop.assert_not_awaited()
 async def test_activation_failure_or_cancel_checks_stop_and_reports_error(self):
  for cancel in [False,True]:
   fan,c,_=self.make()
   if cancel:self.cancel_field='manual_or_auto'
   else:self.fail_field='manual_or_auto'
   with self.assertRaises(asyncio.CancelledError if cancel else OSError):await self.apply(fan)
   c.device.async_emergency_stop.assert_awaited_once();self.assertIn('storm gain failed',c.device.command_error)
 async def test_unconfirmed_readback_never_reports_success(self):
  fan,c,_=self.make();self.mismatch=True
  with self.assertRaisesRegex(ValueError,'not confirmed'):await self.apply(fan)
  c.device.async_emergency_stop.assert_awaited_once()
 async def test_stop_generation_prevents_old_mode_activation(self):
  fan,c,_=self.make();self.stop_after_power=True
  with self.assertRaises(control.OperationSuperseded):await self.apply(fan)
  self.assertTrue(all(name not in ['manual_mode','manual_or_auto']for name, _, _ in self.writes))
if __name__=='__main__':unittest.main()
