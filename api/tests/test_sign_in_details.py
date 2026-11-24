"""Sign-in details the HTTP tests do not see: the exact requests sent to GitHub, the
refusal messages, the request-limit window and the configuration read from the
environment. Mutation testing (the mutation job in ci.yml) found each gap."""

import base64
import hashlib
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import Engine, update
from sqlalchemy.orm import Session

from route_api import auth
from route_api.auth import (
    AUTHORIZE_URL,
    AuthError,
    GitHubOAuth,
    RequestLimit,
    auth_from_env,
    create_session,
)
from route_api.db import GenerationRunRecord
from tests.conftest import FAKE_GITHUB_SECRET, TOM_GITHUB_ID, api_with, as_owner
from tests.recorded_onemap import recorded_response
from tests.test_auth import STRANGER_ID, anonymous, client_for

CALLBACK_URL = "https://testserver/api/auth/callback"
# The worked example in RFC 7636 appendix B.
RFC_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
RFC_CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
TIMEOUT_10_S = {"connect": 10, "read": 10, "write": 10, "pool": 10}


def oauth_answering(
    handle: httpx.MockTransport, client_secret: str | None = FAKE_GITHUB_SECRET
) -> GitHubOAuth:
    return GitHubOAuth(
        httpx.Client(transport=handle),
        client_id="test-client-id",
        client_secret=client_secret,
        callback_url=CALLBACK_URL,
        allowed_ids={TOM_GITHUB_ID},
    )


def github_recording(sent: list[httpx.Request], user_id: int) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "gho_synthetic"})
        return httpx.Response(200, json={"id": user_id})

    return httpx.MockTransport(handle)


def unreachable(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("GitHub is down")


def no_token(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"error": "bad_verification_code"})


def test_the_login_url_names_this_app_and_carries_the_pkce_challenge() -> None:
    oauth = oauth_answering(httpx.MockTransport(no_token))

    url = urlparse(oauth.login_url("some-state", RFC_VERIFIER))

    assert f"{url.scheme}://{url.netloc}{url.path}" == AUTHORIZE_URL
    assert parse_qs(url.query) == {
        "client_id": ["test-client-id"],
        "redirect_uri": [CALLBACK_URL],
        "state": ["some-state"],
        "code_challenge": [RFC_CHALLENGE],
        "code_challenge_method": ["S256"],
        "allow_signup": ["false"],
    }


def test_the_challenge_github_saw_matches_the_verifier_sent_with_the_code(
    clean_engine: Engine,
) -> None:
    sent: list[httpx.Request] = []
    api = anonymous(
        api_with(
            clean_engine,
            httpx.MockTransport(recorded_response),
            "t",
            github=github_recording(sent, TOM_GITHUB_ID),
        )
    )
    login = api.get("/api/auth/login", follow_redirects=False)
    query = parse_qs(urlparse(login.headers["location"]).query)
    api.get("/api/auth/callback", params={"code": "c", "state": query["state"][0]})

    verifier = parse_qs(sent[0].content.decode())["code_verifier"][0]
    digest = hashlib.sha256(verifier.encode()).digest()
    assert query["code_challenge"] == [base64.urlsafe_b64encode(digest).decode().rstrip("=")]


def test_the_code_is_swapped_with_this_apps_credentials_then_the_user_is_asked_for() -> None:
    sent: list[httpx.Request] = []
    oauth = oauth_answering(github_recording(sent, TOM_GITHUB_ID), client_secret=FAKE_GITHUB_SECRET)

    assert oauth.allowed_user_id("the-code", RFC_VERIFIER) == TOM_GITHUB_ID

    token_request, user_request = sent
    assert str(token_request.url) == auth.TOKEN_URL
    assert parse_qs(token_request.content.decode()) == {
        "client_id": ["test-client-id"],
        "client_secret": [FAKE_GITHUB_SECRET],
        "code": ["the-code"],
        "redirect_uri": [CALLBACK_URL],
        "code_verifier": [RFC_VERIFIER],
    }
    assert token_request.headers["Accept"] == "application/json"
    assert token_request.extensions["timeout"] == TIMEOUT_10_S
    assert str(user_request.url) == auth.USER_URL
    assert user_request.headers["Authorization"] == "Bearer gho_synthetic"
    assert user_request.headers["Accept"] == "application/json"
    assert user_request.extensions["timeout"] == TIMEOUT_10_S


@pytest.mark.parametrize(
    ("github", "client_secret", "status", "code", "message"),
    [
        (no_token, None, 503, "sign_in_not_configured", "Sign-in is not configured"),
        (no_token, "secret", 403, "not_allowed", "GitHub did not confirm this sign-in"),
        (unreachable, "secret", 502, "sign_in_failed", "GitHub sign-in failed; try again"),
    ],
)
def test_a_sign_in_github_does_not_complete_is_refused_with_a_reason(
    github: Callable[[httpx.Request], httpx.Response],
    client_secret: str | None,
    status: int,
    code: str,
    message: str,
) -> None:
    oauth = oauth_answering(httpx.MockTransport(github), client_secret=client_secret)

    with pytest.raises(AuthError) as refused:
        oauth.allowed_user_id("the-code", RFC_VERIFIER)

    assert (refused.value.status, refused.value.code, str(refused.value)) == (status, code, message)


def test_a_stranger_is_told_this_account_may_not_use_the_app() -> None:
    oauth = oauth_answering(github_recording([], STRANGER_ID))

    with pytest.raises(AuthError) as refused:
        oauth.allowed_user_id("the-code", RFC_VERIFIER)

    assert (refused.value.status, refused.value.code, str(refused.value)) == (
        403,
        "not_allowed",
        "This GitHub account may not use the app",
    )


class Clock:
    now = 1000.0

    def monotonic(self) -> float:
        return self.now


def test_the_request_limit_forgets_a_request_once_it_is_over_60_seconds_old(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = Clock()
    monkeypatch.setattr(time, "monotonic", clock.monotonic)
    limit = RequestLimit(per_minute=1)

    limit.check("tom")
    limit.check("someone-else")
    clock.now = 1060.0
    with pytest.raises(AuthError):
        limit.check("tom")
    clock.now = 1060.5
    limit.check("tom")


def test_a_request_from_another_origin_is_told_why(clean_engine: Engine) -> None:
    api = client_for(clean_engine)

    refused = api.post(
        "/api/places/search", json={"query": "x"}, headers={"Origin": "https://evil.example"}
    )

    assert refused.json()["error"] == {
        "code": "csrf_failed",
        "message": "Requests must come from the app's own page",
    }


def test_a_configured_smoke_token_leaves_cookie_sessions_working(clean_engine: Engine) -> None:
    smoke = hashlib.sha256(b"synthetic-smoke-token").hexdigest()
    api = api_with(
        clean_engine, httpx.MockTransport(recorded_response), "t", smoke_token_sha256=smoke
    )

    me = api.get("/api/auth/me")
    smoke_me = anonymous(api).get(
        "/api/auth/me", headers={"Authorization": "Bearer synthetic-smoke-token"}
    )
    smoke_write = api.post(
        "/api/places/search",
        json={"query": "x"},
        headers={"Authorization": "Bearer synthetic-smoke-token"},
    )

    assert me.json()["owner_id"] == "local-owner"
    assert smoke_me.json() == {"owner_id": "smoke", "csrf_token": ""}
    assert smoke_write.json()["error"] == {
        "code": "read_only",
        "message": "The smoke test may only read",
    }


def test_a_bearer_token_is_ignored_when_no_smoke_token_is_configured(clean_engine: Engine) -> None:
    api = client_for(clean_engine)

    me = api.get("/api/auth/me", headers={"Authorization": "Bearer guessed"})

    assert me.status_code == 200
    assert me.json()["owner_id"] == "local-owner"


def test_a_run_started_over_a_day_ago_no_longer_counts_against_the_daily_limit(
    clean_engine: Engine,
) -> None:
    api = client_for(clean_engine, runs_per_day=1)
    start = {
        "activity": "running",
        "start": {
            "kind": "map",
            "point": {"type": "Point", "coordinates": [103.8291052120283, 1.276629534107344]},
        },
    }
    request_id = api.post("/api/route-requests", json=start).json()["id"]

    def start_run() -> httpx.Response:
        body = {"operation_id": str(uuid.uuid4()), "distance": {"kind": "target", "target_km": 5}}
        response: httpx.Response = api.post(f"/api/route-requests/{request_id}/runs", json=body)
        return response

    assert start_run().status_code == 201
    refused = start_run()
    with Session(clean_engine) as session:
        session.execute(
            update(GenerationRunRecord).values(started_at=datetime.now(UTC) - timedelta(hours=25))
        )
        session.commit()

    assert refused.json()["error"]["message"] == "At most 1 runs a day; try tomorrow"
    assert start_run().status_code == 201


def test_the_environment_configures_sign_in_and_limits(
    clean_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ORIGIN", "https://routes.example")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("OWNER_GITHUB_IDS", "7, 8,")
    monkeypatch.setenv("SMOKE_TOKEN_SHA256", "abc123")
    monkeypatch.setenv("REQUESTS_PER_MINUTE", "5")
    monkeypatch.setenv("RUNS_PER_DAY", "3")

    configured = auth_from_env(clean_engine)

    assert configured.engine is clean_engine
    assert isinstance(configured.github.http, httpx.Client)
    assert configured.app_origin == "https://routes.example"
    assert configured.github.client_id == "client-id"
    assert configured.github.client_secret == "client-secret"
    assert configured.github.allowed_ids == {7, 8}
    assert configured.github.callback_url == "https://routes.example/api/auth/callback"
    assert configured.github.authorize_url == AUTHORIZE_URL
    assert configured.smoke_token_sha256 == "abc123"
    assert configured.limit.per_minute == 5
    assert configured.runs_per_day == 3


def test_without_configuration_only_tom_may_sign_in_locally(
    clean_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in [
        "APP_ORIGIN",
        "GITHUB_CLIENT_ID",
        "GITHUB_CLIENT_SECRET",
        "OWNER_GITHUB_IDS",
        "SMOKE_TOKEN_SHA256",
        "REQUESTS_PER_MINUTE",
        "RUNS_PER_DAY",
    ]:
        monkeypatch.delenv(name, raising=False)

    configured = auth_from_env(clean_engine)

    assert configured.app_origin == "http://127.0.0.1:3000"
    assert configured.github.allowed_ids == {TOM_GITHUB_ID}
    assert configured.github.client_id is None
    assert configured.github.client_secret is None
    assert configured.github.callback_url == "http://127.0.0.1:3000/api/auth/callback"
    assert configured.smoke_token_sha256 is None
    assert configured.limit.per_minute == 60
    assert configured.runs_per_day == 30


def test_an_empty_smoke_token_setting_means_no_smoke_token(
    clean_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SMOKE_TOKEN_SHA256", "")

    assert auth_from_env(clean_engine).smoke_token_sha256 is None


def test_a_change_without_the_csrf_header_is_told_why(clean_engine: Engine) -> None:
    api = client_for(clean_engine)
    del api.headers["X-CSRF-Token"]

    refused = api.post("/api/places/search", json={"query": "x"})

    assert refused.status_code == 403
    assert refused.json()["error"] == {
        "code": "csrf_failed",
        "message": "Missing or wrong CSRF token",
    }


def test_one_owner_reaching_the_request_limit_does_not_block_another(
    clean_engine: Engine,
) -> None:
    api = client_for(clean_engine, requests_per_minute=1)
    other_owner = as_owner(api, f"github:{TOM_GITHUB_ID}")

    assert api.get("/api/auth/me").status_code == 200
    assert api.get("/api/auth/me").status_code == 429
    assert api.get("/api/auth/me", headers=other_owner).status_code == 200


def test_session_and_csrf_tokens_each_carry_256_random_bits(clean_engine: Engine) -> None:
    token, csrf = create_session(clean_engine, "github:1")

    # token_urlsafe(32): 32 random bytes are 43 URL-safe base64 characters.
    assert (len(token), len(csrf)) == (43, 43)
    assert token != csrf
