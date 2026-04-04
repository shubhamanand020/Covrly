"""Environmental trigger detection engine."""

from datetime import datetime
from typing import Any, Dict, Optional

RAINFALL_THRESHOLD = 70.0
TEMPERATURE_THRESHOLD = 49.0
AQI_THRESHOLD = 500.0

DEFAULT_PAYOUT_BY_DISRUPTION = {
    "heavy rain": 8000.0,
    "road blockade": 5000.0,
    "civic unrest": 6500.0,
    "heat wave": 7000.0,
    "poor air quality": 6000.0,
}


def _normalize(text: str) -> str:
    return text.strip().lower()


def _to_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    if isinstance(value, str) and not value.strip():
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def environmental_trigger_engine(rainfall: Any, temperature: Any, AQI: Any) -> Dict[str, Any]:
    """Detect environmental triggers from weather and air quality signals."""
    rainfall_value = _to_optional_float(rainfall)
    temperature_value = _to_optional_float(temperature)
    aqi_value = _to_optional_float(AQI)

    trigger_types = []
    if rainfall_value is not None and rainfall_value > RAINFALL_THRESHOLD:
        trigger_types.append("Heavy Rain")
    if temperature_value is not None and temperature_value > TEMPERATURE_THRESHOLD:
        trigger_types.append("Heat Wave")
    if aqi_value is not None and aqi_value > AQI_THRESHOLD:
        trigger_types.append("Poor Air Quality")

    trigger_detected = bool(trigger_types)
    trigger_type = " | ".join(trigger_types) if trigger_detected else "No Active Trigger"

    return {
        "trigger_detected": trigger_detected,
        "trigger_type": trigger_type,
    }


def detect_environmental_trigger(data: Dict[str, Any]) -> Dict[str, Any]:
    timestamp_value = data.get("timestamp")
    hour = 0

    if isinstance(timestamp_value, str) and timestamp_value.strip():
        try:
            parsed = datetime.fromisoformat(timestamp_value.strip().replace("Z", "+00:00"))
            hour = parsed.hour
        except ValueError:
            hour = 0

    trigger_detected = 18 <= hour <= 22
    trigger_type = "heavy_rain" if trigger_detected else "none"

    print("ENV TRIGGER:", trigger_detected, trigger_type)

    return {
        "trigger_detected": trigger_detected,
        "trigger_type": trigger_type,
    }


def detect_trigger(claim_data: Dict[str, Any]) -> Dict[str, Any]:
    policy = str(claim_data.get("policy", "HeatGuard")) or "HeatGuard"
    trigger_result = detect_environmental_trigger(claim_data)

    trigger_detected = bool(trigger_result.get("trigger_detected", False))
    trigger_type = str(trigger_result.get("trigger_type", "No Active Trigger"))

    disruption = trigger_type.replace("_", " ").title() if trigger_detected else "No Active Trigger"
    payout = DEFAULT_PAYOUT_BY_DISRUPTION.get(_normalize(disruption), 0.0)

    return {
        "trigger": trigger_detected,
        "disruption": disruption,
        "policy": policy,
        "eligible_payout": payout,
    }


def preview_trigger(policy: str, disruption: str) -> Dict[str, Any]:
    normalized = _normalize(disruption)
    payout = DEFAULT_PAYOUT_BY_DISRUPTION.get(normalized, 8000.0)

    if normalized in DEFAULT_PAYOUT_BY_DISRUPTION:
        canonical_disruption = normalized.title()
    else:
        canonical_disruption = disruption or "Heavy Rain"

    return {
        "trigger": True,
        "disruption": canonical_disruption,
        "policy": policy,
        "eligible_payout": payout,
    }
