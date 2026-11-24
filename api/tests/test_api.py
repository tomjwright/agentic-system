"""Seam 1: the HTTP API, with OneMap replaced by recorded real responses and a real database."""

import json
import logging
from typing import Any

import httpx
import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import FAKE_TOKEN, SOMEONE, TOM, api_with, as_owner
from tests.recorded_onemap import recorded_response

AVENUE_SOUTH_BLOCK_11 = [103.8291052120283, 1.276629534107344]
JOHOR_BAHRU = [103.7578, 1.4655]
SINGAPORE_STRAIT = [103.85, 1.20]
HORT_PARK = [103.8005, 1.2795]


def search(api: TestClient, query: str) -> httpx2.Response:
    response: httpx2.Response = api.post("/api/places/search", json={"query": query})
    return response


def confirm_named(api: TestClient, query: str, source_id: str, owner: str = TOM) -> httpx2.Response:
    start = {"kind": "named", "query": query, "source_id": source_id}
    body = {"activity": "road_cycling", "start": start}
    response: httpx2.Response = api.post(
        "/api/route-requests", json=body, headers=as_owner(api, owner)
    )
    return response


def confirm_map(api: TestClient, coordinates: list[Any], owner: str = TOM) -> httpx2.Response:
    start = {"kind": "map", "point": {"type": "Point", "coordinates": coordinates}}
    body = {"activity": "running", "start": start}
    response: httpx2.Response = api.post(
        "/api/route-requests", json=body, headers=as_owner(api, owner)
    )
    return response


def test_named_search_lists_every_candidate_for_confirmation(api: TestClient) -> None:
    response = search(api, "avenue south residence")

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "multiple_matches"
    assert len(body["candidates"]) == 7
    first = body["candidates"][0]
    assert first["name"] == "AVENUE SOUTH RESIDENCE"
    assert first["address"] == "11 SILAT AVENUE AVENUE SOUTH RESIDENCE SINGAPORE 168877"
    assert first["point"] == {"type": "Point", "coordinates": AVENUE_SOUTH_BLOCK_11}
    assert first["source"] == "onemap"


def test_plural_name_shows_the_bedok_mismatch_instead_of_choosing(api: TestClient) -> None:
    body = search(api, "avenue south residences").json()

    assert body["outcome"] == "multiple_matches"
    assert {c["name"] for c in body["candidates"]} == {"GRANDEUR PARK RESIDENCES"}


def test_no_match_is_explicit(api: TestClient) -> None:
    body = search(api, "qzxv nowhere").json()

    assert body == {"outcome": "no_match", "candidates": [], "more_results": False}


def test_confirmed_named_start_keeps_activity_and_provenance(api: TestClient) -> None:
    candidate = search(api, "avenue south residence").json()["candidates"][0]

    created = confirm_named(api, "avenue south residence", candidate["source_id"])

    assert created.status_code == 201
    route_request = created.json()
    assert route_request["activity"] == "road_cycling"
    start = route_request["start"]
    assert start["name"] == "AVENUE SOUTH RESIDENCE"
    assert start["postal"] == "168877"
    assert start["point"]["coordinates"] == AVENUE_SOUTH_BLOCK_11
    assert start["source"] == "onemap"
    assert start["source_id"] == candidate["source_id"]
    assert start["query"] == "avenue south residence"
    fetched = api.get(f"/api/route-requests/{route_request['id']}", headers=as_owner(api, TOM))
    assert fetched.json() == route_request


def test_confirming_a_place_that_was_not_offered_is_refused(api: TestClient) -> None:
    response = confirm_named(api, "avenue south residence", "made-up-source-id")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "candidate_not_found"


def test_map_selected_start_is_confirmed_without_a_name(api: TestClient) -> None:
    created = confirm_map(api, HORT_PARK)

    assert created.status_code == 201
    start = created.json()["start"]
    assert start["source"] == "map_selection"
    assert start["name"] is None
    assert start["point"]["coordinates"] == HORT_PARK


@pytest.mark.parametrize("coordinates", [JOHOR_BAHRU, SINGAPORE_STRAIT])
def test_start_outside_singapore_land_is_refused(api: TestClient, coordinates: list[float]) -> None:
    response = confirm_map(api, coordinates)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "outside_singapore"


@pytest.mark.parametrize(
    "coordinates",
    [[1.276629534107344, 103.8291052120283], [103.8, 91.0], [103.8], ["east", "coast"]],
)
def test_invalid_coordinates_are_refused(api: TestClient, coordinates: list[Any]) -> None:
    response = confirm_map(api, coordinates)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_non_finite_coordinates_are_refused(api: TestClient) -> None:
    content = '{"activity": "running", "start": {"kind": "map", "point": '
    content += '{"type": "Point", "coordinates": [NaN, 1.3]}}}'
    response = api.post(
        "/api/route-requests", content=content, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_another_owner_cannot_see_a_start(api: TestClient) -> None:
    created = confirm_map(api, HORT_PARK, owner=TOM).json()

    as_tom = api.get(f"/api/route-requests/{created['id']}", headers=as_owner(api, TOM))
    as_other = api.get(f"/api/route-requests/{created['id']}", headers=as_owner(api, SOMEONE))

    assert as_tom.status_code == 200
    assert as_other.status_code == 404
    assert as_other.json()["error"]["code"] == "not_found"


def test_unknown_route_request_is_not_found(api: TestClient) -> None:
    response = api.get("/api/route-requests/6f1c2d34-0000-4000-8000-000000000000")

    assert response.status_code == 404


def test_provider_outage_is_a_redacted_error(
    clean_engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot reach host, header {FAKE_TOKEN}", request=request)

    api = api_with(clean_engine, httpx.MockTransport(handler), FAKE_TOKEN)
    caplog.set_level(logging.INFO)

    response = search(api, "avenue south residence")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_unavailable"
    assert FAKE_TOKEN not in response.text
    assert FAKE_TOKEN not in caplog.text
    provider_lines = []
    for record in caplog.records:
        if record.name != "route_api":
            continue  # the test client logs each request it makes
        line = json.loads(record.getMessage())
        if line["event"] == "provider_error":
            provider_lines.append(line)
    assert provider_lines == [
        {
            "event": "provider_error",
            "request_id": response.headers["X-Request-ID"],
            "provider": "onemap",
            "code": "provider_unavailable",
        }
    ]


def test_expired_token_is_reported_as_a_provider_rejection(clean_engine: Engine) -> None:
    expired = {"error": "Authentication token expired.", "found": 0, "results": []}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=expired)

    api = api_with(clean_engine, httpx.MockTransport(handler), FAKE_TOKEN)

    response = search(api, "avenue south residence")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_rejected"


def test_search_without_a_token_is_unavailable(clean_engine: Engine) -> None:
    api = api_with(clean_engine, httpx.MockTransport(recorded_response), None)

    response = search(api, "avenue south residence")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_not_configured"


def test_token_and_query_stay_out_of_responses_and_logs(
    api: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    response = search(api, "avenue south residence")
    candidate = response.json()["candidates"][0]
    confirm_named(api, "avenue south residence", candidate["source_id"])

    assert FAKE_TOKEN not in response.text
    assert FAKE_TOKEN not in str(response.headers)
    assert FAKE_TOKEN not in caplog.text
    assert "avenue south" not in caplog.text.lower()
    assert "avenue+south" not in caplog.text.lower()
    assert "103.829" not in caplog.text


def test_each_request_logs_one_json_line_with_its_request_id(
    api: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    response = api.post(
        "/api/places/search",
        json={"query": "avenue south residence"},
        headers={"X-Request-ID": "trace-123"},
    )

    assert response.headers["X-Request-ID"] == "trace-123"
    request_lines = []
    for record in caplog.records:
        if record.name != "route_api":
            continue  # the test client logs each request it makes
        line = json.loads(record.getMessage())
        if line["event"] == "request":
            request_lines.append(line)
    assert len(request_lines) == 1
    duration_ms = request_lines[0].pop("duration_ms")
    assert isinstance(duration_ms, int)
    assert request_lines[0] == {
        "event": "request",
        "request_id": "trace-123",
        "method": "POST",
        "path": "/api/places/search",
        "status": 200,
    }
