"""Movement analysis engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Dict, Mapping, Sequence, Tuple

# Mean Earth radius in kilometers.
EARTH_RADIUS_KM = 6371.0088
UNREALISTIC_SPEED_KMH = 120.0
SUDDEN_JUMP_DISTANCE_KM = 5.0
SUDDEN_JUMP_WINDOW_SECONDS = 120.0

LocationTuple = Tuple[float, float, datetime]


def _coalesce_mapping_value(source: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key not in source:
            continue
        value = source.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)

    if isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        if not normalized:
            raise ValueError("timestamp cannot be empty")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)

    raise ValueError("timestamp must be datetime, ISO string, or unix timestamp")


def _extract_location(location: Any, fallback_timestamp: Any = None) -> LocationTuple:
    if isinstance(location, Mapping):
        lat_raw = _coalesce_mapping_value(location, "lat", "latitude")
        long_raw = _coalesce_mapping_value(location, "lng", "long", "longitude")
        ts_raw = _coalesce_mapping_value(location, "timestamp")
        if ts_raw is None:
            ts_raw = fallback_timestamp
    elif isinstance(location, Sequence) and not isinstance(location, (str, bytes)):
        if len(location) not in (2, 3):
            raise ValueError("location sequence must be [lat, long] or [lat, long, timestamp]")
        lat_raw = location[0]
        long_raw = location[1]
        ts_raw = location[2] if len(location) == 3 else fallback_timestamp
    else:
        raise ValueError("location must be an object or sequence")

    try:
        latitude = float(lat_raw)
        longitude = float(long_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("location must include numeric lat and long") from exc

    if not (-90.0 <= latitude <= 90.0):
        raise ValueError("latitude out of range")
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError("longitude out of range")

    if ts_raw is None:
        raise ValueError("location timestamp is required to estimate speed")

    timestamp = _parse_timestamp(ts_raw)
    return (latitude, longitude, timestamp)


def _haversine_distance_km(previous: LocationTuple, current: LocationTuple) -> float:
    lat1, lon1, _ = previous
    lat2, lon2, _ = current

    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    a = sin(delta_phi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2.0) ** 2
    c = 2.0 * atan2(sqrt(a), sqrt(1.0 - a))

    return EARTH_RADIUS_KM * c


def _speed_kmh(distance_km: float, elapsed_seconds: float) -> float:
    if elapsed_seconds <= 0:
        raise ValueError("current timestamp must be later than previous timestamp")
    return distance_km / (elapsed_seconds / 3600.0)


def movement_analysis_engine(previous_location: Any, current_location: Any) -> Dict[str, Any]:
    """Analyze movement and detect sudden-jump or unrealistic-speed anomalies."""
    previous = _extract_location(previous_location)
    current = _extract_location(current_location)

    distance = _haversine_distance_km(previous, current)
    elapsed_seconds = (current[2] - previous[2]).total_seconds()
    speed = _speed_kmh(distance, elapsed_seconds)

    sudden_jump = distance >= SUDDEN_JUMP_DISTANCE_KM and elapsed_seconds <= SUDDEN_JUMP_WINDOW_SECONDS
    unrealistic_speed = speed >= UNREALISTIC_SPEED_KMH
    anomaly_flag = bool(sudden_jump or unrealistic_speed)

    return {
        "distance": round(distance, 3),
        "speed": round(speed, 2),
        "anomaly_flag": anomaly_flag,
        # Backward-compatible alias used by the fraud scoring engine.
        "anomaly_detected": anomaly_flag,
    }


def analyze_movement(claim_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compatibility wrapper for pipeline callers that pass a claim object."""
    previous_location = claim_data.get("previous_location")
    current_location = claim_data.get("current_location")

    if current_location is None and isinstance(claim_data.get("user_location"), Mapping):
        user_location = claim_data["user_location"]
        current_location = {
            "lat": _coalesce_mapping_value(user_location, "lat", "latitude"),
            "long": _coalesce_mapping_value(user_location, "lng", "long", "longitude"),
            "timestamp": claim_data.get("timestamp"),
        }

    if current_location is None:
        return {
            "distance": 0.0,
            "speed": 0.0,
            "anomaly_flag": False,
            "anomaly_detected": False,
        }

    if previous_location is None:
        current_ts = _extract_location(current_location)[2]
        parsed_current = _extract_location(current_location, fallback_timestamp=current_ts)
        previous_location = {
            "lat": parsed_current[0],
            "long": parsed_current[1],
            "timestamp": (parsed_current[2] - timedelta(minutes=5)).isoformat(),
        }

    return movement_analysis_engine(previous_location, current_location)
