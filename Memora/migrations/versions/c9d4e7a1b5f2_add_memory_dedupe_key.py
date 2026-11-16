"""add memory dedupe_key column and unique index

Revision ID: c9d4e7a1b5f2
Revises: 08e9adb56879
Create Date: 2026-11-16

MEM-004 follow-up: production accumulated byte-identical copies of the same
fact because no write path could see an exact duplicate outside its target
namespace and nothing constrained content at the database level. The fix keys
an exact duplicate on (tenant_id, owner_agent, content_hash, provenance
subject) and stores the hash of that tuple in a new ``dedupe_key`` column,
populated by both write services (the 10-step pipeline and
``MemoryService.create_memory``).

The unique index makes the database the final arbiter for concurrent
identical writes: the loser's flush raises IntegrityError and the service
adopts the winner's row. The DDL is portable (plain column + index, no
vendor syntax), so the same revision runs on SQLite, PostgreSQL, and Oracle
Autonomous Database.

Existing rows are deliberately NOT backfilled: the column starts NULL for
every legacy row, and NULLs never collide in a unique index, so this
migration cannot fail on the duplicates already cleaned by the MEM-004
hygiene pass. Legacy rows remain matchable by the services through
``content_hash`` (set by every pipeline write); a keyed backfill, if ever
wanted, is a separate deliberate operation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d4e7a1b5f2"
down_revision: Union[str, Sequence[str], None] = "08e9adb56879"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    if "memory_records" not in tables:
        # Nothing to upgrade: a fresh database is created from ORM metadata.
        return

    columns = {column["name"].lower() for column in inspector.get_columns("memory_records")}
    if "dedupe_key" not in columns:
        op.add_column(
            "memory_records",
            sa.Column("dedupe_key", sa.String(length=64), nullable=True),
        )

    indexes = {index["name"] for index in inspector.get_indexes("memory_records")}
    if "uq_memory_dedupe_key" not in indexes:
        op.create_index(
            "uq_memory_dedupe_key",
            "memory_records",
            ["dedupe_key"],
            unique=True,
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    if "memory_records" not in tables:
        return

    indexes = {index["name"] for index in inspector.get_indexes("memory_records")}
    if "uq_memory_dedupe_key" in indexes:
        op.drop_index("uq_memory_dedupe_key", table_name="memory_records")

    columns = {column["name"].lower() for column in inspector.get_columns("memory_records")}
    if "dedupe_key" in columns:
        op.drop_column("memory_records", "dedupe_key")
