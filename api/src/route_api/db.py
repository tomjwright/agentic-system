"""Database tables. Every query filters by owner_id."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RouteRequestRecord(Base):
    """A route request and the start the owner confirmed. Searches are not stored."""

    __tablename__ = "route_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64))
    activity: Mapped[str] = mapped_column(String(20))
    start_source: Mapped[str] = mapped_column(String(20))
    start_source_id: Mapped[str | None] = mapped_column(String(300))
    start_query: Mapped[str | None] = mapped_column(String(120))
    start_name: Mapped[str | None] = mapped_column(String(300))
    start_address: Mapped[str | None] = mapped_column(String(300))
    start_postal: Mapped[str | None] = mapped_column(String(10))
    start_lon: Mapped[float]
    start_lat: Mapped[float]
    start_retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RouteRequestRevisionRecord(Base):
    """One set of constraints for a route request. Never updated: a change is a new revision."""

    __tablename__ = "route_request_revisions"
    __table_args__ = (UniqueConstraint("route_request_id", "number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    route_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("route_requests.id", ondelete="CASCADE")
    )
    owner_id: Mapped[str] = mapped_column(String(64))
    number: Mapped[int]
    distance: Mapped[dict[str, Any]] = mapped_column(JSONB)
    min_m: Mapped[float]
    max_m: Mapped[float]
    target_m: Mapped[float]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GenerationRunRecord(Base):
    """One generation of a revision. The owner's operation ID makes retries land on it."""

    __tablename__ = "generation_runs"
    __table_args__ = (UniqueConstraint("owner_id", "operation_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64))
    operation_id: Mapped[uuid.UUID]
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("route_request_revisions.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(20))
    profile: Mapped[str] = mapped_column(String(20))
    generator_version: Mapped[str] = mapped_column(String(40))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RouteCandidateRecord(Base):
    """One provider attempt: its parameters, the geometry it returned, and why it was rejected."""

    __tablename__ = "route_candidates"
    __table_args__ = (UniqueConstraint("run_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generation_runs.id", ondelete="CASCADE"))
    owner_id: Mapped[str] = mapped_column(String(64))
    position: Mapped[int]
    method: Mapped[str] = mapped_column(String(20))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB)
    accepted: Mapped[bool]
    reasons: Mapped[list[str]] = mapped_column(JSONB)
    coordinates: Mapped[list[list[float]] | None] = mapped_column(JSONB)
    provider_distance_m: Mapped[float | None]
    measured_distance_m: Mapped[float | None]
    walking_duration_s: Mapped[float | None]
    surfaces_m: Mapped[dict[str, float] | None] = mapped_column(JSONB)
    engine: Mapped[dict[str, str] | None] = mapped_column(JSONB)
    attribution: Mapped[str | None] = mapped_column(String(300))


class SelectedRouteRecord(Base):
    """The candidate a run chose. Its stored geometry is what the map and the GPX show."""

    __tablename__ = "selected_routes"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("generation_runs.id", ondelete="CASCADE"), primary_key=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("route_candidates.id", ondelete="CASCADE"), unique=True
    )
    owner_id: Mapped[str] = mapped_column(String(64))
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
