import os
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from route_api.heigit import Heigit
from route_api.main import create_app
from route_api.onemap import OneMap
from route_api.restrictions import load_restricted_ways
from tests import recorded_heigit
from tests.recorded_onemap import recorded_response

# A database the tests may wipe. Never point this at real data.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/routes_test"
)
FAKE_TOKEN = "fake-onemap-token-for-tests"
FAKE_HEIGIT_KEY = "fake-heigit-key-for-tests"
API_DIR = Path(__file__).parent.parent
RESTRICTED_WAYS = load_restricted_ways()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def clean_engine(engine: Engine) -> Engine:
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE route_requests CASCADE"))
    return engine


def api_with(
    engine: Engine,
    handler: httpx.MockTransport,
    token: str | None,
    heigit_handler: Callable[[httpx.Request], httpx.Response] = recorded_heigit.recorded_response,
    heigit_key: str | None = FAKE_HEIGIT_KEY,
) -> TestClient:
    onemap = OneMap(httpx.Client(transport=handler), token=token, retry_wait_seconds=0)
    heigit_http = httpx.Client(transport=httpx.MockTransport(heigit_handler))
    heigit = Heigit(heigit_http, heigit_key, request_gap_seconds=0, retry_wait_seconds=0)
    app = create_app(onemap, engine, "local-owner", heigit=heigit, restricted_ways=RESTRICTED_WAYS)
    return TestClient(app)


@pytest.fixture
def api(clean_engine: Engine) -> TestClient:
    return api_with(clean_engine, httpx.MockTransport(recorded_response), FAKE_TOKEN)
