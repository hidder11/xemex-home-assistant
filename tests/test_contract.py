from dataclasses import asdict
import importlib.util
from pathlib import Path
import sys
import pytest
from helpers import discovery


def test_all_mqtt_descriptions_and_units_identical_to_immutable_baseline():
    from custom_components.xemex.sensor import SENSORS
    path=Path(__file__).parents[1]/'baseline/custom_components/xemex/sensor.py'
    name='custom_components.xemex._baseline_sensor'
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    try:
        # Execute a source read: never create __pycache__ inside the baseline.
        exec(compile(path.read_text(), str(path), 'exec'), module.__dict__)
        assert [asdict(d) for d in SENSORS]==[asdict(d) for d in module.SENSORS]
        assert len(SENSORS)==53
    finally:
        sys.modules.pop(name,None)

@pytest.mark.parametrize('phases,expected', [([230,None,None],1),([230,230,230],3),
    ([0,0,0],3),([230,'bad',None],None),([230,float('nan'),None],None)])
def test_mqtt_phase_detection_preserved(phases,expected):
    from custom_components.xemex.const import detect_phase_count
    assert detect_phase_count({f'l{i}':{'U':v} for i,v in enumerate(phases,1)})==expected

@pytest.mark.parametrize('topic,error', [('', 'empty_base_topic'),
    ('devices/site/smart-connect/SERIAL/data/power_instant','measurement_topic_included'),
    ('devices/site/other/SERIAL','invalid_base_topic')])
@pytest.mark.asyncio
async def test_native_mqtt_topic_validation_without_mqtt(hass,topic,error):
    flow=await hass.config_entries.flow.async_init('xemex',context={'source':'user'})
    flow=await hass.config_entries.flow.async_configure(flow['flow_id'],{'next_step_id':'manual_mqtt'})
    result=await hass.config_entries.flow.async_configure(flow['flow_id'],{'base_topic':topic})
    assert result['errors']=={'base_topic':error}

@pytest.mark.parametrize('payload', ['not json','[]','null'])
@pytest.mark.asyncio
async def test_invalid_discovery_payload_preserved(hass,payload):
    result=await hass.config_entries.flow.async_init('xemex',context={'source':'mqtt'},data=discovery(payload=payload))
    assert result['reason']=='invalid_discovery_payload'

@pytest.mark.asyncio
async def test_invalid_discovery_topic_preserved(hass):
    info=discovery()
    info.topic='other/topic'
    result=await hass.config_entries.flow.async_init('xemex',context={'source':'mqtt'},data=info)
    assert result['reason']=='invalid_discovery_topic'
