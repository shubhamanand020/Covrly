"""Service utilities for manual claim metadata validation and trigger matching."""

from __future__ import annotations

from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any, Dict, Mapping, Optional, Tuple

from backend.storage.repository import find_matching_trigger


class ClaimMatchingService:
    """Domain service for manual-claim image metadata checks and trigger matching."""

    IMAGE_LOCATION_TOLERANCE_KM = 3.0
    IMAGE_TIME_TOLERANCE_SECONDS = 3 * 60 * 60

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

        if not isinstance(value, str) or not value.strip():
            raise ValueError("timestamp must be a non-empty ISO string")

        normalized = value.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _extract_image_location(metadata: Mapping[str, Any]) -> Optional[Tuple[float, float]]:
        for key in ("user_location", "location"):
            location = metadata.get(key)
            if isinstance(location, Mapping):
                try:
                    return (float(location.get("lat")), float(location.get("lng", location.get("long"))))
                except (TypeError, ValueError):
                    continue

        location_text = metadata.get("location_text")
        if isinstance(location_text, str) and "," in location_text:
            parts = [part.strip() for part in location_text.split(",") if part.strip()]
            if len(parts) == 2:
                try:
                    return (float(parts[0]), float(parts[1]))
                except ValueError:
                    return None

        return None

    @staticmethod
    def _extract_image_timestamp(metadata: Mapping[str, Any]) -> Optional[datetime]:
        direct = metadata.get("timestamp")
        if isinstance(direct, str) and direct.strip():
            try:
                return ClaimMatchingService._parse_timestamp(direct)
            except ValueError:
                return None

        date_value = str(metadata.get("date") or "").strip()
        if not date_value:
            return None

        time_value = str(metadata.get("time") or "").strip()
        if not time_value:
            time_range = str(metadata.get("time_range") or "").strip()
            if time_range:
                time_value = time_range.split("-")[0].strip()

        if not time_value:
            time_value = "00:00"

        try:
            return ClaimMatchingService._parse_timestamp(f"{date_value}T{time_value}:00+00:00")
        except ValueError:
            return None

    @staticmethod
    def _haversine_km(origin: Tuple[float, float], target: Tuple[float, float]) -> float:
        lat1, lon1 = origin
        lat2, lon2 = target

        earth_radius_km = 6371.0
        d_lat = radians(lat2 - lat1)
        d_lon = radians(lon2 - lon1)
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)

        a = sin(d_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(d_lon / 2) ** 2
        c = 2 * asin(min(1.0, sqrt(a)))
        return earth_radius_km * c

    @staticmethod
    def validate_image_metadata(
        image_metadata: Mapping[str, Any],
        user_location: Mapping[str, Any],
        claim_timestamp: str,
    ) -> Tuple[bool, str]:
        if not image_metadata:
            return (False, "Geotagged image metadata is required")

        image_location = ClaimMatchingService._extract_image_location(image_metadata)
        if image_location is None:
            return (False, "Image location metadata missing")

        image_timestamp = ClaimMatchingService._extract_image_timestamp(image_metadata)
        if image_timestamp is None:
            return (False, "Image timestamp metadata missing")

        claim_location = (
            float(user_location.get("lat")),
            float(user_location.get("lng", user_location.get("long"))),
        )
        claim_time = ClaimMatchingService._parse_timestamp(claim_timestamp)

        location_delta = ClaimMatchingService._haversine_km(claim_location, image_location)
        if location_delta > ClaimMatchingService.IMAGE_LOCATION_TOLERANCE_KM:
            return (False, "Image location does not match claim location")

        time_delta = abs((claim_time - image_timestamp).total_seconds())
        if time_delta > ClaimMatchingService.IMAGE_TIME_TOLERANCE_SECONDS:
            return (False, "Image timestamp does not match claim time")

        return (True, "")

    @staticmethod
    def match_trigger(
        policy_type: str,
        user_location: Mapping[str, Any],
        timestamp: str,
        user_id: str,
    ) -> Dict[str, Any] | None:
        return find_matching_trigger(
            location=user_location,
            timestamp=timestamp,
            policy_type=policy_type,
            user_id=user_id,
        )
