"""Sensor entities: temperature, running flow mode, firmware version."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
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
    """Set up the sensor entities."""
    coordinator: GtsWavePumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            TemperatureSensor(coordinator),
            FlowModeSensor(coordinator),
            FirmwareSensor(coordinator),
        ]
    )


class TemperatureSensor(GtsWavePumpEntity, SensorEntity):
    """Pump core temperature (°C)."""

    _attr_translation_key = "temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_temperature"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.current_temp if self.coordinator.data else None


class FlowModeSensor(GtsWavePumpEntity, SensorEntity):
    """The currently running flow mode (constant/pulse/.../off)."""

    _attr_translation_key = "flow_mode"
    _attr_icon = "mdi:waves-arrow-right"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = sorted(set(protocol.MODE_NAMES.values()))

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_flow_mode"

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return protocol.MODE_NAMES.get(self.coordinator.data.current_mode)


class FirmwareSensor(GtsWavePumpEntity, SensorEntity):
    """Reported software_version (diagnostic)."""

    _attr_translation_key = "software_version"
    _attr_icon = "mdi:chip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_software_version"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.software_version if self.coordinator.data else None
