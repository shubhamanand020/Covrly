"""Claim-related API routes built around explicit entry points."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Mapping, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.engines.matching import get_policies_catalog
from backend.routes.dependencies import require_authenticated_user
from backend.services import (
    ClaimMatchingService,
    FraudService,
    PolicyLifecycleService,
    ProfileService,
    TriggerService,
    VerificationService,
)
from backend.storage.repository import (
    append_user_fraud_score,
    create_claim_record,
    get_claim_record,
    get_latest_pending_verification_claim,
    update_claim_record,
)

router = APIRouter()


class UserLocation(BaseModel):
    model_config = ConfigDict(extra="allow")

    lat: float
    lng: Optional[float] = None
    long: Optional[float] = None

    @model_validator(mode="after")
    def _ensure_lng(self) -> "UserLocation":
        if self.lng is None and self.long is None:
            raise ValueError("Either lng or long must be provided")

        if self.lng is None:
            object.__setattr__(self, "lng", float(self.long))

        return self

    def as_dict(self) -> Dict[str, float]:
        return {
            "lat": float(self.lat),
            "lng": float(self.lng),
        }


class TimedUserLocation(UserLocation):
    timestamp: Optional[str] = None


class AutoTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_location: UserLocation
    timestamp: Optional[str] = None
    user_id: Optional[str] = None
    previous_location: Optional[TimedUserLocation] = None


class AutoVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    claim_id: Optional[str] = None
    user_id: Optional[str] = None
    user_location: Optional[UserLocation] = None
    timestamp: Optional[str] = None
    image_metadata: Dict[str, Any]


class ManualClaimRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_id: Optional[str] = None
    policy_type: str = Field(..., min_length=1)
    lat: Optional[float] = None
    lng: Optional[float] = None
    user_location: Optional[UserLocation] = None
    timestamp: str = Field(..., min_length=1)
    image: Optional[str] = None
    image_metadata: Optional[Dict[str, Any]] = None
    claim_type: Optional[str] = None


class FlowResponse(BaseModel):
    status: Literal["approved", "verification_required", "rejected"]
    next_step: Optional[Literal["payout", "verify"]] = None
    data: Dict[str, Any]


class TriggerResponse(BaseModel):
    trigger: bool
    trigger_type: str
    eligible_payout: float = Field(..., ge=0)


class PolicyResponse(BaseModel):
    name: str
    coverage: str
    zone: str
    valid_till: str
    premium_weekly: int
    max_coverage: int
    triggers: List[str]


def _safe_user_id(value: Any) -> str:
    return str(value or "anonymous").strip() or "anonymous"


def _coalesce_mapping_value(source: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key not in source:
            continue
        value = source.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _flow_response(status: str, next_step: Optional[str], data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": status,
        "next_step": next_step,
        "data": data,
    }


def _normalize_user_location(payload_data: Dict[str, Any]) -> Dict[str, float]:
    raw_location = payload_data.get("user_location")

    if isinstance(raw_location, UserLocation):
        return raw_location.as_dict()

    if isinstance(raw_location, Mapping):
        lat_value = _coalesce_mapping_value(raw_location, "lat", "latitude")
        lng_value = _coalesce_mapping_value(raw_location, "lng", "long", "longitude")
    else:
        lat_value = _coalesce_mapping_value(payload_data, "lat", "latitude")
        lng_value = _coalesce_mapping_value(payload_data, "lng", "long", "longitude")

    try:
        lat = float(lat_value)
        lng = float(lng_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Location coordinates lat and lng are required") from exc

    if not (-90.0 <= lat <= 90.0):
        raise ValueError("Latitude out of range")

    if not (-180.0 <= lng <= 180.0):
        raise ValueError("Longitude out of range")

    return {
        "lat": lat,
        "lng": lng,
    }


@router.post("/auto/trigger", response_model=FlowResponse, tags=["auto"])
def auto_trigger(
    payload: AutoTriggerRequest,
    authenticated_user_id: str = Depends(require_authenticated_user),
) -> Dict[str, Any]:
    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()

    try:
        user_id = _safe_user_id(authenticated_user_id)
        ProfileService.ensure_complete_for_claim(user_id)
        PolicyLifecycleService.ensure_any_active_policy(user_id)

        timestamp = payload_data.get("timestamp") or datetime.now(timezone.utc).isoformat()
        user_location = _normalize_user_location(payload_data)

        scoring_payload = {
            "user_location": user_location,
            "timestamp": timestamp,
            "previous_location": payload_data.get("previous_location"),
        }
        fraud_score = FraudService.score_claim(scoring_payload)
        trigger_event = TriggerService.detect(
            {
                "user_location": user_location,
                "timestamp": timestamp,
            }
        )

        TriggerService.persist_detected_trigger(
            trigger_event,
            fraud_score,
            user_id=user_id,
        )

        if not bool(trigger_event.get("trigger_detected")):
            claim_record = create_claim_record(
                user_id=user_id,
                claim_type="auto",
                status="rejected",
                payout=0.0,
                timestamp=timestamp,
                reason="No active trigger detected",
                trigger_type="none",
                fraud_score=fraud_score,
                verification_required=False,
                policy_type="System Auto",
                user_location=user_location,
                payout_candidate=0.0,
            )
            append_user_fraud_score(user_id, fraud_score)

            return _flow_response(
                status="rejected",
                next_step=None,
                data={
                    "flow": "auto",
                    "claim_id": claim_record.get("claim_id"),
                    "user_id": user_id,
                    "trigger_detected": False,
                    "trigger_type": "none",
                    "payout": 0.0,
                    "fraud_score": round(fraud_score, 2),
                    "reason": "No active trigger detected",
                },
            )

        payout_candidate = float(trigger_event.get("eligible_payout", 0.0))
        trigger_type = str(trigger_event.get("trigger_type", "none"))

        if FraudService.requires_auto_verification(fraud_score):
            claim_record = create_claim_record(
                user_id=user_id,
                claim_type="auto",
                status="verification_required",
                payout=0.0,
                timestamp=timestamp,
                reason="Verification required before payout",
                trigger_type=trigger_type,
                fraud_score=fraud_score,
                verification_required=True,
                policy_type="System Auto",
                user_location=user_location,
                payout_candidate=payout_candidate,
            )
            append_user_fraud_score(user_id, fraud_score)

            return _flow_response(
                status="verification_required",
                next_step="verify",
                data={
                    "flow": "auto",
                    "claim_id": claim_record.get("claim_id"),
                    "user_id": user_id,
                    "trigger_detected": True,
                    "trigger_type": trigger_type,
                    "payout": 0.0,
                    "fraud_score": round(fraud_score, 2),
                    "reason": "Verification required before payout",
                },
            )

        claim_record = create_claim_record(
            user_id=user_id,
            claim_type="auto",
            status="approved",
            payout=payout_candidate,
            timestamp=timestamp,
            reason="Auto payout approved",
            trigger_type=trigger_type,
            fraud_score=fraud_score,
            verification_required=False,
            policy_type="System Auto",
            user_location=user_location,
            payout_candidate=payout_candidate,
        )
        append_user_fraud_score(user_id, fraud_score)

        return _flow_response(
            status="approved",
            next_step="payout",
            data={
                "flow": "auto",
                "claim_id": claim_record.get("claim_id"),
                "user_id": user_id,
                "trigger_detected": True,
                "trigger_type": trigger_type,
                "payout": payout_candidate,
                "fraud_score": round(fraud_score, 2),
                "reason": "Auto payout approved",
            },
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to process auto trigger") from exc


@router.post("/auto/verify", response_model=FlowResponse, tags=["auto"])
def auto_verify(
    payload: AutoVerifyRequest,
    authenticated_user_id: str = Depends(require_authenticated_user),
) -> Dict[str, Any]:
    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()

    try:
        claim_id = str(payload_data.get("claim_id") or "").strip()
        user_id = _safe_user_id(authenticated_user_id)
        ProfileService.ensure_complete_for_claim(user_id)

        pending_claim = get_claim_record(claim_id) if claim_id else get_latest_pending_verification_claim(user_id)
        if pending_claim is None:
            raise ValueError("No pending verification claim found")

        pending_claim_user_id = _safe_user_id(pending_claim.get("user_id"))
        if pending_claim_user_id != user_id:
            raise PermissionError("Claim does not belong to the authenticated user")

        if str(pending_claim.get("status")) != "verification_required":
            raise ValueError("Claim is not awaiting verification")

        verification = VerificationService.evaluate_auto_verification(
            claim_record=pending_claim,
            verification_payload=payload_data,
        )

        if verification.get("is_verified"):
            payout = float(pending_claim.get("payout_candidate", 0.0))
            status = "approved"
            reason = "Verification successful"
            next_step = "payout"
        else:
            payout = 0.0
            status = "rejected"
            reason = "Verification failed"
            next_step = None

        updated_claim = update_claim_record(
            str(pending_claim.get("claim_id")),
            status=status,
            payout=payout,
            reason=reason,
            verification_required=False,
        )
        if updated_claim is None:
            raise ValueError("Unable to update claim status")

        return _flow_response(
            status=status,
            next_step=next_step,
            data={
                "flow": "auto",
                "claim_id": updated_claim.get("claim_id"),
                "user_id": updated_claim.get("user_id"),
                "trigger_detected": True,
                "trigger_type": updated_claim.get("trigger_type"),
                "payout": float(updated_claim.get("payout", 0.0)),
                "fraud_score": float(updated_claim.get("fraud_score", 0.0)),
                "reason": reason,
                "verification": {
                    "status": verification.get("verification_status"),
                    "confidence_score": verification.get("confidence_score"),
                },
            },
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to verify auto claim") from exc


@router.post("/claim/manual", response_model=FlowResponse, tags=["claims"])
def manual_claim(
    payload: ManualClaimRequest,
    authenticated_user_id: str = Depends(require_authenticated_user),
) -> Dict[str, Any]:
    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()

    try:
        user_id = _safe_user_id(authenticated_user_id)
        ProfileService.ensure_complete_for_claim(user_id)

        policy_type = str(payload_data.get("policy_type") or "").strip()
        if not policy_type:
            raise ValueError("policy_type is required")

        PolicyLifecycleService.ensure_policy_active_for_claim(user_id, policy_type)

        timestamp = str(payload_data.get("timestamp") or "").strip()
        user_location = _normalize_user_location(payload_data)

        image_metadata = payload_data.get("image_metadata")
        if not isinstance(image_metadata, dict):
            image_metadata = {}

        if not image_metadata.get("user_location"):
            image_metadata["user_location"] = user_location

        if not image_metadata.get("timestamp"):
            image_metadata["timestamp"] = timestamp

        if not image_metadata.get("policy_type"):
            image_metadata["policy_type"] = policy_type

        if payload_data.get("image") and not image_metadata.get("image_name"):
            image_metadata["image_name"] = "manual_upload"

        scoring_payload = {
            "user_location": user_location,
            "timestamp": timestamp,
            "previous_location": payload_data.get("previous_location"),
        }
        current_fraud_score = FraudService.score_claim(scoring_payload)

        metadata_ok, metadata_reason = ClaimMatchingService.validate_image_metadata(
            image_metadata=image_metadata,
            user_location=user_location,
            claim_timestamp=timestamp,
        )
        if not metadata_ok:
            claim_record = create_claim_record(
                user_id=user_id,
                claim_type="manual",
                status="rejected",
                payout=0.0,
                timestamp=timestamp,
                reason=metadata_reason,
                trigger_type="none",
                fraud_score=current_fraud_score,
                verification_required=False,
                policy_type=policy_type,
                user_location=user_location,
                payout_candidate=0.0,
            )
            append_user_fraud_score(user_id, current_fraud_score)

            return _flow_response(
                status="rejected",
                next_step=None,
                data={
                    "flow": "manual",
                    "claim_id": claim_record.get("claim_id"),
                    "user_id": user_id,
                    "trigger_detected": False,
                    "trigger_type": "none",
                    "payout": 0.0,
                    "fraud_score": round(current_fraud_score, 2),
                    "reason": metadata_reason,
                },
            )

        matched_trigger = ClaimMatchingService.match_trigger(
            policy_type=policy_type,
            user_location=user_location,
            timestamp=timestamp,
            user_id=user_id,
        )
        if matched_trigger is None:
            claim_record = create_claim_record(
                user_id=user_id,
                claim_type="manual",
                status="rejected",
                payout=0.0,
                timestamp=timestamp,
                reason="No matching trigger found",
                trigger_type="none",
                fraud_score=current_fraud_score,
                verification_required=False,
                policy_type=policy_type,
                user_location=user_location,
                payout_candidate=0.0,
            )
            append_user_fraud_score(user_id, current_fraud_score)

            return _flow_response(
                status="rejected",
                next_step=None,
                data={
                    "flow": "manual",
                    "claim_id": claim_record.get("claim_id"),
                    "user_id": user_id,
                    "trigger_detected": False,
                    "trigger_type": "none",
                    "payout": 0.0,
                    "fraud_score": round(current_fraud_score, 2),
                    "reason": "No matching trigger found",
                },
            )

        trigger_fraud_score = float(matched_trigger.get("fraud_score", 0.0))
        is_allowed, effective_score, risk_reason = FraudService.evaluate_manual_risk(
            user_id=user_id,
            current_fraud_score=current_fraud_score,
            trigger_fraud_score=trigger_fraud_score,
        )
        if not is_allowed:
            claim_record = create_claim_record(
                user_id=user_id,
                claim_type="manual",
                status="rejected",
                payout=0.0,
                timestamp=timestamp,
                reason=risk_reason,
                trigger_type=str(matched_trigger.get("trigger_type", "none")),
                fraud_score=effective_score,
                verification_required=False,
                policy_type=policy_type,
                user_location=user_location,
                payout_candidate=0.0,
            )
            append_user_fraud_score(user_id, effective_score)

            return _flow_response(
                status="rejected",
                next_step=None,
                data={
                    "flow": "manual",
                    "claim_id": claim_record.get("claim_id"),
                    "user_id": user_id,
                    "trigger_detected": True,
                    "trigger_type": str(matched_trigger.get("trigger_type", "none")),
                    "payout": 0.0,
                    "fraud_score": round(effective_score, 2),
                    "reason": risk_reason,
                },
            )

        matched_trigger_type = str(matched_trigger.get("trigger_type", "none"))
        payout = float(TriggerService.TRIGGER_PAYOUT_MAP.get(matched_trigger_type, 0.0))

        claim_record = create_claim_record(
            user_id=user_id,
            claim_type="manual",
            status="approved",
            payout=payout,
            timestamp=timestamp,
            reason="Manual claim approved after trigger and fraud validation",
            trigger_type=matched_trigger_type,
            fraud_score=effective_score,
            verification_required=False,
            policy_type=policy_type,
            user_location=user_location,
            payout_candidate=payout,
        )
        append_user_fraud_score(user_id, effective_score)

        return _flow_response(
            status="approved",
            next_step="payout",
            data={
                "flow": "manual",
                "claim_id": claim_record.get("claim_id"),
                "user_id": user_id,
                "trigger_detected": True,
                "trigger_type": matched_trigger_type,
                "payout": payout,
                "fraud_score": round(effective_score, 2),
                "reason": "Manual claim approved after trigger and fraud validation",
            },
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to process manual claim") from exc


# Legacy endpoint aliases kept for compatibility.
@router.post("/claim", response_model=FlowResponse, tags=["claims"])
def submit_claim_legacy(
    payload: ManualClaimRequest,
    authenticated_user_id: str = Depends(require_authenticated_user),
) -> Dict[str, Any]:
    return manual_claim(payload, authenticated_user_id)


@router.post("/claim/verify", response_model=FlowResponse, tags=["claims"])
def verify_claim_legacy(
    payload: AutoVerifyRequest,
    authenticated_user_id: str = Depends(require_authenticated_user),
) -> Dict[str, Any]:
    return auto_verify(payload, authenticated_user_id)


@router.get("/check-trigger", response_model=TriggerResponse, tags=["claims"])
def check_trigger_legacy(
    latitude: float = 12.97,
    longitude: float = 77.59,
    timestamp: Optional[str] = None,
    authenticated_user_id: str = Depends(require_authenticated_user),
) -> Dict[str, Any]:
    try:
        user_id = _safe_user_id(authenticated_user_id)
        ProfileService.ensure_complete_for_claim(user_id)
        PolicyLifecycleService.ensure_any_active_policy(user_id)

        timestamp_value = timestamp or datetime.now(timezone.utc).isoformat()
        payload = {
            "user_location": {"lat": latitude, "lng": longitude},
            "timestamp": timestamp_value,
        }
        fraud_score = FraudService.score_claim(payload)
        trigger_event = TriggerService.detect(payload)
        TriggerService.persist_detected_trigger(
            trigger_event,
            fraud_score,
            user_id=user_id,
        )

        return {
            "trigger": bool(trigger_event.get("trigger_detected")),
            "trigger_type": str(trigger_event.get("trigger_type", "none")),
            "eligible_payout": float(trigger_event.get("eligible_payout", 0.0)),
        }
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/policies", response_model=List[PolicyResponse], tags=["policies"])
def get_policies() -> List[Dict[str, Any]]:
    return get_policies_catalog()
