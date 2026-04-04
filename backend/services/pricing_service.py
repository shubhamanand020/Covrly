"""Dynamic pricing service for policy premium calculation."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from math import radians, sin
from typing import Any, Dict, Mapping
from urllib.parse import urlencode
from urllib.request import urlopen


class PricingService:
    """Calculate premium adjustments from simple risk factors."""

    OPENWEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
    OPEN_METEO_API_URL = "https://api.open-meteo.com/v1/forecast"
    DEFAULT_LAT = 12.9716 # mock latitude for testing
    DEFAULT_LNG = 77.5946   #mock longitiude for testing

    POLICY_BASE: Dict[str, int] = {
        "HeatGuard": 100,
        "RainSure Cover": 120,
        "CivicShield Cover": 90,
        "Holistic Cover": 150,
    }

    @staticmethod
    def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
        return max(lower, min(upper, float(value)))

    @staticmethod
    def default_location() -> Dict[str, float]:
        try:
            lat = float(os.getenv("COVRLY_DEFAULT_LAT", str(PricingService.DEFAULT_LAT)))
            lng = float(os.getenv("COVRLY_DEFAULT_LNG", str(PricingService.DEFAULT_LNG)))
        except ValueError:
            lat = PricingService.DEFAULT_LAT
            lng = PricingService.DEFAULT_LNG

        if not (-90.0 <= lat <= 90.0):
            lat = PricingService.DEFAULT_LAT
        if not (-180.0 <= lng <= 180.0):
            lng = PricingService.DEFAULT_LNG

        return {
            "lat": lat,
            "lng": lng,
        }

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

        if isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
                return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        return datetime.now(timezone.utc)

    @staticmethod
    def _fetch_json(url: str, params: Mapping[str, Any], timeout_seconds: int = 7) -> Dict[str, Any]:
        serialized = {
            key: value
            for key, value in params.items()
            if value is not None
        }
        query = urlencode(serialized)
        with urlopen(f"{url}?{query}", timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8")
        return json.loads(payload)

    @staticmethod
    def _open_meteo_condition(weather_code: Any) -> str:
        try:
            code = int(weather_code)
        except (TypeError, ValueError):
            return "unknown"

        if code in {51, 53, 55, 61, 63, 65, 66, 67, 80, 81, 82}:
            return "rain"
        if code in {71, 73, 75, 77, 85, 86}:
            return "snow"
        if code in {95, 96, 99}:
            return "thunderstorm"
        if code in {0, 1}:
            return "clear"
        return "clouds"

    @staticmethod
    def _fetch_openweather_snapshot(lat: float, lng: float, api_key: str) -> Dict[str, Any]:
        payload = PricingService._fetch_json(
            PricingService.OPENWEATHER_API_URL,
            {
                "lat": float(lat),
                "lon": float(lng),
                "appid": api_key,
                "units": "metric",
            },
        )

        status = str(payload.get("cod") or "200") if isinstance(payload, dict) else "200"
        if status not in {"200", "OK"}:
            raise ValueError("openweather request failed")

        weather_main = ""
        weather_items = payload.get("weather", []) if isinstance(payload, dict) else []
        if isinstance(weather_items, list) and weather_items:
            first = weather_items[0] if isinstance(weather_items[0], dict) else {}
            weather_main = str(first.get("main") or first.get("description") or "").strip().lower()

        rain_mm = 0.0
        rain_payload = payload.get("rain") if isinstance(payload, dict) else None
        if isinstance(rain_payload, dict):
            try:
                rain_mm = float(rain_payload.get("1h") or rain_payload.get("3h") or 0.0)
            except (TypeError, ValueError):
                rain_mm = 0.0

        temperature_c = None
        main_payload = payload.get("main", {}) if isinstance(payload, dict) else {}
        if isinstance(main_payload, dict):
            try:
                temperature_c = float(main_payload.get("temp"))
            except (TypeError, ValueError):
                temperature_c = None

        return {
            "rain_mm": max(0.0, rain_mm),
            "temperature_c": temperature_c,
            "condition": weather_main or "unknown",
            "source": "openweather",
        }

    @staticmethod
    def _fetch_open_meteo_snapshot(lat: float, lng: float) -> Dict[str, Any]:
        payload = PricingService._fetch_json(
            PricingService.OPEN_METEO_API_URL,
            {
                "latitude": float(lat),
                "longitude": float(lng),
                "current": "temperature_2m,rain,precipitation,weather_code",
                "timezone": "UTC",
            },
        )

        current = payload.get("current", {}) if isinstance(payload, dict) else {}
        if not isinstance(current, dict):
            current = {}

        rain_mm = 0.0
        for key in ("rain", "precipitation"):
            try:
                rain_mm = max(rain_mm, float(current.get(key) or 0.0))
            except (TypeError, ValueError):
                continue

        try:
            temperature_c = float(current.get("temperature_2m"))
        except (TypeError, ValueError):
            temperature_c = None

        condition = PricingService._open_meteo_condition(current.get("weather_code"))

        return {
            "rain_mm": max(0.0, rain_mm),
            "temperature_c": temperature_c,
            "condition": condition,
            "source": "open_meteo",
        }

    @staticmethod
    def fetch_weather_snapshot(lat: float, lng: float) -> Dict[str, Any]:
        api_key = str(os.getenv("OPENWEATHER_API_KEY", "")).strip()

        if api_key:
            try:
                return PricingService._fetch_openweather_snapshot(lat=float(lat), lng=float(lng), api_key=api_key)
            except Exception:
                pass

        try:
            return PricingService._fetch_open_meteo_snapshot(lat=float(lat), lng=float(lng))
        except Exception:
            return {
                "rain_mm": 0.0,
                "temperature_c": None,
                "condition": "unknown",
                "source": "weather_unavailable",
            }

    @staticmethod
    def _weather_risk_from_snapshot(snapshot: Mapping[str, Any]) -> float:
        rain_mm = float(snapshot.get("rain_mm") or 0.0)
        condition = str(snapshot.get("condition") or "").strip().lower()

        rain_component = 0.6 * PricingService._clamp(rain_mm / 20.0)
        storm_component = 0.0
        if any(token in condition for token in ("storm", "thunder", "squall")):
            storm_component = 0.2
        elif any(token in condition for token in ("rain", "drizzle", "snow")):
            storm_component = 0.1

        temperature_component = 0.0
        temperature_value = snapshot.get("temperature_c")
        if isinstance(temperature_value, (int, float)):
            temperature = float(temperature_value)
            heat_risk = PricingService._clamp((temperature - 32.0) / 15.0)
            cold_risk = PricingService._clamp((8.0 - temperature) / 16.0)
            temperature_component = (0.25 * heat_risk) + (0.1 * cold_risk)

        return round(PricingService._clamp(rain_component + storm_component + temperature_component, 0.0, 0.95), 4)

    @staticmethod
    def _region_risk_from_location(lat: float, lng: float) -> float:
        latitude = abs(float(lat))
        longitude = float(lng)

        tropical_exposure = PricingService._clamp(1.0 - min(latitude, 60.0) / 60.0)
        longitude_variation = 0.5 + (0.5 * abs(sin(radians(longitude * 2.0))))
        score = 0.2 + (0.5 * tropical_exposure) + (0.2 * longitude_variation)

        return round(PricingService._clamp(score, 0.0, 0.95), 4)

    @staticmethod
    def _traffic_risk_from_context(weather_risk: float, lat: float, lng: float, timestamp: datetime) -> float:
        hour = int(timestamp.astimezone(timezone.utc).hour)
        if (7 <= hour <= 10) or (16 <= hour <= 20):
            time_component = 0.8
        elif 11 <= hour <= 15:
            time_component = 0.45
        else:
            time_component = 0.25

        corridor_component = 0.35 + (0.35 * abs(sin(radians((float(lat) + float(lng)) * 3.0))))
        weather_component = 0.35 * PricingService._clamp(weather_risk)
        score = (0.4 * time_component) + (0.35 * corridor_component) + weather_component

        return round(PricingService._clamp(score, 0.0, 0.95), 4)

    @staticmethod
    def build_dynamic_factors(*, lat: float, lng: float, timestamp: Any = None) -> Dict[str, float]:
        latitude = float(lat)
        longitude = float(lng)
        if not (-90.0 <= latitude <= 90.0):
            raise ValueError("Latitude out of range")
        if not (-180.0 <= longitude <= 180.0):
            raise ValueError("Longitude out of range")

        observed_at = PricingService._parse_timestamp(timestamp)
        weather_snapshot = PricingService.fetch_weather_snapshot(latitude, longitude)
        weather_risk = PricingService._weather_risk_from_snapshot(weather_snapshot)
        traffic_risk = PricingService._traffic_risk_from_context(weather_risk, latitude, longitude, observed_at)
        region_risk = PricingService._region_risk_from_location(latitude, longitude)

        return {
            "weatherRisk": weather_risk,
            "trafficRisk": traffic_risk,
            "regionRisk": region_risk,
        }

    @staticmethod
    def calculate_risk_score(factors: Mapping[str, Any]) -> float:
        weather_risk = float(factors.get("weatherRisk", 0.0))
        traffic_risk = float(factors.get("trafficRisk", 0.0))
        region_risk = float(factors.get("regionRisk", 0.0))

        score = (0.4 * weather_risk) + (0.3 * traffic_risk) + (0.3 * region_risk)
        return round(PricingService._clamp(score), 4)

    @staticmethod
    def calculate_premium(policy_type: str, factors: Mapping[str, Any]) -> Dict[str, Any]:
        base = int(PricingService.POLICY_BASE.get(str(policy_type).strip(), 100))
        risk_score = PricingService.calculate_risk_score(factors)
        premium = round(base * (1 + risk_score))

        return {
            "base_premium": base,
            "risk_score": risk_score,
            "final_premium": int(premium),
            "factors": {
                "weatherRisk": float(factors.get("weatherRisk", 0.0)),
                "trafficRisk": float(factors.get("trafficRisk", 0.0)),
                "regionRisk": float(factors.get("regionRisk", 0.0)),
            },
        }
