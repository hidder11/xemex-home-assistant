"""Minimal local MQTT 5 test peer, not a production broker."""
import asyncio
import struct
import pytest_asyncio


def varint(n):
    result=bytearray()
    while True:
        d=n%128;n//=128
        result.append(d|(128 if n else 0))
        if not n:return bytes(result)

class Broker:
    def __init__(self):
        self.clients={}
        self.received=[]
    async def handle(self,reader,writer):
        self.clients[writer]=[]
        try:
            while True:
                header=(await reader.readexactly(1))[0]
                n=0;mult=1
                while True:
                    d=(await reader.readexactly(1))[0];n+=(d&127)*mult;mult*=128
                    if not d&128:break
                data=await reader.readexactly(n)
                kind=header>>4
                if kind==1: # MQTT 5 CONNECT
                    assert data[6]==5
                    writer.write(b'\x20\x03\x00\x00\x00')
                elif kind==8: # packet id + empty properties + topic filters
                    offset=3+data[2];codes=[]
                    while offset<len(data):
                        size=int.from_bytes(data[offset:offset+2]);offset+=2
                        topic=data[offset:offset+size].decode();offset+=size
                        qos=data[offset]&3;offset+=1
                        self.clients[writer].append(topic);codes.append(qos)
                    body=data[:2]+b'\x00'+bytes(codes)
                    writer.write(b'\x90'+varint(len(body))+body)
                elif kind==10:
                    body=data[:2]+b'\x00\x00'
                    writer.write(b'\xb0'+varint(len(body))+body)
                elif kind==3:
                    self.received.append(data)
                    if (header>>1)&3:
                        size=int.from_bytes(data[:2]);packet_id=data[2+size:4+size]
                        writer.write(b'\x40\x04'+packet_id+b'\x00\x00')
                elif kind==12:
                    writer.write(b'\xd0\x00')
                elif kind==14:return
                await writer.drain()
        except (asyncio.IncompleteReadError,ConnectionError):pass
        finally:
            self.clients.pop(writer,None)
            writer.close()
            await writer.wait_closed()
    async def publish(self,topic,payload):
        encoded=topic.encode()
        body=struct.pack('>H',len(encoded))+encoded+b'\x00'+payload.encode()
        for writer,filters in list(self.clients.items()):
            # HA subscribes to discovery filters as well as exact measurement topics.
            if any(all(a=='+' or a==b for a,b in zip(f.split('/'),topic.split('/')))
                   and len(f.split('/'))==len(topic.split('/')) for f in filters):
                writer.write(b'\x30'+varint(len(body))+body)
                await writer.drain()

@pytest_asyncio.fixture
async def broker():
    obj=Broker()
    server=await asyncio.start_server(obj.handle,'127.0.0.1',0)
    obj.port=server.sockets[0].getsockname()[1]
    try:yield obj
    finally:
        server.close()
        for writer in list(obj.clients):writer.close()
        await server.wait_closed()
