"""Config flow for the Xemex integration."""

from __future__ import annotations

import json
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import (
    CONF_BASE_TOPIC,
    CONF_PHASE_COUNT,
    CONF_PHASE_DEFAULTS_PENDING,
    DOMAIN,
    base_topic_from_measurement_topic,
    base_topic_validation_error,
    detect_phase_count,
    normalize_base_topic,
    serial_from_base_topic,
)


class XemexConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Xemex Smart P1 Connect."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_base_topic: str | None = None
        self._discovered_phase_count: int | None = None

    @staticmethod
    def _entry_data(base_topic: str, phase_count: int | None) -> dict[str, Any]:
        """Build config entry data with phase defaults pending when unknown."""
        data: dict[str, Any] = {CONF_BASE_TOPIC: base_topic}
        if phase_count is None:
            data[CONF_PHASE_DEFAULTS_PENDING] = True
        else:
            data[CONF_PHASE_COUNT] = phase_count
        return data

    def _validate_input(
        self, user_input: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        """Normalize a base topic and return a translation error when invalid."""
        topic_error = base_topic_validation_error(user_input[CONF_BASE_TOPIC])
        base_topic = normalize_base_topic(user_input[CONF_BASE_TOPIC])
        if topic_error is not None:
            return None, topic_error
        if not mqtt.mqtt_config_entry_enabled(self.hass):
            return None, "mqtt_not_configured"
        if not mqtt.is_connected(self.hass):
            return None, "mqtt_not_connected"
        return base_topic, None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            base_topic, error = self._validate_input(user_input)
            if error is not None:
                errors[CONF_BASE_TOPIC] = error
            else:
                assert base_topic is not None
                serial = serial_from_base_topic(base_topic)
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Xemex {serial}",
                    data=self._entry_data(base_topic, None),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_BASE_TOPIC): str}),
            errors=errors,
        )

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> FlowResult:
        """Handle a Smart Connect discovered from its MQTT measurements."""
        base_topic = base_topic_from_measurement_topic(discovery_info.topic)
        if base_topic is None:
            return self.async_abort(reason="invalid_discovery_topic")

        try:
            payload = json.loads(discovery_info.payload)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
            return self.async_abort(reason="invalid_discovery_payload")
        if not isinstance(payload, dict):
            return self.async_abort(reason="invalid_discovery_payload")

        phase_count = detect_phase_count(payload)

        serial = serial_from_base_topic(base_topic)
        await self.async_set_unique_id(serial)
        updates: dict[str, Any] = {CONF_BASE_TOPIC: base_topic}
        if phase_count is not None:
            updates[CONF_PHASE_COUNT] = phase_count
        self._abort_if_unique_id_configured(updates=updates)

        self._discovered_base_topic = base_topic
        self._discovered_phase_count = phase_count
        self.context["title_placeholders"] = {"name": f"Xemex {serial}"}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask the user to confirm a discovered Smart Connect device."""
        if self._discovered_base_topic is None:
            return self.async_abort(reason="invalid_discovery_topic")

        serial = serial_from_base_topic(self._discovered_base_topic)
        if user_input is not None:
            return self.async_create_entry(
                title=f"Xemex {serial}",
                data=self._entry_data(
                    self._discovered_base_topic,
                    self._discovered_phase_count,
                ),
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"serial": serial},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to correct the MQTT base topic without re-adding."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            base_topic, error = self._validate_input(user_input)
            if error is not None:
                errors[CONF_BASE_TOPIC] = error
            else:
                assert base_topic is not None
                serial = serial_from_base_topic(base_topic)
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_BASE_TOPIC: base_topic},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BASE_TOPIC,
                        default=entry.data[CONF_BASE_TOPIC],
                    ): str
                }
            ),
            errors=errors,
        )
