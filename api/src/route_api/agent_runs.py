"""Route agent runs in the database, and their public view.

A run is saved as `running` before any model is asked, so the daily run limit counts it,
then its outcome is saved once the agent answers. Only how the answer was made is kept:
the brief and the answer itself are not stored.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from route_api.agent_models import AgentResult
from route_api.contracts import AgentRun, AgentStep
from route_api.db import AgentRunRecord
from route_api.llm import Models


def new_agent_run(
    session: Session, owner: str, route_request_id: uuid.UUID | None, models: Models
) -> AgentRunRecord:
    """Add a `running` agent run. The caller commits."""
    run = AgentRunRecord(
        id=uuid.uuid4(),
        owner_id=owner,
        route_request_id=route_request_id,
        status="running",
        verdicts=[],
        repairs=0,
        agent_model=models.agent_name,
        judge_model=models.judge_name,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    return run


def finish_agent_run(run: AgentRunRecord, result: AgentResult) -> None:
    """Record how the answer was made. The caller commits."""
    run.status = "finished"
    run.kind = result.kind
    run.message_source = result.message_source
    run.fallback_reason = result.fallback_reason
    run.verdicts = [verdict.model_dump() for verdict in result.verdicts]
    run.repairs = result.repairs
    run.finished_at = datetime.now(UTC)


def fail_agent_run(run: AgentRunRecord) -> None:
    """Record that the run ended in an unexpected error. The caller commits."""
    run.status = "finished"
    run.kind = "failed"
    run.finished_at = datetime.now(UTC)


def find_agent_run(session: Session, owner: str, run_id: uuid.UUID) -> AgentRunRecord | None:
    query = select(AgentRunRecord).where(
        AgentRunRecord.id == run_id, AgentRunRecord.owner_id == owner
    )
    return session.scalars(query).first()


def to_agent_run(run: AgentRunRecord) -> AgentRun:
    approvals = []
    for verdict in run.verdicts:
        approvals.append(verdict["approved"])
    return AgentRun(
        id=run.id,
        route_request_id=run.route_request_id,
        status=run.status,  # type: ignore[arg-type]
        kind=run.kind,  # type: ignore[arg-type]
        message_source=run.message_source,  # type: ignore[arg-type]
        fallback_reason=run.fallback_reason,
        approvals=approvals,
        repairs=run.repairs,
        agent_model=run.agent_model,
        judge_model=run.judge_model,
        generation_run_id=run.generation_run_id,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def answer_steps(result: AgentResult) -> list[AgentStep]:
    """The steps the run took, rebuilt from what it recorded: each draft is followed by its
    judgment, and a judge that did not answer leaves a draft without one."""
    steps = [AgentStep(name="read_request")]
    if result.clarification is not None:
        steps.append(AgentStep(name="asked_clarification", reason=result.clarification.reason))
    if result.facts is not None:
        steps.append(AgentStep(name="generated_route", tries=result.facts.tries))
    drafts = len(result.verdicts)
    if result.fallback_reason == "judge_unavailable":
        drafts += 1
    for position in range(drafts):
        if position == 0:
            steps.append(AgentStep(name="drafted"))
        else:
            steps.append(AgentStep(name="repaired"))
        if position < len(result.verdicts):
            steps.append(AgentStep(name="judged", approved=result.verdicts[position].approved))
    if result.fallback_reason is not None:
        steps.append(AgentStep(name="fallback", reason=result.fallback_reason))
    return steps
