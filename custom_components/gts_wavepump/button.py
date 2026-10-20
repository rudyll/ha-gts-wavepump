"""Button entities: feed.

Feeding is a manual_mode value (5) in the app; pressing the feed button sets
manual_mode = 5 and the pump feeds for the configured feed_time.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GtsWavePumpCoordinator, protocol
from .const import DOMAIN
from .entity import GtsWavePumpEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button entities."""
    coordinator: GtsWavePumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FeedButton(coordinator)])


class FeedButton(GtsWavePumpEntity, ButtonEntity):
    """Feed the fish (sets manual_mode = feed)."""

    _attr_translation_key = "feed"
    _attr_icon = "mdi:fish"

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_feed"

    async def async_press(self) -> None:
        sw = self.coordinator.data.software_version if self.coordinator.data else None
        await self.coordinator.device.async_write_named(
            "manual_mode", protocol.MODE_FEED, sw
        )
        await self.coordinator.async_request_refresh()
