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
from .control import OperationGate, OperationSuperseded, serialized
from .const import (
    DOMAIN,
    NOTIFY_CHAR_CANDIDATES,
    RESPONSE_TIMEOUT,
    UPDATE_INTERVAL,
    WRITE_CHAR_CANDIDATES,
    model_from_name,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.FAN,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BUTTON,
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
    tidal: "list[protocol.TidalSegment]" = field(default_factory=list)

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
        self.operations = OperationGate()
        self.command_error: str | None = None
        self._request_frame: bytes | None = None
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
        if self._notify_future is None or self._notify_future.done():
            return
        try:
            interface, payload = protocol.parse_response(data)
        except protocol.InvalidFrameError:
            return
        request = self._request_frame
        if request is None or interface != request[1]:
            return
        if interface == protocol.IFACE_WRITE_CONFIG and payload != request[2:-1]:
            return
        # V2 does not have a proven per-request ACK identifier. All writes are
        # additionally read back; a generic notification alone is not success.
        self._notify_future.set_result(bytes(data))

    async def _send(self, frame: bytes, *, expect_response: bool) -> bytes | None:
        async with self._lock:
            client = await self._ensure_connected()
            self._request_frame = frame
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
            except (asyncio.TimeoutError, asyncio.CancelledError) as err:
                # Do not reuse a notification stream with an outstanding late reply.
                try:
                    await client.disconnect()
                except Exception:
                    pass
                self._client = None
                if isinstance(err, asyncio.CancelledError):
                    raise
                raise UpdateFailed("timed out waiting for pump response") from err
            finally:
                self._request_frame = None
                self._notify_future = None

    @serialized
    async def async_get_status(self) -> protocol.HeartbeatStatus:
        """Poll the heartbeat (interface 3) and return decoded status."""
        response = await self._send(protocol.build_heartbeat(), expect_response=True)
        assert response is not None
        return protocol.parse_heartbeat(response)

    @serialized
    async def async_read_config(
        self, software_version: int | None
    ) -> tuple[dict[str, int], "list[protocol.TidalSegment]"]:
        """Read the full config (interface 2): parsed fields + tidal schedule."""
        response = await self._send(protocol.build_read_config(), expect_response=True)
        assert response is not None
        _LOGGER.debug("config_raw=%s", list(response))
        return (
            protocol.parse_config(response, software_version),
            protocol.parse_tidal(response),
        )

    @serialized
    async def async_write_tidal(
        self, segments: "list[protocol.TidalSegment]"
    ) -> None:
        """Write the whole 24-segment tidal schedule, one field per frame.

        The pump only applies the first field of a multi-field config-v2 frame,
        so each mode/power/period is sent as its own single-field frame.
        """
        status = await self.async_get_status()
        if not protocol.uses_config_v2(status.software_version) or len(segments) != 24:
            raise UpdateFailed("a complete curve and verified v2 firmware are required")
        for field_id, value in protocol.tidal_full_pairs(segments):
            self.operations.check()
            await self._send(
                protocol.build_frame(protocol.IFACE_READ_CONFIG_V2, [field_id, value]),
                expect_response=True,
            )

        _, observed = await self.async_read_config(status.software_version)
        if observed != list(segments):
            raise UpdateFailed("tidal write not confirmed; original baseline retained")

    @serialized
    async def async_write_tidal_powers(self, powers: "list[int]") -> None:
        """Write only each segment's power (auto_p), one field per frame.

        The pump applies only the first field of a multi-field config-v2 frame,
        so each segment power is sent as its own single-field frame.
        """
        status = await self.async_get_status()
        if not protocol.uses_config_v2(status.software_version) or len(powers) != 24:
            raise UpdateFailed("24 powers and verified v2 firmware are required")
        for field_id, value in protocol.tidal_power_pairs(powers):
            self.operations.check()
            await self._send(
                protocol.build_frame(protocol.IFACE_READ_CONFIG_V2, [field_id, value]),
                expect_response=True,
            )


        _, observed = await self.async_read_config(status.software_version)
        if [segment.power for segment in observed] != list(powers):
            raise UpdateFailed("tidal power write not confirmed; retry from retained baseline")

    @serialized
    async def async_write_field(self, field: int, value: int) -> None:
        """Write a single config field by raw interface-1 id."""
        status = await self.async_get_status()
        table = protocol.JC_FIELD_REQ if protocol.uses_new_table(status.software_version) else protocol.ZC_FIELD_IDS
        name = next((name for name, number in table.items() if number == field), None)
        if name is None:
            raise UpdateFailed("raw field has no verified readback contract")
        await self.async_write_named(name, value, status.software_version)

    @serialized
    async def async_write_named(
        self, name: str, value: int, software_version: int | None
    ) -> None:
        """Write a named config field, using the path the app uses.

        software_version > 10 devices take config-v2 writes (interface 10);
        earlier firmware takes single-field interface-1 writes. Verified on
        hardware that the light only responds to the config-v2 path.
        """
        self.operations.check()
        if protocol.uses_config_v2(software_version):
            frame = protocol.build_config_v2_write(name, value)
        else:
            frame = protocol.build_config_write(name, value, software_version)
        await self._send(frame, expect_response=True)
        if name == "manual_mode" and value in (protocol.MODE_OFF, protocol.MODE_FEED):
            status = await self.async_get_status()
            if status.error_code or status.current_mode != value:
                self.command_error = "pump action was not confirmed by heartbeat"
                raise UpdateFailed(self.command_error)
            return
        config, _ = await self.async_read_config(software_version)
        if config.get(name) != value:
            self.command_error = f"{name} write could not be confirmed"
            raise UpdateFailed(self.command_error)

    async def async_emergency_stop(self, software_version) -> None:
        """Keep the outer operation locked until bounded cleanup finishes."""
        async def stop():
            frame = (protocol.build_config_v2_write("manual_mode", protocol.MODE_OFF)
                     if protocol.uses_config_v2(software_version) else
                     protocol.build_config_write("manual_mode", protocol.MODE_OFF, software_version))
            await self._send(frame, expect_response=True)
            response = await self._send(protocol.build_heartbeat(), expect_response=True)
            state = protocol.parse_heartbeat(response)
            if state.error_code or state.current_mode != protocol.MODE_OFF:
                raise UpdateFailed("emergency stop not confirmed")
        cleanup = asyncio.create_task(stop())
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                continue
        cleanup.result()

    @serialized
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
        self.tidal_overlay = None
        # Shown as the HA device name (prefixes every entity's friendly name);
        # set to the config entry title in async_setup_entry.
        self.device_name = device.address
        # Model label (e.g. "L20" / "L40"), set in async_setup_entry.
        self.model = "Wave Pump"

    async def _async_update_data(self) -> PumpState:
        try:
            status = await self.device.async_get_status()
        except (protocol.InvalidFrameError, OperationSuperseded) as err:
            raise UpdateFailed(f"malformed response: {err}") from err
        # Config read is best-effort: a transient failure keeps the last config
        # rather than failing the whole update (heartbeat is the primary data).
        config: dict[str, int] = self.data.config if self.data else {}
        tidal = self.data.tidal if self.data else []
        try:
            config, tidal = await self.device.async_read_config(
                status.software_version
            )
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
        return PumpState(heartbeat=status, config=config, tidal=tidal)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GTS wave pump from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    device = GtsWavePumpDevice(hass, address)
    coordinator = GtsWavePumpCoordinator(hass, device)
    coordinator.device_name = entry.title
    coordinator.model = model_from_name(entry.title)

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
