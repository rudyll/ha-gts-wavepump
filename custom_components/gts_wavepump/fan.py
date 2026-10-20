"""Fan entity for the GTS L20 wave pump.

The pump's on/off and intensity are both mapped onto the ``manual_power``
field (interface 1, field 4): 0 == off, 1..100 == running intensity.

TODO(calibrate): confirm the real manual_power range/unit and whether a
dedicated on/off (e.g. master_or_slave / manual_or_auto) exists. Until then we
treat power 0 as off and 1-100 as the running percentage. See §10 of the
protocol doc.
"""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import GtsWavePumpCoordinator, protocol
from .const import DOMAIN, POWER_DEFAULT_ON, POWER_MAX, POWER_MIN
from .entity import GtsWavePumpEntity

# (min, max) of the raw manual_power value; min excludes 0 (which is "off").
_POWER_RANGE = (POWER_MIN + 1, POWER_MAX)


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
        if power <= 0:
            return 0
        return ranged_value_to_percentage(_POWER_RANGE, power)

    @property
    def speed_count(self) -> int:
        return POWER_MAX - POWER_MIN

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self._async_set_power(0)
            return
        power = math.ceil(percentage_to_ranged_value(_POWER_RANGE, percentage))
        await self._async_set_power(power)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        await self._async_set_power(POWER_DEFAULT_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set_power(0)

    async def _async_set_power(self, power: int) -> None:
        await self.coordinator.device.async_write_field(
            protocol.FIELD_MANUAL_POWER, power
        )
        await self.coordinator.async_request_refresh()
