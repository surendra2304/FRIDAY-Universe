"""TASK-REL-070 regression: Stratex supervision daemon threads must stop cleanly.

Root cause: importing the Stratex dashboard starts an infinite-loop daemon
keeper thread (``stratex-status-summary-keeper``), and each keeper pass can
spawn a long-running market-analysis refresh thread
(``stratex-market-analysis-refresh``) that logs while it runs. If either
thread is alive when CPython finalizes, the interpreter aborts (``Fatal
Python error: _enter_buffered_busy: could not acquire lock for
<_io.BufferedWriter name='<stderr>'> at interpreter shutdown, possibly due
to daemon threads`` -> SIGABRT -> exit 134) after every test passed. That
abort failed the fleet-layout gate on board-only diffs 10 times in the
2026-11-21/22 window (runs 44874617299, 44875277858, 44894544460,
44934353024, 44967481885, 44994834215, 45008909833, 45048755358,
45052231024, 45082613824 — all "3723-3728 passed" then ``Aborted (core
dumped)``), green on re-run every time.

The fix has two halves: ``stop_status_summary_keeper()`` in
``Stratex/api/friday_supervision.py`` (stop event + join the keeper and any
in-flight refresh threads) and a ``pytest_sessionfinish`` hook in
``tests/conftest.py`` that calls it. These tests cover the first half
directly; the hook is exercised by every suite run.

Import hygiene matters here: the suite's e2e test imports the Stratex
dashboard, which starts the keeper on the ``api.friday_supervision`` module
object already in ``sys.modules``. These tests REUSE that module object and
stop its keeper first. A purge + re-import would create a second module
object whose keeper thread no stop call could reach (the first keeper would
be orphaned and keep the shutdown race alive), so that pattern is
deliberately not used.
"""
from __future__ import annotations

import os
import sys
import threading
import time

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KEEPER_NAME = "stratex-status-summary-keeper"
REFRESH_NAME = "stratex-market-analysis-refresh"


def _count_named(name: str) -> int:
    return sum(1 for t in threading.enumerate() if t.is_alive() and t.name == name)


def _wait_for_name(name: str, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _count_named(name) > 0:
            return True
        time.sleep(0.05)
    return False


class TestRel070ShutdownThreads:
    """Use the supervision module object the suite already imported."""

    @classmethod
    def setup_class(cls):
        sup = sys.modules.get("api.friday_supervision") or sys.modules.get(
            "Stratex.api.friday_supervision"
        )
        if sup is None:
            from repo_isolation import purge_ambiguous_modules

            purge_ambiguous_modules()
            stratex_path = os.path.join(REPO_ROOT, "Stratex")
            if stratex_path in sys.path:
                sys.path.remove(stratex_path)
            sys.path.insert(0, stratex_path)
            import api.friday_supervision as sup

        cls.sup = sup
        # Clean slate: stop any keeper an earlier test started, so each
        # test below starts from exactly one known keeper.
        sup.stop_status_summary_keeper(timeout=120)

    @classmethod
    def teardown_class(cls):
        # Never leak a keeper into the rest of the suite.
        cls.sup.stop_status_summary_keeper(timeout=120)

    @pytest.fixture(autouse=True)
    def _stop_keeper(self, monkeypatch):
        monkeypatch.setattr(self.sup, "_compute_engine_status_summary", lambda: {})
        monkeypatch.setattr(self.sup, "_STATUS_SUMMARY_KEEPER_INTERVAL_S", 0.05)
        yield
        self.sup.stop_status_summary_keeper(timeout=120)

    def test_keeper_stops_and_thread_dies(self):
        before = _count_named(KEEPER_NAME)
        thread = self.sup.start_status_summary_keeper()
        assert thread is not None
        assert thread.is_alive()
        assert self.sup.stop_status_summary_keeper(timeout=10) is True
        assert not thread.is_alive()
        assert _count_named(KEEPER_NAME) == before

    def test_start_after_stop_restarts_keeper(self):
        # Stopping an idle keeper is a no-op success ...
        assert self.sup.stop_status_summary_keeper(timeout=10) is True
        # ... and a later start works again (the stop event is cleared).
        thread = self.sup.start_status_summary_keeper()
        assert thread is not None and thread.is_alive()
        assert self.sup.stop_status_summary_keeper(timeout=10) is True
        assert not thread.is_alive()

    def test_analysis_refresh_thread_is_joined_on_stop(self, monkeypatch):
        """A slow in-flight refresh is waited out, not abandoned at exit."""
        started = threading.Event()

        def _slow_refresh(payload=None):
            started.set()
            time.sleep(2.0)
            return {}

        monkeypatch.setattr(self.sup, "_run_market_analysis", _slow_refresh)
        monkeypatch.setattr(self.sup, "_safe_engine", lambda: None)
        # Force a stale snapshot so _ensure_market_analysis spawns a thread.
        self.sup._STATUS_SUMMARY_KEEPER_STOP.clear()
        saved_analysis = self.sup._LAST_MARKET_ANALYSIS
        saved_ts = self.sup._LAST_MARKET_ANALYSIS_TS
        saved_running = self.sup._ANALYSIS_REFRESH_RUNNING
        self.sup._LAST_MARKET_ANALYSIS = None
        self.sup._LAST_MARKET_ANALYSIS_TS = 0.0
        self.sup._ANALYSIS_REFRESH_RUNNING = False
        try:
            self.sup._ensure_market_analysis()
            assert started.wait(timeout=10), "refresh thread never started"
            assert _wait_for_name(REFRESH_NAME, timeout=10)
            t0 = time.monotonic()
            assert self.sup.stop_status_summary_keeper(timeout=30) is True
            waited = time.monotonic() - t0
            assert waited >= 1.0, "stop returned without joining the refresh"
            assert _count_named(REFRESH_NAME) == 0
        finally:
            self.sup._LAST_MARKET_ANALYSIS = saved_analysis
            self.sup._LAST_MARKET_ANALYSIS_TS = saved_ts
            self.sup._ANALYSIS_REFRESH_RUNNING = saved_running

    def test_no_refresh_spawned_after_stop(self, monkeypatch):
        """After a stop, _ensure_market_analysis must not start new work."""
        monkeypatch.setattr(self.sup, "_run_market_analysis", lambda payload=None: {})
        monkeypatch.setattr(self.sup, "_safe_engine", lambda: None)
        self.sup.stop_status_summary_keeper(timeout=10)
        self.sup._LAST_MARKET_ANALYSIS = None
        self.sup._LAST_MARKET_ANALYSIS_TS = 0.0
        self.sup._ANALYSIS_REFRESH_RUNNING = False
        try:
            self.sup._ensure_market_analysis()
            assert _count_named(REFRESH_NAME) == 0
        finally:
            self.sup._STATUS_SUMMARY_KEEPER_STOP.clear()


class TestRel070PurgeOrphan:
    """A repo_isolation purge must not orphan supervision threads.

    Regression (TASK-REL-070 follow-up): the Nov 23 fix joins the keeper
    at ``pytest_sessionfinish`` via the ``api.friday_supervision`` module
    object in ``sys.modules`` — but ``tests/test_e2e_real_repo_integration.py``
    calls ``purge_ambiguous_modules()`` after the dashboard import started
    the keeper, and the purge drops ``api.*`` from ``sys.modules`` (``"api"``
    is in ``AMBIGUOUS_TOP_LEVEL_NAMES``). The keeper thread keeps running
    on the orphaned module object, the sessionfinish hook can no longer
    find the module to stop it, and the gate still aborts at interpreter
    shutdown — runs 45157161309 (Nov 23), 45505142262 + 45514408464*
    (Nov 24), 45756595864 (Nov 26): all tests pass, then ``Fatal Python
    error: _enter_buffered_busy ... at interpreter shutdown, possibly due
    to daemon threads`` with the ``friday_supervision.py`` refresh frames,
    exit 250 (SIGABRT, returncode -6, via the REL-081 runner's
    ``sys.exit(-6)``). (*45514408464's base predates the Nov 23 fix, so it
    is a pre-fix occurrence, not a recurrence.)
    """

    def test_purge_does_not_orphan_supervision_keeper(self):
        from repo_isolation import purge_ambiguous_modules

        sup = sys.modules.get("api.friday_supervision") or sys.modules.get(
            "Stratex.api.friday_supervision"
        )
        if sup is None:
            import api.friday_supervision as sup
        sup.stop_status_summary_keeper(timeout=30)
        thread = sup.start_status_summary_keeper()
        assert thread is not None and thread.is_alive()
        try:
            purge_ambiguous_modules()
            assert "api.friday_supervision" not in sys.modules
            # The invariant: after a purge, no supervision thread may be
            # alive that the sessionfinish hook can no longer reach. The
            # purge must stop the keeper before dropping the module.
            assert not thread.is_alive(), (
                "purge orphaned the supervision keeper: the keeper thread "
                "is still alive but api.friday_supervision is gone from "
                "sys.modules, so pytest_sessionfinish cannot stop it and "
                "the gate can abort at interpreter shutdown"
            )
            assert _count_named(KEEPER_NAME) == 0
            assert _count_named(REFRESH_NAME) == 0
        finally:
            # Clean up via the held reference — the sessionfinish hook
            # cannot reach this module object any more (that is the bug).
            sup.stop_status_summary_keeper(timeout=30)

    def test_dashboard_import_under_pytest_starts_no_keeper(self):
        """Importing the Stratex dashboard under pytest must not start the keeper.

        The keeper is a production warming optimisation; under pytest the
        dashboard import must not start it (TASK-REL-070 follow-up). A
        keeper started at import time is orphaned by the suite's
        repo_isolation purges and aborts the gate at interpreter shutdown.
        Tests that need the keeper call start_status_summary_keeper()
        directly (as TestRel070ShutdownThreads does).
        """
        for name in (
            "Stratex.dashboard",
            "api.friday_supervision",
            "Stratex.api.friday_supervision",
        ):
            sys.modules.pop(name, None)
        before = _count_named(KEEPER_NAME)
        import Stratex.dashboard  # noqa: F401  (import starts the keeper pre-fix)

        assert _count_named(KEEPER_NAME) == before, (
            "dashboard import under pytest started the supervision keeper; "
            "the keeper must only start outside a test process"
        )
