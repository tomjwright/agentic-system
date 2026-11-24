"""Promote one commit to production, or leave the previous release serving.

Run from the deploy workflow after `vercel deploy --prebuilt --prod --skip-domain` has made a
staged (not yet live) page deployment at STAGED_URL:

    uv run python -m route_api.promote

1. Wait for every REQUIRED_CHECKS check run on COMMIT_SHA (from GitHub Actions only) to
   finish, and refuse unless each one concluded "success". Nothing is deployed otherwise.
2. Deploy the API on Render. Its start command migrates first; if migration or start fails
   Render keeps the previous instance serving, and promotion stops here.
3. Smoke-test the staged page (with the deployment protection bypass) against the new API,
   then run the staged browser test (web/playwright.staged.config.ts) against it: one full
   search, generate and GPX download as the e2e owner (E2E_TOKEN), which the API allows one
   run every 10 minutes and 3 a day.
4. Promote the staged page, then smoke-test production.
5. A failed staged check rolls the API back to its previous live deploy; a failed production
   smoke test also rolls the page back to its previous production deployment.

The very first release has no previous API or page; a failure then leaves nothing to roll
back to, and the message says so.

Migrations must only add (expand), so the previous API keeps working on the new schema
while it is still serving or after a rollback (docs/hosting.md).
"""

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

GITHUB_API = "https://api.github.com"
RENDER_API = "https://api.render.com/v1"
VERCEL_API = "https://api.vercel.com"
RENDER_FAILED = {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}


def web_dir() -> Path:
    # Usually three folders up; mutmut runs a copy of this file one folder deeper.
    for folder in Path(__file__).resolve().parents:
        if (folder / "web/playwright.staged.config.ts").is_file():
            return folder / "web"
    raise FileNotFoundError("web/playwright.staged.config.ts not found above " + __file__)


STAGED_BROWSER_TESTS = ["npx", "playwright", "test", "--config", "playwright.staged.config.ts"]
# The only variables the browser tests see; the provider tokens stay with this process.
BROWSER_TEST_ENV = [
    "PATH",
    "HOME",
    "CI",
    "STAGED_URL",
    "VERCEL_AUTOMATION_BYPASS_SECRET",
    "E2E_TOKEN",
]


class PromotionStopped(Exception):
    """Promotion did not happen or was undone; the message says what is serving."""


@dataclass
class Settings:
    repository: str
    commit_sha: str
    required_checks: list[str]
    github_token: str
    render_api_key: str
    render_service_id: str
    vercel_token: str
    vercel_project_id: str
    staged_url: str
    production_url: str
    vercel_bypass_secret: str
    smoke_token: str
    e2e_token: str
    browser_tests: list[str] = field(default_factory=STAGED_BROWSER_TESTS.copy)
    browser_tests_dir: Path = field(default_factory=web_dir)
    poll_seconds: float = 10
    checks_timeout_seconds: float = 60 * 60
    deploy_timeout_seconds: float = 20 * 60


class Promotion:
    def __init__(self, http: httpx.Client, settings: Settings):
        self.http = http
        self.settings = settings

    def run(self) -> None:
        s = self.settings
        self.require_checks()
        previous_api = self.live_render_deploy()
        previous_page = self.production_deployment()
        staged_page = self.deployment_id(s.staged_url)
        self.deploy_api()
        bypass = {"x-vercel-protection-bypass": s.vercel_bypass_secret}
        problem = self.smoke(s.staged_url, bypass)
        if problem is None:
            problem = self.staged_browser_tests()
        if problem:
            undone = self.roll_back_api(previous_api)
            raise PromotionStopped(f"staged checks failed ({problem}); {undone}")
        try:
            self.vercel("POST", f"/v10/projects/{s.vercel_project_id}/promote/{staged_page}")
        except httpx.HTTPError as error:
            undone = self.roll_back_api(previous_api)
            raise PromotionStopped(
                f"Vercel refused the promotion ({type(error).__name__}); page unchanged, {undone}"
            ) from error
        # Smoke-test production only once its domain serves the new page, not the outgoing one.
        problem = None
        if not self.production_serves(staged_page):
            problem = "the production domain did not switch to the staged page in time"
        if problem is None:
            problem = self.smoke(s.production_url, {})
        if problem:
            page_undone = self.roll_back_page(previous_page)
            api_undone = self.roll_back_api(previous_api)
            raise PromotionStopped(
                f"production smoke test failed ({problem}); {page_undone}, {api_undone}"
            )

    def roll_back_page(self, previous_page: str | None) -> str:
        if previous_page is None:
            return "no earlier page to roll back to"
        s = self.settings
        try:
            self.vercel("POST", f"/v1/projects/{s.vercel_project_id}/rollback/{previous_page}")
        except httpx.HTTPError as error:
            return f"PAGE ROLLBACK FAILED ({type(error).__name__})"
        if not self.production_serves(previous_page):
            return "PAGE ROLLBACK FAILED (production still serves the new page)"
        return "page rolled back"

    def production_serves(self, deployment_id: str) -> bool:
        waited = 0.0
        while self.production_deployment() != deployment_id:
            if waited >= self.settings.deploy_timeout_seconds:
                return False
            time.sleep(self.settings.poll_seconds)
            waited += self.settings.poll_seconds
        return True

    def require_checks(self) -> None:
        s = self.settings
        waited = 0.0
        while True:
            try:
                conclusions = self.check_conclusions()
            except (httpx.TransportError, httpx.HTTPStatusError) as error:
                # A network error or GitHub 5xx is asked again; any other refusal stops here.
                if isinstance(error, httpx.HTTPStatusError) and error.response.status_code < 500:
                    raise
                if waited >= s.checks_timeout_seconds:
                    raise PromotionStopped(
                        f"could not read the checks ({type(error).__name__}); nothing deployed"
                    ) from error
                time.sleep(s.poll_seconds)
                waited += s.poll_seconds
                continue
            unfinished = []
            for name in s.required_checks:
                conclusion = conclusions.get(name)
                if conclusion is None:
                    unfinished.append(name)
                elif conclusion != "success":
                    raise PromotionStopped(
                        f"required check {name!r} did not pass ({conclusion}); nothing deployed"
                    )
            if not unfinished:
                return
            if waited >= s.checks_timeout_seconds:
                raise PromotionStopped(
                    f"required check {unfinished[0]!r} has not finished; nothing deployed"
                )
            time.sleep(s.poll_seconds)
            waited += s.poll_seconds

    def check_conclusions(self) -> dict[str, str | None]:
        """The latest conclusion of each check run on the commit, None while it runs. Only
        GitHub Actions runs count, so no other app can post a passing check by that name."""
        s = self.settings
        response = self.http.get(
            f"{GITHUB_API}/repos/{s.repository}/commits/{s.commit_sha}/check-runs",
            params={"per_page": 100, "filter": "latest"},
            headers={"authorization": f"Bearer {s.github_token}"},
        )
        response.raise_for_status()
        conclusions: dict[str, str | None] = {}
        for run in response.json()["check_runs"]:
            if run["app"]["slug"] == "github-actions":
                conclusions.setdefault(run["name"], run["conclusion"])
        return conclusions

    def live_render_deploy(self) -> str | None:
        for item in self.render("GET", "/deploys", params={"limit": 20}):
            if item["deploy"]["status"] == "live":
                deploy_id: str = item["deploy"]["id"]
                return deploy_id
        return None

    def production_deployment(self) -> str | None:
        """The page deployment serving the production domain, or None before the first."""
        host = self.settings.production_url.removeprefix("https://")
        headers = {"authorization": f"Bearer {self.settings.vercel_token}"}
        response = self.http.get(f"{VERCEL_API}/v13/deployments/{host}", headers=headers)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        deployment_id: str = response.json()["id"]
        return deployment_id

    def deployment_id(self, url: str) -> str:
        host = url.removeprefix("https://")
        deployment_id: str = self.vercel("GET", f"/v13/deployments/{host}")["id"]
        return deployment_id

    def deploy_api(self) -> None:
        s = self.settings
        deploy = self.render("POST", "/deploys", json={"commitId": s.commit_sha})
        deploy = self.wait_for_render(deploy)
        if deploy["status"] == "live":
            return
        if deploy["status"] in RENDER_FAILED:
            raise PromotionStopped(
                f"API deploy ended {deploy['status']}; the previous API keeps serving"
            )
        # Left running, Render would put it live later without any staged check.
        self.render("POST", f"/deploys/{deploy['id']}/cancel")
        raise PromotionStopped(
            "API deploy did not go live in time and was canceled; previous API serving"
        )

    def roll_back_api(self, deploy_id: str | None) -> str:
        if deploy_id is None:
            return "no earlier API to roll back to"
        try:
            deploy = self.render("POST", "/rollback", json={"deployId": deploy_id})
            deploy = self.wait_for_render(deploy)
        except httpx.HTTPError as error:
            return f"API ROLLBACK FAILED ({type(error).__name__}); the new API may still be serving"
        if deploy["status"] != "live":
            return f"API ROLLBACK FAILED ({deploy['status']}); the new API may still be serving"
        return "API rolled back"

    def wait_for_render(self, deploy: dict) -> dict:  # type: ignore[type-arg]
        """Polls a Render deploy until it is live, has failed, or the deadline passes."""
        s = self.settings
        waited = 0.0
        while deploy["status"] != "live" and deploy["status"] not in RENDER_FAILED:
            if waited >= s.deploy_timeout_seconds:
                break
            time.sleep(s.poll_seconds)
            waited += s.poll_seconds
            deploy = self.render("GET", f"/deploys/{deploy['id']}")
        return deploy

    def smoke(self, base_url: str, headers: dict[str, str]) -> str | None:
        """Signed-in checks a deploy must pass. Returns the first problem, or None."""
        bearer = {**headers, "authorization": f"Bearer {self.settings.smoke_token}"}
        try:
            ready = self.http.get(f"{base_url}/api/ready", headers=headers, timeout=90)
            if ready.status_code != 200:
                return f"readiness answered {ready.status_code}"
            anonymous = self.http.get(f"{base_url}/api/auth/me", headers=headers)
            if anonymous.status_code != 401:
                return f"an anonymous request answered {anonymous.status_code}"
            me = self.http.get(f"{base_url}/api/auth/me", headers=bearer)
            if me.status_code != 200 or me.json().get("owner_id") != "smoke":
                return f"the smoke owner could not sign in ({me.status_code})"
            page = self.http.get(f"{base_url}/", headers=headers)
            if page.status_code != 200:
                return f"the page answered {page.status_code}"
        except httpx.HTTPError as error:
            return f"{type(error).__name__}"
        return None

    def staged_browser_tests(self) -> str | None:
        """Runs the browser tests against the staged page. Returns the problem, or None."""
        s = self.settings
        env = {
            "STAGED_URL": s.staged_url,
            "VERCEL_AUTOMATION_BYPASS_SECRET": s.vercel_bypass_secret,
            "E2E_TOKEN": s.e2e_token,
        }
        for name in BROWSER_TEST_ENV:
            if name not in env and name in os.environ:
                env[name] = os.environ[name]
        # The command is STAGED_BROWSER_TESTS above; only tests swap it.
        finished = subprocess.run(s.browser_tests, cwd=s.browser_tests_dir, env=env, check=False)  # noqa: S603
        if finished.returncode != 0:
            return f"the staged browser tests failed (exit {finished.returncode})"
        return None

    def render(self, method: str, path: str, **kwargs: object) -> dict:  # type: ignore[type-arg]
        url = f"{RENDER_API}/services/{self.settings.render_service_id}{path}"
        headers = {"authorization": f"Bearer {self.settings.render_api_key}"}
        response = self.http.request(method, url, headers=headers, **kwargs)  # type: ignore[arg-type]
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    def vercel(self, method: str, path: str) -> dict:  # type: ignore[type-arg]
        headers = {"authorization": f"Bearer {self.settings.vercel_token}"}
        response = self.http.request(method, f"{VERCEL_API}{path}", headers=headers)
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()  # type: ignore[no-any-return]


def settings_from_env() -> Settings:
    env = os.environ
    return Settings(
        repository=env["GITHUB_REPOSITORY"],
        commit_sha=env["COMMIT_SHA"],
        required_checks=env["REQUIRED_CHECKS"].split(","),
        github_token=env["GITHUB_TOKEN"],
        render_api_key=env["RENDER_API_KEY"],
        render_service_id=env["RENDER_SERVICE_ID"],
        vercel_token=env["VERCEL_TOKEN"],
        vercel_project_id=env["VERCEL_PROJECT_ID"],
        staged_url=env["STAGED_URL"],
        production_url=env["PRODUCTION_URL"],
        vercel_bypass_secret=env["VERCEL_AUTOMATION_BYPASS_SECRET"],
        smoke_token=env["SMOKE_TOKEN"],
        e2e_token=env["E2E_TOKEN"],
    )


def main() -> None:
    try:
        Promotion(httpx.Client(timeout=30), settings_from_env()).run()
    except PromotionStopped as stopped:
        print(f"Not promoted: {stopped}")
        sys.exit(1)
    print("Promoted")


if __name__ == "__main__":
    main()
