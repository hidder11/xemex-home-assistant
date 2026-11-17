# Xemex Home Assistant Integration

Repository: https://github.com/hidder11/xemex-home-assistant

Read your Xemex Smart Connect in Home Assistant using MQTT or Modbus TCP. Choose the connection when adding the integration. Version: 0.3.0.

## Features

- Sensors for power, voltage, current and, depending on the profile, energy.
- Support for single-phase and three-phase connections.
- MQTT with automatic discovery or a manually configured base topic. Existing MQTT configurations are preserved.
- Modbus TCP with a polling interval of 1–3600 seconds (default: 10 seconds). Read-only: no changes to device settings or firmware.
- Basic Modbus profile (voltage, current and power) and Extended profile (also includes energy and additional measurements).

## Installation

### Via HACS (preferred)

Add this repository as a **custom repository** with type **Integration**. It is not included in the default HACS catalogue. The repository uses `custom_components/xemex` and installs from the default branch; no separate release is required.

If HACS cached an older commit and reports that its version cannot be used, use **Update information** in the repository menu and retry the download from the default branch.

1. Open HACS in Home Assistant and select **Custom repositories** from the top-right menu.
2. Add the GitHub repository URL with the type **Integration**.
3. Find **Xemex** in HACS and download the integration.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration → Xemex**.
6. Choose **MQTT** or **Modbus TCP** and enter the connection details.

### Manual installation (alternative)

1. Copy `custom_components/xemex` from this repository to `custom_components/xemex` in your Home Assistant configuration directory. On a standard installation, the manifest will then be at `/config/custom_components/xemex/manifest.json`. When updating, replace the existing integration directory; make a backup first.
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

## Current source (optional)

Open **Settings → Devices & services → Xemex → Configure** and select the current source:

- **Measured — P1 current** (default): keeps the current reported by the meter. Existing installations remain unchanged.
- **Calculated — |P| / U (estimate)**: calculates each phase's current magnitude from that phase's active power in watts and phase-to-neutral voltage in volts. Export also produces a positive current magnitude. The display defaults to two decimal places; the underlying value is not rounded.

This option works with MQTT and both Modbus profiles, for one- and three-phase meters. It changes the existing L1–L3 current sensors without changing their entity IDs. Saving a different choice automatically reloads the integration. Missing or invalid inputs, zero/negative voltage, and stale or failed measurements make the affected sensor unavailable; there is no silent fallback to the rounded P1 current.

**Accuracy limitation:** active power divided by voltage assumes a power factor of 1. It gives finer resolution than whole-ampere P1 readings but is not a measurement of true RMS current. At lower power factors it can underestimate the actual current. Do not use it as the sole protection for fuses or load balancing. Existing historical current statistics remain attached to the same entities, so their interpretation changes when switching sources.

## Notes

Do not add the same serial number twice, even with different connection types. Modbus settings can be changed later using **Reconfigure**; the serial number remains fixed.

For older firmware that publishes MQTT energy in kWh, the existing MQTT conversion may produce an energy value that is too low. The firmware-dependent unit selection above applies only to Modbus.

## Development

The integration is in `custom_components/xemex/` and tests are in `tests/`. `tests/fixtures/original_mqtt/` contains the original MQTT source code used only for regression tests; do not install it. Test dependencies are listed in `requirements-test.txt` and target Home Assistant 2026.10.4 with Python 3.14. The full suite has also passed on Home Assistant 2026.11.1; for that test environment, use `homeassistant==2026.11.1` and the matching `aiohasupervisor==0.8.1` in place of the older pins. Other Home Assistant versions have not been validated.

Run `python -m pytest tests -v` from the repository in an environment with these dependencies installed. The tests use local simulators and do not replace testing with a physical Smart Connect.
