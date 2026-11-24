"""What the route agent reads and writes, as typed shapes.

The server builds a RunRequest; models only ever produce an Interpretation (the agent)
or a Verdict (the judge), and both are validated before use. RouteFacts are measured by
deterministic code and are the only facts a draft may state. None of these shapes the
models see holds coordinates: the start's position stays in RunStart, on the server.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from route_api.contracts import Activity, Distance
from route_api.generation import Generation


class RunStart(BaseModel):
    """The confirmed start. Only its name is shown to a model."""

    name: str | None
    coordinates: tuple[float, float]  # (longitude, latitude)


class RunRequest(BaseModel):
    run_id: UUID
    brief: str = Field(max_length=1000, description="What the user typed")
    activity: Activity | None = Field(default=None, description="The form's choice, if any")
    distance: Distance | None = Field(default=None, description="The form's distance, if any")
    start: RunStart | None


class Interpretation(BaseModel):
    """The agent's reading of the user's message. Fields the message does not state are null."""

    activity: Activity | None = None
    distance: Distance | None = None
    preferences: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Other wishes in the message, a few words each, e.g. 'shaded'",
    )


class Clarification(BaseModel):
    reason: Literal["missing_activity", "missing_distance", "missing_start"]


class RouteFacts(BaseModel):
    """Measured facts about a generation: everything an answer may state."""

    outcome: Literal["route", "no_route", "provider_error"]
    activity: Activity
    start_name: str | None
    min_km: float
    max_km: float
    distance_km: float | None = None
    duration_minutes: int | None = Field(default=None, description="HeiGIT's time")
    tries: int
    limitations: list[str] = Field(default_factory=list)
    error_code: str | None = None
    unsupported_preferences: list[str] = Field(default_factory=list)


class Verdict(BaseModel):
    """The judge's decision on one draft."""

    approved: bool
    reasons: list[str] = Field(description="Every problem found; empty when approved")


FallbackReason = Literal[
    "interpretation_unavailable",
    "no_route",
    "draft_unavailable",
    "judge_unavailable",
    "rejected_twice",
]


class AgentResult(BaseModel):
    run_id: UUID
    kind: Literal["clarification", "route", "no_route", "failed"]
    message: str = Field(description="An approved draft or the factual fallback, never a draft")
    message_source: Literal["approved_draft", "fallback"]
    fallback_reason: FallbackReason | None
    clarification: Clarification | None
    facts: RouteFacts | None
    generation: Generation | None = Field(description="For storage; never shown to a model")
    verdicts: list[Verdict]
    repairs: int
