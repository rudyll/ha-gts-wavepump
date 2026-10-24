"""Real production classes; simulated transport/storage, no device I/O."""
import ast,asyncio,copy,logging,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from test_fan import FanTests, protocol, load_module, ROOT
control=load_module('gts_test_control',ROOT/'control.py')

def load_class(filename,name,**extra):
    node=next(n for n in ast.parse((ROOT/filename).read_text()).body if isinstance(n,ast.ClassDef) and n.name==name)
    tree=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),node],type_ignores=[])
    ast.fix_missing_locations(tree)
    ctx=dict(asyncio=asyncio,protocol=protocol,OperationGate=control.OperationGate,serialized=control.serialized,UpdateFailed=RuntimeError,RESPONSE_TIMEOUT=.05,_LOGGER=logging.getLogger('test'))
    ctx.update(extra);exec(compile(tree,str(ROOT/filename),'exec'),ctx);return ctx[name]
Device=load_class('__init__.py','GtsWavePumpDevice')

class Operations(FanTests):
    async def test_later_off_waits_for_complete_on(self):
        fan,c=self.make_fan();fan._run_mode_before_off=2
        entered=asyncio.Event();resume=asyncio.Event();writes=[]
        async def write(name,value,sw):
            writes.append((name,value))
            if len(writes)==1:entered.set();await resume.wait()
        c.device.async_write_named=write
        on=asyncio.create_task(fan.async_turn_on());await entered.wait()
        off=asyncio.create_task(fan.async_turn_off());await asyncio.sleep(0)
        self.assertFalse(off.done());resume.set();await asyncio.gather(on,off)
        self.assertEqual(writes[-1],('manual_mode',7))
    async def test_every_resume_failure_stops_before_unlocking(self):
        for stage in range(1,5):
            with self.subTest(stage=stage):
                fan,c=self.make_fan();fan._run_mode_before_off=2;count=0
                async def write(*args):
                    nonlocal count
                    count+=1
                    if count==stage:raise OSError('BLE failed')
                c.device.async_write_named=write
                with self.assertRaises(OSError):await fan.async_turn_on()
                c.device.async_emergency_stop.assert_awaited_once()
                self.assertIn('recovery required',c.device.command_error)
    async def test_cancelled_start_finishes_stop(self):
        fan,c=self.make_fan();fan._run_mode_before_off=2;entered=asyncio.Event()
        async def write(*args): entered.set();await asyncio.Event().wait()
        c.device.async_write_named=write
        task=asyncio.create_task(fan.async_turn_on());await entered.wait();task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        c.device.async_emergency_stop.assert_awaited_once()
        async with c.device.operations.hold():pass
    async def test_refresh_runs_outside_operation(self):
        fan,c=self.make_fan()
        async def refresh():
            # A refresh uses a different HA coordinator task.
            async def poll():
                async with c.device.operations.hold():pass
            await asyncio.wait_for(asyncio.create_task(poll()),.2)
        c.async_request_refresh=refresh
        await fan.async_turn_on();await fan.async_turn_off()

class AckTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_wrong_interface_and_wrong_field_are_ignored(self):
        d=Device(None,'test')
        async def write(char,frame,**kwargs):
            for value in [b'garbage',protocol.build_frame(2,[0]),protocol.build_frame(1,[3,1])]:
                d._notification_handler(None,bytearray(value));self.assertFalse(d._notify_future.done())
            d._notification_handler(None,bytearray(frame))
        d._ensure_connected=AsyncMock(return_value=SimpleNamespace(write_gatt_char=write))
        answer=await d._send(protocol.build_write_field(3,7),expect_response=True)
        self.assertEqual(answer,protocol.build_write_field(3,7))
    async def test_generic_v2_ack_still_requires_readback(self):
        d=Device(None,'test');d._send=AsyncMock(return_value=protocol.build_frame(10))
        d.async_read_config=AsyncMock(return_value=({'manual_or_auto':1},[]))
        with self.assertRaises(RuntimeError):await d.async_write_named('manual_or_auto',2,17)
    async def test_invalid_ack_times_out(self):
        d=Device(None,'test')
        async def write(*args,**kwargs):d._notification_handler(None,bytearray(b'garbage'))
        d._ensure_connected=AsyncMock(return_value=SimpleNamespace(write_gatt_char=write))
        with self.assertRaises(RuntimeError):await d._send(protocol.build_write_field(3,7),expect_response=True)

class Base:
    def __init__(self,c):self.coordinator=c
    def async_write_ha_state(self):pass
class Store:
    saved={}
    def __init__(self,hass,version,key):self.key=key
    async def async_load(self):return copy.deepcopy(self.saved.get(self.key))
    async def async_save(self,value):self.saved[self.key]=copy.deepcopy(value)
Number=load_class('number.py','TidalIntensityNumber',GtsWavePumpEntity=Base,RestoreNumber=type('Restore',(),{}),PERCENTAGE='%',NumberMode=SimpleNamespace(SLIDER='slider'),POWER_MIN=0,POWER_MAX=99,Store=Store)
class BaselineTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_failure_reload_and_retry_keep_original(self):
        Store.saved={}
        c=SimpleNamespace(hass=None,data=SimpleNamespace(tidal=[SimpleNamespace(power=80) for _ in range(24)]),device=SimpleNamespace(address='x',operations=control.OperationGate()),async_request_refresh=AsyncMock())
        async def fail(powers):
            c.data.tidal=[SimpleNamespace(power=40 if i<12 else 80) for i in range(24)]
            raise OSError('partial write')
        c.device.async_write_tidal_powers=fail
        first=Number(c)
        with self.assertRaises(OSError):await first.async_set_native_value(50)
        self.assertTrue(first.has_baseline)
        second=Number(c);c.device.async_write_tidal_powers=AsyncMock()
        await second.async_set_native_value(50)
        self.assertEqual(c.device.async_write_tidal_powers.await_args.args[0],[40]*24)
        await second.async_set_native_value(100)
        self.assertEqual(c.device.async_write_tidal_powers.await_args.args[0],[80]*24)
        self.assertFalse(second.has_baseline)
    async def test_missing_curve_refuses_before_write(self):
        Store.saved={};c=SimpleNamespace(hass=None,data=SimpleNamespace(tidal=[]),device=SimpleNamespace(address='x',operations=control.OperationGate(),async_write_tidal_powers=AsyncMock()))
        with self.assertRaises(ValueError):await Number(c).async_set_native_value(50)
        c.device.async_write_tidal_powers.assert_not_awaited()

class GenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_invalidates_owner_and_queued_old_work(self):
        gate=control.OperationGate();entered=asyncio.Event();release=asyncio.Event()
        async def owner():
            async with gate.hold():
                entered.set();await release.wait()
                with self.assertRaises(control.OperationSuperseded):gate.check()
        async def old_waiter():
            with self.assertRaises(control.OperationSuperseded):
                async with gate.hold():self.fail("stale operation ran")
        first=asyncio.create_task(owner());await entered.wait()
        old=asyncio.create_task(old_waiter());await asyncio.sleep(0)
        gate.request_stop();release.set();await asyncio.gather(first,old)
        async with gate.hold():gate.check()
    async def test_explicit_off_failure_is_visible(self):
        fan,c=FanTests().make_fan();c.device.async_write_named.side_effect=OSError('offline')
        with self.assertRaises(OSError):await fan.async_turn_off()
        self.assertIn('stop unconfirmed',c.device.command_error)
