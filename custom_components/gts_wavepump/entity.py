"""Shared base entity for GTS wave pump."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GtsWavePumpCoordinator
from .const import DOMAIN


class GtsWavePumpEntity(CoordinatorEntity[GtsWavePumpCoordinator]):
    """Base class wiring device info and availability to the coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GtsWavePumpCoordinator) -> None:
        super().__init__(coordinator)
        address = coordinator.device.address
        self._attr_device_info = DeviceInfo(
            connections={("bluetooth", address)},
            identifiers={(DOMAIN, address)},
            manufacturer="GTS (Goutousha)",
            model=f"{coordinator.model} Wave Pump",
            name=coordinator.device_name,
        )
