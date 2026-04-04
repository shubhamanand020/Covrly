"""Service utilities for auto-trigger detection and persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from backend.engines.social import detect_social_disruption
from backend.engines.trigger import detect_environmental_trigger
from backend.storage.repository import record_trigger_event


class TriggerService:
    """Domain service for system-triggered disruption events."""

    TRIGGER_PAYOUT_MAP: Dict[str, float] = {
        "heavy_rain": 8000.0,
        "curfew": 6000.0,
        "rain": 8000.0,
        "traffic": 5000.0,
        "traffic_congestion": 5000.0,
    }

    TRIGGER_POLICY_MAP: Dict[str, list[str]] = {
        "heavy_rain": ["HeatGuard", "RainSure Cover", "Holistic Cover"],
        "curfew": ["CivicShield Cover", "Holistic Cover"],
        "rain": ["HeatGuard", "RainSure Cover", "Holistic Cover"],
        "traffic": ["HeatGuard", "CivicShield Cover", "Holistic Cover"],
        "traffic_congestion": ["HeatGuard", "CivicShield Cover", "Holistic Cover"],
    }

    @staticmethod
    def _normalize_timestamp(timestamp: Any) -> str:
        if isinstance(timestamp, str) and timestamp.strip():
            return timestamp.strip()
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def detect(payload: Mapping[str, Any]) -> Dict[str, Any]:
        location = payload.get("user_location") if isinstance(payload, Mapping) else None
        if not isinstance(location, Mapping):
            raise ValueError("user_location is required")

        timestamp = TriggerService._normalize_timestamp(payload.get("timestamp"))
        trigger_payload = {
            "user_location": {
                "lat": float(location.get("lat")),
                "lng": float(location.get("lng", location.get("long"))),
            },
            "timestamp": timestamp,
        }

        env_trigger = detect_environmental_trigger(trigger_payload)
        social_trigger = detect_social_disruption(trigger_payload)

        social_detected = bool(social_trigger.get("disruption_detected", False))
        env_detected = bool(env_trigger.get("trigger_detected", False))

        trigger_detected = social_detected or env_detected
        if social_detected:
            trigger_type = str(social_trigger.get("event_type", "curfew"))
        elif env_detected:
            trigger_type = str(env_trigger.get("trigger_type", "heavy_rain"))
        else:
            trigger_type = "none"

        payout = float(TriggerService.TRIGGER_PAYOUT_MAP.get(trigger_type, 0.0))
        policy_types = TriggerService.TRIGGER_POLICY_MAP.get(trigger_type, [])

        return {
            "trigger_detected": trigger_detected,
            "trigger_type": trigger_type,
            "eligible_payout": payout,
            "policy_types": policy_types,
            "timestamp": timestamp,
            "user_location": trigger_payload["user_location"],
        }

    @staticmethod
    def persist_detected_trigger(
        trigger_event: Mapping[str, Any],
        fraud_score: float,
        user_id: str,
    ) -> Dict[str, Any] | None:
        if not bool(trigger_event.get("trigger_detected")):
            return None

        return record_trigger_event(
            location=trigger_event.get("user_location", {}),
            timestamp=trigger_event.get("timestamp"),
            trigger_type=str(trigger_event.get("trigger_type", "none")),
            fraud_score=float(fraud_score),
            policy_types=list(trigger_event.get("policy_types", [])),
            user_id=str(user_id),
        )
