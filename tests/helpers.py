from homeassistant.config_entries import ConfigEntry, ConfigEntryDisabler

async def add_entry(hass, data, serial='ABC123', disabled=True):
    entry = ConfigEntry(domain='xemex', title=f'Xemex {serial}', data=data,
        version=1, minor_version=1, source='user', unique_id=serial,
        options={}, subentries_data=None, discovery_keys={},
        disabled_by=ConfigEntryDisabler.USER if disabled else None)
    await hass.config_entries.async_add(entry)
    return entry

def discovery(serial='ABC123', payload='{"l1":{"U":230},"l2":{"U":230},"l3":{"U":230}}'):
    from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
    return MqttServiceInfo(topic=f'devices/changed/smart-connect/{serial}/data/power_instant',
        payload=payload, qos=0, retain=False, subscribed_topic='devices/+/smart-connect/+/data/power_instant',timestamp=0.)
