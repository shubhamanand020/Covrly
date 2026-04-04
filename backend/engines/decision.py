"""Final decision engine for claims."""

from __future__ import annotations

from typing import Any, Dict

LOW_FRAUD_THRESHOLD = 0.3
HIGH_FRAUD_THRESHOLD = 0.7
DEFAULT_APPROVED_PAYOUT = 1000.0


def _normalize_verification_status(verification_status: Any) -> str:
    if verification_status is None:
        return "pending"

    if isinstance(verification_status, bool):
        return "verified" if verification_status else "pending"

    normalized = str(verification_status).strip().lower()
    if normalized in {"verified", "approved", "passed", "success"}:
        return "verified"
    if normalized in {"failed", "rejected", "reject"}:
        return "failed"
    if normalized in {"verify", "verification_required", "pending"}:
        return "pending"
    return "pending"


def claim_decision_engine(
    fraud_score: float,
    trigger_valid: bool,
    verification_status: Any,
) -> Dict[str, Any]:
    """Return claim decision status and payout from core risk signals."""
    score = max(0.0, min(float(fraud_score), 1.0))
    trigger_is_valid = bool(trigger_valid)
    _normalize_verification_status(verification_status)

    if score > HIGH_FRAUD_THRESHOLD:
        return {"status": "rejected", "payout": 0.0}

    if LOW_FRAUD_THRESHOLD <= score <= HIGH_FRAUD_THRESHOLD:
        return {"status": "verification_required", "payout": 0.0}

    if score < LOW_FRAUD_THRESHOLD and trigger_is_valid:
        return {"status": "approved", "payout": DEFAULT_APPROVED_PAYOUT}

    return {"status": "rejected", "payout": 0.0}


def _simple_decision(
    fraud_score: float,
    trigger_detected: bool,
    verification_required: bool,
) -> Dict[str, Any]:
    verification_status: Any = "pending" if verification_required else "verified"
    decision = claim_decision_engine(
        fraud_score=fraud_score,
        trigger_valid=trigger_detected,
        verification_status=verification_status,
    )

    status = str(decision.get("status", "rejected"))
    if status == "approved":
        reason = "Approved by decision engine"
    elif status == "verification_required":
        reason = "Additional verification is required"
    else:
        reason = "Rejected by decision engine"

    return {
        "status": status,
        "payout": float(decision.get("payout", 0.0)),
        "reason": reason,
    }


def _legacy_decision(
    claim_data: Dict[str, Any],
    movement: Dict[str, Any],
    fraud: Dict[str, Any],
    trigger: Dict[str, Any],
    social: Dict[str, Any],
    policy_match: Dict[str, Any],
    verification: Dict[str, Any],
) -> Dict[str, Any]:
    del claim_data
    del movement
    del social

    fraud_score = float(fraud.get("fraud_score", 0.0))
    trigger_detected = bool(trigger.get("trigger"))
    matched = bool(policy_match.get("matched"))

    if verification.get("verification_required"):
        verification_status: Any = "pending"
    else:
        verification_status = verification.get("verification_status", "verified")

    decision = claim_decision_engine(
        fraud_score=fraud_score,
        trigger_valid=trigger_detected and matched,
        verification_status=verification_status,
    )

    payout = float(decision.get("payout", 0.0))
    if decision.get("status") == "approved":
        max_coverage = float(policy_match.get("max_coverage", 0.0))
        eligible_payout = float(trigger.get("eligible_payout", 0.0))
        if eligible_payout > 0.0:
            payout = eligible_payout
        if max_coverage > 0.0:
            payout = min(payout, max_coverage)
        payout = round(max(0.0, payout), 2)

    status = str(decision.get("status", "rejected"))
    if status == "approved":
        reason = "Approved by decision engine"
    elif status == "verification_required":
        reason = "Additional verification is required"
    else:
        reason = "Rejected by decision engine"

    return {
        "status": status,
        "payout": payout,
        "fraud_score": round(fraud_score, 2),
        "reason": reason,
        "trigger_detected": trigger_detected,
    }


def make_claim_decision(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Decision adapter supporting both simplified and legacy signatures."""
    if len(args) == 3 and not kwargs:
        return _simple_decision(
            fraud_score=float(args[0]),
            trigger_detected=bool(args[1]),
            verification_required=bool(args[2]),
        )

    if {
        "fraud_score",
        "trigger_detected",
        "verification_required",
    }.issubset(kwargs.keys()):
        return _simple_decision(
            fraud_score=float(kwargs["fraud_score"]),
            trigger_detected=bool(kwargs["trigger_detected"]),
            verification_required=bool(kwargs["verification_required"]),
        )

    if len(args) == 7 and not kwargs:
        return _legacy_decision(
            claim_data=args[0],
            movement=args[1],
            fraud=args[2],
            trigger=args[3],
            social=args[4],
            policy_match=args[5],
            verification=args[6],
        )

    return _legacy_decision(
        claim_data=kwargs.get("claim_data", {}),
        movement=kwargs.get("movement", {}),
        fraud=kwargs.get("fraud", {}),
        trigger=kwargs.get("trigger", {}),
        social=kwargs.get("social", {}),
        policy_match=kwargs.get("policy_match", {}),
        verification=kwargs.get("verification", {}),
    )
