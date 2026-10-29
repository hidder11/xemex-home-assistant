"""Regression coverage for the approved one-second polling minimum."""
import asyncio
import pytest
from helpers import add_entry
from simulator import meter


def settings(port):
    return {'host': '127.0.0.1', 'port': port, 'serial': 'ONESECOND',
            'scan_interval': 1, 'phase_count': 1, 'profile': 'basic', 'energy_unit': 'Wh'}


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['user', 'reconfigure'])
@pytest.mark.parametrize('interval', [0, 1, 4, 3601])
async def test_native_interval_bounds(hass, meter, source, interval):
    from homeassistant.data_entry_flow import InvalidData
    data = settings(meter.port)
    if source == 'reconfigure':
        entry = await add_entry(hass, {**data, 'transport': 'modbus', 'scan_interval': 10}, serial=data['serial'])
        flow = await hass.config_entries.flow.async_init('xemex', context={
            'source': source, 'entry_id': entry.entry_id})
    else:
        flow = await hass.config_entries.flow.async_init('xemex', context={'source': source})
        flow = await hass.config_entries.flow.async_configure(flow['flow_id'], {'next_step_id': 'modbus'})
    if interval in (0, 3601):
        with pytest.raises(InvalidData):
            await hass.config_entries.flow.async_configure(flow['flow_id'], {**data, 'scan_interval': interval})
        assert not meter.requests
    else:
        result = await hass.config_entries.flow.async_configure(flow['flow_id'], {**data, 'scan_interval': interval})
        if source == 'user':
            assert result['type'] == 'create_entry'
            assert result['data']['scan_interval'] == interval
        else:
            assert result['reason'] == 'reconfigure_successful'
            assert entry.data['scan_interval'] == interval


@pytest.mark.asyncio
async def test_actual_one_second_polling_and_slow_reads_are_serialized(hass, meter):
    from homeassistant.helpers import entity_registry as er
    await hass.async_start()
    entry = await add_entry(hass, {**settings(meter.port), 'transport': 'modbus'}, disabled=False)
    await hass.async_block_till_done()
    runtime = entry.runtime_data
    assert runtime.update_interval.total_seconds() == 1
    net = next(e.entity_id for e in er.async_get(hass).entities.values()
               if e.unique_id == 'ONESECOND_net_power')
    times = []
    original_read = runtime.client.async_read
    async def record_read():
        times.append(asyncio.get_running_loop().time())
        return await original_read()
    runtime.client.async_read = record_read
    meter.values[0x8016] = -222
    async with asyncio.timeout(5):
        while len(times) < 3:
            await asyncio.sleep(.02)
    assert hass.states.get(net).state == '-0.222'
    assert all(.7 < later - earlier < 1.5 for earlier, later in zip(times, times[1:]))
    await runtime.async_shutdown()

    # A full read takes longer than the selected interval. Exercise the real
    # client lock with concurrent requests, using delayed local TCP responses.
    from custom_components.xemex.modbus import XemexModbusClient
    client = XemexModbusClient('127.0.0.1', meter.port, profile='basic', energy_unit='Wh', phase_count=1)
    original_request = client._client.read_holding_registers
    active = 0
    maximum = 0
    async def slow_request(*args, **kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        try:
            await asyncio.sleep(.3)
            return await original_request(*args, **kwargs)
        finally:
            active -= 1
    client._client.read_holding_registers = slow_request
    try:
        async with asyncio.timeout(8):
            results = await asyncio.gather(client.async_read(), client.async_read())
        assert len(results) == 2
        assert maximum == 1
        assert meter.max_active == 1
    finally:
        client.close(permanent=True)
