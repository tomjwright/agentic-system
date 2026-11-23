"""Ask HeiGIT for a few running loops from a confirmed start and pick an acceptable one.

This follows the feasibility go conditions (feasibility/EVIDENCE.md):

- round trips use fixed seeds 1, 2, 3, ... so a run can be repeated;
- after each measured loop the requested length is corrected by how far the last loop
  missed the target, because HeiGIT's round-trip lengths drift;
- after two round trips fail or leave Singapore (a coastal start puts random points in
  the sea), the next attempts are via loops through points pulled inland.

At most MAX_ATTEMPTS requests are made, and generation stops at the first acceptable loop.
"""

import math

from pydantic import BaseModel

from route_api.geography import line_length_m, offset, on_singapore_land
from route_api.heigit import FATAL_CODES, Heigit, HeigitError, round_trip_body, via_loop_body
from route_api.route_selection import (
    Attempt,
    DistanceBounds,
    Selection,
    points_outside_singapore,
    rejection_reasons,
    select_route,
)

GENERATOR_VERSION = "running-loop-1"
MAX_ATTEMPTS = 5
ROUND_TRIP_FAILURES_BEFORE_VIA = 2
# A via loop through 3 points on a circle through the start is about 5.66 radii as the crow
# flies; paths add roughly 30%.
VIA_LOOP_RADII = 5.66 * 1.3
# Via loops head towards the middle of the island first, then either side of it.
ISLAND_CENTRE = (103.8198, 1.3521)
VIA_TURNS = [0, 60, -60]


class Generation(BaseModel):
    attempts: list[Attempt]
    selection: Selection | None  # None when a provider failure stopped the run
    error_code: str | None = None
    error_message: str | None = None


def generate(heigit: Heigit, start: tuple[float, float], bounds: DistanceBounds) -> Generation:
    attempts: list[Attempt] = []
    length_m = bounds.target_m
    seed = 0
    round_trip_failures = 0
    via_loops = 0
    for _ in range(MAX_ATTEMPTS):
        if round_trip_failures < ROUND_TRIP_FAILURES_BEFORE_VIA:
            seed += 1
            attempt = Attempt(
                method="round_trip", parameters={"length_m": round(length_m), "seed": seed}
            )
            body = round_trip_body(start, length_m, seed)
        else:
            bearing = (inland_bearing(start) + VIA_TURNS[via_loops % len(VIA_TURNS)]) % 360
            via_loops += 1
            attempt = Attempt(
                method="via_loop", parameters={"length_m": round(length_m), "bearing": bearing}
            )
            body = via_loop_body(start, inland_via_points(start, length_m, bearing))
        attempt.parameters["provider_request"] = body
        attempts.append(attempt)

        try:
            route = heigit.running_route(body)
        except HeigitError as error:
            attempt.problem = str(error)
            if error.code in FATAL_CODES:
                return Generation(
                    attempts=attempts,
                    selection=select_route(start, bounds, attempts),
                    error_code=error.code,
                    error_message=str(error),
                )
            if attempt.method == "round_trip":
                round_trip_failures += 1
            continue

        attempt.route = route
        if not rejection_reasons(start, bounds, route):
            break
        if attempt.method == "round_trip" and points_outside_singapore(route.coordinates):
            round_trip_failures += 1
        measured_m = line_length_m(route.coordinates)
        if measured_m > 0:
            corrected_m = length_m * bounds.target_m / measured_m
            length_m = min(max(corrected_m, bounds.target_m / 2), bounds.target_m * 1.5)

    return Generation(attempts=attempts, selection=select_route(start, bounds, attempts))


def inland_bearing(start: tuple[float, float]) -> float:
    """Compass bearing from the start towards the middle of Singapore."""
    east_m = (ISLAND_CENTRE[0] - start[0]) * math.cos(math.radians(start[1]))
    north_m = ISLAND_CENTRE[1] - start[1]
    return round(math.degrees(math.atan2(east_m, north_m)) % 360)


def inland_via_points(
    start: tuple[float, float], length_m: float, bearing: float
) -> list[tuple[float, float]]:
    """Three points on a circle through the start, each pulled towards the start until on land."""
    radius_m = length_m / VIA_LOOP_RADII
    centre = offset(start, radius_m, bearing)
    via = []
    for turn in (90, 180, 270):
        point = offset(centre, radius_m, bearing + 180 + turn)
        for share in (1.0, 0.8, 0.6, 0.4, 0.2):
            pulled = (
                round(start[0] + share * (point[0] - start[0]), 6),
                round(start[1] + share * (point[1] - start[1]), 6),
            )
            if on_singapore_land(*pulled):
                via.append(pulled)
                break
    return via
