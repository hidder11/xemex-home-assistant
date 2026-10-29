"""MQTT subscription and state storage for Xemex."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_BASE_TOPIC,
    CONF_PHASE_COUNT,
    POWER_INSTANT_SUFFIX,
    detect_phase_count,
)

_LOGGER = logging.getLogger(__name__)
STALE_AFTER_SECONDS = 300


class XemexData:
    """Store the latest Xemex MQTT message and notify entities about changes."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the shared MQTT data source."""
        self.hass = hass
        self.entry = entry
        self.power_topic = f"{entry.data[CONF_BASE_TOPIC]}/{POWER_INSTANT_SUFFIX}"
        self.payload: Mapping[str, Any] | None = None
        self.available = False
        self.phase_count: int | None = entry.data.get(CONF_PHASE_COUNT)
        self._listeners: list[Callable[[], None]] = []
        self._unsubscribe: CALLBACK_TYPE | None = None
        self._cancel_stale_timer: CALLBACK_TYPE | None = None

    @property
    def subscription_active(self) -> bool:
        """Return whether the MQTT subscription is currently registered."""
        return self._unsubscribe is not None

    async def async_setup(self) -> None:
        """Wait for Home Assistant MQTT and subscribe to Xemex measurements."""
        self._unsubscribe = await mqtt.async_subscribe(
            self.hass,
            self.power_topic,
            self._async_handle_message,
            qos=0,
        )

    async def async_unload(self) -> None:
        """Remove the MQTT subscription."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._cancel_stale_timer is not None:
            self._cancel_stale_timer()
            self._cancel_stale_timer = None

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Register a callback for new Xemex measurements."""
        self._listeners.append(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.remove(listener)

        return remove_listener

    @callback
    def _async_handle_message(self, message: mqtt.ReceiveMessage) -> None:
        """Parse an instantaneous-power message from Xemex."""
        try:
            payload = json.loads(message.payload)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as err:
            _LOGGER.warning("Ignoring invalid Xemex measurement JSON: %s", err)
            return

        if not isinstance(payload, dict):
            _LOGGER.warning("Ignoring non-object Xemex measurement JSON")
            return

        was_available = self.available
        self.payload = payload
        self.available = True
        if self.phase_count is None:
            self.phase_count = detect_phase_count(payload)
            if (
                self.phase_count is not None
                and self.hass.config_entries.async_get_entry(self.entry.entry_id)
                is not None
            ):
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={
                        **self.entry.data,
                        CONF_PHASE_COUNT: self.phase_count,
                    },
                )
        if self._cancel_stale_timer is not None:
            self._cancel_stale_timer()
        self._cancel_stale_timer = async_call_later(
            self.hass, STALE_AFTER_SECONDS, self._async_mark_stale
        )
        if not was_available:
            _LOGGER.info("Xemex measurements have resumed")
        self._notify_listeners()

    @callback
    def _async_mark_stale(self, _: datetime) -> None:
        """Mark measurements unavailable when the device stops publishing."""
        self._cancel_stale_timer = None
        if not self.available:
            return

        self.available = False
        _LOGGER.info("Xemex measurements have stopped; entities are unavailable")
        self._notify_listeners()

    @callback
    def _notify_listeners(self) -> None:
        """Notify entities that availability or measurement data changed."""
        for listener in tuple(self._listeners):
            listener()


type XemexConfigEntry = ConfigEntry[XemexData]
