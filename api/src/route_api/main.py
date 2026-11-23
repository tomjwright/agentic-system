"""The HTTP API: place search, start confirmation and owner-scoped route requests.

Owner identity (local development only): there is no sign-in yet. The caller's owner
is the `X-Owner-Id` header, or LOCAL_OWNER_ID when the header is missing, so anyone
who can reach the API can claim any owner. Issue #5 replaces this with managed sign-in
before the app is hosted. Keep the API on localhost until then.
"""

import os
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from fastapi import FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from route_api.contracts import (
    Candidate,
    ConfirmedStart,
    ErrorResponse,
    MapStartChoice,
    PlaceSearchRequest,
    PlaceSearchResponse,
    Point,
    RouteRequest,
    RouteRequestCreate,
    SearchOutcome,
)
from route_api.db import RouteRequestRecord
from route_api.geography import on_singapore_land
from route_api.logs import configure_logging, log_event
from route_api.onemap import OneMap, ProviderError

ID_PATTERN = r"^[A-Za-z0-9._-]{1,64}$"
ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}
OwnerHeader = Annotated[str | None, Header(alias="X-Owner-Id", pattern=ID_PATTERN)]


class ApiError(Exception):
    """An expected failure, answered as {"error": {"code", "message"}} with this status."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


def error_response(status: int, code: str, message: str) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    return JSONResponse(status_code=status, content=body)


def to_route_request(record: RouteRequestRecord) -> RouteRequest:
    start = ConfirmedStart(
        source=record.start_source,  # type: ignore[arg-type]
        source_id=record.start_source_id,
        query=record.start_query,
        name=record.start_name,
        address=record.start_address,
        postal=record.start_postal,
        point=Point(coordinates=(record.start_lon, record.start_lat)),
        retrieved_at=record.start_retrieved_at,
    )
    return RouteRequest(
        id=record.id,
        activity=record.activity,  # type: ignore[arg-type]
        start=start,
        created_at=record.created_at,
    )


def create_app(onemap: OneMap, engine: Engine, local_owner: str) -> FastAPI:
    app = FastAPI(title="Singapore route creator API", version="0.1.0")

    @app.middleware("http")
    async def log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", "")
        if not re.match(ID_PATTERN, request_id):
            request_id = uuid.uuid4().hex
        started = time.monotonic()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        log_event(
            "request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        return error_response(422, "invalid_request", f"{where}: {first['msg']}")

    @app.exception_handler(ApiError)
    async def api_error(request: Request, error: ApiError) -> JSONResponse:
        return error_response(error.status, error.code, str(error))

    @app.exception_handler(ProviderError)
    async def provider_failed(request: Request, error: ProviderError) -> JSONResponse:
        log_event("provider_error", provider="onemap", code=error.code)
        status = 502
        if error.code == "provider_not_configured":
            status = 503
        return error_response(status, error.code, str(error))

    @app.post("/api/places/search", responses=ERRORS)
    def search_places(body: PlaceSearchRequest) -> PlaceSearchResponse:
        result = onemap.search(body.query)
        candidates = []
        for place in result.places:
            if not on_singapore_land(*place.coordinates):
                continue
            candidates.append(
                Candidate(
                    source_id=place.source_id,
                    name=place.name,
                    address=place.address,
                    postal=place.postal,
                    point=Point(coordinates=place.coordinates),
                )
            )
        outcome: SearchOutcome = "multiple_matches"
        if len(candidates) == 0:
            outcome = "no_match"
        elif len(candidates) == 1:
            outcome = "single_match"
        return PlaceSearchResponse(
            outcome=outcome, candidates=candidates, more_results=result.more_results
        )

    @app.post("/api/route-requests", status_code=201, responses=ERRORS)
    def create_route_request(body: RouteRequestCreate, owner: OwnerHeader = None) -> RouteRequest:
        now = datetime.now(UTC)
        record = RouteRequestRecord(
            id=uuid.uuid4(),
            owner_id=owner or local_owner,
            activity=body.activity,
            start_retrieved_at=now,
            created_at=now,
        )
        if isinstance(body.start, MapStartChoice):
            record.start_source = "map_selection"
            record.start_lon, record.start_lat = body.start.point.coordinates
        else:
            # Search again so the stored place is what OneMap says, not what the browser sent.
            chosen = None
            for place in onemap.search(body.start.query).places:
                if place.source_id == body.start.source_id:
                    chosen = place
            if chosen is None:
                raise ApiError(
                    409, "candidate_not_found", "That place is not among the search results"
                )
            record.start_source = "onemap"
            record.start_source_id = chosen.source_id
            record.start_query = body.start.query
            record.start_name = chosen.name
            record.start_address = chosen.address
            record.start_postal = chosen.postal
            record.start_lon, record.start_lat = chosen.coordinates
        if not on_singapore_land(record.start_lon, record.start_lat):
            raise ApiError(422, "outside_singapore", "The start must be on Singapore land")
        with Session(engine) as session:
            session.add(record)
            session.commit()
            return to_route_request(record)

    @app.get("/api/route-requests/{route_request_id}", responses=ERRORS)
    def get_route_request(route_request_id: uuid.UUID, owner: OwnerHeader = None) -> RouteRequest:
        query = select(RouteRequestRecord).where(
            RouteRequestRecord.id == route_request_id,
            RouteRequestRecord.owner_id == (owner or local_owner),
        )
        with Session(engine) as session:
            record = session.scalars(query).first()
            if record is None:
                raise ApiError(404, "not_found", "No such route request")
            return to_route_request(record)

    return app


def app_from_env() -> FastAPI:
    """Entry point for uvicorn --factory. Reads DATABASE_URL, ONEMAP_API_TOKEN, LOCAL_OWNER_ID."""
    configure_logging()
    onemap = OneMap(httpx.Client(), token=os.environ.get("ONEMAP_API_TOKEN"))
    engine = create_engine(os.environ["DATABASE_URL"])
    return create_app(onemap, engine, local_owner=os.environ.get("LOCAL_OWNER_ID", "local-owner"))
