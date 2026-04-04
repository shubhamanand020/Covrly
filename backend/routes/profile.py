"""Profile routes for authenticated users."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.routes.dependencies import require_authenticated_user
from backend.services.profile_service import ProfileService

router = APIRouter(tags=["profile"])


class ProfileUpsertRequest(BaseModel):
    name: str
    phone: str
    city: str
    vehicle_type: str
    profile_image_url: str


class ProfilePayload(BaseModel):
    user_id: str
    name: str
    phone: str
    city: str
    vehicle_type: str
    profile_image_url: str
    is_complete: bool
    updated_at: str | None = None


class ProfileResponse(BaseModel):
    status: str
    data: ProfilePayload


@router.post("/profile", response_model=ProfileResponse)
def upsert_profile(
    payload: ProfileUpsertRequest,
    user_id: str = Depends(require_authenticated_user),
) -> Dict[str, Any]:
    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()

    try:
        profile = ProfileService.upsert(
            user_id=user_id,
            name=str(payload_data.get("name") or ""),
            phone=str(payload_data.get("phone") or ""),
            city=str(payload_data.get("city") or ""),
            vehicle_type=str(payload_data.get("vehicle_type") or ""),
            profile_image_url=str(payload_data.get("profile_image_url") or ""),
        )
        return {
            "status": "success",
            "data": profile,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to save profile") from exc


@router.get("/profile", response_model=ProfileResponse)
def get_profile(user_id: str = Depends(require_authenticated_user)) -> Dict[str, Any]:
    try:
        profile = ProfileService.get(user_id)
        return {
            "status": "success",
            "data": profile,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to load profile") from exc
