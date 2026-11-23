"""Distance targets and route validation.

A single target such as "10" (km) accepts plus or minus 10 percent.
An explicit range such as "60-70" is used exactly as given: it is never widened.
"""

import itertools
import math
from typing import Any

from pydantic import BaseModel

from route_feasibility.geo import distance_m, point_to_segment_m, ring_contains, sample_route

SINGLE_TARGET_TOLERANCE = 0.10


class DistanceTarget(BaseModel):
    text: str
    min_m: float
    max_m: float

    def accepts(self, distance_m: float) -> bool:
        return self.min_m <= distance_m <= self.max_m


def parse_target(text: str) -> DistanceTarget:
    if "-" in text:
        low_text, high_text = text.split("-", 1)
        low_m = float(low_text) * 1000
        high_m = float(high_text) * 1000
    else:
        target_m = float(text) * 1000
        low_m = target_m * (1 - SINGLE_TARGET_TOLERANCE)
        high_m = target_m * (1 + SINGLE_TARGET_TOLERANCE)
    if low_m <= 0 or high_m <= low_m:
        raise ValueError(f"not a usable distance in km: {text!r}")
    return DistanceTarget(text=text, min_m=low_m, max_m=high_m)


LOOP_CLOSURE_LIMIT_M = 30
COASTLINE_TOLERANCE_M = 50


class Boundary:
    """Singapore's land area, as GeoJSON Polygon or MultiPolygon geometries.

    The real boundary is the URA Master Plan 2019 Planning Area Boundary (No Sea).
    """

    def __init__(self, geometries: list[dict[str, Any]]) -> None:
        self.polygons: list[list[list[list[float]]]] = []
        for geometry in geometries:
            if geometry["type"] == "Polygon":
                self.polygons.append(geometry["coordinates"])
            elif geometry["type"] == "MultiPolygon":
                self.polygons.extend(geometry["coordinates"])

    def contains(self, point: list[float]) -> bool:
        for rings in self.polygons:
            outer, holes = rings[0], rings[1:]
            if not ring_contains(outer, point):
                continue
            in_a_hole = False
            for hole in holes:
                if ring_contains(hole, point):
                    in_a_hole = True
            if not in_a_hole:
                return True
        return False

    def distance_to_edge_m(self, point: list[float]) -> float:
        nearest = math.inf
        for rings in self.polygons:
            for ring in rings:
                for a, b in itertools.pairwise(ring):
                    nearest = min(nearest, point_to_segment_m(point, a, b))
        return nearest


def validate_loop(coordinates: list[list[float]], boundary: Boundary) -> list[str]:
    """Return the problems that stop this geometry being a valid Singapore loop."""
    problems: list[str] = []

    finite = []
    for point in coordinates:
        if math.isfinite(point[0]) and math.isfinite(point[1]):
            finite.append(point)
    not_finite = len(coordinates) - len(finite)
    if not_finite:
        problems.append(f"{not_finite} points are not finite numbers")
        return problems

    gap_m = distance_m(coordinates[0], coordinates[-1])
    if gap_m > LOOP_CLOSURE_LIMIT_M:
        problems.append(f"loop does not close: it ends {gap_m:.0f} m from where it starts")

    outside = 0
    for point in coordinates:
        if boundary.contains(point):
            continue
        if boundary.distance_to_edge_m(point) > COASTLINE_TOLERANCE_M:
            outside += 1
    if outside:
        problems.append(f"{outside} of {len(coordinates)} points are outside Singapore")

    return problems


REPEAT_SPACING_M = 20.0
REPEAT_DISTANCE_M = 15.0
REPEAT_GAP_M = 300.0
REPEAT_CELL_DEGREES = 0.0005  # about 55 m


def repeated_share(coordinates: list[list[float]]) -> float:
    """Share of the route that runs over ground it already covered (out-and-back, backtracking).

    A point counts as repeated when an earlier point at least REPEAT_GAP_M back along
    the route lies within REPEAT_DISTANCE_M of it.
    """
    samples = sample_route(coordinates, REPEAT_SPACING_M)
    seen: dict[tuple[int, int], list[tuple[list[float], float]]] = {}
    travelled_m = 0.0
    repeated = 0
    previous = samples[0][0]
    for point, _ in samples:
        travelled_m += distance_m(previous, point)
        previous = point
        x = int(point[0] // REPEAT_CELL_DEGREES)
        y = int(point[1] // REPEAT_CELL_DEGREES)
        found = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for earlier, earlier_m in seen.get((x + dx, y + dy), []):
                    far_back = travelled_m - earlier_m >= REPEAT_GAP_M
                    if far_back and distance_m(point, earlier) <= REPEAT_DISTANCE_M:
                        found = True
        if found:
            repeated += 1
        seen.setdefault((x, y), []).append((point, travelled_m))
    return repeated / len(samples)
