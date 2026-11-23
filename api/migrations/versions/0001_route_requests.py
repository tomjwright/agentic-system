"""Owner-scoped route requests with their confirmed start.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "route_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("activity", sa.String(20), nullable=False),
        sa.Column("start_source", sa.String(20), nullable=False),
        sa.Column("start_source_id", sa.String(300)),
        sa.Column("start_query", sa.String(120)),
        sa.Column("start_name", sa.String(300)),
        sa.Column("start_address", sa.String(300)),
        sa.Column("start_postal", sa.String(10)),
        sa.Column("start_lon", sa.Float(), nullable=False),
        sa.Column("start_lat", sa.Float(), nullable=False),
        sa.Column("start_retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("activity IN ('running', 'road_cycling')", name="activity_known"),
        sa.CheckConstraint("start_source IN ('onemap', 'map_selection')", name="source_known"),
        sa.CheckConstraint("start_lon BETWEEN -180 AND 180", name="lon_in_range"),
        sa.CheckConstraint("start_lat BETWEEN -90 AND 90", name="lat_in_range"),
    )
    op.create_index("route_requests_owner_created", "route_requests", ["owner_id", "created_at"])


def downgrade() -> None:
    op.drop_table("route_requests")
