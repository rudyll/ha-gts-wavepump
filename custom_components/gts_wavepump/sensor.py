"""Sensor entities: temperature, running flow mode, firmware version."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
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
            TidalScheduleSensor(coordinator),
            FeedScheduleSensor(coordinator),
            SignalStrengthSensor(coordinator),
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


class TidalScheduleSensor(GtsWavePumpEntity, SensorEntity):
    """Read-only view of the 24-segment tidal schedule (diagnostic).

    State is the segment count; the full schedule is in the `schedule`
    attribute as [{hour, mode, power, period_s}, ...].
    """

    _attr_translation_key = "tidal_schedule"
    _attr_icon = "mdi:chart-timeline-variant"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_tidal_schedule"

    @property
    def native_value(self) -> int | None:
        return len(self.coordinator.data.tidal) if self.coordinator.data else None

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        if self.coordinator.data is None:
            return None
        return {
            "schedule": [
                {
                    "hour": i,
                    "mode": protocol.MODE_NAMES.get(seg.mode, seg.mode),
                    "power": seg.power,
                    "period_s": protocol.period_to_seconds(seg.period),
                }
                for i, seg in enumerate(self.coordinator.data.tidal)
            ]
        }


class FeedScheduleSensor(GtsWavePumpEntity, SensorEntity):
    """Scheduled-feeding slots (read-only; enable with the Feed slot switches).

    State is the number of enabled slots; the `slots` attribute lists each
    slot's enabled flag, time (HH:MM) and duration (minutes).
    """

    _attr_translation_key = "feed_schedule"
    _attr_icon = "mdi:calendar-clock"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_feed_schedule"

    def _slots(self) -> list[dict[str, object]]:
        cfg = self.coordinator.data.config if self.coordinator.data else {}
        slots = []
        for s in range(1, protocol.FEED_SLOTS + 1):
            hour = cfg.get(f"feed{s}_hour")
            minute = cfg.get(f"feed{s}_minute")
            time = (
                f"{hour:02d}:{minute:02d}"
                if isinstance(hour, int) and isinstance(minute, int) and hour < 24
                else None
            )
            slots.append(
                {
                    "slot": s,
                    "enabled": cfg.get(f"feed{s}_enable") == 1,
                    "time": time,
                    "duration_min": cfg.get(f"feed{s}_duration"),
                }
            )
        return slots

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return sum(1 for s in self._slots() if s["enabled"])

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        if self.coordinator.data is None:
            return None
        return {"slots": self._slots()}


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


class SignalStrengthSensor(GtsWavePumpEntity, SensorEntity):
    """BLE signal strength (RSSI) from the nearest adapter/proxy (diagnostic).

    The `source` attribute names the Bluetooth adapter or ESP proxy that last
    heard the pump — useful to tell whether a proxy is in range.
    """

    _attr_translation_key = "signal_strength"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_signal_strength"

    def _service_info(self):
        return bluetooth.async_last_service_info(
            self.hass, self.coordinator.device.address, connectable=True
        )

    @property
    def native_value(self) -> int | None:
        info = self._service_info()
        return info.rssi if info else None

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        info = self._service_info()
        if info is None:
            return None
        return {"source": info.source}
