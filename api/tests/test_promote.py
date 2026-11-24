"""Deploy gate: promotion refuses on missing or failed checks, and recovers from bad deploys.

GitHub, Render, Vercel and the deployed app are one fake transport that records every
state-changing call, so each test can say exactly what was (and was not) changed. The staged
browser tests are a small Python command that passes or fails.
"""

import json
import sys
from typing import ClassVar

import httpx
import pytest

from route_api import promote as promote_module
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
        self.rollback_statuses = ["update_in_progress", "live"]
        self.refused: set[str] = set()
        # Polls of the production domain that still show the outgoing page after a switch.
        self.switch_polls = 0
        self.switching_to: str | None = None
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
            return self.vercel(request, path)
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
        if path == "/deploys/dep-new" and request.method == "GET":
            return httpx.Response(
                200, json={"id": "dep-new", "status": self.render_statuses.pop(0)}
            )
        if path == "/deploys/dep-new/cancel" and request.method == "POST":
            self.changes.append("render cancel dep-new")
            return httpx.Response(200, json={"id": "dep-new", "status": "canceled"})
        if path == "/rollback" and request.method == "POST":
            self.changes.append(f"render rollback {json.loads(request.content)['deployId']}")
            if "render rollback" in self.refused:
                return httpx.Response(409, json={"message": "cannot roll back"})
            return httpx.Response(201, json={"id": "dep-rollback", "status": "created"})
        if path == "/deploys/dep-rollback" and request.method == "GET":
            return httpx.Response(
                200, json={"id": "dep-rollback", "status": self.rollback_statuses.pop(0)}
            )
        raise AssertionError(f"unexpected Render call {request.method} {path}")

    def vercel(self, request: httpx.Request, path: str) -> httpx.Response:
        if path.startswith("/v13/deployments/"):
            assert request.method == "GET"
        else:
            assert request.method == "POST"
        if path == "/v13/deployments/routes.vercel.app":
            if self.switching_to is not None:
                if self.switch_polls == 0:
                    self.production_page = self.switching_to
                    self.switching_to = None
                else:
                    self.switch_polls -= 1
            if self.production_page is None:
                return httpx.Response(404, json={"error": {"code": "not_found"}})
            return httpx.Response(200, json={"id": self.production_page})
        if path == "/v13/deployments/stage-abc.vercel.app":
            return httpx.Response(200, json={"id": "dpl-new"})
        if path.startswith(("/v10/projects/prj/promote/", "/v1/projects/prj/rollback/")):
            action, deployment = path.split("/")[4], path.split("/")[-1]
            self.changes.append(f"vercel {action} {deployment}")
            if f"vercel {action}" in self.refused:
                return httpx.Response(403, json={"error": {"code": "forbidden"}})
            self.switching_to = deployment
            # Vercel answers both with an empty body, then moves the domain shortly after.
            return httpx.Response(201)
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
    with pytest.raises(
        PromotionStopped,
        match=r"^API deploy did not go live in time and was canceled; previous API serving$",
    ):
        promote(hosts)
    assert no_waiting == [1] * 5
    assert hosts.changes == ["render deploy abc123", "render cancel dep-new"]


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


def test_signing_in_as_someone_other_than_smoke_fails_the_smoke_test(hosts: FakeHosts) -> None:
    serving = hosts.app

    def wrong_owner(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/me" and "authorization" in request.headers:
            return httpx.Response(200, json={"owner_id": "e2e", "csrf_token": ""})
        return serving(request)

    hosts.app = wrong_owner  # type: ignore[method-assign]
    with pytest.raises(PromotionStopped, match="staged checks failed"):
        promote(hosts)
    assert hosts.changes == ["render deploy abc123", "render rollback dep-old"]


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
    assert (loaded.repository, loaded.commit_sha) == ("tomjwright/agentic-system", "abc123")
    assert (loaded.github_token, loaded.render_api_key) == ("gh", "rnd")
    assert (loaded.render_service_id, loaded.vercel_token) == ("srv-api", "vc")
    assert (loaded.vercel_project_id, loaded.vercel_bypass_secret) == ("prj", "bypass")
    assert (loaded.staged_url, loaded.production_url) == (STAGED, PRODUCTION)
    assert (loaded.smoke_token, loaded.e2e_token) == ("smoke-token", "e2e-token")
    assert loaded.browser_tests == [
        "npx",
        "playwright",
        "test",
        "--config",
        "playwright.staged.config.ts",
    ]
    assert (loaded.browser_tests_dir / "playwright.staged.config.ts").is_file()
    assert (loaded.poll_seconds, loaded.checks_timeout_seconds) == (10, 3600)
    assert loaded.deploy_timeout_seconds == 1200
    assert loaded.smoke_token == "smoke-token"
    assert loaded.e2e_token == "e2e-token"


class RecordedPromotion:
    clients: ClassVar[list[httpx.Client]] = []
    stop_with: ClassVar[str | None] = None

    def __init__(self, client: httpx.Client, loaded: Settings) -> None:
        assert loaded == settings()
        self.clients.append(client)

    def run(self) -> None:
        if self.stop_with is not None:
            raise PromotionStopped(self.stop_with)


@pytest.mark.parametrize(
    ("stop_with", "printed", "exit_code"),
    [(None, "Promoted\n", None), ("checks failed", "Not promoted: checks failed\n", 1)],
)
def test_main_runs_the_promotion_and_exits_1_when_it_stops(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stop_with: str | None,
    printed: str,
    exit_code: int | None,
) -> None:
    monkeypatch.setattr(promote_module, "settings_from_env", settings)
    monkeypatch.setattr(promote_module, "Promotion", RecordedPromotion)
    RecordedPromotion.clients = []
    RecordedPromotion.stop_with = stop_with
    if exit_code is None:
        promote_module.main()
    else:
        with pytest.raises(SystemExit) as stopped:
            promote_module.main()
        assert stopped.value.code == exit_code
    assert capsys.readouterr().out == printed
    assert [client.timeout for client in RecordedPromotion.clients] == [httpx.Timeout(30)]


def test_production_is_smoke_tested_only_once_it_serves_the_new_page(
    hosts: FakeHosts, no_waiting: list[float]
) -> None:
    hosts.switch_polls = 2
    served: list[str | None] = []
    serving = hosts.app

    def record_page(request: httpx.Request) -> httpx.Response:
        if request.url.host == "routes.vercel.app":
            served.append(hosts.production_page)
        return serving(request)

    hosts.app = record_page  # type: ignore[method-assign]
    promote(hosts)
    assert set(served) == {"dpl-new"}
    assert no_waiting == [1] * (3 + 2)  # three Render polls, then two of the domain
    assert hosts.changes == ["render deploy abc123", "vercel promote dpl-new"]


def test_a_domain_that_never_switches_rolls_both_back(
    hosts: FakeHosts, no_waiting: list[float]
) -> None:
    hosts.switch_polls = 100
    with pytest.raises(
        PromotionStopped,
        match=r"did not switch to the staged page in time\); page rolled back, API rolled back$",
    ):
        promote(hosts)
    assert hosts.changes == [
        "render deploy abc123",
        "vercel promote dpl-new",
        "vercel rollback dpl-old",
        "render rollback dep-old",
    ]


def test_a_refused_promotion_rolls_the_api_back(hosts: FakeHosts) -> None:
    hosts.refused.add("vercel promote")
    with pytest.raises(
        PromotionStopped,
        match=r"^Vercel refused the promotion \(HTTPStatusError\); page unchanged, "
        r"API rolled back$",
    ):
        promote(hosts)
    assert hosts.changes == [
        "render deploy abc123",
        "vercel promote dpl-new",
        "render rollback dep-old",
    ]


def test_a_refused_page_rollback_still_rolls_the_api_back(hosts: FakeHosts) -> None:
    hosts.broken_sites.add(PRODUCTION)
    hosts.refused.add("vercel rollback")
    with pytest.raises(
        PromotionStopped,
        match=r"PAGE ROLLBACK FAILED \(HTTPStatusError\), API rolled back$",
    ):
        promote(hosts)
    assert hosts.changes[-1] == "render rollback dep-old"


@pytest.mark.parametrize("ending", ["update_failed", "build_failed"])
def test_a_failed_api_rollback_is_reported(hosts: FakeHosts, ending: str) -> None:
    hosts.broken_sites.add(STAGED)
    hosts.rollback_statuses = ["update_in_progress", ending]
    with pytest.raises(
        PromotionStopped,
        match=f"API ROLLBACK FAILED \\({ending}\\); the new API may still be serving$",
    ):
        promote(hosts)


def test_an_api_rollback_still_running_at_the_deadline_is_reported(
    hosts: FakeHosts, no_waiting: list[float]
) -> None:
    hosts.broken_sites.add(STAGED)
    hosts.rollback_statuses = ["update_in_progress"] * 10
    with pytest.raises(PromotionStopped, match=r"API ROLLBACK FAILED \(update_in_progress\)"):
        promote(hosts)


def test_a_refused_api_rollback_is_reported(hosts: FakeHosts) -> None:
    hosts.broken_sites.add(STAGED)
    hosts.refused.add("render rollback")
    with pytest.raises(
        PromotionStopped,
        match=r"API ROLLBACK FAILED \(HTTPStatusError\); the new API may still be serving$",
    ):
        promote(hosts)
