"""Seam 1: generating, inspecting and exporting a road-cycling loop over HTTP.

HeiGIT is replaced by recorded real cycling-road responses from Avenue South Residence;
the database and the OpenStreetMap restriction extract are real.
"""

import json
import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine, text

from tests.recorded_heigit import FIXTURES, recorded_response
from tests.test_restrictions import CTE, OVER_CTE
from tests.test_runs import (
    AVENUE_SOUTH_BLOCK_11,
    GPX,
    SYNTHETIC_KEY,
    CountingHeigit,
    api_with_heigit,
    confirm_start,
    start_run,
)

OWNER = {"X-Owner-Id": "tom"}
TWENTY_KM = {"kind": "target", "target_km": 20}


def cycling_run(engine: Engine, handler: Any, distance: dict[str, Any]) -> dict[str, Any]:
    api = api_with_heigit(engine, handler)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11, activity="road_cycling")
    response = start_run(api, request_id, distance)
    assert response.status_code == 201
    run: dict[str, Any] = response.json()
    return run


def selected_route(engine: Engine, run_id: str) -> dict[str, Any]:
    api = api_with_heigit(engine, recorded_response)
    route: dict[str, Any] = api.get(f"/api/runs/{run_id}/route", headers=OWNER).json()
    return route


@pytest.mark.parametrize(
    ("activity", "distance", "profile"),
    [
        ("running", {"kind": "target", "target_km": 5}, "foot-walking"),
        ("road_cycling", TWENTY_KM, "cycling-road"),
    ],
)
def test_each_activity_asks_heigit_for_its_own_profile(
    clean_engine: Engine, activity: str, distance: dict[str, Any], profile: str
) -> None:
    heigit = CountingHeigit()
    api = api_with_heigit(clean_engine, heigit)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11, activity=activity)

    run = start_run(api, request_id, distance).json()

    assert run["status"] == "succeeded"
    assert run["profile"] == profile
    for request in heigit.requests:
        assert request.url.path == f"/openrouteservice/v2/directions/{profile}/geojson"


def test_road_cycling_avoids_steps_and_ferries_but_not_roads(clean_engine: Engine) -> None:
    heigit = CountingHeigit()

    cycling_run(clean_engine, heigit, TWENTY_KM)

    for request in heigit.requests:
        options = json.loads(request.content)["options"]
        assert options["avoid_features"] == ["ferries", "steps"]


def test_a_20_km_ride_is_measured_and_checked_for_restricted_roads(clean_engine: Engine) -> None:
    run = cycling_run(clean_engine, recorded_response, TWENTY_KM)
    route = selected_route(clean_engine, run["id"])

    assert route["activity"] == "road_cycling"
    assert 18_000 <= route["distance_m"] <= 22_000
    assert route["access"]["status"] == "no_prohibited_road_found"
    assert "OpenStreetMap extract" in route["access"]["source"]
    for road in route["access"]["roads"]:
        assert road["outcome"] != "on_prohibited_road"
    assert any("unknown, not verified" in line for line in route["limitations"])


def test_crossing_an_expressway_is_permitted(clean_engine: Engine) -> None:
    run = cycling_run(clean_engine, recorded_response, TWENTY_KM)
    route = selected_route(clean_engine, run["id"])

    crossings = []
    for road in route["access"]["roads"]:
        if road["kind"] == "expressway" and road["outcome"] == "crossing_or_beside":
            crossings.append(road)
    assert crossings
    assert crossings[0]["on_m"] == 0


def test_trunk_roads_on_the_route_are_disclosed(clean_engine: Engine) -> None:
    run = cycling_run(clean_engine, recorded_response, TWENTY_KM)
    route = selected_route(clean_engine, run["id"])

    trunk = []
    for road in route["access"]["roads"]:
        if road["outcome"] == "on_disclosed_road":
            trunk.append(road["name"])
    assert trunk
    disclosure = [line for line in route["limitations"] if "trunk roads" in line]
    assert len(disclosure) == 1
    assert trunk[0] in disclosure[0]


def test_minor_road_tunnels_are_disclosed_apart_from_trunk_roads(clean_engine: Engine) -> None:
    run = cycling_run(
        clean_engine, recorded_response, {"kind": "range", "min_km": 60, "max_km": 70}
    )
    route = selected_route(clean_engine, run["id"])

    [trunk] = [line for line in route["limitations"] if "trunk roads" in line]
    [tunnels] = [line for line in route["limitations"] if "tunnels on minor roads" in line]
    assert "Bidadari Park Drive" in tunnels
    assert "Bidadari Park Drive" not in trunk


def test_retries_never_ask_heigit_for_a_round_trip_over_100_km(clean_engine: Engine) -> None:
    short_ride = (FIXTURES / "heigit_avenue_south_ride_20km_1.json").read_bytes()
    lengths = []

    def always_the_short_ride(request: httpx.Request) -> httpx.Response:
        round_trip = json.loads(request.content)["options"].get("round_trip")
        if round_trip is not None:
            lengths.append(round_trip["length"])
        return httpx.Response(200, content=short_ride)

    cycling_run(clean_engine, always_the_short_ride, {"kind": "target", "target_km": 100})

    assert lengths[0] == 100_000
    assert max(lengths) == 100_000


def test_a_capped_retry_that_overshoots_asks_for_less(clean_engine: Engine) -> None:
    short_ride = json.loads((FIXTURES / "heigit_avenue_south_ride_20km_1.json").read_text())
    long_ride = json.loads(json.dumps(short_ride))
    geometry = long_ride["features"][0]["geometry"]
    start = geometry["coordinates"][0]
    for point in geometry["coordinates"]:
        point[0] = start[0] + 6 * (point[0] - start[0])
        point[1] = start[1] + 6 * (point[1] - start[1])
    replies = [short_ride, long_ride, short_ride, short_ride, short_ride]
    lengths = []

    def short_then_long(request: httpx.Request) -> httpx.Response:
        round_trip = json.loads(request.content)["options"].get("round_trip")
        if round_trip is not None:
            lengths.append(round_trip["length"])
        return httpx.Response(200, json=replies[len(lengths) - 1])

    cycling_run(clean_engine, short_then_long, {"kind": "target", "target_km": 100})

    assert lengths[:2] == [100_000, 100_000]
    assert lengths[2] < 100_000


def test_unknown_surface_and_access_are_unknown_never_verified(clean_engine: Engine) -> None:
    run = cycling_run(clean_engine, recorded_response, TWENTY_KM)
    route = selected_route(clean_engine, run["id"])

    surfaces = [surface["surface"] for surface in route["surfaces"]]
    assert "unknown" in surfaces
    assert route["unknown_surface_share"] > 0
    assert any("no surface for" in line for line in route["limitations"])
    text_of_route = json.dumps(route).lower()
    assert "verified" not in text_of_route.replace("not verified", "")


def detour_along(
    coordinates: list[list[float]], detour: list[tuple[float, float]]
) -> list[list[float]]:
    """The loop with an out-and-back along `detour` inserted at its tenth point."""
    out = [[lon, lat] for lon, lat in detour]
    back = list(reversed(out))
    return coordinates[:10] + out + back + coordinates[10:]


def changing_every_route(detour: list[tuple[float, float]]) -> Any:
    """Recorded loops with the detour added; any request not recorded finds no route."""

    def handler(request: httpx.Request) -> httpx.Response:
        try:
            recorded = recorded_response(request)
        except LookupError:
            return httpx.Response(404, content=b'{"error": {"code": 2009}}')
        if recorded.status_code != 200:
            return recorded
        body = json.loads(recorded.content)
        geometry = body["features"][0]["geometry"]
        geometry["coordinates"] = detour_along(geometry["coordinates"], detour)
        return httpx.Response(200, json=body)

    return handler


# Real OSM node positions near Avenue South Residence (see tests/test_restrictions.py).
SLIP_ROAD = [(103.8295389, 1.2748356), (103.8296651, 1.2747716), (103.8302844, 1.2742756)]
SENTOSA_GATEWAY_TUNNEL = [
    (103.8251034, 1.2710664),
    (103.8250239, 1.2712587),
    (103.8248938, 1.27148),
]
# T3 Basement Drive (road tunnel), OSM way 622161254: three of its middle nodes.
T3_BASEMENT_DRIVE = [
    (103.9855389, 1.3543894),
    (103.9860309, 1.3556967),
    (103.9866814, 1.3571691),
]


@pytest.mark.parametrize(
    ("detour", "reason"),
    [
        (CTE, "along expressway Central Expressway"),
        (SLIP_ROAD, "along expressway slip road"),
        (T3_BASEMENT_DRIVE, "along road tunnel T3 Basement Drive"),
        (SENTOSA_GATEWAY_TUNNEL, "along bicycle=no Sentosa Gateway Tunnel"),
    ],
)
def test_loops_along_prohibited_roads_are_rejected(
    clean_engine: Engine, detour: list[tuple[float, float]], reason: str
) -> None:
    run = cycling_run(clean_engine, changing_every_route(detour), TWENTY_KM)

    assert run["status"] == "no_route"
    returned = [candidate for candidate in run["candidates"] if candidate["measured_distance_m"]]
    assert returned
    for candidate in returned:
        assert not candidate["accepted"]
        assert any(reason in line for line in candidate["reasons"])


def test_a_detour_over_an_expressway_bridge_is_not_rejected_for_it(clean_engine: Engine) -> None:
    run = cycling_run(clean_engine, changing_every_route(OVER_CTE), TWENTY_KM)

    for candidate in run["candidates"]:
        for line in candidate["reasons"]:
            assert "expressway" not in line


def test_gpx_export_is_exactly_the_stored_cycling_path(clean_engine: Engine) -> None:
    api = api_with_heigit(clean_engine, recorded_response)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11, activity="road_cycling")
    run_id = start_run(api, request_id, TWENTY_KM).json()["id"]

    route = api.get(f"/api/runs/{run_id}/route", headers=OWNER).json()
    gpx = api.get(f"/api/runs/{run_id}/route.gpx", headers=OWNER)

    assert gpx.status_code == 200
    assert f'filename="road-cycling-loop-{run_id}.gpx"' in gpx.headers["content-disposition"]
    root = ET.fromstring(gpx.content)  # noqa: S314 - our own output
    assert root.findtext(f"{GPX}trk/{GPX}name", "").startswith("Road cycling loop")
    points = []
    for point in root.iter(f"{GPX}trkpt"):
        points.append([float(point.attrib["lon"]), float(point.attrib["lat"])])
    assert points == route["geometry"]["coordinates"]


@pytest.mark.parametrize(
    "distance",
    [{"kind": "target", "target_km": 3}, {"kind": "range", "min_km": 60, "max_km": 101}],
)
def test_ride_distances_outside_5_to_100_km_are_refused(
    clean_engine: Engine, distance: dict[str, Any]
) -> None:
    api = api_with_heigit(clean_engine, recorded_response)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11, activity="road_cycling")

    response = start_run(api, request_id, distance)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_runs_stay_limited_to_50_km(clean_engine: Engine) -> None:
    api = api_with_heigit(clean_engine, recorded_response)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    response = start_run(api, request_id, {"kind": "target", "target_km": 60})

    assert response.status_code == 422
    assert "running loops are 1 to 50 km" in response.json()["error"]["message"]


@pytest.mark.parametrize(
    ("distance", "low_m", "high_m"),
    [
        ({"kind": "target", "target_km": 50}, 45_000, 55_000),
        ({"kind": "range", "min_km": 60, "max_km": 70}, 60_000, 70_000),
    ],
)
def test_long_rides_from_avenue_south_are_generated(
    clean_engine: Engine, distance: dict[str, Any], low_m: int, high_m: int
) -> None:
    run = cycling_run(clean_engine, recorded_response, distance)
    route = selected_route(clean_engine, run["id"])

    assert run["status"] == "succeeded"
    assert low_m <= route["distance_m"] <= high_m
    assert route["access"]["status"] == "no_prohibited_road_found"


def test_the_key_stays_out_of_cycling_responses_logs_and_the_database(
    clean_engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    api = api_with_heigit(clean_engine, recorded_response)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11, activity="road_cycling")
    run = start_run(api, request_id, TWENTY_KM)
    run_id = run.json()["id"]
    route = api.get(f"/api/runs/{run_id}/route", headers=OWNER)
    gpx = api.get(f"/api/runs/{run_id}/route.gpx", headers=OWNER)

    for response in (run, route, gpx):
        assert SYNTHETIC_KEY not in response.text
        assert SYNTHETIC_KEY not in str(response.headers)
    assert SYNTHETIC_KEY not in caplog.text
    assert "103.829" not in caplog.text
    finished = []
    for record in caplog.records:
        if record.name == "route_api" and '"generation_finished"' in record.getMessage():
            finished.append(json.loads(record.getMessage()))
    assert finished[0]["activity"] == "road_cycling"
    assert finished[0]["profile"] == "cycling-road"
    with clean_engine.connect() as connection:
        for table in ("generation_runs", "route_candidates"):
            rows = connection.execute(text(f"SELECT * FROM {table}")).all()  # noqa: S608
            assert SYNTHETIC_KEY not in str(rows)
