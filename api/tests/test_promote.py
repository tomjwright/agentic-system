"""Deploy gate: promotion refuses on missing or failed checks, and recovers from bad deploys.

GitHub, Render, Vercel and the deployed app are one fake transport that records every
state-changing call, so each test can say exactly what was (and was not) changed. The staged
browser tests are a small Python command that passes or fails.
"""

import json
import sys

import httpx
import pytest

from route_api.promote import Promotion, PromotionStopped, Settings, settings_from_env

STAGED = "https://stage-abc.vercel.app"
PRODUCTION = "https://routes.vercel.app"
REQUIRED = ["api", "web", "feasibility"]
PASSING_BROWSER_TESTS = [sys.executable, "-c", "pass"]


def browser_tests_exiting(code: int) -> list[str]:
    return [sys.executable, "-c", f"raise SystemExit({code})"]


class FakeHosts:
    def __init__(self) -> None:
        # Each poll of the check runs pops the next answer; the last one repeats.
        self.check_polls: list[dict[str, str | None]] = [dict.fromkeys(REQUIRED, "success")]
        self.check_queries: list[httpx.QueryParams] = []
        self.other_app_checks: dict[str, str] = {}
        self.render_deploys = [
            {"deploy": {"id": "dep-x", "status": "deactivated"}},
            {"deploy": {"id": "dep-old", "status": "live"}},
        ]
        self.render_statuses = ["build_in_progress", "update_in_progress", "live"]
        self.production_page: str | None = "dpl-old"
        self.broken_sites: set[str] = set()
        self.changes: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/repos/tomjwright/agentic-system/commits/abc123/check-runs":
            assert request.headers["authorization"] == "Bearer gh"
            return self.check_runs(request)
        if path.startswith("/v1/services/"):
            assert request.headers["authorization"] == "Bearer rnd"
            return self.render(request, path.removeprefix("/v1/services/srv-api"))
        if path.startswith(("/v13/", "/v10/", "/v1/projects/")):
            assert request.headers["authorization"] == "Bearer vc"
            return self.vercel(path)
        return self.app(request)

    def check_runs(self, request: httpx.Request) -> httpx.Response:
        self.check_queries.append(request.url.params)
        checks = self.check_polls[0]
        if len(self.check_polls) > 1:
            self.check_polls.pop(0)
        runs: list[dict[str, object]] = []
        for name, other_conclusion in self.other_app_checks.items():
            runs.append(
                {"name": name, "conclusion": other_conclusion, "app": {"slug": "other-app"}}
            )
        for name, conclusion in checks.items():
            runs.append({"name": name, "conclusion": conclusion, "app": {"slug": "github-actions"}})
        return httpx.Response(200, json={"check_runs": runs})

    def render(self, request: httpx.Request, path: str) -> httpx.Response:
        if path == "/deploys" and request.method == "GET":
            assert request.url.params["limit"] == "20"
            return httpx.Response(200, json=self.render_deploys)
        if path == "/deploys" and request.method == "POST":
            self.changes.append(f"render deploy {json.loads(request.content)['commitId']}")
            return httpx.Response(201, json={"id": "dep-new", "status": "created"})
        if path == "/deploys/dep-new":
            return httpx.Response(
                200, json={"id": "dep-new", "status": self.render_statuses.pop(0)}
            )
        if path == "/rollback" and request.method == "POST":
            self.changes.append(f"render rollback {json.loads(request.content)['deployId']}")
            return httpx.Response(201, json={"id": "dep-rollback", "status": "created"})
        raise AssertionError(f"unexpected Render call {request.method} {path}")

    def vercel(self, path: str) -> httpx.Response:
        if path == "/v13/deployments/routes.vercel.app":
            if self.production_page is None:
                return httpx.Response(404, json={"error": {"code": "not_found"}})
            return httpx.Response(200, json={"id": self.production_page})
        if path == "/v13/deployments/stage-abc.vercel.app":
            return httpx.Response(200, json={"id": "dpl-new"})
        if path.startswith(("/v10/projects/prj/promote/", "/v1/projects/prj/rollback/")):
            self.changes.append(f"vercel {path.split('/')[4]} {path.split('/')[-1]}")
            return httpx.Response(201, json={})
        raise AssertionError(f"unexpected Vercel call {path}")

    def app(self, request: httpx.Request) -> httpx.Response:
        site = f"{request.url.scheme}://{request.url.host}"
        assert site in (STAGED, PRODUCTION)
        if site == STAGED:
            assert request.headers["x-vercel-protection-bypass"] == "bypass"
        else:
            assert "x-vercel-protection-bypass" not in request.headers
        if site in self.broken_sites:
            return httpx.Response(503, json={"detail": "not ready"})
        if request.url.path == "/api/ready" or request.url.path == "/":
            return httpx.Response(200, json={"status": "ready"})
        if request.url.path == "/api/auth/me":
            if request.headers.get("authorization") == "Bearer smoke-token":
                return httpx.Response(200, json={"owner_id": "smoke", "csrf_token": ""})
            return httpx.Response(401, json={"detail": "Sign in first."})
        raise AssertionError(f"unexpected request {request.method} {request.url}")


@pytest.fixture
def hosts() -> FakeHosts:
    return FakeHosts()


def settings(browser_tests: list[str] = PASSING_BROWSER_TESTS) -> Settings:
    return Settings(
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
        e2e_token="e2e-token",
        browser_tests=browser_tests,
        poll_seconds=1,
        checks_timeout_seconds=3,
        deploy_timeout_seconds=5,
    )


def promote(hosts: FakeHosts, browser_tests: list[str] = PASSING_BROWSER_TESTS) -> None:
    client = httpx.Client(transport=httpx.MockTransport(hosts.handle))
    Promotion(client, settings(browser_tests)).run()


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    sleeps: list[float] = []
    monkeypatch.setattr("route_api.promote.time.sleep", sleeps.append)
    return sleeps


def test_a_healthy_release_is_promoted(hosts: FakeHosts) -> None:
    promote(hosts)
    assert hosts.changes == ["render deploy abc123", "vercel promote dpl-new"]
    assert hosts.check_queries == [httpx.QueryParams({"per_page": "100", "filter": "latest"})]


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "skipped", "neutral"])
def test_a_failed_check_deploys_nothing(hosts: FakeHosts, conclusion: str) -> None:
    hosts.check_polls = [{"api": "success", "web": conclusion, "feasibility": None}]
    with pytest.raises(PromotionStopped, match=f"'web' did not pass \\({conclusion}\\)"):
        promote(hosts)
    assert hosts.changes == []


def test_promotion_waits_for_checks_still_running(hosts: FakeHosts) -> None:
    running = {"api": "success", "web": None, "feasibility": "success"}
    hosts.check_polls = [running, running, dict.fromkeys(REQUIRED, "success")]
    promote(hosts)
    assert len(hosts.check_queries) == 3
    assert hosts.changes == ["render deploy abc123", "vercel promote dpl-new"]


def test_a_check_still_running_at_the_deadline_deploys_nothing(
    hosts: FakeHosts, no_waiting: list[float]
) -> None:
    hosts.check_polls = [{"api": "success", "web": None, "feasibility": None}]
    with pytest.raises(PromotionStopped, match="'web' has not finished; nothing deployed"):
        promote(hosts)
    assert no_waiting == [1, 1, 1]
    assert hosts.changes == []


def test_a_missing_check_deploys_nothing(hosts: FakeHosts) -> None:
    hosts.check_polls = [{"api": "success", "web": "success"}]
    with pytest.raises(PromotionStopped, match="'feasibility' has not finished"):
        promote(hosts)
    assert hosts.changes == []


def test_a_passing_check_from_another_app_does_not_count(hosts: FakeHosts) -> None:
    hosts.check_polls = [{"api": "success", "web": "success"}]
    hosts.other_app_checks = {"feasibility": "success"}
    with pytest.raises(PromotionStopped, match="'feasibility' has not finished"):
        promote(hosts)
    assert hosts.changes == []


def test_a_failed_migration_leaves_the_old_release_serving(hosts: FakeHosts) -> None:
    hosts.render_statuses = ["build_in_progress", "update_failed"]
    with pytest.raises(PromotionStopped, match="update_failed; the previous API keeps serving"):
        promote(hosts)
    assert hosts.changes == ["render deploy abc123"]


def test_an_api_deploy_that_never_goes_live_stops_promotion(
    hosts: FakeHosts, no_waiting: list[float]
) -> None:
    hosts.render_statuses = ["build_in_progress"] * 10
    with pytest.raises(PromotionStopped, match="did not go live in time; previous API serving"):
        promote(hosts)
    assert no_waiting == [1] * 5
    assert hosts.changes == ["render deploy abc123"]


def test_a_failed_staged_smoke_test_rolls_the_api_back(hosts: FakeHosts) -> None:
    hosts.broken_sites.add(STAGED)
    with pytest.raises(
        PromotionStopped, match=r"staged checks failed \(readiness answered 503\); API rolled back"
    ):
        promote(hosts)
    assert hosts.changes == ["render deploy abc123", "render rollback dep-old"]


def test_failed_staged_browser_tests_roll_the_api_back_and_promote_nothing(
    hosts: FakeHosts,
) -> None:
    with pytest.raises(
        PromotionStopped, match=r"browser tests failed \(exit 3\)\); API rolled back"
    ):
        promote(hosts, browser_tests_exiting(3))
    assert hosts.changes == ["render deploy abc123", "render rollback dep-old"]


def test_the_browser_tests_see_the_staged_page_but_no_provider_token(
    hosts: FakeHosts, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RENDER_API_KEY", "rnd")
    monkeypatch.setenv("SMOKE_TOKEN", "smoke-token")
    monkeypatch.setenv("VERCEL_TOKEN", "vc")
    monkeypatch.setenv("CI", "true")
    check_env = (
        "import os; e = os.environ;"
        f"assert e['STAGED_URL'] == {STAGED!r}, e;"
        "assert e['VERCEL_AUTOMATION_BYPASS_SECRET'] == 'bypass';"
        "assert e['E2E_TOKEN'] == 'e2e-token';"
        "assert 'SMOKE_TOKEN' not in e;"
        "assert 'VERCEL_TOKEN' not in e;"
        "assert e['CI'] == 'true';"
        "assert 'RENDER_API_KEY' not in e;"
        "assert os.path.basename(os.getcwd()) == 'web'"
    )
    promote(hosts, [sys.executable, "-c", check_env])
    assert hosts.changes == ["render deploy abc123", "vercel promote dpl-new"]


def test_a_failed_production_smoke_test_rolls_both_back(hosts: FakeHosts) -> None:
    hosts.broken_sites.add(PRODUCTION)
    with pytest.raises(
        PromotionStopped,
        match=r"production smoke test failed .*; page rolled back, API rolled back",
    ):
        promote(hosts)
    assert hosts.changes == [
        "render deploy abc123",
        "vercel promote dpl-new",
        "vercel rollback dpl-old",
        "render rollback dep-old",
    ]


def test_the_first_release_has_nothing_to_roll_back_to(hosts: FakeHosts) -> None:
    hosts.render_deploys = [{"deploy": {"id": "dep-x", "status": "build_failed"}}]
    hosts.production_page = None
    hosts.broken_sites.add(PRODUCTION)
    with pytest.raises(
        PromotionStopped,
        match="no earlier page to roll back to, no earlier API to roll back to",
    ):
        promote(hosts)
    assert hosts.changes == ["render deploy abc123", "vercel promote dpl-new"]


def test_an_anonymous_answer_other_than_401_fails_the_smoke_test(hosts: FakeHosts) -> None:
    open_door = hosts.app

    def anonymous_allowed(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/me" and "authorization" not in request.headers:
            return httpx.Response(200, json={"owner_id": "anyone", "csrf_token": ""})
        return open_door(request)

    hosts.app = anonymous_allowed  # type: ignore[method-assign]
    with pytest.raises(PromotionStopped, match=r"an anonymous request answered 200\)"):
        promote(hosts)


def test_an_unreachable_site_fails_the_smoke_test(hosts: FakeHosts) -> None:
    serving = hosts.app

    def unreachable_page(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            raise httpx.ConnectError("refused", request=request)
        return serving(request)

    hosts.app = unreachable_page  # type: ignore[method-assign]
    with pytest.raises(PromotionStopped, match=r"\(ConnectError\); API rolled back"):
        promote(hosts)


def test_settings_come_from_the_workflow_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "GITHUB_REPOSITORY": "tomjwright/agentic-system",
        "COMMIT_SHA": "abc123",
        "REQUIRED_CHECKS": "api,web,feasibility",
        "GITHUB_TOKEN": "gh",
        "RENDER_API_KEY": "rnd",
        "RENDER_SERVICE_ID": "srv-api",
        "VERCEL_TOKEN": "vc",
        "VERCEL_PROJECT_ID": "prj",
        "STAGED_URL": STAGED,
        "PRODUCTION_URL": PRODUCTION,
        "VERCEL_AUTOMATION_BYPASS_SECRET": "bypass",
        "SMOKE_TOKEN": "smoke-token",
        "E2E_TOKEN": "e2e-token",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    loaded = settings_from_env()
    assert loaded.required_checks == REQUIRED
    assert loaded.browser_tests == [
        "npx",
        "playwright",
        "test",
        "--config",
        "playwright.staged.config.ts",
    ]
    assert (loaded.poll_seconds, loaded.checks_timeout_seconds) == (10, 3600)
    assert loaded.deploy_timeout_seconds == 1200
    assert loaded.smoke_token == "smoke-token"
    assert loaded.e2e_token == "e2e-token"
