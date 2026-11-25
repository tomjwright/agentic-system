"""Seam 1: the route agent over HTTP, with fake agent and judge models.

HeiGIT and OneMap replay recorded real responses and the database is real; no test calls
an LLM or a live provider.
"""

import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from route_api.agent_models import Interpretation, Verdict
from route_api.contracts import DistanceTarget
from route_api.db import GenerationRunRecord
from route_api.llm import Models
from route_api.retention import ROUTE_REQUEST_DAYS, purge_expired
from route_api.runs import save_generation
from tests.conftest import SOMEONE, TOM, api_with, as_owner
from tests.fake_models import FakeModel
from tests.recorded_heigit import FIXTURES
from tests.recorded_onemap import recorded_response as recorded_onemap
from tests.test_runs import AVENUE_SOUTH_BLOCK_11, GPX, CountingHeigit, confirm_start

RUN_5K = Interpretation(activity="running", distance=DistanceTarget(kind="target", target_km=5))
APPROVED = Verdict(approved=True, reasons=[])
REJECTED = Verdict(approved=False, reasons=["it says 7 km; the route is 5.26 km"])
GOOD_DRAFT = "Here is a 5.26 km running loop from your start."
BAD_DRAFT = "Here is a 7 km running loop, fully shaded and safe."
AGENT_MODEL = "anthropic:claude-haiku-4-5"
JUDGE_MODEL = "google_genai:gemini-3.5-flash"


def step(
    name: str, tries: int | None = None, approved: bool | None = None, reason: str | None = None
) -> dict[str, Any]:
    return {"name": name, "tries": tries, "approved": approved, "reason": reason}


def fake_models(agent_replies: list[Any], judge_replies: list[Any]) -> Models:
    return Models(
        agent=FakeModel(replies=agent_replies),
        judge=FakeModel(replies=judge_replies),
        agent_name=AGENT_MODEL,
        judge_name=JUDGE_MODEL,
    )


def agent_api(
    engine: Engine,
    models: Models | None,
    heigit: CountingHeigit | None = None,
    runs_per_day: int = 1000,
) -> TestClient:
    return api_with(
        engine,
        httpx.MockTransport(recorded_onemap),
        "fake-onemap-token",
        heigit_handler=heigit or CountingHeigit(),
        models=models,
        runs_per_day=runs_per_day,
    )


def ask(
    api: TestClient, request_id: str, brief: str = "a 5k run", owner: str = TOM
) -> httpx2.Response:
    response: httpx2.Response = api.post(
        f"/api/route-requests/{request_id}/agent-runs",
        json={"brief": brief},
        headers=as_owner(api, owner),
    )
    return response


def test_an_approved_answer_comes_with_the_stored_route(clean_engine: Engine) -> None:
    api = agent_api(clean_engine, fake_models([RUN_5K, GOOD_DRAFT], [APPROVED]))
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    response = ask(api, request_id)

    assert response.status_code == 201
    answer = response.json()
    assert answer["message"] == GOOD_DRAFT
    run = answer["run"]
    assert run["route_request_id"] == request_id
    assert run["status"] == "finished"
    assert run["kind"] == "route"
    assert run["message_source"] == "approved_draft"
    assert run["fallback_reason"] is None
    assert run["approvals"] == [True]
    assert run["repairs"] == 0
    assert (run["agent_model"], run["judge_model"]) == (AGENT_MODEL, JUDGE_MODEL)
    assert answer["steps"] == [
        step("read_request"),
        step("generated_route", tries=2),
        step("drafted"),
        step("judged", approved=True),
    ]
    generation_run = api.get(f"/api/runs/{run['generation_run_id']}", headers=as_owner(api, TOM))
    assert generation_run.json()["status"] == "succeeded"
    assert generation_run.json()["distance"] == {"kind": "target", "target_km": 5.0}
    route = api.get(f"/api/runs/{run['generation_run_id']}/route", headers=as_owner(api, TOM))
    recorded = json.loads((FIXTURES / "heigit_avenue_south_5km_1.json").read_text())
    assert (
        route.json()["geometry"]["coordinates"]
        == recorded["features"][0]["geometry"]["coordinates"]
    )
    gpx = api.get(f"/api/runs/{run['generation_run_id']}/route.gpx", headers=as_owner(api, TOM))
    points = []
    for point in ET.fromstring(gpx.text).iter(f"{GPX}trkpt"):  # noqa: S314 (our own GPX)
        points.append([float(point.attrib["lon"]), float(point.attrib["lat"])])
    assert points == recorded["features"][0]["geometry"]["coordinates"]


def test_a_missing_distance_is_asked_about_without_a_route(clean_engine: Engine) -> None:
    heigit = CountingHeigit()
    question = "How far would you like to run?"
    models = fake_models([Interpretation(activity="running"), question], [APPROVED])
    api = agent_api(clean_engine, models, heigit)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    response = ask(api, request_id, brief="a run please")

    assert response.status_code == 201
    assert response.json()["message"] == question
    run = response.json()["run"]
    assert (run["kind"], run["message_source"], run["generation_run_id"]) == (
        "clarification",
        "approved_draft",
        None,
    )
    assert response.json()["steps"] == [
        step("read_request"),
        step("asked_clarification", reason="missing_distance"),
        step("drafted"),
        step("judged", approved=True),
    ]
    assert heigit.requests == []


def test_two_rejections_answer_with_the_factual_fallback(clean_engine: Engine) -> None:
    models = fake_models([RUN_5K, BAD_DRAFT, BAD_DRAFT], [REJECTED, REJECTED])
    api = agent_api(clean_engine, models)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    response = ask(api, request_id)

    answer = response.json()
    assert BAD_DRAFT not in answer["message"]
    assert "5.26 km" in answer["message"]
    run = answer["run"]
    assert (run["kind"], run["message_source"], run["fallback_reason"]) == (
        "route",
        "fallback",
        "rejected_twice",
    )
    assert (run["approvals"], run["repairs"]) == ([False, False], 1)
    assert run["generation_run_id"] is not None
    assert answer["steps"] == [
        step("read_request"),
        step("generated_route", tries=2),
        step("drafted"),
        step("judged", approved=False),
        step("repaired"),
        step("judged", approved=False),
        step("fallback", reason="rejected_twice"),
    ]
    with clean_engine.connect() as connection:
        stored = connection.execute(text("SELECT verdicts FROM agent_runs")).scalar_one()
    assert stored == [REJECTED.model_dump(), REJECTED.model_dump()]


@pytest.mark.parametrize(
    ("agent_replies", "judge_replies", "last_steps"),
    [
        (
            [TimeoutError()],
            [],
            [step("read_request"), step("fallback", reason="interpretation_unavailable")],
        ),
        (
            [RUN_5K, GOOD_DRAFT],
            [TimeoutError()],
            [step("drafted"), step("fallback", reason="judge_unavailable")],
        ),
        (
            [RUN_5K, BAD_DRAFT, GOOD_DRAFT],
            [REJECTED, TimeoutError()],
            [step("repaired"), step("fallback", reason="judge_unavailable")],
        ),
        (
            [RUN_5K, BAD_DRAFT, TimeoutError()],
            [REJECTED],
            [step("judged", approved=False), step("fallback", reason="draft_unavailable")],
        ),
    ],
)
def test_the_steps_end_where_the_run_fell_back(
    clean_engine: Engine,
    agent_replies: list[Any],
    judge_replies: list[Any],
    last_steps: list[dict[str, Any]],
) -> None:
    api = agent_api(clean_engine, fake_models(agent_replies, judge_replies))
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    steps = ask(api, request_id).json()["steps"]

    assert steps[0] == step("read_request")
    assert steps[-2:] == last_steps


def test_without_model_keys_the_agent_is_off_and_asks_nothing(clean_engine: Engine) -> None:
    heigit = CountingHeigit()
    api = agent_api(clean_engine, models=None, heigit=heigit)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    response = ask(api, request_id)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "agent_not_configured"
    assert heigit.requests == []
    with clean_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM agent_runs")).scalar_one() == 0
    assert api.get("/api/ready").status_code == 200


def test_an_agent_run_is_its_owners_alone(clean_engine: Engine) -> None:
    api = agent_api(clean_engine, fake_models([RUN_5K, GOOD_DRAFT], [APPROVED]))
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)
    run = ask(api, request_id).json()["run"]

    mine = api.get(f"/api/agent-runs/{run['id']}", headers=as_owner(api, TOM))
    theirs = api.get(f"/api/agent-runs/{run['id']}", headers=as_owner(api, SOMEONE))
    from_their_request = ask(api, request_id, owner=SOMEONE)

    assert mine.status_code == 200
    assert mine.json() == run
    assert theirs.status_code == 404
    assert from_their_request.status_code == 404


def test_agent_runs_count_towards_the_daily_run_limit(clean_engine: Engine) -> None:
    heigit = CountingHeigit()
    clarifying = fake_models([Interpretation(activity="running"), "How far?"], [APPROVED])
    api = agent_api(clean_engine, clarifying, heigit, runs_per_day=1)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)
    assert ask(api, request_id).status_code == 201

    again = ask(api, request_id)
    route_run = api.post(
        f"/api/route-requests/{request_id}/runs",
        json={"operation_id": str(uuid4()), "distance": {"kind": "target", "target_km": 5}},
        headers=as_owner(api, TOM),
    )

    assert again.status_code == 429
    assert route_run.status_code == 429
    assert heigit.requests == []


def test_a_brief_longer_than_the_agent_reads_is_refused(clean_engine: Engine) -> None:
    api = agent_api(clean_engine, fake_models([], []))
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)

    assert ask(api, request_id, brief="x" * 1001).status_code == 422
    assert ask(api, request_id, brief="").status_code == 422


def test_old_agent_runs_go_with_their_route_request(clean_engine: Engine) -> None:
    api = agent_api(clean_engine, fake_models([RUN_5K, GOOD_DRAFT], [APPROVED]))
    ask(api, confirm_start(api, AVENUE_SOUTH_BLOCK_11))
    old = datetime.now(UTC) - timedelta(days=ROUTE_REQUEST_DAYS + 1)
    with clean_engine.begin() as connection:
        connection.execute(text("UPDATE route_requests SET created_at = :old"), {"old": old})

    purge_expired(clean_engine, datetime.now(UTC))

    with clean_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM agent_runs")).scalar_one() == 0


class Broken(Exception):
    """An unexpected failure, carrying text that must not reach the user or the database."""


def test_a_route_is_saved_holding_the_owner_lock(
    clean_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """So a concurrent run can neither take the same revision number nor count the owner's
    runs while the agent's route is half saved."""
    api = agent_api(clean_engine, fake_models([RUN_5K, GOOD_DRAFT], [APPROVED]))
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)
    lock = text("SELECT pg_try_advisory_xact_lock(hashtext(:owner))")
    others_got_the_lock = []

    def save_while_another_tries_the_lock(
        session: Session, run: GenerationRunRecord, generation: Any
    ) -> None:
        with Session(clean_engine) as concurrent:
            others_got_the_lock.append(concurrent.scalar(lock, {"owner": run.owner_id}))
        save_generation(session, run, generation)

    monkeypatch.setattr("route_api.main.save_generation", save_while_another_tries_the_lock)

    assert ask(api, request_id).status_code == 201
    assert others_got_the_lock == [False]


def fail(*args: object) -> None:
    raise Broken("secret detail: a 5k run from Avenue South")


@pytest.mark.parametrize("failing", ["run_agent", "save_generation"])
def test_an_unexpected_failure_finishes_the_run_as_failed(
    clean_engine: Engine, monkeypatch: pytest.MonkeyPatch, failing: str
) -> None:
    api = agent_api(clean_engine, fake_models([RUN_5K, GOOD_DRAFT], [APPROVED]), runs_per_day=1)
    request_id = confirm_start(api, AVENUE_SOUTH_BLOCK_11)
    monkeypatch.setattr(f"route_api.main.{failing}", fail)

    response = ask(api, request_id)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "agent_failed"
    assert "secret detail" not in response.text
    with clean_engine.connect() as connection:
        stored = connection.execute(text("SELECT * FROM agent_runs")).mappings().one()
        generation_runs = connection.execute(text("SELECT count(*) FROM generation_runs"))
        assert generation_runs.scalar_one() == 0
    assert (stored["status"], stored["kind"], stored["generation_run_id"]) == (
        "finished",
        "failed",
        None,
    )
    assert stored["finished_at"] is not None
    assert "secret detail" not in str(dict(stored))
    assert ask(api, request_id).status_code == 429
