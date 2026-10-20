"""Number entities: manual period (seconds) and communication channel."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GtsWavePumpCoordinator, protocol
from .const import (
    CHANNEL_MAX,
    CHANNEL_MIN,
    DOMAIN,
    FEED_TIME_MAX,
    FEED_TIME_MIN,
    PERIOD_RAW_MAX,
    PERIOD_RAW_MIN,
)
from .entity import GtsWavePumpEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number entities."""
    coordinator: GtsWavePumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PeriodNumber(coordinator),
            FeedTimeNumber(coordinator),
            ChannelNumber(coordinator),
        ]
    )


class PeriodNumber(GtsWavePumpEntity, NumberEntity):
    """Manual wave period, in seconds, for the active waveform bank."""

    _attr_translation_key = "period"
    _attr_icon = "mdi:sine-wave"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_native_min_value = PERIOD_RAW_MIN / protocol.PERIOD_SCALE
    _attr_native_max_value = PERIOD_RAW_MAX / protocol.PERIOD_SCALE
    _attr_native_step = 1 / protocol.PERIOD_SCALE
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_period"

    def _active_mode(self) -> int | None:
        data = self.coordinator.data
        if data is None:
            return None
        return data.config.get("manual_mode", data.current_mode)

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data is None:
            return None
        field = protocol.period_field_name(self._active_mode(), data.software_version)
        raw = data.config.get(field, data.current_period)
        if raw is None:
            return None
        return protocol.period_to_seconds(raw)

    async def async_set_native_value(self, value: float) -> None:
        data = self.coordinator.data
        sw = data.software_version if data else None
        field = protocol.period_field_name(self._active_mode(), sw)
        await self.coordinator.device.async_write_named(
            field, protocol.seconds_to_period(value), sw
        )
        await self.coordinator.async_request_refresh()


class FeedTimeNumber(GtsWavePumpEntity, NumberEntity):
    """Feed duration in seconds (used by the Feed button)."""

    _attr_translation_key = "feed_time"
    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_native_min_value = FEED_TIME_MIN
    _attr_native_max_value = FEED_TIME_MAX
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_feed_time"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data is None:
            return None
        value = data.config.get("feed_time")
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        sw = self.coordinator.data.software_version if self.coordinator.data else None
        await self.coordinator.device.async_write_named("feed_time", int(value), sw)
        await self.coordinator.async_request_refresh()


class ChannelNumber(GtsWavePumpEntity, NumberEntity):
    """Communication channel (diagnostic)."""

    _attr_translation_key = "channel"
    _attr_icon = "mdi:access-point"
    _attr_native_min_value = CHANNEL_MIN
    _attr_native_max_value = CHANNEL_MAX
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_channel"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data is None:
            return None
        value = data.config.get("communication_channel")
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        sw = self.coordinator.data.software_version if self.coordinator.data else None
        await self.coordinator.device.async_write_named(
            "communication_channel", int(value), sw
        )
        await self.coordinator.async_request_refresh()
