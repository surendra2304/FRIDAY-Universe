"""TASK-FRD-011: the status summary is served from a snapshot, not by
paying live-engine calls on every read.

Production evidence: Stratex's /v1/task/execute "status" wall time was
~14 s in FRD-005 re-run 20261116-103839 and 24–90+ s under load in the
FRD-011 probes, while the handler's own execution_time_ms was ~4 s of
one 24 s sample — the read pays engine + process contention inline.
FRIDAY's mesh dispatch budget (30 s after this task; 10 s before)
cannot cover that tail, so voice/chat delegations returned timeout
text instead of Stratex's real state.

Pins (the TASK-VOI-006 pattern, applied to the summary):
- first read computes; reads inside the TTL serve the snapshot;
- a stale read (TTL..MAX_STALE) serves the snapshot AND starts exactly
  one background refresh (single-flight);
- a read beyond MAX_STALE (Stratex's own 60 s telemetry bound)
  computes synchronously rather than serving ancient money data;
- a failed background refresh keeps the last good snapshot and clears
  the single-flight flag so a later read can retry.
"""

import threading
import time

import pytest

from api import friday_supervision as sup


@pytest.fixture(autouse=True)
def _reset_cache(monkeypatch):
    with sup._STATUS_SUMMARY_LOCK:
        sup._STATUS_SUMMARY_CACHE = None
        sup._STATUS_SUMMARY_TS = 0.0
        sup._STATUS_SUMMARY_REFRESHING = False
    yield
    with sup._STATUS_SUMMARY_LOCK:
        sup._STATUS_SUMMARY_CACHE = None
        sup._STATUS_SUMMARY_TS = 0.0
        sup._STATUS_SUMMARY_REFRESHING = False


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    c = _Clock()
    monkeypatch.setattr(sup, "time", _ClockModule(c))
    return c


class _ClockModule:
    """Stand-in for the stdlib time module inside friday_supervision:
    only time() is driven by the test clock; sleep stays real."""

    def __init__(self, clock):
        self._clock = clock

    def time(self):
        return self._clock.now

    def sleep(self, s):
        time.sleep(s)


def _counting_compute(monkeypatch, fail=False):
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        if fail:
            raise RuntimeError("engine unavailable")
        return {"balance": 100.0 + calls["n"], "timestamp": f"t{calls['n']}"}

    monkeypatch.setattr(sup, "_compute_engine_status_summary", compute)
    return calls


def test_first_read_computes_then_ttl_serves_snapshot(monkeypatch, clock):
    calls = _counting_compute(monkeypatch)
    first = sup._get_engine_status_summary()
    assert first["balance"] == 101.0
    clock.now += sup._STATUS_SUMMARY_TTL_S - 1.0
    again = sup._get_engine_status_summary()
    assert again is first
    assert calls["n"] == 1


def test_stale_read_serves_snapshot_and_refreshes_once(monkeypatch, clock):
    calls = _counting_compute(monkeypatch)
    first = sup._get_engine_status_summary()
    clock.now += sup._STATUS_SUMMARY_TTL_S + 5.0

    refreshed = threading.Event()
    real_refresh = sup._refresh_status_summary

    def refresh_and_signal():
        real_refresh()
        refreshed.set()

    monkeypatch.setattr(sup, "_refresh_status_summary", refresh_and_signal)
    served = sup._get_engine_status_summary()
    assert served is first  # stale snapshot served immediately
    assert refreshed.wait(timeout=5.0)
    assert calls["n"] == 2  # exactly one background recompute
    # The refreshed snapshot is now the fresh one.
    assert sup._STATUS_SUMMARY_CACHE["balance"] == 102.0
    assert sup._get_engine_status_summary()["balance"] == 102.0
    assert calls["n"] == 2


def test_beyond_max_stale_computes_synchronously(monkeypatch, clock):
    calls = _counting_compute(monkeypatch)
    sup._get_engine_status_summary()
    clock.now += sup._STATUS_SUMMARY_MAX_STALE_S + 1.0
    fresh = sup._get_engine_status_summary()
    assert fresh["balance"] == 102.0
    assert calls["n"] == 2


def test_failed_refresh_keeps_last_good_snapshot(monkeypatch, clock):
    calls = _counting_compute(monkeypatch)
    first = sup._get_engine_status_summary()
    clock.now += sup._STATUS_SUMMARY_TTL_S + 5.0
    monkeypatch.setattr(
        sup, "_compute_engine_status_summary",
        lambda: (_ for _ in ()).throw(RuntimeError("engine unavailable")),
    )
    served = sup._get_engine_status_summary()
    assert served is first
    # Wait for the background refresh to finish failing.
    deadline = time.time() + 5.0
    while time.time() < deadline and sup._STATUS_SUMMARY_REFRESHING:
        time.sleep(0.02)
    assert sup._STATUS_SUMMARY_REFRESHING is False
    assert sup._STATUS_SUMMARY_CACHE is first


def test_cache_bounds_match_stratex_telemetry_limit():
    assert sup._STATUS_SUMMARY_TTL_S == 10.0
    # advisory_gate.MAX_TELEMETRY_STALENESS_SECONDS = 60.0: a status
    # snapshot is never served older than the fleet's own bound.
    assert sup._STATUS_SUMMARY_MAX_STALE_S == 60.0
