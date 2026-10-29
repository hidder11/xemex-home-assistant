import pytest
from simulator import meter
from helpers import add_entry

@pytest.mark.asyncio
async def test_modbus_native_reconfigure_preserves_identity_and_validates_read(hass,meter):
    data={'transport':'modbus','serial':'ABC123','host':'127.0.0.1','port':502,
          'scan_interval':10,'phase_count':1,'profile':'basic','energy_unit':'Wh'}
    entry = await add_entry(hass,data)
    flow = await hass.config_entries.flow.async_init('xemex',context={'source':'reconfigure','entry_id':entry.entry_id})
    assert flow['step_id'] == 'modbus'
    assert flow['data_schema']({}) == {k:v for k,v in data.items() if k!='transport'}
    user_input = {k:v for k,v in data.items() if k!='transport'}
    result = await hass.config_entries.flow.async_configure(flow['flow_id'],{**user_input,'port':meter.port,'scan_interval':20})
    assert result['reason'] == 'reconfigure_successful'
    assert entry.data['port'] == meter.port and entry.data['scan_interval']==20
    assert entry.unique_id == 'ABC123'
    assert meter.requests

@pytest.mark.asyncio
async def test_modbus_diagnostics_are_redacted(hass,meter):

    from custom_components.xemex.diagnostics import async_get_config_entry_diagnostics
    entry = await add_entry(hass,{'transport':'modbus','serial':'ABC123','host':'127.0.0.1','port':meter.port,
        'scan_interval':10,'phase_count':1,'profile':'basic','energy_unit':'Wh'}, disabled=False)
    await hass.async_block_till_done()
    try:
        result = await async_get_config_entry_diagnostics(hass,entry)
        assert result['entry_data']['host'] == '**REDACTED**'
        assert result['entry_data']['serial'] == '**REDACTED**'
        assert result['transport'] == 'modbus'
        assert result['measurements_available']
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
