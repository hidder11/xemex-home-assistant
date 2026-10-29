"""Xemex Smart P1 Connect integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryNotReady
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .data import XemexConfigEntry, XemexData

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: XemexConfigEntry) -> bool:
    """Set up Xemex from a config entry."""
    if entry.data.get("transport", "mqtt") == "modbus":
        from .modbus_data import XemexModbusData

        data = XemexModbusData(hass, entry)
    else:
        if not hass.config_entries.async_entries('mqtt'):
            raise ConfigEntryNotReady("The MQTT integration is not configured")
        from homeassistant.components import mqtt

        if not mqtt.mqtt_config_entry_enabled(hass):
            raise ConfigEntryNotReady("The MQTT integration is not configured")
        if not mqtt.is_connected(hass):
            raise ConfigEntryNotReady("The MQTT integration is disconnected")
        data = XemexData(hass, entry)
    await data.async_setup()
    entry.runtime_data = data
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await data.async_unload()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: XemexConfigEntry) -> bool:
    """Unload an Xemex config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_unload()
    return unloaded
