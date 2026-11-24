"""Seam 1: generating, inspecting and exporting a running loop over HTTP.

HeiGIT is replaced by recorded real foot-walking responses; the database is real.
"""

import json
import logging
import uuid
import xml.etree.ElementTree as ET
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import Engine, text

from tests.conftest import SOMEONE, TOM, api_with, as_owner
from tests.recorded_heigit import FIXTURES, recorded_response
from tests.recorded_onemap import recorded_response as recorded_onemap

AVENUE_SOUTH_BLOCK_11 = [103.8291052120283, 1.276629534107344]
PASIR_RIS_BEACH_PARK = [103.9471253158095, 1.380999388858507]
SYNTHETIC_KEY = "synthetic-heigit-key-3f9c1d"
GPX = "{http://www.topografix.com/GPX/1/1}"


def confirm_start(
    api: TestClient, point: list[float], owner: str = TOM, activity: str = "running"
) -> str:
    start = {"kind": "map", "point": {"type": "Point", "coordinates": point}}
    response = api.post(
        "/api/route-requests",
        json={"activity": activity, "start": start},
        headers=as_owner(api, owner),
    )
    assert response.status_code == 201
    request_id: str = response.json()["id"]
    return request_id


def start_run(
    api: TestClient,
    request_id: str,
    distance: dict[str, Any],
    owner: str = TOM,
    operation_id: str | None = None,
) -> httpx.Response:
    body = {"operation_id": operation_id or str(uuid.uuid4()), "distance": distance}
    response: httpx.Response = api.post(
        f"/api/route-requests/{request_id}/runs", json=body, headers=as_owner(api, owner)
    )
    return response


def recorded_coordinates(file: str) -> list[list[float]]:
    body = json.loads((FIXTURES / file).read_text())
    coordinates: list[list[float]] = body["features"][0]["geometry"]["coordinates"]
    return coordinates


class CountingHeigit:
    """Recorded responses, optionally changed, counting what reaches 'HeiGIT'."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return recorded_response(request)


def api_with_heigit(engine: Engine, handler: Any, key: str | None = SYNTHETIC_KEY) -> TestClient:
    return api_with(
        engine,
        httpx.MockTransport(recorded_onemap),
        "fake-onemap-token",
        heigit_handler=handler,
        heigit_key=key,
    )


def test_a_target_distance_run_selects_a_measured_loop(clean_engine: Engine) -> None:
    api = api_with_heigit(clean_engine, recorded_response)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    response = start_run(api, request_id, {"kind": "target", "target_km": 5})

    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert run["revision"] == 1
    assert run["bounds"] == {"min_m": 4500, "max_m": 5500}
    candidates = run["candidates"]
    assert [candidate["seed"] for candidate in candidates] == [1, 2]
    assert [candidate["requested_length_m"] for candidate in candidates] == [5000, 3849]
    assert candidates[0]["accepted"] is False
    assert candidates[0]["reasons"] == ["6.496 km is outside 4.500-5.500 km"]
    assert candidates[1]["accepted"] is True


def test_the_selected_route_keeps_heigit_metres_and_longitude_latitude_order(
    clean_engine: Engine,
) -> None:
    api = api_with_heigit(clean_engine, recorded_response)
    run = start_run(
        api, confirm_start(api, AVENUE_SOUTH_BLOCK_11), {"kind": "target", "target_km": 5}
    )

    response = api.get(f"/api/runs/{run.json()['id']}/route", headers=as_owner(api, TOM))

    assert response.status_code == 200
    route = response.json()
    recorded = json.loads((FIXTURES / "heigit_avenue_south_5km_1.json").read_text())
    assert route["geometry"]["type"] == "LineString"
    assert route["geometry"]["coordinates"] == recorded["features"][0]["geometry"]["coordinates"]
    assert route["geometry"]["coordinates"][0] == [103.829025, 1.276996]
    summary = recorded["features"][0]["properties"]["summary"]
    assert route["distance_m"] == pytest.approx(summary["distance"], abs=5)
    assert route["deviation_m"] == pytest.approx(route["distance_m"] - 5000)
    assert route["duration_s"] == summary["duration"]
    assert route["unknown_surface_share"] > 0
    assert any("foot-walking" in limitation for limitation in route["limitations"])
    assert any("surface is unknown" in limitation for limitation in route["limitations"])
    assert "OpenStreetMap" in route["attribution"]


def test_an_explicit_range_with_no_acceptable_loop_reports_exhaustion(clean_engine: Engine) -> None:
    api = api_with_heigit(clean_engine, recorded_response)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    response = start_run(api, request_id, {"kind": "range", "min_km": 5.0, "max_km": 5.05})

    run = response.json()
    assert run["status"] == "no_route"
    assert run["bounds"] == {"min_m": 5000, "max_m": 5050}
    reasons = [candidate["reasons"] for candidate in run["candidates"]]
    assert reasons == [
        ["6.496 km is outside 5.000-5.050 km"],
        ["5.255 km is outside 5.000-5.050 km"],
        ["4.007 km is outside 5.000-5.050 km"],
        ["4.662 km is outside 5.000-5.050 km"],
        ["5.073 km is outside 5.000-5.050 km"],
    ]
    route = api.get(f"/api/runs/{run['id']}/route", headers=as_owner(api, TOM))
    assert route.status_code == 409
    assert route.json()["error"]["code"] == "no_route_selected"


def test_a_coastal_start_falls_back_to_an_inland_via_loop(clean_engine: Engine) -> None:
    def round_trips_fail(request: httpx.Request) -> httpx.Response:
        if "round_trip" in json.loads(request.content)["options"]:
            return httpx.Response(500, content=b'{"error": {"code": 2099}}')
        return recorded_response(request)

    api = api_with_heigit(clean_engine, round_trips_fail)
    request_id = confirm_start(api, PASIR_RIS_BEACH_PARK)

    run = start_run(api, request_id, {"kind": "range", "min_km": 12, "max_km": 18}).json()

    assert run["status"] == "succeeded"
    methods = [candidate["method"] for candidate in run["candidates"]]
    assert methods == ["round_trip", "round_trip", "via_loop"]
    assert run["candidates"][0]["reasons"] == ["HeiGIT found no route for these points"]


def test_gpx_export_is_exactly_the_stored_path(clean_engine: Engine) -> None:
    api = api_with_heigit(clean_engine, recorded_response)
    run = start_run(
        api, confirm_start(api, AVENUE_SOUTH_BLOCK_11), {"kind": "target", "target_km": 5}
    )
    run_id = run.json()["id"]
    route = api.get(f"/api/runs/{run_id}/route", headers=as_owner(api, TOM)).json()

    response = api.get(f"/api/runs/{run_id}/route.gpx", headers=as_owner(api, TOM))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/gpx+xml")
    assert "attachment" in response.headers["content-disposition"]
    points = []
    for point in ET.fromstring(response.text).iter(f"{GPX}trkpt"):  # noqa: S314 (our own GPX)
        points.append([float(point.attrib["lon"]), float(point.attrib["lat"])])
    assert points == route["geometry"]["coordinates"]


def test_a_repeated_operation_resolves_to_the_same_run(clean_engine: Engine) -> None:
    heigit = CountingHeigit()
    api = api_with_heigit(clean_engine, heigit)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)
    operation_id = str(uuid.uuid4())
    distance = {"kind": "target", "target_km": 5}

    first = start_run(api, request_id, distance, operation_id=operation_id)
    again = start_run(api, request_id, distance, operation_id=operation_id)

    assert first.status_code == 201
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert len(heigit.requests) == 2


def test_reusing_an_operation_for_a_different_distance_is_refused(clean_engine: Engine) -> None:
    api = api_with_heigit(clean_engine, recorded_response)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)
    operation_id = str(uuid.uuid4())
    start_run(api, request_id, {"kind": "target", "target_km": 5}, operation_id=operation_id)

    response = start_run(
        api, request_id, {"kind": "range", "min_km": 5, "max_km": 5.05}, operation_id=operation_id
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "operation_conflict"


def test_each_run_gets_its_own_immutable_revision(clean_engine: Engine) -> None:
    api = api_with_heigit(clean_engine, recorded_response)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)
    first = start_run(api, request_id, {"kind": "target", "target_km": 5}).json()

    second = start_run(api, request_id, {"kind": "range", "min_km": 5, "max_km": 5.05}).json()

    assert (first["revision"], second["revision"]) == (1, 2)
    again = api.get(f"/api/runs/{first['id']}", headers=as_owner(api, TOM)).json()
    assert again["distance"] == {"kind": "target", "target_km": 5.0}
    assert again["status"] == "succeeded"


def drop_the_end(coordinates: list[list[float]]) -> list[list[float]]:
    return coordinates[:-20]


def start_elsewhere(coordinates: list[list[float]]) -> list[list[float]]:
    return coordinates[40:] + coordinates[1:41]


def shift_south(coordinates: list[list[float]]) -> list[list[float]]:
    shifted = []
    for lon, lat in coordinates:
        shifted.append([lon, lat - 0.06])
    return shifted


def latitude_first(coordinates: list[list[float]]) -> list[list[float]]:
    swapped = []
    for lon, lat in coordinates:
        swapped.append([lat, lon])
    return swapped


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (drop_the_end, "does not close: it ends 211 m from where it starts"),
        (start_elsewhere, "starts 700 m from the confirmed start"),
        (shift_south, "of 270 points are outside Singapore"),
        (latitude_first, "270 of 270 points are outside Singapore"),
    ],
)
def test_invalid_loops_are_rejected_not_repaired(
    clean_engine: Engine, change: Any, reason: str
) -> None:
    recorded = json.loads((FIXTURES / "heigit_foot_round_trip_5km_seed1.json").read_text())
    geometry = recorded["features"][0]["geometry"]
    geometry["coordinates"] = change(geometry["coordinates"])

    def changed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=recorded)

    api = api_with_heigit(clean_engine, changed)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    run = start_run(api, request_id, {"kind": "target", "target_km": 6}).json()

    assert run["status"] == "no_route"
    found = " | ".join(run["candidates"][0]["reasons"])
    assert reason in found


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b'{"type": "FeatureCollection", "features": [], "metadata": {}}',
        b'{"type": "FeatureCollection", "features": [{"geometry": {"type": "LineString",'
        b' "coordinates": [[103.8, NaN], [103.8, 1.3]]}, "properties": {"summary": {}}}],'
        b' "metadata": {}}',
        b'{"type": "FeatureCollection", "features": [{"geometry": {"type": "Point",'
        b' "coordinates": [103.8, 1.3]}, "properties": {"summary": {}}}], "metadata": {}}',
        b'{"type": "FeatureCollection", "features": [{"geometry": {"type": "LineString",'
        b' "coordinates": [[103.8, 1.3], [103.8, 1.31]]}, "properties": {"summary": {},'
        b' "extras": {"surface": {"summary": [{"value": NaN, "distance": 10}]}}}}],'
        b' "metadata": {}}',
    ],
    ids=["not-json", "no-route", "not-finite", "not-a-line", "surface-not-finite"],
)
def test_malformed_provider_data_is_refused(clean_engine: Engine, body: bytes) -> None:
    def malformed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    api = api_with_heigit(clean_engine, malformed)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    run = start_run(api, request_id, {"kind": "target", "target_km": 5}).json()

    assert run["status"] == "no_route"
    assert len(run["candidates"]) == 5
    for candidate in run["candidates"]:
        assert candidate["reasons"] == ["HeiGIT returned a route in an unexpected shape"]


def test_a_provider_timeout_fails_the_run_with_a_safe_error(clean_engine: Engine) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    api = api_with_heigit(clean_engine, timeout)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    run = start_run(api, request_id, {"kind": "target", "target_km": 5}).json()

    assert run["status"] == "failed"
    assert run["error"] == {
        "code": "provider_unavailable",
        "message": "HeiGIT did not answer in time",
    }


def test_an_exhausted_quota_fails_the_run_without_more_requests(clean_engine: Engine) -> None:
    requests = []

    def quota(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(429, json={"error": "Quota exceeded"})

    api = api_with_heigit(clean_engine, quota)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    run = start_run(api, request_id, {"kind": "target", "target_km": 5}).json()

    assert run["status"] == "failed"
    assert run["error"]["code"] == "provider_quota_exhausted"
    assert len(requests) == 1


def test_a_fatal_provider_error_keeps_earlier_rejection_reasons(clean_engine: Engine) -> None:
    responses = []

    def recorded_then_quota(request: httpx.Request) -> httpx.Response:
        responses.append(request)
        if len(responses) == 1:
            return recorded_response(request)
        return httpx.Response(429, json={"error": "Quota exceeded"})

    api = api_with_heigit(clean_engine, recorded_then_quota)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    run = start_run(api, request_id, {"kind": "target", "target_km": 5}).json()

    assert run["status"] == "failed"
    assert run["error"]["code"] == "provider_quota_exhausted"
    assert run["candidates"][0]["reasons"] == ["6.496 km is outside 4.500-5.500 km"]
    assert run["candidates"][1]["reasons"] != []


def test_generation_without_a_key_is_unavailable(clean_engine: Engine) -> None:
    api = api_with_heigit(clean_engine, recorded_response, key=None)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    response = start_run(api, request_id, {"kind": "target", "target_km": 5})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_not_configured"


@pytest.mark.parametrize(
    "distance",
    [
        {"kind": "target", "target_km": 0.2},
        {"kind": "target", "target_km": 51},
        {"kind": "range", "min_km": 6, "max_km": 5},
        {"kind": "range", "min_km": 5},
        {"kind": "target", "target_km": "Infinity"},
    ],
)
def test_unusable_distances_are_refused(clean_engine: Engine, distance: dict[str, Any]) -> None:
    api = api_with_heigit(clean_engine, recorded_response)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    response = start_run(api, request_id, distance)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_another_owner_cannot_generate_see_or_export_a_run(clean_engine: Engine) -> None:
    api = api_with_heigit(clean_engine, recorded_response)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11, owner=TOM)
    run_id = start_run(api, request_id, {"kind": "target", "target_km": 5}).json()["id"]

    generate = start_run(api, request_id, {"kind": "target", "target_km": 5}, owner=SOMEONE)
    status = api.get(f"/api/runs/{run_id}", headers=as_owner(api, SOMEONE))
    route = api.get(f"/api/runs/{run_id}/route", headers=as_owner(api, SOMEONE))
    gpx = api.get(f"/api/runs/{run_id}/route.gpx", headers=as_owner(api, SOMEONE))

    for response in (generate, status, route, gpx):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


def test_heigit_gets_the_key_at_its_fixed_url_only(clean_engine: Engine) -> None:
    heigit = CountingHeigit()
    api = api_with_heigit(clean_engine, heigit)

    start_run(api, confirm_start(api, AVENUE_SOUTH_BLOCK_11), {"kind": "target", "target_km": 5})

    for request in heigit.requests:
        assert str(request.url) == (
            "https://api.heigit.org/openrouteservice/v2/directions/foot-walking/geojson"
        )
        assert request.headers["Authorization"] == SYNTHETIC_KEY


def test_the_key_stays_out_of_responses_logs_exports_and_the_database(
    clean_engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    api = api_with_heigit(clean_engine, recorded_response)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)
    run = start_run(api, request_id, {"kind": "target", "target_km": 5})
    run_id = run.json()["id"]
    route = api.get(f"/api/runs/{run_id}/route", headers=as_owner(api, TOM))
    gpx = api.get(f"/api/runs/{run_id}/route.gpx", headers=as_owner(api, TOM))
    status = api.get(f"/api/runs/{run_id}", headers=as_owner(api, TOM))

    for response in (run, route, gpx, status):
        assert SYNTHETIC_KEY not in response.text
        assert SYNTHETIC_KEY not in str(response.headers)
    assert SYNTHETIC_KEY not in caplog.text
    assert "103.829" not in caplog.text
    with clean_engine.connect() as connection:
        for table in ("route_request_revisions", "generation_runs", "route_candidates"):
            rows = connection.execute(text(f"SELECT * FROM {table}")).all()  # noqa: S608
            assert SYNTHETIC_KEY not in str(rows)


def test_a_finished_run_logs_its_outcome_without_the_start(
    clean_engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    api = api_with_heigit(clean_engine, recorded_response)

    start_run(api, confirm_start(api, AVENUE_SOUTH_BLOCK_11), {"kind": "target", "target_km": 5})

    events = []
    for record in caplog.records:
        if record.name == "route_api":
            events.append(json.loads(record.getMessage()))
    finished = [event for event in events if event["event"] == "generation_finished"]
    assert len(finished) == 1
    assert finished[0]["status"] == "succeeded"
    assert finished[0]["attempts"] == 2
    assert "103.8" not in json.dumps(finished)


def generate_route_spans(monkeypatch: pytest.MonkeyPatch) -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr("route_api.main.tracer", provider.get_tracer("test"))
    return exporter


@pytest.mark.parametrize(
    ("status", "error_code"), [(200, "none"), (429, "provider_quota_exhausted")]
)
def test_the_generation_span_names_its_error_code_for_the_alert(
    clean_engine: Engine, monkeypatch: pytest.MonkeyPatch, status: int, error_code: str
) -> None:
    exporter = generate_route_spans(monkeypatch)

    def heigit(request: httpx.Request) -> httpx.Response:
        if status == 200:
            return recorded_response(request)
        return httpx.Response(status, json={"error": "Quota exceeded"})

    api = api_with_heigit(clean_engine, heigit)
    start_run(api, confirm_start(api, AVENUE_SOUTH_BLOCK_11), {"kind": "target", "target_km": 5})

    spans = [span for span in exporter.get_finished_spans() if span.name == "generate_route"]
    assert len(spans) == 1
    assert spans[0].attributes is not None
    assert spans[0].attributes["route.error_code"] == error_code


def test_generation_stops_starting_requests_once_its_time_budget_is_spent(
    clean_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Each clock reading is 46 s after the last, so the 45 s budget is spent after one try
    # and the run still answers inside Vercel's 120 s rewrite limit.
    readings = iter(range(0, 10_000, 46))

    def clock() -> int:
        return next(readings)

    monkeypatch.setattr("route_api.generation.time.monotonic", clock)
    heigit = CountingHeigit()
    api = api_with_heigit(clean_engine, heigit)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    run = start_run(api, request_id, {"kind": "range", "min_km": 5.0, "max_km": 5.05}).json()

    assert run["status"] == "no_route"
    assert len(run["candidates"]) == 1
    assert len(heigit.requests) == 1
