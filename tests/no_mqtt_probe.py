"""Fresh-process HA setup with MQTT and Paho imports forbidden."""
import asyncio
import importlib.abc
from pathlib import Path
import shutil
import sys
import tempfile

class ForbidMQTT(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'homeassistant.components.mqtt' or fullname == 'paho' or fullname.startswith('paho.'):
            raise AssertionError(f'Modbus attempted MQTT dependency: {fullname}')
        return None

sys.meta_path.insert(0,ForbidMQTT())

async def main():
    from homeassistant import loader,bootstrap
    from homeassistant.core import HomeAssistant
    with tempfile.TemporaryDirectory(prefix='xemex-no-mqtt-') as tmp:
        shutil.copytree(Path(sys.argv[1])/'custom_components',Path(tmp)/'custom_components')
        (Path(tmp)/'custom_components/__init__.py').touch()
        (Path(tmp)/'configuration.yaml').write_text('{}\n')
        hass=HomeAssistant(tmp)
        hass.config.skip_pip=True
        bootstrap.DEFAULT_INTEGRATIONS=set()
        loader.async_setup(hass)
        try:
            assert await bootstrap.async_from_config_dict({'homeassistant':{
                'name':'No MQTT probe','latitude':52.,'longitude':5.,'elevation':0,
                'time_zone':'Europe/Amsterdam','country':'NL','unit_system':'metric'},'sensor':[]},hass)
            flow=await hass.config_entries.flow.async_init('xemex',context={'source':'user'})
            assert flow['type']=='menu'
            mqtt_flow=await hass.config_entries.flow.async_configure(flow['flow_id'],{'next_step_id':'manual_mqtt'})
            mqtt_flow=await hass.config_entries.flow.async_configure(mqtt_flow['flow_id'],{'base_topic':'devices/site/smart-connect/ABC'})
            assert mqtt_flow['errors']=={'base_topic':'mqtt_not_configured'}
            hass.config_entries.flow.async_abort(mqtt_flow['flow_id'])
            flow=await hass.config_entries.flow.async_init('xemex',context={'source':'user'})
            flow=await hass.config_entries.flow.async_configure(flow['flow_id'],{'next_step_id':'modbus'})
            result=await hass.config_entries.flow.async_configure(flow['flow_id'],{
                'host':'127.0.0.1','port':int(sys.argv[2]),'serial':'NO-MQTT','scan_interval':10,
                'phase_count':3,'profile':'basic','energy_unit':'Wh'})
            assert result['type']=='create_entry',result
            await hass.async_block_till_done()
            entry=result['result']
            assert entry.state.value=='loaded',entry.state
            assert len(hass.states.async_all('sensor'))==10
            assert 'homeassistant.components.mqtt' not in sys.modules
            assert 'paho' not in sys.modules
            assert await hass.config_entries.async_unload(entry.entry_id)
            print('PASS: real HA Modbus flow/setup/10 sensors/unload; MQTT/Paho imports forbidden')
        finally:
            await hass.async_stop()

if __name__=='__main__':asyncio.run(main())
