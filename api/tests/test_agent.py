"""Seam 1: the route agent's whole workflow with fake agent and judge models.

HeiGIT replays recorded real responses; no test calls an LLM or a live provider.
"""

import json
import uuid
from typing import Any

import httpx
import pytest
from langchain_core.tracers.langchain import LangChainTracer

from route_api.agent import run_agent
from route_api.agent_models import (
    AgentResult,
    Clarification,
    Interpretation,
    RunRequest,
    RunStart,
    Verdict,
)
from route_api.contracts import Activity, Distance, DistanceTarget
from route_api.heigit import Heigit
from route_api.restrictions import load_restricted_ways
from tests.fake_models import FakeModel
from tests.recorded_heigit import FIXTURES, recorded_response

AVENUE_SOUTH = RunStart(
    name="AVENUE SOUTH RESIDENCE", coordinates=(103.8291052120283, 1.276629534107344)
)
FIVE_KM = DistanceTarget(kind="target", target_km=5)
RUN_5K = Interpretation(activity="running", distance=FIVE_KM, preferences=[])
APPROVED = Verdict(approved=True, reasons=[])
REJECTED = Verdict(approved=False, reasons=["it says 7 km; the route is 5.26 km"])
GOOD_DRAFT = "Here is a 5.26 km running loop from Avenue South Residence."
BAD_DRAFT = "Here is a 7 km running loop, fully shaded and safe."
RESTRICTED_WAYS = load_restricted_ways()


def run(
    agent: FakeModel,
    judge: FakeModel,
    brief: str = "a 5k run",
    activity: Activity | None = "running",
    distance: Distance | None = None,
    start: RunStart | None = AVENUE_SOUTH,
    heigit_handler: httpx.MockTransport | None = None,
    time_budget_s: float = 100,
) -> AgentResult:
    transport = heigit_handler or httpx.MockTransport(recorded_response)
    heigit = Heigit(
        httpx.Client(transport=transport),
        "synthetic-key",
        request_gap_seconds=0,
        retry_wait_seconds=0,
    )
    request = RunRequest(
        run_id=uuid.uuid4(), brief=brief, activity=activity, distance=distance, start=start
    )
    return run_agent(request, agent, judge, heigit, RESTRICTED_WAYS, time_budget_s)


def test_an_approved_answer_is_published_with_the_provider_geometry() -> None:
    agent = FakeModel(replies=[RUN_5K, GOOD_DRAFT])
    judge = FakeModel(replies=[APPROVED])
    result = run(agent, judge)

    assert result.kind == "route"
    assert result.message == GOOD_DRAFT
    assert agent.schemas == [Interpretation]
    assert judge.schemas == [Verdict]
    assert "a 5k run" in agent.prompts[0]
    assert result.message_source == "approved_draft"
    assert result.verdicts == [APPROVED]
    assert result.repairs == 0
    assert result.facts is not None
    assert result.facts.distance_km == 5.26
    assert (result.facts.min_km, result.facts.max_km) == (4.5, 5.5)
    recorded = json.loads((FIXTURES / "heigit_avenue_south_5km_1.json").read_text())
    selected = result.generation.attempts[1].route  # type: ignore[union-attr]
    assert selected is not None
    assert [list(point) for point in selected.coordinates] == recorded["features"][0]["geometry"][
        "coordinates"
    ]


def test_a_run_sends_nothing_to_langsmith(monkeypatch: pytest.MonkeyPatch) -> None:
    tracers = []

    def record(tracer: LangChainTracer, *args: object, **kwargs: object) -> None:
        tracers.append(tracer)

    monkeypatch.setattr(LangChainTracer, "__init__", record)
    result = run(FakeModel(replies=[RUN_5K, GOOD_DRAFT]), FakeModel(replies=[APPROVED]))

    assert result.message == GOOD_DRAFT
    assert tracers == []


def test_a_rejected_draft_is_repaired_once_with_the_judges_reasons() -> None:
    two_problems = Verdict(approved=False, reasons=["too long", "claims shade"])
    agent = FakeModel(replies=[RUN_5K, BAD_DRAFT, GOOD_DRAFT])
    result = run(agent, FakeModel(replies=[two_problems, APPROVED]))

    assert result.message == GOOD_DRAFT
    assert result.repairs == 1
    assert result.verdicts == [two_problems, APPROVED]
    repair_prompt = agent.prompts[2]
    assert "AVENUE SOUTH RESIDENCE" in repair_prompt
    assert BAD_DRAFT in repair_prompt
    assert "too long; claims shade" in repair_prompt


def test_two_rejections_fall_back_to_a_factual_answer() -> None:
    agent = FakeModel(replies=[RUN_5K, BAD_DRAFT, BAD_DRAFT])
    result = run(agent, FakeModel(replies=[REJECTED, REJECTED]))

    assert result.kind == "route"
    assert result.message_source == "fallback"
    assert result.fallback_reason == "rejected_twice"
    assert result.verdicts == [REJECTED, REJECTED]
    assert result.message == (
        "Here is a 5.26 km running loop for the 4.50-5.50 km you asked for. "
        "Distance is measured along the route shown, which is exactly what the GPX contains. "
        "The time is HeiGIT's foot-walking estimate, not a running time. "
        "Access restrictions, closures and safety are not checked yet. OpenStreetMap data can"
        " be out of date, so check the route before you go."
    )
    assert "shaded" not in result.message
    assert "5.26 km running loop" in result.message
    assert "4.50-5.50 km" in result.message


def test_an_unavailable_judge_fails_closed() -> None:
    agent = FakeModel(replies=[RUN_5K, BAD_DRAFT])
    result = run(agent, FakeModel(replies=[TimeoutError("judge timed out")]))

    assert result.message_source == "fallback"
    assert result.fallback_reason == "judge_unavailable"
    assert BAD_DRAFT not in result.message
    assert result.verdicts == []


@pytest.mark.parametrize("failure", [ConnectionError("down"), " "])
def test_an_unavailable_drafter_falls_back_without_judging(failure: object) -> None:
    judge = FakeModel()
    result = run(FakeModel(replies=[RUN_5K, failure]), judge)

    assert result.fallback_reason == "draft_unavailable"
    assert "5.26 km" in result.message
    assert judge.prompts == []


def test_an_unreadable_request_fails_before_any_route_is_asked_for() -> None:
    def no_heigit(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HeiGIT was called")

    agent = FakeModel(replies=[ValueError("not JSON")])
    result = run(agent, FakeModel(), heigit_handler=httpx.MockTransport(no_heigit))

    assert result.kind == "failed"
    assert result.fallback_reason == "interpretation_unavailable"
    assert result.facts is None
    assert result.message == "The route assistant could not read your request. Please try again."


def test_a_missing_distance_is_a_judged_clarification() -> None:
    question = "How far would you like to run? Give a distance or a range."
    agent = FakeModel(replies=[Interpretation(activity="running", distance=None), question])
    result = run(agent, FakeModel(replies=[APPROVED]), brief="a run please")

    assert result.kind == "clarification"
    assert result.clarification is not None
    assert result.clarification.reason == "missing_distance"
    assert result.message == question
    assert result.generation is None


def test_unsupported_preferences_are_disclosed_in_the_fallback() -> None:
    shaded = Interpretation(activity="running", distance=FIVE_KM, preferences=["shaded", "quiet"])
    agent = FakeModel(replies=[shaded, BAD_DRAFT, BAD_DRAFT])
    result = run(agent, FakeModel(replies=[REJECTED, REJECTED]), brief="a shaded 5k")

    assert result.facts is not None
    assert result.facts.unsupported_preferences == ["shaded", "quiet"]
    assert "Not supported yet: shaded, quiet." in result.message


def quota(request: httpx.Request) -> httpx.Response:
    return httpx.Response(429, json={"error": "quota"})


def timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("slow", request=request)


def broken(request: httpx.Request) -> httpx.Response:
    raise RuntimeError("an unexpected failure")


@pytest.mark.parametrize(
    ("heigit", "error_code"),
    [
        (quota, "provider_quota_exhausted"),
        (timeout, "provider_unavailable"),
        (broken, "generation_failed"),
    ],
)
def test_a_failed_generation_ends_in_a_factual_error_without_a_draft(
    heigit: Any, error_code: str
) -> None:
    agent = FakeModel(replies=[RUN_5K])
    judge = FakeModel()
    result = run(agent, judge, heigit_handler=httpx.MockTransport(heigit))

    assert result.kind == "failed"
    assert result.message_source == "fallback"
    assert result.fallback_reason == "no_route"
    assert result.facts is not None
    assert result.facts.error_code == error_code
    assert result.message == f"No route could be made: {error_code}."
    assert len(agent.prompts) == 1
    assert judge.prompts == []


def test_a_loop_that_cannot_be_made_ends_without_a_draft() -> None:
    narrow = Interpretation(activity="running", distance=DistanceTarget(kind="target", target_km=1))

    def no_path(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"code": 2009}})

    agent = FakeModel(replies=[narrow])
    result = run(agent, FakeModel(), heigit_handler=httpx.MockTransport(no_path))

    assert result.kind == "no_route"
    assert result.fallback_reason == "no_route"
    assert result.message == "No acceptable 0.90-1.10 km running loop was found in 5 tries."
    assert len(agent.prompts) == 1


def test_an_exhausted_time_budget_makes_no_model_call() -> None:
    agent = FakeModel(replies=[RUN_5K])
    result = run(agent, FakeModel(), time_budget_s=0)

    assert result.fallback_reason == "interpretation_unavailable"
    assert agent.prompts == []


def test_models_never_see_the_start_coordinates_or_the_key() -> None:
    agent = FakeModel(replies=[RUN_5K, BAD_DRAFT, GOOD_DRAFT])
    judge = FakeModel(replies=[REJECTED, APPROVED])
    run(agent, judge)

    for prompt in agent.prompts + judge.prompts:
        assert "103.829" not in prompt
        assert "1.2766" not in prompt
        assert "synthetic-key" not in prompt
    assert "AVENUE SOUTH RESIDENCE" in agent.prompts[1]


def test_each_run_has_its_own_state() -> None:
    first = run(
        FakeModel(replies=[RUN_5K, BAD_DRAFT, BAD_DRAFT]), FakeModel(replies=[REJECTED, REJECTED])
    )
    second = run(FakeModel(replies=[RUN_5K, GOOD_DRAFT]), FakeModel(replies=[APPROVED]))

    assert first.run_id != second.run_id
    assert second.verdicts == [APPROVED]
    assert second.repairs == 0
    assert second.message == GOOD_DRAFT


def test_unanswered_questions_fall_back_to_fixed_wording() -> None:
    no_activity = run(
        FakeModel(replies=[Interpretation(distance=FIVE_KM), ConnectionError()]),
        FakeModel(),
        activity=None,
    )
    no_distance = run(
        FakeModel(replies=[Interpretation(activity="running"), ConnectionError()]), FakeModel()
    )
    no_start = run(FakeModel(replies=[RUN_5K, ConnectionError()]), FakeModel(), start=None)

    assert no_activity.message == "Is this a run or a road-cycling ride?"
    assert no_distance.message == "What distance would you like? Give a target or a range in km."
    assert no_start.clarification == Clarification(reason="missing_start")
    assert no_start.message == (
        "Where should the loop start? Search for a place and confirm it first."
    )


def test_the_form_fills_what_the_message_leaves_out() -> None:
    agent = FakeModel(replies=[Interpretation(), GOOD_DRAFT])
    result = run(agent, FakeModel(replies=[APPROVED]), brief="a loop", distance=FIVE_KM)

    assert result.kind == "route"
    assert result.facts is not None
    assert result.facts.activity == "running"
    assert result.facts.duration_minutes == 63


def test_a_ride_is_checked_for_restricted_roads() -> None:
    ride = Interpretation(
        activity="road_cycling", distance=DistanceTarget(kind="target", target_km=20)
    )
    agent = FakeModel(replies=[ride, ConnectionError()])
    result = run(agent, FakeModel(), brief="a 20 km ride", activity="road_cycling")

    assert result.kind == "route"
    assert result.generation is not None
    chosen = result.generation.selection.chosen  # type: ignore[union-attr]
    assert result.generation.attempts[chosen].restricted_roads is not None  # type: ignore[index]
    assert "cycling-road estimate" in result.message
