"""Config flow for the Xemex integration."""

from __future__ import annotations

import ipaddress
import json
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
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
        if not self.hass.config_entries.async_entries('mqtt'):
            return None, 'mqtt_not_configured'
        from homeassistant.components import mqtt

        if not mqtt.mqtt_config_entry_enabled(self.hass):
            return None, "mqtt_not_configured"
        if not mqtt.is_connected(self.hass):
            return None, "mqtt_not_connected"
        return base_topic, None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose a transport without requiring an MQTT configuration."""
        return self.async_show_menu(step_id="user", menu_options=["manual_mqtt", "modbus"])

    async def async_step_manual_mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the existing MQTT transport."""
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
            step_id="manual_mqtt",
            data_schema=vol.Schema({vol.Required(CONF_BASE_TOPIC): str}),
            errors=errors,
        )

    async def async_step_modbus(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Validate a read-only endpoint before creating an entry."""
        from .modbus import XemexModbusClient
        from pymodbus.exceptions import ModbusException

        errors = {}
        entry = self._get_reconfigure_entry() if self.source == 'reconfigure' else None
        defaults = entry.data if entry else {}
        if user_input is not None:
            for key in ('port', 'phase_count', 'scan_interval'):
                if isinstance(user_input[key], bool):
                    errors[key] = 'invalid_value'
            host = user_input['host']
            try:
                ipaddress.ip_address(host)
            except ValueError:
                labels = host.removesuffix('.').split('.')
                if (len(host) > 253 or re.fullmatch(r'[0-9.]+', host)
                    or not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
                               for label in labels)):
                    errors['host'] = 'invalid_host'
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', user_input['serial']):
                errors['serial'] = 'invalid_serial'
            if not errors:
                await self.async_set_unique_id(user_input['serial'])
                if entry:
                    self._abort_if_unique_id_mismatch()
                else:
                    self._abort_if_unique_id_configured()
                client = XemexModbusClient(
                    host, user_input['port'], profile=user_input['profile'],
                    energy_unit=user_input['energy_unit'], phase_count=user_input[CONF_PHASE_COUNT])
                # The device permits one TCP client. Validate a live endpoint
                # using its already-serialized connection rather than opening two.
                runtime = getattr(entry, 'runtime_data', None) if entry else None
                reuse = (runtime is not None and entry.data['host'] == host
                         and entry.data['port'] == user_input['port'])
                if reuse:
                    client.close()
                    client = runtime.client
                try:
                    await client.async_read()
                except (OSError, ModbusException):
                    errors['base'] = 'cannot_connect'
                finally:
                    if not reuse:
                        client.close()
                if not errors:
                    if entry:
                        return self.async_update_reload_and_abort(entry, data_updates=user_input)
                    return self.async_create_entry(
                        title=f"Xemex {user_input['serial']}",
                        data={**user_input, 'transport': 'modbus'})
        return self.async_show_form(step_id='modbus', errors=errors, data_schema=vol.Schema({
            vol.Required('host', default=defaults.get('host', vol.UNDEFINED)): str,
            vol.Required('port', default=defaults.get('port', 502)): vol.All(int, vol.Range(min=1, max=65535)),
            vol.Required('serial', default=defaults.get('serial', vol.UNDEFINED)): str,
            vol.Required('scan_interval', default=defaults.get('scan_interval', 10)): vol.All(int, vol.Range(min=1, max=3600)),
            vol.Required(CONF_PHASE_COUNT, default=defaults.get(CONF_PHASE_COUNT, 3)): vol.In([1, 3]),
            vol.Required('profile', default=defaults.get('profile', 'basic')): vol.In(['basic', 'extended']),
            vol.Required('energy_unit', default=defaults.get('energy_unit', vol.UNDEFINED)): vol.In(['Wh', 'kWh']),
        }))

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
        if any(entry.unique_id == serial and entry.data.get('transport', 'mqtt') == 'modbus'
               for entry in self._async_current_entries()):
            return self.async_abort(reason='already_configured')
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
        """Correct connection settings without changing device identity."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if entry.data.get('transport', 'mqtt') == 'modbus':
            return await self.async_step_modbus(user_input)

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
