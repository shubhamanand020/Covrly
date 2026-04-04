"""Routes for live rider location monitoring and environmental trigger generation."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.routes.dependencies import require_authenticated_user
from backend.services.trigger_generator_service import TriggerGeneratorService
from backend.storage.mongo_repository import list_user_triggers

router = APIRouter(tags=["monitor"])
monitor_service = TriggerGeneratorService(interval_seconds=60)


class MonitorLocationRequest(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    timestamp: str | None = None


class MonitorLocationResponse(BaseModel):
    status: str
    data: Dict[str, Any]


class MonitorTriggerHistoryResponse(BaseModel):
    status: str
    data: Dict[str, Any]


@router.post("/monitor/location", response_model=MonitorLocationResponse)
def monitor_location(
    payload: MonitorLocationRequest,
    user_id: str = Depends(require_authenticated_user),
) -> Dict[str, Any]:
    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()

    try:
        result = monitor_service.process_location_update(
            user_id=user_id,
            lat=float(payload_data.get("lat")),
            lng=float(payload_data.get("lng")),
            timestamp=payload_data.get("timestamp"),
        )

        return {
            "status": "success",
            "data": result,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to process live location") from exc


@router.get("/monitor/my-triggers", response_model=MonitorTriggerHistoryResponse)
def monitor_trigger_history(user_id: str = Depends(require_authenticated_user)) -> Dict[str, Any]:
    try:
        triggers = list_user_triggers(user_id=user_id, limit=100)
        return {
            "status": "success",
            "data": {
                "triggers": triggers,
                "count": len(triggers),
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to fetch trigger history") from exc
