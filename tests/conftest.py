from pathlib import Path
import shutil
import sys
import pytest_asyncio

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'candidate'))

@pytest_asyncio.fixture
async def hass(tmp_path, monkeypatch):
    from homeassistant import loader
    from homeassistant.bootstrap import async_from_config_dict
    from homeassistant.core import HomeAssistant
    shutil.copytree(ROOT / 'candidate/custom_components', tmp_path / 'custom_components')
    (tmp_path / 'custom_components/__init__.py').touch()
    (tmp_path / 'configuration.yaml').write_text('{}\n')
    instance = HomeAssistant(str(tmp_path))
    instance.config.skip_pip = True
    loader.async_setup(instance)
    monkeypatch.setattr('homeassistant.bootstrap.DEFAULT_INTEGRATIONS', set())
    try:
        assert await async_from_config_dict({'homeassistant': {
            'name': 'Xemex offline QA', 'latitude': 52., 'longitude': 5.,
            'elevation': 0, 'unit_system': 'metric', 'time_zone': 'Europe/Amsterdam',
            'country': 'NL'}, 'sensor': [], 'persistent_notification': {}}, instance)
        yield instance
    finally:
        import asyncio
        async with asyncio.timeout(10):
            for entry in instance.config_entries.async_entries('xemex'):
                if entry.state.value == 'loaded':
                    await instance.config_entries.async_unload(entry.entry_id)
            await instance.async_stop()
