"""Deploy gate: the deploy workflow, which holds production secrets, only ever runs code that
is already on this repository's main branch. The repository is public, so a fork's pull
request (even from a branch named "main") must never reach it."""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

WORKFLOW = Path(__file__).parents[2] / ".github/workflows/deploy.yml"


def load() -> dict[Any, Any]:
    workflow: dict[Any, Any] = yaml.safe_load(WORKFLOW.read_text())
    return workflow


def test_only_a_finished_app_run_or_a_manual_dispatch_starts_it() -> None:
    triggers = load()[True]  # PyYAML reads the "on" key as True
    assert set(triggers) == {"workflow_run", "workflow_dispatch"}
    assert triggers["workflow_run"]["workflows"] == ["app"]
    assert triggers["workflow_run"]["types"] == ["completed"]


def test_a_workflow_run_must_be_a_passing_push_to_main_of_this_repository() -> None:
    condition = load()["jobs"]["promote"]["if"]
    run, dispatch = condition.split(" || ")
    for clause in (
        "github.event_name == 'workflow_run'",
        "github.event.workflow_run.event == 'push'",
        "github.event.workflow_run.head_repository.full_name == github.repository",
        "github.event.workflow_run.head_branch == 'main'",
        "github.event.workflow_run.conclusion == 'success'",
    ):
        assert clause in run
    manual_on_main = "github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'"
    assert dispatch == f"({manual_on_main})"


def test_it_uses_the_protected_environment_and_checks_out_only_the_trusted_commit() -> None:
    job = load()["jobs"]["promote"]
    assert job["environment"] == "production"
    assert job["env"]["COMMIT_SHA"] == "${{ github.event.workflow_run.head_sha || github.sha }}"
    checkout = job["steps"][0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"] == {"ref": "${{ env.COMMIT_SHA }}", "persist-credentials": False}
