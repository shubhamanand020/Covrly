"""Authenticated policy management routes for buy/list flows."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.routes.dependencies import require_authenticated_user
from backend.services.policy_lifecycle_service import PolicyLifecycleService

router = APIRouter(tags=["policies"])


class BuyPolicyRequest(BaseModel):
    policy_type: str = Field(..., min_length=1)
    lat: float | None = Field(default=None, ge=-90.0, le=90.0)
    lng: float | None = Field(default=None, ge=-180.0, le=180.0)
    timestamp: str | None = None


class BuyPolicyResponse(BaseModel):
    status: str
    data: Dict[str, Any]


class UserPoliciesResponse(BaseModel):
    status: str
    data: List[Dict[str, Any]]


@router.post("/policies/buy", response_model=BuyPolicyResponse)
def buy_policy(
    payload: BuyPolicyRequest,
    user_id: str = Depends(require_authenticated_user),
) -> Dict[str, Any]:
    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()

    try:
        lat = payload_data.get("lat")
        lng = payload_data.get("lng")
        if (lat is None) != (lng is None):
            raise ValueError("Both lat and lng are required when providing location")

        policy = PolicyLifecycleService.buy_policy(
            user_id=user_id,
            policy_type=str(payload_data.get("policy_type") or ""),
            lat=float(lat) if lat is not None else None,
            lng=float(lng) if lng is not None else None,
            timestamp=payload_data.get("timestamp"),
        )
        policy["status"] = "active" if bool(policy.get("is_active")) else "expired"
        return {
            "status": "success",
            "data": policy,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to buy policy") from exc


@router.get("/policies/my", response_model=UserPoliciesResponse)
def get_user_policies(user_id: str = Depends(require_authenticated_user)) -> Dict[str, Any]:
    try:
        policies = PolicyLifecycleService.list_user_policies(user_id)
        return {
            "status": "success",
            "data": policies,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to load user policies") from exc
