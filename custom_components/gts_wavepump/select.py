"""Select entities: water-flow waveform and run mode (manual/tide)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.const import EntityCategory

from . import GtsWavePumpCoordinator, protocol
from .const import DOMAIN, MASTER_SLAVE_OPTIONS, RUN_MODE_OPTIONS, WATER_MODE_OPTIONS
from .entity import GtsWavePumpEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select entities."""
    coordinator: GtsWavePumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WaterModeSelect(coordinator),
            RunModeSelect(coordinator),
            MasterSlaveSelect(coordinator),
        ]
    )


class WaterModeSelect(GtsWavePumpEntity, SelectEntity):
    """The manual waveform (constant/pulse/sine/turbulence/surge)."""

    _attr_translation_key = "water_mode"
    _attr_icon = "mdi:waves"
    _value_to_slug = WATER_MODE_OPTIONS
    _slug_to_value = {slug: value for value, slug in WATER_MODE_OPTIONS.items()}
    _attr_options = list(WATER_MODE_OPTIONS.values())

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_water_mode"

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        if data is None:
            return None
        # Prefer the stored manual_mode; fall back to the running current_mode.
        value = data.config.get("manual_mode", data.current_mode)
        return self._value_to_slug.get(value)

    async def async_select_option(self, option: str) -> None:
        value = self._slug_to_value[option]
        sw = self.coordinator.data.software_version if self.coordinator.data else None
        # Selecting a waveform implies manual mode.
        await self.coordinator.device.async_write_named(
            "manual_or_auto", protocol.MANUAL_OR_AUTO_MANUAL, sw
        )
        await self.coordinator.device.async_write_named("manual_mode", value, sw)
        await self.coordinator.async_request_refresh()


class RunModeSelect(GtsWavePumpEntity, SelectEntity):
    """Manual vs tide (auto) run mode."""

    _attr_translation_key = "run_mode"
    _attr_icon = "mdi:cog-transfer"
    _value_to_slug = RUN_MODE_OPTIONS
    _slug_to_value = {slug: value for value, slug in RUN_MODE_OPTIONS.items()}
    _attr_options = list(RUN_MODE_OPTIONS.values())

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_run_mode"

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        if data is None:
            return None
        return self._value_to_slug.get(data.config.get("manual_or_auto"))

    async def async_select_option(self, option: str) -> None:
        value = self._slug_to_value[option]
        sw = self.coordinator.data.software_version if self.coordinator.data else None
        await self.coordinator.device.async_write_named("manual_or_auto", value, sw)
        await self.coordinator.async_request_refresh()


class MasterSlaveSelect(GtsWavePumpEntity, SelectEntity):
    """Master (main) vs slave role, for multi-pump sync."""

    _attr_translation_key = "master_slave"
    _attr_icon = "mdi:transit-connection-variant"
    _attr_entity_category = EntityCategory.CONFIG
    _value_to_slug = MASTER_SLAVE_OPTIONS
    _slug_to_value = {slug: value for value, slug in MASTER_SLAVE_OPTIONS.items()}
    _attr_options = list(MASTER_SLAVE_OPTIONS.values())

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_master_slave"

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        if data is None:
            return None
        return self._value_to_slug.get(data.config.get("master_or_slave"))

    async def async_select_option(self, option: str) -> None:
        value = self._slug_to_value[option]
        sw = self.coordinator.data.software_version if self.coordinator.data else None
        await self.coordinator.device.async_write_named("master_or_slave", value, sw)
        await self.coordinator.async_request_refresh()
