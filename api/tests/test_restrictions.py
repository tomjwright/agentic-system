"""The restriction check against the committed OpenStreetMap extract, on hand-made routes.

Coordinates are real OSM node positions near Avenue South Residence, as HeiGIT returns them.
"""

import pytest

from route_api.restrictions import RestrictedWays, check_route, load_restricted_ways

# Central Expressway (CTE), OSM way 45071007: its first four nodes.
CTE = [
    (103.8288172, 1.2786635),
    (103.8286473, 1.2784041),
    (103.8284843, 1.278192),
    (103.8283047, 1.2779908),
]
# Keppel Road (trunk), OSM way 33913122: its first four nodes.
KEPPEL_ROAD = [
    (103.8318517, 1.2722577),
    (103.8320032, 1.272391),
    (103.8321507, 1.2725055),
    (103.832255, 1.2725698),
]
# Sime Underpass (tertiary, tunnel=yes), OSM way 654642353: its first four nodes.
SIME_UNDERPASS = [
    (103.818641, 1.3354437),
    (103.8186729, 1.3353402),
    (103.8187247, 1.3352338),
    (103.8188163, 1.3351153),
]
# A car park ramp (service, tunnel=yes), OSM way 146981349: its first three nodes.
CAR_PARK_RAMP = [(103.7671863, 1.2941617), (103.7672108, 1.2941463), (103.7672425, 1.2941524)]
# A straight line over the CTE between its first two nodes, about 30 m either side.
OVER_CTE = [(103.8284650, 1.2786540), (103.8289995, 1.2784136)]


@pytest.fixture(scope="module")
def ways() -> RestrictedWays:
    return load_restricted_ways()


def test_the_extract_says_where_it_came_from(ways: RestrictedWays) -> None:
    assert "OpenStreetMap" in ways.source
    assert "2026-11-21" in ways.source
    assert len(ways.ways) > 10_000


def test_riding_along_an_expressway_is_a_prohibited_stretch(ways: RestrictedWays) -> None:
    roads = check_route(CTE, ["Central Expressway"] * len(CTE), ways)

    [road] = roads
    assert road.kind == "expressway"
    assert road.name == "Central Expressway"
    assert road.outcome == "on_prohibited_road"
    assert road.on_m > 50
    assert 45071007 in road.osm_way_ids


def test_crossing_over_an_expressway_is_permitted(ways: RestrictedWays) -> None:
    roads = check_route(OVER_CTE, ["Bridge"] * len(OVER_CTE), ways)

    [road] = roads
    assert road.kind == "expressway"
    assert road.outcome == "crossing_or_beside"
    assert road.near_m > 0
    assert road.on_m == 0


def test_riding_along_a_trunk_road_is_legal_but_disclosed(ways: RestrictedWays) -> None:
    roads = check_route(KEPPEL_ROAD, ["Keppel Road"] * len(KEPPEL_ROAD), ways)

    [road] = roads
    assert road.kind == "major arterial (trunk)"
    assert road.name == "Keppel Road"
    assert road.outcome == "on_disclosed_road"
    assert road.on_m > 0


def test_a_route_away_from_restricted_roads_touches_none(ways: RestrictedWays) -> None:
    # Two points inside Avenue South Residence's grounds.
    route = [(103.8291052, 1.2766295), (103.8293, 1.2768)]

    assert check_route(route, ["", ""], ways) == []


def test_riding_through_a_minor_road_tunnel_is_legal_but_disclosed(ways: RestrictedWays) -> None:
    roads = check_route(SIME_UNDERPASS, ["Sime Underpass"] * len(SIME_UNDERPASS), ways)

    [road] = roads
    assert road.kind == "minor road tunnel"
    assert road.outcome == "on_disclosed_road"
    assert 654642353 in road.osm_way_ids


def test_a_car_park_ramp_is_not_a_road_tunnel(ways: RestrictedWays) -> None:
    assert check_route(CAR_PARK_RAMP, ["", "", ""], ways) == []
