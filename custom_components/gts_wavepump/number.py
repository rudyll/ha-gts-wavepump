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

from . import power
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
    relative weather gain in App-display units (nonzero raw+20 on newer firmware).
    The daily maximum determines gain headroom; oversize gains fail before writing.
    Zeros and waveforms are unchanged. No peak clipping is used.
    Only effective in tide (auto) mode. Scaling is always computed from a
    stored baseline (the 100% curve), so it is drift-free and 100% restores the
    original exactly. Baseline + level persist across restarts.
    """

    _attr_translation_key = "tidal_intensity"
    _attr_icon = "mdi:waves-arrow-up"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 10
    _attr_native_max_value = 10000
    _attr_native_step = 1
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
            if baseline is not None and (not isinstance(baseline, list) or len(baseline) != 24 or
                    any(type(p) is not int or not 0 <= p <= 99 for p in baseline)):
                raise ValueError("invalid saved tidal baseline; manual recovery required")
            if saved.get("pending") is not None and baseline is None:
                raise ValueError("pending tidal write has no baseline; manual recovery required")
            if saved.get("gain_basis") not in (None, "app_percent"):
                raise ValueError("unknown persisted tidal gain units")
            if saved.get("gain_basis") is None and (value != 100 or saved.get("pending") is not None):
                raise ValueError("legacy raw gain requires explicit100% recovery before migration")
            self._baseline = baseline
            self._pending = saved.get("pending")
            self._attr_native_value = value
        elif self._attr_native_value != 100:
            raise ValueError("legacy gain without operation store requires explicit recovery")
        self._loaded = True

    @property
    def has_baseline(self):
        return self._baseline is not None or self._pending is not None

    @property
    def extra_restore_state_data(self) -> _IntensityExtraData:
        return _IntensityExtraData(self._baseline)

    def _gain_context(self):
        data = self.coordinator.data
        sw = getattr(data, "software_version", None) if data is not None else None
        if type(sw) is not int or sw < 0:
            raise ValueError("verified firmware required for App-based gain")
        base = self._baseline
        if base is None:
            if self._attr_native_value != 100 or data is None:
                raise ValueError("original baseline unavailable")
            base = [segment.power for segment in data.tidal]
        return base, sw

    @property
    def native_max_value(self):
        try:
            base, sw = self._gain_context()
            return power.gain_limit(base, sw)
        except ValueError:
            return 100

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        try:
            base, sw = self._gain_context()
            peak = max(power.display_power(v, sw) for v in base)
        except ValueError:
            peak = None
        return {"baseline_powers": self._baseline, "recovery_required": self._pending is not None,
                "gain_basis": "app_percent", "baseline_peak_app_percent": peak,
                "max_app_output_percent": (119 if getattr(self.coordinator.data, "software_version", None) > 4 else 99) if type(getattr(self.coordinator.data, "software_version", None)) is int else None, "baseline_power_unit": "raw_0_99"}

    async def async_set_native_value(self, value: float) -> None:
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                not self._attr_native_min_value <= value <= self._attr_native_max_value):
            raise ValueError("invalid tidal gain")
        async with self.coordinator.device.operations.hold():
            await self._load_operation()
            data = self.coordinator.data
            if data is None or len(data.tidal) != 24:
                raise ValueError("complete tidal curve required before editing")
            sw = getattr(data, "software_version", None)
            if type(sw) is not int or sw < 0:
                raise ValueError("verified firmware required")
            _, segments = await self.coordinator.device.async_read_config(sw)
            if len(segments) != 24:
                raise ValueError("complete fresh tidal curve required")
            observed = [segment.power for segment in segments]
            # Never recapture a partially applied curve after a failed write.
            if self._baseline is None:
                if self._attr_native_value != 100:
                    raise ValueError("missing full-strength baseline; manual recovery required")
                self._baseline = observed
            base, sw = self._gain_context()
            target = power.scale_curve(base, value, sw)
            if self._pending is None:
                expected = power.scale_curve(base, self._attr_native_value, sw)
                if observed != expected:
                    raise ValueError("external tidal curve edit; refusing to overwrite retained baseline")
            elif self._pending.get("value") != value:
                raise ValueError("retry pending gain before changing target")
            pending = {"value": float(value), "powers": target}
            await self._store.async_save({"baseline": self._baseline,
                "pending": pending, "value": self._attr_native_value, "gain_basis": "app_percent"})
            self._pending = pending
            self.async_write_ha_state()
            await self.coordinator.device.async_write_tidal_powers(target)
            baseline = None if value == 100 else self._baseline
            await self._store.async_save({"baseline": baseline, "pending": None,
                                          "value": float(value), "gain_basis": "app_percent"})
            self._baseline, self._pending = baseline, None
            self._attr_native_value = float(value)
            self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
