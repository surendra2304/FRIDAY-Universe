"""durable state for the per-agent budget ledger (TASK-IG2-COR-01)

Revision ID: 009_agent_budget_state
Revises: 008_sentinel_tenant_findings
Create Date: 2026-11-16 20:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009_agent_budget_state"
down_revision: str | None = "008_sentinel_tenant_findings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Portable JSON type: native JSONB on PostgreSQL, JSON elsewhere (same
# convention as 005_create_cognition_tables.py).
JSONType = sa.JSON().with_variant(sa.dialects.postgresql.JSONB, "postgresql")


def upgrade() -> None:
    op.create_table(
        "agent_budget_state",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("state", JSONType, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("agent_budget_state")
