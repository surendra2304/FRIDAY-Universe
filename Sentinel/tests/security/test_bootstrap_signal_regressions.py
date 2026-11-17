"""Regression tests for the two Sentinel defects fixed in SENTINEL-FIX-PR.

1. The raw-DDL audit bootstrap module
   (``sentinel/storage/database/bootstrap_audit_hmac_sha256.py``) was dead
   code whose statement splitter silently skipped its own CREATE TABLEs and
   failed with ORA-00942/ORA-00900 at every startup. Nothing referenced the
   tables it targeted; ORM ``create_all`` already creates every used table.
   The module and its ``init_database()`` call are deleted.

2. The API lifespan installed a custom ``loop.add_signal_handler`` for
   SIGTERM/SIGINT whose handler only logged. asyncio replaces uvicorn's own
   handler, so uvicorn never initiated shutdown, the bounded lifespan drain
   never ran, and systemd SIGKILLed the process at every stop. The custom
   handler block is deleted; uvicorn owns SIGTERM again.
"""

from pathlib import Path

SENTINEL_ROOT = Path(__file__).resolve().parents[2]
SESSION_PY = SENTINEL_ROOT / "sentinel" / "storage" / "database" / "session.py"
BOOTSTRAP_PY = SENTINEL_ROOT / "sentinel" / "storage" / "database" / "bootstrap_audit_hmac_sha256.py"
API_MAIN_PY = SENTINEL_ROOT / "sentinel" / "apps" / "api" / "main.py"


def test_dead_audit_bootstrap_module_is_deleted() -> None:
    assert not BOOTSTRAP_PY.exists()


def test_session_module_has_no_bootstrap_reference() -> None:
    source = SESSION_PY.read_text(encoding="utf-8")
    assert "bootstrap_audit" not in source
    assert "bootstrap_audit_tables" not in source


def test_no_sentinel_module_references_the_dead_bootstrap() -> None:
    package_root = SENTINEL_ROOT / "sentinel"
    offenders = [
        str(path)
        for path in package_root.rglob("*.py")
        if "bootstrap_audit_hmac_sha256" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert offenders == []


async def test_init_database_creates_schema_without_bootstrap(monkeypatch, caplog) -> None:
    """init_database() must run create_all and never touch the dead bootstrap."""
    from sentinel.storage.database import session as db_session

    run_sync_calls: list[object] = []

    class _FakeConn:
        async def run_sync(self, fn) -> None:
            run_sync_calls.append(fn)

    class _FakeBegin:
        async def __aenter__(self) -> _FakeConn:
            return _FakeConn()

        async def __aexit__(self, *exc) -> bool:
            return False

    class _FakeEngine:
        def begin(self) -> _FakeBegin:
            return _FakeBegin()

    class _FakeSettings:
        uses_database_backend = True
        is_oracle_database = False
        database_dialect = "sqlite"
        storage_backend_normalized = "oracle"

    monkeypatch.setattr(db_session, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(db_session, "get_async_engine", lambda: _FakeEngine())

    with caplog.at_level("WARNING"):
        await db_session.init_database()

    from sentinel.storage.database.models import Base

    assert run_sync_calls == [Base.metadata.create_all]
    assert "bootstrap skipped" not in caplog.text


def test_api_entrypoint_installs_no_custom_signal_handlers() -> None:
    source = API_MAIN_PY.read_text(encoding="utf-8")
    assert "add_signal_handler" not in source
    assert "_sig_handler" not in source


def test_lifespan_drain_is_unchanged() -> None:
    """The bounded drain the fix relies on must still be there, untouched."""
    source = API_MAIN_PY.read_text(encoding="utf-8")
    assert "await asyncio.wait_for(_graceful_drain(), timeout=5.0)" in source
    assert "Initiating graceful shutdown" in source
