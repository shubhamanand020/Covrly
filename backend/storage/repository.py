"""MongoDB-backed persistence for triggers, claims, and user fraud profiles."""

from __future__ import annotations

from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Dict, List, Mapping, Optional, Tuple
from uuid import uuid4

from backend.storage.mongo_db import get_db
from backend.storage.mongo_repository import (
    update_claim_snapshot,
    upsert_claim_snapshot,
    upsert_trigger_snapshot,
)

EARTH_RADIUS_METERS = 6371000.0

def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty ISO string")

    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)

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

def _extract_location(source: Mapping[str, Any]) -> Tuple[float, float]:
    latitude = float(_coalesce_mapping_value(source, "lat", "latitude"))
    longitude = float(_coalesce_mapping_value(source, "lng", "long", "longitude"))
    return (latitude, longitude)

def _haversine_meters(start: Tuple[float, float], end: Tuple[float, float]) -> float:
    lat1, lon1 = start
    lat2, lon2 = end

    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    a = sin(delta_phi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2.0) ** 2
    c = 2.0 * atan2(sqrt(a), sqrt(1.0 - a))

    return EARTH_RADIUS_METERS * c

def _normalize_policy(value: Any) -> str:
    return str(value or "").strip().lower()

def _doc_to_dict(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    item = dict(doc)
    if "_id" in item and "id" not in item:
        item["id"] = item["_id"]
    if "_id" in item:
        del item["_id"]
    return item

def record_trigger_event(
    location: Mapping[str, Any],
    timestamp: Any,
    trigger_type: str,
    fraud_score: float,
    policy_types: Optional[List[str]] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    parsed_timestamp = _parse_timestamp(timestamp)
    latitude, longitude = _extract_location(location)
    normalized_user_id = str(user_id or "system").strip() or "system"

    trigger_id = f"trg_{uuid4().hex[:12]}"
    trigger_record = {
        "trigger_id": trigger_id,
        "user_id": normalized_user_id,
        "location": {"lat": latitude, "lng": longitude},
        "timestamp": parsed_timestamp.isoformat(),
        "trigger_type": str(trigger_type).strip(),
        "fraud_score": float(fraud_score),
        "policy_types": [str(policy).strip() for policy in (policy_types or [])],
    }

    try:
        # Also syncs to primary triggers collection via mongo_repository equivalent logic
        upsert_trigger_snapshot(trigger_record)
    except Exception:
        # Keep claim flow resilient
        pass

    return trigger_record

def has_recent_similar_trigger(
    *,
    user_id: str,
    trigger_type: str,
    location: Mapping[str, Any],
    timestamp: Any,
    max_distance_meters: float = 100.0,
    max_time_window_seconds: float = 5 * 60,
) -> bool:
    normalized_user_id = str(user_id or "system").strip() or "system"
    normalized_trigger_type = str(trigger_type or "").strip().lower()

    if not normalized_trigger_type:
        return False

    try:
        current_timestamp = _parse_timestamp(timestamp)
        current_location = _extract_location(location)
    except Exception:
        return False

    db = get_db()
    # Fetch recent triggers to verify distance
    cursor = db.triggers.find(
        {"user_id": normalized_user_id, "trigger_type": normalized_trigger_type}
    ).sort("timestamp", -1).limit(20)
    
    triggers = list(cursor)

    for trigger in triggers:
        try:
            existing_timestamp = _parse_timestamp(trigger.get("timestamp"))
            existing_location = _extract_location(trigger.get("location", {}))
        except Exception:
            continue

        time_delta_seconds = abs((current_timestamp - existing_timestamp).total_seconds())
        if time_delta_seconds > float(max_time_window_seconds):
            continue

        distance_meters = _haversine_meters(current_location, existing_location)
        if distance_meters <= float(max_distance_meters):
            return True

    return False

def find_matching_trigger(
    location: Mapping[str, Any],
    timestamp: Any,
    policy_type: str,
    user_id: Optional[str] = None,
    max_distance_meters: float = 50.0,
    max_time_window_seconds: float = 3 * 60 * 60,
) -> Optional[Dict[str, Any]]:
    claim_time = _parse_timestamp(timestamp)
    claim_location = _extract_location(location)
    policy_key = _normalize_policy(policy_type)
    normalized_user_id = str(user_id or "").strip()

    db = get_db()
    
    query: Dict[str, Any] = {}
    if normalized_user_id:
        query["user_id"] = normalized_user_id

    triggers = list(db.triggers.find(query).sort("timestamp", -1))
    
    best_match: Optional[Dict[str, Any]] = None
    best_delta: Optional[float] = None

    for trigger in triggers:
        try:
            trigger_time = _parse_timestamp(trigger.get("timestamp"))
            trigger_location = _extract_location(trigger.get("location", {}))
        except Exception:
            continue

        trigger_policy_types = [
            _normalize_policy(policy)
            for policy in trigger.get("policy_types", [])
            if str(policy).strip()
        ]
        if trigger_policy_types and policy_key and policy_key not in trigger_policy_types:
            continue

        distance = _haversine_meters(claim_location, trigger_location)
        if distance > max_distance_meters:
            continue

        time_delta = abs((claim_time - trigger_time).total_seconds())
        if time_delta > max_time_window_seconds:
            continue

        if best_delta is None or time_delta < best_delta:
            best_match = _doc_to_dict(trigger)
            best_delta = time_delta

    return best_match

def create_claim_record(
    user_id: str,
    claim_type: str,
    status: str,
    payout: float,
    timestamp: Any,
    reason: str,
    trigger_type: str,
    fraud_score: float,
    verification_required: bool,
    policy_type: str,
    user_location: Mapping[str, Any],
    payout_candidate: float = 0.0,
) -> Dict[str, Any]:
    parsed_timestamp = _parse_timestamp(timestamp)
    latitude, longitude = _extract_location(user_location)

    claim_id = f"clm_{uuid4().hex[:12]}"
    claim_record = {
        "claim_id": claim_id,
        "user_id": str(user_id).strip() or "anonymous",
        "claim_type": str(claim_type).strip(),
        "status": str(status).strip(),
        "payout": float(payout),
        "payout_candidate": float(payout_candidate),
        "timestamp": parsed_timestamp.isoformat(),
        "reason": str(reason),
        "trigger_type": str(trigger_type),
        "fraud_score": float(fraud_score),
        "verification_required": bool(verification_required),
        "policy_type": str(policy_type),
        "user_location": {"lat": latitude, "lng": longitude},
    }

    try:
        upsert_claim_snapshot(claim_record)
    except Exception:
        pass

    return claim_record

def update_claim_record(
    claim_id: str,
    *,
    status: str,
    payout: float,
    reason: str,
    verification_required: bool,
) -> Optional[Dict[str, Any]]:
    try:
        update_claim_snapshot(
            claim_id,
            status=status,
            payout=payout,
            reason=reason,
            verification_required=verification_required,
        )
        return get_claim_record(claim_id)
    except Exception:
        return None

def get_claim_record(claim_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    doc = db.claims.find_one({"_id": claim_id} if not claim_id.startswith("clm_") else {"claim_id": claim_id})
    if not doc:
        doc = db.claims.find_one({"claim_id": claim_id})
    return _doc_to_dict(doc)

def get_latest_pending_verification_claim(user_id: str) -> Optional[Dict[str, Any]]:
    target_user = str(user_id).strip() or "anonymous"

    db = get_db()
    docs = list(db.claims.find({
        "status": "verification_required",
        "user_id": target_user
    }).sort("timestamp", -1).limit(1))

    if not docs:
        return None

    return _doc_to_dict(docs[0])

def get_latest_pending_auto_claim(user_id: str) -> Optional[Dict[str, Any]]:
    """Backward-compatible alias for existing callers."""
    return get_latest_pending_verification_claim(user_id)

def append_user_fraud_score(user_id: str, score: float) -> List[float]:
    key = str(user_id).strip() or "anonymous"

    db = get_db()
    res = db.user_fraud_profiles.find_one_and_update(
        {"_id": key},
        {"$push": {"history": float(score)}},
        upsert=True,
        return_document=True
    )
    
    if res and "history" in res:
        return res["history"]
    return [float(score)]

def get_user_fraud_history(user_id: str) -> List[float]:
    key = str(user_id).strip() or "anonymous"

    db = get_db()
    doc = db.user_fraud_profiles.find_one({"_id": key})
    if doc and "history" in doc:
        return doc["history"]
    return []
