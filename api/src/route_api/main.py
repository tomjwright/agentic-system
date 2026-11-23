"""The HTTP API: place search, start confirmation, owner-scoped route requests, and
generating, inspecting and exporting a running loop.

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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from route_api.contracts import (
    Candidate,
    ConfirmedStart,
    ErrorResponse,
    GenerationRun,
    MapStartChoice,
    PlaceSearchRequest,
    PlaceSearchResponse,
    Point,
    RouteRequest,
    RouteRequestCreate,
    RunCreate,
    SearchOutcome,
    SelectedRoute,
)
from route_api.db import GenerationRunRecord, RouteRequestRecord
from route_api.generation import generate
from route_api.geography import on_singapore_land
from route_api.gpx import route_to_gpx
from route_api.heigit import Heigit
from route_api.logs import configure_logging, log_event
from route_api.onemap import OneMap, ProviderError
from route_api.route_selection import distance_bounds
from route_api.runs import (
    find_operation,
    find_run,
    find_selected,
    new_run,
    save_generation,
    to_generation_run,
    to_selected_route,
)
from route_api.telemetry import setup_tracing, tracer

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


def find_route_request(
    session: Session, owner: str, route_request_id: uuid.UUID
) -> RouteRequestRecord:
    query = select(RouteRequestRecord).where(
        RouteRequestRecord.id == route_request_id, RouteRequestRecord.owner_id == owner
    )
    record = session.scalars(query).first()
    if record is None:
        raise ApiError(404, "not_found", "No such route request")
    return record


def owned_run(session: Session, owner: str, run_id: uuid.UUID) -> GenerationRunRecord:
    run = find_run(session, owner, run_id)
    if run is None:
        raise ApiError(404, "not_found", "No such run")
    return run


def create_app(onemap: OneMap, engine: Engine, local_owner: str, heigit: Heigit) -> FastAPI:
    app = FastAPI(title="Singapore route creator API", version="0.1.0")

    @app.middleware("http")
    async def log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", "")
        if not re.match(ID_PATTERN, request_id):
            request_id = uuid.uuid4().hex
        request.state.request_id = request_id
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
        log_event(
            "provider_error",
            request_id=request.state.request_id,
            provider="onemap",
            code=error.code,
        )
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
        with Session(engine) as session:
            record = find_route_request(session, owner or local_owner, route_request_id)
            return to_route_request(record)

    @app.post("/api/route-requests/{route_request_id}/runs", status_code=201, responses=ERRORS)
    def start_run(
        route_request_id: uuid.UUID,
        body: RunCreate,
        request: Request,
        response: Response,
        owner: OwnerHeader = None,
    ) -> GenerationRun:
        """Generate a loop now and return the finished run.

        Retrying with the same operation_id returns the run already recorded (HTTP 200),
        even while it is still generating; a different distance is refused.
        """
        owner = owner or local_owner
        bounds = distance_bounds(body.distance)
        with Session(engine) as session:
            route_request = find_route_request(session, owner, route_request_id)
            existing = find_operation(session, owner, body.operation_id)
            if existing is not None:
                response.status_code = 200
                return same_operation(session, existing, route_request_id, body)
            if route_request.activity != "running":
                raise ApiError(
                    422, "activity_not_supported", "Only running loops can be generated so far"
                )
            if not heigit.configured:
                raise ApiError(503, "provider_not_configured", "Route generation is not configured")
            start = (route_request.start_lon, route_request.start_lat)
            try:
                run = new_run(
                    session, owner, route_request_id, body.operation_id, body.distance, bounds
                )
                with tracer.start_as_current_span("db.save_run"):
                    session.commit()
            except IntegrityError:
                # The same operation arrived twice at once; the other request recorded it.
                session.rollback()
                existing = find_operation(session, owner, body.operation_id)
                if existing is None:
                    raise
                response.status_code = 200
                return same_operation(session, existing, route_request_id, body)

            started = time.monotonic()
            with tracer.start_as_current_span("generate_route") as span:
                generation = generate(heigit, start, bounds)
                span.set_attribute("route.attempts", len(generation.attempts))
            with tracer.start_as_current_span("db.save_generation"):
                save_generation(session, run, generation)
                session.commit()
            chosen = None
            if generation.selection is not None:
                chosen = generation.selection.chosen
            log_event(
                "generation_finished",
                request_id=request.state.request_id,
                run_id=str(run.id),
                status=run.status,
                error_code=run.error_code or "",
                attempts=len(generation.attempts),
                chosen=-1 if chosen is None else chosen,
                duration_ms=round((time.monotonic() - started) * 1000),
            )
            return to_generation_run(session, run)

    def same_operation(
        session: Session, run: GenerationRunRecord, route_request_id: uuid.UUID, body: RunCreate
    ) -> GenerationRun:
        found = to_generation_run(session, run)
        same_request = found.route_request_id == route_request_id
        if not same_request or found.distance != body.distance:
            raise ApiError(
                409, "operation_conflict", "That operation_id was already used for another run"
            )
        return found

    @app.get("/api/runs/{run_id}", responses=ERRORS)
    def get_run(run_id: uuid.UUID, owner: OwnerHeader = None) -> GenerationRun:
        with Session(engine) as session:
            return to_generation_run(session, owned_run(session, owner or local_owner, run_id))

    @app.get("/api/runs/{run_id}/route", responses=ERRORS)
    def get_selected_route(run_id: uuid.UUID, owner: OwnerHeader = None) -> SelectedRoute:
        with Session(engine) as session:
            run = owned_run(session, owner or local_owner, run_id)
            selected = find_selected(session, run)
            if selected is None:
                raise ApiError(409, "no_route_selected", "This run has no selected route")
            return to_selected_route(session, run, selected[0], selected[1])

    @app.get(
        "/api/runs/{run_id}/route.gpx",
        responses={**ERRORS, 200: {"content": {"application/gpx+xml": {}}}},
        response_class=Response,
    )
    def export_gpx(run_id: uuid.UUID, owner: OwnerHeader = None) -> Response:
        with Session(engine) as session:
            run = owned_run(session, owner or local_owner, run_id)
            selected = find_selected(session, run)
            if selected is None:
                raise ApiError(409, "no_route_selected", "This run has no selected route")
            candidate = selected[1]
            distance_km = (candidate.measured_distance_m or 0) / 1000
            gpx = route_to_gpx(
                f"Running loop {distance_km:.2f} km",
                candidate.coordinates or [],
                candidate.attribution or "",
            )
        filename = f"running-loop-{run_id}.gpx"
        return Response(
            content=gpx,
            media_type="application/gpx+xml",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return app


def app_from_env() -> FastAPI:
    """Entry point for uvicorn --factory.

    Reads DATABASE_URL, ONEMAP_API_TOKEN, HEIGIT_API_KEY, LOCAL_OWNER_ID and, optionally,
    OTEL_EXPORTER_OTLP_ENDPOINT.
    """
    configure_logging()
    setup_tracing()
    onemap = OneMap(httpx.Client(), token=os.environ.get("ONEMAP_API_TOKEN"))
    heigit = Heigit(httpx.Client(), api_key=os.environ.get("HEIGIT_API_KEY"))
    engine = create_engine(os.environ["DATABASE_URL"])
    local_owner = os.environ.get("LOCAL_OWNER_ID", "local-owner")
    return create_app(onemap, engine, local_owner=local_owner, heigit=heigit)
