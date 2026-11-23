"""Alembic runs migrations against DATABASE_URL (or the URL the tests set)."""

import os

from alembic import context
from sqlalchemy import create_engine

url = context.config.get_main_option("sqlalchemy.url") or os.environ["DATABASE_URL"]
engine = create_engine(url)
with engine.connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
