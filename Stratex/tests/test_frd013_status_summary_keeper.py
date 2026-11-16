"""TASK-FRD-013: the status-summary snapshot is kept warm by a keeper,
so a read never pays the unbounded synchronous compute.

Production incident (2026-11-16 13:38 IST, journals on Server 1):
Stratex.service restarted 13:26:37 (deploy). The owner's figures
question at 13:38:10 was the FIRST status read in the new process —
cache cold, engine singleton unconstructed. Stratex logged the
/v1/task/execute audit at 13:38:13 and completed it at 13:39:16
(63 s: strategy-registry flood + engine construction inline on the
request thread), while FRIDAY's mesh budget is 30 s → the brain
answered "Stratex could not answer that: ReadTimeout" at calm host
load (0.42). The same path in a warm process answered in 4 s (12:22).

The FRD-011 cache only absorbs reads that arrive within 60 s of a
previous compute; status questions are sporadic, so that cadence never
happens by itself. Pins:
- a keeper pass computes the snapshot through the existing
  single-flight refresh machinery and clears the flag;
- a keeper pass is a no-op while a refresh is already in flight;
- with keeper passes on the 30 s cadence, a read arriving long after
  process start still serves the snapshot — it never falls into the
  beyond-bound synchronous compute (the incident branch);
- starting the keeper is idempotent, and the dashboard wires the start.
"""

import time

import pytest

from api import friday_supervision as sup


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    with sup._STATUS_SUMMARY_LOCK:
        sup._STATUS_SUMMARY_CACHE = None
        sup._STATUS_SUMMARY_TS = 0.0
        sup._STATUS_SUMMARY_REFRESHING = False
    with sup._STATUS_SUMMARY_KEEPER_LOCK:
        sup._STATUS_SUMMARY_KEEPER_THREAD = None
    yield
    with sup._STATUS_SUMMARY_LOCK:
        sup._STATUS_SUMMARY_CACHE = None
        sup._STATUS_SUMMARY_TS = 0.0
        sup._STATUS_SUMMARY_REFRESHING = False
    with sup._STATUS_SUMMARY_KEEPER_LOCK:
        sup._STATUS_SUMMARY_KEEPER_THREAD = None


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class _ClockModule:
    """Stand-in for the stdlib time module inside friday_supervision:
    only time() is driven by the test clock; sleep stays real."""

    def __init__(self, clock):
        self._clock = clock

    def time(self):
        return self._clock.now

    def sleep(self, s):
        time.sleep(s)


@pytest.fixture
def clock(monkeypatch):
    c = _Clock()
    monkeypatch.setattr(sup, "time", _ClockModule(c))
    return c


def _counting_compute(monkeypatch):
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"balance": 100.0 + calls["n"], "timestamp": f"t{calls['n']}"}

    monkeypatch.setattr(sup, "_compute_engine_status_summary", compute)
    return calls


def test_keeper_pass_computes_and_clears_flag(monkeypatch, clock):
    calls = _counting_compute(monkeypatch)
    assert sup._keeper_refresh_once() is True
    assert calls["n"] == 1
    assert sup._STATUS_SUMMARY_CACHE["balance"] == 101.0
    assert sup._STATUS_SUMMARY_TS == 1000.0
    assert sup._STATUS_SUMMARY_REFRESHING is False


def test_keeper_pass_skips_while_refresh_in_flight(monkeypatch, clock):
    calls = _counting_compute(monkeypatch)
    with sup._STATUS_SUMMARY_LOCK:
        sup._STATUS_SUMMARY_REFRESHING = True
    assert sup._keeper_refresh_once() is False
    assert calls["n"] == 0


def test_keeper_cadence_keeps_reads_off_synchronous_compute(monkeypatch, clock):
    """The incident scenario, replayed: without the keeper, a read at
    +70 s pays the synchronous compute (FRD-011 pin); with keeper passes
    at +0/+30/+60 the same read serves the keeper's snapshot."""
    calls = _counting_compute(monkeypatch)
    assert sup._keeper_refresh_once() is True          # boot, t=1000
    clock.now += 30.0
    assert sup._keeper_refresh_once() is True          # t=1030
    clock.now += 30.0
    assert sup._keeper_refresh_once() is True          # t=1060
    assert calls["n"] == 3
    keeper_snapshot = sup._STATUS_SUMMARY_CACHE

    clock.now += 10.0                                  # t=1070: the "owner question"
    served = sup._get_engine_status_summary()
    # Served the keeper-warmed snapshot (TTL/SWR branch) — a synchronous
    # compute would have returned a NEW dict (balance 104.0).
    assert served is keeper_snapshot
    assert served["balance"] == 103.0


def test_keeper_interval_leaves_headroom_under_the_staleness_bound():
    # One full cadence plus a slow compute must still land inside the
    # FRD-011 hard bound, or the keeper could not keep its promise.
    assert sup._STATUS_SUMMARY_KEEPER_INTERVAL_S == 30.0
    assert sup._STATUS_SUMMARY_KEEPER_INTERVAL_S * 2 <= sup._STATUS_SUMMARY_MAX_STALE_S


class _FakeThread:
    instances = []

    def __init__(self, target=None, daemon=None, name=None):
        self.target = target
        self.name = name
        self._alive = False
        _FakeThread.instances.append(self)

    def start(self):
        self._alive = True

    def is_alive(self):
        return self._alive


def test_start_keeper_is_idempotent(monkeypatch):
    _FakeThread.instances = []
    monkeypatch.setattr(sup.threading, "Thread", _FakeThread)
    first = sup.start_status_summary_keeper()
    assert first is not None
    assert first.name == "stratex-status-summary-keeper"
    second = sup.start_status_summary_keeper()
    assert second is None
    assert len(_FakeThread.instances) == 1


def test_dashboard_starts_the_keeper():
    from pathlib import Path

    dashboard = Path(sup.__file__).resolve().parent.parent / "dashboard.py"
    source = dashboard.read_text(encoding="utf-8")
    assert "start_status_summary_keeper" in source, (
        "dashboard startup must start the status-summary keeper, or the "
        "first status read after every restart pays the engine compute"
    )
