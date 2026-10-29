import pytest
from helpers import add_entry, discovery

@pytest.mark.asyncio
async def test_mqtt_discovery_never_mutates_modbus_entry(hass):
    data={'transport':'modbus','serial':'ABC123','host':'127.0.0.1','port':502,
          'scan_interval':10,'phase_count':1,'profile':'basic','energy_unit':'Wh'}
    entry = await add_entry(hass, data)
    result = await hass.config_entries.flow.async_init('xemex', context={'source':'mqtt'}, data=discovery())
    assert result['type'] == 'abort' and result['reason'] == 'already_configured'
    assert dict(entry.data) == data

@pytest.mark.asyncio
async def test_mqtt_discovery_still_updates_legacy_mqtt_entry(hass):
    entry = await add_entry(hass, {'base_topic':'devices/old/smart-connect/ABC123'})
    result = await hass.config_entries.flow.async_init('xemex', context={'source':'mqtt'},data=discovery())
    assert result['reason'] == 'already_configured'
    assert entry.data['base_topic'] == 'devices/changed/smart-connect/ABC123'
    assert entry.data['phase_count'] == 3
