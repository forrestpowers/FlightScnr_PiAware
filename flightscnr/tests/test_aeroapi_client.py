"""Focused tests for the cost-aware FlightAware AeroAPI adapter."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utilities.aeroapi_client import AeroAPIClient


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def flight_record():
    return {
        "ident": "UAL123",
        "ident_icao": "UAL123",
        "ident_iata": "UA123",
        "atc_ident": "UAL123",
        "fa_flight_id": "UAL123-1234567890-airline-0001",
        "operator_icao": "UAL",
        "operator_iata": "UA",
        "registration": "N12345",
        "aircraft_type": "B738",
        "origin": {"code": "KSFO", "code_icao": "KSFO", "code_iata": "SFO"},
        "destination": {"code": "KORD", "code_icao": "KORD", "code_iata": "ORD"},
        "status": "En Route",
        "cancelled": False,
        "actual_off": "2026-07-14T12:00:00Z",
        "actual_on": None,
        "actual_in": None,
        "scheduled_off": "2026-07-14T11:55:00Z",
        "scheduled_on": "2026-07-14T16:00:00Z",
        "estimated_on": "2026-07-14T15:50:00Z",
        "route_distance": 1846,
        "progress_percent": 50,
    }


def position_payload():
    return {
        "latitude": 40.1,
        "longitude": -100.2,
        "altitude": 350,
        "groundspeed": 455,
        "heading": 87,
        "timestamp": "2026-07-14T14:00:00Z",
        "altitude_change": "-",
    }


def test_nearby_lookup_reuses_adsb_position_and_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("AEROAPI_KEY", raising=False)
    session = FakeSession([FakeResponse({"flights": [flight_record()]})])
    client = AeroAPIClient(
        "secret-key", session=session, data_dir=str(tmp_path), daily_budget_usd=1
    )
    entry = {
        "plane_latitude": 41.0,
        "plane_longitude": -99.0,
        "altitude": 33000,
        "ground_speed": 440,
        "heading": 90,
    }

    first = client.find_by_callsign("UAL123", position_entry=entry)
    second = client.find_by_callsign("UAL123", position_entry=entry)

    assert first is not None
    assert first.latitude == 41.0
    assert first.altitude == 33000
    assert first.origin_airport_iata == "SFO"
    assert first.destination_airport_iata == "ORD"
    assert second is not None
    assert len(session.calls) == 1
    assert session.calls[0][1]["headers"]["x-apikey"] == "secret-key"
    assert client.usage["estimated_cost_usd"] == 0.005


def test_global_lookup_fetches_current_position(tmp_path, monkeypatch):
    monkeypatch.delenv("AEROAPI_KEY", raising=False)
    session = FakeSession(
        [
            FakeResponse({"flights": [flight_record()]}),
            FakeResponse(position_payload()),
        ]
    )
    client = AeroAPIClient(
        "secret-key", session=session, data_dir=str(tmp_path), daily_budget_usd=1
    )

    flight = client.find_by_callsign("UAL123")

    assert flight is not None
    assert flight.latitude == 40.1
    assert flight.altitude == 35000
    assert flight.ground_speed == 455
    assert len(session.calls) == 2
    assert session.calls[1][0].endswith("/position")
    assert client.usage["estimated_cost_usd"] == 0.015


def test_global_tracking_reuses_nearby_flight_info(tmp_path, monkeypatch):
    monkeypatch.delenv("AEROAPI_KEY", raising=False)
    session = FakeSession(
        [
            FakeResponse({"flights": [flight_record()]}),
            FakeResponse(position_payload()),
        ]
    )
    client = AeroAPIClient(
        "secret-key", session=session, data_dir=str(tmp_path), daily_budget_usd=1
    )

    nearby = client.find_by_callsign(
        "UAL123",
        position_entry={"plane_latitude": 41, "plane_longitude": -99},
    )
    tracked = client.find_by_callsign("UAL123")

    assert nearby is not None
    assert tracked is not None
    assert tracked.latitude == 40.1
    assert len(session.calls) == 2
    assert client.usage["estimated_cost_usd"] == 0.015


def test_details_are_derived_without_an_extra_request(tmp_path, monkeypatch):
    monkeypatch.delenv("AEROAPI_KEY", raising=False)
    session = FakeSession([FakeResponse({"flights": [flight_record()]})])
    client = AeroAPIClient(
        "secret-key", session=session, data_dir=str(tmp_path), daily_budget_usd=1
    )
    flight = client.find_by_callsign(
        "UAL123",
        position_entry={
            "plane_latitude": 41,
            "plane_longitude": -99,
            "altitude": 33000,
            "ground_speed": 440,
            "heading": 90,
        },
    )

    details = client.get_flight_details(flight)

    assert details["aircraft"]["model"]["code"] == "B738"
    assert details["schedule_info"]["flight_number"] == "UA123"
    assert details["flight_plan"]["departure_icao"] == "KSFO"
    assert details["flight_progress"]["great_circle_distance"] > 2900
    assert len(session.calls) == 1


def test_daily_budget_blocks_higher_cost_route_search(tmp_path, monkeypatch):
    monkeypatch.delenv("AEROAPI_KEY", raising=False)
    session = FakeSession([])
    client = AeroAPIClient(
        "secret-key", session=session, data_dir=str(tmp_path), daily_budget_usd=0.049
    )

    assert client.find_by_route("KSFO", "KORD") == []
    assert session.calls == []
    assert client.usage["estimated_cost_usd"] == 0.0


def test_usage_ledger_persists_across_clients(tmp_path, monkeypatch):
    monkeypatch.delenv("AEROAPI_KEY", raising=False)
    first = AeroAPIClient(
        "secret-key",
        session=FakeSession([FakeResponse({"flights": [flight_record()]})]),
        data_dir=str(tmp_path),
        daily_budget_usd=1,
    )
    first.find_by_callsign(
        "UAL123",
        position_entry={"plane_latitude": 1, "plane_longitude": 2},
    )
    second = AeroAPIClient(
        "secret-key", session=FakeSession([]), data_dir=str(tmp_path), daily_budget_usd=1
    )

    assert second.usage["estimated_cost_usd"] == 0.005
    assert Path(tmp_path, "aeroapi_usage.json").exists()


def test_portal_budget_overrides_environment_without_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("AEROAPI_DAILY_BUDGET_USD", "0.15")
    client = AeroAPIClient("secret-key", session=FakeSession([]), data_dir=str(tmp_path))
    assert client.usage["daily_budget_usd"] == 0.15
    assert client.usage["budget_source"] == "environment"

    with open(tmp_path / "secrets.json", "w", encoding="utf-8") as fh:
        json.dump({"AEROAPI_DAILY_BUDGET_USD": 0.30}, fh)

    assert client.usage["daily_budget_usd"] == 0.30
    assert client.usage["budget_source"] == "web portal"


def test_portal_save_persists_budget_and_existing_settings(tmp_path, monkeypatch):
    import secrets_store

    path = tmp_path / "secrets.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"USE_AEROAPI": False, "UNRELATED_SETTING": "keep"}, fh)
    monkeypatch.setattr(secrets_store, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(secrets_store, "SECRETS_JSON_PATH", str(path))

    saved = secrets_store.save_secrets_from_portal(
        {"aeroapi_daily_budget_usd": 0.30}
    )

    assert saved["AEROAPI_DAILY_BUDGET_USD"] == 0.30
    assert saved["USE_AEROAPI"] is False
    assert saved["UNRELATED_SETTING"] == "keep"
