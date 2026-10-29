"""Diagnostics support for Xemex."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_BASE_TOPIC
from .data import XemexConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: XemexConfigEntry
) -> dict[str, Any]:
    """Return sanitized diagnostics for a config entry."""
    del hass
    data = entry.runtime_data
    return {
        "entry_data": async_redact_data(entry.data, {CONF_BASE_TOPIC}),
        "mqtt_subscription_active": data.subscription_active,
        "has_received_measurement": data.payload is not None,
        "measurements_available": data.available,
        "detected_phase_count": data.phase_count,
    }
