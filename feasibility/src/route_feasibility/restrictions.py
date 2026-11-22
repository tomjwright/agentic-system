"""Where a route touches roads a cyclist or runner may not use, from OpenStreetMap tags.

The input is restricted_ways.geojson, made by scripts/extract_restricted_ways.py from a
Singapore OSM extract. Each road the route comes near is reported with how much of
the route is near it (a crossing, a bridge over, a path beside it) and how much runs
on it (routing along it).
"""

import itertools
from typing import Any

from pydantic import BaseModel

from route_feasibility.geo import LineIndex, distance_m, sample_route

MATCH_DISTANCE_M = 8.0
SAMPLE_SPACING_M = 10.0
ON_WAY_M = 1.5


class RestrictedWay(BaseModel):
    osm_way_id: int
    kind: str
    name: str
    line: list[list[float]]


class RestrictionContact(BaseModel):
    """Everything one route does near one restricted road (grouped by kind and name)."""

    kind: str
    name: str
    contacts: int
    near_m: float
    on_m: float
    osm_way_ids: list[int]
    route_step_names: list[str]


def restriction_kind(tags: dict[str, Any]) -> str | None:
    """The reason a way matters, or None. Singapore bans cycling and walking on expressways."""
    highway = tags.get("highway")
    if highway == "motorway":
        return "expressway"
    if highway == "motorway_link":
        return "expressway slip road"
    if tags.get("bicycle") == "no":
        return "bicycle=no"
    if tags.get("tunnel") == "yes" and highway in ("trunk", "trunk_link", "primary", "secondary"):
        return "road tunnel"
    if highway in ("trunk", "trunk_link"):
        return "major arterial (trunk)"
    return None


def load_restricted_ways(geojson: dict[str, Any]) -> list[RestrictedWay]:
    ways = []
    for feature in geojson["features"]:
        tags = feature["properties"]
        kind = restriction_kind(tags)
        if kind is None:
            continue
        name = tags.get("name") or tags.get("ref") or "unnamed"
        ways.append(
            RestrictedWay(
                osm_way_id=tags["osm_way_id"],
                kind=kind,
                name=name,
                line=feature["geometry"]["coordinates"],
            )
        )
    return ways


def contact_for(
    found: dict[tuple[str, str], RestrictionContact], way: RestrictedWay, step_name: str
) -> RestrictionContact:
    key = (way.kind, way.name)
    if key not in found:
        found[key] = RestrictionContact(
            kind=way.kind, name=way.name, contacts=0, near_m=0.0, on_m=0.0,
            osm_way_ids=[], route_step_names=[],
        )  # fmt: skip
    contact = found[key]
    if way.osm_way_id not in contact.osm_way_ids:
        contact.osm_way_ids.append(way.osm_way_id)
    if step_name not in contact.route_step_names:
        contact.route_step_names.append(step_name)
    return contact


def inspect_route(
    coordinates: list[list[float]], ways: list[RestrictedWay], step_names: list[str]
) -> list[RestrictionContact]:
    """How close the route comes to restricted roads, and how far it runs on them.

    near_m: route length within MATCH_DISTANCE_M of the road (parallel paths, crossings).
    on_m: route edges whose ends and middle all lie within ON_WAY_M of the road. HeiGIT
    returns OSM node positions, so an edge on the road itself sits on it; a crossing
    or a path beside it does not. step_names[i] is the HeiGIT step name at vertex i.
    """
    index: LineIndex[RestrictedWay] = LineIndex()
    for each_way in ways:
        index.add_line(each_way, each_way.line)

    found: dict[tuple[str, str], RestrictionContact] = {}

    previous_point = coordinates[0]
    previous_key: tuple[str, str] | None = None
    for point, vertex in sample_route(coordinates, SAMPLE_SPACING_M):
        way = index.nearest(point, MATCH_DISTANCE_M)
        step_m = distance_m(previous_point, point)
        previous_point = point
        if way is None:
            previous_key = None
            continue
        contact = contact_for(found, way, step_names[vertex])
        if (way.kind, way.name) != previous_key:
            contact.contacts += 1
        contact.near_m += step_m
        previous_key = (way.kind, way.name)

    for vertex, (a, b) in enumerate(itertools.pairwise(coordinates)):
        middle = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
        way = index.nearest(middle, ON_WAY_M)
        if way is None:
            continue
        way_at_a = index.nearest(a, ON_WAY_M)
        way_at_b = index.nearest(b, ON_WAY_M)
        if way_at_a is None or way_at_b is None:
            continue
        if way_at_a.kind != way.kind or way_at_b.kind != way.kind:
            continue
        contact_for(found, way, step_names[vertex]).on_m += distance_m(a, b)

    return list(found.values())
