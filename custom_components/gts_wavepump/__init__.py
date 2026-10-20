"""The GTS L20 wave pump (local BLE) integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

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
    NOTIFY_CHAR_CANDIDATES,
    RESPONSE_TIMEOUT,
    UPDATE_INTERVAL,
    WRITE_CHAR_CANDIDATES,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.FAN,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SENSOR,
]


@dataclass
class PumpState:
    """Combined pump state: the latest heartbeat plus the full config read.

    Heartbeat fields are exposed as passthrough properties so entities can read
    ``state.current_power`` etc., while ``config`` holds the parsed read-all
    (manual_or_auto, manual_mode, per-mode banks, light, channel, ...).
    """

    heartbeat: "protocol.HeartbeatStatus"
    config: dict[str, int] = field(default_factory=dict)

    @property
    def software_version(self) -> int:
        return self.heartbeat.software_version

    @property
    def current_mode(self) -> int:
        return self.heartbeat.current_mode

    @property
    def current_power(self) -> int:
        return self.heartbeat.current_power

    @property
    def current_temp(self) -> int:
        return self.heartbeat.current_temp

    @property
    def current_period(self) -> int:
        return self.heartbeat.current_period


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
        self._write_char: str | None = None
        self._notify_char: str | None = None

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
        self._write_char, self._notify_char = self._resolve_characteristics(
            self._client
        )
        await self._client.start_notify(
            self._notify_char, self._notification_handler
        )
        return self._client

    def _resolve_characteristics(
        self, client: BleakClientWithServiceCache
    ) -> tuple[str, str]:
        """Pick write/notify characteristics by their real GATT properties.

        The reverse-engineered UUIDs did not match hardware (the documented
        notify characteristic lacked the notify property), so resolve against
        the live GATT table and the candidate lists instead of trusting fixed
        UUIDs. The full table is logged at debug for calibration.
        """
        by_uuid: dict[str, object] = {}
        for service in client.services:
            for char in service.characteristics:
                by_uuid[char.uuid.lower()] = char
                _LOGGER.debug(
                    "GATT service=%s char=%s props=%s",
                    service.uuid,
                    char.uuid,
                    char.properties,
                )

        def _pick(candidates: list[str], wanted: set[str], exclude: str | None):
            for uuid in candidates:
                char = by_uuid.get(uuid.lower())
                if (
                    char is not None
                    and char.uuid.lower() != exclude
                    and wanted & set(char.properties)
                ):
                    return char.uuid
            return None

        notify = _pick(NOTIFY_CHAR_CANDIDATES, {"notify", "indicate"}, None)
        write = _pick(
            WRITE_CHAR_CANDIDATES,
            {"write", "write-without-response"},
            notify.lower() if notify else None,
        )
        if notify is None or write is None:
            table = [
                f"{c.uuid}({'/'.join(c.properties)})" for c in by_uuid.values()
            ]
            _LOGGER.warning(
                "Could not resolve UART characteristics (write=%s notify=%s). "
                "GATT table: %s",
                write,
                notify,
                ", ".join(table),
            )
            raise UpdateFailed("no usable write/notify characteristic found")
        _LOGGER.debug("Using write=%s notify=%s", write, notify)
        return write, notify

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
                    self._write_char, frame, response=False
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

    async def async_read_config(self, software_version: int | None) -> dict[str, int]:
        """Read the full config (interface 2) and return parsed fields."""
        response = await self._send(protocol.build_read_config(), expect_response=True)
        assert response is not None
        # Temporary diagnostic: full raw config bytes, to locate unknown fields.
        _LOGGER.debug("config_raw=%s", list(response))
        return protocol.parse_config(response, software_version)

    async def async_write_field(self, field: int, value: int) -> None:
        """Write a single config field by raw interface-1 id."""
        await self._send(
            protocol.build_write_field(field, value), expect_response=True
        )

    async def async_write_named(
        self, name: str, value: int, software_version: int | None
    ) -> None:
        """Write a named config field, using the path the app uses.

        software_version > 10 devices take config-v2 writes (interface 10);
        earlier firmware takes single-field interface-1 writes. Verified on
        hardware that the light only responds to the config-v2 path.
        """
        if protocol.uses_config_v2(software_version):
            frame = protocol.build_config_v2_write(name, value)
        else:
            frame = protocol.build_config_write(name, value, software_version)
        await self._send(frame, expect_response=True)

    async def async_disconnect(self) -> None:
        if self._client is not None and self._client.is_connected:
            if self._notify_char is not None:
                try:
                    await self._client.stop_notify(self._notify_char)
                except Exception:  # noqa: BLE001 - best effort on teardown
                    pass
            await self._client.disconnect()
        self._client = None


class GtsWavePumpCoordinator(DataUpdateCoordinator[PumpState]):
    """Polls pump status and exposes the shared :class:`GtsWavePumpDevice`."""

    def __init__(self, hass: HomeAssistant, device: GtsWavePumpDevice) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {device.address}",
            update_interval=UPDATE_INTERVAL,
        )
        self.device = device

    async def _async_update_data(self) -> PumpState:
        try:
            status = await self.device.async_get_status()
        except protocol.InvalidFrameError as err:
            raise UpdateFailed(f"malformed response: {err}") from err
        # Config read is best-effort: a transient failure keeps the last config
        # rather than failing the whole update (heartbeat is the primary data).
        config: dict[str, int] = self.data.config if self.data else {}
        try:
            config = await self.device.async_read_config(status.software_version)
        except (protocol.InvalidFrameError, UpdateFailed) as err:
            _LOGGER.debug("config read failed, keeping last: %s", err)
        _LOGGER.debug(
            "heartbeat sw=%s mode=%s power=%s temp=%sC period=%s err=%s | config=%s",
            status.software_version,
            status.current_mode,
            status.current_power,
            status.current_temp,
            status.current_period,
            status.error_code,
            config,
        )
        return PumpState(heartbeat=status, config=config)


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
