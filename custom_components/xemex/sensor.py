"""Sensor platform for Xemex Smart P1 Connect."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfReactiveEnergy,
    UnitOfReactivePower,
    UnitOfPower,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_BASE_TOPIC,
    CONF_PHASE_DEFAULTS_PENDING,
    DOMAIN,
    PHASE_COUNT_SINGLE,
    serial_from_base_topic,
)
from .data import XemexConfigEntry, XemexData


@dataclass(frozen=True, kw_only=True)
class XemexSensorEntityDescription(SensorEntityDescription):
    """Describe one metric in an Xemex MQTT payload."""

    payload_path: tuple[str, ...]
    divide_by: float = 1
    as_timestamp: bool = False
    entity_registry_enabled_default: bool = False


def _metric(
    key: str,
    payload_key: str,
    *,
    device_class: SensorDeviceClass | None = None,
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT,
    unit: str | None = None,
    precision: int = 0,
    entity_category: EntityCategory | None = None,
    divide_by: float = 1,
    as_timestamp: bool = False,
    enabled_default: bool = False,
) -> XemexSensorEntityDescription:
    """Create a description for a top-level Xemex metric."""
    return XemexSensorEntityDescription(
        key=key,
        translation_key=key,
        payload_path=(payload_key,),
        device_class=device_class,
        state_class=state_class,
        native_unit_of_measurement=unit,
        suggested_display_precision=precision,
        entity_category=entity_category,
        divide_by=divide_by,
        as_timestamp=as_timestamp,
        entity_registry_enabled_default=enabled_default,
    )


SENSORS: tuple[XemexSensorEntityDescription, ...] = (
    _metric(
        "energy_import",
        "E_IMPORT",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        precision=3,
        divide_by=1000,
        enabled_default=True,
    ),
    _metric(
        "energy_export",
        "E_EXPORT",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        precision=3,
        divide_by=1000,
        enabled_default=True,
    ),
    _metric(
        "last_measurement",
        "ts",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=None,
        as_timestamp=True,
    ),
    _metric(
        "net_power",
        "P",
        device_class=SensorDeviceClass.POWER,
        unit=UnitOfPower.KILO_WATT,
        divide_by=1000,
        precision=3,
        enabled_default=True,
    ),
    _metric(
        "power_import",
        "P+",
        device_class=SensorDeviceClass.POWER,
        unit=UnitOfPower.KILO_WATT,
        divide_by=1000,
        precision=3,
        enabled_default=True,
    ),
    _metric(
        "power_export",
        "P-",
        device_class=SensorDeviceClass.POWER,
        unit=UnitOfPower.KILO_WATT,
        divide_by=1000,
        precision=3,
        enabled_default=True,
    ),
    _metric(
        "line_voltage_l1_l2",
        "U12",
        device_class=SensorDeviceClass.VOLTAGE,
        unit=UnitOfElectricPotential.VOLT,
        precision=1,
        enabled_default=True,
    ),
    _metric(
        "line_voltage_l3_l1",
        "U31",
        device_class=SensorDeviceClass.VOLTAGE,
        unit=UnitOfElectricPotential.VOLT,
        precision=1,
        enabled_default=True,
    ),
    _metric(
        "line_voltage_l2_l3",
        "U32",
        device_class=SensorDeviceClass.VOLTAGE,
        unit=UnitOfElectricPotential.VOLT,
        precision=1,
        enabled_default=True,
    ),
    _metric(
        "reactive_power",
        "Q",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        unit=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    ),
    _metric(
        "reactive_power_positive",
        "Q+",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        unit=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    ),
    _metric(
        "reactive_power_negative",
        "Q-",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        unit=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    ),
    *(
        _metric(
            f"reactive_energy_quadrant_{quadrant}",
            f"EQ{quadrant}",
            device_class=SensorDeviceClass.REACTIVE_ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            unit=UnitOfReactiveEnergy.VOLT_AMPERE_REACTIVE_HOUR,
            precision=3,
        )
        for quadrant in range(1, 5)
    ),
    _metric(
        "power_failures",
        "PFAIL",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_default=True,
    ),
    _metric(
        "long_power_failures",
        "LPFAIL",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_default=True,
    ),
    _metric(
        "power_factor",
        "PF",
        device_class=SensorDeviceClass.POWER_FACTOR,
        precision=2,
    ),
    _metric(
        "apparent_power",
        "S",
        device_class=SensorDeviceClass.APPARENT_POWER,
        unit=UnitOfApparentPower.VOLT_AMPERE,
    ),
)

PHASE_METRICS = (
    ("voltage", "U", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, 1, 1, True),
    ("current", "I", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE, 1, 1, True),
    ("net_power", "P", SensorDeviceClass.POWER, UnitOfPower.KILO_WATT, 3, 1000, True),
    ("power_import", "P+", SensorDeviceClass.POWER, UnitOfPower.KILO_WATT, 3, 1000, True),
    ("power_export", "P-", SensorDeviceClass.POWER, UnitOfPower.KILO_WATT, 3, 1000, True),
    ("reactive_power", "Q", SensorDeviceClass.REACTIVE_POWER, UnitOfReactivePower.VOLT_AMPERE_REACTIVE, 0, 1, False),
    ("reactive_power_positive", "Q+", SensorDeviceClass.REACTIVE_POWER, UnitOfReactivePower.VOLT_AMPERE_REACTIVE, 0, 1, False),
    ("reactive_power_negative", "Q-", SensorDeviceClass.REACTIVE_POWER, UnitOfReactivePower.VOLT_AMPERE_REACTIVE, 0, 1, False),
    ("voltage_sags", "VSAGS", None, None, 0, 1, True),
    ("voltage_swells", "VSWELLS", None, None, 0, 1, True),
    ("apparent_power", "S", SensorDeviceClass.APPARENT_POWER, UnitOfApparentPower.VOLT_AMPERE, 0, 1, False),
)

SENSORS += tuple(
    XemexSensorEntityDescription(
        key=f"phase_{phase}_{metric_key}",
        translation_key=f"phase_{phase}_{metric_key}",
        payload_path=(f"l{phase}", payload_key),
        device_class=device_class,
        state_class=state_class,
        native_unit_of_measurement=unit,
        suggested_display_precision=precision,
        entity_category=(
            EntityCategory.DIAGNOSTIC
            if metric_key in {"voltage_sags", "voltage_swells"}
            else None
        ),
        divide_by=divide_by,
        entity_registry_enabled_default=enabled_default,
    )
    for phase in range(1, 4)
    for metric_key, payload_key, device_class, unit, precision, divide_by, enabled_default
    in PHASE_METRICS
    for state_class in (
        SensorStateClass.TOTAL_INCREASING
        if metric_key in {"voltage_sags", "voltage_swells"}
        else SensorStateClass.MEASUREMENT,
    )
)

LINE_VOLTAGE_KEYS = {
    "line_voltage_l1_l2",
    "line_voltage_l3_l1",
    "line_voltage_l2_l3",
}


def _is_nonexistent_single_phase_metric(key: str) -> bool:
    """Return whether a metric requires phase L2 or L3."""
    return key.startswith(("phase_2_", "phase_3_")) or key in LINE_VOLTAGE_KEYS


def _phase_enabled_default(
    description: XemexSensorEntityDescription, phase_count: int | None
) -> bool:
    """Return the entity default adjusted for a detected phase count."""
    return description.entity_registry_enabled_default and not (
        phase_count == PHASE_COUNT_SINGLE
        and _is_nonexistent_single_phase_metric(description.key)
    )


@callback
def _apply_single_phase_registry_defaults(
    hass: HomeAssistant, entry: XemexConfigEntry
) -> bool:
    """Disable newly registered L2/L3 metrics without overriding preferences."""
    registry = er.async_get(hass)
    all_entities_registered = True
    serial = serial_from_base_topic(entry.data[CONF_BASE_TOPIC])

    for description in SENSORS:
        if not (
            description.entity_registry_enabled_default
            and _is_nonexistent_single_phase_metric(description.key)
        ):
            continue

        unique_id = f"{serial}_{description.key}"
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id is None:
            all_entities_registered = False
            continue

        registry_entry = registry.async_get(entity_id)
        if registry_entry is not None and registry_entry.disabled_by is None:
            registry.async_update_entity(
                entity_id,
                disabled_by=er.RegistryEntryDisabler.INTEGRATION,
            )

    return all_entities_registered


@callback
def _finish_phase_defaults(hass: HomeAssistant, entry: XemexConfigEntry) -> None:
    """Mark one-time phase entity defaults as applied."""
    data = dict(entry.data)
    data.pop(CONF_PHASE_DEFAULTS_PENDING, None)
    hass.config_entries.async_update_entry(entry, data=data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XemexConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Xemex sensors."""
    data: XemexData = entry.runtime_data
    if entry.data.get('transport', 'mqtt') == 'modbus':
        paths = data.client.supported_paths
        async_add_entities(XemexSensor(entry, data, description)
                           for description in SENSORS if description.payload_path in paths)
        return
    async_add_entities(XemexSensor(entry, data, description) for description in SENSORS)

    if not entry.data.get(CONF_PHASE_DEFAULTS_PENDING):
        return

    if data.phase_count is not None:
        _finish_phase_defaults(hass, entry)
        return

    remove_listener: CALLBACK_TYPE | None = None

    @callback
    def apply_detected_phase_defaults() -> None:
        """Apply phase defaults once a conclusive measurement arrives."""
        nonlocal remove_listener
        if data.phase_count is None:
            return
        if (
            data.phase_count == PHASE_COUNT_SINGLE
            and not _apply_single_phase_registry_defaults(hass, entry)
        ):
            return

        _finish_phase_defaults(hass, entry)
        if data.phase_count == PHASE_COUNT_SINGLE:
            hass.config_entries.async_schedule_reload(entry.entry_id)
        if remove_listener is not None:
            remove_listener()

    remove_listener = data.async_add_listener(apply_detected_phase_defaults)


class XemexSensor(SensorEntity):
    """Represent one value from the Xemex instantaneous-power message."""

    entity_description: XemexSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: XemexConfigEntry,
        data: XemexData,
        description: XemexSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._data = data
        self._attr_entity_registry_enabled_default = _phase_enabled_default(
            description, data.phase_count
        )
        serial = (entry.data['serial'] if entry.data.get('transport', 'mqtt') == 'modbus'
                  else serial_from_base_topic(entry.data[CONF_BASE_TOPIC]))
        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer="Xemex",
            model="Smart P1 Connect",
            name=f"Xemex Smart P1 Connect {serial}",
        )

    @property
    def available(self) -> bool:
        """Return whether the current payload contains this metric."""
        return self._data.available and self._native_value is not None

    @property
    def native_value(self) -> datetime | float | None:
        """Return the native Home Assistant value for this metric."""
        return self._native_value

    @property
    def _native_value(self) -> datetime | float | None:
        """Return a validated payload value."""
        raw_value: Any = self._data.payload
        for key in self.entity_description.payload_path:
            if not isinstance(raw_value, dict):
                return None
            raw_value = raw_value.get(key)
        if raw_value is None:
            return None
        try:
            value = float(raw_value) / self.entity_description.divide_by
        except (TypeError, ValueError, ZeroDivisionError):
            return None
        if not math.isfinite(value):
            return None
        if self.entity_description.as_timestamp:
            try:
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None
        return value

    async def async_added_to_hass(self) -> None:
        """Subscribe to shared Xemex updates when the entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(self._data.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        """Write the new MQTT value to Home Assistant."""
        self.async_write_ha_state()
