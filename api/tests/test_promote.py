"""Deploy gate: promotion refuses on missing or failed checks, and recovers from bad deploys.

GitHub, Render, Vercel and the deployed app are one fake transport that records every
state-changing call, so each test can say exactly what was (and was not) changed.
"""

import json

import httpx
import pytest

from route_api.promote import Promotion, PromotionStopped, Settings

STAGED = "https://stage-abc.vercel.app"
PRODUCTION = "https://routes.vercel.app"
REQUIRED = ["api", "web", "feasibility"]


class FakeHosts:
    def __init__(self) -> None:
        self.checks = {name: "success" for name in REQUIRED}
        self.render_statuses = ["build_in_progress", "update_in_progress", "live"]
        self.broken_sites: set[str] = set()
        self.changes: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        path = request.url.path
        if "check-runs" in path:
            runs = [{"name": n, "conclusion": c} for n, c in self.checks.items()]
            return httpx.Response(200, json={"check_runs": runs})
        if path == "/v1/services/srv-api/deploys" and request.method == "GET":
            older = [{"deploy": {"id": "dep-old", "status": "live"}}]
            return httpx.Response(
                200, json=[{"deploy": {"id": "dep-x", "status": "deactivated"}}, *older]
            )
        if path == "/v1/services/srv-api/deploys":
            self.changes.append(f"render deploy {json.loads(request.content)['commitId']}")
            return httpx.Response(201, json={"id": "dep-new", "status": "created"})
        if path == "/v1/services/srv-api/deploys/dep-new":
            return httpx.Response(
                200, json={"id": "dep-new", "status": self.render_statuses.pop(0)}
            )
        if path == "/v1/services/srv-api/rollback":
            self.changes.append(f"render rollback {json.loads(request.content)['deployId']}")
            return httpx.Response(201, json={"id": "dep-rollback", "status": "created"})
        if path == "/v13/deployments/routes.vercel.app":
            return httpx.Response(200, json={"id": "dpl-old"})
        if path == "/v13/deployments/stage-abc.vercel.app":
            return httpx.Response(200, json={"id": "dpl-new"})
        if path.startswith(("/v10/projects/prj/promote/", "/v1/projects/prj/rollback/")):
            self.changes.append(f"vercel {path.split('/')[4]} {path.split('/')[-1]}")
            return httpx.Response(201, json={})
        return self.app(request, url)

    def app(self, request: httpx.Request, url: str) -> httpx.Response:
        site = f"{request.url.scheme}://{request.url.host}"
        if site in self.broken_sites:
            return httpx.Response(503, json={"detail": "not ready"})
        if request.url.path == "/api/ready" or request.url.path == "/":
            return httpx.Response(200, json={"status": "ready"})
        if request.url.path == "/api/auth/me":
            if request.headers.get("authorization") == "Bearer smoke-token":
                return httpx.Response(200, json={"owner_id": "smoke", "csrf_token": ""})
            return httpx.Response(401, json={"detail": "Sign in first."})
        raise AssertionError(f"unexpected request {request.method} {url}")


@pytest.fixture
def hosts() -> FakeHosts:
    return FakeHosts()


def promote(hosts: FakeHosts) -> None:
    settings = Settings(
        repository="tomjwright/agentic-system",
        commit_sha="abc123",
        required_checks=REQUIRED,
        github_token="gh",
        render_api_key="rnd",
        render_service_id="srv-api",
        vercel_token="vc",
        vercel_project_id="prj",
        staged_url=STAGED,
        production_url=PRODUCTION,
        vercel_bypass_secret="bypass",
        smoke_token="smoke-token",
        poll_seconds=0,
    )
    Promotion(httpx.Client(transport=httpx.MockTransport(hosts.handle)), settings).run()


def test_a_healthy_release_is_promoted(hosts: FakeHosts) -> None:
    promote(hosts)
    assert hosts.changes == ["render deploy abc123", "vercel promote dpl-new"]


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", None])
def test_a_failed_or_unfinished_check_deploys_nothing(
    hosts: FakeHosts, conclusion: str | None
) -> None:
    hosts.checks["web"] = conclusion  # type: ignore[assignment]
    with pytest.raises(PromotionStopped, match="'web' did not pass"):
        promote(hosts)
    assert hosts.changes == []


def test_a_missing_check_deploys_nothing(hosts: FakeHosts) -> None:
    del hosts.checks["feasibility"]
    with pytest.raises(PromotionStopped, match="'feasibility' has not run"):
        promote(hosts)
    assert hosts.changes == []


def test_a_failed_migration_leaves_the_old_release_serving(hosts: FakeHosts) -> None:
    hosts.render_statuses = ["build_in_progress", "update_failed"]
    with pytest.raises(PromotionStopped, match="update_failed; the previous API keeps serving"):
        promote(hosts)
    assert hosts.changes == ["render deploy abc123"]


def test_a_failed_staged_smoke_test_rolls_the_api_back(hosts: FakeHosts) -> None:
    hosts.broken_sites.add(STAGED)
    with pytest.raises(PromotionStopped, match="staged smoke test failed"):
        promote(hosts)
    assert hosts.changes == ["render deploy abc123", "render rollback dep-old"]


def test_a_failed_production_smoke_test_rolls_both_back(hosts: FakeHosts) -> None:
    hosts.broken_sites.add(PRODUCTION)
    with pytest.raises(PromotionStopped, match="production smoke test failed"):
        promote(hosts)
    assert hosts.changes == [
        "render deploy abc123",
        "vercel promote dpl-new",
        "vercel rollback dpl-old",
        "render rollback dep-old",
    ]
