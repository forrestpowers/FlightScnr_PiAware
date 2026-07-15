"""Cost-aware synchronous client for FlightAware AeroAPI v4.

The radar's high-frequency positions still come from the configured ADS-B feed.
AeroAPI is used for route/schedule enrichment and explicitly tracked flights so
the paid API is not polled every two seconds.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote

import requests

from utilities.cache import TTLCache

logger = logging.getLogger(__name__)

API_BASE = "https://aeroapi.flightaware.com/aeroapi"

# Published per-result-set prices as of July 2026. Every collection request in
# this client is constrained to one page so these are also per-request ceilings.
IDENT_COST_USD = 0.005
POSITION_COST_USD = 0.010
ADVANCED_SEARCH_COST_USD = 0.050

DEFAULT_DAILY_BUDGET_USD = 0.15
MAX_DAILY_BUDGET_USD = 100.0
DEFAULT_INFO_TTL_S = 30 * 60
DEFAULT_POSITION_TTL_S = 30 * 60
DEFAULT_ROUTE_TTL_S = 5 * 60


class AeroAPIError(RuntimeError):
    """AeroAPI request or response error."""


class AeroAPIBudgetExceeded(AeroAPIError):
    """The configured local daily cost ceiling has been reached."""


def _epoch(value: Any) -> int:
    """Convert an AeroAPI ISO-8601 timestamp to Unix seconds."""
    if value in (None, ""):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())
    except (TypeError, ValueError, OverflowError):
        return 0


def _airport_code(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return str(
        value.get("code_iata")
        or value.get("code_icao")
        or value.get("code_lid")
        or value.get("code")
        or ""
    ).strip().upper()


def _position_from_entry(entry: dict) -> dict:
    """Translate an adsb_client display entry into AeroAPI position fields."""
    altitude = entry.get("altitude")
    try:
        altitude_hundreds = int(round(float(altitude or 0) / 100.0))
    except (TypeError, ValueError):
        altitude_hundreds = 0
    return {
        "latitude": entry.get("plane_latitude"),
        "longitude": entry.get("plane_longitude"),
        "altitude": altitude_hundreds,
        "groundspeed": entry.get("ground_speed") or 0,
        "heading": entry.get("heading") or 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "altitude_change": "-",
    }


@dataclass
class LiveFlight:
    """Flight object consumed by the existing display pipeline."""

    flight_id: str
    latitude: float
    longitude: float
    altitude: int
    ground_speed: int
    heading: int
    vertical_speed: int
    callsign: str
    registration: str
    origin_airport_iata: str
    destination_airport_iata: str
    airline_icao: str
    airline_iata: str
    aircraft_code: str
    on_ground: bool
    eta: int
    airline_name: str = ""
    number: str = ""
    origin_airport_latitude: float = 0.0
    origin_airport_longitude: float = 0.0
    destination_airport_latitude: float = 0.0
    destination_airport_longitude: float = 0.0
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    def set_flight_details(self, details: dict) -> None:
        if not details:
            return
        schedule = details.get("schedule_info", {}) or {}
        aircraft = details.get("aircraft_info", {}) or {}
        flight_info = details.get("flight_info", {}) or {}

        self.number = schedule.get("flight_number") or self.number or self.callsign
        self.airline_name = aircraft.get("registered_owners") or self.airline_name
        self.aircraft_code = aircraft.get("typecode") or self.aircraft_code
        if flight_info:
            self.latitude = float(flight_info.get("latitude", self.latitude) or self.latitude)
            self.longitude = float(flight_info.get("longitude", self.longitude) or self.longitude)
            self.altitude = int(flight_info.get("altitude", self.altitude) or 0)
            self.ground_speed = int(flight_info.get("ground_speed", self.ground_speed) or 0)
            self.heading = int(flight_info.get("heading", self.heading) or 0)
            self.vertical_speed = int(flight_info.get("vertical_speed", self.vertical_speed) or 0)


class _DailyBudget:
    """Cross-process, persistent estimated-cost ceiling for a Raspberry Pi."""

    def __init__(self, path: str, limit_usd: float):
        self.path = path
        self.lock_path = path + ".lock"
        self.limit_usd = max(0.0, float(limit_usd))
        self._thread_lock = threading.Lock()

    @staticmethod
    def _today() -> str:
        return datetime.now().astimezone().date().isoformat()

    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError, TypeError):
            data = {}
        today = self._today()
        if data.get("date") != today:
            return {"date": today, "estimated_cost_usd": 0.0, "requests": 0}
        return {
            "date": today,
            "estimated_cost_usd": float(data.get("estimated_cost_usd") or 0.0),
            "requests": int(data.get("requests") or 0),
        }

    def _write(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, self.path)

    def reserve(self, estimated_cost_usd: float) -> dict:
        try:
            import fcntl
        except ImportError:  # pragma: no cover - Raspberry Pi/Linux has fcntl
            fcntl = None

        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with self._thread_lock, open(self.lock_path, "a+", encoding="utf-8") as lock_fh:
            if fcntl is not None:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            try:
                data = self._load()
                proposed = data["estimated_cost_usd"] + float(estimated_cost_usd)
                if proposed > self.limit_usd + 1e-9:
                    raise AeroAPIBudgetExceeded(
                        f"AeroAPI daily budget reached "
                        f"(${data['estimated_cost_usd']:.3f}/${self.limit_usd:.3f})"
                    )
                data["estimated_cost_usd"] = round(proposed, 6)
                data["requests"] += 1
                self._write(data)
                return data
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

    def set_limit(self, limit_usd: float) -> None:
        with self._thread_lock:
            self.limit_usd = max(0.0, min(MAX_DAILY_BUDGET_USD, float(limit_usd)))

    def status(self) -> dict:
        with self._thread_lock:
            data = self._load()
        data["daily_budget_usd"] = self.limit_usd
        data["remaining_usd"] = round(
            max(0.0, self.limit_usd - data["estimated_cost_usd"]), 6
        )
        return data


class AeroAPIClient:
    """Small AeroAPI v4 client tailored to FlightScnr's display model."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        session: requests.Session | None = None,
        data_dir: str | None = None,
        daily_budget_usd: float | None = None,
    ):
        self._configured_key = (api_key or "").strip()
        self._session = session or requests.Session()
        self._ok = True
        self._info_cache = TTLCache(DEFAULT_INFO_TTL_S)
        self._position_cache = TTLCache(DEFAULT_POSITION_TTL_S)
        self._route_cache = TTLCache(DEFAULT_ROUTE_TTL_S)
        self._raw_by_id = TTLCache(6 * 60 * 60)

        root = data_dir or os.environ.get("FLIGHTSCNR_DATA_DIR", "/var/lib/flightscnr")
        self._data_dir = root
        self._budget_override = daily_budget_usd is not None
        self._budget_source = "constructor" if self._budget_override else "default"
        if daily_budget_usd is None:
            daily_budget_usd, self._budget_source = self._configured_budget()
        self._budget = _DailyBudget(
            os.path.join(root, "aeroapi_usage.json"), daily_budget_usd
        )

    @property
    def aeroapi_ok(self) -> bool:
        return self.configured and self._ok

    @property
    def configured(self) -> bool:
        return bool(self._api_key())

    @property
    def usage(self) -> dict:
        self._refresh_budget()
        status = self._budget.status()
        status["budget_source"] = self._budget_source
        return status

    @staticmethod
    def _valid_budget(value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if 0.0 <= parsed <= MAX_DAILY_BUDGET_USD:
            return parsed
        return None

    def _configured_budget(self) -> tuple[float, str]:
        # A portal selection intentionally overrides the install-time .env
        # default so Pi users can change plans without editing system files.
        try:
            with open(os.path.join(self._data_dir, "secrets.json"), encoding="utf-8") as fh:
                payload = json.load(fh)
            portal_value = self._valid_budget(
                payload.get("AEROAPI_DAILY_BUDGET_USD")
                if isinstance(payload, dict)
                else None
            )
            if portal_value is not None:
                return portal_value, "web portal"
        except (OSError, json.JSONDecodeError, TypeError):
            pass

        env_value = self._valid_budget(os.environ.get("AEROAPI_DAILY_BUDGET_USD"))
        if env_value is not None:
            return env_value, "environment"
        return DEFAULT_DAILY_BUDGET_USD, "default"

    def _refresh_budget(self) -> None:
        if self._budget_override:
            return
        limit, source = self._configured_budget()
        self._budget.set_limit(limit)
        self._budget_source = source

    def _api_key(self) -> str:
        try:
            from secrets_store import api_enabled

            if not api_enabled("AEROAPI_KEY"):
                return ""
        except Exception:
            pass
        return (os.environ.get("AEROAPI_KEY") or self._configured_key).strip()

    def _request(self, path: str, *, params: dict | None, cost_usd: float) -> dict:
        key = self._api_key()
        if not key:
            raise AeroAPIError("AEROAPI_KEY is not configured or AeroAPI is disabled")

        self._refresh_budget()
        self._budget.reserve(cost_usd)
        url = f"{API_BASE}/{path.lstrip('/')}"
        try:
            response = self._session.get(
                url,
                params=params or {},
                headers={
                    "x-apikey": key,
                    "Accept": "application/json; charset=UTF-8",
                    "User-Agent": "FlightScnrPi/1.0",
                },
                timeout=(5, 20),
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise AeroAPIError("AeroAPI returned an unexpected response")
            self._ok = True
            return data
        except AeroAPIError:
            self._ok = False
            raise
        except (requests.RequestException, ValueError) as exc:
            self._ok = False
            detail = ""
            response = getattr(exc, "response", None)
            if response is not None:
                try:
                    payload = response.json()
                    detail = payload.get("detail") or payload.get("title") or ""
                except (ValueError, AttributeError):
                    detail = ""
            message = f"AeroAPI request failed: {exc}"
            if detail:
                message = f"{message} ({detail})"
            raise AeroAPIError(message) from exc

    @staticmethod
    def _is_live(record: dict) -> bool:
        status = str(record.get("status") or "").lower()
        if record.get("cancelled") or record.get("actual_on") or record.get("actual_in"):
            return False
        if record.get("actual_off"):
            return True
        return any(word in status for word in ("en route", "active", "taxi", "departed"))

    @classmethod
    def _select_record(cls, records: list[dict], *, require_live: bool) -> dict | None:
        now = int(time.time())
        ranked: list[tuple[int, dict]] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            live = cls._is_live(record)
            if require_live and not live:
                continue
            score = 500 if live else 0
            if record.get("cancelled"):
                score -= 1000
            scheduled = _epoch(record.get("scheduled_off") or record.get("scheduled_out"))
            if scheduled:
                delta = scheduled - now
                if -86400 <= delta <= 7200:
                    score += 150
                elif 0 < delta <= 86400:
                    score += 50
                score -= min(abs(delta) // 3600, 100)
            estimated_on = _epoch(record.get("estimated_on") or record.get("estimated_in"))
            if estimated_on > now:
                score += 50
            ranked.append((score, record))
        return max(ranked, key=lambda item: item[0])[1] if ranked else None

    def _flight_record(self, ident: str, *, require_live: bool) -> dict | None:
        ident = ident.strip().upper()
        cache_key = f"{ident}:{int(require_live)}"
        cached = self._info_cache.get(cache_key)
        if cached is not None:
            return cached.get("record")

        # A nearby ADS-B enrichment and a global tracked-flight lookup may ask
        # for the same ident through different paths. Reuse the other path's
        # record when it satisfies the stricter live-flight requirement.
        alternate = self._info_cache.get(f"{ident}:{int(not require_live)}")
        if alternate is not None:
            record = alternate.get("record")
            if not require_live or (record and self._is_live(record)):
                self._info_cache.set(cache_key, {"record": record})
                return record

        data = self._request(
            f"flights/{quote(ident, safe='')}",
            params={"ident_type": "designator", "max_pages": 1},
            cost_usd=IDENT_COST_USD,
        )
        record = self._select_record(data.get("flights") or [], require_live=require_live)
        self._info_cache.set(cache_key, {"record": record})
        if record and record.get("fa_flight_id"):
            self._raw_by_id.set(record["fa_flight_id"], record)
        return record

    def _flight_position(self, flight_id: str) -> dict | None:
        cached = self._position_cache.get(flight_id)
        if cached is not None:
            return cached.get("position")
        data = self._request(
            f"flights/{quote(flight_id, safe='')}/position",
            params=None,
            cost_usd=POSITION_COST_USD,
        )
        position = data if data.get("latitude") is not None else None
        self._position_cache.set(flight_id, {"position": position})
        return position

    @staticmethod
    def _to_live_flight(record: dict, position: dict) -> LiveFlight | None:
        try:
            latitude = float(position.get("latitude"))
            longitude = float(position.get("longitude"))
        except (TypeError, ValueError):
            return None

        altitude = position.get("altitude")
        try:
            altitude_ft = int(round(float(altitude or 0) * 100))
        except (TypeError, ValueError):
            altitude_ft = 0
        try:
            speed = int(round(float(position.get("groundspeed") or 0)))
        except (TypeError, ValueError):
            speed = 0
        try:
            heading = int(round(float(position.get("heading") or 0)))
        except (TypeError, ValueError):
            heading = 0

        callsign = str(
            record.get("atc_ident")
            or record.get("ident_icao")
            or record.get("ident")
            or ""
        ).strip().upper()
        eta = _epoch(
            record.get("estimated_on")
            or record.get("estimated_in")
            or record.get("scheduled_on")
            or record.get("scheduled_in")
        )
        live = LiveFlight(
            flight_id=str(record.get("fa_flight_id") or ""),
            latitude=latitude,
            longitude=longitude,
            altitude=altitude_ft,
            ground_speed=speed,
            heading=heading,
            vertical_speed=0,
            callsign=callsign,
            registration=str(record.get("registration") or "").strip().upper(),
            origin_airport_iata=_airport_code(record.get("origin")),
            destination_airport_iata=_airport_code(record.get("destination")),
            airline_icao=str(record.get("operator_icao") or "").strip().upper(),
            airline_iata=str(record.get("operator_iata") or "").strip().upper(),
            aircraft_code=str(record.get("aircraft_type") or "").strip().upper(),
            on_ground=bool(record.get("actual_on") or record.get("actual_in")),
            eta=eta,
            number=str(record.get("ident_iata") or record.get("ident") or callsign),
            raw=record,
        )
        return live

    def find_by_callsign(
        self, callsign: str, *, position_entry: dict | None = None
    ) -> Optional[LiveFlight]:
        """Find a current flight; optionally use an already-known ADS-B position."""
        callsign = callsign.strip().upper()
        if not callsign:
            return None
        try:
            record = self._flight_record(callsign, require_live=position_entry is None)
            if not record:
                return None
            if position_entry is not None:
                position = _position_from_entry(position_entry)
            else:
                flight_id = str(record.get("fa_flight_id") or "")
                if not flight_id:
                    return None
                position = self._flight_position(flight_id)
            if not position:
                return None
            flight = self._to_live_flight(record, position)
            if flight:
                self._raw_by_id.set(flight.flight_id, record)
            return flight
        except AeroAPIBudgetExceeded as exc:
            logger.info("%s", exc)
            return None
        except AeroAPIError as exc:
            logger.warning("AeroAPI callsign lookup failed for %s: %s", callsign, exc)
            return None

    def find_by_route(self, origin: str, destination: str) -> list[LiveFlight]:
        """Explicit one-page route search (the higher-cost AeroAPI endpoint)."""
        origin = origin.strip().upper()
        destination = destination.strip().upper()
        if not origin or not destination:
            return []
        key = f"{origin}:{destination}"
        cached = self._route_cache.get(key)
        if cached is not None:
            return cached
        query = f"{{= orig {origin}}} {{= dest {destination}}} {{false arrived}}"
        try:
            data = self._request(
                "flights/search/advanced",
                params={"query": query, "max_pages": 1},
                cost_usd=ADVANCED_SEARCH_COST_USD,
            )
        except AeroAPIBudgetExceeded as exc:
            logger.info("%s", exc)
            return []
        except AeroAPIError as exc:
            logger.warning("AeroAPI route search failed: %s", exc)
            return []

        flights = []
        for record in data.get("flights") or []:
            position = record.get("last_position") or {}
            flight = self._to_live_flight(record, position)
            if flight:
                self._raw_by_id.set(flight.flight_id, record)
                flights.append(flight)
        self._route_cache.set(key, flights)
        return flights

    def get_flight_details(self, flight: LiveFlight) -> dict:
        """Return the old nested display contract without making another call."""
        record = flight.raw or self._raw_by_id.get(flight.flight_id) or {}
        if not record:
            return {}

        scheduled_departure = _epoch(record.get("scheduled_off") or record.get("scheduled_out"))
        scheduled_arrival = _epoch(record.get("scheduled_on") or record.get("scheduled_in"))
        actual_departure = _epoch(record.get("actual_off") or record.get("actual_out"))
        actual_arrival = _epoch(record.get("actual_on") or record.get("actual_in"))
        eta = _epoch(
            record.get("estimated_on")
            or record.get("estimated_in")
            or record.get("scheduled_on")
            or record.get("scheduled_in")
        )
        now = int(time.time())
        remaining_time = max(0, eta - now) if eta else 0

        try:
            total_km = float(record.get("route_distance") or 0) * 1.609344
        except (TypeError, ValueError):
            total_km = 0
        try:
            progress = min(100.0, max(0.0, float(record.get("progress_percent") or 0)))
        except (TypeError, ValueError):
            progress = 0
        traversed_km = total_km * progress / 100.0
        remaining_km = max(0.0, total_km - traversed_km)

        origin = record.get("origin") or {}
        destination = record.get("destination") or {}
        flight_number = str(
            record.get("ident_iata")
            or record.get("ident_icao")
            or record.get("ident")
            or flight.callsign
        )
        aircraft_type = str(record.get("aircraft_type") or flight.aircraft_code or "")

        return {
            "aircraft": {
                "model": {"code": aircraft_type},
                "registration": record.get("registration") or flight.registration,
            },
            "airline": {
                "name": "",
                "code": {"icao": record.get("operator_icao") or flight.airline_icao},
            },
            "airport": {"origin": origin or None, "destination": destination or None},
            "time": {
                "scheduled": {
                    "departure": scheduled_departure or None,
                    "arrival": scheduled_arrival or None,
                },
                "real": {"departure": actual_departure or None},
                "estimated": {"arrival": eta or None},
            },
            "trail": [],
            "owner": {"code": {"icao": record.get("operator_icao") or flight.airline_icao}},
            "schedule_info": {
                "flight_number": flight_number,
                "operated_by_id": 0,
                "painted_as_id": 0,
                "origin_id": 0,
                "destination_id": 0,
                "scheduled_departure": scheduled_departure or None,
                "scheduled_arrival": scheduled_arrival or None,
                "actual_departure": actual_departure or None,
                "actual_arrival": actual_arrival or None,
            },
            "aircraft_info": {
                "icao_address": "",
                "reg": record.get("registration") or flight.registration,
                "typecode": aircraft_type,
                "registered_owners": "",
            },
            "flight_progress": {
                "traversed_distance": traversed_km,
                "remaining_distance": remaining_km,
                "elapsed_time": 0,
                "remaining_time": remaining_time,
                "eta": eta,
                "great_circle_distance": total_km,
            },
            "flight_plan": {
                "departure_icao": origin.get("code_icao") or origin.get("code") or "",
                "destination_icao": destination.get("code_icao") or destination.get("code") or "",
            },
            "flight_info": {
                "latitude": flight.latitude,
                "longitude": flight.longitude,
                "altitude": flight.altitude,
                "ground_speed": flight.ground_speed,
                "heading": flight.heading,
                "vertical_speed": flight.vertical_speed,
                "callsign": flight.callsign,
            },
        }
