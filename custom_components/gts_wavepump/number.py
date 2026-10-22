"""Number entities: period, feed time, channel, and tidal-intensity overlay."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData

from . import GtsWavePumpCoordinator, protocol
from .const import (
    CHANNEL_MAX,
    CHANNEL_MIN,
    DOMAIN,
    FEED_TIME_MAX,
    FEED_TIME_MIN,
    PERIOD_RAW_MAX,
    PERIOD_RAW_MIN,
    POWER_MAX,
    POWER_MIN,
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
            TidalIntensityNumber(coordinator),
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
    """Feed duration in minutes (the app's 即时喂食 "喂食时间", used by Feed)."""

    _attr_translation_key = "feed_time"
    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
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


@dataclass
class _IntensityExtraData(ExtraStoredData):
    """Persisted baseline (24 full-strength segment powers) for the overlay."""

    baseline: list[int] | None

    def as_dict(self) -> dict:
        return {"baseline": self.baseline}


class TidalIntensityNumber(GtsWavePumpEntity, RestoreNumber):
    """Overlay that scales the whole tidal (auto) curve by a percentage.

    For coral acclimation: lower the whole day's flow proportionally and raise
    it back toward 100%, WITHOUT changing each hour's waveform or relative
    power. Only effective in tide (auto) mode. Scaling is always computed from a
    stored baseline (the 100% curve), so it is drift-free and 100% restores the
    original exactly. Baseline + level persist across restarts.
    """

    _attr_translation_key = "tidal_intensity"
    _attr_icon = "mdi:waves-arrow-up"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 10
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_tidal_intensity"
        self._attr_native_value = 100.0
        self._baseline: list[int] | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_number_data()) and (
            last.native_value is not None
        ):
            self._attr_native_value = last.native_value
        if (extra := await self.async_get_last_extra_data()) is not None:
            baseline = extra.as_dict().get("baseline")
            if isinstance(baseline, list):
                self._baseline = [int(p) for p in baseline]

    @property
    def extra_restore_state_data(self) -> _IntensityExtraData:
        return _IntensityExtraData(self._baseline)

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        return {"baseline_powers": self._baseline}

    async def async_set_native_value(self, value: float) -> None:
        data = self.coordinator.data
        if data is None or not data.tidal:
            return  # no tidal curve read yet
        current = [seg.power for seg in data.tidal]
        # (Re)capture the baseline only when the device currently holds the full
        # curve (level at 100%, or none stored) — never from a scaled curve.
        if self._baseline is None or (self._attr_native_value or 0) >= 100:
            self._baseline = current
        factor = value / 100.0
        scaled_powers = [
            min(POWER_MAX, max(POWER_MIN, round(base * factor)))
            for base in self._baseline
        ]
        await self.coordinator.device.async_write_tidal_powers(scaled_powers)
        self._attr_native_value = float(value)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
