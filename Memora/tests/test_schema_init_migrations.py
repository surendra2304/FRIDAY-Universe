import re
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

_ALEMBIC_INI = str(Path(__file__).resolve().parent.parent / "alembic.ini")

from storage.relational import session as relational_session


def _normalized_check(sqltext):
    normalized = (sqltext or "").upper().replace('"', "").replace("'", "")
    return re.sub(r"\s+", "", normalized)


def _schema_shape(engine):
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names()) - {"alembic_version"}
    columns = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in table_names
    }
    unique_keys = {}
    check_keys = {}
    for table in table_names:
        keys = {
            tuple(sorted(constraint["column_names"]))
            for constraint in inspector.get_unique_constraints(table)
        }
        keys.update(
            tuple(sorted(index["column_names"]))
            for index in inspector.get_indexes(table)
            if index.get("unique")
        )
        unique_keys[table] = keys
        # TASK-REL-015: PR #105 compared tables/columns/uniqueness only,
        # which is exactly why ck_memory_scope (ORM-only until revision
        # 08e9adb56879) drifted invisibly. Compare check constraints too.
        check_keys[table] = {
            constraint["name"]: _normalized_check(constraint.get("sqltext"))
            for constraint in inspector.get_check_constraints(table)
            if constraint.get("name")
        }
    return table_names, columns, unique_keys, check_keys


def test_fresh_create_all_database_is_stamped_before_future_upgrades(tmp_path, monkeypatch):
    database_path = tmp_path / "fresh-memora.db"
    engine = create_engine(f"sqlite:///{database_path}")
    migration_only_engine = create_engine(f"sqlite:///{tmp_path / 'migration-only.db'}")
    monkeypatch.setattr(relational_session, "engine", engine)
    monkeypatch.setattr(relational_session, "storage_ready", lambda: True)

    try:
        relational_session.init_db()
        with engine.connect() as connection:
            stamped_revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert stamped_revision == "08e9adb56879"

        # The same schema can now pass through the deployment migration command
        # without replaying historical CREATE TABLE/ADD COLUMN operations.
        config = Config(_ALEMBIC_INI)
        config.attributes["connection"] = engine
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == stamped_revision

        migration_config = Config(_ALEMBIC_INI)
        migration_config.attributes["connection"] = migration_only_engine
        command.upgrade(migration_config, "head")
        # The current ORM metadata and a clean migration-only install have the
        # same tables, columns, uniqueness invariants, and check constraints
        # at the stamped head.
        assert _schema_shape(engine) == _schema_shape(migration_only_engine)
    finally:
        engine.dispose()
        migration_only_engine.dispose()
