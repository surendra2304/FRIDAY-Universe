"""
Regression test: Forge's lifespan must NOT install process signal handlers.

Defect (fleet graceful-shutdown diagnosis, 2026-11-17): lifespan startup
registered a log-only ``loop.add_signal_handler`` for SIGTERM/SIGINT.
uvicorn installs its own SIGTERM/SIGINT handlers *before* the lifespan
runs, and the app's registration replaced that disposition — SIGTERM was
delivered exclusively to a callback that only wrote a log line, uvicorn
never set ``should_exit``, the lifespan-exit sandbox halt never ran, and
systemd SIGKILLed the service at TimeoutStopSec on every stop (10/10
sampled stops: signal log line, then exactly ~10s later, SIGKILL).

uvicorn owns SIGTERM/SIGINT. The lifespan must register nothing, so the
already-written lifespan exit (reaper cancel + sandbox terminate)
becomes the shutdown path. This test records every ``add_signal_handler``
call made while the app lifespan starts and asserts none targets
SIGTERM or SIGINT. (asyncio's own SIGCHLD child-watcher registration is
unrelated and ignored.)

DB note: at this base the lifespan's ``db_manager.init_db()`` requires a
live Oracle Autonomous Database (SQLite/PostgreSQL URLs are rejected by
``Settings.get_database_url``), which no test environment here provides.
The signal-handler block under test is independent of DB init, so the
two DB-init calls are stubbed out; everything else in the lifespan runs
for real, exactly as the other lifespan-entering suites
(test_production_api_auth, test_rate_limiting) run it.
"""

import asyncio
import asyncio.unix_events
import signal
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import app.main as main_module
from app.main import create_app

_WATCHED = (signal.SIGTERM, signal.SIGINT)


def test_lifespan_installs_no_sigterm_sigint_handlers(monkeypatch):
    monkeypatch.setattr(
        main_module.db_manager, "init_db", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        main_module.performance_optimizer,
        "optimize_sqlite_pragmas",
        AsyncMock(return_value=None),
    )

    installed: list = []
    loop_cls = asyncio.unix_events._UnixSelectorEventLoop
    original = loop_cls.add_signal_handler

    def recording(self, sig, callback, *args):
        if sig in _WATCHED:
            installed.append(sig)
        return original(self, sig, callback, *args)

    monkeypatch.setattr(loop_cls, "add_signal_handler", recording)

    app = create_app()
    with TestClient(app):
        pass  # entering the context runs the full lifespan startup

    assert installed == [], (
        f"lifespan installed signal handlers for {installed}; uvicorn must "
        "own SIGTERM/SIGINT or graceful shutdown never runs"
    )
