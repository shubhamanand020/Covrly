"""Repository helpers for MongoDB-backed auth, profile, and policy operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from backend.storage.mongo_db import get_db

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _parse_iso_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty ISO string")

    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)

def _doc_to_dict(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    item = dict(doc)
    if "_id" in item and "id" not in item:
        item["id"] = item["_id"]
    if "_id" in item:
        del item["_id"]
        
    return item

def create_user(email: str, password_hash: str) -> Dict[str, Any]:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        raise ValueError("Email is required")

    user_id = f"usr_{uuid4().hex[:12]}"
    created_at = _utc_now_iso()

    db = get_db()
    try:
        db.users.insert_one({
            "_id": user_id,
            "id": user_id, # for compatibility
            "email": normalized_email,
            "password_hash": str(password_hash),
            "created_at": created_at
        })
    except DuplicateKeyError as exc:
        raise ValueError("User already exists") from exc

    return {
        "id": user_id,
        "email": normalized_email,
        "created_at": created_at,
    }

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return None

    db = get_db()
    doc = db.users.find_one({"email": normalized_email})
    return _doc_to_dict(doc)

def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    target_user_id = str(user_id or "").strip()
    if not target_user_id:
        return None

    db = get_db()
    doc = db.users.find_one({"_id": target_user_id})
    return _doc_to_dict(doc)

def upsert_registration_otp(email: str, otp_hash: str, expires_at: str) -> None:
    normalized_email = str(email or "").strip().lower()
    normalized_hash = str(otp_hash or "").strip()
    normalized_expiry = str(expires_at or "").strip()
    if not normalized_email or not normalized_hash or not normalized_expiry:
        raise ValueError("email, otp_hash, and expires_at are required")

    now_iso = _utc_now_iso()

    db = get_db()
    db.registration_otps.update_one(
        {"_id": normalized_email},
        {
            "$set": {
                "email": normalized_email,
                "otp_hash": normalized_hash,
                "expires_at": normalized_expiry,
                "attempts": 0,
                "updated_at": now_iso
            },
            "$setOnInsert": {
                "created_at": now_iso
            }
        },
        upsert=True
    )

def get_registration_otp(email: str) -> Optional[Dict[str, Any]]:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return None

    db = get_db()
    doc = db.registration_otps.find_one({"_id": normalized_email})
    return _doc_to_dict(doc)

def increment_registration_otp_attempt(email: str) -> int:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return 0

    db = get_db()
    doc = db.registration_otps.find_one_and_update(
        {"_id": normalized_email},
        {
            "$inc": {"attempts": 1},
            "$set": {"updated_at": _utc_now_iso()}
        },
        return_document=True
    )
    if doc is None:
        return 0
    return doc.get("attempts", 0)

def delete_registration_otp(email: str) -> None:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return

    db = get_db()
    db.registration_otps.delete_one({"_id": normalized_email})

def upsert_profile(
    user_id: str,
    name: str,
    phone: str,
    city: str,
    vehicle_type: str,
    profile_image_url: str,
) -> Dict[str, Any]:
    target_user_id = str(user_id or "").strip()
    if not target_user_id:
        raise ValueError("user_id is required")

    profile_name = str(name or "").strip()
    profile_phone = str(phone or "").strip()
    profile_city = str(city or "").strip()
    profile_vehicle = str(vehicle_type or "").strip()
    profile_image = str(profile_image_url or "").strip()
    is_complete = bool(profile_name and profile_phone and profile_city and profile_vehicle and profile_image)
    updated_at = _utc_now_iso()

    db = get_db()
    res = db.profiles.find_one_and_update(
        {"_id": target_user_id},
        {
            "$set": {
                "user_id": target_user_id,
                "name": profile_name,
                "phone": profile_phone,
                "city": profile_city,
                "vehicle_type": profile_vehicle,
                "profile_image_url": profile_image,
                "is_complete": bool(is_complete),
                "updated_at": updated_at
            }
        },
        upsert=True,
        return_document=True
    )
    
    if res is None:
        raise ValueError("Unable to save profile")
        
    return _doc_to_dict(res) or {}

def get_profile(user_id: str) -> Optional[Dict[str, Any]]:
    target_user_id = str(user_id or "").strip()
    if not target_user_id:
        return None

    db = get_db()
    doc = db.profiles.find_one({"_id": target_user_id})
    return _doc_to_dict(doc)

def create_policy(
    user_id: str,
    policy_type: str,
    base_premium: float,
    dynamic_premium: float,
    start_date: str,
    end_date: str,
    is_active: bool = True,
) -> Dict[str, Any]:
    target_user_id = str(user_id or "").strip()
    normalized_type = str(policy_type or "").strip()
    if not target_user_id or not normalized_type:
        raise ValueError("user_id and policy_type are required")

    policy_id = f"pol_{uuid4().hex[:12]}"
    created_at = _utc_now_iso()

    db = get_db()
    db.policies.insert_one({
        "_id": policy_id,
        "id": policy_id,
        "user_id": target_user_id,
        "policy_type": normalized_type,
        "base_premium": float(base_premium),
        "dynamic_premium": float(dynamic_premium),
        "start_date": str(start_date),
        "end_date": str(end_date),
        "is_active": bool(is_active),
        "created_at": created_at
    })

    policy = get_policy_by_id(policy_id)
    if policy is None:
        raise ValueError("Unable to create policy")
    return policy

def get_policy_by_id(policy_id: str) -> Optional[Dict[str, Any]]:
    target_policy_id = str(policy_id or "").strip()
    if not target_policy_id:
        return None

    db = get_db()
    doc = db.policies.find_one({"_id": target_policy_id})
    
    policy = _doc_to_dict(doc)
    if policy is None:
        return None

    return _refresh_policy_status(policy)

def _set_policy_active(policy_id: str, is_active: bool) -> None:
    db = get_db()
    db.policies.update_one({"_id": policy_id}, {"$set": {"is_active": bool(is_active)}})

def _refresh_policy_status(policy: Dict[str, Any]) -> Dict[str, Any]:
    end_date = _parse_iso_timestamp(policy.get("end_date"))
    now = datetime.now(timezone.utc)
    should_be_active = now <= end_date

    if bool(policy.get("is_active")) != should_be_active:
        _set_policy_active(str(policy.get("id")), should_be_active)
        policy["is_active"] = should_be_active

    return policy

def list_user_policies(user_id: str) -> List[Dict[str, Any]]:
    target_user_id = str(user_id or "").strip()
    if not target_user_id:
        return []

    db = get_db()
    docs = db.policies.find({"user_id": target_user_id}).sort("start_date", -1)

    active_policies: List[Dict[str, Any]] = []
    for doc in docs:
        policy = _doc_to_dict(doc)
        if policy is None:
            continue
        active_policies.append(_refresh_policy_status(policy))
    return active_policies

def get_latest_policy_for_type(user_id: str, policy_type: str) -> Optional[Dict[str, Any]]:
    target_user_id = str(user_id or "").strip()
    target_policy_type = str(policy_type or "").strip()
    if not target_user_id or not target_policy_type:
        return None

    db = get_db()
    
    # Needs case-insensitive matching if the old sqlite `lower(policy_type) = lower(?)` was heavily relied upon.
    # A simple regex for case insensitivity:
    doc = db.policies.find_one(
        {"user_id": target_user_id, "policy_type": {"$regex": f"^{target_policy_type}$", "$options": "i"}},
        sort=[("start_date", -1)]
    )

    policy = _doc_to_dict(doc)
    if policy is None:
        return None

    return _refresh_policy_status(policy)

def list_user_triggers(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    target_user_id = str(user_id or "").strip()
    if not target_user_id:
        return []

    safe_limit = max(1, min(int(limit), 200))

    db = get_db()
    docs = db.triggers.find({"user_id": target_user_id}).sort("timestamp", -1).limit(safe_limit)

    triggers: List[Dict[str, Any]] = []
    for doc in docs:
        item = _doc_to_dict(doc)
        if item is None: continue
        
        policy_types = item.get("policy_types", [])
        if not isinstance(policy_types, list):
            try:
                # Fallback for old records if json dumped
                policy_types = json.loads(str(item.get("policy_types_json") or "[]"))
                if not isinstance(policy_types, list):
                    policy_types = []
            except Exception:
                policy_types = []

        triggers.append(
            {
                "trigger_id": str(item.get("trigger_id") or item.get("id") or ""),
                "user_id": str(item.get("user_id") or ""),
                "trigger_type": str(item.get("trigger_type") or "unknown"),
                "fraud_score": float(item.get("fraud_score") or 0.0),
                "location": {
                    "lat": float(item.get("location_lat", item.get("location", {}).get("lat", 0.0))),
                    "lng": float(item.get("location_lng", item.get("location", {}).get("lng", 0.0))),
                },
                "timestamp": str(item.get("timestamp") or ""),
                "policy_types": [str(policy) for policy in policy_types],
            }
        )

    return triggers

def upsert_location_snapshot(user_id: str, lat: float, lng: float, timestamp: str) -> None:
    normalized_user_id = str(user_id or "system").strip() or "system"

    try:
        normalized_timestamp = _parse_iso_timestamp(timestamp).isoformat()
    except Exception:
        normalized_timestamp = _utc_now_iso()

    db = get_db()
    db.location_snapshots.update_one(
        {"_id": normalized_user_id},
        {
            "$set": {
                "user_id": normalized_user_id,
                "location_lat": float(lat),
                "location_lng": float(lng),
                "timestamp": normalized_timestamp,
                "updated_at": _utc_now_iso()
            }
        },
        upsert=True
    )

def list_recent_location_snapshots(max_age_seconds: float = 15 * 60) -> List[Dict[str, Any]]:
    max_age = max(0.0, float(max_age_seconds))
    now = datetime.now(timezone.utc)

    db = get_db()
    docs = db.location_snapshots.find().sort("updated_at", -1)

    locations: List[Dict[str, Any]] = []
    for doc in docs:
        item = _doc_to_dict(doc)
        if item is None:
            continue

        try:
            snapshot_time = _parse_iso_timestamp(item.get("timestamp"))
            lat = float(item.get("location_lat"))
            lng = float(item.get("location_lng"))
        except Exception:
            continue

        age_seconds = abs((now - snapshot_time).total_seconds())
        if age_seconds > max_age:
            continue

        user_id = str(item.get("user_id") or "system").strip() or "system"
        locations.append(
            {
                "user_id": user_id,
                "lat": lat,
                "lng": lng,
                "timestamp": snapshot_time.isoformat(),
            }
        )

    return locations

def upsert_trigger_snapshot(trigger_record: Dict[str, Any]) -> None:
    trigger_id = str(trigger_record.get("trigger_id") or "").strip()
    if not trigger_id:
        return

    location = trigger_record.get("location", {})
    try:
        lat = float(location.get("lat"))
        lng = float(location.get("lng", location.get("long")))
    except (TypeError, ValueError):
        return

    user_id = str(trigger_record.get("user_id") or "system").strip() or "system"

    db = get_db()
    db.triggers.update_one(
        {"_id": trigger_id},
        {
            "$set": {
                "trigger_id": trigger_id,
                "user_id": user_id,
                "trigger_type": str(trigger_record.get("trigger_type") or "none"),
                "fraud_score": float(trigger_record.get("fraud_score", 0.0)),
                "location_lat": lat,
                "location_lng": lng,
                "location": {"lat": lat, "lng": lng}, # Keep embedded for convenience
                "timestamp": str(trigger_record.get("timestamp") or _utc_now_iso()),
                "policy_types_json": json.dumps(trigger_record.get("policy_types", [])), # For compat
                "policy_types": trigger_record.get("policy_types", [])
            }
        },
        upsert=True
    )

def upsert_claim_snapshot(claim_record: Dict[str, Any]) -> None:
    claim_id = str(claim_record.get("claim_id") or "").strip()
    if not claim_id:
        return

    location = claim_record.get("user_location", {})
    try:
        lat = float(location.get("lat"))
        lng = float(location.get("lng", location.get("long")))
    except (TypeError, ValueError):
        return

    db = get_db()
    db.claims.update_one(
        {"_id": claim_id},
        {
            "$set": {
                "claim_id": claim_id,
                "user_id": str(claim_record.get("user_id") or "anonymous"),
                "claim_type": str(claim_record.get("claim_type") or "manual"),
                "status": str(claim_record.get("status") or "pending"),
                "payout": float(claim_record.get("payout", 0.0)),
                "payout_candidate": float(claim_record.get("payout_candidate", 0.0)),
                "timestamp": str(claim_record.get("timestamp") or _utc_now_iso()),
                "reason": str(claim_record.get("reason") or ""),
                "trigger_type": str(claim_record.get("trigger_type") or "none"),
                "fraud_score": float(claim_record.get("fraud_score", 0.0)),
                "verification_required": bool(claim_record.get("verification_required", False)),
                "policy_type": str(claim_record.get("policy_type") or ""),
                "user_location_lat": lat,
                "user_location_lng": lng,
                "user_location": {"lat": lat, "lng": lng},
                "updated_at": _utc_now_iso(),
            }
        },
        upsert=True
    )

def update_claim_snapshot(
    claim_id: str,
    *,
    status: str,
    payout: float,
    reason: str,
    verification_required: bool,
) -> None:
    target_claim_id = str(claim_id or "").strip()
    if not target_claim_id:
        return

    db = get_db()
    db.claims.update_one(
        {"_id": target_claim_id},
        {
            "$set": {
                "status": str(status),
                "payout": float(payout),
                "reason": str(reason),
                "verification_required": bool(verification_required),
                "updated_at": _utc_now_iso()
            }
        }
    )
