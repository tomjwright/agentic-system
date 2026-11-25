"""Run the API with OneMap, HeiGIT and GitHub replaced by recorded or fake responses, and the
route agent's models by scripted fakes (`AGENT_SCRIPT`, `JUDGE_SCRIPT`), for the browser tests.
"Sign in with GitHub" goes to a fake authorize page that signs Tom in. With E2E_TOKEN_SHA256
set, the staged browser test's e2e owner signs in by bearer token instead
(web/playwright.staged.config.ts), starting with none of its earlier route requests.

Run: uv run python -m tests.serve_recorded (needs DATABASE_URL, migrated)
"""

import os
from urllib.parse import urlencode

import httpx
import uvicorn
from fastapi.responses import RedirectResponse
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from route_api.agent_models import Interpretation, Verdict
from route_api.auth import E2E_OWNER, Auth, GitHubOAuth
from route_api.contracts import DistanceTarget
from route_api.db import RouteRequestRecord
from route_api.heigit import Heigit
from route_api.llm import Models
from route_api.logs import configure_logging
from route_api.main import create_app
from route_api.onemap import OneMap
from route_api.restrictions import load_restricted_ways
from tests import recorded_heigit
from tests.conftest import TOM_GITHUB_ID
from tests.fake_models import FakeModel
from tests.recorded_onemap import recorded_response
from tests.test_auth import github_user

# Each reply answers every prompt holding its key (web/e2e/assistant.spec.ts sends the briefs).
AGENT_SCRIPT = {
    "a 10k run": Interpretation(
        activity="running", distance=DistanceTarget(kind="target", target_km=10)
    ),
    "5k is fine": Interpretation(
        activity="running", distance=DistanceTarget(kind="target", target_km=5)
    ),
    '"reason":"conflict"': "Your form says 5 km but your message says 10 km. Which would you like?",
    '"outcome":"route"': "Here is a 5.26 km running loop from Avenue South Residence.",
}
JUDGE_SCRIPT = {"Reply to check": Verdict(approved=True, reasons=[])}


def main() -> None:
    configure_logging()
    recorded = httpx.Client(transport=httpx.MockTransport(recorded_response))
    onemap = OneMap(recorded, token="recorded-responses")
    engine = create_engine(os.environ["DATABASE_URL"])
    heigit_http = httpx.Client(transport=httpx.MockTransport(recorded_heigit.recorded_response))
    heigit = Heigit(heigit_http, api_key="recorded-responses", request_gap_seconds=0)
    app_origin = os.environ["APP_ORIGIN"]
    github = GitHubOAuth(
        httpx.Client(transport=github_user(TOM_GITHUB_ID)),
        client_id="recorded-client",
        client_secret="recorded-secret",
        callback_url=f"{app_origin}/api/auth/callback",
        allowed_ids={TOM_GITHUB_ID},
        authorize_url="/api/fake-github/authorize",
    )
    # Every browser test signs in as Tom, so the per-owner limits are raised (test_auth.py
    # covers them).
    e2e_token_sha256 = os.environ.get("E2E_TOKEN_SHA256")
    if e2e_token_sha256:
        with Session(engine) as session, session.begin():
            session.execute(
                delete(RouteRequestRecord).where(RouteRequestRecord.owner_id == E2E_OWNER)
            )
    auth = Auth(
        engine,
        github,
        app_origin,
        e2e_token_sha256=e2e_token_sha256,
        requests_per_minute=10_000,
        runs_per_day=10_000,
    )
    models = Models(
        agent=FakeModel(replies_by_text=AGENT_SCRIPT),
        judge=FakeModel(replies_by_text=JUDGE_SCRIPT),
        agent_name="fake:scripted-agent",
        judge_name="fake:scripted-judge",
    )
    app = create_app(
        onemap, engine, auth, heigit=heigit, restricted_ways=load_restricted_ways(), models=models
    )

    @app.get("/api/fake-github/authorize")
    def fake_authorize(state: str) -> RedirectResponse:
        query = urlencode({"code": "good-code", "state": state})
        return RedirectResponse("/api/auth/callback?" + query)

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8001")), access_log=False)


if __name__ == "__main__":
    main()
