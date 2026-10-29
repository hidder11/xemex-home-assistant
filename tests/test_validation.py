import pytest
from helpers import add_entry
from simulator import meter

@pytest.mark.asyncio
@pytest.mark.parametrize('field,value,error', [
    ('host','http://127.0.0.1','invalid_host'), ('host','bad host','invalid_host'),
    ('host','bad..host','invalid_host'), ('host','999.999.999.999','invalid_host'),
    ('serial','','invalid_serial'), ('serial','ABC/123','invalid_serial'),
    ('serial','ABC 123','invalid_serial'), ('serial','ABC+123','invalid_serial')])
async def test_native_form_rejects_invalid_identity_or_host_without_network(hass,meter,field,value,error):
    flow=await hass.config_entries.flow.async_init('xemex',context={'source':'user'})
    flow=await hass.config_entries.flow.async_configure(flow['flow_id'],{'next_step_id':'modbus'})
    data={'host':'127.0.0.1','port':meter.port,'serial':'VALID','scan_interval':10,
          'phase_count':3,'profile':'basic','energy_unit':'Wh',field:value}
    result=await hass.config_entries.flow.async_configure(flow['flow_id'],data)
    assert result['errors']=={field:error}
    assert not meter.requests

@pytest.mark.asyncio
@pytest.mark.parametrize('field,value', [('port',0),('port',65536),('port','502'),
    ('scan_interval',0),('scan_interval',-1),('scan_interval',3601),('scan_interval','10'),

    ('phase_count',2),('profile','invented'),('energy_unit','auto')])
async def test_native_schema_rejects_invalid_bounds(hass,field,value):
    from homeassistant.data_entry_flow import InvalidData
    flow=await hass.config_entries.flow.async_init('xemex',context={'source':'user'})
    flow=await hass.config_entries.flow.async_configure(flow['flow_id'],{'next_step_id':'modbus'})
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(flow['flow_id'],{
            'host':'localhost','port':502,'serial':'VALID','scan_interval':10,
            'phase_count':3,'profile':'basic','energy_unit':'Wh',field:value})

@pytest.mark.asyncio
async def test_native_failed_read_creates_no_entry(hass,meter):
    del meter.values[0x8016]
    flow=await hass.config_entries.flow.async_init('xemex',context={'source':'user'})
    flow=await hass.config_entries.flow.async_configure(flow['flow_id'],{'next_step_id':'modbus'})
    result=await hass.config_entries.flow.async_configure(flow['flow_id'],{
        'host':'127.0.0.1','port':meter.port,'serial':'VALID','scan_interval':10,
        'phase_count':3,'profile':'basic','energy_unit':'Wh'})
    assert result['errors']=={'base':'cannot_connect'}
    assert not hass.config_entries.async_entries('xemex')

@pytest.mark.asyncio
async def test_duplicate_serial_across_transports_does_not_connect(hass,meter):
    await add_entry(hass,{'base_topic':'devices/site/smart-connect/ABC123'})
    flow=await hass.config_entries.flow.async_init('xemex',context={'source':'user'})
    flow=await hass.config_entries.flow.async_configure(flow['flow_id'],{'next_step_id':'modbus'})
    result=await hass.config_entries.flow.async_configure(flow['flow_id'],{
        'host':'127.0.0.1','port':meter.port,'serial':'ABC123','scan_interval':10,
        'phase_count':3,'profile':'basic','energy_unit':'Wh'})
    assert result['reason']=='already_configured'
    assert not meter.requests

@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['port','phase_count'])
async def test_native_boolean_is_not_an_integer_configuration(hass,meter,field):
    flow=await hass.config_entries.flow.async_init('xemex',context={'source':'user'})
    flow=await hass.config_entries.flow.async_configure(flow['flow_id'],{'next_step_id':'modbus'})
    result=await hass.config_entries.flow.async_configure(flow['flow_id'],{
        'host':'127.0.0.1','port':meter.port,'serial':'VALID','scan_interval':10,
        'phase_count':3,'profile':'basic','energy_unit':'Wh',field:True})
    assert result['errors']=={field:'invalid_value'}
    assert not meter.requests

@pytest.mark.asyncio
async def test_closed_tcp_endpoint_is_not_accepted(hass,unused_tcp_port):
    flow=await hass.config_entries.flow.async_init('xemex',context={'source':'user'})
    flow=await hass.config_entries.flow.async_configure(flow['flow_id'],{'next_step_id':'modbus'})
    result=await hass.config_entries.flow.async_configure(flow['flow_id'],{
        'host':'127.0.0.1','port':unused_tcp_port,'serial':'CLOSED','scan_interval':10,
        'phase_count':3,'profile':'basic','energy_unit':'Wh'})
    assert result['errors']=={'base':'cannot_connect'}
    assert not hass.config_entries.async_entries('xemex')

@pytest.mark.asyncio
async def test_modbus_reconfigure_cannot_change_serial(hass,meter):
    data={'transport':'modbus','serial':'ABC123','host':'127.0.0.1','port':meter.port,
        'scan_interval':10,'phase_count':3,'profile':'basic','energy_unit':'Wh'}
    entry=await add_entry(hass,data)
    flow=await hass.config_entries.flow.async_init('xemex',context={'source':'reconfigure','entry_id':entry.entry_id})
    result=await hass.config_entries.flow.async_configure(flow['flow_id'],{
        **{k:v for k,v in data.items() if k!='transport'},'serial':'CHANGED'})
    assert result['reason']=='unique_id_mismatch'
    assert dict(entry.data)==data
    assert not meter.requests
