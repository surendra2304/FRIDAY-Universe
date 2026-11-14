"""TASK-REL-015 regressions: production logging survives init_db, and a
legacy-shaped event_log is converged at boot.

Two production findings drive these tests:

* ``init_db()`` stamps a fresh schema through Alembic, whose env.py called
  ``logging.config.fileConfig`` with the default
  ``disable_existing_loggers=True`` and alembic.ini's root=WARN config —
  in-process migrations could silence the host application's loggers for
  the rest of the process lifetime (the production twin of the PR #107
  test pollution). The fix is env.py's ``disable_existing_loggers=False``
  plus session.py's ``_preserve_logging_state`` guard around the stamp.

* The live Oracle ``event_log`` table was built by ``create_all`` from a
  model that predated ``cloud_synced``; ``create_all`` never alters an
  existing table and production never runs ``alembic upgrade``, so every
  event read failed with ORA-00904. ``init_db()`` now converges the table
  at boot via ``_ensure_event_log_shape``, the same idempotent pattern as
  the scope repairs.
"""
import io
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from storage.relational import models as relational_models
from storage.relational import session as relational_session
from storage.relational.base import Base


def _use_test_engine(monkeypatch, engine):
    monkeypatch.setattr(relational_session, "engine", engine)
    monkeypatch.setattr(relational_session, "storage_ready", lambda: True)


def test_init_db_stamp_preserves_process_logging(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh-logging.db'}")
    _use_test_engine(monkeypatch, engine)

    root = logging.getLogger()
    sentinel = logging.getLogger("memora.rel015.sentinel")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    saved_handlers = root.handlers[:]
    saved_level = root.level
    saved_sentinel_disabled = sentinel.disabled
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    sentinel.disabled = False
    try:
        relational_session.init_db()

        # The stamp really happened (a fresh schema is stamped at head)...
        with engine.connect() as connection:
            stamped = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert stamped == "08e9adb56879"

        # ...and the process logging configuration survived it.
        assert sentinel.disabled is False
        assert root.level == logging.INFO
        assert handler in root.handlers
        sentinel.info("rel015-sentinel-message")
        handler.flush()
        assert "rel015-sentinel-message" in stream.getvalue()
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
        sentinel.disabled = saved_sentinel_disabled
        engine.dispose()


def test_init_db_repairs_legacy_event_log(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-event-log.db'}")
    Base.metadata.create_all(bind=engine)

    # Rebuild the production shape: event_log as create_all made it before
    # the ORM learned cloud_synced (no column, no index).
    with engine.begin() as connection:
        connection.execute(
            text("DROP INDEX IF EXISTS ix_event_log_cloud_synced")
        )
        connection.execute(text("ALTER TABLE event_log DROP COLUMN cloud_synced"))
    inspector = inspect(engine)
    assert "cloud_synced" not in {
        column["name"] for column in inspector.get_columns("event_log")
    }

    _use_test_engine(monkeypatch, engine)
    try:
        relational_session.init_db()

        inspector = inspect(engine)
        assert "cloud_synced" in {
            column["name"] for column in inspector.get_columns("event_log")
        }
        assert "ix_event_log_cloud_synced" in {
            index["name"] for index in inspector.get_indexes("event_log")
        }

        # The repaired table serves the ORM path that failed in production.
        factory = sessionmaker(bind=engine)
        db = factory()
        try:
            record = relational_models.EventLog(
                event_id="rel015-probe",
                event_type="memory.created",
                tenant_id="default",
                payload={"probe": True},
            )
            db.add(record)
            db.commit()
            fetched = (
                db.query(relational_models.EventLog)
                .filter_by(event_id="rel015-probe")
                .one()
            )
            assert fetched.cloud_synced is False
        finally:
            db.close()
    finally:
        engine.dispose()
