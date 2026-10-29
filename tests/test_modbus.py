import importlib.util
import pytest
from simulator import meter
from registers import EXTENDED

@pytest.mark.asyncio
@pytest.mark.parametrize('unit,scale', [('Wh', 1), ('kWh', 1000)])
async def test_extended_all_documented_fields_explicit_energy_units(meter, unit, scale):
    from custom_components.xemex.modbus import XemexModbusClient
    meter.values.update({address: float(i + 101) for i,address in enumerate(EXTENDED)})
    client = XemexModbusClient('127.0.0.1', meter.port, profile='extended', energy_unit=unit)
    try:
        payload = await client.async_read()
        assert len(client.registers) == 49
        for address,path in EXTENDED.items():
            target = payload
            for key in path:
                target = target[key]
            assert target == meter.values[address] * (scale if address in (0x8100,0x8106) else 1)
        assert len(meter.requests) == 49
    finally:
        client.close()

@pytest.mark.asyncio
async def test_extended_illegal_optional_addresses_do_not_kill_basic_reads(meter):
    from custom_components.xemex.modbus import XemexModbusClient
    client = XemexModbusClient('127.0.0.1', meter.port, profile='extended')
    try:
        assert (await client.async_read())['P'] == -1234.5
        assert len(meter.requests) == 49
        meter.requests.clear()
        assert (await client.async_read())['P'] == -1234.5
        assert len(meter.requests) == 10
    finally:
        client.close()

@pytest.mark.asyncio
async def test_real_tcp_basic_word_swap_signed_and_one_connection(meter):
    assert importlib.util.find_spec('custom_components.xemex.modbus') is not None, 'Modbus client missing'
    from custom_components.xemex.modbus import XemexModbusClient
    client = XemexModbusClient('127.0.0.1', meter.port, profile='basic', energy_unit='Wh', phase_count=3, timeout=.2)
    try:
        payload = await client.async_read()
        assert payload['P'] == -1234.5
        assert payload['l1']['U'] == 1
        assert payload['l3']['P'] == 10
        assert 'E_IMPORT' not in payload
        await client.async_read()
        assert meter.connections == 1
        assert len(meter.requests) == 20
        assert all(fc == 3 and count == 2 for fc, _, count in meter.requests)
    finally:
        client.close()
