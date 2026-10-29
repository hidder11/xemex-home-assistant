"""Read-only Smart Connect Modbus TCP, manual V1.8 pp.20–22.

No probing of undocumented registers and no writes. One persistent connection,
serialized reads; FC03, Float32 big-endian bytes, low word first.
"""
from __future__ import annotations

import asyncio
import struct
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

# (register, MQTT-compatible payload path). Basic: manual V1.6.
BASIC_REGISTERS = {
    0x8006: ('l1', 'U'), 0x8008: ('l2', 'U'), 0x800A: ('l3', 'U'),
    0x800E: ('l1', 'I'), 0x8010: ('l2', 'I'), 0x8012: ('l3', 'I'),
    0x8016: ('P',),
    0x801E: ('l1', 'P'), 0x8020: ('l2', 'P'), 0x8022: ('l3', 'P'),
}

EXTENDED_REGISTERS = {
    0x8018: ('Q',), 0x801A: ('S',), 0x801C: ('PF',),
    0x8024: ('l1','Q'), 0x8026: ('l2','Q'), 0x8028: ('l3','Q'),
    0x802A: ('l1','S'), 0x802C: ('l2','S'), 0x802E: ('l3','S'),
    0x8100: ('E_IMPORT',), 0x8106: ('E_EXPORT',),
    0x8C00: ('Q+',), 0x8C02: ('Q-',),
    0x8C04: ('l1','Q+'), 0x8C06: ('l1','Q-'),
    0x8C08: ('l2','Q+'), 0x8C0A: ('l2','Q-'),
    0x8C0C: ('l3','Q+'), 0x8C0E: ('l3','Q-'),
    0x8C10: ('EQ1',), 0x8C12: ('EQ2',), 0x8C14: ('EQ3',), 0x8C16: ('EQ4',),
    0x8C18: ('l1','VSAGS'), 0x8C1A: ('l2','VSAGS'), 0x8C1C: ('l3','VSAGS'),
    0x8C1E: ('l1','VSWELLS'), 0x8C20: ('l2','VSWELLS'), 0x8C22: ('l3','VSWELLS'),
    0x8C24: ('PFAIL',), 0x8C26: ('LPFAIL',),
    0x8C28: ('P+',), 0x8C2A: ('P-',),
    0x8C2C: ('l1','P+'), 0x8C2E: ('l1','P-'),
    0x8C30: ('l2','P+'), 0x8C32: ('l2','P-'),
    0x8C34: ('l3','P+'), 0x8C36: ('l3','P-'),
}

class XemexModbusClient:
    """Own the device's single connection; only read documented registers."""

    def __init__(self, host: str, port: int = 502, *, profile: str = 'basic',
                 energy_unit: str = 'Wh', phase_count: int = 3,
                 timeout: float = 3) -> None:
        self.registers = dict(BASIC_REGISTERS)
        if profile == 'extended':
            self.registers.update(EXTENDED_REGISTERS)
        if phase_count == 1:
            self.registers = {address: path for address, path in self.registers.items()
                              if path[0] not in ('l2', 'l3')}
        self._energy_scale = 1000 if energy_unit == 'kWh' else 1
        self._unsupported: set[int] = set()
        self._closed = False
        self._lock = asyncio.Lock()
        self._client = AsyncModbusTcpClient(host, port=port, timeout=timeout,
                                          retries=0, reconnect_delay=0)

    async def async_read(self) -> dict:
        """Return a complete read, discarding partial samples on network failure."""
        async with self._lock:
            try:
                if self._closed:
                    raise OSError('Modbus client is shut down')
                if not self._client.connected and not await self._client.connect():
                    raise OSError('Cannot connect to Smart Connect')
                payload = {}
                for address, path in self.registers.items():
                    if address in self._unsupported:
                        continue
                    response = await self._client.read_holding_registers(address, count=2, device_id=1)
                    if response.isError():
                        if address not in BASIC_REGISTERS and getattr(response, 'exception_code', None) == 2:
                            self._unsupported.add(address)
                            continue
                        raise OSError(f'Modbus exception at {address:#x}')
                    if len(response.registers) != 2:
                        raise OSError(f'Invalid Modbus response at {address:#x}')
                    low, high = response.registers
                    value = struct.unpack('>f', struct.pack('>HH', high, low))[0]
                    if address in (0x8100, 0x8106):
                        value *= self._energy_scale
                    target = payload
                    for key in path[:-1]:
                        target = target.setdefault(key, {})
                    target[path[-1]] = value
                return payload
            except (OSError, ModbusException, asyncio.TimeoutError):
                self.close()
                # pymodbus wraps external cancellation as ModbusIOException.
                # Preserve asyncio cancellation so shutdown cannot schedule recovery.
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError from None
                raise
            except asyncio.CancelledError:
                self.close()
                raise

    @property
    def supported_paths(self) -> set[tuple[str, ...]]:
        """Paths selected by profile/phases, excluding proven illegal addresses."""
        return {path for address, path in self.registers.items() if address not in self._unsupported}

    def close(self, *, permanent: bool = False) -> None:
        """Close TCP; permanent shutdown also prevents queued future reconnects."""
        self._closed |= permanent
        self._client.close()
