"""Constants for the Xemex integration."""

from __future__ import annotations

from collections.abc import Mapping
import math
import re
from typing import Any

DOMAIN = "xemex"
CONF_BASE_TOPIC = "base_topic"
CONF_PHASE_COUNT = "phase_count"
CONF_PHASE_DEFAULTS_PENDING = "phase_defaults_pending"
POWER_INSTANT_SUFFIX = "data/power_instant"

PHASE_COUNT_SINGLE = 1
PHASE_COUNT_THREE = 3

BASE_TOPIC_PATTERN = re.compile(r"^devices/[^/]+/smart-connect/[^/]+$")


def base_topic_validation_error(value: str) -> str | None:
    """Return the translation key for an invalid base topic, if any."""
    topic = value.strip().strip("/")
    if not topic:
        return "empty_base_topic"
    if topic.endswith(POWER_INSTANT_SUFFIX):
        return "measurement_topic_included"
    if not BASE_TOPIC_PATTERN.fullmatch(topic):
        return "invalid_base_topic"
    return None


def normalize_base_topic(value: str) -> str | None:
    """Validate and normalize an Xemex Smart Connect MQTT base topic.

    Xemex publishes instantaneous power at
    ``devices/<site>/smart-connect/<serial>/data/power_instant``. The user
    supplies the stable part ending at the serial number.
    """
    if base_topic_validation_error(value) is not None:
        return None
    return value.strip().strip("/")


def serial_from_base_topic(base_topic: str) -> str:
    """Return the Smart Connect serial number from a validated base topic."""
    return base_topic.rsplit("/", maxsplit=1)[-1]


def base_topic_from_measurement_topic(topic: str) -> str | None:
    """Return a validated base topic from an Xemex measurement topic."""
    suffix = f"/{POWER_INSTANT_SUFFIX}"
    if not topic.endswith(suffix):
        return None
    return normalize_base_topic(topic.removesuffix(suffix))


def detect_phase_count(payload: Mapping[str, Any]) -> int | None:
    """Detect a one- or three-phase meter from explicit phase voltages.

    Missing, malformed, or partially populated phase data is inconclusive. This
    prevents an incomplete MQTT message from changing entity defaults.
    """
    phases_present: list[bool] = []
    for phase in range(1, 4):
        phase_payload = payload.get(f"l{phase}")
        if not isinstance(phase_payload, Mapping) or "U" not in phase_payload:
            return None

        voltage = phase_payload["U"]
        if voltage is None:
            phases_present.append(False)
        elif (
            isinstance(voltage, (int, float))
            and not isinstance(voltage, bool)
            and math.isfinite(voltage)
        ):
            phases_present.append(True)
        else:
            return None

    if phases_present == [True, False, False]:
        return PHASE_COUNT_SINGLE
    if phases_present == [True, True, True]:
        return PHASE_COUNT_THREE
    return None
