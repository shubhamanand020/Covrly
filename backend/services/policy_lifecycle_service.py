"""Policy lifecycle service for purchase, expiration checks, and claim eligibility."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from backend.services.pricing_service import PricingService
from backend.storage import mongo_repository


class PolicyLifecycleService:
    """Service for buying policies and enforcing expiry-based claim eligibility."""

    @staticmethod
    def _resolve_purchase_location(lat: float | None, lng: float | None) -> Dict[str, float]:
        if lat is not None and lng is not None:
            return {
                "lat": float(lat),
                "lng": float(lng),
            }

        return PricingService.default_location()

    @staticmethod
    def buy_policy(
        user_id: str,
        policy_type: str,
        lat: float | None = None,
        lng: float | None = None,
        timestamp: str | None = None,
    ) -> Dict[str, Any]:
        normalized_type = str(policy_type or "").strip()
        if not normalized_type:
            raise ValueError("policy_type is required")

        purchase_location = PolicyLifecycleService._resolve_purchase_location(lat, lng)
        factors = PricingService.build_dynamic_factors(
            lat=float(purchase_location["lat"]),
            lng=float(purchase_location["lng"]),
            timestamp=timestamp,
        )
        premium = PricingService.calculate_premium(policy_type=normalized_type, factors=factors)

        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=7)

        return mongo_repository.create_policy(
            user_id=user_id,
            policy_type=normalized_type,
            base_premium=float(premium.get("base_premium", 0.0)),
            dynamic_premium=float(premium.get("final_premium", 0.0)),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            is_active=True,
        )

    @staticmethod
    def list_user_policies(user_id: str) -> List[Dict[str, Any]]:
        policies = mongo_repository.list_user_policies(user_id)

        enriched: List[Dict[str, Any]] = []
        for policy in policies:
            item = dict(policy)
            item["status"] = "active" if bool(item.get("is_active")) else "expired"
            enriched.append(item)

        return enriched

    @staticmethod
    def ensure_policy_active_for_claim(user_id: str, policy_type: str) -> Dict[str, Any]:
        policy = mongo_repository.get_latest_policy_for_type(user_id=user_id, policy_type=policy_type)
        if policy is None:
            raise PermissionError("No policy found for this claim type")

        if not bool(policy.get("is_active")):
            raise PermissionError("Policy expired")

        return policy

    @staticmethod
    def ensure_any_active_policy(user_id: str) -> None:
        policies = mongo_repository.list_user_policies(user_id)
        has_active = any(bool(policy.get("is_active")) for policy in policies)
        if not has_active:
            raise PermissionError("Policy expired")
