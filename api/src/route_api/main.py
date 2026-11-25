"""The HTTP API: GitHub sign-in, place search, start confirmation, owner-scoped route
requests, and generating, inspecting and exporting a loop.

Every endpoint except health, readiness and the sign-in redirects needs a signed-in owner
(route_api.auth). There is no CORS: the page reaches the API through its own origin.
"""

import os
import re
import secrets
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import httpx
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import Cookie, Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from route_api.agent import run_agent
from route_api.agent_models import AgentResult, RunRequest, RunStart
from route_api.agent_runs import (
    answer_steps,
    fail_agent_run,
    find_agent_run,
    finish_agent_run,
    new_agent_run,
    to_agent_run,
)
from route_api.auth import (
    LOGIN_COOKIE,
    LOGIN_SECONDS,
    SAFE_METHODS,
    SESSION_COOKIE,
    SESSION_DAYS,
    Auth,
    AuthError,
    auth_from_env,
    create_session,
    end_session,
)
from route_api.contracts import (
    AgentAnswer,
    AgentRun,
    AgentRunCreate,
    AgentRunWithoutStartCreate,
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
    SignedIn,
    StartChoices,
)
from route_api.db import AgentRunRecord, GenerationRunRecord, RouteRequestRecord
from route_api.generation import generate
from route_api.geography import on_singapore_land
from route_api.gpx import route_to_gpx
from route_api.heigit import Heigit
from route_api.llm import Models, models_from_env
from route_api.logs import configure_logging, log_event
from route_api.migrate import known_revisions
from route_api.onemap import OneMap, Place, ProviderError
from route_api.restrictions import RestrictedWays, load_restricted_ways
from route_api.retention import purge_expired
from route_api.route_selection import DISTANCE_LIMITS_KM, distance_bounds, outside_activity_limits
from route_api.runs import (
    find_operation,
    find_run,
    find_selected,
    new_run,
    run_activity,
    save_generation,
    to_generation_run,
    to_selected_route,
)
from route_api.telemetry import setup_tracing, tracer

ID_PATTERN = r"^[A-Za-z0-9._-]{1,64}$"
ACTIVITY_NAMES = {"running": "running", "road_cycling": "road cycling"}
MAX_BODY_BYTES = 8192
MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


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


def migration_head() -> str | None:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    return ScriptDirectory.from_config(config).get_current_head()


def to_candidate(place: Place) -> Candidate:
    return Candidate(
        source_id=place.source_id,
        name=place.name,
        address=place.address,
        postal=place.postal,
        point=Point(coordinates=place.coordinates),
    )


def to_start_choices(result: AgentResult) -> StartChoices | None:
    found = result.start_search
    if found is None:
        return None
    candidates = [to_candidate(place) for place in found.matches]
    return StartChoices(query=found.query, activity=found.activity, candidates=candidates)


def create_app(
    onemap: OneMap,
    engine: Engine,
    auth: Auth,
    heigit: Heigit,
    restricted_ways: RestrictedWays,
    models: Models | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Singapore route creator API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.engine = engine
    head = migration_head()
    revisions = known_revisions()

    def current_owner(request: Request) -> str:
        owner_id, _ = auth.owner(request)
        return owner_id

    Owner = Annotated[str, Depends(current_owner)]

    @app.middleware("http")
    async def log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", "")
        if not re.match(ID_PATTERN, request_id):
            request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.monotonic()
        length = request.headers.get("Content-Length", "0")
        if request.method in SAFE_METHODS:
            response = await call_next(request)
        elif "Transfer-Encoding" in request.headers or not length.isdigit():
            response = error_response(411, "length_required", "Send a Content-Length")
        elif int(length) > MAX_BODY_BYTES:
            response = error_response(413, "payload_too_large", "The request body is too large")
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
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

    @app.exception_handler(AuthError)
    async def auth_error(request: Request, error: AuthError) -> JSONResponse:
        if error.status in (401, 403, 429):
            log_event("auth_refused", request_id=request.state.request_id, code=error.code)
        return error_response(error.status, error.code, str(error))

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """The process is up. Says nothing about the database or providers."""
        return {"status": "ok"}

    @app.get("/api/ready", responses={503: {}})
    def ready() -> JSONResponse:
        """Ready for traffic: database reachable, migrations current, providers configured."""
        missing = []
        if not onemap.token:
            missing.append("ONEMAP_API_TOKEN")
        if not heigit.configured:
            missing.append("HEIGIT_API_KEY")
        if not auth.github.configured:
            missing.append("GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET")
        database = "ok"
        migrations = "behind"
        try:
            with engine.connect() as connection:
                applied = connection.execute(text("SELECT version_num FROM alembic_version"))
                revision = applied.scalar()
                if revision == head:
                    migrations = "current"
                elif revision is not None and revision not in revisions:
                    # A newer release migrated further and this one is serving again after a
                    # rollback; migrations only add, so this release still works on it.
                    migrations = "ahead"
        except Exception:  # any database failure means not ready
            database = "unavailable"
        body: dict[str, Any] = {"status": "ready", "database": database, "migrations": migrations}
        if missing or database != "ok" or migrations == "behind":
            body["status"] = "not_ready"
            body["missing"] = missing
            return JSONResponse(body, status_code=503)
        return JSONResponse(body)

    @app.get("/api/auth/login", status_code=302, response_class=RedirectResponse)
    def login() -> RedirectResponse:
        """Send the browser to GitHub with a fresh state and PKCE verifier."""
        if not auth.github.configured:
            raise AuthError(503, "sign_in_not_configured", "Sign-in is not configured")
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        response = RedirectResponse(auth.github.login_url(state, verifier), status_code=302)
        response.set_cookie(
            LOGIN_COOKIE,
            f"{state}.{verifier}",
            max_age=LOGIN_SECONDS,
            path="/",
            secure=True,
            httponly=True,
            samesite="lax",
        )
        return response

    @app.get("/api/auth/callback", status_code=302, response_class=RedirectResponse)
    def callback(
        code: str = "",
        state: str = "",
        started: Annotated[str, Cookie(alias=LOGIN_COOKIE)] = "",
    ) -> RedirectResponse:
        """GitHub sends the browser back here; an allowlisted account gets a session."""
        expected_state, _, verifier = started.partition(".")
        if not expected_state or not secrets.compare_digest(state, expected_state):
            raise AuthError(400, "invalid_state", "Sign-in expired or was not started here")
        user_id = auth.github.allowed_user_id(code, verifier)
        token, _ = create_session(engine, f"github:{user_id}")
        log_event("signed_in", github_id=user_id)
        response = RedirectResponse("/", status_code=302)
        response.delete_cookie(LOGIN_COOKIE, path="/", secure=True, httponly=True)
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=SESSION_DAYS * 24 * 3600,
            path="/",
            secure=True,
            httponly=True,
            samesite="lax",
        )
        return response

    @app.get("/api/auth/me", responses=ERRORS)
    def me(request: Request) -> SignedIn:
        """Who is signed in, and the CSRF token to send with every change."""
        owner_id, csrf = auth.owner(request)
        return SignedIn(owner_id=owner_id, csrf_token=csrf)

    @app.post("/api/auth/logout", status_code=204, responses=ERRORS, response_class=Response)
    def logout(request: Request, owner: Owner) -> Response:
        end_session(engine, request.cookies.get(SESSION_COOKIE, ""))
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True)
        return response

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
    def search_places(body: PlaceSearchRequest, owner: Owner) -> PlaceSearchResponse:
        result = onemap.search(body.query)
        candidates = []
        for place in result.places:
            if not on_singapore_land(*place.coordinates):
                continue
            candidates.append(to_candidate(place))
        outcome: SearchOutcome = "multiple_matches"
        if len(candidates) == 0:
            outcome = "no_match"
        elif len(candidates) == 1:
            outcome = "single_match"
        return PlaceSearchResponse(
            outcome=outcome, candidates=candidates, more_results=result.more_results
        )

    @app.post("/api/route-requests", status_code=201, responses=ERRORS)
    def create_route_request(body: RouteRequestCreate, owner: Owner) -> RouteRequest:
        now = datetime.now(UTC)
        record = RouteRequestRecord(
            id=uuid.uuid4(),
            owner_id=owner,
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
    def get_route_request(route_request_id: uuid.UUID, owner: Owner) -> RouteRequest:
        with Session(engine) as session:
            record = find_route_request(session, owner, route_request_id)
            return to_route_request(record)

    @app.post(
        "/api/route-requests/{route_request_id}/runs",
        status_code=201,
        responses={
            **ERRORS,
            200: {
                "model": GenerationRun,
                "description": "The run already recorded for this operation",
            },
        },
    )
    def start_run(
        route_request_id: uuid.UUID,
        body: RunCreate,
        request: Request,
        response: Response,
        owner: Owner,
    ) -> GenerationRun:
        """Generate a loop now and return the finished run.

        Retrying with the same operation_id returns the run already recorded (HTTP 200),
        even while it is still generating; a different distance is refused.
        """
        bounds = distance_bounds(body.distance)
        with Session(engine) as session:
            route_request = find_route_request(session, owner, route_request_id)
            existing = find_operation(session, owner, body.operation_id)
            if existing is not None:
                response.status_code = 200
                return same_operation(session, existing, route_request_id, body)
            activity = route_request.activity
            if outside_activity_limits(activity, body.distance):
                lowest_km, highest_km = DISTANCE_LIMITS_KM[activity]
                raise ApiError(
                    422,
                    "invalid_request",
                    f"distance: {ACTIVITY_NAMES[activity]} loops are {lowest_km} to"
                    f" {highest_km} km",
                )
            auth.check_run_budget(session, owner)
            if not heigit.configured:
                raise ApiError(503, "provider_not_configured", "Route generation is not configured")
            start = (route_request.start_lon, route_request.start_lat)
            restriction_data = None
            if activity == "road_cycling":
                restriction_data = restricted_ways.source
            try:
                run = new_run(
                    session,
                    owner,
                    route_request_id,
                    activity,  # type: ignore[arg-type]
                    restriction_data,
                    body.operation_id,
                    body.distance,
                    bounds,
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
                generation = generate(heigit, activity, start, bounds, restricted_ways)
                span.set_attribute("route.activity", activity)
                span.set_attribute("route.attempts", len(generation.attempts))
                span.set_attribute("route.error_code", generation.error_code or "none")
            with tracer.start_as_current_span("db.save_generation"):
                save_generation(session, run, generation)
                session.commit()
            chosen = None
            if generation.selection is not None:
                chosen = generation.selection.chosen
            prohibited = 0
            for attempt in generation.attempts:
                for road in attempt.restricted_roads or []:
                    if road.outcome == "on_prohibited_road":
                        prohibited += 1
            log_event(
                "generation_finished",
                request_id=request.state.request_id,
                run_id=str(run.id),
                activity=activity,
                profile=run.profile,
                status=run.status,
                error_code=run.error_code or "",
                attempts=len(generation.attempts),
                chosen=-1 if chosen is None else chosen,
                prohibited_roads=prohibited,
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

    @app.post(
        "/api/route-requests/{route_request_id}/agent-runs", status_code=201, responses=ERRORS
    )
    def start_agent_run(
        route_request_id: uuid.UUID, body: AgentRunCreate, request: Request, owner: Owner
    ) -> AgentAnswer:
        """Ask the route agent for a loop from the confirmed start. Every answer it gives
        was approved by the judge or written by code from measured facts."""
        with Session(engine) as session:
            route_request = find_route_request(session, owner, route_request_id)
            if models is None:
                raise ApiError(503, "agent_not_configured", "The route assistant is not configured")
            if not heigit.configured:
                raise ApiError(503, "provider_not_configured", "Route generation is not configured")
            auth.check_run_budget(session, owner)
            start = RunStart(
                name=route_request.start_name,
                coordinates=(route_request.start_lon, route_request.start_lat),
            )
            run = new_agent_run(session, owner, route_request_id, models)
            session.commit()
            agent_request = RunRequest(
                run_id=run.id,
                brief=body.brief,
                activity=route_request.activity,  # type: ignore[arg-type]
                distance=body.distance,
                start=start,
            )
            return answer_agent_run(session, request, owner, run, agent_request)

    @app.post("/api/agent-runs", status_code=201, responses=ERRORS)
    def start_agent_run_without_start(
        body: AgentRunWithoutStartCreate, request: Request, owner: Owner
    ) -> AgentAnswer:
        """Ask the route agent before a start is confirmed. It searches OneMap for the start
        the message names and lists every match in start_choices; it never makes a route."""
        with Session(engine) as session:
            if models is None:
                raise ApiError(503, "agent_not_configured", "The route assistant is not configured")
            auth.check_run_budget(session, owner)
            run = new_agent_run(session, owner, None, models)
            session.commit()
            agent_request = RunRequest(
                run_id=run.id,
                brief=body.brief,
                activity=body.activity,
                distance=body.distance,
                start=None,
            )
            return answer_agent_run(session, request, owner, run, agent_request)

    def answer_agent_run(
        session: Session,
        request: Request,
        owner: str,
        run: AgentRunRecord,
        agent_request: RunRequest,
    ) -> AgentAnswer:
        """Run the agent, then save its route (if it made one) and how the answer was made."""
        assert models is not None
        started = time.monotonic()
        try:
            result = run_agent(
                agent_request, models.agent, models.judge, onemap, heigit, restricted_ways
            )
            if result.generation is not None and result.facts is not None:
                assert run.route_request_id is not None
                restriction_data = None
                if result.facts.activity == "road_cycling":
                    restriction_data = restricted_ways.source
                auth.lock_owner(session, owner)
                generation_run = new_run(
                    session,
                    owner,
                    run.route_request_id,
                    result.facts.activity,
                    restriction_data,
                    run.id,
                    result.facts.requested,
                    distance_bounds(result.facts.requested),
                )
                save_generation(session, generation_run, result.generation)
                run.generation_run_id = generation_run.id
            finish_agent_run(run, result)
            session.commit()
        except Exception as error:
            session.rollback()
            fail_agent_run(run)
            session.commit()
            log_event(
                "agent_failed",
                request_id=request.state.request_id,
                agent_run_id=str(run.id),
                error=type(error).__name__,
            )
            message = "The route assistant failed; try again"
            raise ApiError(500, "agent_failed", message) from None
        log_event(
            "agent_finished",
            request_id=request.state.request_id,
            agent_run_id=str(run.id),
            kind=result.kind,
            message_source=result.message_source,
            fallback_reason=result.fallback_reason or "",
            repairs=result.repairs,
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return AgentAnswer(
            run=to_agent_run(run),
            message=result.message,
            steps=answer_steps(result),
            start_choices=to_start_choices(result),
        )

    @app.get("/api/agent-runs/{agent_run_id}", responses=ERRORS)
    def get_agent_run(agent_run_id: uuid.UUID, owner: Owner) -> AgentRun:
        with Session(engine) as session:
            run = find_agent_run(session, owner, agent_run_id)
            if run is None:
                raise ApiError(404, "not_found", "No such agent run")
            return to_agent_run(run)

    @app.get("/api/runs/{run_id}", responses=ERRORS)
    def get_run(run_id: uuid.UUID, owner: Owner) -> GenerationRun:
        with Session(engine) as session:
            return to_generation_run(session, owned_run(session, owner, run_id))

    @app.get("/api/runs/{run_id}/route", responses=ERRORS)
    def get_selected_route(run_id: uuid.UUID, owner: Owner) -> SelectedRoute:
        with Session(engine) as session:
            run = owned_run(session, owner, run_id)
            selected = find_selected(session, run)
            if selected is None:
                raise ApiError(409, "no_route_selected", "This run has no selected route")
            return to_selected_route(session, run, selected[0], selected[1])

    @app.get(
        "/api/runs/{run_id}/route.gpx",
        responses={**ERRORS, 200: {"content": {"application/gpx+xml": {}}}},
        response_class=Response,
    )
    def export_gpx(run_id: uuid.UUID, owner: Owner) -> Response:
        with Session(engine) as session:
            run = owned_run(session, owner, run_id)
            selected = find_selected(session, run)
            if selected is None:
                raise ApiError(409, "no_route_selected", "This run has no selected route")
            candidate = selected[1]
            activity = run_activity(session, run)
            distance_km = (candidate.measured_distance_m or 0) / 1000
            gpx = route_to_gpx(
                f"{ACTIVITY_NAMES[activity].capitalize()} loop {distance_km:.2f} km",
                candidate.coordinates or [],
                candidate.attribution or "",
            )
        filename = f"{ACTIVITY_NAMES[activity].replace(' ', '-')}-loop-{run_id}.gpx"
        return Response(
            content=gpx,
            media_type="application/gpx+xml",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return app


def app_from_env() -> FastAPI:
    """Entry point for uvicorn --factory.

    Reads DATABASE_URL, ONEMAP_API_TOKEN, HEIGIT_API_KEY, the sign-in settings in
    route_api.auth and, optionally, OTEL_EXPORTER_OTLP_ENDPOINT.
    """
    configure_logging()
    setup_tracing()
    onemap = OneMap(httpx.Client(), token=os.environ.get("ONEMAP_API_TOKEN"))
    heigit = Heigit(httpx.Client(), api_key=os.environ.get("HEIGIT_API_KEY"))
    # Neon suspends idle computes; pre-ping replaces connections it closed.
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    purge_expired(engine, datetime.now(UTC))
    return create_app(
        onemap,
        engine,
        auth_from_env(engine),
        heigit=heigit,
        restricted_ways=load_restricted_ways(),
        models=models_from_env(),
    )
