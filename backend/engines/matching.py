"""Policy matching engine."""

from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Dict, List, Optional

EARTH_RADIUS_KM = 6371.0088
DEFAULT_MAX_DISTANCE_KM = 2.0
DEFAULT_MAX_TIME_WINDOW_SECONDS = 30.0 * 60.0

POLICIES: List[Dict[str, Any]] = [
    {
        "name": "HeatGuard",
        "coverage": "Weather-triggered commute coverage",
        "zone": "Urban Zone A",
        "valid_till": "2026-12-31",
        "premium_weekly": 149,
        "max_coverage": 10000,
        "triggers": ["Heavy Rain", "Road Blockade"],
    },
    {
        "name": "RainSure Cover",
        "coverage": "Rainfall disruption protection",
        "zone": "Metro Zone B",
        "valid_till": "2026-10-31",
        "premium_weekly": 129,
        "max_coverage": 8500,
        "triggers": ["Heavy Rain"],
    },
    {
        "name": "CivicShield Cover",
        "coverage": "Civil event disruption support",
        "zone": "City Core",
        "valid_till": "2026-11-30",
        "premium_weekly": 169,
        "max_coverage": 12000,
        "triggers": ["Road Blockade", "Civic Unrest"],
    },
    {
        "name": "Holistic Cover",
        "coverage": "Multi-trigger comprehensive policy",
        "zone": "Nationwide",
        "valid_till": "2027-01-31",
        "premium_weekly": 219,
        "max_coverage": 15000,
        "triggers": ["Heavy Rain", "Road Blockade", "Civic Unrest"],
    },
]


def get_policies_catalog() -> List[Dict[str, Any]]:
    return [policy.copy() for policy in POLICIES]


def match_policy(claim_data: Dict[str, Any]) -> Dict[str, Any]:
    policy_name = str(claim_data.get("policy", "")).strip()
    matched_policy: Optional[Dict[str, Any]] = next(
        (policy for policy in POLICIES if policy["name"].lower() == policy_name.lower()),
        None,
    )

    if matched_policy is None:
        return {
            "matched": False,
            "policy_name": policy_name,
            "max_coverage": 0,
            "policy": None,
        }

    return {
        "matched": True,
        "policy_name": matched_policy["name"],
        "max_coverage": matched_policy["max_coverage"],
        "policy": matched_policy,
    }


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty ISO string")

    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _extract_location(value: Any) -> tuple[float, float]:
    if isinstance(value, (tuple, list)) and len(value) == 2:
        latitude = float(value[0])
        longitude = float(value[1])
    elif isinstance(value, dict):
        latitude = float(value.get("lat", value.get("latitude")))
        longitude = float(value.get("long", value.get("lng", value.get("longitude"))))
    else:
        raise ValueError("location must be a tuple/list or dict with lat/long")

    if not (-90.0 <= latitude <= 90.0):
        raise ValueError("latitude out of range")
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError("longitude out of range")

    return (latitude, longitude)


def _haversine_distance_km(start: tuple[float, float], end: tuple[float, float]) -> float:
    lat1, lon1 = start
    lat2, lon2 = end

    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    a = sin(delta_phi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2.0) ** 2
    c = 2.0 * atan2(sqrt(a), sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def claim_matching_engine(
    user_location: Any,
    timestamp: Any,
    recorded_triggers: Any,
) -> Dict[str, bool]:
    """
    Match a claim against recorded trigger events using proximity, time, and trigger type.

    Inputs:
    - user_location: mapping/tuple with claim coordinates; mapping may include optional trigger_type
    - timestamp: ISO datetime string (or datetime)
    - recorded_triggers: iterable of trigger events with location, timestamp, trigger_type
    """
    claim_location = _extract_location(user_location)
    claim_timestamp = _parse_timestamp(timestamp)

    expected_trigger_type = ""
    if isinstance(user_location, dict):
        expected_trigger_type = str(user_location.get("trigger_type", "")).strip().lower()

    if not isinstance(recorded_triggers, list):
        return {"match_found": False}

    for event in recorded_triggers:
        if not isinstance(event, dict):
            continue

        try:
            event_location = _extract_location(event.get("location"))
            event_timestamp = _parse_timestamp(event.get("timestamp"))
        except (TypeError, ValueError):
            continue

        distance = _haversine_distance_km(claim_location, event_location)
        if distance > DEFAULT_MAX_DISTANCE_KM:
            continue

        time_delta_seconds = abs((event_timestamp - claim_timestamp).total_seconds())
        if time_delta_seconds > DEFAULT_MAX_TIME_WINDOW_SECONDS:
            continue

        event_trigger_type = str(event.get("trigger_type", "")).strip().lower()
        if not event_trigger_type:
            continue

        if expected_trigger_type and expected_trigger_type != event_trigger_type:
            continue

        return {"match_found": True}

    return {"match_found": False}


def match_claim_with_triggers(data: Dict[str, Any]) -> Dict[str, bool]:
    """Standardized payload-based wrapper for trigger matching."""
    user_location = data.get("user_location")
    timestamp = data.get("timestamp")
    recorded_triggers = data.get("recorded_triggers", [])

    if isinstance(user_location, dict):
        location_payload: Dict[str, Any] = {
            "lat": user_location.get("lat"),
            "long": user_location.get("long"),
        }
        trigger_type = str(data.get("trigger_type", "")).strip()
        if trigger_type:
            location_payload["trigger_type"] = trigger_type
    else:
        location_payload = user_location

    return claim_matching_engine(
        user_location=location_payload,
        timestamp=timestamp,
        recorded_triggers=recorded_triggers,
    )
