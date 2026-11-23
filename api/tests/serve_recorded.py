"""Run the API with OneMap, HeiGIT and GitHub replaced by recorded or fake responses, for the
browser tests. "Sign in with GitHub" goes to a fake authorize page that signs Tom in.

Run: uv run python -m tests.serve_recorded (needs DATABASE_URL, migrated)
"""

import os

import httpx
import uvicorn
from fastapi.responses import RedirectResponse
from sqlalchemy import create_engine

from route_api.auth import Auth, GitHubOAuth
from route_api.heigit import Heigit
from route_api.logs import configure_logging
from route_api.main import create_app
from route_api.onemap import OneMap
from route_api.restrictions import load_restricted_ways
from tests import recorded_heigit
from tests.conftest import TOM_GITHUB_ID
from tests.recorded_onemap import recorded_response
from tests.test_auth import github_user


def main() -> None:
    configure_logging()
    recorded = httpx.Client(transport=httpx.MockTransport(recorded_response))
    # Synthetic credentials: the browser tests fail if any of them reaches the browser.
    onemap = OneMap(recorded, token="synthetic-onemap-token-must-not-ship")
    engine = create_engine(os.environ["DATABASE_URL"])
    heigit_http = httpx.Client(transport=httpx.MockTransport(recorded_heigit.recorded_response))
    heigit_key = "synthetic-heigit-key-must-not-ship"
    heigit = Heigit(heigit_http, api_key=heigit_key, request_gap_seconds=0)
    app_origin = os.environ["APP_ORIGIN"]
    github = GitHubOAuth(
        httpx.Client(transport=github_user(TOM_GITHUB_ID)),
        client_id="recorded-client",
        client_secret="synthetic-github-secret-must-not-ship",
        callback_url=f"{app_origin}/api/auth/callback",
        allowed_ids={TOM_GITHUB_ID},
        authorize_url="/api/fake-github/authorize",
    )
    # Every browser test signs in as Tom, so the per-owner limits are raised (test_auth.py
    # covers them).
    auth = Auth(engine, github, app_origin, requests_per_minute=10_000, runs_per_day=10_000)
    app = create_app(onemap, engine, auth, heigit=heigit, restricted_ways=load_restricted_ways())

    @app.get("/api/fake-github/authorize")
    def fake_authorize(state: str) -> RedirectResponse:
        return RedirectResponse(f"/api/auth/callback?code=good-code&state={state}")

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8001")), access_log=False)


if __name__ == "__main__":
    main()
