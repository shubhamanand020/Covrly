"""Repository helpers for SQLite-backed auth, profile, and policy operations."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.storage.sqlite_db import DB_LOCK, get_connection


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


def _row_to_dict(row: sqlite3.Row | None) -> Optional[Dict[str, Any]]:
    if row is None:
        return None

    item = dict(row)
    if "is_complete" in item:
        item["is_complete"] = bool(item["is_complete"])
    if "is_active" in item:
        item["is_active"] = bool(item["is_active"])
    if "verification_required" in item:
        item["verification_required"] = bool(item["verification_required"])
    return item


def create_user(email: str, password_hash: str) -> Dict[str, Any]:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        raise ValueError("Email is required")

    user_id = f"usr_{uuid4().hex[:12]}"
    created_at = _utc_now_iso()

    with DB_LOCK:
        with get_connection() as conn:
            try:
                conn.execute(
                    "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, normalized_email, str(password_hash), created_at),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
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

    with DB_LOCK:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, email, password_hash, created_at FROM users WHERE email = ?",
                (normalized_email,),
            ).fetchone()

    return _row_to_dict(row)


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    target_user_id = str(user_id or "").strip()
    if not target_user_id:
        return None

    with DB_LOCK:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, email, password_hash, created_at FROM users WHERE id = ?",
                (target_user_id,),
            ).fetchone()

    return _row_to_dict(row)


def upsert_registration_otp(email: str, otp_hash: str, expires_at: str) -> None:
    normalized_email = str(email or "").strip().lower()
    normalized_hash = str(otp_hash or "").strip()
    normalized_expiry = str(expires_at or "").strip()
    if not normalized_email or not normalized_hash or not normalized_expiry:
        raise ValueError("email, otp_hash, and expires_at are required")

    now_iso = _utc_now_iso()

    with DB_LOCK:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO registration_otps (
                    email,
                    otp_hash,
                    expires_at,
                    attempts,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, 0, ?, ?)
                ON CONFLICT(email)
                DO UPDATE SET
                    otp_hash = excluded.otp_hash,
                    expires_at = excluded.expires_at,
                    attempts = 0,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_email,
                    normalized_hash,
                    normalized_expiry,
                    now_iso,
                    now_iso,
                ),
            )
            conn.commit()


def get_registration_otp(email: str) -> Optional[Dict[str, Any]]:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return None

    with DB_LOCK:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT email, otp_hash, expires_at, attempts, created_at, updated_at
                FROM registration_otps
                WHERE email = ?
                """,
                (normalized_email,),
            ).fetchone()

    return _row_to_dict(row)


def increment_registration_otp_attempt(email: str) -> int:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return 0

    with DB_LOCK:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE registration_otps
                SET attempts = attempts + 1, updated_at = ?
                WHERE email = ?
                """,
                (_utc_now_iso(), normalized_email),
            )
            row = conn.execute(
                "SELECT attempts FROM registration_otps WHERE email = ?",
                (normalized_email,),
            ).fetchone()
            conn.commit()

    if row is None:
        return 0

    return int(row[0])


def delete_registration_otp(email: str) -> None:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return

    with DB_LOCK:
        with get_connection() as conn:
            conn.execute("DELETE FROM registration_otps WHERE email = ?", (normalized_email,))
            conn.commit()


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

    with DB_LOCK:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO profiles (
                    user_id,
                    name,
                    phone,
                    city,
                    vehicle_type,
                    profile_image_url,
                    is_complete,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET
                    name = excluded.name,
                    phone = excluded.phone,
                    city = excluded.city,
                    vehicle_type = excluded.vehicle_type,
                    profile_image_url = excluded.profile_image_url,
                    is_complete = excluded.is_complete,
                    updated_at = excluded.updated_at
                """,
                (
                    target_user_id,
                    profile_name,
                    profile_phone,
                    profile_city,
                    profile_vehicle,
                    profile_image,
                    int(is_complete),
                    updated_at,
                ),
            )
            conn.commit()

    profile = get_profile(target_user_id)
    if profile is None:
        raise ValueError("Unable to save profile")
    return profile


def get_profile(user_id: str) -> Optional[Dict[str, Any]]:
    target_user_id = str(user_id or "").strip()
    if not target_user_id:
        return None

    with DB_LOCK:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT user_id, name, phone, city, vehicle_type, profile_image_url, is_complete, updated_at
                FROM profiles
                WHERE user_id = ?
                """,
                (target_user_id,),
            ).fetchone()

    return _row_to_dict(row)


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

    with DB_LOCK:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO policies (
                    id,
                    user_id,
                    policy_type,
                    base_premium,
                    dynamic_premium,
                    start_date,
                    end_date,
                    is_active,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy_id,
                    target_user_id,
                    normalized_type,
                    float(base_premium),
                    float(dynamic_premium),
                    str(start_date),
                    str(end_date),
                    int(bool(is_active)),
                    created_at,
                ),
            )
            conn.commit()

    policy = get_policy_by_id(policy_id)
    if policy is None:
        raise ValueError("Unable to create policy")
    return policy


def get_policy_by_id(policy_id: str) -> Optional[Dict[str, Any]]:
    target_policy_id = str(policy_id or "").strip()
    if not target_policy_id:
        return None

    with DB_LOCK:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    user_id,
                    policy_type,
                    base_premium,
                    dynamic_premium,
                    start_date,
                    end_date,
                    is_active,
                    created_at
                FROM policies
                WHERE id = ?
                """,
                (target_policy_id,),
            ).fetchone()

    policy = _row_to_dict(row)
    if policy is None:
        return None

    return _refresh_policy_status(policy)


def _set_policy_active(policy_id: str, is_active: bool) -> None:
    with DB_LOCK:
        with get_connection() as conn:
            conn.execute(
                "UPDATE policies SET is_active = ? WHERE id = ?",
                (int(bool(is_active)), str(policy_id)),
            )
            conn.commit()


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

    with DB_LOCK:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    user_id,
                    policy_type,
                    base_premium,
                    dynamic_premium,
                    start_date,
                    end_date,
                    is_active,
                    created_at
                FROM policies
                WHERE user_id = ?
                ORDER BY start_date DESC
                """,
                (target_user_id,),
            ).fetchall()

    policies = [_row_to_dict(row) for row in rows]
    active_policies: List[Dict[str, Any]] = []
    for policy in policies:
        if policy is None:
            continue
        active_policies.append(_refresh_policy_status(policy))
    return active_policies


def get_latest_policy_for_type(user_id: str, policy_type: str) -> Optional[Dict[str, Any]]:
    target_user_id = str(user_id or "").strip()
    target_policy_type = str(policy_type or "").strip()
    if not target_user_id or not target_policy_type:
        return None

    with DB_LOCK:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    user_id,
                    policy_type,
                    base_premium,
                    dynamic_premium,
                    start_date,
                    end_date,
                    is_active,
                    created_at
                FROM policies
                WHERE user_id = ? AND lower(policy_type) = lower(?)
                ORDER BY start_date DESC
                LIMIT 1
                """,
                (target_user_id, target_policy_type),
            ).fetchone()

    policy = _row_to_dict(row)
    if policy is None:
        return None

    return _refresh_policy_status(policy)


def list_user_triggers(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    target_user_id = str(user_id or "").strip()
    if not target_user_id:
        return []

    safe_limit = max(1, min(int(limit), 200))

    with DB_LOCK:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    trigger_id,
                    user_id,
                    trigger_type,
                    fraud_score,
                    location_lat,
                    location_lng,
                    timestamp,
                    policy_types_json
                FROM triggers
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (target_user_id, safe_limit),
            ).fetchall()

    triggers: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            policy_types = json.loads(str(item.get("policy_types_json") or "[]"))
            if not isinstance(policy_types, list):
                policy_types = []
        except Exception:
            policy_types = []

        triggers.append(
            {
                "trigger_id": str(item.get("trigger_id") or ""),
                "user_id": str(item.get("user_id") or ""),
                "trigger_type": str(item.get("trigger_type") or "unknown"),
                "fraud_score": float(item.get("fraud_score") or 0.0),
                "location": {
                    "lat": float(item.get("location_lat") or 0.0),
                    "lng": float(item.get("location_lng") or 0.0),
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

    with DB_LOCK:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO location_snapshots (
                    user_id,
                    location_lat,
                    location_lng,
                    timestamp,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET
                    location_lat = excluded.location_lat,
                    location_lng = excluded.location_lng,
                    timestamp = excluded.timestamp,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_user_id,
                    float(lat),
                    float(lng),
                    normalized_timestamp,
                    _utc_now_iso(),
                ),
            )
            conn.commit()


def list_recent_location_snapshots(max_age_seconds: float = 15 * 60) -> List[Dict[str, Any]]:
    max_age = max(0.0, float(max_age_seconds))
    now = datetime.now(timezone.utc)

    with DB_LOCK:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT user_id, location_lat, location_lng, timestamp, updated_at
                FROM location_snapshots
                ORDER BY updated_at DESC
                """
            ).fetchall()

    locations: List[Dict[str, Any]] = []
    for row in rows:
        item = _row_to_dict(row)
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

    with DB_LOCK:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO triggers (
                    trigger_id,
                    user_id,
                    trigger_type,
                    fraud_score,
                    location_lat,
                    location_lng,
                    timestamp,
                    policy_types_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trigger_id)
                DO UPDATE SET
                    user_id = excluded.user_id,
                    trigger_type = excluded.trigger_type,
                    fraud_score = excluded.fraud_score,
                    location_lat = excluded.location_lat,
                    location_lng = excluded.location_lng,
                    timestamp = excluded.timestamp,
                    policy_types_json = excluded.policy_types_json
                """,
                (
                    trigger_id,
                    user_id,
                    str(trigger_record.get("trigger_type") or "none"),
                    float(trigger_record.get("fraud_score", 0.0)),
                    lat,
                    lng,
                    str(trigger_record.get("timestamp") or _utc_now_iso()),
                    json.dumps(trigger_record.get("policy_types", [])),
                ),
            )
            conn.commit()


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

    with DB_LOCK:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO claims (
                    claim_id,
                    user_id,
                    claim_type,
                    status,
                    payout,
                    payout_candidate,
                    timestamp,
                    reason,
                    trigger_type,
                    fraud_score,
                    verification_required,
                    policy_type,
                    user_location_lat,
                    user_location_lng,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(claim_id)
                DO UPDATE SET
                    user_id = excluded.user_id,
                    claim_type = excluded.claim_type,
                    status = excluded.status,
                    payout = excluded.payout,
                    payout_candidate = excluded.payout_candidate,
                    timestamp = excluded.timestamp,
                    reason = excluded.reason,
                    trigger_type = excluded.trigger_type,
                    fraud_score = excluded.fraud_score,
                    verification_required = excluded.verification_required,
                    policy_type = excluded.policy_type,
                    user_location_lat = excluded.user_location_lat,
                    user_location_lng = excluded.user_location_lng,
                    updated_at = excluded.updated_at
                """,
                (
                    claim_id,
                    str(claim_record.get("user_id") or "anonymous"),
                    str(claim_record.get("claim_type") or "manual"),
                    str(claim_record.get("status") or "pending"),
                    float(claim_record.get("payout", 0.0)),
                    float(claim_record.get("payout_candidate", 0.0)),
                    str(claim_record.get("timestamp") or _utc_now_iso()),
                    str(claim_record.get("reason") or ""),
                    str(claim_record.get("trigger_type") or "none"),
                    float(claim_record.get("fraud_score", 0.0)),
                    int(bool(claim_record.get("verification_required", False))),
                    str(claim_record.get("policy_type") or ""),
                    lat,
                    lng,
                    _utc_now_iso(),
                ),
            )
            conn.commit()


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

    with DB_LOCK:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE claims
                SET
                    status = ?,
                    payout = ?,
                    reason = ?,
                    verification_required = ?,
                    updated_at = ?
                WHERE claim_id = ?
                """,
                (
                    str(status),
                    float(payout),
                    str(reason),
                    int(bool(verification_required)),
                    _utc_now_iso(),
                    target_claim_id,
                ),
            )
            conn.commit()
