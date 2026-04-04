"""Pricing API routes for dynamic premium calculation."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.pricing_service import PricingService

router = APIRouter()


class PremiumData(BaseModel):
    base_premium: int
    final_premium: int
    risk_score: float
    factors: Dict[str, float]


class PremiumResponse(BaseModel):
    status: str
    data: PremiumData


@router.get("/premium/calculate", response_model=PremiumResponse, tags=["pricing"])
def calculate_premium(
    policy_type: str = Query(..., min_length=1),
    lat: float = Query(..., ge=-90.0, le=90.0),
    lng: float = Query(..., ge=-180.0, le=180.0),
    timestamp: str | None = Query(default=None),
) -> Dict[str, Any]:
    try:
        factors = PricingService.build_dynamic_factors(
            lat=float(lat),
            lng=float(lng),
            timestamp=timestamp,
        )

        premium = PricingService.calculate_premium(policy_type=policy_type, factors=factors)

        return {
            "status": "success",
            "data": premium,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to calculate premium") from exc
