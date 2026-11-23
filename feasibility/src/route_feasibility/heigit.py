"""HeiGIT openrouteservice Directions: the only place the API key is used.

The key goes in the Authorization header of requests to the fixed HeiGIT URL below
and nowhere else. Error messages never include the key or the request headers.
"""

from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

HEIGIT_DIRECTIONS_URL = "https://api.heigit.org/openrouteservice/v2/directions"
PROFILES = {"run": "foot-walking", "ride": "cycling-road"}
AVOID_FEATURES = {"run": ["ferries"], "ride": ["ferries", "steps"]}
EXTRA_INFO = ["surface", "waytype", "waycategory", "steepness"]
MAX_RESPONSE_BYTES = 10_000_000
TIMEOUT_SECONDS = 60

# Value tables from the openrouteservice extra-info documentation.
SURFACES = {
    0: "unknown", 1: "paved", 2: "unpaved", 3: "asphalt", 4: "concrete", 5: "cobblestone",
    6: "metal", 7: "wood", 8: "compacted gravel", 9: "fine gravel", 10: "gravel", 11: "dirt",
    12: "ground", 13: "ice", 14: "paving stones", 15: "sand", 16: "woodchips", 17: "grass",
    18: "grass paver",
}  # fmt: skip
WAY_TYPES = {
    0: "unknown", 1: "state road", 2: "road", 3: "street", 4: "path", 5: "track",
    6: "cycleway", 7: "footway", 8: "steps", 9: "ferry", 10: "construction",
}  # fmt: skip
WAY_CATEGORIES = {1: "highway", 2: "tollway", 4: "steps", 8: "ferry", 16: "ford"}


class HeigitError(Exception):
    pass


# Provider payload: only the parts of the GeoJSON response this experiment reads.
class OrsExtra(BaseModel):
    values: list[list[float]]
    summary: list[dict[str, float]]


class OrsStep(BaseModel):
    name: str
    distance: float
    way_points: list[int]


class OrsSegment(BaseModel):
    steps: list[OrsStep] = []


class OrsSummary(BaseModel):
    distance: float = 0.0
    duration: float = 0.0


class OrsProperties(BaseModel):
    summary: OrsSummary
    way_points: list[int]
    extras: dict[str, OrsExtra] = {}
    segments: list[OrsSegment] = []
    warnings: list[dict[str, Any]] = []


class OrsGeometry(BaseModel):
    type: str
    coordinates: list[list[float]]


class OrsFeature(BaseModel):
    geometry: OrsGeometry
    properties: OrsProperties


class OrsResponse(BaseModel):
    features: list[OrsFeature]
    metadata: dict[str, Any]


# Normalized result used by the rest of the experiment.
class Step(BaseModel):
    name: str
    distance_m: float
    first_index: int
    last_index: int


class MeasuredRoute(BaseModel):
    profile: str
    request: dict[str, Any]
    coordinates: list[list[float]]
    distance_m: float
    duration_s: float
    waypoint_indices: list[int]
    surfaces_m: dict[str, float]
    way_types_m: dict[str, float]
    way_categories_m: dict[str, float]
    steps: list[Step]
    warnings: list[str]
    engine: dict[str, Any]
    attribution: str
    quota_remaining: str | None


def round_trip_body(
    activity: str, start: list[float], length_m: float, seed: int
) -> dict[str, Any]:
    return {
        "coordinates": [start],
        "options": {
            "round_trip": {"length": round(length_m), "points": 3, "seed": seed},
            "avoid_features": AVOID_FEATURES[activity],
        },
        "extra_info": EXTRA_INFO,
        "instructions": True,
    }


def waypoint_loop_body(activity: str, start: list[float], via: list[list[float]]) -> dict[str, Any]:
    return {
        "coordinates": [start, *via, start],
        "options": {"avoid_features": AVOID_FEATURES[activity]},
        "extra_info": EXTRA_INFO,
        "instructions": True,
    }


def summary_by_name(extra: OrsExtra | None, names: dict[int, str]) -> dict[str, float]:
    totals: dict[str, float] = {}
    if extra is None:
        return totals
    for item in extra.summary:
        value = int(item["value"])
        name = names.get(value, f"code {value}")
        totals[name] = totals.get(name, 0.0) + item["distance"]
    return totals


def category_summary(extra: OrsExtra | None) -> dict[str, float]:
    """Way categories are bit fields: a value of 3 is both highway (1) and tollway (2)."""
    totals: dict[str, float] = {}
    if extra is None:
        return totals
    for item in extra.summary:
        value = int(item["value"])
        if value == 0:
            totals["none of these"] = totals.get("none of these", 0.0) + item["distance"]
        for bit, name in WAY_CATEGORIES.items():
            if value & bit:
                totals[name] = totals.get(name, 0.0) + item["distance"]
    return totals


def directions(
    http: httpx.Client, api_key: str, activity: str, body: dict[str, Any]
) -> MeasuredRoute:
    profile = PROFILES[activity]
    url = f"{HEIGIT_DIRECTIONS_URL}/{profile}/geojson"
    try:
        response = http.post(
            url, json=body, headers={"Authorization": api_key}, timeout=TIMEOUT_SECONDS
        )
    except httpx.HTTPError as error:
        raise HeigitError(f"HeiGIT request failed: {type(error).__name__}") from None
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise HeigitError("HeiGIT response is larger than expected")
    if response.status_code != 200:
        raise HeigitError(f"HeiGIT returned {response.status_code}: {provider_message(response)}")
    try:
        payload = OrsResponse.model_validate_json(response.content)
    except ValidationError:
        raise HeigitError("HeiGIT response did not match the expected GeoJSON shape") from None
    if len(payload.features) != 1 or payload.features[0].geometry.type != "LineString":
        raise HeigitError("HeiGIT response did not contain exactly one LineString route")

    feature = payload.features[0]
    properties = feature.properties
    steps = []
    for segment in properties.segments:
        for step in segment.steps:
            first, last = step.way_points[0], step.way_points[-1]
            steps.append(
                Step(name=step.name, distance_m=step.distance, first_index=first, last_index=last)
            )
    warnings = []
    for warning in properties.warnings:
        warnings.append(str(warning.get("message", warning)))
    return MeasuredRoute(
        profile=profile,
        request=body,
        coordinates=[[point[0], point[1]] for point in feature.geometry.coordinates],
        distance_m=properties.summary.distance,
        duration_s=properties.summary.duration,
        waypoint_indices=properties.way_points,
        surfaces_m=summary_by_name(properties.extras.get("surface"), SURFACES),
        way_types_m=summary_by_name(properties.extras.get("waytype"), WAY_TYPES),
        way_categories_m=category_summary(properties.extras.get("waycategory")),
        steps=steps,
        warnings=warnings,
        engine=payload.metadata.get("engine", {}),
        attribution=payload.metadata.get("attribution", ""),
        quota_remaining=response.headers.get("x-ratelimit-remaining"),
    )


def provider_message(response: httpx.Response) -> str:
    """The provider's own error text, cut short. It never contains our request headers."""
    try:
        error = response.json().get("error")
    except ValueError:
        return response.text[:200]
    if isinstance(error, dict):
        return str(error.get("message", error))[:200]
    return str(error)[:200]
