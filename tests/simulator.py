import asyncio
import struct
import pytest_asyncio

class Meter:
    def __init__(self):
        self.values = {a: float(i + 1) for i, a in enumerate([
            0x8006,0x8008,0x800A,0x800E,0x8010,0x8012,0x8016,0x801E,0x8020,0x8022])}
        self.values[0x8016] = -1234.5
        self.requests = []
        self.writers = set()
        self.readers = {}
        self.connections = 0
        self.max_active = 0
        self.silent = False
        self.disconnect = False
    async def handle(self, reader, writer):
        self.writers.add(writer)
        self.readers[writer] = reader
        active = sum(not self.readers[w].at_eof() and not w.is_closing() for w in self.writers)
        self.max_active = max(self.max_active, active)
        self.connections += 1
        try:
            while True:
                header = await reader.readexactly(7)
                tid, proto, length, unit = struct.unpack('>HHHB', header)
                pdu = await reader.readexactly(length - 1)
                fc, address, count = struct.unpack('>BHH', pdu)
                self.requests.append((fc, address, count))
                assert proto == 0 and fc == 3 and count == 2
                if self.disconnect:
                    return
                if self.silent:
                    continue
                if address not in self.values:
                    body = bytes([fc | 0x80, 2])
                else:
                    high, low = struct.unpack('>HH', struct.pack('>f', self.values[address]))
                    body = bytes([fc, 4]) + struct.pack('>HH', low, high)
                writer.write(struct.pack('>HHHB', tid, 0, len(body) + 1, unit) + body)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            self.writers.discard(writer)
            self.readers.pop(writer, None)

@pytest_asyncio.fixture
async def meter():
    instance = Meter()
    server = await asyncio.start_server(instance.handle, '127.0.0.1', 0)
    instance.port = server.sockets[0].getsockname()[1]
    try:
        yield instance
    finally:
        server.close()
        for writer in list(instance.writers):
            writer.close()
        await server.wait_closed()
        await asyncio.sleep(0)
