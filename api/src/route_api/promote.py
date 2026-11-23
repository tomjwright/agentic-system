"""Promote one commit to production, or leave the previous release serving.

Run from the deploy workflow after `vercel deploy --prebuilt --prod --skip-domain` has made a
staged (not yet live) page deployment at STAGED_URL:

    uv run python -m route_api.promote

1. Refuse unless every REQUIRED_CHECKS check run on COMMIT_SHA concluded "success".
2. Deploy the API on Render. Its start command migrates first; if migration or start fails
   Render keeps the previous instance serving, and promotion stops here.
3. Smoke-test the staged page (with the deployment protection bypass) against the new API.
4. Promote the staged page, then smoke-test production.
5. A failed smoke test rolls the API back to its previous live deploy, and the page back to
   its previous production deployment if it was already promoted.

Migrations must only add (expand), so the previous API keeps working on the new schema
while it is still serving or after a rollback (docs/hosting.md).
"""

import os
import sys
import time
from dataclasses import dataclass

import httpx

GITHUB_API = "https://api.github.com"
RENDER_API = "https://api.render.com/v1"
VERCEL_API = "https://api.vercel.com"
RENDER_FAILED = {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}


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
    poll_seconds: float = 10
    deploy_timeout_seconds: float = 20 * 60


class Promotion:
    def __init__(self, http: httpx.Client, settings: Settings):
        self.http = http
        self.settings = settings

    def run(self) -> None:
        s = self.settings
        self.require_checks()
        previous_api = self.live_render_deploy()
        previous_page = self.deployment_id(s.production_url)
        staged_page = self.deployment_id(s.staged_url)
        self.deploy_api()
        bypass = {"x-vercel-protection-bypass": s.vercel_bypass_secret}
        problem = self.smoke(s.staged_url, bypass)
        if problem:
            self.roll_back_api(previous_api)
            raise PromotionStopped(f"staged smoke test failed ({problem}); API rolled back")
        self.vercel("POST", f"/v10/projects/{s.vercel_project_id}/promote/{staged_page}")
        problem = self.smoke(s.production_url, {})
        if problem:
            self.vercel("POST", f"/v1/projects/{s.vercel_project_id}/rollback/{previous_page}")
            self.roll_back_api(previous_api)
            raise PromotionStopped(f"production smoke test failed ({problem}); rolled back")

    def require_checks(self) -> None:
        s = self.settings
        response = self.http.get(
            f"{GITHUB_API}/repos/{s.repository}/commits/{s.commit_sha}/check-runs",
            params={"per_page": 100},
            headers={"Authorization": f"Bearer {s.github_token}"},
        )
        response.raise_for_status()
        conclusions: dict[str, str | None] = {}
        for run in response.json()["check_runs"]:
            conclusions.setdefault(run["name"], run["conclusion"])
        for name in s.required_checks:
            if name not in conclusions:
                raise PromotionStopped(f"required check {name!r} has not run; nothing deployed")
            if conclusions[name] != "success":
                raise PromotionStopped(f"required check {name!r} did not pass; nothing deployed")

    def live_render_deploy(self) -> str:
        for item in self.render("GET", "/deploys", params={"limit": 20}):
            if item["deploy"]["status"] == "live":
                deploy_id: str = item["deploy"]["id"]
                return deploy_id
        raise PromotionStopped("the API has no live deploy to fall back to; nothing deployed")

    def deployment_id(self, url: str) -> str:
        host = url.removeprefix("https://")
        deployment_id: str = self.vercel("GET", f"/v13/deployments/{host}")["id"]
        return deployment_id

    def deploy_api(self) -> None:
        s = self.settings
        deploy = self.render("POST", "/deploys", json={"commitId": s.commit_sha})
        waited = 0.0
        while deploy["status"] != "live":
            if deploy["status"] in RENDER_FAILED:
                raise PromotionStopped(
                    f"API deploy ended {deploy['status']}; the previous API keeps serving"
                )
            if waited >= s.deploy_timeout_seconds:
                raise PromotionStopped("API deploy did not go live in time; previous API serving")
            time.sleep(s.poll_seconds)
            waited += s.poll_seconds
            deploy = self.render("GET", f"/deploys/{deploy['id']}")

    def roll_back_api(self, deploy_id: str) -> None:
        self.render("POST", "/rollback", json={"deployId": deploy_id})

    def smoke(self, base_url: str, headers: dict[str, str]) -> str | None:
        """Signed-in checks a deploy must pass. Returns the first problem, or None."""
        bearer = {**headers, "Authorization": f"Bearer {self.settings.smoke_token}"}
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

    def render(self, method: str, path: str, **kwargs: object) -> dict:  # type: ignore[type-arg]
        url = f"{RENDER_API}/services/{self.settings.render_service_id}{path}"
        headers = {"Authorization": f"Bearer {self.settings.render_api_key}"}
        response = self.http.request(method, url, headers=headers, **kwargs)  # type: ignore[arg-type]
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    def vercel(self, method: str, path: str) -> dict:  # type: ignore[type-arg]
        headers = {"Authorization": f"Bearer {self.settings.vercel_token}"}
        response = self.http.request(method, f"{VERCEL_API}{path}", headers=headers)
        response.raise_for_status()
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
