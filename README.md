# Xemex Home Assistant Integration

Repository: https://github.com/hidder11/xemex-home-assistant

Read your Xemex Smart Connect in Home Assistant using MQTT or Modbus TCP. Choose the connection when adding the integration. Version: 0.2.0.

## Features

- Sensors for power, voltage, current and, depending on the profile, energy.
- Support for single-phase and three-phase connections.
- MQTT with automatic discovery or a manually configured base topic. Existing MQTT configurations are preserved.
- Modbus TCP with a polling interval of 1–3600 seconds (default: 10 seconds). Read-only: no changes to device settings or firmware.
- Basic Modbus profile (voltage, current and power) and Extended profile (also includes energy and additional measurements).

## Installation

### Via HACS (preferred)

Note: this repository is not yet ready for HACS installation. The integration must first be moved into the required HACS directory structure. Publishing the repository on GitHub alone does not make it installable through HACS; use manual installation for now.

Once available:

1. Open HACS in Home Assistant and select **Custom repositories** from the top-right menu.
2. Add the GitHub repository URL with the type **Integration**.
3. Find **Xemex** in HACS and download the integration.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration → Xemex**.
6. Choose **MQTT** or **Modbus TCP** and enter the connection details.

### Manual installation (alternative)

1. Copy `candidate/custom_components/xemex` from this repository to `custom_components/xemex` in your Home Assistant configuration directory. On a standard installation, the manifest will then be at `/config/custom_components/xemex/manifest.json`. When updating, replace the existing integration directory; make a backup first.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Xemex**.
4. Choose **MQTT** or **Modbus TCP** and enter the connection details.

### MQTT setup

First configure the Home Assistant MQTT integration and have the Smart Connect publish to the same broker. Enter `devices/<site>/smart-connect/<serial_number>` as the base topic, without `/data/power_instant`.

The Xemex Smart Connect only supports MQTTS (MQTT over TLS) with a valid broker certificate. Supplying your own certificate to Xemex and using unencrypted MQTT are not supported. In response to the user's request, Xemex stated that neither option is planned in the short term for security reasons. Make sure the broker uses a certificate that the Smart Connect accepts.

### Modbus TCP setup

Enter the IP address or hostname, TCP port (default: 502) and Smart Connect serial number printed on the label. Choose the polling interval, number of phases and register profile.

For the energy unit, choose **Wh** for firmware V5.1.x or newer and **kWh** for older firmware. Check your device's firmware version before choosing.

The Smart Connect supports only one Modbus TCP client at a time. Do not use this connection alongside a charging station, EMS or another Modbus client. A polling interval of 1 second does not mean the meter provides new data every second.

## Notes

Do not add the same serial number twice, even with different connection types. Modbus settings can be changed later using **Reconfigure**; the serial number remains fixed.

For older firmware that publishes MQTT energy in kWh, the existing MQTT conversion may produce an energy value that is too low. The firmware-dependent unit selection above applies only to Modbus.

## Development

The integration is in `candidate/custom_components/xemex/` and tests are in `tests/`. `baseline/` contains the original MQTT source code for regression tests; do not install that directory. Test dependencies are listed in `requirements-test.txt`. Local tests target Home Assistant 2026.10.4 and Python 3.14; other versions have not been validated.

Run `python -m pytest tests -v` from the repository in an environment with these dependencies installed. The tests use local simulators and do not replace testing with a physical Smart Connect.
