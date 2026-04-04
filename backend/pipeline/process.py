"""Compatibility pipeline helpers backed by explicit workflow entry points."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from backend.services import (
    ClaimMatchingService,
    FraudService,
    TriggerService,
    VerificationService,
)
from backend.storage.repository import (
    append_user_fraud_score,
    create_claim_record,
    get_claim_record,
    get_latest_pending_verification_claim,
    update_claim_record,
)


def _safe_user_id(value: Any) -> str:
    return str(value or "anonymous").strip() or "anonymous"


def process_auto_trigger(data: Mapping[str, Any]) -> Dict[str, Any]:
    user_id = _safe_user_id(data.get("user_id"))
    timestamp = str(data.get("timestamp") or datetime.now(timezone.utc).isoformat())
    user_location = dict(data.get("user_location", {}))

    scoring_payload = {
        "user_location": user_location,
        "timestamp": timestamp,
        "previous_location": data.get("previous_location"),
    }
    fraud_score = FraudService.score_claim(scoring_payload)
    trigger_event = TriggerService.detect(
        {
            "user_location": user_location,
            "timestamp": timestamp,
        }
    )
    TriggerService.persist_detected_trigger(
        trigger_event,
        fraud_score,
        user_id=user_id,
    )

    if not bool(trigger_event.get("trigger_detected")):
        claim_record = create_claim_record(
            user_id=user_id,
            claim_type="auto",
            status="rejected",
            payout=0.0,
            timestamp=timestamp,
            reason="No active trigger detected",
            trigger_type="none",
            fraud_score=fraud_score,
            verification_required=False,
            policy_type="System Auto",
            user_location=user_location,
            payout_candidate=0.0,
        )
        append_user_fraud_score(user_id, fraud_score)
        return {
            "status": "rejected",
            "next_step": None,
            "data": {
                "flow": "auto",
                "claim_id": claim_record.get("claim_id"),
                "user_id": user_id,
                "trigger_detected": False,
                "trigger_type": "none",
                "payout": 0.0,
                "fraud_score": round(fraud_score, 2),
                "reason": "No active trigger detected",
            },
        }

    trigger_type = str(trigger_event.get("trigger_type", "none"))
    payout_candidate = float(trigger_event.get("eligible_payout", 0.0))

    if FraudService.requires_auto_verification(fraud_score):
        claim_record = create_claim_record(
            user_id=user_id,
            claim_type="auto",
            status="verification_required",
            payout=0.0,
            timestamp=timestamp,
            reason="Verification required before payout",
            trigger_type=trigger_type,
            fraud_score=fraud_score,
            verification_required=True,
            policy_type="System Auto",
            user_location=user_location,
            payout_candidate=payout_candidate,
        )
        append_user_fraud_score(user_id, fraud_score)
        return {
            "status": "verification_required",
            "next_step": "verify",
            "data": {
                "flow": "auto",
                "claim_id": claim_record.get("claim_id"),
                "user_id": user_id,
                "trigger_detected": True,
                "trigger_type": trigger_type,
                "payout": 0.0,
                "fraud_score": round(fraud_score, 2),
                "reason": "Verification required before payout",
            },
        }

    claim_record = create_claim_record(
        user_id=user_id,
        claim_type="auto",
        status="approved",
        payout=payout_candidate,
        timestamp=timestamp,
        reason="Auto payout approved",
        trigger_type=trigger_type,
        fraud_score=fraud_score,
        verification_required=False,
        policy_type="System Auto",
        user_location=user_location,
        payout_candidate=payout_candidate,
    )
    append_user_fraud_score(user_id, fraud_score)

    return {
        "status": "approved",
        "next_step": "payout",
        "data": {
            "flow": "auto",
            "claim_id": claim_record.get("claim_id"),
            "user_id": user_id,
            "trigger_detected": True,
            "trigger_type": trigger_type,
            "payout": payout_candidate,
            "fraud_score": round(fraud_score, 2),
            "reason": "Auto payout approved",
        },
    }


def process_auto_verification(data: Mapping[str, Any]) -> Dict[str, Any]:
    claim_id = str(data.get("claim_id") or "").strip()
    user_id = _safe_user_id(data.get("user_id"))

    pending_claim = get_claim_record(claim_id) if claim_id else get_latest_pending_verification_claim(user_id)
    if pending_claim is None:
        raise ValueError("No pending verification claim found")

    if _safe_user_id(pending_claim.get("user_id")) != user_id:
        raise PermissionError("Claim does not belong to the authenticated user")

    if str(pending_claim.get("status")) != "verification_required":
        raise ValueError("Claim is not awaiting verification")

    verification = VerificationService.evaluate_auto_verification(
        claim_record=pending_claim,
        verification_payload=data,
    )

    if verification.get("is_verified"):
        payout = float(pending_claim.get("payout_candidate", 0.0))
        status = "approved"
        reason = "Verification successful"
        next_step = "payout"
    else:
        payout = 0.0
        status = "rejected"
        reason = "Verification failed"
        next_step = None

    updated_claim = update_claim_record(
        str(pending_claim.get("claim_id")),
        status=status,
        payout=payout,
        reason=reason,
        verification_required=False,
    )
    if updated_claim is None:
        raise ValueError("Unable to update claim status")

    return {
        "status": status,
        "next_step": next_step,
        "data": {
            "flow": "auto",
            "claim_id": updated_claim.get("claim_id"),
            "user_id": updated_claim.get("user_id"),
            "trigger_detected": True,
            "trigger_type": updated_claim.get("trigger_type"),
            "payout": float(updated_claim.get("payout", 0.0)),
            "fraud_score": float(updated_claim.get("fraud_score", 0.0)),
            "reason": reason,
            "verification": {
                "status": verification.get("verification_status"),
                "confidence_score": verification.get("confidence_score"),
            },
        },
    }


def process_manual_claim(data: Mapping[str, Any]) -> Dict[str, Any]:
    user_id = _safe_user_id(data.get("user_id"))
    policy_type = str(data.get("policy_type") or "").strip()
    if not policy_type:
        raise ValueError("policy_type is required")

    timestamp = str(data.get("timestamp") or "").strip()
    user_location = dict(data.get("user_location", {}))
    image_metadata = data.get("image_metadata", {})

    scoring_payload = {
        "user_location": user_location,
        "timestamp": timestamp,
        "previous_location": data.get("previous_location"),
    }
    current_fraud_score = FraudService.score_claim(scoring_payload)

    metadata_ok, metadata_reason = ClaimMatchingService.validate_image_metadata(
        image_metadata=image_metadata,
        user_location=user_location,
        claim_timestamp=timestamp,
    )
    if not metadata_ok:
        claim_record = create_claim_record(
            user_id=user_id,
            claim_type="manual",
            status="rejected",
            payout=0.0,
            timestamp=timestamp,
            reason=metadata_reason,
            trigger_type="none",
            fraud_score=current_fraud_score,
            verification_required=False,
            policy_type=policy_type,
            user_location=user_location,
            payout_candidate=0.0,
        )
        append_user_fraud_score(user_id, current_fraud_score)
        return {
            "status": "rejected",
            "next_step": None,
            "data": {
                "flow": "manual",
                "claim_id": claim_record.get("claim_id"),
                "user_id": user_id,
                "trigger_detected": False,
                "trigger_type": "none",
                "payout": 0.0,
                "fraud_score": round(current_fraud_score, 2),
                "reason": metadata_reason,
            },
        }

    matched_trigger = ClaimMatchingService.match_trigger(
        policy_type=policy_type,
        user_location=user_location,
        timestamp=timestamp,
        user_id=user_id,
    )
    if matched_trigger is None:
        claim_record = create_claim_record(
            user_id=user_id,
            claim_type="manual",
            status="rejected",
            payout=0.0,
            timestamp=timestamp,
            reason="No matching trigger found",
            trigger_type="none",
            fraud_score=current_fraud_score,
            verification_required=False,
            policy_type=policy_type,
            user_location=user_location,
            payout_candidate=0.0,
        )
        append_user_fraud_score(user_id, current_fraud_score)
        return {
            "status": "rejected",
            "next_step": None,
            "data": {
                "flow": "manual",
                "claim_id": claim_record.get("claim_id"),
                "user_id": user_id,
                "trigger_detected": False,
                "trigger_type": "none",
                "payout": 0.0,
                "fraud_score": round(current_fraud_score, 2),
                "reason": "No matching trigger found",
            },
        }

    trigger_fraud_score = float(matched_trigger.get("fraud_score", 0.0))
    is_allowed, effective_score, risk_reason = FraudService.evaluate_manual_risk(
        user_id=user_id,
        current_fraud_score=current_fraud_score,
        trigger_fraud_score=trigger_fraud_score,
    )
    if not is_allowed:
        claim_record = create_claim_record(
            user_id=user_id,
            claim_type="manual",
            status="rejected",
            payout=0.0,
            timestamp=timestamp,
            reason=risk_reason,
            trigger_type=str(matched_trigger.get("trigger_type", "none")),
            fraud_score=effective_score,
            verification_required=False,
            policy_type=policy_type,
            user_location=user_location,
            payout_candidate=0.0,
        )
        append_user_fraud_score(user_id, effective_score)
        return {
            "status": "rejected",
            "next_step": None,
            "data": {
                "flow": "manual",
                "claim_id": claim_record.get("claim_id"),
                "user_id": user_id,
                "trigger_detected": True,
                "trigger_type": str(matched_trigger.get("trigger_type", "none")),
                "payout": 0.0,
                "fraud_score": round(effective_score, 2),
                "reason": risk_reason,
            },
        }

    matched_trigger_type = str(matched_trigger.get("trigger_type", "none"))
    payout = float(TriggerService.TRIGGER_PAYOUT_MAP.get(matched_trigger_type, 0.0))

    claim_record = create_claim_record(
        user_id=user_id,
        claim_type="manual",
        status="approved",
        payout=payout,
        timestamp=timestamp,
        reason="Manual claim approved after trigger and fraud validation",
        trigger_type=matched_trigger_type,
        fraud_score=effective_score,
        verification_required=False,
        policy_type=policy_type,
        user_location=user_location,
        payout_candidate=payout,
    )
    append_user_fraud_score(user_id, effective_score)

    return {
        "status": "approved",
        "next_step": "payout",
        "data": {
            "flow": "manual",
            "claim_id": claim_record.get("claim_id"),
            "user_id": user_id,
            "trigger_detected": True,
            "trigger_type": matched_trigger_type,
            "payout": payout,
            "fraud_score": round(effective_score, 2),
            "reason": "Manual claim approved after trigger and fraud validation",
        },
    }


def process_pipeline(data: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible pipeline alias that maps to the manual entry point."""
    return process_manual_claim(data)


def process_claim(claim_data: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible wrapper retained for existing imports."""
    return process_manual_claim(claim_data)
