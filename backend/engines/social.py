"""Social disruption analysis engine."""

from datetime import datetime
from typing import Any, Dict, Mapping

TRAFFIC_DROP_THRESHOLD = 70.0
DELIVERY_DROP_THRESHOLD = 80.0


def social_disruption_engine(
    traffic_drop: float,
    delivery_activity_drop: float,
    weather: str = "normal",
) -> Dict[str, Any]:
    """Detect social disruption from structured (simulated) activity signals."""
    traffic = float(traffic_drop)
    delivery = float(delivery_activity_drop)
    weather_status = str(weather or "normal").strip().lower()

    disruption_detected = (
        weather_status == "normal"
        and traffic > TRAFFIC_DROP_THRESHOLD
        and delivery > DELIVERY_DROP_THRESHOLD
    )

    event_type = "Traffic and Delivery Collapse" if disruption_detected else "No Social Disruption"

    return {
        "disruption_detected": bool(disruption_detected),
        "event_type": event_type,
    }


def _simulate_structured_inputs(claim_data: Mapping[str, Any]) -> Dict[str, Any]:
    weather = str(claim_data.get("weather", "normal")).strip().lower() or "normal"

    traffic_drop_value = claim_data.get("traffic_drop")
    delivery_drop_value = claim_data.get("delivery_activity_drop")

    if traffic_drop_value is not None and delivery_drop_value is not None:
        return {
            "weather": weather,
            "traffic_drop": float(traffic_drop_value),
            "delivery_activity_drop": float(delivery_drop_value),
        }

    # No real APIs exist yet, so derive deterministic simulated drops from claim text.
    subject = str(claim_data.get("subject", "")).lower()
    location = str(claim_data.get("location", "")).lower()
    combined = f"{subject} {location}"

    disruption_keywords = ("road blockade", "blockade", "strike", "protest", "civic unrest")
    has_disruption_signal = any(keyword in combined for keyword in disruption_keywords)

    return {
        "weather": weather,
        "traffic_drop": 78.0 if has_disruption_signal else 42.0,
        "delivery_activity_drop": 85.0 if has_disruption_signal else 48.0,
    }


def analyze_social_disruption(claim_data: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible adapter used by the pipeline."""
    inputs = _simulate_structured_inputs(claim_data)
    result = social_disruption_engine(
        traffic_drop=inputs["traffic_drop"],
        delivery_activity_drop=inputs["delivery_activity_drop"],
        weather=inputs["weather"],
    )

    disruption_detected = bool(result["disruption_detected"])

    return {
        **result,
        "weather": inputs["weather"],
        "traffic_drop": round(float(inputs["traffic_drop"]), 2),
        "delivery_activity_drop": round(float(inputs["delivery_activity_drop"]), 2),
        "social_score": 0.82 if disruption_detected else 0.2,
        "severity": "high" if disruption_detected else "low",
    }


def detect_social_disruption(data: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic social trigger simulation using location zone and hour."""
    user_location = data.get("user_location") if isinstance(data, dict) else None
    latitude = 0.0

    if isinstance(user_location, Mapping):
        try:
            latitude = float(user_location.get("lat", 0.0))
        except (TypeError, ValueError):
            latitude = 0.0

    timestamp_value = data.get("timestamp") if isinstance(data, dict) else None
    hour = 0
    if isinstance(timestamp_value, str) and timestamp_value.strip():
        try:
            parsed = datetime.fromisoformat(timestamp_value.strip().replace("Z", "+00:00"))
            hour = parsed.hour
        except ValueError:
            hour = 0

    zone = "A" if latitude > 12.95 else "B"
    disruption_detected = zone == "A" and 20 <= hour <= 22
    event_type = "curfew" if disruption_detected else "none"

    print("SOCIAL TRIGGER:", disruption_detected, event_type, zone)

    return {
        "disruption_detected": disruption_detected,
        "event_type": event_type,
        "zone": zone,
    }
