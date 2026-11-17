"""TASK-STR-FWD-017 — unrecorded_close alert resolver + raise-time stamp.

Live evidence (diagnosis 2026-11-17, ~/workspace/unrecorded-close):
the unrecorded_close latch on S1 has been ACTIVE since 2026-11-14
(count 5, latest detail "fill rejected, missing ['qty']: BTCUSDT").
A three-way census proved the instance benign — every close of the
era is in the fill ledger, order-id for order-id — but the latch can
never clear: append_fill() raises this kind on a rejected row, and
NOTHING in the code called clear_alert("unrecorded_close") (only
venue_unhealthy and untracked_position had clearers). Worse, every
future genuine rejection silently merges into the same latch:
raise_alert overwrites detail/updated_at on each raise, so raises
#2-#4 of the live instance are individually unrecoverable.

Fix, two parts:

  1. Sweep resolver in the daemon's reconciliation sweep, shaped
     like the untracked_position resolver beside it: on a COMPLETE
     sweep, if the latch's raise count is unchanged since the
     previous complete sweep (no append_fill rejection and no
     closed-without-a-row detection in the interval — every such
     event bumps the count), clear the alert. An incomplete sweep
     never clears and never touches the baseline; the first complete
     sweep after startup only sets the baseline.

  2. Raise-time stamp: raise_alert() gains an optional keyword-only
     ``stamp`` stored on the latch as ``last_rejected``; append_fill
     stamps both of its unrecorded_close raises with the rejected
     row's identity (symbol, order_id, entry_order_id, signal_id,
     rejected_at; the validation path also records the missing-field
     list). A raise without a stamp preserves an existing one. Old
     latch files without the stamp load unchanged.

Tests (daemon tests drive the REAL _reconcile_positions sweep with a
stub adapter, the FWD-014 harness pattern):

  (a) alert clears on the second consecutive clean complete sweep
      (FAILS on pristine code: nothing ever clears it)
  (b) a rejection between sweeps blocks the clear; the following
      clean sweep clears (FAILS on pristine)
  (c) an incomplete sweep never clears and does not consume the
      baseline (FAILS on pristine)
  (d) the stamp is recorded by both append_fill raise paths,
      survives a reload from disk, is replaced by a newer rejection,
      is preserved across a stamp-less raise, and old-format latches
      still load (FAILS on pristine: no stamp exists)
  (e) unchanged behaviour: untracked_position still clears on the
      FIRST clean complete sweep; venue_unhealthy is NOT cleared by
      the daemon sweep (passes before and after)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from measurement import fill_ledger  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_state_dir(tmp_path, monkeypatch):
    """All fill-ledger / alert writes land in a tmp state dir."""
    monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path / "mstate"))
    yield


# ---------------------------------------------------------------------------
# Daemon sweep harness (same pattern as test_fwd014_untracked_alert_integrity)
# ---------------------------------------------------------------------------

class _StubAdapter:
    """Venue adapter stub. ``live`` is what get_positions_or_none()
    returns: a list is a successful read ([] = genuinely flat), None
    is a failed read (state unknown -> the sweep is incomplete)."""

    def __init__(self, live):
        self.live = live
        self.base_url = ""

    def get_positions_or_none(self):
        return self.live


class _StubEngine:
    def __init__(self, adapter):
        self.positions = {}
        self.venues = {"binance_futures": adapter}
        self.position_opened_at = {}
        self.position_strategy = {}
        self.position_timeframe = {}
        self.realized_pnl = 100.0
        self.daily_realized_pnl = 10.0
        self.telegram_bot = None
        self.breaker_checks = 0
        self.exits = []

    def _check_daily_loss_limit(self):
        self.breaker_checks += 1

    def save_state(self):
        pass

    def get_ticker(self, venue, symbol):
        return None

    def equity_snapshot(self, trigger=None):
        return {"trigger": trigger}

    def mark_exit(self, venue, symbol):
        self.exits.append((venue, symbol))


def _make_daemon(engine, tmp_path, monkeypatch):
    from autonomy import run_daemon

    # Redirect the legacy testnet ledger into tmp (path derives from
    # run_daemon.__file__).
    monkeypatch.setattr(
        run_daemon, "__file__", str(tmp_path / "autonomy" / "run_daemon.py")
    )
    daemon = object.__new__(run_daemon.StratexTradingEngine)
    daemon.engine = engine
    daemon._reconcile_pass = 19  # next pass runs the sweep
    return daemon


def _sweep(daemon):
    """Run one reconciliation pass with the every-20th-pass sweep due."""
    daemon._reconcile_pass = 19
    daemon._reconcile_positions()


def _rejected_row(**overrides):
    """A close row append_fill must reject: every required field is
    present except qty (the live instance's exact failure shape)."""
    row = {
        "strategy": "strategy_dow_effect",
        "engine": "daemon",
        "venue": "binance_futures",
        "symbol": "BTCUSDT",
        "side": "LONG",
        "entry_price": 64000.0,
        "exit_price": 64812.8,
        "qty": None,
        "gross_pnl": 1.10,
        "fees": 0.05,
        "net_pnl": 1.05,
        "exit_reason": "SL_TP_BROKER",
        "order_id": "exit-1001",
        "entry_order_id": "entry-1001",
        "signal_id": "sig-1001",
    }
    row.update(overrides)
    return row


def _latch_via_rejection(**overrides):
    """Raise unrecorded_close through the real append_fill path."""
    assert fill_ledger.append_fill(_rejected_row(**overrides)) is None
    assert "unrecorded_close" in fill_ledger.active_alerts()


# ---------------------------------------------------------------------------
# (a) Clean complete sweeps clear the alert (second sweep)
# ---------------------------------------------------------------------------

def test_unrecorded_close_clears_on_second_clean_complete_sweep(
    tmp_path, monkeypatch
):
    _latch_via_rejection()
    adapter = _StubAdapter(live=[])  # successful read, flat venue
    daemon = _make_daemon(_StubEngine(adapter), tmp_path, monkeypatch)

    _sweep(daemon)
    assert "unrecorded_close" in fill_ledger.active_alerts(), (
        "the first complete sweep only sets the baseline — a latch "
        "raised before the daemon started must not clear on sight"
    )
    assert getattr(daemon, "_unrecorded_close_seen_count", None) == 1

    _sweep(daemon)
    assert "unrecorded_close" not in fill_ledger.active_alerts(), (
        "no rejection since the previous complete sweep: the latch "
        "must clear instead of staying ACTIVE forever"
    )
    assert getattr(daemon, "_unrecorded_close_seen_count", None) is None


# ---------------------------------------------------------------------------
# (b) A rejection between sweeps blocks the clear
# ---------------------------------------------------------------------------

def test_rejection_between_sweeps_blocks_the_clear(tmp_path, monkeypatch):
    _latch_via_rejection()
    adapter = _StubAdapter(live=[])
    daemon = _make_daemon(_StubEngine(adapter), tmp_path, monkeypatch)

    _sweep(daemon)  # baseline = count 1
    assert "unrecorded_close" in fill_ledger.active_alerts()

    # A genuine new rejection lands between sweeps (count 1 -> 2).
    _latch_via_rejection(order_id="exit-1002", entry_order_id="entry-1002")

    _sweep(daemon)
    assert "unrecorded_close" in fill_ledger.active_alerts(), (
        "a rejection since the last sweep means a close may be "
        "unrecorded right now — the latch must NOT clear"
    )
    assert getattr(daemon, "_unrecorded_close_seen_count", None) == 2

    _sweep(daemon)  # clean interval at the new baseline
    assert "unrecorded_close" not in fill_ledger.active_alerts()


# ---------------------------------------------------------------------------
# (c) An incomplete sweep never clears and never consumes the baseline
# ---------------------------------------------------------------------------

def test_incomplete_sweep_never_clears_and_preserves_baseline(
    tmp_path, monkeypatch
):
    _latch_via_rejection()
    adapter = _StubAdapter(live=[])
    daemon = _make_daemon(_StubEngine(adapter), tmp_path, monkeypatch)

    _sweep(daemon)  # complete: baseline = 1
    assert getattr(daemon, "_unrecorded_close_seen_count", None) == 1

    adapter.live = None  # venue read starts failing
    _sweep(daemon)  # incomplete sweep
    assert "unrecorded_close" in fill_ledger.active_alerts(), (
        "an incomplete sweep cannot prove anything — it must never clear"
    )
    assert getattr(daemon, "_unrecorded_close_seen_count", None) == 1, (
        "an incomplete sweep must not consume or move the baseline"
    )

    adapter.live = []  # reads recover
    _sweep(daemon)  # complete, count still 1 == preserved baseline
    assert "unrecorded_close" not in fill_ledger.active_alerts(), (
        "with the baseline preserved across the incomplete sweep, the "
        "next clean complete sweep clears"
    )


def test_first_sweep_incomplete_then_baseline_then_clear(tmp_path, monkeypatch):
    _latch_via_rejection()
    adapter = _StubAdapter(live=None)  # reads failing from the start
    daemon = _make_daemon(_StubEngine(adapter), tmp_path, monkeypatch)

    _sweep(daemon)  # incomplete: no baseline, no clear
    assert "unrecorded_close" in fill_ledger.active_alerts()
    assert getattr(daemon, "_unrecorded_close_seen_count", None) is None

    adapter.live = []
    _sweep(daemon)  # first complete sweep: baseline only
    assert "unrecorded_close" in fill_ledger.active_alerts()

    _sweep(daemon)  # second complete sweep: clears
    assert "unrecorded_close" not in fill_ledger.active_alerts()


# ---------------------------------------------------------------------------
# (d) Raise-time stamp: recorded, reloadable, replaceable, preservable
# ---------------------------------------------------------------------------

def _alerts_on_disk():
    return json.loads(Path(fill_ledger.alerts_path()).read_text(encoding="utf-8"))


def test_rejection_stamp_recorded_and_survives_reload():
    _latch_via_rejection()
    entry = _alerts_on_disk()["alerts"]["unrecorded_close"]
    stamp = entry["last_rejected"]
    assert stamp["symbol"] == "BTCUSDT"
    assert stamp["order_id"] == "exit-1001"
    assert stamp["entry_order_id"] == "entry-1001"
    assert stamp["signal_id"] == "sig-1001"
    assert stamp["missing"] == ["qty"]
    assert stamp["rejected_at"]  # ISO timestamp present
    # Reload through the module API (fill_ledger keeps no cache — every
    # read is a fresh load from disk).
    reloaded = fill_ledger.active_alerts()["unrecorded_close"]
    assert reloaded["last_rejected"]["order_id"] == "exit-1001"
    assert reloaded["count"] == 1


def test_newer_rejection_replaces_the_stamp():
    _latch_via_rejection()
    _latch_via_rejection(
        symbol="ETHUSDT", order_id="exit-2002",
        entry_order_id="entry-2002", signal_id="sig-2002",
    )
    entry = fill_ledger.active_alerts()["unrecorded_close"]
    assert entry["count"] == 2
    assert entry["last_rejected"]["order_id"] == "exit-2002"
    assert entry["last_rejected"]["symbol"] == "ETHUSDT"


def test_stampless_raise_preserves_existing_stamp():
    """The testnet watchdog raises this kind with no row identity —
    its raise must not erase the last append_fill stamp."""
    _latch_via_rejection()
    fill_ledger.raise_alert(
        "unrecorded_close", "tracked position vanished with no fill row"
    )
    entry = fill_ledger.active_alerts()["unrecorded_close"]
    assert entry["count"] == 2
    assert entry["last_rejected"]["order_id"] == "exit-1001"


def test_append_failure_path_also_stamps(monkeypatch):
    real_append = fill_ledger._append

    def _boom(path, record):
        if Path(path) == fill_ledger.fill_ledger_path():
            raise OSError("disk full")
        return real_append(path, record)

    monkeypatch.setattr(fill_ledger, "_append", _boom)
    row = _rejected_row(qty=0.0011)  # fully valid: reaches the append
    assert fill_ledger.append_fill(row) is None
    entry = fill_ledger.active_alerts()["unrecorded_close"]
    stamp = entry["last_rejected"]
    assert stamp["order_id"] == "exit-1001"
    assert stamp["entry_order_id"] == "entry-1001"
    assert "missing" not in stamp  # not a validation rejection


def test_old_format_latch_without_stamp_still_loads():
    """Latches written before the stamp existed (the live instance's
    exact shape) must load, raise and resolve unchanged."""
    path = Path(fill_ledger.alerts_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "alerts": {
                    "unrecorded_close": {
                        "active": True,
                        "since": "2026-11-14T12:45:56.321561+00:00",
                        "updated_at": "2026-11-15T06:06:58.497032+00:00",
                        "detail": "fill rejected, missing ['qty']: BTCUSDT",
                        "count": 5,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    entry = fill_ledger.active_alerts()["unrecorded_close"]
    assert entry["count"] == 5
    assert "last_rejected" not in entry

    fill_ledger.raise_alert("unrecorded_close", "another rejection")
    entry = fill_ledger.active_alerts()["unrecorded_close"]
    assert entry["count"] == 6
    assert "last_rejected" not in entry  # stamp-less raise adds none

    fill_ledger.clear_alert("unrecorded_close")
    assert "unrecorded_close" not in fill_ledger.active_alerts()


# ---------------------------------------------------------------------------
# (e) Unchanged behaviour for the other alert kinds
# ---------------------------------------------------------------------------

def test_untracked_position_still_clears_on_first_clean_sweep(
    tmp_path, monkeypatch
):
    fill_ledger.raise_alert(
        "untracked_position",
        "binance_futures:BTCUSDT open at broker but not tracked by the daemon",
    )
    adapter = _StubAdapter(live=[])
    daemon = _make_daemon(_StubEngine(adapter), tmp_path, monkeypatch)

    _sweep(daemon)  # ONE clean complete sweep — no baseline delay
    assert "untracked_position" not in fill_ledger.active_alerts()


def test_venue_unhealthy_is_not_cleared_by_the_daemon_sweep(
    tmp_path, monkeypatch
):
    fill_ledger.raise_alert("venue_unhealthy", "binance_futures reads failing")
    adapter = _StubAdapter(live=[])
    daemon = _make_daemon(_StubEngine(adapter), tmp_path, monkeypatch)

    _sweep(daemon)
    _sweep(daemon)
    assert "venue_unhealthy" in fill_ledger.active_alerts(), (
        "venue_unhealthy is cleared by the venue engine's own health "
        "path, not by the daemon sweep — that must not change"
    )
