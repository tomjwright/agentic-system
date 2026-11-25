"""Agent runs asked before a start is confirmed have no route request.

Only drops a NOT NULL, so the release before it keeps working on the new schema. The
retention job deletes these runs by their own age, as no route request takes them.

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade() -> None:
    op.alter_column("agent_runs", "route_request_id", nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM agent_runs WHERE route_request_id IS NULL")
    op.alter_column("agent_runs", "route_request_id", nullable=False)
