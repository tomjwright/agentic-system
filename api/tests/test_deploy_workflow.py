"""Deploy gate: the deploy workflow, which holds production secrets, only ever runs code that
is already on this repository's main branch and has passed every check main requires. The
repository is public, so a fork's pull request (even from a branch named "main") must never
reach it. Each test fails on one kind of weakening edit to .github/workflows/deploy.yml."""

import re
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

WORKFLOWS = Path(__file__).parents[2] / ".github/workflows"
# The checks main's branch protection requires, plus the two smoke jobs added with deploy.
REQUIRED_CHECKS = [
    "secrets-scan",
    "feasibility",
    "actionlint",
    "zizmor",
    "codeql (python)",
    "codeql (actions)",
    "api",
    "web",
    "codeql (javascript-typescript)",
    "migration-compat",
    "mutation-api",
    "mutation-feasibility",
    "render-smoke",
    "vercel-build",
]
FULL_SHA_PIN = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


def load(name: str) -> dict[Any, Any]:
    workflow: dict[Any, Any] = yaml.safe_load((WORKFLOWS / name).read_text())
    return workflow


def promote_job() -> dict[Any, Any]:
    job: dict[Any, Any] = load("deploy.yml")["jobs"]["promote"]
    return job


def step_named(start: str) -> int:
    for index, step in enumerate(promote_job()["steps"]):
        if step.get("name", "").startswith(start):
            return index
    raise AssertionError(f"no step named {start!r}")


def pull_request_check_names() -> set[str]:
    """Every check a pull request runs: ci and workflow-security jobs, one per codeql language."""
    names = set()
    for workflow in ("ci.yml", "workflow-security.yml"):
        assert "pull_request" in load(workflow)[True]
        names.update(load(workflow)["jobs"])
    codeql = load("codeql.yml")
    assert "pull_request" in codeql[True]
    analyze = codeql["jobs"]["analyze"]
    assert analyze["name"] == "codeql (${{ matrix.language }})"
    for language in analyze["strategy"]["matrix"]["language"]:
        names.add(f"codeql ({language})")
    return names


def test_only_a_finished_ci_run_on_main_or_a_manual_dispatch_starts_it() -> None:
    triggers = load("deploy.yml")[True]  # PyYAML reads the "on" key as True
    assert set(triggers) == {"workflow_run", "workflow_dispatch"}
    assert triggers["workflow_run"] == {
        "workflows": ["ci"],
        "types": ["completed"],
        "branches": ["main"],
    }
    assert triggers["workflow_dispatch"] is None


def test_a_workflow_run_must_be_a_passing_push_to_main_of_this_repository() -> None:
    condition = promote_job()["if"]
    run, dispatch = condition.split(" || ")
    clauses = run.removeprefix("(").removesuffix(")").split(" && ")
    assert clauses == [
        "github.event_name == 'workflow_run'",
        "github.event.workflow_run.event == 'push'",
        "github.event.workflow_run.head_repository.full_name == github.repository",
        "github.event.workflow_run.head_branch == 'main'",
        "github.event.workflow_run.conclusion == 'success'",
    ]
    manual_on_main = "github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'"
    assert dispatch == f"({manual_on_main})"


def test_it_uses_the_protected_environment_and_checks_out_only_the_trusted_commit() -> None:
    job = promote_job()
    assert job["environment"] == "production"
    assert job["env"]["COMMIT_SHA"] == "${{ github.event.workflow_run.head_sha || github.sha }}"
    checkout = job["steps"][0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"] == {"ref": "${{ env.COMMIT_SHA }}", "persist-credentials": False}


def test_its_token_may_only_read_code_and_check_results() -> None:
    workflow = load("deploy.yml")
    assert workflow["permissions"] == {"contents": "read", "checks": "read"}
    assert "permissions" not in promote_job()


def test_one_deploy_at_a_time_and_a_running_one_is_never_cancelled() -> None:
    assert load("deploy.yml")["concurrency"] == {"group": "production", "cancel-in-progress": False}


def test_it_requires_exactly_the_checks_main_requires() -> None:
    sent = promote_job()["steps"][step_named("Promote")]["env"]["REQUIRED_CHECKS"]
    assert sent.split(",") == REQUIRED_CHECKS


def test_every_pull_request_check_is_required_before_deploying() -> None:
    assert pull_request_check_names() == set(REQUIRED_CHECKS)


def test_the_page_is_built_scanned_and_staged_before_promotion() -> None:
    steps = promote_job()["steps"]
    build = step_named("Build the page")
    scan = step_named("No provider key")
    stage = step_named("Stage the page")
    install_browser_tests = step_named("Install the staged browser tests")
    promote = step_named("Promote")
    assert build < scan < stage < install_browser_tests < promote == len(steps) - 1
    assert "build --prod" in steps[build]["run"]
    assert "VERCEL_TOKEN" not in steps[build].get("env", {})
    assert steps[scan]["run"] == "scripts/no_provider_secrets.sh .vercel/output"
    assert "deploy --prebuilt --prod --skip-domain" in steps[stage]["run"]


def test_promotion_and_its_rollback_run_as_one_unconditional_step() -> None:
    job = promote_job()
    promote = job["steps"][step_named("Promote")]
    assert promote["run"].splitlines() == [
        "uv sync --frozen --no-dev",
        "uv run --no-sync python -m route_api.promote",
    ]
    assert promote["env"]["STAGED_URL"] == "${{ steps.stage.outputs.url }}"
    for step in job["steps"]:
        assert "if" not in step
        assert "continue-on-error" not in step
    # Longer than promote.py's own waits, so the job is never cut off before rolling back.
    assert job["timeout-minutes"] >= 150


def test_secrets_reach_only_the_steps_that_need_them() -> None:
    allowed = {
        "Pull the production project settings": {"VERCEL_TOKEN"},
        "Stage the page (not yet live)": {"VERCEL_TOKEN"},
        "Promote, or roll back to the previous healthy release": {
            "RENDER_API_KEY",
            "VERCEL_TOKEN",
            "VERCEL_AUTOMATION_BYPASS_SECRET",
            "SMOKE_TOKEN",
        },
    }
    assert "secrets." not in str(promote_job()["env"])
    for step in promote_job()["steps"]:
        used = set()
        for name, value in step.get("env", {}).items():
            if "secrets." in str(value):
                used.add(name)
        assert used == allowed.get(step.get("name"), set()), step.get("name")


def test_every_action_is_pinned_to_a_full_commit() -> None:
    for step in promote_job()["steps"]:
        if "uses" in step:
            assert FULL_SHA_PIN.match(step["uses"]), step["uses"]
