"""Retention: route requests (which hold start locations and route geometry) and ended sign-ins
are deleted once they pass the documented age (docs/hosting.md)."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from route_api.auth import create_session
from route_api.db import (
    GenerationRunRecord,
    OwnerSessionRecord,
    RouteCandidateRecord,
    RouteRequestRecord,
)
from route_api.retention import ROUTE_REQUEST_DAYS, purge_expired
from tests.test_runs import AVENUE_SOUTH_BLOCK_11, confirm_start, start_run


def generate_5km(api: TestClient) -> None:
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)
    assert start_run(api, request_id, {"kind": "target", "target_km": 5}).status_code == 201


def count(engine: Engine, table: type) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(table)) or 0


def test_old_route_requests_go_with_everything_under_them(api: TestClient) -> None:
    generate_5km(api)
    generate_5km(api)
    engine = api.app.state.engine  # type: ignore[attr-defined]
    old = datetime.now(UTC) - timedelta(days=ROUTE_REQUEST_DAYS + 1)
    with Session(engine) as session, session.begin():
        first = session.scalars(select(RouteRequestRecord.id)).first()
        session.execute(
            update(RouteRequestRecord).where(RouteRequestRecord.id == first).values(created_at=old)
        )

    purge_expired(engine)

    assert count(engine, RouteRequestRecord) == 1
    assert count(engine, GenerationRunRecord) == 1
    assert count(engine, RouteCandidateRecord) > 0


def test_expired_sign_ins_are_deleted(api: TestClient) -> None:
    engine = api.app.state.engine  # type: ignore[attr-defined]
    create_session(engine, "tom")
    with Session(engine) as session, session.begin():
        session.execute(
            update(OwnerSessionRecord)
            .where(OwnerSessionRecord.owner_id == "tom")
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )

    purge_expired(engine)

    with Session(engine) as session:
        owners = session.scalars(select(OwnerSessionRecord.owner_id)).all()
    assert owners == ["local-owner"]
