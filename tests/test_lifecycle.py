import asyncio
import pytest
from simulator import meter
from helpers import add_entry


def config(port):
    return {'transport':'modbus','serial':'ABC123','host':'127.0.0.1','port':port,
        'scan_interval':5,'phase_count':1,'profile':'basic','energy_unit':'Wh'}

@pytest.mark.asyncio
async def test_live_reconfigure_reuses_single_connection_during_validation(hass,meter):
    entry=await add_entry(hass,config(meter.port),disabled=False)
    await hass.async_block_till_done()
    flow=await hass.config_entries.flow.async_init('xemex',context={'source':'reconfigure','entry_id':entry.entry_id})
    data={k:v for k,v in entry.data.items() if k!='transport'}
    result=await hass.config_entries.flow.async_configure(flow['flow_id'],{**data,'scan_interval':10})
    assert result['reason']=='reconfigure_successful'
    await hass.async_block_till_done()
    assert meter.max_active==1
    await hass.config_entries.async_unload(entry.entry_id)

@pytest.mark.asyncio
async def test_native_periodic_poll_unavailable_recovery_and_stop_closes(hass,meter):
    from homeassistant.helpers import entity_registry as er
    await hass.async_start()
    entry=await add_entry(hass,config(meter.port),disabled=False)
    await hass.async_block_till_done()
    net=next(e.entity_id for e in er.async_get(hass).entities.values() if e.unique_id=='ABC123_net_power')
    runtime=entry.runtime_data
    initial=len(meter.requests)
    meter.values[0x8016]=-222
    async with asyncio.timeout(8):
        while len(meter.requests)<=initial or hass.states.get(net).state!='-0.222':
            await asyncio.sleep(.02)
    meter.disconnect=True
    await runtime.async_refresh()
    assert hass.states.get(net).state=='unavailable'
    meter.disconnect=False
    await runtime.async_refresh()
    assert hass.states.get(net).state=='-0.222'
    await hass.async_stop()
    assert not runtime.client._client.connected

@pytest.mark.asyncio
async def test_native_optional_illegal_registers_not_registered(hass,meter):
    from homeassistant.helpers import entity_registry as er
    entry=await add_entry(hass,{**config(meter.port),'phase_count':3,'profile':'extended'},disabled=False)
    await hass.async_block_till_done()
    entities=[e for e in er.async_get(hass).entities.values() if e.config_entry_id==entry.entry_id]
    assert len(entities)==10
    assert await hass.config_entries.async_unload(entry.entry_id)

@pytest.mark.asyncio
async def test_startup_failure_is_retryable_and_leaves_no_connection(hass,meter):
    del meter.values[0x8016]
    entry=await add_entry(hass,config(meter.port),disabled=False)
    await hass.async_block_till_done()
    assert entry.state.value=='setup_retry'
    async with asyncio.timeout(1):
        while meter.writers:
            await asyncio.sleep(.01)
    meter.values[0x8016]=1000
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state.value=='loaded'
    await hass.config_entries.async_unload(entry.entry_id)

@pytest.mark.asyncio
async def test_unload_cancels_inflight_and_queued_reads_without_reconnect(hass,meter):
    entry=await add_entry(hass,config(meter.port),disabled=False)
    await hass.async_block_till_done()
    runtime=entry.runtime_data
    meter.silent=True
    initial=len(meter.requests)
    tasks=[asyncio.create_task(runtime.async_refresh()) for _ in range(2)]
    async with asyncio.timeout(1):
        while len(meter.requests)==initial:await asyncio.sleep(.001)
    await hass.config_entries.async_unload(entry.entry_id)
    assert all(task.done() for task in tasks)
    assert not runtime.client._client.connected
    connections=meter.connections
    await asyncio.gather(*tasks,return_exceptions=True)
    await asyncio.sleep(.05)
    assert meter.connections==connections
    with pytest.raises(OSError, match='shut down'):
        await runtime.client.async_read()
    assert meter.connections==connections
