"""Delete what is past its retention age (docs/hosting.md#retention).

A route request holds the confirmed start location; its revisions, runs, candidates (with
route geometry) and selection are deleted with it by ON DELETE CASCADE. Searches are never
stored. Runs at every API start, which on Render Free is at least daily after idling.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from route_api.db import OwnerSessionRecord, RouteRequestRecord
from route_api.logs import log_event

ROUTE_REQUEST_DAYS = 90


def purge_expired(engine: Engine) -> None:
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=ROUTE_REQUEST_DAYS)
    with Session(engine) as session, session.begin():
        requests = session.execute(
            delete(RouteRequestRecord).where(RouteRequestRecord.created_at < cutoff)
        )
        sessions = session.execute(
            delete(OwnerSessionRecord).where(OwnerSessionRecord.expires_at < now)
        )
    log_event(
        "retention_purged",
        route_requests=requests.rowcount,  # type: ignore[attr-defined]
        sessions=sessions.rowcount,  # type: ignore[attr-defined]
    )
