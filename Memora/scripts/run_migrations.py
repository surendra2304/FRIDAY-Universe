#!/usr/bin/env python3
"""Run Memora's Alembic migrations to head — the deploy/start-path step.

TASK-MEM-009: on 2026-11-17 a merged migration (PR #831, revision
c9d4e7a1b5f2) never ran on the production database, because nothing in
Memora's deploy or start path ran Alembic: the systemd unit is
uvicorn-direct and Fleet CD only restarts the service, while the app's
boot path (``init_db``) converges some schema objects without ever
advancing ``alembic_version``. Every ``memory_records`` ORM query then
failed ORA-00904 for ~1.5h while ``/health`` stayed green.

This script is wired as ``ExecStartPre`` in the Memora unit that
``deploy/setup_fleet.sh`` writes, so it runs before EVERY service start
(Fleet CD restart, manual restart, reboot, crash restart) with the
unit's working directory and EnvironmentFile applied:

- it logs the Alembic revision before and after;
- it upgrades to head against the application's own engine — the same
  connection ``migrations/env.py`` falls back to — so the schema the
  code boots against is the schema the code expects;
- it verifies the post-upgrade revision equals the script head and
  exits non-zero on ANY failure, so systemd fails the start loudly
  instead of booting on a stale schema;
- it holds an flock for the whole run, so it can never execute
  concurrently with itself (systemd already serialises starts of one
  unit; the lock also covers a manual invocation racing a start).

Idempotency: ``alembic upgrade head`` on a database already at head
runs zero migration scripts — safe on every restart. That property,
the failure exit code, and the production drift shape (schema objects
ahead of the version row) are pinned by
``Memora/tests/test_mem009_deploy_migrations.py``.

Operator overrides (environment):
- ``MEMORA_ALEMBIC_INI`` — Alembic config path (default: the packaged
  ``Memora/migrations/alembic.ini`` that ``init_db`` stamps with).
- ``MEMORA_MIGRATION_LOCK_FILE`` — flock path (default:
  ``Memora/data/alembic-upgrade.lock``).
- ``MEMORA_MIGRATION_LOCK_TIMEOUT_S`` — seconds to wait for the lock
  before failing the start (default 60).
"""

from __future__ import annotations

import fcntl
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Tuple

MEMORA_ROOT = Path(__file__).resolve().parent.parent
if str(MEMORA_ROOT) not in sys.path:
    sys.path.insert(0, str(MEMORA_ROOT))

DEFAULT_CONFIG_PATH = MEMORA_ROOT / "migrations" / "alembic.ini"
DEFAULT_LOCK_TIMEOUT_S = 60.0


def _config_path() -> Path:
    override = os.environ.get("MEMORA_ALEMBIC_INI")
    return Path(override) if override else DEFAULT_CONFIG_PATH


def _lock_path() -> Path:
    override = os.environ.get("MEMORA_MIGRATION_LOCK_FILE")
    if override:
        return Path(override)
    return MEMORA_ROOT / "data" / "alembic-upgrade.lock"


def _lock_timeout_s() -> float:
    raw = os.environ.get("MEMORA_MIGRATION_LOCK_TIMEOUT_S")
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return DEFAULT_LOCK_TIMEOUT_S


@contextmanager
def _upgrade_lock(lock_file: Path, timeout_s: float) -> Iterator[None]:
    """Hold an exclusive flock so two upgrade runs can never overlap."""
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_file.open("a+")
    try:
        deadline = time.monotonic() + timeout_s
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"another Memora migration run holds {lock_file} "
                        f"(waited {timeout_s:.0f}s); refusing to run concurrently"
                    )
                time.sleep(0.25)
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _current_revision(engine) -> Optional[str]:
    from alembic.runtime.migration import MigrationContext

    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _head_revision(config) -> Optional[str]:
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(config).get_current_head()


def upgrade_to_head(engine, config_path: Optional[Path] = None) -> Tuple[Optional[str], Optional[str]]:
    """Upgrade ``engine``'s database to Alembic head.

    Returns ``(before, after)`` revisions. Raises on any failure, and
    raises RuntimeError if the post-upgrade revision is not the script
    head — a silent partial upgrade must fail the start, not boot.
    """
    from alembic import command
    from alembic.config import Config

    config = Config(str(config_path or _config_path()))
    # migrations/env.py prefers an injected connection; give it the
    # application's own engine so the migration runs against exactly
    # the database the service is about to serve from.
    config.attributes["connection"] = engine

    head = _head_revision(config)
    before = _current_revision(engine)
    command.upgrade(config, "head")
    after = _current_revision(engine)
    if after != head:
        raise RuntimeError(
            f"alembic upgrade did not reach head: before={before!r} "
            f"after={after!r} head={head!r}"
        )
    return before, after


def _default_engine():
    """The application's own engine — the one env.py falls back to."""
    from storage.relational.session import engine

    return engine


def run(engine=None, config_path: Optional[Path] = None, log=print) -> Tuple[Optional[str], Optional[str]]:
    """Locked upgrade with journal-friendly before/after logging."""
    with _upgrade_lock(_lock_path(), _lock_timeout_s()):
        before, after = upgrade_to_head(engine or _default_engine(), config_path)
    log(f"MEMORA-MIGRATION before={before or 'none'} after={after or 'none'} status=at-head")
    return before, after


def main() -> int:
    # The app resolves its settings (.env, data paths) relative to the
    # Memora root — the unit's WorkingDirectory. Fleet CD invokes this
    # script from the repo root, so anchor the process here first;
    # otherwise the migration could read a different .env than the
    # service is about to boot with.
    os.chdir(MEMORA_ROOT)
    try:
        run()
    except Exception as exc:  # noqa: BLE001 - the exit code is the contract
        print(f"MEMORA-MIGRATION FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
