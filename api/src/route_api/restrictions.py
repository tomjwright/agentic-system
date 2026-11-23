"""Roads a route must not run along, from a committed OpenStreetMap extract.

restricted_ways.geojson.gz holds Singapore's expressways, slip roads, trunk roads, road
tunnels and bicycle=no ways (feasibility/scripts/extract_restricted_ways.py; refresh it
as api/README.md says). The geometry check is the feasibility one
(route_feasibility.restrictions): `on_m` is route length along the road itself, `near_m`
includes crossings, bridges and paths beside it. A cycling loop is rejected when it runs
along a prohibited road; trunk roads are legal for bicycles, so they are only disclosed.
A way missing from the extract is not proof that access is allowed.
"""

import gzip
import json
from pathlib import Path

from pydantic import BaseModel
from route_feasibility.restrictions import RestrictedWay, inspect_route
from route_feasibility.restrictions import load_restricted_ways as read_ways

from route_api.contracts import RestrictedRoad

EXTRACT = Path(__file__).parent / "restricted_ways.geojson.gz"
PROHIBITED_KINDS = {"expressway", "expressway slip road", "road tunnel", "bicycle=no"}


class RestrictedWays(BaseModel):
    source: str
    ways: list[RestrictedWay]


def load_restricted_ways(path: Path = EXTRACT) -> RestrictedWays:
    with gzip.open(path, "rt", encoding="utf-8") as file:
        geojson = json.load(file)
    source = geojson["source"]
    return RestrictedWays(
        source=f"OpenStreetMap extract {source['extract']} of {source['osm_timestamp']}"
        f" ({source['licence']})",
        ways=read_ways(geojson),
    )


def check_route(
    coordinates: list[tuple[float, float]], step_names: list[str], ways: RestrictedWays
) -> list[RestrictedRoad]:
    """Each restricted road the route comes near, and whether it runs along a prohibited one."""
    points = [[lon, lat] for lon, lat in coordinates]
    roads = []
    for contact in inspect_route(points, ways.ways, step_names):
        outcome = "crossing_or_beside"
        if contact.on_m > 0 and contact.kind in PROHIBITED_KINDS:
            outcome = "on_prohibited_road"
        elif contact.on_m > 0:
            outcome = "on_disclosed_road"
        roads.append(
            RestrictedRoad(
                kind=contact.kind,  # type: ignore[arg-type]
                name=contact.name,
                osm_way_ids=contact.osm_way_ids,
                near_m=round(contact.near_m, 1),
                on_m=round(contact.on_m, 1),
                outcome=outcome,  # type: ignore[arg-type]
            )
        )
    return roads
