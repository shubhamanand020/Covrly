"""Service utilities for fraud scoring and risk gating."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from backend.engines.fraud import calculate_fraud_score
from backend.engines.movement import analyze_movement
from backend.storage.repository import get_user_fraud_history


class FraudService:
    """Domain service for fraud scoring and threshold checks."""

    AUTO_VERIFICATION_THRESHOLD = 0.3
    MANUAL_CURRENT_THRESHOLD = 0.65
    MANUAL_HISTORY_THRESHOLD = 0.75

    @staticmethod
    def score_claim(payload: Mapping[str, Any]) -> float:
        movement = analyze_movement(dict(payload))
        return float(calculate_fraud_score(movement))

    @staticmethod
    def requires_auto_verification(fraud_score: float) -> bool:
        return float(fraud_score) >= FraudService.AUTO_VERIFICATION_THRESHOLD

    @staticmethod
    def evaluate_manual_risk(user_id: str, current_fraud_score: float, trigger_fraud_score: float) -> Tuple[bool, float, str]:
        effective_score = max(float(current_fraud_score), float(trigger_fraud_score))
        history = get_user_fraud_history(user_id)

        if effective_score >= FraudService.MANUAL_CURRENT_THRESHOLD:
            return (False, effective_score, "High-risk claim rejected")

        high_risk_history_hits = sum(
            1 for score in history if float(score) >= FraudService.MANUAL_HISTORY_THRESHOLD
        )
        if high_risk_history_hits >= 2:
            return (False, effective_score, "User flagged as high-risk")

        return (True, effective_score, "")
