"""Seam 2: candidate selection, on recorded real HeiGIT foot-walking loops from Avenue South."""

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from route_api.contracts import Distance, DistanceRange, DistanceTarget
from route_api.heigit import ProviderRoute
from route_api.route_selection import Attempt, distance_bounds, select_route
from tests.recorded_heigit import FIXTURES

AVENUE_SOUTH_BLOCK_11 = (103.8291052120283, 1.276629534107344)


def recorded_route(seed: int) -> ProviderRoute:
    """The 5 km round trips HeiGIT returned for seeds 1 (6.50 km) and 2 (5.53 km)."""
    body = json.loads((FIXTURES / f"heigit_foot_round_trip_5km_seed{seed}.json").read_text())
    feature = body["features"][0]
    coordinates = []
    for lon, lat in feature["geometry"]["coordinates"]:
        coordinates.append((lon, lat))
    return ProviderRoute(
        coordinates=coordinates,
        distance_m=feature["properties"]["summary"]["distance"],
        duration_s=feature["properties"]["summary"]["duration"],
        surfaces_m={"unknown": 1000.0},
        engine={},
        attribution="openrouteservice.org | OpenStreetMap contributors",
    )


def attempts(*routes: ProviderRoute) -> list[Attempt]:
    found = []
    for route in routes:
        found.append(Attempt(route=route))
    return found


def test_single_target_accepts_ten_percent_either_side() -> None:
    bounds = distance_bounds(DistanceTarget(kind="target", target_km=6))

    selection = select_route(AVENUE_SOUTH_BLOCK_11, bounds, attempts(recorded_route(1)))

    assert (bounds.min_m, bounds.max_m) == (5400, 6600)
    assert selection.chosen == 0
    assert selection.reasons == [[]]


def test_the_acceptable_loop_nearest_the_target_is_chosen() -> None:
    bounds = distance_bounds(DistanceTarget(kind="target", target_km=6))

    # 6.50 km is 496 m over the target, 5.52 km is 475 m under it.
    selection = select_route(
        AVENUE_SOUTH_BLOCK_11, bounds, attempts(recorded_route(1), recorded_route(2))
    )

    assert selection.chosen == 1


def test_explicit_range_gets_no_added_tolerance() -> None:
    bounds = distance_bounds(DistanceRange(kind="range", min_km=6.5, max_km=7))

    selection = select_route(AVENUE_SOUTH_BLOCK_11, bounds, attempts(recorded_route(1)))

    assert (bounds.min_m, bounds.max_m) == (6500, 7000)
    assert selection.chosen is None
    assert selection.reasons == [["6.496 km is outside 6.500-7.000 km"]]


def test_exhaustion_reports_every_rejection_reason() -> None:
    bounds = distance_bounds(DistanceTarget(kind="target", target_km=5))
    no_route = Attempt(problem="HeiGIT found no route through its generated points")

    selection = select_route(
        AVENUE_SOUTH_BLOCK_11, bounds, [no_route, *attempts(recorded_route(1), recorded_route(2))]
    )

    assert selection.chosen is None
    assert selection.reasons == [
        ["HeiGIT found no route through its generated points"],
        ["6.496 km is outside 4.500-5.500 km"],
        ["5.525 km is outside 4.500-5.500 km"],
    ]


def test_a_loop_that_does_not_return_to_its_start_is_rejected() -> None:
    route = recorded_route(2)
    route.coordinates = route.coordinates[:-20]
    bounds = distance_bounds(DistanceRange(kind="range", min_km=4, max_km=6))

    selection = select_route(AVENUE_SOUTH_BLOCK_11, bounds, attempts(route))

    assert selection.chosen is None
    assert "does not close: it ends 417 m from where it starts" in selection.reasons[0]


def test_a_loop_leaving_singapore_is_rejected() -> None:
    route = recorded_route(2)
    # Shift the loop 1.5 km south, into the Singapore Strait off Sentosa.
    shifted = []
    for lon, lat in route.coordinates:
        shifted.append((lon, lat - 0.035))
    route.coordinates = shifted
    bounds = distance_bounds(DistanceRange(kind="range", min_km=4, max_km=6))

    selection = select_route((shifted[0][0], shifted[0][1]), bounds, attempts(route))

    assert selection.chosen is None
    assert any("outside Singapore" in reason for reason in selection.reasons[0])


def test_latitude_longitude_order_is_caught() -> None:
    route = recorded_route(2)
    swapped = []
    for lon, lat in route.coordinates:
        swapped.append((lat, lon))
    route.coordinates = swapped
    bounds = distance_bounds(DistanceRange(kind="range", min_km=4, max_km=6))

    selection = select_route(AVENUE_SOUTH_BLOCK_11, bounds, attempts(route))

    assert selection.chosen is None
    assert "201 of 201 points are outside Singapore" in selection.reasons[0]


def test_a_loop_snapped_far_from_the_confirmed_start_is_rejected() -> None:
    hort_park = (103.8005, 1.2795)
    bounds = distance_bounds(DistanceRange(kind="range", min_km=4, max_km=6))

    selection = select_route(hort_park, bounds, attempts(recorded_route(2)))

    assert selection.chosen is None
    assert "starts 3183 m from the confirmed start" in selection.reasons[0]


def test_a_distance_in_the_wrong_unit_is_rejected() -> None:
    route = recorded_route(2)
    route.distance_m = 5.5251  # kilometres, not metres
    bounds = distance_bounds(DistanceRange(kind="range", min_km=4, max_km=6))

    selection = select_route(AVENUE_SOUTH_BLOCK_11, bounds, attempts(route))

    assert selection.chosen is None
    assert "HeiGIT's distance (6 m) does not match the geometry (5525 m)" in selection.reasons[0]


@pytest.mark.parametrize(
    "distance",
    [
        {"kind": "target", "target_km": 0},
        {"kind": "target", "target_km": 101},
        {"kind": "range", "min_km": 8, "max_km": 6},
        {"kind": "range", "min_km": 5, "max_km": 5},
        {"kind": "range", "min_km": 0.5, "max_km": 5},
    ],
)
def test_unusable_distances_are_refused(distance: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(Distance).validate_python(distance)
