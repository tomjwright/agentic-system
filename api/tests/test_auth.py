"""Sign-in and abuse limits, through the HTTP API (approved seam 1).

GitHub is replaced by an httpx.MockTransport that plays its OAuth token and user endpoints.
"""

import hashlib
import json
import uuid
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text, update
from sqlalchemy.orm import Session

from route_api.auth import auth_from_env, create_session
from route_api.db import GenerationRunRecord
from tests.conftest import FAKE_TOKEN, TOM_GITHUB_ID, api_with, as_owner
from tests.recorded_onemap import recorded_response

OTHER_ALLOWED_ID = 2
STRANGER_ID = 999
PUBLIC_PATHS = {"/api/health", "/api/ready", "/api/auth/login", "/api/auth/callback"}
SMOKE_TOKEN = "synthetic-smoke-token"
E2E_TOKEN = "synthetic-e2e-token"
STAGED_ORIGIN = "https://agentic-system-abc123.vercel.app"


def github_user(user_id: int) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            form = parse_qs(request.content.decode())
            if form.get("code") != ["good-code"] or not form.get("code_verifier"):
                return httpx.Response(200, json={"error": "bad_verification_code"})
            return httpx.Response(200, json={"access_token": "gho_synthetic"})
        if request.url.path == "/user":
            assert request.headers["Authorization"] == "Bearer gho_synthetic"
            return httpx.Response(200, json={"id": user_id, "login": "tomjwright"})
        return httpx.Response(404)

    return httpx.MockTransport(handle)


def client_for(
    engine: Engine,
    user_id: int = TOM_GITHUB_ID,
    requests_per_minute: int = 1000,
    runs_per_day: int = 1000,
) -> TestClient:
    return api_with(
        engine,
        httpx.MockTransport(recorded_response),
        "t",
        github=github_user(user_id),
        requests_per_minute=requests_per_minute,
        runs_per_day=runs_per_day,
    )


def sign_in(api: TestClient, code: str = "good-code") -> httpx.Response:
    login = api.get("/api/auth/login", follow_redirects=False)
    assert login.status_code == 302
    query = parse_qs(urlparse(login.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert "scope" not in query
    callback: httpx.Response = api.get(
        "/api/auth/callback",
        params={"code": code, "state": query["state"][0]},
        follow_redirects=False,
    )
    return callback


def anonymous(api: TestClient) -> TestClient:
    api.headers.clear()
    api.cookies.clear()
    return api


def call(api: TestClient, route: APIRoute, headers: dict[str, str]) -> httpx.Response:
    path = route.path.replace("{route_request_id}", str(uuid.uuid4()))
    path = path.replace("{run_id}", str(uuid.uuid4()))
    method = sorted(route.methods or [])[0]
    response: httpx.Response = api.request(method, path, json={}, headers=headers)
    return response


def protected_routes(api: TestClient) -> list[APIRoute]:
    routes = [route for route in api.app.routes if isinstance(route, APIRoute)]  # type: ignore[attr-defined]
    return [route for route in routes if route.path not in PUBLIC_PATHS]


def test_tom_signs_in_with_github_and_gets_a_session(clean_engine: Engine) -> None:
    api = anonymous(client_for(clean_engine))
    callback = sign_in(api)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/"
    cookies = callback.headers.get_list("set-cookie")
    [cookie] = [c for c in cookies if c.startswith("__Host-route-session=")]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
    me = api.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["owner_id"] == f"github:{TOM_GITHUB_ID}"
    assert "gho_synthetic" not in callback.text + me.text


def test_a_github_account_outside_the_allowlist_gets_no_session(clean_engine: Engine) -> None:
    api = anonymous(client_for(clean_engine, user_id=STRANGER_ID))
    callback = sign_in(api)
    assert callback.status_code == 403
    assert callback.json()["error"]["code"] == "not_allowed"
    assert "route-session" not in str(callback.headers.get_list("set-cookie"))
    assert api.get("/api/auth/me").status_code == 401


def test_a_callback_with_a_forged_state_or_bad_code_is_refused(clean_engine: Engine) -> None:
    api = anonymous(client_for(clean_engine))
    api.get("/api/auth/login", follow_redirects=False)
    forged = api.get("/api/auth/callback", params={"code": "good-code", "state": "forged"})
    assert forged.status_code == 400
    assert sign_in(api, code="stolen").status_code == 403
    assert api.get("/api/auth/me").status_code == 401


def test_every_endpoint_refuses_a_missing_or_invalid_session(clean_engine: Engine) -> None:
    api = anonymous(client_for(clean_engine))
    for route in protected_routes(api):
        for headers in [{}, {"Cookie": "__Host-route-session=made-up"}, {"X-Owner-Id": "tom"}]:
            response = call(api, route, headers)
            assert response.status_code == 401, (route.path, headers)
            assert response.json() == {
                "error": {"code": "not_signed_in", "message": "Sign in first"}
            }


def test_a_signed_out_session_stops_working(clean_engine: Engine) -> None:
    api = anonymous(client_for(clean_engine))
    sign_in(api)
    csrf = api.get("/api/auth/me").json()["csrf_token"]
    session = api.cookies["__Host-route-session"]
    assert api.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    replayed = api.get("/api/auth/me", headers={"Cookie": f"__Host-route-session={session}"})
    assert replayed.status_code == 401


def test_an_owner_taken_off_the_allowlist_is_refused_by_every_instance(
    clean_engine: Engine,
) -> None:
    # During a deploy the old instance, still on the old allowlist, can sign in an owner
    # the new allowlist removed; the new instance must refuse that session.
    removed, _ = create_session(clean_engine, f"github:{OTHER_ALLOWED_ID}")
    kept, _ = create_session(clean_engine, f"github:{TOM_GITHUB_ID}")
    api = anonymous(
        api_with(
            clean_engine,
            httpx.MockTransport(recorded_response),
            FAKE_TOKEN,
            allowed_ids=frozenset({TOM_GITHUB_ID}),
        )
    )
    for token, status in [(removed, 401), (kept, 200)]:
        me = api.get("/api/auth/me", headers={"Cookie": f"__Host-route-session={token}"})
        assert me.status_code == status


def test_starting_the_api_ends_sessions_of_owners_no_longer_allowed(
    clean_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    removed, _ = create_session(clean_engine, f"github:{OTHER_ALLOWED_ID}")
    kept, _ = create_session(clean_engine, f"github:{TOM_GITHUB_ID}")
    monkeypatch.setenv("OWNER_GITHUB_IDS", str(TOM_GITHUB_ID))
    auth_from_env(clean_engine)
    api = anonymous(client_for(clean_engine))
    for token, status in [(removed, 401), (kept, 200)]:
        me = api.get("/api/auth/me", headers={"Cookie": f"__Host-route-session={token}"})
        assert me.status_code == status


def test_a_cookie_without_the_csrf_token_cannot_change_anything(clean_engine: Engine) -> None:
    api = client_for(clean_engine)
    cookie_only = {"Cookie": api.headers["Cookie"], "X-CSRF-Token": ""}
    for route in protected_routes(api):
        if "GET" in (route.methods or []):
            continue
        for csrf in ["", "wrong"]:
            response = call(api, route, {**cookie_only, "X-CSRF-Token": csrf})
            assert response.status_code == 403, route.path
            assert response.json()["error"]["code"] == "csrf_failed"


def test_another_origin_gets_no_cors_access(clean_engine: Engine) -> None:
    api = client_for(clean_engine)
    preflight = api.options(
        "/api/route-requests",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    read = api.get("/api/auth/me", headers={"Origin": "https://evil.example"})
    write = api.post(
        "/api/places/search", json={"query": "x"}, headers={"Origin": "https://evil.example"}
    )
    for response in [preflight, read]:
        assert "access-control-allow-origin" not in response.headers
    assert write.status_code == 403
    assert write.json()["error"]["code"] == "csrf_failed"


def test_an_allowlisted_owner_cannot_see_another_owners_data(clean_engine: Engine) -> None:
    api = client_for(clean_engine)
    start = {
        "activity": "running",
        "start": {"kind": "map", "point": {"type": "Point", "coordinates": [103.8198, 1.3521]}},
    }
    created = api.post("/api/route-requests", json=start).json()
    other = as_owner(api, f"github:{OTHER_ALLOWED_ID}")
    response = api.get(f"/api/route-requests/{created['id']}", headers=other)
    assert response.status_code == 404
    assert created["id"] not in response.text


def test_too_many_requests_are_refused_without_data(clean_engine: Engine) -> None:
    api = client_for(clean_engine, requests_per_minute=3)
    for _ in range(3):
        assert api.get("/api/auth/me").status_code == 200
    refused = api.get("/api/auth/me")
    assert refused.status_code == 429
    assert refused.json() == {
        "error": {"code": "rate_limited", "message": "Too many requests; wait a minute"}
    }


def test_runs_past_the_daily_spending_limit_are_refused(clean_engine: Engine) -> None:
    api = client_for(clean_engine, runs_per_day=1)
    start = {
        "activity": "running",
        "start": {
            "kind": "map",
            "point": {"type": "Point", "coordinates": [103.8291052120283, 1.276629534107344]},
        },
    }
    request_id = api.post("/api/route-requests", json=start).json()["id"]
    distance = {"kind": "target", "target_km": 5}
    first = api.post(
        f"/api/route-requests/{request_id}/runs",
        json={"operation_id": str(uuid.uuid4()), "distance": distance},
    )
    assert first.status_code == 201
    second = api.post(
        f"/api/route-requests/{request_id}/runs",
        json={"operation_id": str(uuid.uuid4()), "distance": distance},
    )
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "run_limit_reached"


@pytest.mark.parametrize("size", [9000, 100_000])
def test_an_oversized_body_is_refused_before_it_is_read(clean_engine: Engine, size: int) -> None:
    api = client_for(clean_engine)
    response = api.post(
        "/api/places/search",
        content=json.dumps({"query": "x" * size}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_the_smoke_token_can_only_read_as_the_smoke_owner(clean_engine: Engine) -> None:
    api = anonymous(
        api_with(
            clean_engine,
            httpx.MockTransport(recorded_response),
            "t",
            smoke_token_sha256=hashlib.sha256(SMOKE_TOKEN.encode()).hexdigest(),
        )
    )
    bearer = {"Authorization": f"Bearer {SMOKE_TOKEN}"}
    me = api.get("/api/auth/me", headers=bearer)
    assert me.status_code == 200
    assert me.json()["owner_id"] == "smoke"
    write = api.post("/api/places/search", json={"query": "x"}, headers=bearer)
    assert write.status_code == 403
    wrong = api.get("/api/auth/me", headers={"Authorization": "Bearer guessed"})
    assert wrong.status_code == 401


def bearer_client(engine: Engine) -> TestClient:
    """An API with the smoke and e2e tokens configured and no browser session."""
    return anonymous(
        api_with(
            engine,
            httpx.MockTransport(recorded_response),
            "t",
            smoke_token_sha256=hashlib.sha256(SMOKE_TOKEN.encode()).hexdigest(),
            e2e_token_sha256=hashlib.sha256(E2E_TOKEN.encode()).hexdigest(),
            runs_per_day=1000,
        )
    )


def test_the_e2e_token_may_write_as_the_e2e_owner_from_the_staged_page(
    clean_engine: Engine,
) -> None:
    api = bearer_client(clean_engine)
    staged = {"Authorization": f"Bearer {E2E_TOKEN}", "Origin": STAGED_ORIGIN}
    me = api.get("/api/auth/me", headers=staged)
    assert me.status_code == 200
    assert me.json()["owner_id"] == "e2e"
    search = api.post(
        "/api/places/search", json={"query": "avenue south residence"}, headers=staged
    )
    assert search.status_code == 200
    as_smoke = {"Authorization": f"Bearer {SMOKE_TOKEN}", "Origin": STAGED_ORIGIN}
    assert api.get("/api/auth/me", headers=as_smoke).json()["owner_id"] == "smoke"
    refused = api.post("/api/places/search", json={"query": "x"}, headers=as_smoke)
    assert refused.json()["error"]["code"] == "read_only"


def test_a_cookie_session_from_another_origin_is_still_refused_with_bearer_owners_configured(
    clean_engine: Engine,
) -> None:
    api = bearer_client(clean_engine)
    cookie = as_owner(api, f"github:{TOM_GITHUB_ID}")
    for origin in [STAGED_ORIGIN, "https://evil.example"]:
        write = api.post(
            "/api/places/search",
            json={"query": "x"},
            headers={**cookie, "Origin": origin, "Authorization": "Bearer guessed"},
        )
        assert write.status_code == 403
        assert write.json()["error"]["code"] == "csrf_failed"
    no_csrf = api.post(
        "/api/places/search", json={"query": "x"}, headers={"Cookie": cookie["Cookie"]}
    )
    assert no_csrf.json()["error"]["code"] == "csrf_failed"


def test_a_cookie_session_cannot_pose_as_the_e2e_owner(clean_engine: Engine) -> None:
    api = bearer_client(clean_engine)
    me = api.get("/api/auth/me", headers=as_owner(api, "e2e"))
    assert me.status_code == 401


def test_the_e2e_owner_may_start_one_run_every_10_minutes_and_3_a_day(
    clean_engine: Engine,
) -> None:
    api = bearer_client(clean_engine)
    bearer = {"Authorization": f"Bearer {E2E_TOKEN}"}
    start = {
        "activity": "running",
        "start": {
            "kind": "map",
            "point": {"type": "Point", "coordinates": [103.8291052120283, 1.276629534107344]},
        },
    }
    request_id = api.post("/api/route-requests", json=start, headers=bearer).json()["id"]

    def start_run() -> httpx.Response:
        body = {"operation_id": str(uuid.uuid4()), "distance": {"kind": "target", "target_km": 5}}
        response: httpx.Response = api.post(
            f"/api/route-requests/{request_id}/runs", json=body, headers=bearer
        )
        return response

    def age_runs_by(minutes: int) -> None:
        with Session(clean_engine) as session:
            session.execute(
                update(GenerationRunRecord).values(
                    started_at=GenerationRunRecord.started_at - timedelta(minutes=minutes)
                )
            )
            session.commit()

    assert start_run().status_code == 201
    too_soon = start_run()
    assert too_soon.status_code == 429
    assert too_soon.json()["error"] == {
        "code": "run_limit_reached",
        "message": "The e2e owner may start one run every 10 minutes",
    }
    age_runs_by(9)
    assert start_run().status_code == 429
    age_runs_by(1)
    assert start_run().status_code == 201
    age_runs_by(10)
    assert start_run().status_code == 201
    age_runs_by(10)
    over_the_day = start_run()
    assert over_the_day.status_code == 429
    assert over_the_day.json()["error"]["message"] == "At most 3 runs a day; try tomorrow"
    other = as_owner(api, f"github:{TOM_GITHUB_ID}")
    tom_body = {"operation_id": str(uuid.uuid4()), "distance": {"kind": "target", "target_km": 5}}
    tom_request = api.post("/api/route-requests", json=start, headers=other).json()["id"]
    tom_run = api.post(f"/api/route-requests/{tom_request}/runs", json=tom_body, headers=other)
    assert tom_run.status_code == 201


def test_health_and_readiness_need_no_session(clean_engine: Engine) -> None:
    api = anonymous(client_for(clean_engine))
    assert api.get("/api/health").json() == {"status": "ok"}
    ready = api.get("/api/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready", "database": "ok", "migrations": "current"}


def test_readiness_fails_when_a_provider_is_not_configured(clean_engine: Engine) -> None:
    api = anonymous(api_with(clean_engine, httpx.MockTransport(recorded_response), None))
    ready = api.get("/api/ready")
    assert ready.status_code == 503
    assert ready.json()["status"] == "not_ready"
    assert ready.json()["missing"] == ["ONEMAP_API_TOKEN"]


def test_checking_the_run_budget_holds_the_owner_until_the_run_is_saved(
    clean_engine: Engine,
) -> None:
    auth = auth_from_env(clean_engine)
    lock = text("SELECT pg_try_advisory_xact_lock(hashtext(:owner))")
    with Session(clean_engine) as checking, Session(clean_engine) as concurrent:
        auth.check_run_budget(checking, "e2e")
        assert concurrent.scalar(lock, {"owner": "e2e"}) is False
        assert concurrent.scalar(lock, {"owner": "github:1"}) is True
        concurrent.rollback()
        checking.commit()
        assert concurrent.scalar(lock, {"owner": "e2e"}) is True
