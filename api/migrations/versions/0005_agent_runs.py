"""Route agent runs: what was answered and how it was judged, never what the user typed.

Only adds a table, so the release before it keeps working on the new schema while the new
release starts. Rows go with their route request (ON DELETE CASCADE), so the retention job
deletes them at the same age.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column(
            "route_request_id",
            sa.Uuid(),
            sa.ForeignKey("route_requests.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "generation_run_id",
            sa.Uuid(),
            sa.ForeignKey("generation_runs.id", ondelete="CASCADE"),
            unique=True,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(20)),
        sa.Column("message_source", sa.String(20)),
        sa.Column("fallback_reason", sa.String(40)),
        sa.Column("verdicts", JSONB(), nullable=False),
        sa.Column("repairs", sa.Integer(), nullable=False),
        sa.Column("agent_model", sa.String(100), nullable=False),
        sa.Column("judge_model", sa.String(100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('running', 'finished')", name="agent_run_status_known"),
    )


def downgrade() -> None:
    op.drop_table("agent_runs")
