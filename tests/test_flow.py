import pytest
from simulator import meter

@pytest.mark.asyncio
async def test_native_modbus_setup_sensors_reload_unload_without_mqtt(hass, meter):
    from homeassistant.helpers import entity_registry as er
    result = await hass.config_entries.flow.async_init('xemex', context={'source':'user'})
    result = await hass.config_entries.flow.async_configure(result['flow_id'], {'next_step_id':'modbus'})
    assert result['step_id'] == 'modbus'
    defaults = result['data_schema']({'host':'127.0.0.1', 'serial':'ABC123', 'energy_unit':'Wh'})
    assert defaults['port'] == 502 and defaults['scan_interval'] == 10
    result = await hass.config_entries.flow.async_configure(result['flow_id'], {**defaults, 'port':meter.port})
    assert result['type'] == 'create_entry', result
    entry = result['result']
    await hass.async_block_till_done()
    assert entry.state.value == 'loaded'
    assert entry.unique_id == 'ABC123'
    assert 'mqtt' not in hass.config.components
    entities = [e for e in er.async_get(hass).entities.values() if e.config_entry_id == entry.entry_id]
    assert len(entities) == 10
    net = next(e for e in entities if e.unique_id == 'ABC123_net_power')
    assert hass.states.get(net.entity_id).state == '-1.2345'
    old = entry.runtime_data
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert not old.client._client.connected
    current = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not current.client._client.connected
    import asyncio
    async with asyncio.timeout(1):
        while meter.writers:
            await asyncio.sleep(.01)
    assert not meter.writers

@pytest.mark.asyncio
async def test_native_transport_menu_without_mqtt(hass):
    result = await hass.config_entries.flow.async_init('xemex', context={'source':'user'})
    assert result['type'] == 'menu', result
    assert result['menu_options'] == ['manual_mqtt', 'modbus']
    result = await hass.config_entries.flow.async_configure(result['flow_id'], {'next_step_id': 'manual_mqtt'})
    assert result['step_id'] == 'manual_mqtt'
    result = await hass.config_entries.flow.async_configure(result['flow_id'], {'base_topic': 'devices/site/smart-connect/ABC123'})
    assert result['errors'] == {'base_topic': 'mqtt_not_configured'}
