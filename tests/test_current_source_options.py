"""Native Home Assistant options flows for the optional current calculation."""

import json
from pathlib import Path

import pytest

from helpers import add_entry, discovery
from simulator import meter


@pytest.mark.asyncio
@pytest.mark.parametrize('transport', ['mqtt', 'modbus'])
async def test_current_source_default_select_and_restore(hass, transport):
    import voluptuous as vol  # HA installs its validation compatibility layer first.

    data = ({'base_topic': 'devices/site/smart-connect/ABC123'}
            if transport == 'mqtt' else
            {'transport': 'modbus', 'serial': 'ABC123', 'host': '127.0.0.1',
             'port': 502, 'scan_interval': 10, 'phase_count': 3,
             'profile': 'basic', 'energy_unit': 'Wh'})
    entry = await add_entry(hass, data)
    original_data = dict(entry.data)
    for default, chosen in [('measured', 'calculated'), ('calculated', 'measured')]:
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        assert flow['type'] == 'form', flow
        assert flow['step_id'] == 'init'
        assert flow['data_schema']({}) == {'current_source': default}
        with pytest.raises(vol.Invalid):
            flow['data_schema']({'current_source': 'unsupported'})
        result = await hass.config_entries.options.async_configure(
            flow['flow_id'], {'current_source': chosen})
        assert result['type'] == 'create_entry', result
        assert dict(entry.options) == {'current_source': chosen}
        assert dict(entry.data) == original_data
        assert entry.unique_id == 'ABC123'


@pytest.mark.asyncio
async def test_discovery_preserves_selected_current_source(hass):
    entry = await add_entry(hass, {'base_topic': 'devices/site/smart-connect/ABC123'})
    hass.config_entries.async_update_entry(entry, options={'current_source': 'calculated'})
    result = await hass.config_entries.flow.async_init(
        'xemex', context={'source': 'mqtt'}, data=discovery())
    assert result['reason'] == 'already_configured'
    assert entry.options['current_source'] == 'calculated'


@pytest.mark.asyncio
async def test_options_reload_live_modbus_and_preserve_entity_ids(hass, meter):
    from homeassistant.helpers import entity_registry as er

    entry = await add_entry(hass, {
        'transport': 'modbus', 'serial': 'ABC123', 'host': '127.0.0.1',
        'port': meter.port, 'scan_interval': 10, 'phase_count': 3,
        'profile': 'basic', 'energy_unit': 'Wh'}, disabled=False)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    ids = {item.unique_id: item.entity_id for item in registry.entities.values()
           if item.config_entry_id == entry.entry_id}
    current_id = ids['ABC123_phase_1_current']
    runtime = entry.runtime_data
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow['flow_id'], {'current_source': 'calculated'})
    assert result['type'] == 'create_entry'
    await hass.async_block_till_done()
    assert entry.state.value == 'loaded'
    assert entry.runtime_data is not runtime  # OptionsFlowWithReload is exercised.
    assert not runtime.client._client.connected
    assert {item.unique_id: item.entity_id for item in registry.entities.values()
            if item.config_entry_id == entry.entry_id} == ids
    sample = entry.runtime_data.payload['l1']
    state = hass.states.get(current_id)
    assert state is not None
    assert float(state.state) == pytest.approx(abs(sample['P']) / sample['U'])


@pytest.mark.parametrize('language', ['en', 'nl'])
def test_current_source_options_translated(language):
    path = Path(__file__).parents[1] / 'custom_components/xemex/translations'
    step = json.loads((path / f'{language}.json').read_text())['options']['step']['init']
    assert step['data']['current_source']
    assert step['data_description']['current_source']
    assert set(step['data_options']['current_source']) == {'measured', 'calculated'}
    assert 'P' in step['description'] and 'U' in step['description']
