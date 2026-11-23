"""Road-cycling restriction results, and a duration that is not always a walking time.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    op.alter_column("route_candidates", "walking_duration_s", new_column_name="duration_s")
    op.add_column("route_candidates", sa.Column("restricted_roads", JSONB()))
    op.add_column("generation_runs", sa.Column("restriction_data", sa.String(200)))


def downgrade() -> None:
    op.drop_column("generation_runs", "restriction_data")
    op.drop_column("route_candidates", "restricted_roads")
    op.alter_column("route_candidates", "duration_s", new_column_name="walking_duration_s")
