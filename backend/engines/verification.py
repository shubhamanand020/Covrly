"""Claim verification engine."""

from __future__ import annotations

from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any, Dict, List, Mapping, Optional, Tuple

LOCATION_MATCH_RADIUS_KM = 3.0
TIMESTAMP_MATCH_WINDOW_SECONDS = 3 * 60 * 60


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _parse_time_component(value: str) -> Optional[Tuple[int, int]]:
    parts = value.split(":")
    if len(parts) < 2:
        return None

    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    return (hour, minute)


def _metadata_timestamp(image_metadata: Mapping[str, Any]) -> Optional[datetime]:
    # Prefer a direct timestamp if provided.
    direct = _parse_datetime(image_metadata.get("timestamp"))
    if direct is not None:
        return direct

    date_value = str(image_metadata.get("date") or "").strip()
    if not date_value:
        return None

    time_value = str(image_metadata.get("time") or "").strip()
    if not time_value:
        time_range = str(image_metadata.get("time_range") or "").strip()
        if time_range:
            time_value = time_range.split("-")[0].strip()

    if not time_value:
        time_value = "00:00"

    parsed_time = _parse_time_component(time_value)
    if parsed_time is None:
        return None

    composed = f"{date_value}T{parsed_time[0]:02d}:{parsed_time[1]:02d}:00+00:00"
    return _parse_datetime(composed)


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _extract_coordinates(source: Any) -> Optional[Tuple[float, float]]:
    if isinstance(source, Mapping):
        lat = _to_float(_coalesce_mapping_value(source, "lat", "latitude"))
        lng = _to_float(_coalesce_mapping_value(source, "lng", "long", "longitude"))
        if lat is None or lng is None:
            return None
        return (lat, lng)

    if isinstance(source, (list, tuple)) and len(source) == 2:
        lat = _to_float(source[0])
        lng = _to_float(source[1])
        if lat is None or lng is None:
            return None
        return (lat, lng)

    if isinstance(source, str):
        parts = [part.strip() for part in source.split(",") if part.strip()]
        if len(parts) != 2:
            return None
        lat = _to_float(parts[0])
        lng = _to_float(parts[1])
        if lat is None or lng is None:
            return None
        return (lat, lng)

    return None


def _haversine_km(origin: Tuple[float, float], target: Tuple[float, float]) -> float:
    lat1, lng1 = origin
    lat2, lng2 = target

    earth_radius_km = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lng = radians(lng2 - lng1)
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)

    a = sin(d_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(d_lng / 2) ** 2
    c = 2 * asin(min(1.0, sqrt(a)))
    return earth_radius_km * c


def _location_match(image_metadata: Mapping[str, Any], trigger_event: Mapping[str, Any]) -> bool:
    metadata_location = (
        _extract_coordinates(image_metadata.get("location"))
        or _extract_coordinates(image_metadata.get("location_text"))
        or _extract_coordinates(image_metadata.get("user_location"))
    )

    trigger_location = (
        _extract_coordinates(trigger_event.get("location"))
        or _extract_coordinates(trigger_event.get("user_location"))
    )

    if metadata_location is None or trigger_location is None:
        return False

    return _haversine_km(metadata_location, trigger_location) <= LOCATION_MATCH_RADIUS_KM


def _timestamp_match(image_metadata: Mapping[str, Any], trigger_event: Mapping[str, Any]) -> bool:
    claim_time = _metadata_timestamp(image_metadata)
    trigger_time = (
        _parse_datetime(trigger_event.get("timestamp"))
        or _parse_datetime(trigger_event.get("event_time"))
        or _parse_datetime(trigger_event.get("recorded_at"))
    )

    if claim_time is None or trigger_time is None:
        return False

    delta_seconds = abs((claim_time - trigger_time).total_seconds())
    return delta_seconds <= TIMESTAMP_MATCH_WINDOW_SECONDS


def verification_engine(
    image_metadata: Mapping[str, Any] | None,
    trigger_event: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Verify delayed claims using metadata and stored trigger event context."""
    metadata = dict(image_metadata or {})
    event = dict(trigger_event or {})

    metadata_present = bool(metadata)
    location_match = _location_match(metadata, event)
    timestamp_match = _timestamp_match(metadata, event)

    confidence = 0.0
    if metadata_present:
        confidence += 0.4
    if location_match:
        confidence += 0.3
    if timestamp_match:
        confidence += 0.3

    confidence_score = round(max(0.0, min(confidence, 1.0)), 2)

    if confidence_score >= 0.8:
        verification_status = "verified"
    elif confidence_score >= 0.5:
        verification_status = "needs_review"
    else:
        verification_status = "failed"

    return {
        "verification_status": verification_status,
        "confidence_score": confidence_score,
    }


def assess_verification(
    claim_data: Dict[str, Any],
    fraud: Dict[str, Any],
    trigger: Dict[str, Any],
    policy_match: Dict[str, Any],
) -> Dict[str, Any]:
    """Backward-compatible wrapper used by the pipeline decision flow."""
    reasons: List[str] = []

    if not policy_match.get("matched"):
        reasons.append("Policy not found")

    if float(fraud.get("fraud_score", 0.0)) >= 0.55:
        reasons.append("Fraud score above manual threshold")

    if not trigger.get("trigger"):
        reasons.append("No external trigger detected for manual claim")

    image_metadata = claim_data.get("image_metadata")
    if not isinstance(image_metadata, Mapping):
        image_metadata = {
            "location_text": claim_data.get("location"),
            "date": claim_data.get("date"),
            "time": claim_data.get("time"),
        }

    trigger_event = {
        "location": claim_data.get("location"),
        "timestamp": f"{claim_data.get('date', '')}T{claim_data.get('time', '')}:00+00:00",
        **trigger,
    }
    verification = verification_engine(image_metadata=image_metadata, trigger_event=trigger_event)

    if verification.get("verification_status") != "verified":
        reasons.append("Metadata verification mismatch")

    verification_required = bool(reasons) and bool(policy_match.get("matched"))

    return {
        "verification_required": verification_required,
        "reasons": reasons,
        "verification_status": verification.get("verification_status"),
        "confidence_score": verification.get("confidence_score"),
    }


def verify_claim(data: Dict[str, Any]) -> Dict[str, Any]:
    """Standardized payload-based verification entrypoint for pipeline use."""
    image_metadata = data.get("image_metadata")
    if not isinstance(image_metadata, Mapping):
        image_metadata = {}

    trigger_event = data.get("trigger_event")
    if not isinstance(trigger_event, Mapping):
        trigger_event = {
            "location": data.get("user_location"),
            "timestamp": data.get("timestamp"),
            "trigger_type": data.get("trigger_type"),
        }

    return verification_engine(image_metadata=image_metadata, trigger_event=trigger_event)
