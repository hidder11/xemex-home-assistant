import json
from pathlib import Path
import pytest

@pytest.mark.parametrize('language', ['en','nl'])
def test_transport_translations_and_explicit_firmware_units(language):
    root=Path(__file__).parents[1]/'candidate/custom_components/xemex'
    text=json.loads((root/'translations'/f'{language}.json').read_text())
    steps=text['config']['step']
    assert set(steps['user']['menu_options'])=={'manual_mqtt','modbus'}
    assert 'base_topic' in steps['manual_mqtt']['data']
    assert set(steps['modbus']['data'])=={'host','port','serial','scan_interval','phase_count','profile','energy_unit'}
    assert '5.1' in steps['modbus']['data_description']['energy_unit']
    assert set(steps['modbus']['data_options']['energy_unit'])=={'Wh','kWh'}
    assert set(steps['modbus']['data_options']['profile'])=={'basic','extended'}
    for error in ['invalid_host','invalid_serial','cannot_connect']:
        assert text['config']['error'][error]
    assert text['config']['abort']['unique_id_mismatch']
    assert text['config']['abort']['reconfigure_successful']
