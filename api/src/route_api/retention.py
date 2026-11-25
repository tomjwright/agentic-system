"""Delete what is past its retention age (docs/hosting.md#retention).

A route request holds the confirmed start location; its revisions, runs, candidates (with
route geometry), selection and agent runs are deleted with it by ON DELETE CASCADE. Agent
runs asked before a start was confirmed have no route request and go at the same age.
Searches are never stored. The staged browser test's route requests (owner e2e) go after a
day: its daily run limit needs a day of runs, and nobody needs them after that. Runs at
every API start, which on Render Free is at least daily after idling.
"""

from datetime import datetime, timedelta

from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from route_api.auth import E2E_OWNER
from route_api.db import AgentRunRecord, OwnerSessionRecord, RouteRequestRecord
from route_api.logs import log_event

ROUTE_REQUEST_DAYS = 90
E2E_ROUTE_REQUEST_HOURS = 24


def purge_expired(engine: Engine, now: datetime) -> None:
    cutoff = now - timedelta(days=ROUTE_REQUEST_DAYS)
    with Session(engine) as session, session.begin():
        requests = session.execute(
            delete(RouteRequestRecord).where(RouteRequestRecord.created_at < cutoff)
        )
        e2e_cutoff = now - timedelta(hours=E2E_ROUTE_REQUEST_HOURS)
        e2e_requests = session.execute(
            delete(RouteRequestRecord)
            .where(RouteRequestRecord.owner_id == E2E_OWNER)
            .where(RouteRequestRecord.created_at < e2e_cutoff)
        )
        agent_runs = session.execute(
            delete(AgentRunRecord)
            .where(AgentRunRecord.route_request_id.is_(None))
            .where(AgentRunRecord.started_at < cutoff)
        )
        sessions = session.execute(
            delete(OwnerSessionRecord).where(OwnerSessionRecord.expires_at < now)
        )
    log_event(
        "retention_purged",
        route_requests=requests.rowcount,  # type: ignore[attr-defined]
        e2e_route_requests=e2e_requests.rowcount,  # type: ignore[attr-defined]
        agent_runs_without_start=agent_runs.rowcount,  # type: ignore[attr-defined]
        sessions=sessions.rowcount,  # type: ignore[attr-defined]
    )
