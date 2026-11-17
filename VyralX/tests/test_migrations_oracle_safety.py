"""Oracle additive-migration safety tests — the PR #882 ORA-01758 regression.

On Oracle the empty string IS NULL, so a column declared ``NOT NULL
DEFAULT ''`` has no usable default: ``ALTER TABLE ... ADD <col> ...
NOT NULL`` against a populated table fails with ORA-01758 ("table must be
empty to add mandatory column"). PR #882 added publish_jobs.thumbnail_path
and publish_jobs.category_id in exactly that shape; the startup migration
in app/main.py (and app/worker.py) then crash-looped production VyralX
while publish_jobs held 54 rows.

These tests pin the Oracle translator and the migration runner so the
shape cannot recur: on Oracle, such columns must be added NULLABLE (the
application's Python-side defaults supply '' for new rows).
"""
from __future__ import annotations

import re

from sqlalchemy import create_engine, inspect, text

from app.migrations import ADDITIVE_COLUMNS, _oracle_declaration, run_additive_migrations


def test_882_columns_translate_to_nullable_on_oracle():
    # The exact declarations PR #882 added for publish_jobs.
    assert _oracle_declaration("VARCHAR(2048) NOT NULL DEFAULT ''") == "VARCHAR(2048)"
    assert _oracle_declaration("VARCHAR(8) NOT NULL DEFAULT ''") == "VARCHAR(8)"


def test_bare_not_null_without_default_is_also_nullable_on_oracle():
    assert _oracle_declaration("VARCHAR(10) NOT NULL") == "VARCHAR(10)"


def test_no_oracle_translation_is_not_null_without_a_usable_default():
    """Whole-table invariant over ADDITIVE_COLUMNS (fails on the old code).

    For every declared additive column, the Oracle translation must never
    carry NOT NULL unless it also carries a DEFAULT whose literal can
    actually backfill existing rows (i.e. not '' and not NULL).
    """
    for table, columns in ADDITIVE_COLUMNS.items():
        for column, declaration in columns.items():
            translated = _oracle_declaration(declaration)
            if "NOT NULL" not in translated:
                continue
            match = re.search(r"DEFAULT\s+('[^']*'|\S+)", translated)
            assert match, f"{table}.{column}: NOT NULL without DEFAULT -> {translated!r}"
            assert match.group(1) not in ("''", "NULL"), (
                f"{table}.{column}: NOT NULL with unusable default -> {translated!r}"
            )


def test_usable_defaults_keep_their_not_null():
    # Numeric and real-string defaults CAN backfill a populated Oracle
    # table, so those translations must keep NOT NULL + DEFAULT intact.
    assert _oracle_declaration("INTEGER NOT NULL DEFAULT 0") == "INTEGER NOT NULL DEFAULT 0"
    assert _oracle_declaration("BOOLEAN NOT NULL DEFAULT FALSE") == "NUMBER(1) DEFAULT 0 NOT NULL"
    assert (
        _oracle_declaration("VARCHAR(40) NOT NULL DEFAULT 'not_generated'")
        == "VARCHAR(40) NOT NULL DEFAULT 'NOT_GENERATED'"  # translator uppercases declarations
    )


def _populated_publish_jobs_engine():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE publish_jobs (id INTEGER PRIMARY KEY, title VARCHAR(100))")
        )
        connection.execute(
            text("INSERT INTO publish_jobs (id, title) VALUES (1, 'a'), (2, 'b')")
        )
    return engine


def test_migration_adds_columns_to_populated_table_and_is_idempotent():
    engine = _populated_publish_jobs_engine()
    run_additive_migrations(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("publish_jobs")}
    assert {"thumbnail_path", "category_id"} <= columns
    # Running the migration again must be a no-op success (existence-checked).
    run_additive_migrations(engine)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM publish_jobs")).scalar() == 2


def test_migration_noop_when_columns_already_exist():
    """Mirrors the production recovery state: the two columns were added
    manually (nullable) ahead of the fixed migration; the migration must
    skip them instead of failing on a duplicate column."""
    engine = _populated_publish_jobs_engine()
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE publish_jobs ADD thumbnail_path VARCHAR(2048)"))
        connection.execute(text("ALTER TABLE publish_jobs ADD category_id VARCHAR(8)"))
    run_additive_migrations(engine)
    run_additive_migrations(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("publish_jobs")}
    assert {"thumbnail_path", "category_id"} <= columns
