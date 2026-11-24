"""How far a route runs on each restricted road, on hand-made ways."""

import pytest

from route_feasibility.geo import distance_m
from route_feasibility.restrictions import RestrictedWay, inspect_route

P0 = [103.8002, 1.3001]
P1 = [103.8006, 1.3001]
P2 = [103.8010, 1.3001]
P3 = [103.8014, 1.3001]


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
