import asyncio
import json
import pytest
from mqtt_simulator import broker
from helpers import add_entry, discovery

@pytest.mark.asyncio
async def test_real_ha_mqtt_socket_flow_all_53_sensors_and_legacy_reload(hass,broker,unused_tcp_port):
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.setup import async_setup_component
    from homeassistant.components import mqtt
    from homeassistant.helpers import entity_registry as er
    from custom_components.xemex.sensor import SENSORS
    assert len(SENSORS)==53
    assert await async_setup_component(hass,'http',{'http':{'server_host':'127.0.0.1','server_port':unused_tcp_port}})
    mqtt_entry=ConfigEntry(domain='mqtt',title='Local simulator',version=2,minor_version=1,
        data={'broker':'127.0.0.1','port':broker.port,'protocol':'5','discovery':False},
        options={},source='user',unique_id=None,subentries_data=None,discovery_keys={})
    await hass.config_entries.async_add(mqtt_entry)
    await hass.async_start()
    async with asyncio.timeout(10):
        while not mqtt.is_connected(hass):await asyncio.sleep(.02)
    await hass.async_block_till_done()
    flow=await hass.config_entries.flow.async_init('xemex',context={'source':'user'})
    flow=await hass.config_entries.flow.async_configure(flow['flow_id'],{'next_step_id':'manual_mqtt'})
    result=await hass.config_entries.flow.async_configure(flow['flow_id'],{'base_topic':' /devices/site/smart-connect/ABC123/ '})
    assert result['type']=='create_entry', result
    entry=result['result']
    await hass.async_block_till_done()
    assert entry.state.value=='loaded'
    assert entry.data.get('transport','mqtt')=='mqtt'
    assert entry.unique_id=='ABC123'
    entities=[e for e in er.async_get(hass).entities.values() if e.config_entry_id==entry.entry_id]
    assert len(entities)==53
    # Enable every description to exercise values through real HA state writes.
    for entity in entities:
        if entity.disabled_by:
            er.async_get(hass).async_update_entity(entity.entity_id,disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    payload={}
    for i,description in enumerate(SENSORS):
        target=payload
        for part in description.payload_path[:-1]:target=target.setdefault(part,{})
        target[description.payload_path[-1]]=1700000000 if description.as_timestamp else (i+1)*1000
    topic='devices/site/smart-connect/ABC123/data/power_instant'
    async with asyncio.timeout(5):
        while not any(topic in filters for filters in broker.clients.values()):await asyncio.sleep(.02)
    await broker.publish(topic,json.dumps(payload))
    async with asyncio.timeout(5):
        while not entry.runtime_data.available:await asyncio.sleep(.02)
    await hass.async_block_till_done()
    for description in SENSORS:
        entity=next(e for e in entities if e.unique_id==f'ABC123_{description.key}')
        state=hass.states.get(entity.entity_id)
        assert state and state.state not in ('unknown','unavailable'), (description.key,state)
        if not description.as_timestamp:
            raw=payload
            for part in description.payload_path:raw=raw[part]
            assert float(state.state)==raw/description.divide_by
    # Staleness, malformed message and clean resume preserve MQTT semantics.
    entry.runtime_data._async_mark_stale(None)
    assert not entry.runtime_data.available
    await broker.publish(topic,'not json')
    await asyncio.sleep(.05)
    assert not entry.runtime_data.available
    await broker.publish(topic,json.dumps(payload))
    async with asyncio.timeout(2):
        while not entry.runtime_data.available:await asyncio.sleep(.01)
    old=entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not old.subscription_active and old._cancel_stale_timer is None
    assert await hass.config_entries.async_unload(mqtt_entry.entry_id)

@pytest.mark.asyncio
async def test_mqtt_discovery_confirm_and_reconfigure_legacy_identity(hass,monkeypatch):
    from homeassistant.components import mqtt
    from homeassistant.config_entries import ConfigEntry, ConfigEntryDisabler
    await hass.config_entries.async_add(ConfigEntry(domain='mqtt',title='Stub boundary',
        version=2,minor_version=1,data={'broker':'localhost','protocol':'5'},options={},
        source='user',unique_id=None,subentries_data=None,discovery_keys={},disabled_by=ConfigEntryDisabler.USER))
    monkeypatch.setattr(mqtt,'mqtt_config_entry_enabled',lambda hass:True)
    from unittest.mock import AsyncMock
    monkeypatch.setattr(mqtt,'is_connected',lambda hass:True)
    monkeypatch.setattr(mqtt,'async_subscribe',AsyncMock(return_value=lambda:None))
    flow=await hass.config_entries.flow.async_init('xemex',context={'source':'mqtt'},data=discovery('DISCOVERED'))
    assert flow['step_id']=='discovery_confirm'
    result=await hass.config_entries.flow.async_configure(flow['flow_id'],{})
    entry=result['result']
    assert entry.data['phase_count']==3
    assert entry.unique_id=='DISCOVERED'
    # No broker here: MQTT subscription boundary is explicitly replaced.
    entry2=await add_entry(hass,{'base_topic':'devices/site/smart-connect/LEGACY'},serial='LEGACY')
    flow=await hass.config_entries.flow.async_init('xemex',context={'source':'reconfigure','entry_id':entry2.entry_id})
    result=await hass.config_entries.flow.async_configure(flow['flow_id'],{'base_topic':'devices/new/smart-connect/LEGACY'})
    assert result['reason']=='reconfigure_successful'
    assert dict(entry2.data)=={'base_topic':'devices/new/smart-connect/LEGACY'}
    flow=await hass.config_entries.flow.async_init('xemex',context={'source':'reconfigure','entry_id':entry2.entry_id})
    result=await hass.config_entries.flow.async_configure(flow['flow_id'],{'base_topic':'devices/new/smart-connect/DIFFERENT'})
    assert result['reason']=='unique_id_mismatch'
