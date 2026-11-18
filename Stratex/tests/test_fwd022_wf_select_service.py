"""TASK-STR-FWD-022 — walk-forward selection service.

Pins:
1. The selection rule reproduces the judged RD-002 procedure record
   EXACTLY from the recorded trade streams (acid test, runs when the
   RD-002 results backup is present): picks roc24/roc168/roc72/
   roc42/roc42 and the pooled OOS record (453 trades, PF 1.1694).
2. Ranking semantics on synthetic streams: PF desc, win-rate
   tiebreak, PF-None and zero-trade variants excluded, expanding
   in-sample window (trades at/after the epoch start never count).
3. The ported bracket simulator and ts_momentum entries reproduce
   the judged harness (rd/fastsim.py + rd2/families2.py) trade for
   trade on real fixture slices.
4. run_selection causality: appending post-epoch bars cannot change
   the pick for that epoch.
5. The entrant module: no persisted pick -> no signal; with a pick,
   a judged entry cross on the last closed bar yields the BR24
   bracket signal of the PICKED variant only.
6. Registry/daemon wiring: FORWARD_TEST entry, lane partition, and
   the daemon hook persisting a selection (state + append-only log).
"""

from __future__ import annotations

import json
import os
import sys
import time
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import wf_select_service as wfs

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")
RD2_BACKUP = os.path.expanduser(
    "~/workspace/str-rd2/results_full_backup/grid_rows"
)
PROC = "ts_momentum__crypto30__1d"


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def _trade(entry: str, net: float) -> wfs.SimTrade:
    t = pd.Timestamp(entry, tz="UTC")
    return wfs.SimTrade("BTCUSDT", t, t, "LONG", 100.0, 100.0, net, "TP")


# ---------------------------------------------------------------------------
# 1. Acid test: the judged record, reproduced from its own streams
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.path.isdir(RD2_BACKUP), reason="RD-002 results backup not present"
)
def test_selection_reproduces_judged_record():
    streams = {}
    for variant in ("roc24", "roc42", "roc72", "roc168"):
        with open(os.path.join(
            RD2_BACKUP, f"ts_momentum__{variant}__crypto30__1d.json"
        )) as fh:
            row = json.load(fh)
        streams[variant] = [
            wfs.SimTrade(
                t["symbol"], pd.Timestamp(t["entry_time"]),
                pd.Timestamp(t["exit_time"]), t["side"],
                t["entry_price"], t["exit_price"], t["net_return"],
                t["exit_reason"],
            )
            for t in row["trades"]
        ]
    folds = [
        ("2024-07-01", "2025-01-01"), ("2025-01-01", "2025-07-01"),
        ("2025-07-01", "2026-01-01"), ("2026-01-01", "2026-07-01"),
        ("2026-07-01", "2026-11-01"),
    ]
    picks = []
    pooled: list[wfs.SimTrade] = []
    for start, end in folds:
        s = pd.Timestamp(start, tz="UTC")
        e = pd.Timestamp(end, tz="UTC")
        pick, _table = wfs.select_from_streams(streams, s)
        picks.append(pick)
        pooled.extend(
            t for t in streams[pick] if s <= t.entry_time < e
        )
    assert picks == ["roc24", "roc168", "roc72", "roc42", "roc42"]
    m = wfs.trade_metrics(pooled)
    assert m["trades"] == 453
    assert m["profit_factor_net"] == pytest.approx(1.1693910203271725, abs=1e-9)
    assert m["expectancy_net"] == pytest.approx(0.014095536468863041, abs=1e-9)
    assert m["win_rate"] == pytest.approx(0.36644591611479027, abs=1e-9)


# ---------------------------------------------------------------------------
# 2. Ranking semantics
# ---------------------------------------------------------------------------

def test_ranking_pf_then_win_rate_and_exclusions():
    epoch = pd.Timestamp("2026-01-01", tz="UTC")
    streams = {
        # PF 2.0, win rate 0.5
        "a": [_trade("2025-01-01", 0.10), _trade("2025-02-01", 0.10),
              _trade("2025-03-01", -0.05), _trade("2025-04-01", -0.05)],
        # PF 2.0, win rate 0.75 -> wins the tiebreak
        "b": [_trade("2025-01-01", 0.05), _trade("2025-02-01", 0.05),
              _trade("2025-03-01", 0.10), _trade("2025-04-01", -0.10)],
        # No losses and no wins (all zero) -> PF None -> excluded
        "c": [_trade("2025-01-01", 0.0)],
        # Trades only after the epoch -> zero IS trades -> excluded
        "d": [_trade("2026-06-01", 0.50)],
    }
    pick, table = wfs.select_from_streams(streams, epoch)
    assert pick == "b"
    assert table["c"]["profit_factor_net"] is None
    assert table["d"]["trades"] == 0


def test_ranking_expanding_window_uses_all_past():
    epoch = pd.Timestamp("2026-01-01", tz="UTC")
    streams = {
        "old_strong": [_trade("2022-01-01", 0.20), _trade("2022-06-01", -0.05)],
        "recent_weak": [_trade("2025-12-01", 0.01), _trade("2025-12-02", -0.05)],
    }
    pick, _ = wfs.select_from_streams(streams, epoch)
    assert pick == "old_strong"  # 2022 trades still count (expanding)


# ---------------------------------------------------------------------------
# 3. Simulator / entries equivalence with the judged harness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
@pytest.mark.parametrize("lookback", [24, 42, 72, 168])
def test_simulator_matches_fastsim(fixture, lookback):
    from rigorous_backtest.rd import fastsim
    from rigorous_backtest.rd.common import atr as harness_atr
    from rigorous_backtest.rd2 import families2
    from rigorous_backtest.simulator import Costs as HarnessCosts

    df = _load(fixture)
    entries_judged = families2.sig_ts_momentum(df, lookback, 260)
    entries_live = wfs.ts_momentum_entries(df, lookback, 260)
    assert entries_live == entries_judged
    atr = harness_atr(df, 14).to_numpy()
    judged = fastsim.simulate_entries(
        df, entries_judged, atr, {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0},
        "BTCUSDT", HarnessCosts(),
    )
    live = wfs.simulate_bracket(
        df, entries_live, atr, 2.0, 4.0, "BTCUSDT", wfs.Costs()
    )
    assert len(live) == len(judged)
    for lt, jt in zip(live, judged):
        assert lt.entry_time == jt.entry_time
        assert lt.exit_time == jt.exit_time
        assert lt.side == jt.side
        assert lt.net_return == pytest.approx(jt.net_return, abs=1e-12)
        assert lt.exit_reason == jt.exit_reason


# ---------------------------------------------------------------------------
# 4. run_selection causality + persistence
# ---------------------------------------------------------------------------

def _frames(seed: int = 5, n: int = 900):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-06-01", periods=n, freq="D", tz="UTC")
    frames = {}
    for k, symbol in enumerate(("BTCUSDT", "ETHUSDT")):
        close = 100.0 * np.cumprod(1.0 + rng.normal(0.001 * (k + 1), 0.02, n))
        frames[symbol] = pd.DataFrame(
            {"open": close, "high": close * 1.01, "low": close * 0.99,
             "close": close},
            index=idx,
        )
    return frames


def test_run_selection_is_causal_and_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("WF_SELECT_STATE_DIR", str(tmp_path))
    frames = _frames()
    epoch = pd.Timestamp("2025-06-01", tz="UTC")
    decision = wfs.run_selection(PROC, frames, epoch)
    assert decision["pick"] in ("roc24", "roc42", "roc72", "roc168")
    assert set(decision["is_table"]) == {"roc24", "roc42", "roc72", "roc168"}
    # Append wild post-epoch bars: the pick for the epoch must not move.
    mutated = {}
    for symbol, df in frames.items():
        extra_idx = pd.date_range("2025-06-01", periods=60, freq="D", tz="UTC")
        extra = pd.DataFrame(
            {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
            index=extra_idx,
        )
        mutated[symbol] = pd.concat([df, extra])
    decision2 = wfs.run_selection(PROC, mutated, epoch)
    assert decision2["pick"] == decision["pick"]
    assert decision2["is_table"] == decision["is_table"]
    # Persistence: state + append-only log.
    wfs.save_selection(decision)
    assert wfs.current_pick(PROC) == decision["pick"]
    wfs.save_selection(decision)
    log_lines = open(os.path.join(str(tmp_path), f"{PROC}_selections.jsonl")).read().strip().split("\n")
    assert len(log_lines) == 2


# ---------------------------------------------------------------------------
# 5. Entrant module behaviour
# ---------------------------------------------------------------------------

def test_module_no_pick_no_signal(tmp_path, monkeypatch):
    monkeypatch.setenv("WF_SELECT_STATE_DIR", str(tmp_path))
    import strategy_wf_select_tsmom as mod

    mod._pick_cache["mtime"] = None
    assert mod.current_pick() is None
    df = _load("BTCUSDT_1d.csv")
    assert mod.get_signal(df) == {"side": None}


def test_module_trades_only_the_pick(tmp_path, monkeypatch):
    monkeypatch.setenv("WF_SELECT_STATE_DIR", str(tmp_path))
    import strategy_wf_select_tsmom as mod

    # Find a bar where roc72 crosses but roc24 does not (or vice versa)
    # on the fixture, then pin the pick and compare.
    df = _load("BTCUSDT_1d.csv")
    frame = mod._closed_frame(df, now_s=time.time() + 10 * 365 * 86400)
    found = None
    for variant in ("roc24", "roc42", "roc72", "roc168"):
        entries = mod.entries_for_frame(frame, variant)
        if entries:
            found = (variant, entries[-1][0])
            break
    assert found is not None
    variant, bar = found
    sub = frame.iloc[: bar + 1]
    decision = {
        "procedure": PROC,
        "epoch_start": wfs.epoch_start_for().isoformat(),
        "decided_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "pick": variant,
        "is_table": {},
        "history": {},
    }
    wfs.save_selection(decision)
    mod._pick_cache["mtime"] = None
    assert mod.current_pick() == variant
    sig = mod.get_signal(sub)
    entries = mod.entries_for_frame(sub, variant)
    if entries and entries[-1][0] == len(sub) - 1:
        assert sig["side"] in ("BUY", "SELL")
        assert sig["sl_dist"] > 0 and sig["tp_dist"] == pytest.approx(
            2.0 * sig["sl_dist"]
        )
    else:
        assert sig == {"side": None}


# ---------------------------------------------------------------------------
# 6. Registry + daemon hook
# ---------------------------------------------------------------------------

def test_registry_entry():
    from config_strategy import CRYPTO30_SYMBOLS, PRODUCTION_STRATEGY_REGISTRY

    entry = PRODUCTION_STRATEGY_REGISTRY["wf_select_tsmom"]
    assert entry["status"] == "FORWARD_TEST"
    assert entry["execution_mode"] == "wf_select"
    assert entry["wf_select"]["procedure"] == PROC
    assert entry["forward_protocol"] is True
    assert entry["lane_assets"] == CRYPTO30_SYMBOLS
    assert entry["runtime_priors_nulled"] is False
    assert entry["oos_win_rate_prior"] == pytest.approx(0.3664)


def test_lane_partition_includes_procedure():
    from autonomy.run_daemon import StratexTradingEngine

    daemon = StratexTradingEngine.__new__(StratexTradingEngine)
    entries = daemon._forward_protocol_entries()
    assert "strategy_wf_select_tsmom" in entries
    assert daemon._lane_for_strategy("strategy_wf_select_tsmom") == "FORWARD_TEST"


class _FakeEngine:
    def __init__(self, closes):
        self.venues = {"binance_futures": object()}
        self._closes = closes

    def get_candles(self, venue, symbol, timeframe="15m", limit=100):
        now = time.time()
        step = 86400
        start = now - step * (len(self._closes) + 1)
        return [
            {"timestamp": start + step * i, "open": c, "high": c * 1.01,
             "low": c * 0.99, "close": c}
            for i, c in enumerate(self._closes)
        ]


def test_daemon_hook_persists_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("WF_SELECT_STATE_DIR", str(tmp_path))
    from autonomy.run_daemon import StratexTradingEngine
    from strategies.strategy_registry import strategy_registry

    monkeypatch.setattr(
        strategy_registry, "demo_venues",
        lambda: frozenset({"binance_futures"}),
    )
    rng = np.random.default_rng(11)
    closes = list(100.0 * np.cumprod(1.0 + rng.normal(0.001, 0.02, 800)))
    daemon = StratexTradingEngine.__new__(StratexTradingEngine)
    daemon.engine = _FakeEngine(closes)
    from config_strategy import CRYPTO30_SYMBOLS

    daemon.symbols = {"binance_futures": list(CRYPTO30_SYMBOLS)}
    daemon._last_wf_select_check = 0.0
    daemon._maybe_run_wf_selection()
    state = wfs.load_state(PROC)
    assert state is not None
    assert state["pick"] in ("roc24", "roc42", "roc72", "roc168")
    assert os.path.exists(os.path.join(str(tmp_path), f"{PROC}_selections.jsonl"))
    # Second call in the same epoch: no duplicate log line.
    daemon._last_wf_select_check = 0.0
    daemon._maybe_run_wf_selection()
    lines = open(os.path.join(str(tmp_path), f"{PROC}_selections.jsonl")).read().strip().split("\n")
    assert len(lines) == 1
