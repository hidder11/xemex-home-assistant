"""Calculated current contracts and real local HA transport regressions."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from mqtt_simulator import broker
from simulator import meter

from custom_components.xemex.sensor import SENSORS, XemexSensor


def make_sensor(payload, key="phase_1_current", source="calculated", available=True):
    entry_data = {"base_topic": "devices/site/smart-connect/CURRENT"}
    options = {} if source is None else {"current_source": source}
    data = SimpleNamespace(payload=payload, available=available, phase_count=3)
    description = next(item for item in SENSORS if item.key == key)
    return XemexSensor(SimpleNamespace(data=entry_data, options=options), data, description)


@pytest.mark.parametrize("phase,power,voltage", [(1, 537, 231), (2, -811, 229), (3, 0, 230)])
def test_calculated_current_uses_own_phase_watts_and_volts(phase, power, voltage):
    payload = {"P": 999999, **{f"l{i}": {"I": 9, "P": 123, "U": 240, "P+": 987, "P-": 654} for i in range(1, 4)}}
    payload[f"l{phase}"].update(P=power, U=voltage)
    original = deepcopy(payload)
    sensor = make_sensor(payload, f"phase_{phase}_current")
    assert sensor.native_value == abs(power) / voltage
    assert sensor.available
    assert payload == original


@pytest.mark.parametrize("field", ["P", "U"])
@pytest.mark.parametrize("bad", [None, True, False, "broken", "", {}, [], float("nan"), float("inf"), -float("inf"), 10**1000])
def test_calculated_current_rejects_invalid_inputs(field, bad):
    phase = {"P": 537, "U": 231, "I": 9}
    phase[field] = bad
    sensor = make_sensor({"l1": phase})
    assert sensor.native_value is None
    assert not sensor.available


@pytest.mark.parametrize("payload", [None, {}, {"l1": None}, {"l1": []}, {"l1": {"I": 9}}, {"l1": {"P": 537}}, {"l1": {"U": 231}}, {"l1": {"P": 1, "U": 0}}, {"l1": {"P": 1, "U": -230}}, {"l1": {"P": 1e308, "U": 1e-308}}])
def test_calculated_current_missing_nonpositive_or_overflow_is_unavailable(payload):
    sensor = make_sensor(payload)
    assert sensor.native_value is None
    assert not sensor.available


def test_calculated_current_recomputes_latest_payload_and_respects_transport():
    sensor = make_sensor({"l1": {"P": 537, "U": 231}})
    assert sensor.native_value == 537 / 231
    sensor._data.payload = {"l1": {"P": -113, "U": 229}}
    assert sensor.native_value == 113 / 229
    sensor._data.available = False
    assert not sensor.available
    sensor._data.available = True
    assert sensor.available
    sensor._data.payload = {"l1": {"P": 9}}
    assert not sensor.available


@pytest.mark.parametrize("source,precision", [(None, 1), ("measured", 1), ("calculated", 2)])
def test_precision_default_compatibility_and_identity(source, precision):
    sensor = make_sensor({"l1": {"I": 9, "P": 537, "U": 231}}, source=source)
    assert sensor.suggested_display_precision == precision
    assert sensor.unique_id == "CURRENT_phase_1_current"
    assert sensor.native_value == (537 / 231 if source == "calculated" else 9)
    assert len(SENSORS) == 53
    assert sensor.entity_description.suggested_display_precision == 1


@pytest.mark.parametrize("source", [None, "measured"])
def test_measured_current_does_not_require_calculation_inputs_or_read_data_option(source):
    sensor = make_sensor({"l1": {"I": 9, "P": None, "U": 0}}, source=source)
    assert sensor.native_value == 9
    assert sensor.available
    entry = SimpleNamespace(data={"base_topic": "devices/site/smart-connect/CURRENT", "current_source": "calculated"}, options={})
    legacy = XemexSensor(entry, sensor._data, sensor.entity_description)
    assert legacy.native_value == 9
    assert legacy.suggested_display_precision == 1


@pytest.mark.parametrize("description", [item for item in SENSORS if item.key not in {"phase_1_current", "phase_2_current", "phase_3_current"}], ids=lambda item: item.key)
def test_calculated_mode_leaves_every_unrelated_description_unchanged(description):
    payload = {}
    target = payload
    for part in description.payload_path[:-1]:
        target = target.setdefault(part, {})
    target[description.payload_path[-1]] = 1700000000 if description.as_timestamp else 123.456
    calculated = make_sensor(payload, description.key)
    measured = make_sensor(payload, description.key, source=None)
    assert calculated.native_value == measured.native_value
    assert calculated.suggested_display_precision == measured.suggested_display_precision
    assert calculated.unique_id == measured.unique_id


async def add_current_entry(hass, data):
    from homeassistant.config_entries import ConfigEntry
    entry = ConfigEntry(domain="xemex", title="Current simulator", data=data,
        options={}, version=1, minor_version=1, source="user", unique_id="CURRENT",
        subentries_data=None, discovery_keys={})
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    assert entry.state.value == "loaded"
    return entry


def registry_snapshot(hass, entry):
    from homeassistant.helpers import entity_registry as er
    return {e.unique_id: e.entity_id for e in er.async_get(hass).entities.values()
            if e.config_entry_id == entry.entry_id}


async def select_current_source(hass, entry, source):
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"current_source": source}
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.options["current_source"] == source


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["basic", "extended"])
@pytest.mark.parametrize("phases", [1, 3])
async def test_native_modbus_current_reload_identity_offline_recovery(hass, meter, profile, phases):
    from registers import EXTENDED
    meter.values.update({address: 123.5 for address in EXTENDED})
    for u, i, p, voltage, power in [(0x8006, 0x800E, 0x801E, 231, 537),
            (0x8008, 0x8010, 0x8020, 229, -811), (0x800A, 0x8012, 0x8022, 230, 0)]:
        meter.values.update({u: voltage, i: 9, p: power})
    entry = await add_current_entry(hass, {"transport": "modbus", "serial": "CURRENT",
        "host": "127.0.0.1", "port": meter.port, "scan_interval": 3600,
        "phase_count": phases, "profile": profile, "energy_unit": "Wh"})
    identities = registry_snapshot(hass, entry)
    assert len(identities) == ({1: 4, 3: 10} if profile == "basic" else {1: 27, 3: 49})[phases]
    currents = [identities[f"CURRENT_phase_{i}_current"] for i in range(1, phases + 1)]
    assert all(hass.states.get(e).state == "9.0" for e in currents)
    await select_current_source(hass, entry, "calculated")
    assert registry_snapshot(hass, entry) == identities
    for entity_id, expected in zip(currents, [537 / 231, 811 / 229, 0]):
        assert float(hass.states.get(entity_id).state) == pytest.approx(expected, rel=1e-14)
    assert entry.runtime_data.payload["l1"]["I"] == 9
    assert hass.states.get(identities["CURRENT_net_power"]).state == "-1.2345"
    for address, bad in [(0x8006, 0), (0x8006, -230), (0x801E, float("nan"))]:
        meter.values[0x8006] = 231
        meter.values[address] = bad
        await entry.runtime_data.async_refresh()
        assert hass.states.get(currents[0]).state == "unavailable"
    meter.values[0x801E] = -113
    await entry.runtime_data.async_refresh()
    assert float(hass.states.get(currents[0]).state) == pytest.approx(113 / 231, rel=1e-14)
    meter.disconnect = True
    await entry.runtime_data.async_refresh()
    assert all(hass.states.get(e).state == "unavailable" for e in currents)
    meter.disconnect = False
    await entry.runtime_data.async_refresh()
    assert float(hass.states.get(currents[0]).state) == pytest.approx(113 / 231, rel=1e-14)
    await select_current_source(hass, entry, "measured")
    assert registry_snapshot(hass, entry) == identities
    assert all(hass.states.get(e).state == "9.0" for e in currents)


@pytest.mark.asyncio
async def test_native_mqtt_current_stale_invalid_recovery_identity(hass, broker, unused_tcp_port):
    import asyncio
    import json
    from homeassistant.components import mqtt
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.setup import async_setup_component
    assert await async_setup_component(hass, "http", {"http": {"server_host": "127.0.0.1", "server_port": unused_tcp_port}})
    mqtt_entry = ConfigEntry(domain="mqtt", title="Local current simulator", version=2, minor_version=1,
        data={"broker": "127.0.0.1", "port": broker.port, "protocol": "5", "discovery": False},
        options={}, source="user", unique_id=None, subentries_data=None, discovery_keys={})
    await hass.config_entries.async_add(mqtt_entry)
    await hass.async_start()
    async with asyncio.timeout(10):
        while not mqtt.is_connected(hass):
            await asyncio.sleep(.02)
    entry = await add_current_entry(hass, {"base_topic": "devices/site/smart-connect/CURRENT", "phase_count": 3})
    identities = registry_snapshot(hass, entry)
    assert len(identities) == 53
    currents = [identities[f"CURRENT_phase_{i}_current"] for i in range(1, 4)]
    topic = "devices/site/smart-connect/CURRENT/data/power_instant"
    payload = {"P": -9999, "l1": {"I": 9, "P": 537, "U": 231},
               "l2": {"I": 9, "P": -811, "U": 229}, "l3": {"I": 9, "P": 0, "U": 230}}

    async def publish(sample):
        async with asyncio.timeout(5):
            while not any(topic in filters for filters in broker.clients.values()):
                await asyncio.sleep(.02)
        await broker.publish(topic, json.dumps(sample))
        async with asyncio.timeout(5):
            while entry.runtime_data.payload != sample or not entry.runtime_data.available:
                await asyncio.sleep(.02)
        await hass.async_block_till_done()

    await publish(payload)
    assert all(hass.states.get(e).state == "9.0" for e in currents)
    await select_current_source(hass, entry, "calculated")
    assert registry_snapshot(hass, entry) == identities
    await publish(payload)
    for entity_id, expected in zip(currents, [537 / 231, 811 / 229, 0]):
        assert float(hass.states.get(entity_id).state) == pytest.approx(expected, rel=1e-14)
    assert entry.runtime_data.payload == payload
    assert hass.states.get(identities["CURRENT_net_power"]).state == "-9.999"
    for bad in [None, True, "bad", 0, -230]:
        sample = deepcopy(payload)
        sample["l1"]["U"] = bad
        await publish(sample)
        assert hass.states.get(currents[0]).state == "unavailable"
        assert float(hass.states.get(currents[1]).state) == pytest.approx(811 / 229, rel=1e-14)
    await publish(payload)
    entry.runtime_data._async_mark_stale(None)
    assert all(hass.states.get(e).state == "unavailable" for e in currents)
    await publish(payload)
    assert float(hass.states.get(currents[0]).state) == pytest.approx(537 / 231, rel=1e-14)
    await select_current_source(hass, entry, "measured")
    await publish(payload)
    assert registry_snapshot(hass, entry) == identities
    assert all(hass.states.get(e).state == "9.0" for e in currents)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_unload(mqtt_entry.entry_id)
