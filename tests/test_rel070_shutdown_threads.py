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


def _live_names() -> set[str]:
    return {t.name for t in threading.enumerate() if t.is_alive()}


class TestRel070ShutdownThreads:
    """Import the supervision module the way the dashboard does (Stratex/ first)."""

    @classmethod
    def setup_class(cls):
        from repo_isolation import purge_ambiguous_modules

        purge_ambiguous_modules()
        stratex_path = os.path.join(REPO_ROOT, "Stratex")
        if stratex_path in sys.path:
            sys.path.remove(stratex_path)
        sys.path.insert(0, stratex_path)
        import api.friday_supervision as sup

        cls.sup = sup

    @classmethod
    def teardown_class(cls):
        # Never leak a keeper into the rest of the suite.
        cls.sup.stop_status_summary_keeper(timeout=30)

    @pytest.fixture(autouse=True)
    def _stop_keeper(self, monkeypatch):
        monkeypatch.setattr(self.sup, "_compute_engine_status_summary", lambda: {})
        monkeypatch.setattr(self.sup, "_STATUS_SUMMARY_KEEPER_INTERVAL_S", 0.05)
        yield
        self.sup.stop_status_summary_keeper(timeout=30)

    def test_keeper_stops_and_thread_dies(self):
        thread = self.sup.start_status_summary_keeper()
        assert thread is not None
        assert thread.is_alive()
        assert KEEPER_NAME in _live_names()
        assert self.sup.stop_status_summary_keeper(timeout=10) is True
        assert not thread.is_alive()
        assert KEEPER_NAME not in _live_names()

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
            assert REFRESH_NAME in _live_names()
            t0 = time.monotonic()
            assert self.sup.stop_status_summary_keeper(timeout=30) is True
            waited = time.monotonic() - t0
            assert waited >= 1.0, "stop returned without joining the refresh"
            assert REFRESH_NAME not in _live_names()
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
            assert REFRESH_NAME not in _live_names()
        finally:
            self.sup._STATUS_SUMMARY_KEEPER_STOP.clear()
