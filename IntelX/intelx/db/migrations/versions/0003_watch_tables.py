"""Watch seen-store and envelope tables (TASK-DB-002).

Revision ID: 0003_watch_tables
Revises: 0002_evidence_data_model
Create Date: 2026-11-25 19:00:00.000000

Creates the two tables that move the standing-watch file stores into
Autonomous DB #2 ("IntelX DB", INTELX schema):

- ``watch_seen`` — the DB-backed seen-store (replaces ``state.json``).
  One row per (watch, fingerprinted item); composite PK
  (watch_id, fingerprint); index on (watch_id, status, first_seen)
  for the 90-day prune of non-alert records.
- ``watch_envelopes`` — the DB-backed outbox history (mirrors the
  ``outbox.jsonl`` envelope, schema ``intelx.watch_alert/1``).
  ``dedupe_key`` is unique: the idempotency guard that replaces
  "already in the file".

Column definitions match ``intelx/db/models.py`` (WatchSeen,
WatchEnvelope) exactly — the migration and the models must not disagree
(decision D2: Alembic is the schema-creation mechanism on ADB #2;
``create_all`` in the lifespan stays as the belt-and-braces boot path).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_watch_tables"
down_revision: str | None = "0002_evidence_data_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. watch_seen — DB-backed seen-store (TASK-DB-002, decision D1(a)).
    op.create_table(
        "watch_seen",
        sa.Column("watch_id", sa.String(length=64), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("title_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("watch_id", "fingerprint"),
    )
    op.create_index("ix_watch_seen_status", "watch_seen", ["status"])
    op.create_index(
        "ix_watch_seen_watch_status_seen",
        "watch_seen",
        ["watch_id", "status", "first_seen"],
    )

    # 2. watch_envelopes — DB-backed outbox history (TASK-DB-002).
    op.create_table(
        "watch_envelopes",
        sa.Column("envelope_id", sa.String(length=64), primary_key=True),
        sa.Column("watch_id", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key", sa.String(length=128), unique=True, nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("score_reasons", sa.JSON(), nullable=True),
        sa.Column("alert_class", sa.String(length=32), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("envelope_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_watch_envelopes_watch_id", "watch_envelopes", ["watch_id"])
    op.create_index("ix_watch_envelopes_dedupe_key", "watch_envelopes", ["dedupe_key"])


def downgrade() -> None:
    op.drop_table("watch_envelopes")
    op.drop_table("watch_seen")
