"""Command line for the feasibility experiment.

    feasibility fetch-data --data-dir data
    feasibility route --name core-ride --activity ride --start "avenue south residence" \\
        --distance 60-70 --round-trip --seeds 1,2,3 --require-green

Each route case writes <name>.md (the measured report), and when a candidate is
accepted, <name>.geojson and <name>.gpx with the same points.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from route_feasibility import datasets, heigit
from route_feasibility.checks import Boundary, parse_target, repeated_share, validate_loop
from route_feasibility.gpx import route_to_gpx
from route_feasibility.green import Track, find_green_sections, load_tracks
from route_feasibility.onemap import resolve_start
from route_feasibility.report import Attempt, build_report
from route_feasibility.restrictions import RestrictedWay, inspect_route, load_restricted_ways

MAX_ATTEMPTS = 6
PROHIBITED = {
    "run": {"expressway", "expressway slip road", "road tunnel"},
    "ride": {"expressway", "expressway slip road", "road tunnel", "bicycle=no"},
}
OSM_ATTRIBUTION = (
    "Route geometry © OpenStreetMap contributors (ODbL), routed by © openrouteservice by HeiGIT. "
    "Green evidence: NParks Tracks, Singapore Open Data Licence v1.0."
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="feasibility")
    commands = parser.add_subparsers(dest="command", required=True)

    fetch = commands.add_parser("fetch-data", help="download the public data.gov.sg datasets")
    fetch.add_argument("--data-dir", type=Path, default=Path("data"))

    route = commands.add_parser("route", help="generate and measure one loop case")
    route.add_argument("--name", required=True)
    route.add_argument("--activity", choices=["run", "ride"], required=True)
    route.add_argument("--start", required=True, help="OneMap search text for the start")
    route.add_argument("--confirm", help="the OneMap place name the user confirmed")
    route.add_argument("--distance", required=True, help="km, like 10 or 60-70")
    route.add_argument("--round-trip", action="store_true", help="HeiGIT round_trip candidates")
    route.add_argument("--seeds", default="1,2,3", help="round_trip seeds, in order")
    route.add_argument("--request-km", type=float, help="round_trip length to ask for")
    route.add_argument(
        "--via",
        action="append",
        default=[],
        help="one candidate loop through these points: 'lon,lat;lon,lat' (repeatable)",
    )
    route.add_argument("--require-green", action="store_true")
    route.add_argument("--data-dir", type=Path, default=Path("data"))
    route.add_argument("--out", type=Path, default=Path("evidence"))
    route.add_argument("--pause-seconds", type=float, default=2.0, help="between HeiGIT calls")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, transport: httpx.BaseTransport | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    with httpx.Client(transport=transport) as http:
        if args.command == "fetch-data":
            datasets.fetch_all(http, args.data_dir)
            return 0
        return run_case(args, http)


def candidates(args: argparse.Namespace, start: list[float], length_m: float) -> list[Any]:
    found: list[tuple[str, dict[str, Any]]] = []
    if args.round_trip:
        for seed_text in args.seeds.split(","):
            seed = int(seed_text)
            body = heigit.round_trip_body(args.activity, start, length_m, seed)
            found.append((f"seed {seed}", body))
    for via_text in args.via:
        via = []
        for pair in via_text.split(";"):
            lon, lat = pair.split(",")
            via.append([float(lon), float(lat)])
        found.append(
            (f"via {len(via)} points", heigit.waypoint_loop_body(args.activity, start, via))
        )
    return found[:MAX_ATTEMPTS]


def run_case(args: argparse.Namespace, http: httpx.Client) -> int:
    api_key = os.environ.get("HEIGIT_API_KEY")
    if not api_key:
        print("HEIGIT_API_KEY is not set", file=sys.stderr)
        return 2
    target = parse_target(args.distance)
    tracks = load_tracks(read_json(args.data_dir / "nparks_tracks.geojson"))
    boundary = Boundary(geometries(read_json(args.data_dir / "singapore_boundary.geojson")))
    restricted: list[RestrictedWay] | None = None
    restricted_path = args.data_dir / "restricted_ways.geojson"
    if restricted_path.exists():
        restricted = load_restricted_ways(read_json(restricted_path))

    args.out.mkdir(parents=True, exist_ok=True)
    report_path = args.out / f"{args.name}.md"
    start = resolve_start(http, args.start, args.confirm)
    if start.place is None:
        report_path.write_text(build_report(args.name, args.activity, start, target, [], None))
        print(f"{args.name}: start {start.status} ({start.reason})")
        return 3

    start_point = [start.place.lon, start.place.lat]
    length_m = (target.min_m + target.max_m) / 2
    if args.request_km is not None:
        length_m = args.request_km * 1000

    attempts: list[Attempt] = []
    selected: Attempt | None = None
    for number, (label, body) in enumerate(candidates(args, start_point, length_m), start=1):
        if number > 1:
            time.sleep(args.pause_seconds)
        attempt = measure(args, http, api_key, body, target, boundary, tracks, restricted)
        attempt.number = number
        attempt.candidate = label
        attempts.append(attempt)
        if attempt.route is not None:
            write_geojson(
                args.out / f"{args.name}.attempt-{number}.geojson",
                args.name,
                attempt.route.coordinates,
            )
        print(f"{args.name}: attempt {number} {label}: {attempt_summary(attempt)}")
        if attempt.accepted:
            selected = attempt
            break

    report_path.write_text(
        build_report(args.name, args.activity, start, target, attempts, selected)
    )
    if selected is None or selected.route is None:
        return 1
    write_route_files(args.out, args.name, selected.route.coordinates)
    return 0


def measure(
    args: argparse.Namespace,
    http: httpx.Client,
    api_key: str,
    body: dict[str, Any],
    target: Any,
    boundary: Boundary,
    tracks: list[Track],
    restricted: list[RestrictedWay] | None,
) -> Attempt:
    attempt = Attempt(
        number=0, candidate="", route=None, error=None, accepted=False, problems=[],
        green=[], restrictions=None, repeated_share=None,
    )  # fmt: skip
    try:
        route = heigit.directions(http, api_key, args.activity, body)
    except heigit.HeigitError as error:
        attempt.error = str(error)
        return attempt
    attempt.route = route
    if not target.accepts(route.distance_m):
        attempt.problems.append("outside target")
    attempt.problems += validate_loop(route.coordinates, boundary)
    attempt.repeated_share = repeated_share(route.coordinates)
    attempt.green = find_green_sections(route.coordinates, tracks)
    has_allowed_green = any(section.counts_as_green_cycling for section in attempt.green)
    if args.require_green and not has_allowed_green:
        attempt.problems.append("no green section where NParks allows cycling")
    if restricted is not None:
        attempt.restrictions = inspect_route(route.coordinates, restricted, step_names(route))
        for contact in attempt.restrictions:
            if contact.on_m > 0 and contact.kind in PROHIBITED[args.activity]:
                attempt.problems.append(f"on {contact.on_m:.0f} m of {contact.kind} {contact.name}")
    attempt.accepted = not attempt.problems
    return attempt


def step_names(route: heigit.MeasuredRoute) -> list[str]:
    names = ["?"] * len(route.coordinates)
    for step in route.steps:
        for index in range(step.first_index, step.last_index + 1):
            names[index] = step.name
    return names


def attempt_summary(attempt: Attempt) -> str:
    if attempt.route is None:
        return f"error: {attempt.error}"
    outcome = "accepted" if attempt.accepted else "; ".join(attempt.problems)
    return f"{attempt.route.distance_m / 1000:.2f} km, {outcome}"


def write_route_files(out: Path, name: str, coordinates: list[list[float]]) -> None:
    write_geojson(out / f"{name}.geojson", name, coordinates)
    (out / f"{name}.gpx").write_text(route_to_gpx(name, coordinates, OSM_ATTRIBUTION))


def write_geojson(path: Path, name: str, coordinates: list[list[float]]) -> None:
    feature = {
        "type": "Feature",
        "properties": {"name": name, "attribution": OSM_ATTRIBUTION},
        "geometry": {"type": "LineString", "coordinates": coordinates},
    }
    collection = {"type": "FeatureCollection", "features": [feature]}
    path.write_text(json.dumps(collection))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def geometries(geojson: dict[str, Any]) -> list[dict[str, Any]]:
    return [feature["geometry"] for feature in geojson["features"]]
