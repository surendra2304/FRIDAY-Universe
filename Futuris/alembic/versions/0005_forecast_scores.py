"""Add the forecast_scores table (TASK-FUT-006 live forecast tracker).

One row per resolved forecast, written when the forecast's actual value
lands: the issuance snapshot (target, horizon, prediction, interval
bounds, nominal level + its source, confidence, model, provenance) plus
the measured score (signed/absolute error, interval hit, width, Winkler).
``forecast_id`` is unique -- a forecast is scored exactly once, which is
what makes the tracker's scoring sweep idempotent.

Production bootstraps its schema from SQLAlchemy metadata
(``futuris.storage.db.ensure_schema`` runs ``create_all``), so this
migration is the managed-deployment path for the same table declared by
``ForecastScoreModel``; the two must stay in step.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-15 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forecast_scores",
        sa.Column("score_id", sa.Uuid(), nullable=False),
        sa.Column("forecast_id", sa.Uuid(), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=False),
        sa.Column("model_version", sa.String(length=255), nullable=False),
        sa.Column("evidence_class", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_seconds", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prediction", sa.Float(), nullable=False),
        sa.Column("range_lower", sa.Float(), nullable=False),
        sa.Column("range_upper", sa.Float(), nullable=False),
        sa.Column("nominal_level", sa.Float(), nullable=False),
        sa.Column("nominal_level_source", sa.String(length=64), nullable=False),
        sa.Column("observed_value", sa.Float(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signed_error", sa.Float(), nullable=False),
        sa.Column("abs_error", sa.Float(), nullable=False),
        sa.Column("pct_error", sa.Float(), nullable=True),
        sa.Column("interval_hit", sa.Boolean(), nullable=False),
        sa.Column("interval_width", sa.Float(), nullable=False),
        sa.Column("winkler", sa.Float(), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["forecast_id"], ["forecasts.forecast_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("score_id"),
        sa.UniqueConstraint("forecast_id"),
    )
    op.create_index(
        "ix_forecast_scores_forecast_id", "forecast_scores", ["forecast_id"], unique=True
    )
    op.create_index("ix_forecast_scores_target", "forecast_scores", ["target"])
    op.create_index(
        "ix_forecast_scores_evidence_class", "forecast_scores", ["evidence_class"]
    )
    op.create_index("ix_forecast_scores_scored_at", "forecast_scores", ["scored_at"])


def downgrade() -> None:
    op.drop_index("ix_forecast_scores_scored_at", table_name="forecast_scores")
    op.drop_index("ix_forecast_scores_evidence_class", table_name="forecast_scores")
    op.drop_index("ix_forecast_scores_target", table_name="forecast_scores")
    op.drop_index("ix_forecast_scores_forecast_id", table_name="forecast_scores")
    op.drop_table("forecast_scores")
