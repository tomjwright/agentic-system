import os
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, make_url, text

from route_api.auth import SESSION_COOKIE, Auth, GitHubOAuth, create_session
from route_api.heigit import Heigit
from route_api.llm import Models
from route_api.main import create_app
from route_api.onemap import OneMap
from route_api.restrictions import load_restricted_ways
from tests import recorded_heigit
from tests.recorded_onemap import recorded_response

# No test sends a trace to LangSmith, whatever the developer's shell sets. LangSmith reads
# these once per process, so they are removed before any test runs.
for tracing_variable in (
    "LANGSMITH_TRACING",
    "LANGSMITH_TRACING_V2",
    "LANGCHAIN_TRACING",
    "LANGCHAIN_TRACING_V2",
):
    os.environ.pop(tracing_variable, None)

# A database the tests may wipe. Never point this at real data.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/routes_test"
)
FAKE_TOKEN = "fake-onemap-token-for-tests"
FAKE_HEIGIT_KEY = "fake-heigit-key-for-tests"
FAKE_GITHUB_SECRET = "fake-github-secret-for-tests"
TOM_GITHUB_ID = 119127762
# Session owners are "github:<id>"; these three ids are on the test allowlist.
TOM = f"github:{TOM_GITHUB_ID}"
SOMEONE = "github:2"
LOCAL_OWNER = "github:3"
API_DIR = Path(__file__).parent.parent
RESTRICTED_WAYS = load_restricted_ways()


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """TEST_DATABASE_URL, or under mutmut, which runs mutants in parallel processes, a
    database of this process's own on the same server."""
    if "MUTANT_UNDER_TEST" not in os.environ:
        yield TEST_DATABASE_URL
        return
    name = f"routes_mutant_{os.getpid()}"
    server = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {name}"))
        connection.execute(text(f"CREATE DATABASE {name}"))
    yield make_url(TEST_DATABASE_URL).set(database=name).render_as_string(hide_password=False)
    with server.connect() as connection:
        connection.execute(text(f"DROP DATABASE {name} WITH (FORCE)"))
    server.dispose()


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def clean_engine(engine: Engine) -> Engine:
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE route_requests, owner_sessions CASCADE"))
    return engine


def api_with(
    engine: Engine,
    handler: httpx.MockTransport,
    token: str | None,
    heigit_handler: Callable[[httpx.Request], httpx.Response] = recorded_heigit.recorded_response,
    heigit_key: str | None = FAKE_HEIGIT_KEY,
    github: httpx.MockTransport | None = None,
    smoke_token_sha256: str | None = None,
    e2e_token_sha256: str | None = None,
    requests_per_minute: int = 1000,
    runs_per_day: int = 1000,
    allowed_ids: frozenset[int] = frozenset({TOM_GITHUB_ID, 2, 3}),
    models: Models | None = None,
) -> TestClient:
    """An API whose providers answer from recordings, signed in as LOCAL_OWNER."""
    onemap = OneMap(httpx.Client(transport=handler), token=token, retry_wait_seconds=0)
    heigit_http = httpx.Client(transport=httpx.MockTransport(heigit_handler))
    heigit = Heigit(heigit_http, heigit_key, request_gap_seconds=0, retry_wait_seconds=0)
    oauth = GitHubOAuth(
        httpx.Client(transport=github or httpx.MockTransport(no_github)),
        client_id="test-client-id",
        client_secret=FAKE_GITHUB_SECRET,
        callback_url="https://testserver/api/auth/callback",
        allowed_ids=set(allowed_ids),
    )
    auth = Auth(
        engine,
        oauth,
        app_origin="https://testserver",
        smoke_token_sha256=smoke_token_sha256,
        e2e_token_sha256=e2e_token_sha256,
        requests_per_minute=requests_per_minute,
        runs_per_day=runs_per_day,
    )
    app = create_app(
        onemap, engine, auth, heigit=heigit, restricted_ways=RESTRICTED_WAYS, models=models
    )
    client = TestClient(app, base_url="https://testserver")
    client.headers.update(as_owner(client, LOCAL_OWNER))
    return client


def no_github(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected GitHub call to {request.url}")


def as_owner(api: TestClient, owner: str) -> dict[str, str]:
    """Headers of a browser signed in as this owner (sign-in itself is in test_auth.py)."""
    app = api.app
    assert isinstance(app, FastAPI)
    token, csrf = create_session(app.state.engine, owner)
    return {"Cookie": f"{SESSION_COOKIE}={token}", "X-CSRF-Token": csrf}


@pytest.fixture
def api(clean_engine: Engine) -> TestClient:
    return api_with(clean_engine, httpx.MockTransport(recorded_response), FAKE_TOKEN)
