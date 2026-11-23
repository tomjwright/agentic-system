"""Request revisions, generation runs, their candidates and the selected route.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.create_table(
        "route_request_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "route_request_id",
            sa.Uuid(),
            sa.ForeignKey("route_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("distance", JSONB(), nullable=False),
        sa.Column("min_m", sa.Float(), nullable=False),
        sa.Column("max_m", sa.Float(), nullable=False),
        sa.Column("target_m", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("route_request_id", "number"),
        sa.CheckConstraint("number >= 1", name="revision_number_positive"),
        sa.CheckConstraint("0 < min_m AND min_m < max_m", name="revision_bounds_ordered"),
    )
    op.create_table(
        "generation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "revision_id",
            sa.Uuid(),
            sa.ForeignKey("route_request_revisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(40)),
        sa.Column("error_message", sa.String(200)),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("profile", sa.String(20), nullable=False),
        sa.Column("generator_version", sa.String(40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("owner_id", "operation_id"),
        sa.CheckConstraint(
            "status IN ('generating', 'succeeded', 'no_route', 'failed')", name="run_status_known"
        ),
    )
    op.create_index("ix_generation_runs_revision_id", "generation_runs", ["revision_id"])
    op.create_table(
        "route_candidates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("generation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("parameters", JSONB(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("reasons", JSONB(), nullable=False),
        sa.Column("coordinates", JSONB()),
        sa.Column("provider_distance_m", sa.Float()),
        sa.Column("measured_distance_m", sa.Float()),
        sa.Column("walking_duration_s", sa.Float()),
        sa.Column("surfaces_m", JSONB()),
        sa.Column("engine", JSONB()),
        sa.Column("attribution", sa.String(300)),
        sa.UniqueConstraint("run_id", "position"),
        sa.CheckConstraint("method IN ('round_trip', 'via_loop')", name="candidate_method_known"),
    )
    op.create_table(
        "selected_routes",
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("generation_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "candidate_id",
            sa.Uuid(),
            sa.ForeignKey("route_candidates.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("selected_routes")
    op.drop_table("route_candidates")
    op.drop_index("ix_generation_runs_revision_id", "generation_runs")
    op.drop_table("generation_runs")
    op.drop_table("route_request_revisions")
