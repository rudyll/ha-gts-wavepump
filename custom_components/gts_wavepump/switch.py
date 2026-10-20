"""Switch entity for the wave pump's forward/reverse (field 79).

The heartbeat (interface 3) does not report ``forward_or_reverse``, so this
switch is optimistic: it writes the field and remembers the requested state.

TODO(calibrate): confirm the value semantics (which value is forward vs
reverse) and, ideally, read it back via the read-all-config request
(interface 2) so the state can be authoritative instead of assumed.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GtsWavePumpCoordinator
from .const import DOMAIN, REVERSE_OFF, REVERSE_ON
from .entity import GtsWavePumpEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the forward/reverse switch."""
    coordinator: GtsWavePumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GtsWavePumpReverseSwitch(coordinator)])


class GtsWavePumpReverseSwitch(GtsWavePumpEntity, SwitchEntity):
    """Toggles forward_or_reverse (field 79). Optimistic state."""

    _attr_translation_key = "reverse"
    _attr_assumed_state = True

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_reverse"
        self._is_on = False

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set_reverse(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set_reverse(False)

    async def _async_set_reverse(self, reverse: bool) -> None:
        value = REVERSE_ON if reverse else REVERSE_OFF
        sw = (
            self.coordinator.data.software_version
            if self.coordinator.data is not None
            else None
        )
        await self.coordinator.device.async_write_named(
            "forward_or_reverse", value, sw
        )
        self._is_on = reverse
        self.async_write_ha_state()
