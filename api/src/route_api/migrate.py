"""Migrate DATABASE_URL to this release's head before the API starts (render.yaml).

A rollback starts the previous release on a database a newer release has already migrated.
`alembic upgrade head` would fail there, since the older migrations do not know the newer
revision, and Render would keep the rejected release serving. Migrations only add
(docs/hosting.md), so an older release runs on the newer schema as it is.
"""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine

API_DIR = Path(__file__).resolve().parents[2]


def known_revisions() -> set[str]:
    script = ScriptDirectory(str(API_DIR / "migrations"))
    return {revision.revision for revision in script.walk_revisions()}


def applied_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def migrate(url: str) -> str:
    """Upgrades to head, unless a newer release has migrated further. Says which."""
    engine = create_engine(url)
    try:
        applied = applied_revision(engine)
    finally:
        engine.dispose()
    if applied is not None and applied not in known_revisions():
        return f"database at {applied}, newer than this release; left as it is"
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return "database at this release's head"


if __name__ == "__main__":
    print(migrate(os.environ["DATABASE_URL"]))
