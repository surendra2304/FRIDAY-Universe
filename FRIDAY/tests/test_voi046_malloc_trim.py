"""Tests for the VOI-046 malloc_trim fix (TASK-VOI-046).

TP10's VOI-045 root-cause probe (hub #2045 comments #1195/#1196) proved
the FRIDAY.service growth is native glibc arena retention — [heap] 76 MB
+ arenas 56/28/19/19 MB, traced Python only ~5% of RSS, a +11.5 MB
anonymous step in 30 s with file-backed PSS flat — and prescribed
periodic malloc_trim(0) on the memory-watch tick, measuring the
post-trim plateau before any cap talk. The trim rides the
ProactiveEngine (the repo's committed in-process memory watch, running
in the FRIDAY.service process); the tick named in the prescription
(TP1's FRD-064 tracemalloc watch) exists only as uncommitted
instrumentation on FRIDAY-Server and is not in the repo.
"""

from __future__ import annotations

import ctypes
import time

import friday.observability.proactive_engine as engine_module
from friday.observability.notifications import NotificationManager
from friday.observability.proactive_engine import (
    ProactiveEngine,
    _malloc_trim_enabled,
    _malloc_trim_interval_s,
    _read_rss_mb,
    trim_allocator,
)


def _engine(**kwargs):
    return ProactiveEngine(NotificationManager(), **kwargs)


# -- trim_allocator ---------------------------------------------------------


def test_trim_allocator_returns_measured_result():
    result = trim_allocator()
    assert set(result) == {
        "supported", "trimmed",
        "rss_before_mb", "rss_after_mb", "reclaimed_mb",
    }
    assert isinstance(result["supported"], bool)
    assert isinstance(result["trimmed"], bool)
    if result["supported"]:
        # On glibc/Linux the call succeeds and RSS readings are real.
        assert result["rss_before_mb"] > 0
        assert result["rss_after_mb"] > 0
        assert result["reclaimed_mb"] >= 0
        assert result["reclaimed_mb"] <= result["rss_before_mb"]


def test_trim_allocator_fail_soft_without_libc(monkeypatch):
    def _boom(*args, **kwargs):
        raise OSError("no libc here")

    monkeypatch.setattr(ctypes, "CDLL", _boom)
    result = trim_allocator()
    assert result["supported"] is False
    assert result["trimmed"] is False


def test_trim_allocator_fail_soft_when_trim_raises(monkeypatch):
    class FakeLibc:
        def __init__(self, *args, **kwargs):
            pass

        @property
        def malloc_trim(self):
            def _raise(_pad):
                raise RuntimeError("trim exploded")

            return _raise

    monkeypatch.setattr(ctypes, "CDLL", FakeLibc)
    result = trim_allocator()
    assert result["supported"] is False


def test_read_rss_mb_positive_on_linux():
    assert _read_rss_mb() > 0


# -- env gate + interval ----------------------------------------------------


def test_trim_disabled_by_env(monkeypatch):
    monkeypatch.setenv("FRIDAY_MALLOC_TRIM_ENABLED", "0")
    assert _malloc_trim_enabled() is False
    monkeypatch.setenv("FRIDAY_MALLOC_TRIM_ENABLED", "false")
    assert _malloc_trim_enabled() is False
    monkeypatch.setenv("FRIDAY_MALLOC_TRIM_ENABLED", "1")
    assert _malloc_trim_enabled() is True


def test_trim_interval_default_and_bad_value(monkeypatch):
    monkeypatch.delenv("FRIDAY_MALLOC_TRIM_INTERVAL_S", raising=False)
    assert _malloc_trim_interval_s() == 60.0
    monkeypatch.setenv("FRIDAY_MALLOC_TRIM_INTERVAL_S", "not-a-number")
    assert _malloc_trim_interval_s() == 60.0
    monkeypatch.setenv("FRIDAY_MALLOC_TRIM_INTERVAL_S", "5")
    assert _malloc_trim_interval_s() == 5.0


# -- ProactiveEngine cadence -------------------------------------------------


def test_engine_trims_at_most_once_per_interval(monkeypatch):
    calls: list[int] = []

    def _fake_trim():
        calls.append(1)
        return {
            "supported": True,
            "trimmed": True,
            "rss_before_mb": 100.0,
            "rss_after_mb": 99.0,
            "reclaimed_mb": 1.0,
        }

    monkeypatch.setattr(engine_module, "trim_allocator", _fake_trim)
    monkeypatch.setenv("FRIDAY_MALLOC_TRIM_INTERVAL_S", "60")
    engine = _engine()
    engine._maybe_trim_allocator()
    engine._maybe_trim_allocator()
    assert len(calls) == 1
    # Interval elapsed -> trims again.
    engine._last_trim_at = time.monotonic() - 61
    engine._maybe_trim_allocator()
    assert len(calls) == 2


def test_engine_trim_disabled_is_noop(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(engine_module, "trim_allocator", lambda: calls.append(1))
    monkeypatch.setenv("FRIDAY_MALLOC_TRIM_ENABLED", "0")
    engine = _engine()
    engine._maybe_trim_allocator()
    assert calls == []


def test_engine_trim_never_raises(monkeypatch):
    def _boom():
        raise RuntimeError("trim exploded")

    monkeypatch.setattr(engine_module, "trim_allocator", _boom)
    engine = _engine()
    engine._maybe_trim_allocator()  # must not raise
