"""Fan entity for the GTS L20 wave pump.

On/off and intensity map onto the pump's manual power. On new-firmware devices
(software_version > 4) the live power lives in a per-mode bank
``manual_power_<manual_mode>`` and only applies in manual mode, so setting
intensity here: (1) forces manual mode, (2) re-asserts the current waveform,
(3) writes that bank's power. See protocol.py for the field tables.

TODO(calibrate): the app displays current_power + 20 on sw > 4 and the real raw
ceiling may be ~80, not 100; we currently map the HA percentage 1:1 onto the
raw value. Also "off" here is power 0, not the app's dedicated 关机 command.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GtsWavePumpCoordinator, protocol
from .const import DOMAIN, POWER_DEFAULT_ON, POWER_MAX, POWER_MIN
from .entity import GtsWavePumpEntity

SERVICE_SET_TIDAL_SCHEDULE = "set_tidal_schedule"
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

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if percentage is not None:
            await self._async_write_power(percentage)
            return
        # Plain "turn on": resume the run mode the pump had before it was turned
        # off — so a feeding off/on cycle returns to tide instead of forcing
        # manual. Falls back to manual at the default power if it wasn't tide.
        run_mode = self._run_mode_before_off
        if run_mode is None and self.coordinator.data is not None:
            # The pump retains its run mode across off/feed and HA reloads.
            run_mode = self.coordinator.data.config.get("manual_or_auto")
        if run_mode == protocol.MANUAL_OR_AUTO_TIDE:
            await self._async_resume_tide()
            return
        await self._async_write_power(POWER_DEFAULT_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_off()

    async def _async_off(self) -> None:
        """Turn the pump off with the app's dedicated 关机 (manual_mode = 7).

        Remembers the current run mode so a following turn_on can resume it.
        """
        if self.coordinator.data is not None:
            self._run_mode_before_off = self.coordinator.data.config.get(
                "manual_or_auto"
            )
        await self.coordinator.device.async_write_named(
            "manual_mode", protocol.MODE_OFF, self._software_version
        )
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
        await self.coordinator.device.async_write_tidal(segs)
        await self.coordinator.async_request_refresh()

    async def _async_resume_tide(self) -> None:
        """Restart the pump into running tide mode from an off/关机 state.

        Setting manual_or_auto=tide alone does NOT restart a pump that was turned
        off (manual_mode 7, power 0): it must first be running (a manual waveform
        at some power) and then switched to tide, which picks up the schedule.
        """
        sw = self._software_version
        mode = self._current_mode
        if mode not in protocol.MANUAL_MODES:
            mode = protocol.MANUAL_MODES[0]
        device = self.coordinator.device
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
        await self.coordinator.async_request_refresh()

    async def _async_write_power(self, raw_power: int) -> None:
        """Force manual mode, re-assert the waveform, then set its bank power."""
        sw = self._software_version
        mode = self._current_mode
        if mode not in protocol.MANUAL_MODES:
            mode = protocol.MANUAL_MODES[0]
        device = self.coordinator.device
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
        await self.coordinator.async_request_refresh()
