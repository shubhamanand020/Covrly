"""Service utilities for auto-flow verification and claim finalization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from backend.engines.verification import verify_claim
from backend.services.fraud_service import FraudService


class VerificationService:
    """Domain service for auto-claim verification checks."""

    @staticmethod
    def evaluate_auto_verification(
        claim_record: Mapping[str, Any],
        verification_payload: Mapping[str, Any],
    ) -> Dict[str, Any]:
        claim_fraud_score = float(claim_record.get("fraud_score") or 0.0)
        if claim_fraud_score >= FraudService.MANUAL_CURRENT_THRESHOLD:
            return {
                "is_verified": False,
                "verification_status": "failed",
                "confidence_score": 0.0,
                "risk_reason": "High-risk claim blocked during verification",
            }

        image_metadata = verification_payload.get("image_metadata")
        if not isinstance(image_metadata, Mapping) or not image_metadata:
            raise ValueError("Image metadata is required for verification")

        fallback_location = (
            verification_payload.get("user_location")
            or claim_record.get("user_location")
        )
        fallback_timestamp = (
            verification_payload.get("timestamp")
            or datetime.now(timezone.utc).isoformat()
        )

        engine_payload = {
            "image_metadata": {
                **dict(image_metadata),
                "user_location": image_metadata.get("user_location") or fallback_location,
                "timestamp": image_metadata.get("timestamp") or fallback_timestamp,
            },
            "trigger_event": {
                "location": claim_record.get("user_location"),
                "timestamp": claim_record.get("timestamp"),
                "trigger_type": claim_record.get("trigger_type"),
            },
        }

        verification_result = verify_claim(engine_payload)
        verification_status = str(verification_result.get("verification_status", "failed"))
        is_verified = verification_status == "verified"

        return {
            "is_verified": is_verified,
            "verification_status": verification_status,
            "confidence_score": float(verification_result.get("confidence_score", 0.0)),
        }
