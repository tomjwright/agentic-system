import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from route_api.main import create_app
from route_api.onemap import OneMap
from tests.recorded_onemap import recorded_response

# A database the tests may wipe. Never point this at real data.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/routes_test"
)
FAKE_TOKEN = "fake-onemap-token-for-tests"
API_DIR = Path(__file__).parent.parent


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
        connection.execute(text("TRUNCATE route_requests"))
    return engine


def api_with(engine: Engine, handler: httpx.MockTransport, token: str | None) -> TestClient:
    onemap = OneMap(httpx.Client(transport=handler), token=token, retry_wait_seconds=0)
    return TestClient(create_app(onemap, engine, local_owner="local-owner"))


@pytest.fixture
def api(clean_engine: Engine) -> TestClient:
    return api_with(clean_engine, httpx.MockTransport(recorded_response), FAKE_TOKEN)
