"""Switch entities: the controller light."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GtsWavePumpCoordinator, protocol
from .const import DOMAIN, LIGHT_OFF, LIGHT_ON
from .entity import GtsWavePumpEntity

# NOTE: forward_or_reverse (Tee 1=direct/2=reverse) exists in the protocol but
# the L20 firmware removed the reverse feature (changelog: 取消…反转功能) and the
# app does not expose it, so no reverse switch is created. Re-add for GTS models
# that still support it.


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch entities."""
    coordinator: GtsWavePumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = [LightSwitch(coordinator)]
    for slot in range(1, protocol.FEED_SLOTS + 1):
        entities.append(FeedSlotSwitch(coordinator, slot))
    async_add_entities(entities)


class _ConfigSwitch(GtsWavePumpEntity, SwitchEntity):
    """A switch backed by a single config field, read from the config poll."""

    _field: str
    _on_value: int
    _off_value: int

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if data is None:
            return None
        value = data.config.get(self._field)
        if value is None:
            return None
        return value == self._on_value

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_write(self._on_value)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_write(self._off_value)

    async def _async_write(self, value: int) -> None:
        sw = self.coordinator.data.software_version if self.coordinator.data else None
        await self.coordinator.device.async_write_named(self._field, value, sw)
        await self.coordinator.async_request_refresh()


class LightSwitch(_ConfigSwitch):
    """Controller indicator light (light_on: 2=on, 1=off).

    Writes go through the shared named-write path, which uses config-v2 on
    software_version > 10 devices (the only path the light responds to).
    """

    _attr_translation_key = "light"
    _attr_icon = "mdi:lightbulb"
    _field = "light_on"
    _on_value = LIGHT_ON
    _off_value = LIGHT_OFF

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_light"


class FeedSlotSwitch(_ConfigSwitch):
    """Enable/disable one scheduled-feeding slot (定时组). Verified on hardware."""

    _attr_icon = "mdi:fish"
    _on_value = 1
    _off_value = 0
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: GtsWavePumpCoordinator, slot: int) -> None:
        super().__init__(coordinator)
        self._slot = slot
        self._field = f"feed{slot}_enable"
        self._attr_translation_key = f"feed_slot_{slot}"
        self._attr_unique_id = f"{coordinator.device.address}_feed{slot}_enable"

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """This slot's feeding time (HH:MM) and duration (minutes)."""
        data = self.coordinator.data
        if data is None:
            return None
        cfg = data.config
        hour = cfg.get(f"feed{self._slot}_hour")
        minute = cfg.get(f"feed{self._slot}_minute")
        time = (
            f"{hour:02d}:{minute:02d}"
            if isinstance(hour, int) and isinstance(minute, int) and hour < 24
            else None
        )
        return {"time": time, "duration_min": cfg.get(f"feed{self._slot}_duration")}
