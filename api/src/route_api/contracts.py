"""Public request and response shapes. The OpenAPI document and the browser types come from these.

Points are GeoJSON: `coordinates` is `[longitude, latitude]` in degrees.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
