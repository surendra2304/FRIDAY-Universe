"""TASK-STR-FWD-014 — untracked_position alert integrity: the alert may
clear only on a SUCCESSFUL venue read.

Live evidence (orphan census, 2026-11-17): the untracked_position
alert for OANDA trade 470 (USDJPY LONG 15 @ 159.691, sleeve-owned,
forgotten by the sleeve) went INACTIVE at 2026-11-17T03:27:26Z —
inside the 03:07Z venue_unhealthy window, while OANDA reads were
failing and the position was still open. The alert cleared on a
FAILED read, not on a resolution.

Root cause: the daemon sweep's clear guard (TASK-STR-FWD-007) keys on
a venue read returning None via get_positions_or_none(), but
OandaExchangeAdapter never implemented that method — only the Binance
adapter had it. For the oanda venue the sweep therefore fell back to
get_positions(), which returns [] on ANY failure (no credentials, or
_request() -> None on an HTTP error / missing "account" key). A
failed read was indistinguishable from a genuinely flat account:
sweep_complete stayed True, no untracked positions were "found", and
the sweep cleared the latch. TASK-STR-FWD-007's own tests never
exercised this path — their stub adapter defines
get_positions_or_none.

Fix: OandaExchangeAdapter.get_positions_or_none() mirrors the Binance
contract (None = state unknown; [] = genuinely flat);
get_positions() keeps its exact legacy contract ([] on failure) for
existing callers. The sweep itself is unchanged — its FWD-007 guard
now engages for the oanda venue too.

These tests drive the REAL OandaExchangeAdapter (request layer
stubbed) through the daemon's _reconcile_positions sweep:

  (a) failed read                       -> alert stays latched
      (FAILS on pristine code: the sweep clears it)
  (b) successful read, position open
      and untracked                     -> alert stays latched
  (c) successful read, account flat     -> alert clears
  (d) successful read, position open
      and tracked by the daemon         -> alert clears

plus adapter-contract pins for the None-vs-[] semantics.
"""

from __future__ import annotations

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from measurement import fill_ledger  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_state_dir(tmp_path, monkeypatch):
    """All fill-ledger / alert writes land in a tmp state dir."""
    monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path / "mstate"))
    yield


# ---------------------------------------------------------------------------
# Real OANDA adapter with the request layer stubbed
# ---------------------------------------------------------------------------

_PRICING = {"prices": [{"bids": [{"price": "159.100"}], "asks": [{"price": "159.120"}]}]}

_ACCOUNT_WITH_USDJPY = {
    "account": {
        "balance": "10000.0041",
        "NAV": "9999.9495",
        "marginUsed": "0",
        "marginAvailable": "9999.9495",
        "unrealizedPL": "-0.0546",
        "positions": [
            {
                "instrument": "USD_JPY",
                "long": {
                    "units": "15",
                    "averagePrice": "159.691",
                    "unrealizedPL": "-0.0546",
                    "marginRate": "0.02",
                },
                "short": {"units": "0"},
            }
        ],
    }
}

_ACCOUNT_FLAT = {
    "account": {
        "balance": "10000.0041",
        "NAV": "10000.0041",
        "marginUsed": "0",
        "marginAvailable": "10000.0041",
        "unrealizedPL": "0",
        "positions": [],
    }
}


def _make_adapter(account_payload):
    """Real OandaExchangeAdapter; _request serves the given account
    payload (None simulates a failed read: _request returns None on
    any HTTP error) and a static pricing payload."""
    from exchanges.oanda_adapter import OandaExchangeAdapter

    adapter = OandaExchangeAdapter(api_key="key", account_id="acc", practice=True)

    def _request(method, path, params=None, json=None, **kwargs):
        if "/pricing" in path:
            return _PRICING
        return account_payload

    adapter._request = _request
    return adapter


# ---------------------------------------------------------------------------
# Daemon sweep harness (same pattern as test_fwd007_booking_integrity)
# ---------------------------------------------------------------------------

class _StubPos:
    def __init__(self, symbol, side="LONG", quantity=15.0,
                 entry_price=159.691, mark_price=160.0, position_id="470"):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.entry_price = entry_price
        self.mark_price = mark_price
        self.position_id = position_id


class _StubEngine:
    def __init__(self, adapter):
        self.positions = {}
        self.venues = {"oanda": adapter}
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


def _make_daemon(engine, tmp_path, monkeypatch, reconcile_pass=19):
    from autonomy import run_daemon

    # Redirect the legacy testnet ledger into tmp (path derives from
    # run_daemon.__file__).
    monkeypatch.setattr(
        run_daemon, "__file__", str(tmp_path / "autonomy" / "run_daemon.py")
    )
    daemon = object.__new__(run_daemon.StratexTradingEngine)
    daemon.engine = engine
    daemon._reconcile_pass = reconcile_pass  # next pass runs the sweep
    return daemon


_KEY = "oanda:USDJPY"


def _latch_alert():
    fill_ledger.raise_alert(
        "untracked_position", "oanda:USDJPY open at broker but not tracked by the daemon"
    )
    assert "untracked_position" in fill_ledger.active_alerts()


# ---------------------------------------------------------------------------
# (a) A failed venue read must NOT clear the alert
# ---------------------------------------------------------------------------

def test_failed_read_keeps_untracked_alert_latched(tmp_path, monkeypatch):
    """The 2026-11-17 03:27Z failure mode: OANDA reads failing
    (venue_unhealthy window) while trade 470 is still open. On
    pristine code the sweep sees get_positions() == [] and clears."""
    _latch_alert()
    adapter = _make_adapter(None)  # every account read fails
    engine = _StubEngine(adapter)
    daemon = _make_daemon(engine, tmp_path, monkeypatch)

    daemon._reconcile_positions()

    assert "untracked_position" in fill_ledger.active_alerts(), \
        "a failed venue read must never clear the untracked_position alert"


def test_error_payload_read_keeps_untracked_alert_latched(tmp_path, monkeypatch):
    """An HTTP-level error body (no "account" key) is also a failed
    read, not a flat account."""
    _latch_alert()
    adapter = _make_adapter({"errorMessage": "service unavailable"})
    engine = _StubEngine(adapter)
    daemon = _make_daemon(engine, tmp_path, monkeypatch)

    daemon._reconcile_positions()

    assert "untracked_position" in fill_ledger.active_alerts(), \
        "an error payload must never clear the untracked_position alert"


# ---------------------------------------------------------------------------
# (b) Successful read, position still open and untracked -> stays latched
# ---------------------------------------------------------------------------

def test_successful_read_with_untracked_position_keeps_alert(tmp_path, monkeypatch):
    _latch_alert()
    adapter = _make_adapter(_ACCOUNT_WITH_USDJPY)
    engine = _StubEngine(adapter)  # daemon tracks nothing
    daemon = _make_daemon(engine, tmp_path, monkeypatch)

    daemon._reconcile_positions()

    assert "untracked_position" in fill_ledger.active_alerts(), \
        "position still open and untracked: the alert must stay latched"


# ---------------------------------------------------------------------------
# (c) Successful read, account genuinely flat -> clears
# ---------------------------------------------------------------------------

def test_successful_flat_read_clears_untracked_alert(tmp_path, monkeypatch):
    _latch_alert()
    adapter = _make_adapter(_ACCOUNT_FLAT)
    engine = _StubEngine(adapter)
    daemon = _make_daemon(engine, tmp_path, monkeypatch)

    daemon._reconcile_positions()

    assert "untracked_position" not in fill_ledger.active_alerts(), \
        "a successful read of a flat account is a genuine resolution"


# ---------------------------------------------------------------------------
# (d) Successful read, position open but tracked (attributed) -> clears
# ---------------------------------------------------------------------------

def test_successful_read_with_tracked_position_clears_alert(tmp_path, monkeypatch):
    _latch_alert()
    adapter = _make_adapter(_ACCOUNT_WITH_USDJPY)
    engine = _StubEngine(adapter)
    engine.positions[_KEY] = _StubPos("USDJPY")  # daemon tracks it
    engine.position_opened_at[_KEY] = int(time.time() * 1000) - 60_000
    daemon = _make_daemon(engine, tmp_path, monkeypatch)

    daemon._reconcile_positions()

    assert "untracked_position" not in fill_ledger.active_alerts(), \
        "position open but tracked by the daemon: the alert resolves"


# ---------------------------------------------------------------------------
# Adapter contract pins: None (unknown) vs [] (genuinely flat)
# ---------------------------------------------------------------------------

def test_get_positions_or_none_returns_none_on_failed_read():
    adapter = _make_adapter(None)
    assert adapter.get_positions_or_none() is None


def test_get_positions_or_none_returns_none_on_error_payload():
    adapter = _make_adapter({"errorMessage": "boom"})
    assert adapter.get_positions_or_none() is None


def test_get_positions_or_none_returns_none_without_credentials(monkeypatch):
    from exchanges.oanda_adapter import OandaExchangeAdapter

    monkeypatch.delenv("OANDA_API_KEY", raising=False)
    monkeypatch.delenv("OANDA_ACCOUNT_ID", raising=False)
    adapter = OandaExchangeAdapter(api_key="", account_id="", practice=True)
    assert adapter.get_positions_or_none() is None


def test_get_positions_or_none_returns_empty_list_on_flat_account():
    adapter = _make_adapter(_ACCOUNT_FLAT)
    assert adapter.get_positions_or_none() == []


def test_get_positions_or_none_parses_open_position():
    adapter = _make_adapter(_ACCOUNT_WITH_USDJPY)
    positions = adapter.get_positions_or_none()
    assert positions is not None and len(positions) == 1
    pos = positions[0]
    assert pos.symbol == "USDJPY"
    assert pos.side == "LONG"
    assert pos.quantity == pytest.approx(15.0)
    assert pos.entry_price == pytest.approx(159.691)


def test_get_positions_legacy_contract_unchanged():
    """get_positions() keeps returning [] on failure for its existing
    callers — only the new or_none variant distinguishes unknown."""
    assert _make_adapter(None).get_positions() == []
    assert _make_adapter(_ACCOUNT_FLAT).get_positions() == []
    positions = _make_adapter(_ACCOUNT_WITH_USDJPY).get_positions()
    assert len(positions) == 1 and positions[0].symbol == "USDJPY"
