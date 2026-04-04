"""Real-time environmental trigger generation service."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt
from threading import Event, Lock, Thread
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlencode
from urllib.request import urlopen

from backend.services.fraud_service import FraudService
from backend.storage.repository import has_recent_similar_trigger, record_trigger_event
from backend.storage.mongo_repository import list_recent_location_snapshots, upsert_location_snapshot


class TriggerGeneratorService:
    """Generates rain and traffic_congestion triggers from live environmental signals."""

    WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
    OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
    DIRECTIONS_API_URL = "https://maps.googleapis.com/maps/api/directions/json"

    DEFAULT_INTERVAL_SECONDS = 60
    DEFAULT_TRAFFIC_MIN_DURATION_SECONDS = 300
    DEFAULT_TRAFFIC_RATIO_THRESHOLD = 1.5
    DEFAULT_DESTINATION_OFFSET = 0.01
    DEFAULT_SECONDARY_DESTINATION_OFFSET = 0.03
    DEFAULT_TRAFFIC_FREE_SPEED_KMPH = 32.0
    DEFAULT_TRAFFIC_CONGESTED_SPEED_KMPH = 12.0
    DEFAULT_DUPLICATE_RADIUS_METERS = 100.0
    DEFAULT_DUPLICATE_WINDOW_SECONDS = 5 * 60
    DEFAULT_LOCATION_SNAPSHOT_MAX_AGE_SECONDS = 15 * 60

    EARTH_RADIUS_METERS = 6371000.0

    _recent_positions: Dict[str, Dict[str, Any]] = {}
    _recent_positions_lock = Lock()

    TRIGGER_POLICY_MAP: Dict[str, List[str]] = {
        "rain": ["HeatGuard", "RainSure Cover", "Holistic Cover"],
        "traffic_congestion": ["HeatGuard", "CivicShield Cover", "Holistic Cover"],
    }

    def __init__(
        self,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
        monitored_locations: Optional[Iterable[Dict[str, float]]] = None,
    ) -> None:
        self.interval_seconds = max(10, int(interval_seconds))
        self.monitored_locations = self._normalize_locations(monitored_locations)

        self.traffic_min_duration_seconds = int(
            os.getenv(
                "COVRLY_TRAFFIC_MIN_DURATION_SECONDS",
                str(self.DEFAULT_TRAFFIC_MIN_DURATION_SECONDS),
            )
        )
        self.traffic_ratio_threshold = float(
            os.getenv(
                "COVRLY_TRAFFIC_RATIO_THRESHOLD",
                str(self.DEFAULT_TRAFFIC_RATIO_THRESHOLD),
            )
        )
        self.destination_offset = float(
            os.getenv(
                "COVRLY_TRAFFIC_DESTINATION_OFFSET",
                str(self.DEFAULT_DESTINATION_OFFSET),
            )
        )
        self.secondary_destination_offset = max(self.destination_offset, self.DEFAULT_SECONDARY_DESTINATION_OFFSET)
        self.traffic_free_speed_kmph = max(
            5.0,
            float(
                os.getenv(
                    "COVRLY_TRAFFIC_FREE_SPEED_KMPH",
                    str(self.DEFAULT_TRAFFIC_FREE_SPEED_KMPH),
                )
            ),
        )
        self.traffic_congested_speed_kmph = max(
            2.0,
            float(
                os.getenv(
                    "COVRLY_TRAFFIC_CONGESTED_SPEED_KMPH",
                    str(self.DEFAULT_TRAFFIC_CONGESTED_SPEED_KMPH),
                )
            ),
        )
        self.duplicate_radius_meters = float(
            os.getenv(
                "COVRLY_TRIGGER_DUPLICATE_RADIUS_METERS",
                str(self.DEFAULT_DUPLICATE_RADIUS_METERS),
            )
        )
        self.duplicate_window_seconds = float(
            os.getenv(
                "COVRLY_TRIGGER_DUPLICATE_WINDOW_SECONDS",
                str(self.DEFAULT_DUPLICATE_WINDOW_SECONDS),
            )
        )
        self.location_snapshot_max_age_seconds = float(
            os.getenv(
                "COVRLY_BACKGROUND_LOCATION_MAX_AGE_SECONDS",
                str(self.DEFAULT_LOCATION_SNAPSHOT_MAX_AGE_SECONDS),
            )
        )

        self._stop_event = Event()
        self._thread: Optional[Thread] = None

    @staticmethod
    def _normalize_locations(locations: Optional[Iterable[Dict[str, float]]]) -> List[Dict[str, float]]:
        parsed_locations = list(locations or [])
        if not parsed_locations:
            parsed_locations = TriggerGeneratorService._locations_from_env()

        normalized: List[Dict[str, float]] = []
        for location in parsed_locations:
            if not isinstance(location, dict):
                continue
            try:
                lat = float(location.get("lat"))
                lng = float(location.get("lng", location.get("long")))
            except (TypeError, ValueError):
                continue

            if not (-90.0 <= lat <= 90.0):
                continue
            if not (-180.0 <= lng <= 180.0):
                continue

            normalized.append({"lat": lat, "lng": lng})

        return normalized

    @staticmethod
    def _locations_from_env() -> List[Dict[str, float]]:
        raw = str(os.getenv("COVRLY_MONITORED_LOCATIONS", "")).strip()
        if not raw:
            return []

        locations: List[Dict[str, float]] = []
        for chunk in raw.split(";"):
            item = chunk.strip()
            if not item:
                continue

            parts = [part.strip() for part in item.split(",")]
            if len(parts) != 2:
                continue

            try:
                locations.append({"lat": float(parts[0]), "lng": float(parts[1])})
            except ValueError:
                continue

        return locations

    @staticmethod
    def _normalize_timestamp(value: Optional[str]) -> datetime:
        if isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
                return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        return datetime.now(timezone.utc)

    @staticmethod
    def _fetch_json(url: str, params: Dict[str, Any], timeout_seconds: int = 8) -> Dict[str, Any]:
        query = urlencode(params)
        with urlopen(f"{url}?{query}", timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _open_meteo_condition(weather_code: int | None) -> str:
        if weather_code is None:
            return "unknown"
        if weather_code in {51, 53, 55, 61, 63, 65, 66, 67, 80, 81, 82}:
            return "Rain"
        if weather_code in {71, 73, 75, 77, 85, 86}:
            return "Snow"
        if weather_code in {0, 1}:
            return "Clear"
        return "Clouds"

    def _fetch_open_meteo_weather(self, lat: float, lng: float) -> Dict[str, Any]:
        try:
            payload = self._fetch_json(
                self.OPEN_METEO_URL,
                {
                    "latitude": float(lat),
                    "longitude": float(lng),
                    "current": "temperature_2m,rain,precipitation,weather_code",
                    "timezone": "UTC",
                },
            )
        except Exception:
            return {
                "trigger_type": None,
                "rain_mm": 0.0,
                "condition": "unknown",
                "temperature_c": None,
                "source": "open_meteo_error",
            }

        current = payload.get("current", {}) if isinstance(payload, dict) else {}
        if not isinstance(current, dict):
            current = {}

        try:
            rain_mm = float(current.get("rain") or 0.0)
        except (TypeError, ValueError):
            rain_mm = 0.0

        try:
            precipitation_mm = float(current.get("precipitation") or 0.0)
        except (TypeError, ValueError):
            precipitation_mm = 0.0

        weather_code = None
        try:
            raw_weather_code = current.get("weather_code")
            weather_code = int(raw_weather_code) if raw_weather_code is not None else None
        except (TypeError, ValueError):
            weather_code = None

        condition = self._open_meteo_condition(weather_code)

        try:
            temperature_c = float(current.get("temperature_2m"))
        except (TypeError, ValueError):
            temperature_c = None

        trigger_type = None
        if rain_mm > 0.0 or precipitation_mm > 0.0 or condition.lower() == "rain":
            trigger_type = "rain"

        return {
            "trigger_type": trigger_type,
            "rain_mm": max(rain_mm, precipitation_mm),
            "condition": condition,
            "temperature_c": temperature_c,
            "source": "open_meteo",
        }

    def fetch_weather(self, lat: float, lng: float) -> Dict[str, Any]:
        api_key = str(os.getenv("OPENWEATHER_API_KEY", "")).strip()
        if not api_key:
            return self._fetch_open_meteo_weather(lat, lng)

        try:
            payload = self._fetch_json(
                self.WEATHER_API_URL,
                {
                    "lat": float(lat),
                    "lon": float(lng),
                    "appid": api_key,
                    "units": "metric",
                },
            )
        except Exception:
            return self._fetch_open_meteo_weather(lat, lng)

        openweather_status = str(payload.get("cod") or "200") if isinstance(payload, dict) else "200"
        if openweather_status not in {"200", "OK"}:
            return self._fetch_open_meteo_weather(lat, lng)

        rain_payload = payload.get("rain") if isinstance(payload, dict) else None
        rain_exists = isinstance(rain_payload, dict) and bool(rain_payload)
        rain_mm = 0.0
        if isinstance(rain_payload, dict):
            try:
                rain_mm = float(rain_payload.get("1h") or rain_payload.get("3h") or 0.0)
            except (TypeError, ValueError):
                rain_mm = 0.0

        weather_main = ""
        weather_list = payload.get("weather", []) if isinstance(payload, dict) else []
        if isinstance(weather_list, list) and weather_list:
            first_weather = weather_list[0] if isinstance(weather_list[0], dict) else {}
            weather_main = str(first_weather.get("main") or first_weather.get("description") or "")

        temperature_c = None
        main_payload = payload.get("main", {}) if isinstance(payload, dict) else {}
        if isinstance(main_payload, dict):
            try:
                temperature_c = float(main_payload.get("temp"))
            except (TypeError, ValueError):
                temperature_c = None

        normalized_condition = weather_main.strip().lower()
        trigger_type = "rain" if rain_exists or "rain" in normalized_condition else None

        return {
            "trigger_type": trigger_type,
            "rain_mm": rain_mm,
            "condition": weather_main or "unknown",
            "temperature_c": temperature_c,
            "source": "openweather",
        }

    @staticmethod
    def _haversine_meters(start: tuple[float, float], end: tuple[float, float]) -> float:
        lat1, lon1 = start
        lat2, lon2 = end

        phi1 = radians(lat1)
        phi2 = radians(lat2)
        delta_phi = radians(lat2 - lat1)
        delta_lambda = radians(lon2 - lon1)

        a = sin(delta_phi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2.0) ** 2
        c = 2.0 * atan2(sqrt(a), sqrt(1.0 - a))
        return TriggerGeneratorService.EARTH_RADIUS_METERS * c

    def _evaluate_traffic_trigger(
        self,
        duration_seconds: int | None,
        duration_in_traffic_seconds: int | None,
    ) -> Dict[str, Any]:
        ratio = None
        trigger_type = None

        if (
            duration_seconds
            and duration_seconds > 0
            and duration_in_traffic_seconds
            and duration_in_traffic_seconds > 0
        ):
            ratio = float(duration_in_traffic_seconds) / float(duration_seconds)
            if (
                int(duration_seconds) > self.traffic_min_duration_seconds
                and ratio > self.traffic_ratio_threshold
            ):
                trigger_type = "traffic_congestion"

        return {
            "trigger_type": trigger_type,
            "duration_seconds": duration_seconds,
            "duration_in_traffic_seconds": duration_in_traffic_seconds,
            "ratio": ratio,
        }

    def _estimate_live_speed_kmph(self, user_id: str, lat: float, lng: float, timestamp: datetime) -> float | None:
        normalized_user_id = str(user_id or "system").strip() or "system"

        with self._recent_positions_lock:
            previous = self._recent_positions.get(normalized_user_id)

        if not previous:
            return None

        previous_time = previous.get("timestamp")
        if not isinstance(previous_time, datetime):
            return None

        delta_seconds = max(0.0, (timestamp - previous_time).total_seconds())
        if delta_seconds < 5.0:
            return None

        distance_meters = self._haversine_meters(
            (float(previous.get("lat")), float(previous.get("lng"))),
            (float(lat), float(lng)),
        )
        speed_mps = distance_meters / delta_seconds
        speed_kmph = speed_mps * 3.6
        return max(0.0, speed_kmph)

    def _read_previous_location(self, user_id: str, current_timestamp: datetime) -> Dict[str, Any] | None:
        normalized_user_id = str(user_id or "system").strip() or "system"

        with self._recent_positions_lock:
            previous = self._recent_positions.get(normalized_user_id)

        if isinstance(previous, dict):
            previous_timestamp = previous.get("timestamp")
            if isinstance(previous_timestamp, datetime) and previous_timestamp < current_timestamp:
                try:
                    return {
                        "lat": float(previous.get("lat")),
                        "lng": float(previous.get("lng")),
                        "timestamp": previous_timestamp.isoformat(),
                    }
                except (TypeError, ValueError):
                    pass

        try:
            snapshots = list_recent_location_snapshots(
                max_age_seconds=max(self.location_snapshot_max_age_seconds, 24 * 60 * 60),
            )
        except Exception:
            return None

        for snapshot in snapshots:
            snapshot_user_id = str(snapshot.get("user_id") or "system").strip() or "system"
            if snapshot_user_id != normalized_user_id:
                continue

            raw_timestamp = str(snapshot.get("timestamp") or "").strip()
            if not raw_timestamp:
                continue

            try:
                parsed_timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
                if parsed_timestamp.tzinfo is None:
                    parsed_timestamp = parsed_timestamp.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            if parsed_timestamp >= current_timestamp:
                continue

            try:
                return {
                    "lat": float(snapshot.get("lat")),
                    "lng": float(snapshot.get("lng")),
                    "timestamp": parsed_timestamp.isoformat(),
                }
            except (TypeError, ValueError):
                continue

        return None

    def _remember_current_position(self, user_id: str, lat: float, lng: float, timestamp: datetime) -> None:
        normalized_user_id = str(user_id or "system").strip() or "system"

        with self._recent_positions_lock:
            self._recent_positions[normalized_user_id] = {
                "lat": float(lat),
                "lng": float(lng),
                "timestamp": timestamp,
            }

    def _heuristic_traffic_fallback(self, user_id: str, lat: float, lng: float, timestamp: datetime) -> Dict[str, Any]:
        heuristic_offset = self.secondary_destination_offset
        route_distance_meters = self._haversine_meters(
            (float(lat), float(lng)),
            (float(lat) + heuristic_offset, float(lng) + heuristic_offset),
        )

        free_speed_mps = self.traffic_free_speed_kmph * (1000.0 / 3600.0)
        base_duration_seconds = int(max(1.0, route_distance_meters / free_speed_mps))

        observed_speed_kmph = self._estimate_live_speed_kmph(user_id, lat, lng, timestamp)
        if observed_speed_kmph is None:
            hour = int(timestamp.hour)
            if (8 <= hour <= 10) or (17 <= hour <= 21):
                observed_speed_kmph = self.traffic_congested_speed_kmph
            else:
                observed_speed_kmph = self.traffic_free_speed_kmph

        observed_speed_mps = max(0.5, observed_speed_kmph * (1000.0 / 3600.0))
        duration_in_traffic_seconds = int(max(1.0, route_distance_meters / observed_speed_mps))

        evaluated = self._evaluate_traffic_trigger(base_duration_seconds, duration_in_traffic_seconds)
        return {
            **evaluated,
            "source": "traffic_fallback_heuristic",
        }

    def _fetch_google_directions_metrics(
        self,
        lat: float,
        lng: float,
        timestamp: datetime,
        offset: float,
    ) -> Dict[str, Any]:
        api_key = str(os.getenv("GOOGLE_MAPS_API_KEY", "")).strip()
        if not api_key:
            return {
                "source": "missing_key",
                "duration_seconds": None,
                "duration_in_traffic_seconds": None,
            }

        destination_lat = float(lat) + float(offset)
        destination_lng = float(lng) + float(offset)

        try:
            payload = self._fetch_json(
                self.DIRECTIONS_API_URL,
                {
                    "origin": f"{float(lat)},{float(lng)}",
                    "destination": f"{destination_lat},{destination_lng}",
                    "departure_time": int(timestamp.timestamp()),
                    "traffic_model": "best_guess",
                    "key": api_key,
                },
            )
        except Exception:
            return {
                "source": "google_request_error",
                "duration_seconds": None,
                "duration_in_traffic_seconds": None,
            }

        status = str(payload.get("status") or "UNKNOWN") if isinstance(payload, dict) else "UNKNOWN"
        if status != "OK":
            return {
                "source": f"google_status_{status.lower()}",
                "duration_seconds": None,
                "duration_in_traffic_seconds": None,
            }

        routes = payload.get("routes", []) if isinstance(payload, dict) else []
        if not routes or not isinstance(routes[0], dict):
            return {
                "source": "google_no_routes",
                "duration_seconds": None,
                "duration_in_traffic_seconds": None,
            }

        legs = routes[0].get("legs", []) if isinstance(routes[0], dict) else []
        if not legs or not isinstance(legs[0], dict):
            return {
                "source": "google_no_legs",
                "duration_seconds": None,
                "duration_in_traffic_seconds": None,
            }

        leg = legs[0]
        try:
            duration_seconds = int(leg.get("duration", {}).get("value"))
        except Exception:
            duration_seconds = None

        try:
            duration_in_traffic_seconds = int(leg.get("duration_in_traffic", {}).get("value"))
        except Exception:
            duration_in_traffic_seconds = None

        return {
            "source": "google_directions",
            "duration_seconds": duration_seconds,
            "duration_in_traffic_seconds": duration_in_traffic_seconds,
        }

    def fetch_traffic(self, user_id: str, lat: float, lng: float, timestamp: datetime) -> Dict[str, Any]:
        offsets = [self.destination_offset, self.secondary_destination_offset]
        metrics: Dict[str, Any] = {
            "source": "unavailable",
            "duration_seconds": None,
            "duration_in_traffic_seconds": None,
        }

        for offset in offsets:
            probe = self._fetch_google_directions_metrics(lat=lat, lng=lng, timestamp=timestamp, offset=offset)
            if probe.get("duration_seconds") and probe.get("duration_in_traffic_seconds"):
                metrics = probe
                if int(probe["duration_seconds"]) > self.traffic_min_duration_seconds:
                    break
            elif metrics.get("duration_seconds") is None:
                metrics = probe

        if metrics.get("duration_seconds") and metrics.get("duration_in_traffic_seconds"):
            evaluated = self._evaluate_traffic_trigger(
                int(metrics["duration_seconds"]),
                int(metrics["duration_in_traffic_seconds"]),
            )
            return {
                **evaluated,
                "source": str(metrics.get("source") or "google_directions"),
            }

        fallback = self._heuristic_traffic_fallback(user_id=user_id, lat=lat, lng=lng, timestamp=timestamp)
        fallback["provider_source"] = str(metrics.get("source") or "unknown")
        return fallback

    def _store_trigger(
        self,
        *,
        user_id: str,
        trigger_type: str,
        lat: float,
        lng: float,
        timestamp: datetime,
        previous_location: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        scoring_payload = {
            "user_location": {
                "lat": float(lat),
                "lng": float(lng),
            },
            "timestamp": timestamp.isoformat(),
            "previous_location": previous_location,
        }

        try:
            fraud_score = float(FraudService.score_claim(scoring_payload))
        except Exception:
            # Trigger generation should stay resilient even if scoring fails.
            fraud_score = 0.0

        return record_trigger_event(
            user_id=str(user_id),
            location={"lat": float(lat), "lng": float(lng)},
            timestamp=timestamp.isoformat(),
            trigger_type=str(trigger_type),
            fraud_score=fraud_score,
            policy_types=list(self.TRIGGER_POLICY_MAP.get(trigger_type, [])),
        )

    def process_location_update(
        self,
        *,
        user_id: str,
        lat: float,
        lng: float,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_user_id = str(user_id or "system").strip() or "system"
        normalized_timestamp = self._normalize_timestamp(timestamp)
        previous_location = self._read_previous_location(normalized_user_id, normalized_timestamp)

        try:
            upsert_location_snapshot(
                user_id=normalized_user_id,
                lat=float(lat),
                lng=float(lng),
                timestamp=normalized_timestamp.isoformat(),
            )
        except Exception:
            # Monitoring should continue even if snapshot persistence fails.
            pass

        location = {
            "lat": float(lat),
            "lng": float(lng),
        }

        weather_result = self.fetch_weather(float(lat), float(lng))
        traffic_result = self.fetch_traffic(
            user_id=normalized_user_id,
            lat=float(lat),
            lng=float(lng),
            timestamp=normalized_timestamp,
        )

        candidate_types: List[str] = []
        if weather_result.get("trigger_type"):
            candidate_types.append(str(weather_result["trigger_type"]))
        if traffic_result.get("trigger_type"):
            candidate_types.append(str(traffic_result["trigger_type"]))

        stored_triggers: List[Dict[str, Any]] = []
        for trigger_type in candidate_types:
            if has_recent_similar_trigger(
                user_id=normalized_user_id,
                trigger_type=trigger_type,
                location=location,
                timestamp=normalized_timestamp.isoformat(),
                max_distance_meters=self.duplicate_radius_meters,
                max_time_window_seconds=self.duplicate_window_seconds,
            ):
                continue

            stored = self._store_trigger(
                user_id=normalized_user_id,
                trigger_type=trigger_type,
                lat=float(lat),
                lng=float(lng),
                timestamp=normalized_timestamp,
                previous_location=previous_location,
            )
            stored_triggers.append(stored)

        self._remember_current_position(
            user_id=normalized_user_id,
            lat=float(lat),
            lng=float(lng),
            timestamp=normalized_timestamp,
        )

        return {
            "lat": float(lat),
            "lng": float(lng),
            "timestamp": normalized_timestamp.isoformat(),
            "weather": weather_result,
            "traffic": traffic_result,
            "trigger_count": len(stored_triggers),
            "stored_triggers": stored_triggers,
        }

    def _runtime_locations(self) -> List[Dict[str, Any]]:
        if self.monitored_locations:
            return [
                {
                    "user_id": "system",
                    "lat": float(location["lat"]),
                    "lng": float(location["lng"]),
                }
                for location in self.monitored_locations
            ]

        try:
            return list_recent_location_snapshots(
                max_age_seconds=self.location_snapshot_max_age_seconds,
            )
        except Exception:
            return []

    def run_once(self) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for location in self._runtime_locations():
            try:
                result = self.process_location_update(
                    user_id=str(location.get("user_id") or "system"),
                    lat=float(location["lat"]),
                    lng=float(location["lng"]),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                if result.get("trigger_count", 0) > 0:
                    results.append(result)
            except Exception:
                continue

        return results

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.run_once()
            self._stop_event.wait(self.interval_seconds)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = Thread(target=self._run_loop, name="trigger-generator", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)
