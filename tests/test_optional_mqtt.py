import asyncio
from pathlib import Path
import sys
import pytest
from simulator import meter

@pytest.mark.asyncio
async def test_modbus_fresh_process_with_mqtt_imports_forbidden(meter, tmp_path):
    root=Path(__file__).parents[1]
    process=await asyncio.create_subprocess_exec(sys.executable,
        str(root/'tests/no_mqtt_probe.py'),str(root),str(meter.port),
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
    async with asyncio.timeout(45):
        output,_=await process.communicate()
    (tmp_path/'no-mqtt-probe.txt').write_bytes(output)
    assert process.returncode==0,output.decode()
    assert b'MQTT/Paho imports forbidden' in output
