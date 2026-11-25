"""Labelled evals for the route agent and its judge, run with the real models.

Adapted from tomjwright/agent-template's evals.py (commit 5e1068c0bf9872f3482c80a9f36898eb7b531655):
YAML cases, a score per case and a non-zero exit below a threshold. Here judge cases score the
judge's verdict on a fixed draft against its RouteFacts; the drafts' labels agree with the code
check in fact_check.py.

    uv run python -m route_api.evals [--agent-model SPEC] [--judge-model SPEC]
"""

import argparse
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import httpx
import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel

from route_api.agent import RouteAgent
from route_api.agent_models import RouteFacts, RunRequest
from route_api.heigit import Heigit
from route_api.llm import AGENT_MODEL, JUDGE_MODEL, Models, models_from_env
from route_api.restrictions import RestrictedWays, load_restricted_ways
from tests import recorded_heigit

EVALS_DIR = Path(__file__).parents[2] / "evals"
PAUSE_S = 4.0  # between cases, for the judge's free-tier rate limit
RETRY_WAIT_S = 30.0  # before the one retry of a case whose model was unavailable (e.g. a 429)
JudgeKind = Literal[
    "honest",
    "invented_measurement",
    "unsupported_claim",
    "ignored_constraint",
    "missing_disclosure",
    "bypass",
]
# One false approval of a stated falsehood or a bypass fails the run; a missed disclosure counts
# towards the false-approval rate.
ZERO_TOLERANCE = {"invented_measurement", "unsupported_claim", "ignored_constraint", "bypass"}


class JudgeCase(BaseModel):
    name: str
    facts: str  # a key of the fixture's facts
    kind: JudgeKind
    draft: str


class EvalSet(BaseModel):
    facts: dict[str, RouteFacts]
    judge_cases: list[JudgeCase]


class Baseline(BaseModel):
    max_false_approval_rate: float
    max_false_rejection_rate: float


class ModelUnavailable(Exception):
    pass


def load_eval_set(directory: Path) -> EvalSet:
    judge = yaml.safe_load((directory / "judge_cases.yaml").read_text())
    return EvalSet(facts=judge["facts"], judge_cases=judge["cases"])


@dataclass
class Report:
    false_approvals: list[JudgeCase] = field(default_factory=list)
    false_rejections: list[JudgeCase] = field(default_factory=list)


def run_evals(eval_set: EvalSet, models: Models, pause_s: float) -> Report:
    report = Report()
    restricted_ways = load_restricted_ways()
    for case in eval_set.judge_cases:
        approved = judge_draft(case, eval_set.facts[case.facts], models, restricted_ways)
        print(f"  judge {'approved' if approved else 'rejected'} {case.name!r}", flush=True)
        if approved and case.kind != "honest":
            report.false_approvals.append(case)
        if not approved and case.kind == "honest":
            report.false_rejections.append(case)
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
    print(f"agent {models.agent_name}, judge {models.judge_name}")
    print(
        f"judge: false approvals {len(report.false_approvals)}/{len(rejects)}"
        f" ({approval_rate:.2f}), false rejections {len(report.false_rejections)}/{honest}"
        f" ({rejection_rate:.2f})"
    )
    for case in report.false_rejections:
        print(f"  judge rejected honest {case.name!r}")

    failures: list[str] = []
    for case in report.false_approvals:
        if case.kind in ZERO_TOLERANCE:
            failures.insert(0, f"judge approved {case.name!r} ({case.kind})")
    most_approvals = baseline.max_false_approval_rate
    most_rejections = baseline.max_false_rejection_rate
    if approval_rate > most_approvals:
        failures.append(f"false approval rate {approval_rate:.2f} is above {most_approvals:.2f}")
    if rejection_rate > most_rejections:
        failures.append(f"false rejection rate {rejection_rate:.2f} is above {most_rejections:.2f}")
    for failure in failures:
        print(f"FAIL {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
