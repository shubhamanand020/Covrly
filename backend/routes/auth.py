"""Authentication routes for register and login."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=6)
    otp: str = Field(..., min_length=6, max_length=6)


class RequestRegistrationOtpRequest(BaseModel):
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=1)


class RegisterResponse(BaseModel):
    status: str
    data: Dict[str, Any]


class RequestRegistrationOtpResponse(BaseModel):
    status: str
    data: Dict[str, Any]


class LoginResponse(BaseModel):
    status: str
    data: Dict[str, Any]


@router.post("/register/request-otp", response_model=RequestRegistrationOtpResponse)
def request_register_otp(payload: RequestRegistrationOtpRequest) -> Dict[str, Any]:
    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()

    try:
        result = AuthService.request_registration_otp(
            email=str(payload_data.get("email")),
        )
        return {
            "status": "success",
            "data": result,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to send OTP") from exc


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest) -> Dict[str, Any]:
    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()

    try:
        user = AuthService.register(
            email=str(payload_data.get("email")),
            password=str(payload_data.get("password")),
            otp=str(payload_data.get("otp")),
        )
        return {
            "status": "success",
            "data": {
                "message": "User registered successfully",
                "user": user,
            },
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Registration failed") from exc


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> Dict[str, Any]:
    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()

    try:
        login_data = AuthService.login(
            email=str(payload_data.get("email")),
            password=str(payload_data.get("password")),
        )
        return {
            "status": "success",
            "data": login_data,
        }
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Login failed") from exc
