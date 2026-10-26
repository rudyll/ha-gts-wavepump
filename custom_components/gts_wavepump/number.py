"""Number entities: period, feed time, channel, and tidal-intensity overlay."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData
from homeassistant.helpers.storage import Store

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

    100% is the existing daily curve; below100 attenuates it and above100 adds
    relative weather gain. Each result is bounded by the existing raw POWER_MAX;
    clipped peaks need not preserve relative power. Waveforms are unchanged.
    Only effective in tide (auto) mode. Scaling is always computed from a
    stored baseline (the 100% curve), so it is drift-free and 100% restores the
    original exactly. Baseline + level persist across restarts.
    """

    _attr_translation_key = "tidal_intensity"
    _attr_icon = "mdi:waves-arrow-up"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 10
    _attr_native_max_value = 200
    _attr_native_step = 5
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_tidal_intensity"
        self._attr_native_value = 100.0
        self._baseline: list[int] | None = None
        self._pending = None
        self._store = Store(coordinator.hass, 1, f"gts_wavepump.{coordinator.device.address}.intensity")
        self._loaded = False
        coordinator.tidal_overlay = self

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
        await self._load_operation()

    async def _load_operation(self):
        if self._loaded:
            return
        saved = await self._store.async_load()
        if saved is not None:
            value = saved.get("value", 100)
            if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                    not self._attr_native_min_value <= value <= self._attr_native_max_value):
                raise ValueError("invalid saved tidal gain; manual recovery required")
            baseline = saved.get("baseline")
            if baseline is not None and (len(baseline) != 24 or
                    any(type(p) is not int or not 0 <= p <= 255 for p in baseline)):
                raise ValueError("invalid saved tidal baseline; manual recovery required")
            if saved.get("pending") is not None and baseline is None:
                raise ValueError("pending tidal write has no baseline; manual recovery required")
            self._baseline = baseline
            self._pending = saved.get("pending")
            self._attr_native_value = value
        self._loaded = True

    @property
    def has_baseline(self):
        return self._baseline is not None or self._pending is not None

    @property
    def extra_restore_state_data(self) -> _IntensityExtraData:
        return _IntensityExtraData(self._baseline)

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        return {"baseline_powers": self._baseline, "recovery_required": self._pending is not None}

    async def async_set_native_value(self, value: float) -> None:
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                not self._attr_native_min_value <= value <= self._attr_native_max_value):
            raise ValueError("tidal gain must be between 10 and 200")
        async with self.coordinator.device.operations.hold():
            await self._load_operation()
            data = self.coordinator.data
            if data is None or len(data.tidal) != 24:
                raise ValueError("complete tidal curve required before editing")
            # Never recapture a partially applied curve after a failed write.
            if self._baseline is None:
                if self._attr_native_value != 100:
                    raise ValueError("missing full-strength baseline; manual recovery required")
                self._baseline = [seg.power for seg in data.tidal]
            target = list(self._baseline) if value == 100 else [min(POWER_MAX, max(POWER_MIN, round(p * value / 100)))
                      for p in self._baseline]
            pending = {"value": float(value), "powers": target}
            await self._store.async_save({"baseline": self._baseline,
                "pending": pending, "value": self._attr_native_value})
            self._pending = pending
            self.async_write_ha_state()
            await self.coordinator.device.async_write_tidal_powers(target)
            baseline = None if value == 100 else self._baseline
            await self._store.async_save({"baseline": baseline, "pending": None,
                                          "value": float(value)})
            self._baseline, self._pending = baseline, None
            self._attr_native_value = float(value)
            self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
