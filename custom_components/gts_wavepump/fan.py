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

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GtsWavePumpCoordinator, protocol
from .const import DOMAIN, POWER_DEFAULT_ON, POWER_MAX, POWER_MIN
from .entity import GtsWavePumpEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the wave pump fan entity."""
    coordinator: GtsWavePumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GtsWavePumpFan(coordinator)])


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
            await self._async_write_power(0)
            return
        await self._async_write_power(min(POWER_MAX, percentage))

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        await self._async_write_power(
            percentage if percentage is not None else POWER_DEFAULT_ON
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        # TODO(calibrate): use the app's dedicated 关机 command instead of power 0.
        await self._async_write_power(0)

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
