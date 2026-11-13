"""add durable viking context snapshots

Revision ID: f8a2d6c14b93
Revises: a1d4c7e9f2b3
Create Date: 2026-11-13 00:00:00.000000+00:00

TASK-MEM-010: make the ``viking://`` context database survive a restart.

``core/memory/real_viking_context.py`` keeps the whole context state in an
in-memory ``VikingFS``; everything written through ``/v1/context/*`` was lost
when the process stopped. This revision adds ``context_snapshots``, one row per
``(tenant_id, scope_key)`` holding the serialized context state (FS tree, open
sessions, commit history, session-id sequence) as a JSON document in a Text
column, plus the sha256 digest the loader verifies before trusting it.

Written in the convergent style of b1206b9e4a61: create the table if it is
absent, add only the columns a previously-created table is missing, and never
touch rows that already exist.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f8a2d6c14b93"
down_revision: Union[str, None] = "a1d4c7e9f2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Columns this revision is responsible for, with the type used to add any
#: that a previously-created table is missing.
_COLUMNS: tuple[tuple[str, object], ...] = (
    ("scope_key", sa.String(length=128)),
    ("schema_version", sa.Integer()),
    ("payload", sa.Text()),
    ("content_sha256", sa.String(length=64)),
    ("node_count", sa.Integer()),
    ("updated_at", sa.DateTime(timezone=True)),
)


def _existing() -> set[str]:
    """Column names currently present on context_snapshots, or set() if absent."""
    inspector = sa.inspect(op.get_bind())
    if "context_snapshots" not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns("context_snapshots")}


def _existing_indexes() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if "context_snapshots" not in inspector.get_table_names():
        return set()
    return {ix["name"] for ix in inspector.get_indexes("context_snapshots")}


def upgrade() -> None:
    present = _existing()

    if not present:
        op.create_table(
            "context_snapshots",
            sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default"),
            sa.Column("scope_key", sa.String(length=128), nullable=False),
            sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("content_sha256", sa.String(length=64), nullable=False),
            sa.Column("node_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("tenant_id", "scope_key"),
        )
        present = {name for name, _ in _COLUMNS}
        present.add("tenant_id")

    # Bring a table that create_all built from an older model up to this
    # revision's shape, without touching the rows it already holds.
    for name, coltype in _COLUMNS:
        if name in present:
            continue
        nullable = name == "schema_version" or name == "node_count"
        server_default = None
        if name == "schema_version":
            server_default = "1"
        elif name == "node_count":
            server_default = "0"
        op.add_column(
            "context_snapshots",
            sa.Column(name, coltype, nullable=nullable, server_default=server_default),
        )
        present.add(name)


def downgrade() -> None:
    if not _existing():
        return
    for name in _existing_indexes():
        op.drop_index(name, table_name="context_snapshots")
    op.drop_table("context_snapshots")
