"""Retention: route requests (which hold start locations and route geometry) and ended sign-ins
are deleted once they pass the documented age (docs/hosting.md)."""

from datetime import UTC, datetime, timedelta

import pytest
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
from route_api.main import app_from_env
from route_api.retention import E2E_ROUTE_REQUEST_HOURS, ROUTE_REQUEST_DAYS, purge_expired
from tests.conftest import LOCAL_OWNER
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


def test_the_staged_browser_tests_route_requests_go_after_a_day(api: TestClient) -> None:
    for _ in range(3):
        generate_5km(api)
    engine = api.app.state.engine  # type: ignore[attr-defined]
    now = datetime.now(UTC)
    with Session(engine) as session, session.begin():
        ids = session.scalars(select(RouteRequestRecord.id)).all()
        ages = {
            ids[0]: ("e2e", E2E_ROUTE_REQUEST_HOURS + 1),
            ids[1]: ("e2e", E2E_ROUTE_REQUEST_HOURS - 1),
            ids[2]: (LOCAL_OWNER, E2E_ROUTE_REQUEST_HOURS + 1),
        }
        for request_id, (owner, hours) in ages.items():
            session.execute(
                update(RouteRequestRecord)
                .where(RouteRequestRecord.id == request_id)
                .values(owner_id=owner, created_at=now - timedelta(hours=hours))
            )

    purge_expired(engine)

    with Session(engine) as session:
        kept = set(session.scalars(select(RouteRequestRecord.id)).all())
    assert kept == {ids[1], ids[2]}


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
    assert owners == [LOCAL_OWNER]


def test_the_api_purges_on_start(clean_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    # Tom is allowed by default, so only the expiry can remove his session.
    create_session(clean_engine, "github:119127762")
    with Session(clean_engine) as session, session.begin():
        session.execute(
            update(OwnerSessionRecord).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    monkeypatch.setenv("DATABASE_URL", clean_engine.url.render_as_string(hide_password=False))

    app_from_env()

    assert count(clean_engine, OwnerSessionRecord) == 0
