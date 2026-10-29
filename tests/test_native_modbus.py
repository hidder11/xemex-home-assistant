import pytest
from simulator import meter
from registers import EXTENDED

@pytest.mark.asyncio
@pytest.mark.parametrize('profile,phases,count', [('basic',1,4), ('extended',1,27), ('extended',3,49)])
async def test_native_profiles_phases_energy_nan_and_recovery(hass,meter,profile,phases,count):
    from homeassistant.helpers import entity_registry as er
    meter.values.update({a: 123.5 for a in EXTENDED})
    meter.values.update({0x8006:0,0x8008:0,0x800A:0})
    flow = await hass.config_entries.flow.async_init('xemex',context={'source':'user'})
    flow = await hass.config_entries.flow.async_configure(flow['flow_id'],{'next_step_id':'modbus'})
    result = await hass.config_entries.flow.async_configure(flow['flow_id'], {
        'host':'127.0.0.1','port':meter.port,'serial':'NATIVE','profile':profile,
        'phase_count':phases,'scan_interval':5,'energy_unit':'kWh'})
    entry = result['result']
    await hass.async_block_till_done()
    entities = [e for e in er.async_get(hass).entities.values() if e.config_entry_id == entry.entry_id]
    assert len(entities) == count
    assert len(entry.runtime_data.client.registers) == count
    assert all(not e.unique_id.startswith(('NATIVE_phase_2_', 'NATIVE_phase_3_')) for e in entities) if phases == 1 else True
    if profile == 'extended':
        energy = next(e for e in entities if e.unique_id == 'NATIVE_energy_import')
        assert hass.states.get(energy.entity_id).state == '123.5'
    net = next(e for e in entities if e.unique_id == 'NATIVE_net_power')
    voltage = next(e for e in entities if e.unique_id == 'NATIVE_phase_1_voltage')
    assert hass.states.get(voltage.entity_id).state == '0.0'
    meter.values[0x8016] = float('nan')
    await entry.runtime_data.async_refresh()
    assert hass.states.get(net.entity_id).state == 'unavailable'
    assert hass.states.get(voltage.entity_id).state == '0.0'
    meter.values[0x8016] = -500
    await entry.runtime_data.async_refresh()
    assert hass.states.get(net.entity_id).state == '-0.5'
    assert await hass.config_entries.async_unload(entry.entry_id)
