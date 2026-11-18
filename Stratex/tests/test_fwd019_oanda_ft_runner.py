"""TASK-STR-FWD-019 (PR 1) — the OANDA FORWARD_TEST runner.

The registry's forex FORWARD_TEST entries (status FORWARD_TEST,
forward_protocol True, forward_venues ["oanda_practice"], non-empty
lane_assets) had no engine: oanda_demo.trader admits ONLY VALIDATED
entries and sleeve_runner admits ONLY the VALIDATED sleeve leg. This
file pins the new engine (oanda_demo/forward_test_runner.py):

1. GOVERNANCE ADMISSION TABLE: only the full FORWARD_TEST forex
   shape is admitted — VALIDATED entries, FORWARD_TEST entries
   without forward_protocol / without the oanda_practice venue /
   with empty lane_assets are all refused, fail closed.
2. PRACTICE ATTESTATION: a non-practice adapter halts the scan
   before any order; NO live OANDA calls happen anywhere in this
   file (the adapter is a fake; the account/transport is mocked).
3. SIGNAL -> ORDER: a stub governed module's signal on a synthetic
   candle frame maps to a market order whose SL/TP are the judged
   bracket distances anchored to the pricing mid, and the fill is
   recorded in the runner's trade log tagged FORWARD_TEST.
4. KILL CRITERIA: expectancy < 0 / PF < 1.0 after >= 50 closed
   trades, and MTM drawdown > 5% of equity, evaluated on fabricated
   fill histories (via measurement/forward_guard.py when importable,
   else the runner's identical local evaluator).
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from oanda_demo import forward_test_runner as ftr


# ---------------------------------------------------------------------------
# Fakes (no live OANDA calls anywhere in this file)
# ---------------------------------------------------------------------------

PRACTICE_URL = "https://api-fxpractice.oanda.com/v3"
LIVE_URL = "https://api-fxtrade.oanda.com/v3"


def _entry(**over):
    base = {
        "status": "FORWARD_TEST",
        "forward_protocol": True,
        "forward_venues": ["oanda_practice"],
        "lane_assets": ["EURUSD"],
        "timeframe": "1d",
        "forward_lane": "FORWARD_TEST",
    }
    base.update(over)
    return base


class FakeAdapter:
    """Mocked OANDA transport: canned account / pricing / candles."""

    def __init__(self, practice=True, base_url=PRACTICE_URL, candles=None):
        self.practice = practice
        self.base_url = base_url
        self.account_id = "101-001-00000000-001"
        self.orders = []
        self._candles = candles or []
        self._open = []

    def get_account_summary(self):
        return {
            "balance": 10_000.0, "equity": 10_000.0,
            "margin_available": 9_000.0, "margin_rate": 0.02,
        }

    def open_trades(self):
        return list(self._open)

    def get_pricing(self, symbols):
        return {s: {"mid": 1.1000, "spread": 0.0001} for s in symbols}

    def normalize_symbol(self, symbol):
        return symbol

    def denormalize_symbol(self, symbol):
        return symbol[:3] + "_" + symbol[3:]

    def _request(self, method, endpoint, params=None):
        if "candles" in endpoint:
            return {"candles": self._candles}
        return {}

    def place_order(self, symbol, side, order_type, units,
                    stop_loss=None, take_profit=None):
        self.orders.append({
            "symbol": symbol, "side": side, "type": order_type,
            "units": units, "stop_loss": stop_loss,
            "take_profit": take_profit,
        })
        return SimpleNamespace(
            trade_id="T-1", order_id="O-1", price=1.1000, status="FILLED"
        )


def _candles(n=300, close=1.1000):
    out = []
    base_ts = 1_700_000_000
    for i in range(n):
        ts = base_ts + i * 86400
        from datetime import datetime, timezone
        iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000000000Z"
        )
        out.append({
            "complete": True, "time": iso, "volume": 100,
            "mid": {"o": str(close), "h": str(close + 0.001),
                    "l": str(close - 0.001), "c": str(close)},
        })
    return out


def _stub_module(signal):
    return SimpleNamespace(get_signal=lambda df: signal)


def _runner(tmp_path, adapter, registry, module):
    return ftr.ForwardTestRunner(
        adapter=adapter, data_dir=tmp_path, registry=registry,
        module_loader=lambda key: module,
    )


# ---------------------------------------------------------------------------
# 1. Governance admission table
# ---------------------------------------------------------------------------

def test_admission_table():
    registry = {
        "good_forex": _entry(),
        "validated_fx": _entry(status="VALIDATED"),
        "no_protocol": _entry(forward_protocol=False),
        "no_venues": {k: v for k, v in _entry().items()
                      if k != "forward_venues"},
        "wrong_venue": _entry(forward_venues=["binance_futures"]),
        "empty_lane": _entry(lane_assets=[]),
        "no_lane": {k: v for k, v in _entry().items() if k != "lane_assets"},
        "disabled": _entry(status="DISABLED"),
    }
    admitted = ftr.admitted_entries(registry)
    assert sorted(admitted) == ["good_forex"]


def test_real_registry_admits_nothing_yet():
    # On the base registry the OANDA engines' own entrants must NOT be
    # admitted here: fx_mr_v4 is VALIDATED (trader's), the sleeve legs
    # are VALIDATED (sleeve_runner's), and the crypto FORWARD_TEST
    # lane entries carry no forward_venues.
    admitted = ftr.admitted_entries()
    assert "fx_mr_v4" not in admitted
    assert "sleeve_tsmom2_dual" not in admitted
    assert "bollinger_trend" not in admitted


# ---------------------------------------------------------------------------
# 2. Practice attestation (fail closed, no orders)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("practice,url", [
    (False, LIVE_URL), (True, LIVE_URL), (False, PRACTICE_URL),
])
def test_non_practice_attestation_refused(tmp_path, practice, url):
    adapter = FakeAdapter(practice=practice, base_url=url,
                          candles=_candles())
    assert ftr.practice_attested(adapter) is False
    runner = _runner(tmp_path, adapter, {"stubft": _entry()},
                     _stub_module({"side": "BUY", "sl_dist": 0.002,
                                   "tp_dist": 0.004}))
    out = runner.run_once()
    assert "attestation" in out.get("halted", "")
    assert adapter.orders == []


def test_practice_attestation_accepts_practice_adapter():
    assert ftr.practice_attested(FakeAdapter()) is True


def test_no_admitted_entries_halts_closed(tmp_path):
    adapter = FakeAdapter(candles=_candles())
    runner = _runner(tmp_path, adapter, {"v": _entry(status="VALIDATED")},
                     _stub_module({"side": "BUY", "sl_dist": 0.002,
                                   "tp_dist": 0.004}))
    out = runner.run_once()
    assert "governance" in out.get("halted", "")
    assert adapter.orders == []


# ---------------------------------------------------------------------------
# 3. Signal -> order mapping + bracket anchoring + lane-tagged log
# ---------------------------------------------------------------------------

def test_bracket_prices_arithmetic():
    assert ftr.bracket_prices("BUY", 1.1000, 0.0020, 0.0040) == (
        pytest.approx(1.0980), pytest.approx(1.1040))
    assert ftr.bracket_prices("SELL", 1.1000, 0.0020, 0.0040) == (
        pytest.approx(1.1020), pytest.approx(1.0960))


def test_signal_to_order_on_synthetic_frame(tmp_path):
    adapter = FakeAdapter(candles=_candles())
    runner = _runner(
        tmp_path, adapter, {"stubft": _entry()},
        _stub_module({"side": "BUY", "sl_dist": 0.0020, "tp_dist": 0.0040,
                      "win_rate_prior": 0.5, "rr_ratio": 2.0,
                      "strategy_type": "RULE_BASED"}),
    )
    out = runner.run_once()
    assert len(adapter.orders) == 1
    order = adapter.orders[0]
    assert order["symbol"] == "EURUSD"
    assert order["side"] == "BUY"
    assert order["type"] == "MARKET"
    assert order["units"] >= 1
    # Bracket anchored to the pricing mid (1.1000): SL -0.0020, TP +0.0040.
    assert order["stop_loss"] == pytest.approx(1.0980)
    assert order["take_profit"] == pytest.approx(1.1040)
    # Sizing: the lane term is 0.1% of 10,000 NAV = $10 risk over a
    # 0.0020 stop on EURUSD (quote USD) = 5000 units, but the 25%
    # notional cap binds first (sleeve_runner arithmetic):
    # 0.25 * 10,000 / 1.1000 = 2272 units.
    assert order["units"] == 2272
    assert out["own_open_trades"] == 1
    # The fill is recorded in the runner's trade log, lane-tagged.
    log_text = (tmp_path / "forward_test_trades.csv").read_text()
    assert "FORWARD_TEST" in log_text
    assert "stubft" in log_text
    assert "OPEN" in log_text


def test_no_signal_no_order(tmp_path):
    adapter = FakeAdapter(candles=_candles())
    runner = _runner(tmp_path, adapter, {"stubft": _entry()},
                     _stub_module({"side": None}))
    out = runner.run_once()
    assert adapter.orders == []
    assert out["actions"] == []


def test_extract_signal_absolute_levels():
    # gov2-style absolute sl/tp are converted to distances from close.
    sig = ftr.extract_signal({"side": "BUY", "sl": 1.098, "tp": 1.104}, 1.100)
    assert sig["sl_dist"] == pytest.approx(0.002)
    assert sig["tp_dist"] == pytest.approx(0.004)
    sig = ftr.extract_signal(
        SimpleNamespace(side="SELL", sl=1.102, tp=1.096), 1.100)
    assert sig["sl_dist"] == pytest.approx(0.002)
    assert ftr.extract_signal({"side": None}, 1.100) is None
    assert ftr.extract_signal({"side": "BUY", "sl_dist": -1, "tp_dist": 1},
                              1.100) is None


def test_unsupported_timeframe_is_skipped(tmp_path):
    adapter = FakeAdapter(candles=_candles())
    runner = _runner(tmp_path, adapter,
                     {"stubft": _entry(timeframe="1h")},
                     _stub_module({"side": "BUY", "sl_dist": 0.002,
                                   "tp_dist": 0.004}))
    out = runner.run_once()
    assert adapter.orders == []
    assert out["unsupported_timeframe"] == ["stubft:1h"]


# ---------------------------------------------------------------------------
# 4. Kill criteria on fabricated fill histories
# ---------------------------------------------------------------------------

def _fills(pnls, tag="strategy_stubft"):
    return [
        {"strategy": tag, "net_pnl": p, "exit_time": 1_700_000_000 + 3600 * i}
        for i, p in enumerate(pnls)
    ]


def test_kill_expectancy_and_pf_after_50():
    decision = ftr.evaluate_kill(_fills([-1.0] * 55), 10_000.0, "strategy_stubft")
    assert decision["trades"] == 55
    assert decision["breached"] is True
    assert any("expectancy" in r for r in decision["reasons"])


def test_kill_not_armed_before_50():
    decision = ftr.evaluate_kill(_fills([-1.0] * 49), 10_000.0, "strategy_stubft")
    assert decision["breached"] is False


def test_kill_healthy_history_does_not_breach():
    decision = ftr.evaluate_kill(
        _fills([2.0, -1.0] * 30), 10_000.0, "strategy_stubft")
    assert decision["breached"] is False


def test_kill_mtm_drawdown_over_5pct():
    # +$10 x10 then a single -$600 close: peak-to-trough $600 > 5% of
    # $10,000 equity, with too few trades for the expectancy/PF leg.
    decision = ftr.evaluate_kill(
        _fills([10.0] * 10 + [-600.0]), 10_000.0, "strategy_stubft")
    assert decision["breached"] is True
    assert any("drawdown" in r for r in decision["reasons"])


def test_kill_unrealized_counts_toward_mtm_drawdown():
    decision = ftr.evaluate_kill(
        _fills([10.0] * 10), 10_000.0, "strategy_stubft",
        unrealized=-600.0)
    assert decision["breached"] is True


def test_local_evaluator_matches_criteria():
    # The local fallback implements the identical criteria (used only
    # when measurement/forward_guard.py cannot be imported).
    d = ftr._local_kill_decision(_fills([-2.0] * 60), 10_000.0, "strategy_stubft")
    assert d["breached"] is True
    d = ftr._local_kill_decision(_fills([1.0] * 60), 10_000.0, "strategy_stubft")
    assert d["breached"] is False
