"""Fan entity for the GTS L20 wave pump.

On/off and intensity map onto the pump's manual power. On new-firmware devices
(software_version > 4) the live power lives in a per-mode bank
``manual_power_<manual_mode>`` and only applies in manual mode, so setting
intensity here: (1) forces manual mode, (2) re-asserts the current waveform,
(3) writes that bank's power. See protocol.py for the field tables.

TODO(calibrate): the app displays current_power + 20 on sw > 4 and the real raw
ceiling may be ~80, not 100; we currently map the HA percentage 1:1 onto the
raw value. Off uses the dedicated 关机 command and requires heartbeat confirmation.
"""

from __future__ import annotations

from typing import Any
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GtsWavePumpCoordinator, protocol, storm
from .const import DOMAIN, POWER_DEFAULT_ON, POWER_MAX, POWER_MIN
from .entity import GtsWavePumpEntity

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_TIDAL_SCHEDULE = "set_tidal_schedule"
SERVICE_STORM_GAIN = "storm_gain"
_SEGMENT_SCHEMA = vol.Schema(
    {
        vol.Required("mode"): vol.In(protocol.MANUAL_MODES),
        vol.Required("power"): vol.All(vol.Coerce(int), vol.Range(min=0, max=POWER_MAX)),
        vol.Required("period"): vol.All(vol.Coerce(float), vol.Range(min=0, max=60)),
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the wave pump fan entity."""
    coordinator: GtsWavePumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GtsWavePumpFan(coordinator)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_TIDAL_SCHEDULE,
        {
            vol.Required("segments"): vol.All(
                cv.ensure_list,
                [_SEGMENT_SCHEMA],
                vol.Length(min=1, max=protocol.TIDAL_SEGMENTS),
            )
        },
        "async_set_tidal_schedule",
    )

    platform.async_register_entity_service(
        SERVICE_STORM_GAIN,
        {
            vol.Required("gain"): vol.All(vol.Coerce(float), vol.Range(min=100, max=200)),
            vol.Required("power_ceiling"): vol.All(vol.Coerce(int), vol.Range(min=1, max=99)),
            vol.Optional("wave_mode", default="daily"): vol.In(["daily", "surge", "turbulence", "pulse"]),
            vol.Optional("expected_run_mode", default="tide"): vol.In(["tide", "manual"]),
            vol.Required("clock_confirmed"): cv.boolean,
        },
        "async_storm_gain",
    )


class GtsWavePumpFan(GtsWavePumpEntity, FanEntity):
    """Represents the wave pump as a fan (on/off + intensity percentage)."""

    _attr_name = None  # primary entity: use the device name
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.device.address
        # Remembered run mode (manual_or_auto) before turn_off, so turn_on can
        # resume it — e.g. a feeding automation off/on keeps the pump in tide.
        self._run_mode_before_off: int | None = None

    @property
    def _software_version(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.software_version

    @property
    def _current_mode(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.current_mode

    @property
    def _current_power(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.current_power

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        if self._current_mode == protocol.MODE_OFF:
            return False
        power = self._current_power
        if power is None:
            return None
        return power > 0

    @property
    def extra_state_attributes(self):
        return {"recovery_required": self.coordinator.device.command_error is not None,
                "command_error": self.coordinator.device.command_error}

    @property
    def percentage(self) -> int | None:
        power = self._current_power
        if power is None:
            return None
        return max(POWER_MIN, min(POWER_MAX, power))

    @property
    def speed_count(self) -> int:
        return POWER_MAX - POWER_MIN

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage <= 0:
            await self._async_off()
            return
        await self._async_write_power(min(POWER_MAX, percentage))
        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        device = self.coordinator.device
        async with device.operations.hold():
            config, _ = await device.async_read_config(self._software_version)
            if config.get("manual_or_auto") == protocol.MANUAL_OR_AUTO_TIDE:
                await self._async_resume_tide()
            else:
                await self._async_write_power(POWER_DEFAULT_ON)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_off()

    async def _async_off(self) -> None:
        """A newer stop supersedes unfinished starts/curve writes."""
        device = self.coordinator.device
        device.operations.request_stop()
        try:
            async with device.operations.hold():
                await device.async_write_named("manual_mode", protocol.MODE_OFF, self._software_version)
                device.command_error = None
        except (Exception, asyncio.CancelledError):
            device.command_error = "stop unconfirmed; check pump"
            raise
        await self.coordinator.async_request_refresh()

    async def async_set_tidal_schedule(self, segments: list[dict]) -> None:
        """Service: write the tidal schedule (list of {mode, power, period_s})."""
        segs = [
            protocol.TidalSegment(
                mode=s["mode"],
                power=s["power"],
                period=protocol.seconds_to_period(s["period"]),
            )
            for s in segments
        ]
        device = self.coordinator.device
        async with device.operations.hold():
            overlay = self.coordinator.tidal_overlay
            if overlay is not None:
                await overlay._load_operation()
            if overlay is not None and overlay.has_baseline:
                raise ValueError("restore tidal intensity to 100% before replacing the schedule")
            await device.async_write_tidal(segs)
        await self.coordinator.async_request_refresh()

    async def async_storm_gain(self, gain: float, power_ceiling: int,
                               wave_mode: str = "daily", expected_run_mode: str = "tide",
                               clock_confirmed: bool = False) -> None:
        """Apply one bounded, transient setpoint; never rewrite the daily curve."""
        if clock_confirmed is not True:
            raise ValueError("confirm pump clock matches Home Assistant local time first")
        device = self.coordinator.device
        async with device.operations.hold():
            status = await device.async_get_status()
            sw = status.software_version
            if not protocol.uses_config_v2(sw):
                raise ValueError("verified per-wave config-v2 banks required")
            config, segments = await device.async_read_config(sw)
            expected = {"tide": protocol.MANUAL_OR_AUTO_TIDE,
                        "manual": protocol.MANUAL_OR_AUTO_MANUAL}.get(expected_run_mode)
            if (expected is None or config.get("manual_or_auto") != expected or
                    status.error_code or status.current_mode not in protocol.MANUAL_MODES or
                    status.current_power <= 0):
                raise ValueError("running mode changed, stopped, feeding or unconfirmed")
            overlay = self.coordinator.tidal_overlay
            if overlay is None:
                raise ValueError("tidal gain entity required")
            await overlay._load_operation()
            if overlay._pending is not None:
                raise ValueError("finish pending curve recovery before storm control")
            if len(segments) != 24:
                raise ValueError("complete current tidal schedule required")
            baseline = storm.daily_baseline(overlay._baseline,
                [segment.power for segment in segments], overlay._attr_native_value)
            # Resolve the hour after taking the operation lock, not at trigger time.
            hour = dt_util.now().hour
            target = storm.storm_target(baseline, hour, gain,
                                       overlay._attr_native_value, power_ceiling)
            segment = segments[hour]
            if (segment.mode not in protocol.MANUAL_MODES or type(segment.period) is not int
                    or not 0 <= segment.period <= 255):
                raise ValueError("current daily waveform/period cannot be used")
            modes = {"surge": 6, "turbulence": 4, "pulse": 2}
            mode = segment.mode if wave_mode == "daily" else modes.get(wave_mode)
            if mode is None:
                raise ValueError("unsupported storm waveform")
            power_field = protocol.power_field_name(mode, sw)
            period_field = protocol.period_field_name(mode, sw)
            may_affect_output = expected == protocol.MANUAL_OR_AUTO_MANUAL
            try:
                # Prime inactive banks BEFORE a waveform/manual switch can use them.
                await device.async_write_named(power_field, target.power, sw)
                await device.async_write_named(period_field, segment.period, sw)
                may_affect_output = True
                await device.async_write_named("manual_mode", mode, sw)
                await device.async_write_named("manual_or_auto", protocol.MANUAL_OR_AUTO_MANUAL, sw)
                observed = await device.async_get_status()
                if (observed.error_code or observed.current_mode != mode or
                        observed.current_power != target.power):
                    raise ValueError("storm setpoint not confirmed")
            except (Exception, asyncio.CancelledError):
                device.command_error = "storm gain preparation failed; mode switch not attempted"
                if may_affect_output:
                    try:
                        await device.async_emergency_stop(sw)
                        device.command_error = "storm gain failed; pump stopped, recovery required"
                    except Exception:
                        device.command_error = "storm gain failed; stop unconfirmed, check pump"
                        _LOGGER.exception(device.command_error)
                raise
            else:
                device.command_error = None
        await self.coordinator.async_request_refresh()

    async def _async_resume_tide(self) -> None:
        """Restart the pump into running tide mode from an off/关机 state.

        Setting manual_or_auto=tide alone does NOT restart a pump that was turned
        off (manual_mode 7, power 0): it must first be running (a manual waveform
        at some power) and then switched to tide, which picks up the schedule.
        """
        async with self.coordinator.device.operations.hold():
            sw = self._software_version
            mode = self._current_mode
            if mode not in protocol.MANUAL_MODES:
                mode = protocol.MANUAL_MODES[0]
            device = self.coordinator.device
            try:
                # 1) exit 关机 and start running (manual waveform at the default power)
                await device.async_write_named(
                    "manual_or_auto", protocol.MANUAL_OR_AUTO_MANUAL, sw
                )
                await device.async_write_named("manual_mode", mode, sw)
                await device.async_write_named(
                    protocol.power_field_name(mode, sw), POWER_DEFAULT_ON, sw
                )
                # 2) switch to tide so the tidal schedule resumes
                await device.async_write_named(
                    "manual_or_auto", protocol.MANUAL_OR_AUTO_TIDE, sw
                )
                status = await device.async_get_status()
                if status.error_code or status.current_mode in (protocol.MODE_OFF, protocol.MODE_FEED):
                    raise ValueError("running tide not confirmed by heartbeat")
            except (Exception, asyncio.CancelledError):
                device.command_error = "tide resume failed; checking safe stop"
                try:
                    await device.async_emergency_stop(sw)
                    device.command_error = "tide resume failed; pump stopped, recovery required"
                except Exception:
                    device.command_error = "tide resume failed; stop unconfirmed, check pump"
                    _LOGGER.exception(device.command_error)
                raise
            else:
                device.command_error = None

    async def _async_write_power(self, raw_power: int) -> None:
        """Force manual mode, re-assert the waveform, then set its bank power."""
        async with self.coordinator.device.operations.hold():
            sw = self._software_version
            mode = self._current_mode
            if mode not in protocol.MANUAL_MODES:
                mode = protocol.MANUAL_MODES[0]
            device = self.coordinator.device
            try:
                # 1) ensure manual mode so manual power actually applies
                await device.async_write_named(
                    "manual_or_auto", protocol.MANUAL_OR_AUTO_MANUAL, sw
                )
                # 2) re-assert the current waveform as the active manual mode
                await device.async_write_named("manual_mode", mode, sw)
                # 3) write that mode's power bank
                await device.async_write_named(
                    protocol.power_field_name(mode, sw), raw_power, sw
                )
            except (Exception, asyncio.CancelledError):
                device.command_error = "manual start failed; checking safe stop"
                try:
                    await device.async_emergency_stop(sw)
                except Exception:
                    _LOGGER.exception("Manual start failed and stop is unconfirmed")
                raise
            else:
                device.command_error = None
