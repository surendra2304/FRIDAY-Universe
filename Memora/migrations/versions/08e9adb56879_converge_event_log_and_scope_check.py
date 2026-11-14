"""converge event_log cloud_synced + ck_memory_scope (TASK-REL-015)

Revision ID: 08e9adb56879
Revises: f8a2d6c14b93
Create Date: 2026-11-14 00:00:00.000000+00:00

Two ORM-vs-migration drifts survived PR #105, which aligned tables,
columns and uniqueness but never compared check constraints or the live
database:

1. ``ck_memory_scope`` exists in the ORM (``memory_records.__table_args__``)
   and therefore in every ``create_all`` database — and the production
   boot path maintains it via ``_ensure_scope_constraint`` — but NO
   migration ever created it, so a migration-built database lacked the
   constraint the ORM promises.

2. ``event_log.cloud_synced`` (+ ``ix_event_log_cloud_synced``) is added
   convergently by b1206b9e4a61, yet the production schema's version row
   sits past that revision while its event_log was built by ``create_all``
   from a model without the column — so the column is missing there even
   though the version claims the revision ran. Production never executes
   ``alembic upgrade`` (init_db's boot-time ensures converge it instead;
   see ``_ensure_event_log_shape``), but any environment that DOES upgrade
   from a stamped-past-b1206 state needs this revision to repair the
   column rather than trust the version row.

Written in the convergent style of b1206b9e4a61 / f8a2d6c14b93: add only
what is missing, never touch rows that already exist.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "08e9adb56879"
down_revision: Union[str, None] = "f8a2d6c14b93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCOPE_CHECK_SQL = "scope IN ('PRIVATE', 'SHARED', 'UNIVERSAL')"


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {c["name"].lower() for c in inspector.get_columns(table)}


def _indexes(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {(ix["name"] or "").lower() for ix in inspector.get_indexes(table)}


def _checks(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {
        (chk["name"] or "").lower()
        for chk in inspector.get_check_constraints(table)
    }


def upgrade() -> None:
    tables = _tables()

    if "event_log" in tables:
        if "cloud_synced" not in _columns("event_log"):
            op.add_column(
                "event_log",
                sa.Column(
                    "cloud_synced",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )
        if "ix_event_log_cloud_synced" not in _indexes("event_log"):
            op.create_index(
                "ix_event_log_cloud_synced", "event_log", ["cloud_synced"]
            )

    if "memory_records" in tables and "ck_memory_scope" not in _checks(
        "memory_records"
    ):
        if op.get_bind().dialect.name == "sqlite":
            # SQLite cannot add a CHECK in place; batch mode rebuilds the
            # table with the constraint, preserving rows.
            with op.batch_alter_table("memory_records") as batch_op:
                batch_op.create_check_constraint(
                    "ck_memory_scope", _SCOPE_CHECK_SQL
                )
        else:
            op.create_check_constraint(
                "ck_memory_scope", "memory_records", _SCOPE_CHECK_SQL
            )


def downgrade() -> None:
    """Remove the objects this revision is responsible for, if present.

    Convergent revisions cannot know whether a given object pre-existed
    their run, so — as with the drop-table downgrades of b1206b9e4a61 and
    f8a2d6c14b93 — downgrading removes the converged objects outright.
    """
    tables = _tables()

    if "memory_records" in tables and "ck_memory_scope" in _checks(
        "memory_records"
    ):
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table("memory_records") as batch_op:
                batch_op.drop_constraint("ck_memory_scope", type_="check")
        else:
            op.drop_constraint(
                "ck_memory_scope", "memory_records", type_="check"
            )

    if "event_log" in tables:
        if "ix_event_log_cloud_synced" in _indexes("event_log"):
            op.drop_index("ix_event_log_cloud_synced", table_name="event_log")
        if "cloud_synced" in _columns("event_log"):
            op.drop_column("event_log", "cloud_synced")
