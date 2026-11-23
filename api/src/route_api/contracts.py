"""Public request and response shapes. The OpenAPI document and the browser types come from these.

Points are GeoJSON: `coordinates` is `[longitude, latitude]` in degrees.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Activity = Literal["running", "road_cycling"]
StartSource = Literal["onemap", "map_selection"]
SearchOutcome = Literal["no_match", "single_match", "multiple_matches"]
ErrorCode = Literal[
    "invalid_request",
    "outside_singapore",
    "candidate_not_found",
    "not_found",
    "provider_not_configured",
    "provider_unavailable",
    "provider_rejected",
    "provider_response_invalid",
    "provider_quota_exhausted",
    "operation_conflict",
    "no_route_selected",
    "generation_interrupted",
]


class Point(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float] = Field(description="[longitude, latitude] in degrees")

    @field_validator("coordinates")
    @classmethod
    def within_world(cls, coordinates: tuple[float, float]) -> tuple[float, float]:
        lon, lat = coordinates
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            raise ValueError("coordinates must be [longitude, latitude] in degrees")
        return coordinates


class PlaceSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=120)


class Candidate(BaseModel):
    source: Literal["onemap"] = "onemap"
    source_id: str
    name: str
    address: str
    postal: str | None
    point: Point


class PlaceSearchResponse(BaseModel):
    outcome: SearchOutcome = Field(
        description="A start is never chosen automatically: even a single match needs confirming."
    )
    candidates: list[Candidate]
    more_results: bool = Field(description="OneMap has more pages; a more specific query helps.")


class NamedStartChoice(BaseModel):
    kind: Literal["named"]
    query: str = Field(min_length=2, max_length=120)
    source_id: str = Field(max_length=300)


class MapStartChoice(BaseModel):
    kind: Literal["map"]
    point: Point


class RouteRequestCreate(BaseModel):
    activity: Activity
    start: Annotated[NamedStartChoice | MapStartChoice, Field(discriminator="kind")]


class ConfirmedStart(BaseModel):
    source: StartSource
    source_id: str | None
    query: str | None
    name: str | None
    address: str | None
    postal: str | None
    point: Point
    retrieved_at: datetime


class RouteRequest(BaseModel):
    id: UUID
    activity: Activity
    start: ConfirmedStart
    created_at: datetime


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


MIN_DISTANCE_KM = 1
MAX_DISTANCE_KM = 100  # per activity: route_selection.DISTANCE_LIMITS_KM


class DistanceTarget(BaseModel):
    """One distance to aim for. A loop within 10% either side of it is acceptable."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    kind: Literal["target"]
    target_km: float = Field(ge=MIN_DISTANCE_KM, le=MAX_DISTANCE_KM)


class DistanceRange(BaseModel):
    """Exact lower and upper bounds. No tolerance is added on either side."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    kind: Literal["range"]
    min_km: float = Field(ge=MIN_DISTANCE_KM, le=MAX_DISTANCE_KM)
    max_km: float = Field(ge=MIN_DISTANCE_KM, le=MAX_DISTANCE_KM)

    @model_validator(mode="after")
    def lower_below_upper(self) -> "DistanceRange":
        if self.min_km >= self.max_km:
            raise ValueError("min_km must be below max_km")
        return self


Distance = Annotated[DistanceTarget | DistanceRange, Field(discriminator="kind")]


RunStatus = Literal["generating", "succeeded", "no_route", "failed"]


class RunCreate(BaseModel):
    operation_id: UUID = Field(
        description="Chosen by the client. Sending the same one again returns the same run."
    )
    distance: Distance


class DistanceBoundsOut(BaseModel):
    min_m: float
    max_m: float


class RouteCandidate(BaseModel):
    position: int
    method: Literal["round_trip", "via_loop"]
    seed: int | None = Field(description="Round-trip seed; null for a via loop")
    requested_length_m: int = Field(description="Length asked of HeiGIT, after correction")
    measured_distance_m: float | None = Field(description="Measured along the returned geometry")
    accepted: bool
    reasons: list[str] = Field(description="Why this candidate was rejected; empty if accepted")


class GenerationRun(BaseModel):
    id: UUID
    route_request_id: UUID
    revision: int = Field(description="The request revision, numbered from 1; never changed")
    distance: Distance
    bounds: DistanceBoundsOut = Field(description="Accepted distance in metres")
    status: RunStatus
    error: ErrorDetail | None
    candidates: list[RouteCandidate]
    provider: Literal["heigit"] = "heigit"
    profile: str
    generator_version: str
    started_at: datetime
    finished_at: datetime | None


class LineString(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[float, float]] = Field(description="[longitude, latitude] in degrees")


class SurfaceDistance(BaseModel):
    surface: str
    distance_m: float


class RestrictedRoad(BaseModel):
    """One OpenStreetMap road from the restriction check that the route comes near."""

    kind: Literal[
        "expressway", "expressway slip road", "road tunnel", "bicycle=no", "major arterial (trunk)"
    ]
    name: str
    osm_way_ids: list[int]
    near_m: float = Field(description="Route length within 8 m: crossings, bridges, paths beside")
    on_m: float = Field(description="Route length running along the road itself")
    outcome: Literal["on_prohibited_road", "crossing_or_beside", "on_disclosed_road"]


class AccessCheck(BaseModel):
    status: Literal["not_checked", "no_prohibited_road_found"] = Field(
        description="Access anywhere else on the route is unknown, never verified"
    )
    source: str | None = Field(description="The OpenStreetMap extract the check used")
    roads: list[RestrictedRoad]


class SelectedRoute(BaseModel):
    run_id: UUID
    geometry: LineString
    distance_m: float = Field(description="Measured along the geometry")
    target_m: float
    deviation_m: float = Field(description="distance_m minus target_m")
    bounds: DistanceBoundsOut
    activity: Activity
    profile: str = Field(description="HeiGIT profile: foot-walking or cycling-road")
    duration_s: float = Field(
        description="HeiGIT's time for the profile. For running it is a walking time."
    )
    surfaces: list[SurfaceDistance]
    unknown_surface_share: float = Field(description="Share of the distance with no known surface")
    access: AccessCheck
    limitations: list[str]
    attribution: str
    provider_engine: str
    selected_at: datetime


class SignedIn(BaseModel):
    owner_id: str
    csrf_token: str = Field(description="Send as X-CSRF-Token with every POST.")
