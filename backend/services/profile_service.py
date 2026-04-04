"""Profile service for read/update and completion checks."""

from __future__ import annotations

from typing import Any, Dict

from backend.storage.mongo_repository import get_profile, upsert_profile


class ProfileService:
    """Service wrapper for user profile operations."""

    @staticmethod
    def get(user_id: str) -> Dict[str, Any]:
        profile = get_profile(user_id)
        if profile is None:
            return {
                "user_id": str(user_id),
                "name": "",
                "phone": "",
                "city": "",
                "vehicle_type": "",
                "profile_image_url": "",
                "is_complete": False,
                "updated_at": None,
            }
        return profile

    @staticmethod
    def upsert(
        user_id: str,
        name: str,
        phone: str,
        city: str,
        vehicle_type: str,
        profile_image_url: str,
    ) -> Dict[str, Any]:
        return upsert_profile(
            user_id=user_id,
            name=name,
            phone=phone,
            city=city,
            vehicle_type=vehicle_type,
            profile_image_url=profile_image_url,
        )

    @staticmethod
    def ensure_complete_for_claim(user_id: str) -> Dict[str, Any]:
        profile = ProfileService.get(user_id)
        if not bool(profile.get("is_complete")):
            raise PermissionError("Complete your profile before claiming")
        return profile
