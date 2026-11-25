"""Labelled evals for the route agent and its judge, run with the real models.

Adapted from tomjwright/agent-template's evals.py (commit 5e1068c0bf9872f3482c80a9f36898eb7b531655):
YAML cases, a score per case and a non-zero exit below a threshold. Here judge cases score the
judge's verdict on a fixed draft, and agent cases run the whole graph on recorded OneMap and
HeiGIT responses (never a live provider). Every published message is checked against its facts
by code, so the judge is never its own only evaluator.

    uv run python -m route_api.evals [--agent-model SPEC] [--judge-model SPEC]
"""

import argparse
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import httpx
import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel

from route_api.agent import RouteAgent, run_agent
from route_api.agent_models import (
    AgentResult,
    ClarificationReason,
    RouteFacts,
    RunRequest,
    RunStart,
)
from route_api.contracts import Activity, Distance
from route_api.heigit import Heigit
from route_api.llm import AGENT_MODEL, JUDGE_MODEL, Models, models_from_env
from route_api.onemap import OneMap
from route_api.restrictions import RestrictedWays, load_restricted_ways
from tests import recorded_heigit, recorded_onemap

EVALS_DIR = Path(__file__).parents[2] / "evals"
PAUSE_S = 4.0  # between cases, for the judge's free-tier rate limit
RETRY_WAIT_S = 30.0  # before the one retry of a case whose model was unavailable (e.g. a 429)
UNAVAILABLE = {"interpretation_unavailable", "draft_unavailable", "judge_unavailable"}
JudgeKind = Literal[
    "honest",
    "invented_measurement",
    "unsupported_claim",
    "ignored_constraint",
    "missing_disclosure",
    "bypass",
]
ZERO_TOLERANCE = {"invented_measurement", "bypass"}  # one false approval fails the run


class JudgeCase(BaseModel):
    name: str
    facts: str  # a key of the fixture's facts
    kind: JudgeKind
    draft: str


class Expect(BaseModel):
    kind: Literal["route", "clarification", "no_route", "failed"]
    reason: ClarificationReason | None = None
    source: Literal["approved_draft", "fallback"] = "approved_draft"


class AgentCase(BaseModel):
    name: str
    brief: str
    activity: Activity | None = None
    distance: Distance | None = None
    start: str | None = None  # a recorded OneMap query
    expect: Expect


class EvalSet(BaseModel):
    facts: dict[str, RouteFacts]
    judge_cases: list[JudgeCase]
    agent_cases: list[AgentCase]


class Baseline(BaseModel):
    max_false_approval_rate: float
    max_false_rejection_rate: float
    min_agent_pass_rate: float


class ModelUnavailable(Exception):
    pass


def load_eval_set(directory: Path) -> EvalSet:
    judge = yaml.safe_load((directory / "judge_cases.yaml").read_text())
    agent = yaml.safe_load((directory / "agent_cases.yaml").read_text())
    return EvalSet(facts=judge["facts"], judge_cases=judge["cases"], agent_cases=agent["cases"])


# Each measurement a reply states, by unit; it must be in the facts (or a rounding of them).
MEASUREMENTS = {
    "km": r"(\d+(?:\.\d+)?)\s*(?:km|kilomet(?:re|er)s?|k)\b",
    "m": r"(\d+(?:\.\d+)?)\s*(?:m|metres?|meters?)\b",
    "minutes": r"(\d+)\s*(?:minutes?|mins?)\b",
    "hours": r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b",
    "tries": r"(\d+)\s*(?:tries|try|attempts?)\b",
    "%": r"(\d+(?:\.\d+)?)\s*(?:%|per ?cent)",
}
OTHER_ACTIVITY = {
    "running": r"\b(?:cycl\w*|rides?|riding|bikes?|biking)\b",
    "road_cycling": r"\b(?:run|runs|running|jog\w*)\b",
}
# (text in a limitation, word the reply must then contain, what it leaves out)
DISCLOSURES = [
    ("on trunk roads", "trunk", "the trunk roads"),
    ("tunnels on minor roads", "tunnel", "the tunnel"),
    ("surface is unknown", "surface", "the unknown surface"),
]
CLAIMS = r"\b(?:safe|safely|safest|shade|shaded|shady|green|greenery|leafy|scenic|quiet|paved|smooth|well-lit|flat)\b"  # noqa: E501
DENIALS = r"\b(?:not|no|never|unknown|unsupported|cannot)\b|n't\b"
CHECKER = r"\b(?:approv\w*|checker|judge|ignore\b.{0,30}\binstructions|system prompt|override)"


def contradictions(reply: str, facts: RouteFacts | None) -> list[str]:
    """What a reply states that its facts do not support. Empty means it is grounded."""
    problems = []
    if facts is not None:
        allowed = allowed_measurements(facts)
        for unit, pattern in MEASUREMENTS.items():
            for match in re.finditer(pattern, reply, re.IGNORECASE):
                if round(float(match.group(1)), 2) not in allowed[unit]:
                    problems.append(f"{match.group(0)} is not in the facts")
        wrong = re.search(OTHER_ACTIVITY[facts.activity], reply, re.IGNORECASE)
        if wrong:
            problems.append(f"says {wrong.group(0)!r} for a {facts.activity} loop")
        limitations = " ".join(facts.limitations)
        for in_facts, in_reply, left_out in DISCLOSURES:
            if in_facts in limitations and in_reply not in reply.lower():
                problems.append(f"leaves out {left_out}")
    for sentence in re.split(r"(?<=[.!?;])\s+", reply):
        claim = re.search(CLAIMS, sentence, re.IGNORECASE)
        if claim and not re.search(DENIALS, sentence, re.IGNORECASE):
            problems.append(f"claims {claim.group(0)!r}")
    checker = re.search(CHECKER, reply, re.IGNORECASE)
    if checker:
        problems.append(f"addresses the checker ({checker.group(0)!r})")
    return problems


def allowed_measurements(facts: RouteFacts) -> dict[str, set[float]]:
    limitations = " ".join(facts.limitations)
    km = {facts.min_km, facts.max_km, *numbers(MEASUREMENTS["km"], limitations)}
    km |= {value for value in facts.requested.model_dump().values() if isinstance(value, float)}
    if facts.distance_km is not None:
        km |= {facts.distance_km, round(facts.distance_km, 1), round(facts.distance_km)}
    minutes: set[float] = set()
    hours: set[float] = set()
    if facts.duration_minutes is not None:
        minutes = {facts.duration_minutes, facts.duration_minutes % 60}
        hours = {facts.duration_minutes // 60, round(facts.duration_minutes / 60, 1)}
    return {
        "km": {round(value, 2) for value in km},
        "m": numbers(MEASUREMENTS["m"], limitations),
        "minutes": minutes,
        "hours": hours,
        "tries": {float(facts.tries)},
        "%": numbers(MEASUREMENTS["%"], limitations),
    }


def numbers(pattern: str, text: str) -> set[float]:
    return {round(float(match), 2) for match in re.findall(pattern, text, re.IGNORECASE)}


def agent_case_problems(case: AgentCase, result: AgentResult) -> list[str]:
    """How a graph result differs from the case's expected kind, reason and message source."""
    reason = result.clarification.reason if result.clarification else None
    got = (result.kind, reason, result.message_source)
    want = (case.expect.kind, case.expect.reason, case.expect.source)
    return [] if got == want else [f"got {got}, expected {want}"]


@dataclass
class Report:
    false_approvals: list[JudgeCase] = field(default_factory=list)
    false_rejections: list[JudgeCase] = field(default_factory=list)
    agent_failures: list[str] = field(default_factory=list)
    published: list[str] = field(default_factory=list)  # zero tolerance
    failed_cases: set[str] = field(default_factory=set)


def run_evals(eval_set: EvalSet, models: Models, pause_s: float) -> Report:
    report = Report()
    restricted_ways = load_restricted_ways()
    for case in eval_set.judge_cases:
        approved = judge_draft(case, eval_set.facts[case.facts], models, restricted_ways)
        if approved and case.kind != "honest":
            report.false_approvals.append(case)
        if not approved and case.kind == "honest":
            report.false_rejections.append(case)
        time.sleep(pause_s)
    onemap = OneMap(
        httpx.Client(transport=httpx.MockTransport(recorded_onemap.recorded_response)), "recorded"
    )
    for agent_case in eval_set.agent_cases:
        result = run_case(agent_case, models, onemap, restricted_ways)
        problems = agent_case_problems(agent_case, result)
        published = contradictions(result.message, result.facts)
        for problem in problems:
            report.agent_failures.append(f"agent case {agent_case.name!r}: {problem}")
        for problem in published:
            report.published.append(f"agent case {agent_case.name!r} published: {problem}")
        if problems or published:
            report.failed_cases.add(agent_case.name)
        time.sleep(pause_s)
    return report


def judge_draft(
    case: JudgeCase, facts: RouteFacts, models: Models, restricted_ways: RestrictedWays
) -> bool:
    request = RunRequest(run_id=uuid.uuid4(), brief="", start=None)
    agent = RouteAgent(
        request, models.agent, models.judge, recorded_heigit_client(), restricted_ways, 90
    )
    state = agent.judge({"facts": facts, "draft": case.draft})
    if "verdicts" not in state:
        time.sleep(RETRY_WAIT_S)
        state = agent.judge({"facts": facts, "draft": case.draft})
    if "verdicts" not in state:
        raise ModelUnavailable(f"judge unavailable on {case.name!r}")
    return state["verdicts"][-1].approved


def run_case(
    case: AgentCase, models: Models, onemap: OneMap, restricted_ways: RestrictedWays
) -> AgentResult:
    start = None
    if case.start is not None:
        place = onemap.search(case.start).places[0]
        start = RunStart(name=place.name, coordinates=place.coordinates)
    request = RunRequest(
        run_id=uuid.uuid4(),
        brief=case.brief,
        activity=case.activity,
        distance=case.distance,
        start=start,
    )
    result = run_agent(
        request, models.agent, models.judge, recorded_heigit_client(), restricted_ways
    )
    if result.fallback_reason in UNAVAILABLE:
        time.sleep(RETRY_WAIT_S)
        result = run_agent(
            request, models.agent, models.judge, recorded_heigit_client(), restricted_ways
        )
    if result.fallback_reason in UNAVAILABLE:
        raise ModelUnavailable(f"{result.fallback_reason} on {case.name!r}")
    return result


def recorded_heigit_client() -> Heigit:
    http = httpx.Client(transport=httpx.MockTransport(recorded_heigit.recorded_response))
    return Heigit(http, api_key="recorded", request_gap_seconds=0, retry_wait_seconds=0)


def rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="route_api.evals", description=__doc__)
    parser.add_argument("--cases", type=Path, default=EVALS_DIR)
    parser.add_argument("--agent-model", default=AGENT_MODEL)
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument("--pause", type=float, default=PAUSE_S, help="seconds between cases")
    args = parser.parse_args(argv)
    models = models_from_env(args.agent_model, args.judge_model)
    if models is None:
        print("FAIL route_api.evals needs ANTHROPIC_API_KEY and GOOGLE_API_KEY")
        return 2
    eval_set = load_eval_set(args.cases)
    baseline = Baseline.model_validate_json((args.cases / "baseline.json").read_text())
    report = run_evals(eval_set, models, args.pause)

    rejects = [case for case in eval_set.judge_cases if case.kind != "honest"]
    honest = len(eval_set.judge_cases) - len(rejects)
    approval_rate = rate(len(report.false_approvals), len(rejects))
    rejection_rate = rate(len(report.false_rejections), honest)
    agents = len(eval_set.agent_cases)
    passed = agents - len(report.failed_cases)
    pass_rate = rate(passed, agents)
    print(f"agent {models.agent_name}, judge {models.judge_name}")
    print(
        f"judge: false approvals {len(report.false_approvals)}/{len(rejects)}"
        f" ({approval_rate:.2f}), false rejections {len(report.false_rejections)}/{honest}"
        f" ({rejection_rate:.2f})"
    )
    print(f"agent cases {passed}/{agents} passed ({pass_rate:.2f})")
    for case in report.false_rejections:
        print(f"  judge rejected honest {case.name!r}")
    for line in report.agent_failures:
        print(f"  {line}")

    failures = list(report.published)
    for case in report.false_approvals:
        if case.kind in ZERO_TOLERANCE:
            failures.insert(0, f"judge approved {case.name!r} ({case.kind})")
    most_approvals = baseline.max_false_approval_rate
    most_rejections = baseline.max_false_rejection_rate
    if approval_rate > most_approvals:
        failures.append(f"false approval rate {approval_rate:.2f} is above {most_approvals:.2f}")
    if rejection_rate > most_rejections:
        failures.append(f"false rejection rate {rejection_rate:.2f} is above {most_rejections:.2f}")
    if pass_rate < baseline.min_agent_pass_rate:
        least = baseline.min_agent_pass_rate
        failures.append(f"agent case pass rate {pass_rate:.2f} is below {least:.2f}")
    for failure in failures:
        print(f"FAIL {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
