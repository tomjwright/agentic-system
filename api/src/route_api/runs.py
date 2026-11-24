"""Generation runs in the database, and their public views.

A run is saved as `generating` before HeiGIT is asked, then its candidates, the
selected route and its final status are saved together in one transaction. Generation
runs inside the HTTP request (at most MAX_ATTEMPTS provider calls); it is not a durable
background job, so a run whose request died is reported as interrupted.
"""

import uuid
from datetime import UTC, datetime, timedelta

from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from route_api.contracts import (
    AccessCheck,
    Activity,
    Distance,
    DistanceBoundsOut,
    ErrorDetail,
    GenerationRun,
    LineString,
    RestrictedRoad,
    RouteCandidate,
    SelectedRoute,
    SurfaceDistance,
)
from route_api.db import (
    GenerationRunRecord,
    RouteCandidateRecord,
    RouteRequestRecord,
    RouteRequestRevisionRecord,
    SelectedRouteRecord,
)
from route_api.generation import GENERATOR_VERSIONS, Generation
from route_api.geography import line_length_m
from route_api.heigit import PROFILES
from route_api.route_selection import DistanceBounds

INTERRUPTED_AFTER = timedelta(minutes=10)
DISTANCE = TypeAdapter(Distance)
LIMITATIONS = {
    "running": [
        "Distance is measured along the route shown, which is exactly what the GPX contains.",
        "The time is HeiGIT's foot-walking estimate, not a running time.",
        "Access restrictions, closures and safety are not checked yet. OpenStreetMap data can"
        " be out of date, so check the route before you go.",
    ],
    "road_cycling": [
        "Distance is measured along the route shown, which is exactly what the GPX contains.",
        "The time is HeiGIT's cycling-road estimate.",
        "The route is checked only against OpenStreetMap expressways, slip roads, road tunnels"
        " and bicycle=no ways. Access everywhere else is unknown, not verified.",
        "Surfaces are OpenStreetMap tags, not checked on the ground. Closures, traffic and"
        " safety are not checked, so check the route before you ride.",
    ],
}


def new_run(
    session: Session,
    owner: str,
    route_request_id: uuid.UUID,
    activity: Activity,
    restriction_data: str | None,
    operation_id: uuid.UUID,
    distance: Distance,
    bounds: DistanceBounds,
) -> GenerationRunRecord:
    """Add a new revision and a `generating` run for it. The caller commits."""
    count_query = select(func.count()).where(
        RouteRequestRevisionRecord.route_request_id == route_request_id,
        RouteRequestRevisionRecord.owner_id == owner,
    )
    now = datetime.now(UTC)
    revision = RouteRequestRevisionRecord(
        id=uuid.uuid4(),
        route_request_id=route_request_id,
        owner_id=owner,
        number=session.scalar(count_query) + 1,  # type: ignore[operator]
        distance=distance.model_dump(),
        min_m=bounds.min_m,
        max_m=bounds.max_m,
        target_m=bounds.target_m,
        created_at=now,
    )
    run = GenerationRunRecord(
        id=uuid.uuid4(),
        owner_id=owner,
        operation_id=operation_id,
        revision_id=revision.id,
        status="generating",
        provider="heigit",
        profile=PROFILES[activity],
        restriction_data=restriction_data,
        generator_version=GENERATOR_VERSIONS[activity],
        started_at=now,
    )
    session.add(revision)
    session.flush()
    session.add(run)
    return run


def save_generation(session: Session, run: GenerationRunRecord, generation: Generation) -> None:
    """Store every attempt, the chosen one and the run's outcome. The caller commits."""
    chosen_id = None
    for position, attempt in enumerate(generation.attempts):
        reasons = []
        if generation.selection is not None:
            reasons = generation.selection.reasons[position]
        accepted = generation.selection is not None and generation.selection.chosen == position
        candidate = RouteCandidateRecord(
            id=uuid.uuid4(),
            run_id=run.id,
            owner_id=run.owner_id,
            position=position,
            method=attempt.method,
            parameters=attempt.parameters,
            accepted=accepted,
            reasons=reasons,
        )
        route = attempt.route
        if route is not None:
            candidate.coordinates = [list(point) for point in route.coordinates]
            candidate.provider_distance_m = route.distance_m
            candidate.measured_distance_m = line_length_m(route.coordinates)
            candidate.duration_s = route.duration_s
            candidate.surfaces_m = route.surfaces_m
            candidate.engine = route.engine
            candidate.attribution = route.attribution[:300]
        if attempt.restricted_roads is not None:
            candidate.restricted_roads = [road.model_dump() for road in attempt.restricted_roads]
        session.add(candidate)
        if accepted:
            chosen_id = candidate.id
    session.flush()

    now = datetime.now(UTC)
    if generation.error_code is not None:
        run.status = "failed"
        run.error_code = generation.error_code
        run.error_message = generation.error_message
    elif chosen_id is None:
        run.status = "no_route"
    else:
        run.status = "succeeded"
        session.add(
            SelectedRouteRecord(
                run_id=run.id, candidate_id=chosen_id, owner_id=run.owner_id, selected_at=now
            )
        )
    run.finished_at = now


def find_run(session: Session, owner: str, run_id: uuid.UUID) -> GenerationRunRecord | None:
    query = select(GenerationRunRecord).where(
        GenerationRunRecord.id == run_id, GenerationRunRecord.owner_id == owner
    )
    return session.scalars(query).first()


def find_operation(
    session: Session, owner: str, operation_id: uuid.UUID
) -> GenerationRunRecord | None:
    query = select(GenerationRunRecord).where(
        GenerationRunRecord.operation_id == operation_id, GenerationRunRecord.owner_id == owner
    )
    return session.scalars(query).first()


def run_activity(session: Session, run: GenerationRunRecord) -> Activity:
    query = (
        select(RouteRequestRecord.activity)
        .join(
            RouteRequestRevisionRecord,
            RouteRequestRevisionRecord.route_request_id == RouteRequestRecord.id,
        )
        .where(
            RouteRequestRevisionRecord.id == run.revision_id,
            RouteRequestRecord.owner_id == run.owner_id,
        )
    )
    activity: Activity = session.scalars(query).one()  # type: ignore[assignment]
    return activity


def find_revision(session: Session, run: GenerationRunRecord) -> RouteRequestRevisionRecord:
    query = select(RouteRequestRevisionRecord).where(
        RouteRequestRevisionRecord.id == run.revision_id,
        RouteRequestRevisionRecord.owner_id == run.owner_id,
    )
    return session.scalars(query).one()


def to_generation_run(session: Session, run: GenerationRunRecord) -> GenerationRun:
    revision = find_revision(session, run)
    query = (
        select(RouteCandidateRecord)
        .where(RouteCandidateRecord.run_id == run.id, RouteCandidateRecord.owner_id == run.owner_id)
        .order_by(RouteCandidateRecord.position)
    )
    candidates = []
    for record in session.scalars(query):
        candidates.append(
            RouteCandidate(
                position=record.position,
                method=record.method,  # type: ignore[arg-type]
                seed=record.parameters.get("seed"),
                requested_length_m=record.parameters["length_m"],
                measured_distance_m=record.measured_distance_m,
                accepted=record.accepted,
                reasons=record.reasons,
            )
        )
    status = run.status
    error = None
    if run.error_code is not None:
        error = ErrorDetail(code=run.error_code, message=run.error_message or "")  # type: ignore[arg-type]
    if status == "generating" and datetime.now(UTC) - run.started_at > INTERRUPTED_AFTER:
        status = "failed"
        error = ErrorDetail(
            code="generation_interrupted", message="Generation stopped before it finished"
        )
    return GenerationRun(
        id=run.id,
        route_request_id=revision.route_request_id,
        revision=revision.number,
        distance=DISTANCE.validate_python(revision.distance),
        bounds=DistanceBoundsOut(min_m=revision.min_m, max_m=revision.max_m),
        status=status,  # type: ignore[arg-type]
        error=error,
        candidates=candidates,
        profile=run.profile,
        generator_version=run.generator_version,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def find_selected(
    session: Session, run: GenerationRunRecord
) -> tuple[SelectedRouteRecord, RouteCandidateRecord] | None:
    query = (
        select(SelectedRouteRecord, RouteCandidateRecord)
        .join(RouteCandidateRecord, RouteCandidateRecord.id == SelectedRouteRecord.candidate_id)
        .where(
            SelectedRouteRecord.run_id == run.id,
            SelectedRouteRecord.owner_id == run.owner_id,
            RouteCandidateRecord.owner_id == run.owner_id,
        )
    )
    row = session.execute(query).first()
    if row is None:
        return None
    return row[0], row[1]


def to_selected_route(
    session: Session,
    run: GenerationRunRecord,
    selected: SelectedRouteRecord,
    candidate: RouteCandidateRecord,
) -> SelectedRoute:
    revision = find_revision(session, run)
    activity = run_activity(session, run)
    distance_m = candidate.measured_distance_m or 0.0
    surfaces = []
    unknown_m = 0.0
    for surface, metres in (candidate.surfaces_m or {}).items():
        surfaces.append(SurfaceDistance(surface=surface, distance_m=metres))
        if surface == "unknown":
            unknown_m += metres
    surfaced_m = sum(surface.distance_m for surface in surfaces)
    unknown_share = 1.0
    if surfaced_m > 0:
        unknown_share = unknown_m / surfaced_m
    limitations = list(LIMITATIONS[activity])
    access = AccessCheck(status="not_checked", source=None, roads=[])
    if candidate.restricted_roads is not None:
        roads = [RestrictedRoad.model_validate(road) for road in candidate.restricted_roads]
        access = AccessCheck(
            status="no_prohibited_road_found", source=run.restriction_data, roads=roads
        )
        trunk_m = 0.0
        trunk_names = []
        tunnel_names = []
        for road in roads:
            if road.outcome != "on_disclosed_road":
                continue
            if road.kind == "minor road tunnel":
                tunnel_names.append(road.name)
            else:
                trunk_m += road.on_m
                trunk_names.append(road.name)
        if tunnel_names:
            limitations.insert(
                3,
                f"It goes through tunnels on minor roads ({', '.join(tunnel_names)})."
                " OpenStreetMap records no cycling ban there; follow any signs at the entrance.",
            )
        if trunk_names:
            trunk_length = f"{trunk_m / 1000:.1f} km"
            if trunk_m < 1000:
                trunk_length = f"{round(trunk_m)} m"
            limitations.insert(
                3,
                f"It rides {trunk_length} on trunk roads ({', '.join(trunk_names)})."
                " Bicycles are allowed there, but traffic is heavy.",
            )
    if unknown_share > 0:
        limitations.insert(
            2,
            f"OpenStreetMap has no surface for {unknown_share:.0%} of this route, so its"
            " surface is unknown there.",
        )
    engine = candidate.engine or {}
    return SelectedRoute(
        run_id=run.id,
        geometry=LineString(coordinates=[(lon, lat) for lon, lat in candidate.coordinates or []]),
        distance_m=distance_m,
        target_m=revision.target_m,
        deviation_m=distance_m - revision.target_m,
        bounds=DistanceBoundsOut(min_m=revision.min_m, max_m=revision.max_m),
        activity=activity,
        profile=run.profile,
        duration_s=candidate.duration_s or 0.0,
        surfaces=surfaces,
        unknown_surface_share=unknown_share,
        access=access,
        limitations=limitations,
        attribution=candidate.attribution or "",
        provider_engine=f"openrouteservice {engine.get('version', 'unknown')}"
        f" (graph {engine.get('graph_date', 'unknown')})",
        selected_at=selected.selected_at,
    )
