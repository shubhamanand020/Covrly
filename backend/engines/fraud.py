"""Fraud scoring engine."""

from __future__ import annotations

from typing import Any, Dict, Mapping

ANOMALY_WEIGHT = 0.3
HIGH_SPEED_WEIGHT = 0.2
INCONSISTENT_MOVEMENT_WEIGHT = 0.3

HIGH_SPEED_THRESHOLD_KMH = 100.0
INCONSISTENT_DISTANCE_THRESHOLD_KM = 5.0


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _derive_risk_band(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _is_anomaly(movement_data: Mapping[str, Any]) -> bool:
    return bool(
        movement_data.get("anomaly_flag")
        or movement_data.get("anomaly_detected")
        or movement_data.get("is_jump_anomaly")
    )


def _is_high_speed(movement_data: Mapping[str, Any]) -> bool:
    speed = _to_float(movement_data.get("speed"), 0.0)
    explicit_flag = movement_data.get("high_speed")
    if isinstance(explicit_flag, bool):
        return explicit_flag
    return speed >= HIGH_SPEED_THRESHOLD_KMH


def _is_inconsistent_movement(movement_data: Mapping[str, Any]) -> bool:
    explicit_flag = movement_data.get("inconsistent_movement")
    if isinstance(explicit_flag, bool):
        return explicit_flag

    # Fallback heuristic: a long-distance anomalous jump is treated as
    # inconsistent movement when no explicit continuity signal is provided.
    distance = _to_float(movement_data.get("distance"), 0.0)
    return _is_anomaly(movement_data) and distance >= INCONSISTENT_DISTANCE_THRESHOLD_KM


def fraud_scoring_engine(movement_data: Mapping[str, Any]) -> Dict[str, Any]:
    """Compute deterministic fraud score from movement features."""
    if not isinstance(movement_data, Mapping):
        movement_data = {}

    anomaly_flag = _is_anomaly(movement_data)
    high_speed_flag = _is_high_speed(movement_data)
    inconsistent_movement_flag = _is_inconsistent_movement(movement_data)

    score = 0.0
    if anomaly_flag:
        score += ANOMALY_WEIGHT
    if high_speed_flag:
        score += HIGH_SPEED_WEIGHT
    if inconsistent_movement_flag:
        score += INCONSISTENT_MOVEMENT_WEIGHT

    bounded_score = max(0.0, min(score, 1.0))
    rounded_score = round(bounded_score, 2)

    return {
        "fraud_score": rounded_score,
        "risk_band": _derive_risk_band(rounded_score),
        "explanation": {
            "weights": {
                "anomaly": ANOMALY_WEIGHT,
                "high_speed": HIGH_SPEED_WEIGHT,
                "inconsistent_movement": INCONSISTENT_MOVEMENT_WEIGHT,
            },
            "signals": {
                "anomaly": anomaly_flag,
                "high_speed": high_speed_flag,
                "inconsistent_movement": inconsistent_movement_flag,
            },
        },
    }


def score_fraud(claim_data: Dict[str, Any], movement: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible wrapper for existing pipeline callers."""
    del claim_data
    return fraud_scoring_engine(movement)


def calculate_fraud_score(movement_data: Mapping[str, Any]) -> float:
    """Return normalized fraud score as a plain float for pipeline orchestration."""
    result = fraud_scoring_engine(movement_data)
    return float(result.get("fraud_score", 0.0))
