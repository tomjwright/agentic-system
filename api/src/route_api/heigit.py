"""HeiGIT openrouteservice Directions: the only code that talks to HeiGIT or reads its key.

The adapter posts to one fixed URL per profile and sends the key as the `Authorization`
header, so the API is never an open proxy. Coordinates stay GeoJSON
`(longitude, latitude)`, distances metres and durations seconds, as HeiGIT sends them.
Unknown surface codes are kept as "code N", never dropped. A malformed response is
refused, never repaired.

HeiGIT's error text echoes the coordinates it was given, so errors carry a short code
and a fixed message, never the provider's text.
"""

import math
import time
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from route_api.telemetry import tracer

DIRECTIONS_URL = "https://api.heigit.org/openrouteservice/v2/directions/{profile}/geojson"
# Running uses walkable ways; road cycling uses HeiGIT's road-bike profile, which keeps
# ordinary roads. Steps are avoided for bikes, as in feasibility/EVIDENCE.md.
PROFILES = {"running": "foot-walking", "road_cycling": "cycling-road"}
AVOID_FEATURES = {"running": ["ferries"], "road_cycling": ["ferries", "steps"]}
# A cycling-road via point in a park is often over 350 m (HeiGIT's default) from a road.
CYCLING_VIA_SNAP_M = 1000
EXTRA_INFO = ["surface", "waytype", "waycategory", "steepness"]
TIMEOUT = httpx.Timeout(30.0, connect=5.0)
ATTEMPTS = 2
MAX_RESPONSE_BYTES = 5_000_000  # a 50 km loop with instructions is well under 1 MB
RETRY_STATUSES = {502, 503, 504}

# Value table from the openrouteservice extra-info documentation.
SURFACES = {
    0: "unknown", 1: "paved", 2: "unpaved", 3: "asphalt", 4: "concrete", 5: "cobblestone",
    6: "metal", 7: "wood", 8: "compacted gravel", 9: "fine gravel", 10: "gravel", 11: "dirt",
    12: "ground", 13: "ice", 14: "paving stones", 15: "sand", 16: "woodchips", 17: "grass",
    18: "grass paver",
}  # fmt: skip

# Failures that end a whole generation run. Other failures only lose one candidate.
FATAL_CODES = {"provider_unavailable", "provider_quota_exhausted", "provider_rejected"}


class HeigitError(Exception):
    """A HeiGIT failure, as a short code and a message that are safe to show and log."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# Provider payload: the parts of HeiGIT's GeoJSON response the app reads.
class OrsGeometry(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    type: Literal["LineString"]
    coordinates: list[tuple[float, float]] | list[tuple[float, float, float]] = Field(min_length=2)


class OrsExtraSummary(BaseModel):
    value: float
    distance: float


class OrsExtra(BaseModel):
    summary: list[OrsExtraSummary]


class OrsSummary(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    distance: float = Field(default=0.0, ge=0)
    duration: float = Field(default=0.0, ge=0)


class OrsStep(BaseModel):
    name: str = ""
    way_points: tuple[int, int]


class OrsSegment(BaseModel):
    steps: list[OrsStep] = []


class OrsProperties(BaseModel):
    summary: OrsSummary
    extras: dict[str, OrsExtra] = {}
    segments: list[OrsSegment] = []


class OrsFeature(BaseModel):
    geometry: OrsGeometry
    properties: OrsProperties


class OrsMetadata(BaseModel):
    attribution: str = ""
    engine: dict[str, str] = {}


class OrsResponse(BaseModel):
    type: Literal["FeatureCollection"]
    features: list[OrsFeature] = Field(min_length=1, max_length=1)
    metadata: OrsMetadata


class ProviderRoute(BaseModel):
    """One route as the app understands it, measured in metres and seconds."""

    coordinates: list[tuple[float, float]]  # (longitude, latitude), exactly as HeiGIT sent them
    distance_m: float
    duration_s: float  # the profile's own time: walking for running, cycling for road cycling
    surfaces_m: dict[str, float]
    step_names: list[str] = []  # HeiGIT's street name at each coordinate, "" when unnamed
    engine: dict[str, str]
    attribution: str


def round_trip_body(
    activity: str, start: tuple[float, float], length_m: float, seed: int
) -> dict[str, Any]:
    return {
        "coordinates": [list(start)],
        "options": {
            "round_trip": {"length": round(length_m), "points": 3, "seed": seed},
            "avoid_features": AVOID_FEATURES[activity],
        },
        "extra_info": EXTRA_INFO,
        "instructions": True,
    }


def via_loop_body(
    activity: str, start: tuple[float, float], via: list[tuple[float, float]]
) -> dict[str, Any]:
    coordinates = [list(start)]
    for point in via:
        coordinates.append(list(point))
    coordinates.append(list(start))
    body: dict[str, Any] = {
        "coordinates": coordinates,
        "options": {"avoid_features": AVOID_FEATURES[activity]},
        "extra_info": EXTRA_INFO,
        "instructions": True,
    }
    if activity == "road_cycling":
        radiuses = [350]
        for _ in via:
            radiuses.append(CYCLING_VIA_SNAP_M)
        radiuses.append(350)
        body["radiuses"] = radiuses
    return body


class Heigit:
    def __init__(
        self,
        http: httpx.Client,
        api_key: str | None,
        request_gap_seconds: float = 2.0,
        retry_wait_seconds: float = 1.0,
    ):
        self.http = http
        self.api_key = api_key
        self.request_gap_seconds = request_gap_seconds
        self.retry_wait_seconds = retry_wait_seconds
        self.last_request_at = -math.inf

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def route(self, activity: str, body: dict[str, Any]) -> ProviderRoute:
        content = self.post(PROFILES[activity], body)
        try:
            payload = OrsResponse.model_validate_json(content)
        except ValidationError:
            raise HeigitError(
                "provider_response_invalid", "HeiGIT returned a route in an unexpected shape"
            ) from None
        feature = payload.features[0]
        coordinates = []
        for point in feature.geometry.coordinates:
            coordinates.append((point[0], point[1]))
        surfaces_m: dict[str, float] = {}
        surface = feature.properties.extras.get("surface")
        if surface is not None:
            for item in surface.summary:
                name = SURFACES.get(int(item.value), f"code {item.value:g}")
                surfaces_m[name] = surfaces_m.get(name, 0.0) + item.distance
        step_names = [""] * len(coordinates)
        for segment in feature.properties.segments:
            for step in segment.steps:
                first, last = step.way_points
                for vertex in range(max(first, 0), min(last + 1, len(coordinates))):
                    step_names[vertex] = step.name
        return ProviderRoute(
            coordinates=coordinates,
            distance_m=feature.properties.summary.distance,
            duration_s=feature.properties.summary.duration,
            surfaces_m=surfaces_m,
            engine=payload.metadata.engine,
            attribution=payload.metadata.attribution,
            step_names=step_names,
        )

    def post(self, profile: str, body: dict[str, Any]) -> bytes:
        """POST one directions request, retrying a timeout or gateway error once."""
        if not self.api_key:
            raise HeigitError("provider_not_configured", "Route generation is not configured")
        url = DIRECTIONS_URL.format(profile=profile)
        headers = {"Authorization": self.api_key}
        for attempt in range(1, ATTEMPTS + 1):
            if attempt > 1:
                time.sleep(self.retry_wait_seconds)
            self.wait_for_gap()
            try:
                with (
                    tracer.start_as_current_span("heigit.directions") as span,
                    self.http.stream(
                        "POST", url, json=body, headers=headers, timeout=TIMEOUT
                    ) as response,
                ):
                    span.set_attribute("http.response.status_code", response.status_code)
                    if response.status_code in RETRY_STATUSES:
                        continue
                    if response.status_code == 429:
                        raise HeigitError(
                            "provider_quota_exhausted", "HeiGIT's request quota is used up"
                        )
                    if response.status_code in (401, 403):
                        raise HeigitError(
                            "provider_rejected", "HeiGIT refused the request; check the key"
                        )
                    if response.status_code in (404, 500):
                        # Seen live: a generated point where nothing is routable.
                        raise HeigitError("no_route", "HeiGIT found no route for these points")
                    if response.status_code != 200:
                        raise HeigitError(
                            "provider_rejected", f"HeiGIT answered HTTP {response.status_code}"
                        )
                    return read_limited(response)
            except httpx.TransportError:
                continue
        raise HeigitError("provider_unavailable", "HeiGIT did not answer in time")

    def wait_for_gap(self) -> None:
        """Keep requests at least request_gap_seconds apart, well inside 40 a minute."""
        wait = self.last_request_at + self.request_gap_seconds - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.last_request_at = time.monotonic()


def read_limited(response: httpx.Response) -> bytes:
    body = b""
    for chunk in response.iter_bytes():
        body += chunk
        if len(body) > MAX_RESPONSE_BYTES:
            raise HeigitError("provider_response_invalid", "HeiGIT's response was too large")
    return body
