"""Home Assistant polling lifecycle for the read-only Modbus client."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus.exceptions import ModbusException

from .modbus import XemexModbusClient

_LOGGER = logging.getLogger(__name__)


class XemexModbusData(DataUpdateCoordinator[dict[str, Any]]):
    """Publish MQTT-compatible payload paths without an MQTT dependency."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name="Xemex Modbus", config_entry=entry,
                         update_interval=timedelta(seconds=entry.data["scan_interval"]))
        self.phase_count = entry.data["phase_count"]
        self.client = XemexModbusClient(
            entry.data["host"], entry.data["port"], profile=entry.data["profile"],
            energy_unit=entry.data["energy_unit"], phase_count=self.phase_count)
        self._read_tasks: set[asyncio.Task] = set()

        async def on_stop(_event: Event) -> None:
            await self.async_shutdown()

        entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_stop))

    @property
    def payload(self) -> dict[str, Any] | None:
        """Return the last complete sample."""
        return self.data

    @property
    def available(self) -> bool:
        """Never serve stale values as available after a failed read."""
        return self.last_update_success

    async def _async_update_data(self) -> dict[str, Any]:
        task = asyncio.current_task()
        self._read_tasks.add(task)
        try:
            return await self.client.async_read()
        except (OSError, ModbusException) as err:
            raise UpdateFailed(f"Modbus read failed: {err}") from err
        finally:
            self._read_tasks.discard(task)

    async def async_setup(self) -> None:
        """Make startup failures retryable and close failed connections."""
        try:
            await self.async_config_entry_first_refresh()
        except BaseException:
            await self.async_unload()
            raise

    async def async_unload(self) -> None:
        """Remove timers and close the owned connection."""
        await self.async_shutdown()

    async def async_shutdown(self) -> None:
        """Cancel active/queued reads before closing; never reconnect on unload."""
        await super().async_shutdown()
        self.client.close(permanent=True)
        tasks = self._read_tasks - {asyncio.current_task()}
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

