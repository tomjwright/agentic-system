"""Signed-in owner sessions, and an index for retention by age.

Only adds tables and indexes, so the release before it keeps working on the new schema
while the new release starts.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    op.create_table(
        "owner_sessions",
        sa.Column("token_sha256", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False, index=True),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_route_requests_created_at", "route_requests", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_route_requests_created_at", "route_requests")
    op.drop_table("owner_sessions")
