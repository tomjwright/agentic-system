"""A rolled-back release starts and serves on a schema a newer release has migrated."""

from collections.abc import Iterator

import httpx
import httpx2
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from route_api.migrate import API_DIR, applied_revision, known_revisions, migrate
from tests.conftest import api_with
from tests.recorded_onemap import recorded_response
from tests.test_auth import anonymous


@pytest.fixture
def database_at(clean_engine: Engine) -> Iterator[Engine]:
    """Lets a test set alembic_version, then puts this release's head back."""
    head = applied_revision(clean_engine)
    yield clean_engine
    with clean_engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = :v"), {"v": head})


def set_revision(engine: Engine, revision: str) -> None:
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = :v"), {"v": revision})


def ready(engine: Engine) -> httpx2.Response:
    api = anonymous(api_with(engine, httpx.MockTransport(recorded_response), "token"))
    response: httpx2.Response = api.get("/api/ready")
    return response


def test_a_database_at_this_release_is_upgraded_in_place(
    database_at: Engine, database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://nobody@127.0.0.1:1/none")
    assert migrate(database_url) == "database at this release's head"
    assert applied_revision(database_at) == "0004"


def test_a_database_a_newer_release_migrated_is_left_as_it_is(
    database_at: Engine, database_url: str
) -> None:
    set_revision(database_at, "0099")
    assert migrate(database_url) == "database at 0099, newer than this release; left as it is"
    assert applied_revision(database_at) == "0099"
    answer = ready(database_at)
    assert answer.status_code == 200
    assert answer.json() == {"status": "ready", "database": "ok", "migrations": "ahead"}


def test_a_database_behind_this_release_is_not_ready_until_migrated(
    database_at: Engine, database_url: str
) -> None:
    # Built first: starting the API cleans up owner_sessions, which 0004 adds.
    api = anonymous(api_with(database_at, httpx.MockTransport(recorded_response), "token"))
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.downgrade(config, "0003")
    answer = api.get("/api/ready")
    assert answer.status_code == 503
    assert answer.json()["migrations"] == "behind"
    assert migrate(database_url) == "database at this release's head"
    assert applied_revision(database_at) == "0004"
    assert api.get("/api/ready").json()["migrations"] == "current"


def test_every_migration_is_known() -> None:
    assert known_revisions() == {"0001", "0002", "0003", "0004"}


def test_a_percent_encoded_database_url_migrates(database_at: Engine, database_url: str) -> None:
    encoded = f"{database_url}?application_name=route%20api"
    assert migrate(encoded) == "database at this release's head"
