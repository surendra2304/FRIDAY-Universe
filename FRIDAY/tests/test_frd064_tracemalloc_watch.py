"""TASK-FRD-064: tests for the env-gated tracemalloc observation watch.

The watch must be inert unless FRIDAY_TRACEMALLOC=1, must write
timestamped allocation-diff ticks while enabled, and must never raise
into startup or shutdown. Tests run the watch with a short interval
against a tmp log file; every test stops the watch in a finally so no
global tracemalloc state leaks into the rest of the suite.
"""

import os
import time
import tracemalloc

import pytest

from friday.core import tracemalloc_watch as watch


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in (
        watch.ENV_VAR,
        watch.INTERVAL_ENV_VAR,
        watch.LOG_ENV_VAR,
    ):
        monkeypatch.delenv(var, raising=False)
    yield
    watch.stop_tracemalloc_watch()
    if tracemalloc.is_tracing():
        tracemalloc.stop()


def test_disabled_by_default_does_nothing(tmp_path):
    log = tmp_path / "trace.log"
    assert watch.maybe_start_tracemalloc_watch() is False
    assert watch.is_watching() is False
    assert not tracemalloc.is_tracing()
    assert not log.exists()


def test_enabled_writes_ticks_with_allocation_diffs(monkeypatch, tmp_path):
    log = tmp_path / "trace.log"
    monkeypatch.setenv(watch.ENV_VAR, "1")
    monkeypatch.setenv(watch.INTERVAL_ENV_VAR, "0.2")
    monkeypatch.setenv(watch.LOG_ENV_VAR, str(log))
    assert watch.maybe_start_tracemalloc_watch() is True
    assert watch.is_watching() is True
    assert tracemalloc.is_tracing()
    # Hold a distinctive allocation alive across ticks so a diff exists.
    retained = [0] * 300_000
    time.sleep(0.55)
    assert len(retained) == 300_000
    watch.stop_tracemalloc_watch()
    text = log.read_text(encoding="utf-8")
    assert "tick rss_mb=" in text
    assert "traced_mb=" in text
    assert "shutdown rss_mb=" in text
    assert "MB" in text


def test_bad_interval_falls_back_to_default(monkeypatch, tmp_path):
    log = tmp_path / "trace.log"
    monkeypatch.setenv(watch.ENV_VAR, "true")
    monkeypatch.setenv(watch.INTERVAL_ENV_VAR, "not-a-number")
    monkeypatch.setenv(watch.LOG_ENV_VAR, str(log))
    assert watch.maybe_start_tracemalloc_watch() is True
    assert watch._interval_s == watch.DEFAULT_INTERVAL_S
    watch.stop_tracemalloc_watch()
    assert "shutdown rss_mb=" in log.read_text(encoding="utf-8")


def test_start_is_idempotent_and_stop_is_safe(monkeypatch, tmp_path):
    log = tmp_path / "trace.log"
    monkeypatch.setenv(watch.ENV_VAR, "yes")
    monkeypatch.setenv(watch.INTERVAL_ENV_VAR, "0.2")
    monkeypatch.setenv(watch.LOG_ENV_VAR, str(log))
    assert watch.maybe_start_tracemalloc_watch() is True
    assert watch.maybe_start_tracemalloc_watch() is True
    assert watch.stop_tracemalloc_watch() is True
    assert watch.is_watching() is False
    # Second stop is a no-op, never raises.
    assert watch.stop_tracemalloc_watch() is False


def test_env_values_other_than_truthy_do_not_enable(monkeypatch):
    for value in ("0", "false", "no", "", "off"):
        monkeypatch.setenv(watch.ENV_VAR, value)
        assert watch.maybe_start_tracemalloc_watch() is False
        assert watch.is_watching() is False
