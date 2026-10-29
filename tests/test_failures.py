import asyncio
import pytest
from simulator import meter

@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['timeout','disconnect','mandatory_illegal'])
async def test_real_tcp_failure_closes_and_next_poll_reconnects(meter,failure):
    from custom_components.xemex.modbus import XemexModbusClient
    from pymodbus.exceptions import ModbusException
    client = XemexModbusClient('127.0.0.1',meter.port,timeout=.08)
    try:
        assert (await client.async_read())['P'] == -1234.5
        if failure == 'timeout': meter.silent = True
        elif failure == 'disconnect': meter.disconnect = True
        else: del meter.values[0x8016]
        with pytest.raises((OSError,ModbusException)):
            async with asyncio.timeout(1):
                await client.async_read()
        assert not client._client.connected
        meter.silent = meter.disconnect = False
        meter.values[0x8016] = -321
        assert (await client.async_read())['P'] == -321
        assert meter.connections >= 2
    finally:
        client.close()

@pytest.mark.asyncio
async def test_real_tcp_cancel_closes_connection(meter):
    from custom_components.xemex.modbus import XemexModbusClient
    client=XemexModbusClient('127.0.0.1',meter.port,timeout=3)
    meter.silent=True
    task=asyncio.create_task(client.async_read())
    while not meter.requests:
        await asyncio.sleep(.001)
    task.cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not client._client.connected
    finally:
        client.close()

@pytest.mark.asyncio
async def test_concurrent_reads_are_serialized_on_one_connection(meter):
    from custom_components.xemex.modbus import XemexModbusClient
    client=XemexModbusClient('127.0.0.1',meter.port)
    try:
        samples=await asyncio.gather(*(client.async_read() for _ in range(4)))
        assert all(p['P']==-1234.5 for p in samples)
        assert meter.connections==1
        addresses=[address for _,address,_ in meter.requests]
        assert addresses==list(client.registers)*4
    finally:
        client.close()
