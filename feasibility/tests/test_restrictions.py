"""How far a route runs on each restricted road, on hand-made ways."""

import pytest

from route_feasibility.geo import distance_m
from route_feasibility.restrictions import (
    RestrictedWay,
    inspect_route,
    load_restricted_ways,
    restriction_kind,
)

P0 = [103.8002, 1.3001]
P1 = [103.8006, 1.3001]
P2 = [103.8010, 1.3001]
P3 = [103.8014, 1.3001]
P1_2M_NORTH = [103.8006, 1.300118]
NORTH_OF_P1 = [103.8006, 1.3005]


def test_a_one_edge_tunnel_between_trunk_roads_counts_as_ridden_on() -> None:
    # The tunnel is listed first, so on a tie at its shared ends the trunk roads are nearer.
    ways = [
        RestrictedWay(osm_way_id=1, kind="road tunnel", name="Tunnel", line=[P1, P2]),
        RestrictedWay(osm_way_id=2, kind="major arterial (trunk)", name="West", line=[P0, P1]),
        RestrictedWay(osm_way_id=3, kind="major arterial (trunk)", name="East", line=[P2, P3]),
    ]

    contacts = inspect_route([P0, P1, P2, P3], ways, ["West", "Tunnel", "East", "East"])

    on_m = {contact.name: contact.on_m for contact in contacts}
    assert on_m["Tunnel"] == pytest.approx(distance_m(P1, P2))
    assert on_m["West"] == pytest.approx(distance_m(P0, P1))
    assert on_m["East"] == pytest.approx(distance_m(P2, P3))


@pytest.mark.parametrize(
    ("tags", "kind"),
    [
        ({"highway": "motorway"}, "expressway"),
        ({"highway": "motorway_link"}, "expressway slip road"),
        ({"highway": "residential", "bicycle": "no"}, "bicycle=no"),
        ({"highway": "trunk", "tunnel": "yes"}, "road tunnel"),
        ({"highway": "trunk_link", "tunnel": "yes"}, "road tunnel"),
        ({"highway": "primary", "tunnel": "yes"}, "road tunnel"),
        ({"highway": "secondary", "tunnel": "yes"}, "road tunnel"),
        ({"highway": "trunk"}, "major arterial (trunk)"),
        ({"highway": "trunk_link"}, "major arterial (trunk)"),
        ({"highway": "primary"}, None),
        ({"highway": "residential", "tunnel": "yes"}, None),
        ({"highway": "cycleway"}, None),
    ],
)
def test_restriction_kind_names_why_a_way_matters(tags: dict[str, str], kind: str | None) -> None:
    assert restriction_kind(tags) == kind


def test_loading_keeps_restricted_ways_named_by_name_then_ref() -> None:
    def feature(osm_way_id: int, tags: dict[str, str]) -> dict[str, object]:
        return {
            "properties": {"osm_way_id": osm_way_id, **tags},
            "geometry": {"coordinates": [P0, P1]},
        }

    geojson = {
        "features": [
            feature(1, {"highway": "residential", "name": "Silat Avenue"}),
            feature(2, {"highway": "motorway", "name": "Ayer Rajah Expressway", "ref": "AYE"}),
            feature(3, {"highway": "trunk", "ref": "R1"}),
            feature(4, {"highway": "motorway_link"}),
        ]
    }

    ways = load_restricted_ways(geojson)

    assert [(way.osm_way_id, way.kind, way.name) for way in ways] == [
        (2, "expressway", "Ayer Rajah Expressway"),
        (3, "major arterial (trunk)", "R1"),
        (4, "expressway slip road", "unnamed"),
    ]


def test_a_road_split_into_two_ways_is_one_contact_listing_both() -> None:
    ways = [
        RestrictedWay(osm_way_id=1, kind="expressway", name="AYE", line=[P0, P1]),
        RestrictedWay(osm_way_id=2, kind="expressway", name="AYE", line=[P1, P3]),
    ]

    contacts = inspect_route([P0, P1, P2, P3], ways, ["AYE", "AYE", "AYE", "AYE"])

    assert len(contacts) == 1
    assert contacts[0].osm_way_ids == [1, 2]
    assert contacts[0].route_step_names == ["AYE"]
    assert contacts[0].contacts == 1
    assert contacts[0].near_m == pytest.approx(distance_m(P0, P3))
    assert contacts[0].on_m == pytest.approx(distance_m(P0, P3))


@pytest.mark.parametrize(
    ("next_road_kind", "on_m"), [("expressway", distance_m(P0, P1_2M_NORTH)), ("bicycle=no", 0.0)]
)
def test_an_edge_ending_on_the_next_road_of_the_same_kind_runs_on_the_road(
    next_road_kind: str, on_m: float
) -> None:
    # The edge ends 2 m off the first road's end, on the start of the next road.
    ways = [
        RestrictedWay(osm_way_id=1, kind="expressway", name="First", line=[P0, P1]),
        RestrictedWay(
            osm_way_id=2, kind=next_road_kind, name="Next", line=[P1_2M_NORTH, NORTH_OF_P1]
        ),
    ]

    contacts = inspect_route([P0, P1_2M_NORTH], ways, ["First", "Next"])

    on_first = {contact.name: contact.on_m for contact in contacts}["First"]
    assert on_first == pytest.approx(on_m)
