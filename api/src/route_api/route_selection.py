"""Which generated loop, if any, is acceptable. Pure checks on measured geometry.

A loop is rejected, with a reason a person can read, when it does not close, starts
far from the confirmed start, leaves Singapore, has a provider distance that does not
match its own geometry (a unit or order mistake), is outside the distance bounds, or
(road cycling) runs along an expressway, slip road, road tunnel or bicycle=no way.
Geometry is never changed to make it pass.
"""

from typing import Any

from pydantic import BaseModel

from route_api.contracts import DistanceRange, DistanceTarget, RestrictedRoad
from route_api.geography import (
    distance_m,
    distance_to_land_edge_m,
    line_length_m,
    on_singapore_land,
)
from route_api.heigit import ProviderRoute

SINGLE_TARGET_TOLERANCE = 0.10
LOOP_CLOSURE_LIMIT_M = 30
START_SNAP_LIMIT_M = 200
COASTLINE_TOLERANCE_M = 50
PROVIDER_DISTANCE_TOLERANCE = 0.10
DISTANCE_LIMITS_KM = {"running": (1, 50), "road_cycling": (5, 100)}


class DistanceBounds(BaseModel):
    min_m: float
    max_m: float
    target_m: float


class Attempt(BaseModel):
    """One request to the provider: the loop it returned, or why it returned none."""

    method: str = "round_trip"
    parameters: dict[str, Any] = {}
    route: ProviderRoute | None = None
    restricted_roads: list[RestrictedRoad] | None = None  # None: not checked (running)
    problem: str | None = None


class Selection(BaseModel):
    chosen: int | None
    reasons: list[list[str]]  # one list per attempt; empty when the loop is acceptable


def distance_bounds(distance: DistanceTarget | DistanceRange) -> DistanceBounds:
    if isinstance(distance, DistanceTarget):
        target_m = distance.target_km * 1000
        return DistanceBounds(
            min_m=round(target_m * (1 - SINGLE_TARGET_TOLERANCE), 3),
            max_m=round(target_m * (1 + SINGLE_TARGET_TOLERANCE), 3),
            target_m=target_m,
        )
    min_m = distance.min_km * 1000
    max_m = distance.max_km * 1000
    return DistanceBounds(min_m=min_m, max_m=max_m, target_m=(min_m + max_m) / 2)


def outside_activity_limits(activity: str, distance: DistanceTarget | DistanceRange) -> bool:
    lowest_km, highest_km = DISTANCE_LIMITS_KM[activity]
    if isinstance(distance, DistanceTarget):
        return not lowest_km <= distance.target_km <= highest_km
    return distance.min_km < lowest_km or distance.max_km > highest_km


def rejection_reasons(
    start: tuple[float, float],
    bounds: DistanceBounds,
    route: ProviderRoute,
    restricted_roads: list[RestrictedRoad] | None = None,
) -> list[str]:
    coordinates = route.coordinates
    if len(coordinates) < 2:
        return ["the route has fewer than two points"]
    reasons = []

    gap_m = distance_m(coordinates[0], coordinates[-1])
    if gap_m > LOOP_CLOSURE_LIMIT_M:
        reasons.append(f"does not close: it ends {gap_m:.0f} m from where it starts")

    snap_m = distance_m(start, coordinates[0])
    if snap_m > START_SNAP_LIMIT_M:
        reasons.append(f"starts {snap_m:.0f} m from the confirmed start")

    outside = points_outside_singapore(coordinates)
    if outside:
        reasons.append(f"{outside} of {len(coordinates)} points are outside Singapore")

    measured_m = line_length_m(coordinates)
    if abs(route.distance_m - measured_m) > PROVIDER_DISTANCE_TOLERANCE * measured_m:
        reasons.append(
            f"HeiGIT's distance ({route.distance_m:.0f} m) does not match"
            f" the geometry ({measured_m:.0f} m)"
        )

    if not bounds.min_m <= measured_m <= bounds.max_m:
        reasons.append(
            f"{measured_m / 1000:.3f} km is outside"
            f" {bounds.min_m / 1000:.3f}-{bounds.max_m / 1000:.3f} km"
        )

    for road in restricted_roads or []:
        if road.outcome == "on_prohibited_road":
            reasons.append(f"runs {road.on_m:.0f} m along {road.kind} {road.name}")
    return reasons


def points_outside_singapore(coordinates: list[tuple[float, float]]) -> int:
    """Points off Singapore's land by more than the coastline outline's tolerance."""
    outside = 0
    for lon, lat in coordinates:
        if on_singapore_land(lon, lat):
            continue
        if distance_to_land_edge_m(lon, lat) > COASTLINE_TOLERANCE_M:
            outside += 1
    return outside


def select_route(
    start: tuple[float, float], bounds: DistanceBounds, attempts: list[Attempt]
) -> Selection:
    """Choose the acceptable loop nearest the target, or none, with every attempt's reasons."""
    chosen = None
    best_miss_m = 0.0
    all_reasons = []
    for index, attempt in enumerate(attempts):
        if attempt.route is None:
            all_reasons.append([attempt.problem or "HeiGIT returned no route"])
            continue
        reasons = rejection_reasons(start, bounds, attempt.route, attempt.restricted_roads)
        all_reasons.append(reasons)
        if reasons:
            continue
        miss_m = abs(line_length_m(attempt.route.coordinates) - bounds.target_m)
        if chosen is None or miss_m < best_miss_m:
            chosen = index
            best_miss_m = miss_m
    return Selection(chosen=chosen, reasons=all_reasons)
