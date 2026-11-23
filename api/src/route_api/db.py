"""Database tables. Every query on route_requests filters by owner_id."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
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
