"""The GTS L20 wave pump (local BLE) integration."""

from __future__ import annotations

import asyncio
import logging

from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import protocol
from .const import (
    DOMAIN,
    RESPONSE_TIMEOUT,
    UART_NOTIFY_CHAR_UUID,
    UART_WRITE_CHAR_UUID,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.FAN, Platform.SWITCH]


class GtsWavePumpDevice:
    """Thin BLE wrapper: connect, subscribe to notifications, send frames.

    Commands are serialized through a lock; each command that expects a reply
    waits on a future resolved by the notification callback.
    """

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self._hass = hass
        self._address = address
        self._client: BleakClientWithServiceCache | None = None
        self._lock = asyncio.Lock()
        self._notify_future: asyncio.Future[bytes] | None = None

    @property
    def address(self) -> str:
        return self._address

    def _resolve_ble_device(self) -> BLEDevice:
        ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(
                f"GTS wave pump {self._address} not found; out of range or "
                "no BLE adapter/proxy in reach"
            )
        return ble_device

    async def _ensure_connected(self) -> BleakClientWithServiceCache:
        if self._client is not None and self._client.is_connected:
            return self._client
        ble_device = self._resolve_ble_device()
        self._client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            ble_device.name or self._address,
        )
        await self._client.start_notify(
            UART_NOTIFY_CHAR_UUID, self._notification_handler
        )
        return self._client

    def _notification_handler(self, _char, data: bytearray) -> None:
        if self._notify_future is not None and not self._notify_future.done():
            self._notify_future.set_result(bytes(data))

    async def _send(self, frame: bytes, *, expect_response: bool) -> bytes | None:
        async with self._lock:
            client = await self._ensure_connected()
            if expect_response:
                loop = asyncio.get_running_loop()
                self._notify_future = loop.create_future()
            else:
                self._notify_future = None
            try:
                await client.write_gatt_char(
                    UART_WRITE_CHAR_UUID, frame, response=False
                )
                if not expect_response:
                    return None
                return await asyncio.wait_for(
                    self._notify_future, timeout=RESPONSE_TIMEOUT
                )
            except asyncio.TimeoutError as err:
                raise UpdateFailed("timed out waiting for pump response") from err
            finally:
                self._notify_future = None

    async def async_get_status(self) -> protocol.HeartbeatStatus:
        """Poll the heartbeat (interface 3) and return decoded status."""
        response = await self._send(protocol.build_heartbeat(), expect_response=True)
        assert response is not None
        return protocol.parse_heartbeat(response)

    async def async_write_field(self, field: int, value: int) -> None:
        """Write a single config field (interface 1)."""
        await self._send(
            protocol.build_write_field(field, value), expect_response=True
        )

    async def async_disconnect(self) -> None:
        if self._client is not None and self._client.is_connected:
            try:
                await self._client.stop_notify(UART_NOTIFY_CHAR_UUID)
            except Exception:  # noqa: BLE001 - best effort on teardown
                pass
            await self._client.disconnect()
        self._client = None


class GtsWavePumpCoordinator(DataUpdateCoordinator[protocol.HeartbeatStatus]):
    """Polls pump status and exposes the shared :class:`GtsWavePumpDevice`."""

    def __init__(self, hass: HomeAssistant, device: GtsWavePumpDevice) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {device.address}",
            update_interval=UPDATE_INTERVAL,
        )
        self.device = device

    async def _async_update_data(self) -> protocol.HeartbeatStatus:
        try:
            return await self.device.async_get_status()
        except protocol.InvalidFrameError as err:
            raise UpdateFailed(f"malformed response: {err}") from err


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GTS wave pump from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    device = GtsWavePumpDevice(hass, address)
    coordinator = GtsWavePumpCoordinator(hass, device)

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        raise
    except UpdateFailed as err:
        raise ConfigEntryNotReady(str(err)) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: GtsWavePumpCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.device.async_disconnect()
    return unloaded
