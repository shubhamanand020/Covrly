"""Authentication service for user registration, login, and JWT validation."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from urllib import error as url_error
from urllib import request as url_request

import bcrypt
import jwt

from backend.storage.mongo_repository import (
    create_user,
    delete_registration_otp,
    get_registration_otp,
    get_user_by_email,
    get_user_by_id,
    increment_registration_otp_attempt,
    upsert_registration_otp,
)

JWT_SECRET = os.getenv("COVRLY_JWT_SECRET", "covrly-dev-secret-chbkxbkvbdjsvbskdange-me-32chars")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
OTP_DIGITS = 6
OTP_EXPIRY_MINUTES = int(os.getenv("COVRLY_OTP_EXPIRY_MINUTES", "10"))
OTP_MAX_ATTEMPTS = int(os.getenv("COVRLY_OTP_MAX_ATTEMPTS", "5"))
OTP_SECRET = os.getenv("COVRLY_OTP_SECRET", JWT_SECRET)
LOGGER = logging.getLogger(__name__)


def send_otp_email(to_email: str, otp: str) -> None:
    resend_api_key = str(os.getenv("RESEND_API_KEY", "")).strip()
    if not resend_api_key:
        raise ValueError("Resend API key is not configured. Set RESEND_API_KEY.")

    payload = {
        "from": "onboarding@resend.dev",
        "to": [to_email],
        "subject": "Your OTP Code",
        "html": f"<p>Your OTP is <b>{otp}</b></p>",
    }

    request_body = json.dumps(payload).encode("utf-8")
    request = url_request.Request(
        url="https://api.resend.com/emails",
        data=request_body,
        method="POST",
        headers={
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with url_request.urlopen(request, timeout=15) as response:
            status_code = int(getattr(response, "status", 0) or 0)
            if status_code < 200 or status_code >= 300:
                LOGGER.error("Resend returned unexpected status code %s", status_code)
                raise ValueError("Unable to send OTP right now")
    except url_error.HTTPError as exc:
        response_body = ""
        try:
            response_body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            response_body = ""
        LOGGER.error("Resend HTTP error %s: %s", exc.code, response_body or exc.reason)
        raise ValueError("Unable to send OTP right now") from exc
    except url_error.URLError as exc:
        LOGGER.error("Resend network error: %s", exc.reason)
        raise ValueError("Unable to send OTP right now") from exc
    except Exception as exc:
        LOGGER.exception("Unexpected error while sending OTP via Resend")
        raise ValueError("Unable to send OTP right now") from exc


class AuthService:
    """Service for registration, login, and token verification."""

    @staticmethod
    def _normalize_email(email: str) -> str:
        normalized_email = str(email or "").strip().lower()
        if not normalized_email:
            raise ValueError("Email is required")
        if not EMAIL_PATTERN.match(normalized_email):
            raise ValueError("Invalid email format")
        return normalized_email

    @staticmethod
    def _generate_otp() -> str:
        return "".join(str(secrets.randbelow(10)) for _ in range(OTP_DIGITS))

    @staticmethod
    def _hash_otp(email: str, otp: str) -> str:
        payload = f"{str(email).strip().lower()}:{str(otp).strip()}:{OTP_SECRET}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def request_registration_otp(email: str) -> Dict[str, Any]:
        normalized_email = AuthService._normalize_email(email)

        existing_user = get_user_by_email(normalized_email)
        if existing_user is not None:
            raise ValueError("User already exists for this email")

        otp = AuthService._generate_otp()
        otp_hash = AuthService._hash_otp(normalized_email, otp)
        expiry = datetime.now(timezone.utc) + timedelta(minutes=max(1, OTP_EXPIRY_MINUTES))
        upsert_registration_otp(normalized_email, otp_hash, expiry.isoformat())

        try:
            send_otp_email(normalized_email, otp)
        except Exception as exc:
            delete_registration_otp(normalized_email)
            raise ValueError(str(exc)) from exc

        return {
            "message": "OTP sent to your email",
            "email": normalized_email,
            "expires_in_minutes": max(1, OTP_EXPIRY_MINUTES),
        }

    @staticmethod
    def register(email: str, password: str, otp: str) -> Dict[str, Any]:
        normalized_email = AuthService._normalize_email(email)
        plain_password = str(password or "")
        normalized_otp = str(otp or "").strip()

        if len(plain_password) < 6:
            raise ValueError("Password must be at least 6 characters long")
        if len(normalized_otp) != OTP_DIGITS or not normalized_otp.isdigit():
            raise ValueError("OTP must be a 6-digit code")

        otp_record = get_registration_otp(normalized_email)
        if otp_record is None:
            raise ValueError("OTP not requested for this email")

        try:
            expires_at = datetime.fromisoformat(str(otp_record.get("expires_at")).replace("Z", "+00:00"))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        except Exception:
            delete_registration_otp(normalized_email)
            raise ValueError("OTP expired. Request a new OTP")

        now = datetime.now(timezone.utc)
        if now > expires_at:
            delete_registration_otp(normalized_email)
            raise ValueError("OTP expired. Request a new OTP")

        attempts = int(otp_record.get("attempts") or 0)
        if attempts >= max(1, OTP_MAX_ATTEMPTS):
            delete_registration_otp(normalized_email)
            raise ValueError("OTP attempts exceeded. Request a new OTP")

        expected_hash = str(otp_record.get("otp_hash") or "")
        submitted_hash = AuthService._hash_otp(normalized_email, normalized_otp)
        if not expected_hash or submitted_hash != expected_hash:
            updated_attempts = increment_registration_otp_attempt(normalized_email)
            remaining_attempts = max(0, max(1, OTP_MAX_ATTEMPTS) - updated_attempts)
            if remaining_attempts <= 0:
                delete_registration_otp(normalized_email)
                raise ValueError("OTP attempts exceeded. Request a new OTP")
            raise ValueError(f"Invalid OTP. {remaining_attempts} attempt(s) remaining")

        delete_registration_otp(normalized_email)

        password_hash = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
        user = create_user(normalized_email, password_hash)

        return {
            "user_id": user["id"],
            "email": user["email"],
            "created_at": user["created_at"],
        }

    @staticmethod
    def login(email: str, password: str) -> Dict[str, Any]:
        normalized_email = str(email or "").strip().lower()
        plain_password = str(password or "")

        if not EMAIL_PATTERN.match(normalized_email):
            raise ValueError("Invalid email or password")

        user = get_user_by_email(normalized_email)
        if user is None:
            raise ValueError("Invalid email or password")

        stored_hash = str(user.get("password_hash") or "")
        if not stored_hash or not bcrypt.checkpw(plain_password.encode("utf-8"), stored_hash.encode("utf-8")):
            raise ValueError("Invalid email or password")

        token = AuthService.create_access_token(str(user["id"]))
        return {
            "token": token,
            "token_type": "bearer",
            "expires_in_days": JWT_EXPIRY_DAYS,
            "user": {
                "id": user["id"],
                "email": user["email"],
            },
        }

    @staticmethod
    def create_access_token(user_id: str) -> str:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=JWT_EXPIRY_DAYS)
        payload = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def verify_access_token(token: str) -> str:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError as exc:
            raise ValueError("Token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise ValueError("Invalid token") from exc

        user_id = str(payload.get("sub") or "").strip()
        if not user_id:
            raise ValueError("Invalid token payload")

        user = get_user_by_id(user_id)
        if user is None:
            raise ValueError("User not found")

        return user_id
