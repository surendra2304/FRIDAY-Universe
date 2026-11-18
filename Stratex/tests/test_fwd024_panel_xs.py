"""TASK-STR-FWD-024 — panel-signal machinery for the cross-sectional
streams xs_momentum / xs_lowvol.

The two RD-002 near-miss rows rank a PANEL (CRYPTO30) cross-
sectionally, which the daemon's per-symbol get_signal(df) contract
cannot express — wave 2 excluded them for exactly that reason.
panel_signal_service.py is the machinery: the daemon's ranking hook
evaluates the judged ranking on the judged cadence and persists a
per-symbol membership; the entrant modules only look their own
symbol up. This file pins:

1. EQUIVALENCE: the service's entry ports reproduce the judged
   rd2 harness (families2.xs_entries / families3.xs_lowvol_fn)
   entry-for-entry on the RD-002 cache panel, and the judged
   bracket + recorded costs reproduce the RD-002 pooled OOS
   metrics exactly. (Skipped where the cache is absent.)
2. OFFSET/CAUSALITY: a windowed panel reproduces the full-history
   entries at shared rebalance bars, and a membership computed on
   truncated frames names exactly the picks of the last closed
   rebalance bar — nothing later.
3. FAIL-CLOSED: missing reference series, a panel too small to
   rank 2k, an off-anchor start, and persistence refusals (failure
   records, stale panels, rebalance regressions).
4. MODULE BEHAVIOUR: an entrant fires the judged bracket only for
   its own symbol, only on the membership's signal bar.
5. GOVERNANCE: the two FORWARD_TEST registry entries carry the
   lane terms, the measured FWD-012 stop-cap overrides, and the
   panel_xs execution mode; the registry passes evaluation context
   only to modules that declare it.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import panel_signal_service as pss
import strategy_xs_lowvol as lowvol_mod
import strategy_xs_momentum as mom_mod

WARMUP = 260
CACHE = "/home/hatch/workspace/str-rd2/cache2"
ANCHOR = pd.Timestamp("2022-01-01T00:00:00Z")

RECORDED = {
    "xs_momentum__crypto30__1d": {
        "trades": 258,
        "expectancy_net": 0.008649310636976184,
        "profit_factor_net": 1.1346758585082095,
        "win_rate": 0.5193798449612403,
        "spec": {"type": "bracket_time", "sl_atr": 3.0, "tp_atr": 6.0,
                 "max_bars": 20},
        "override": 0.90,
    },
    "xs_lowvol__crypto30__1d": {
        "trades": 510,
        "expectancy_net": 0.007156229510753745,
        "profit_factor_net": 1.178977800025495,
        "win_rate": 0.5392156862745098,
        "spec": {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 4.0,
                 "max_bars": 10},
        "override": 0.60,
    },
}


# ---------------------------------------------------------------------------
# Synthetic panel helpers
# ---------------------------------------------------------------------------

def _synthetic_panel(n_symbols=8, n_bars=400, start=ANCHOR):
    """Deterministic daily panel from the judged anchor: symbol i
    trends at a distinct daily rate, so both rankings are stable
    and reproducible."""
    idx = pd.date_range(start, periods=n_bars, freq="1d", tz="UTC")
    frames = {}
    symbols = list(pss.PANEL_SYMBOLS[:n_symbols])
    for i, sym in enumerate(symbols):
        drift = 0.004 * (i - n_symbols / 2)
        wave = 0.01 * (1 + i % 3) * np.sin(np.arange(n_bars) / (7.0 + i))
        close = 100.0 * np.exp(np.cumsum(np.full(n_bars, drift) + wave * 0.01))
        frames[sym] = pd.DataFrame(
            {
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.full(n_bars, 1000.0),
            },
            index=idx,
        )
    return frames


@pytest.fixture(autouse=True)
def _reset_module_caches():
    mom_mod._membership_cache.update({"state": None, "mtime": None})
    lowvol_mod._membership_cache.update({"state": None, "mtime": None})
    yield
    mom_mod._membership_cache.update({"state": None, "mtime": None})
    lowvol_mod._membership_cache.update({"state": None, "mtime": None})


# ---------------------------------------------------------------------------
# 1. Equivalence on the RD-002 cache panel
# ---------------------------------------------------------------------------

_cache_panel = {}


def _load_cache_panel():
    if "datasets" not in _cache_panel:
        from rigorous_backtest.rd2 import panels

        datasets = panels.load_panel("crypto30", "1d")
        _cache_panel["datasets"] = datasets
        _cache_panel["dfs"] = {s: ds.df for s, ds in datasets.items()}
    return _cache_panel["datasets"], _cache_panel["dfs"]


@pytest.mark.skipif(not os.path.isdir(CACHE),
                    reason="RD-002 cache panel not present on this host")
class TestCacheEquivalence:
    def test_momentum_entries_equal_harness(self):
        from rigorous_backtest.rd2 import families2

        _, dfs = _load_cache_panel()
        judged = families2.xs_entries(dfs, 60, 20, 3, WARMUP)
        mine = pss.xs_momentum_entries(dfs, 60, 20, 3, WARMUP)
        assert mine == judged
        assert sum(len(v) for v in mine.values()) == 456

    def test_lowvol_entries_equal_harness(self):
        from rigorous_backtest.rd2 import families3

        _, dfs = _load_cache_panel()
        judged = families3.xs_lowvol_fn()(dfs, WARMUP)
        mine = pss.xs_lowvol_entries(dfs, WARMUP)
        assert mine == judged
        assert sum(len(v) for v in mine.values()) == 906

    @pytest.mark.parametrize(
        "stream_id,entries_fn",
        [
            ("xs_momentum__crypto30__1d",
             lambda dfs: pss.xs_momentum_entries(dfs, 60, 20, 3, WARMUP)),
            ("xs_lowvol__crypto30__1d",
             lambda dfs: pss.xs_lowvol_entries(dfs, WARMUP)),
        ],
    )
    def test_pooled_metrics_reproduce_the_record(self, stream_id, entries_fn):
        from rigorous_backtest.rd.common import atr as harness_atr
        from rigorous_backtest.rd.fastsim import simulate_entries
        from rigorous_backtest.rd2.costs2 import costs_for
        from rigorous_backtest.simulator import trade_metrics
        from rigorous_backtest.walkforward import FOLDS, trades_in_window

        datasets, dfs = _load_cache_panel()
        rec = RECORDED[stream_id]
        entries = entries_fn(dfs)
        trades = []
        for sym, ds in datasets.items():
            a = harness_atr(ds.df, 14).to_numpy(dtype=float)
            trades.extend(simulate_entries(
                ds.df, entries.get(sym, []), a, rec["spec"], sym,
                costs_for("crypto30", sym)))
        pooled = []
        for _fid, s, e in FOLDS:
            pooled.extend(trades_in_window(trades, s, e))
        m = trade_metrics(pooled)
        assert m["trades"] == rec["trades"]
        assert m["expectancy_net"] == pytest.approx(
            rec["expectancy_net"], abs=1e-12)
        assert m["profit_factor_net"] == pytest.approx(
            rec["profit_factor_net"], abs=1e-9)
        assert m["win_rate"] == pytest.approx(rec["win_rate"], abs=1e-12)

    @pytest.mark.parametrize(
        "stream_id,entries_fn",
        [
            ("xs_momentum__crypto30__1d",
             lambda dfs: pss.xs_momentum_entries(dfs, 60, 20, 3, WARMUP)),
            ("xs_lowvol__crypto30__1d",
             lambda dfs: pss.xs_lowvol_entries(dfs, WARMUP)),
        ],
    )
    def test_stop_cap_override_covers_measured_max(self, stream_id, entries_fn):
        """FWD-012: the registry override must exceed the stop
        distribution measured at the judged entry bars."""
        from rigorous_backtest.rd.common import atr as harness_atr

        datasets, dfs = _load_cache_panel()
        rec = RECORDED[stream_id]
        entries = entries_fn(dfs)
        sl_atr = rec["spec"]["sl_atr"]
        stops = []
        for sym, ds in datasets.items():
            a = harness_atr(ds.df, 14).to_numpy(dtype=float)
            cl = ds.df["close"].to_numpy(dtype=float)
            for pos, _side in entries.get(sym, []):
                stops.append(sl_atr * a[pos] / cl[pos])
        stops = np.array(stops)
        # The override is load-bearing (a real share exceeds the
        # 0.15 global cap) and sufficient (nothing exceeds it).
        assert (stops > 0.15).mean() > 0.30
        assert stops.max() < rec["override"]


# ---------------------------------------------------------------------------
# 2. Offset consistency + causality
# ---------------------------------------------------------------------------

class TestOffsetAndCausality:
    def test_windowed_panel_reproduces_full_history_entries(self):
        frames = _synthetic_panel(n_symbols=10, n_bars=1400)
        offset = 1000
        window = {s: df.iloc[offset:] for s, df in frames.items()}

        def grid(ts):
            return int((ts - ANCHOR) / pd.Timedelta(days=1))

        for stream_id, fn in (
            ("xs_momentum__crypto30__1d",
             lambda d, off: pss.xs_momentum_entries(d, 60, 20, 3, WARMUP, offset=off)),
            ("xs_lowvol__crypto30__1d",
             lambda d, off: pss.xs_lowvol_entries(d, WARMUP, offset=off)),
        ):
            full = fn(frames, 0)
            part = fn(window, offset)
            for sym in frames:
                # Compare only at grid bars >= 1100: below that the
                # windowed run's scores are not yet computable from
                # window-local history (the judged lookbacks reach
                # back past the window start) — the disclosed
                # live-history translation.
                expected = [
                    (pos - offset, side)
                    for pos, side in full[sym]
                    if grid(frames[sym].index[pos]) >= 1100
                ]
                actual = [
                    (pos, side)
                    for pos, side in part[sym]
                    if grid(window[sym].index[pos]) >= 1100
                ]
                assert actual == expected, (stream_id, sym)

    def test_membership_names_only_the_last_closed_rebalance(self):
        frames = _synthetic_panel(n_symbols=10, n_bars=400)
        # Truncate one bar after the momentum rebalance bar 380
        # (260 + 6*20; the judged loop bound j < n-1 needs the
        # entry bar to exist): the decision must name bar 380's
        # picks and nothing later.
        truncated = {s: df.iloc[:382] for s, df in frames.items()}
        decision = pss.run_membership("xs_momentum__crypto30__1d", truncated)
        assert decision["ok"] is True
        expected_bar = ANCHOR + pd.Timedelta(days=380)
        assert decision["rebalance_epoch"] == int(expected_bar.timestamp())
        full_entries = pss.xs_momentum_entries(frames, 60, 20, 3, WARMUP)
        expected = {}
        for sym, entries in full_entries.items():
            for pos, side in entries:
                if frames[sym].index[pos] == expected_bar:
                    expected[sym] = side
        assert {s: e["side"] for s, e in decision["entries"].items()} == expected
        for entry in decision["entries"].values():
            assert entry["signal_bar_epoch"] == int(expected_bar.timestamp())


# ---------------------------------------------------------------------------
# 3. Fail-closed behaviour
# ---------------------------------------------------------------------------

class TestFailClosed:
    def test_missing_reference_series(self):
        frames = _synthetic_panel()
        del frames[pss.PANEL_SYMBOLS[0]]
        decision = pss.run_membership("xs_momentum__crypto30__1d", frames)
        assert decision["ok"] is False
        assert "reference series" in decision["reason"]

    def test_panel_too_small_to_rank(self):
        frames = _synthetic_panel(n_symbols=4)
        decision = pss.run_membership("xs_lowvol__crypto30__1d", frames)
        assert decision["ok"] is False
        assert "no effective rebalance" in decision["reason"]

    def test_off_anchor_start(self):
        frames = _synthetic_panel(start=ANCHOR + pd.Timedelta(hours=12))
        decision = pss.run_membership("xs_momentum__crypto30__1d", frames)
        assert decision["ok"] is False
        assert "anchor grid" in decision["reason"]

    def test_save_membership_refusals(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PANEL_SIGNAL_STATE_DIR", str(tmp_path))
        frames = _synthetic_panel(n_symbols=10, n_bars=400)
        decision = pss.run_membership("xs_momentum__crypto30__1d", frames)
        assert decision["ok"] is True
        # A failure record is never persisted.
        assert pss.save_membership(
            {"ok": False, "stream": decision["stream"],
             "reason": "x"}) is False
        assert pss.load_membership(decision["stream"]) is None
        # The fresh decision persists.
        assert pss.save_membership(decision) is True
        # A stale panel (older as-of) is refused.
        stale = dict(decision)
        stale["panel_asof_epoch"] = decision["panel_asof_epoch"] - 86400
        stale["panel_asof"] = "earlier"
        assert pss.save_membership(stale) is False
        # A rebalance regression at the same as-of is refused.
        regressed = dict(decision)
        regressed["rebalance_epoch"] = decision["rebalance_epoch"] - 20 * 86400
        assert pss.save_membership(regressed) is False
        # The stored state is still the original decision.
        stored = pss.load_membership(decision["stream"])
        assert stored["rebalance_epoch"] == decision["rebalance_epoch"]


# ---------------------------------------------------------------------------
# 4. Entrant module behaviour
# ---------------------------------------------------------------------------

class TestEntrantModules:
    def _arm(self, tmp_path, monkeypatch, module, stream_id):
        monkeypatch.setenv("PANEL_SIGNAL_STATE_DIR", str(tmp_path))
        frames = _synthetic_panel(n_symbols=10, n_bars=400)
        decision = pss.run_membership(stream_id, frames)
        assert decision["ok"] is True and decision["entries"]
        assert pss.save_membership(decision) is True
        return frames, decision

    @pytest.mark.parametrize(
        "module,stream_id,sl_atr,tp_atr",
        [
            (mom_mod, "xs_momentum__crypto30__1d", 3.0, 6.0),
            (lowvol_mod, "xs_lowvol__crypto30__1d", 2.0, 4.0),
        ],
    )
    def test_fires_judged_bracket_on_signal_bar(
            self, tmp_path, monkeypatch, module, stream_id, sl_atr, tp_atr):
        frames, decision = self._arm(
            tmp_path, monkeypatch, module, stream_id)
        sym, entry = next(iter(decision["entries"].items()))
        # The frame as the daemon sees it during the signal bar's
        # own day: its last closed bar IS the membership's bar.
        df = frames[sym].loc[:pd.Timestamp(entry["signal_bar"])]
        signal = module.get_signal(df, symbol=sym, timeframe="1d",
                                   venue="binance_demo")
        assert signal["side"] == (
            "BUY" if entry["side"] == "LONG" else "SELL")
        atr = float(pss.atr14(df).iloc[-1])
        assert signal["sl_dist"] == pytest.approx(sl_atr * atr)
        assert signal["tp_dist"] == pytest.approx(tp_atr * atr)
        assert signal["rr_ratio"] == pytest.approx(2.0)

    @pytest.mark.parametrize(
        "module,stream_id",
        [(mom_mod, "xs_momentum__crypto30__1d"),
         (lowvol_mod, "xs_lowvol__crypto30__1d")],
    )
    def test_silent_off_signal_bar_and_without_context(
            self, tmp_path, monkeypatch, module, stream_id):
        frames, decision = self._arm(
            tmp_path, monkeypatch, module, stream_id)
        sym, entry = next(iter(decision["entries"].items()))
        df = frames[sym].loc[:pd.Timestamp(entry["signal_bar"])]
        # One bar later: the entry's bar is no longer the last bar.
        pos = frames[sym].index.get_loc(pd.Timestamp(entry["signal_bar"]))
        later = frames[sym].iloc[:pos + 2]
        assert module.get_signal(later, symbol=sym)["side"] is None
        # A symbol outside the membership stays silent.
        outsider = next(s for s in frames if s not in decision["entries"])
        assert module.get_signal(frames[outsider],
                                 symbol=outsider)["side"] is None
        # The classic context-free call can never fire.
        assert module.get_signal(df)["side"] is None
        # A wrong timeframe stays silent.
        assert module.get_signal(df, symbol=sym,
                                 timeframe="4h")["side"] is None

    def test_silent_without_any_membership(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PANEL_SIGNAL_STATE_DIR", str(tmp_path))
        frames = _synthetic_panel(n_symbols=10, n_bars=400)
        sym = pss.PANEL_SYMBOLS[1]
        assert mom_mod.get_signal(frames[sym], symbol=sym)["side"] is None
        assert lowvol_mod.get_signal(frames[sym], symbol=sym)["side"] is None


# ---------------------------------------------------------------------------
# 5. Governance pins
# ---------------------------------------------------------------------------

class TestGovernance:
    def test_panel_universe_matches_config(self):
        import config_strategy as cs

        assert pss.PANEL_SYMBOLS == tuple(cs.CRYPTO30_SYMBOLS)
        assert pss.PANEL_SYMBOLS[0] == "BTCUSDT"
        assert len(pss.PANEL_SYMBOLS) == 30

    @pytest.mark.parametrize(
        "key,stream_id,max_bars,max_stop,prior,edge",
        [
            ("xs_momentum", "xs_momentum__crypto30__1d", 20, 0.90,
             0.5194, 86.5),
            ("xs_lowvol", "xs_lowvol__crypto30__1d", 10, 0.60,
             0.5392, 71.6),
        ],
    )
    def test_registry_entries(self, key, stream_id, max_bars, max_stop,
                              prior, edge):
        import config_strategy as cs

        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "FORWARD_TEST"
        assert entry["forward_protocol"] is True
        assert entry["forward_lane"] == "FORWARD_TEST"
        assert entry["execution_mode"] == "panel_xs"
        assert entry["panel_xs"] == {"stream": stream_id}
        assert stream_id in pss.STREAMS
        assert entry["timeframe"] == "1d"
        assert entry["max_bars"] == max_bars
        assert entry["max_stop_pct"] == max_stop
        assert entry["risk_per_trade_pct"] == 0.001
        assert entry["max_heat_pct"] == 0.02
        assert entry["oos_win_rate_prior"] == prior
        assert entry["expected_net_edge_bps"] == edge
        assert entry["total_friction_bps"] == 16.0
        assert entry["lane_assets"] == cs.CRYPTO30_SYMBOLS
        assert entry["validated_assets"] == []
        assert entry["runtime_priors_nulled"] is False

    def test_registry_passes_context_only_when_declared(self):
        from strategies.strategy_registry import UnifiedStrategyRegistry

        registry = UnifiedStrategyRegistry()
        calls = {}

        def context_fn(df, symbol=None, timeframe=None, venue=None):
            calls["context"] = (symbol, timeframe, venue)
            return {"side": None}

        def classic_fn(df):
            calls["classic"] = True
            return {"side": None}

        registry._get_signal_fns["ctx_mod"] = context_fn
        registry._accepts_context["ctx_mod"] = True
        registry._get_signal_fns["classic_mod"] = classic_fn
        registry._accepts_context["classic_mod"] = False
        registry.executable = lambda *a, **k: (True, "")
        registry.get = lambda name: SimpleNamespace(status="VALIDATED")

        df = pd.DataFrame({"close": [1.0]})
        registry.execute_strategy("ctx_mod", df, timeframe="1d",
                                  symbol="BTCUSDT", venue="binance_demo")
        assert calls["context"] == ("BTCUSDT", "1d", "binance_demo")
        registry.execute_strategy("classic_mod", df, timeframe="1d",
                                  symbol="BTCUSDT", venue="binance_demo")
        assert calls["classic"] is True
