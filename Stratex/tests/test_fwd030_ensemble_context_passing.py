"""TASK-STR-FWD-030 — ensemble engine context passing + gap modules.

Pins, in order:
  1. EQUIVALENCE: the three gap modules reproduce the judged rd2
     harnesses entry-for-entry on the fwd002 fixture slices —
     tsmom2_dual roc90_ema200 @ crypto30 1d (families2
     sig_dual_momentum), shock_breakout k1.0 @ crypto30 1w
     (families3 sig_shock, warmup 104, judged weekly buckets), and
     zscore_reversion w50_t2.5_filt @ forex28 1d (families2
     sig_zscore with the ADX(14) < 25 filter). Live signals reproduce
     the judged brackets.
  2. ENGINE CONTEXT PASSING: evaluate_book passes symbol/timeframe/
     venue to members whose get_signal accepts them (same detection
     as the registry); classic members are called exactly as before.
     The xs member resolves end-to-end through the persisted panel
     membership, and abstains without one (or without a symbol).
  3. REGISTRY/PARTITION: the three new keys are FORWARD_TEST with
     forward_protocol True, forward_lane "FORWARD_TEST", lane_assets
     exactly the judged universe, risk fields 0.001/0.02, judged
     edges intact (runtime_priors_nulled False). The win-rate prior
     is 0.4679 for SHW (pooled OOS, RD-011 stream report); DUAL 1d
     and ZSC carry NO published win rate — none is recorded (see the
     module docstrings and the registry reasons).
  4. STOP-CAP (FWD-012): per entry, either no max_stop_pct and the
     measured entry-bar stop% is <= 0.15, or max_stop_pct is present,
     > 0.15 and >= the measured panel maximum (capcheck_books.json).
     Fixture cross-checks are recomputed here.
  5. DISCOVERY: the registry discovers all three modules and they
     are demo-executable at their judged timeframe/symbol/venue.
  6. BOOKS: 3933 and 3978 evaluate through the daemon's own
     execute_strategy path (NO_SIGNAL on flat fixtures, never a
     refusal) — at 1d and, for 3978, at the venue label '1w'.

No test touches the network, the bridge, or a live venue. Everything
runs on synthetic frames, fake member modules, or shipped fixtures.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import strategy_shock_breakout_1wk as shw
import strategy_tsmom2_dual_crypto_1d as dual
import strategy_xs_lowvol as xsl_module
import strategy_zscore_reversion as zsc
from rigorous_backtest.rd.common import atr as harness_atr
from rigorous_backtest.rd2 import families2, families3
from strategies.ensemble_book import Book, BookState, Member, evaluate_book
from strategies.ensemble_books import BOOKS

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fwd002")

# key: (module, timeframe, lane universe constant name,
#       oos win rate prior (None = no win rate was published for this
#       cell — none is recorded), expected edge bps, measured panel
#       entry-bar max stop fraction (capcheck_books.json),
#       max_stop_pct or None)
KEYS = {
    "tsmom2_dual_crypto_1d": (dual, "1d", "CRYPTO30_SYMBOLS", None, 760.3,
                              0.4246, 0.60),
    "shock_breakout_1wk": (shw, "1w", "CRYPTO30_SYMBOLS", 0.4679, 904.3,
                           0.8716, 0.90),
    "zscore_reversion": (zsc, "1d", "FOREX28_SYMBOLS", None, 34.7,
                         0.0694, None),
}

BASE_VALIDATED = {
    "ichimoku_trend", "dow_effect", "fx_mr_v4",
    "sleeve_shock_breakout", "sleeve_tsmom2_dual",
}


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(FIXTURES, name), index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def _flat_frame(n=300, close=100.0, start="2024-01-01", freq="D"):
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )


def _entries_stop_max(df, entries, mult):
    a = harness_atr(df, 14)
    return max(mult * float(a.iloc[i]) / float(df["close"].iloc[i])
               for i, _ in entries)


# ---------------------------------------------------------------------------
# 1. Equivalence vs the judged harnesses
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["BTCUSDT_1d.csv", "SOLUSDT_1d.csv"])
def test_dual_1d_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families2.sig_dual_momentum(df, 90, 260)
    production = dual.entries_for_frame(df, 260)
    assert len(judged) >= 5, "fixture must contain a meaningful entry set"
    assert production == judged


@pytest.mark.parametrize("fixture", ["BTCUSDT_1wk.csv", "SUIUSDT_1wk.csv"])
def test_shock_1wk_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families3.sig_shock(df, 1.0, 104)
    production = shw.entries_for_frame(df, 104)
    assert len(judged) >= 4, "fixture must contain a meaningful entry set"
    assert production == judged


@pytest.mark.parametrize(
    "fixture", ["FX_EURUSD_1d.csv", "FX_GBPJPY_1d.csv", "FX_USDJPY_1d.csv"]
)
def test_zscore_entries_match_judged_harness(fixture):
    df = _load(fixture)
    judged = families2.sig_zscore(df, 50, 2.5, True, 260)
    production = zsc.entries_for_frame(df, 260)
    assert len(judged) >= 1, "fixture must contain a meaningful entry set"
    assert production == judged


def test_live_signals_reproduce_judged_brackets():
    # DUAL 1d: SL 2.5x / TP 5.0x ATR(14); no win-rate prior is recorded.
    df = _load("BTCUSDT_1d.csv")
    judged = families2.sig_dual_momentum(df, 90, 260)
    atr = harness_atr(df, 14).to_numpy()
    for i, side in judged[:3]:
        sig = dual.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.5 * atr[i])
        assert sig["tp_dist"] == pytest.approx(5.0 * atr[i])
        assert sig["rr_ratio"] == pytest.approx(2.0)
        assert "win_rate_prior" not in sig
    assert dual.WIN_RATE_PRIOR is None
    assert not hasattr(dual, "_OOS_WIN_RATE_PRIOR")
    # SHW 1w: SL 2.0x / TP 4.0x ATR(14); pooled OOS win rate 0.4679.
    df = _load("BTCUSDT_1wk.csv")
    judged = families3.sig_shock(df, 1.0, 104)
    atr = harness_atr(df, 14).to_numpy()
    for i, side in judged[:3]:
        sig = shw.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(4.0 * atr[i])
        assert sig["win_rate_prior"] == pytest.approx(0.4679)
        assert sig["rr_ratio"] == pytest.approx(2.0)
    # ZSC: SL 2.0x / TP 2.0x ATR(14); no win-rate prior is recorded.
    df = _load("FX_EURUSD_1d.csv")
    judged = families2.sig_zscore(df, 50, 2.5, True, 260)
    atr = harness_atr(df, 14).to_numpy()
    for i, side in judged[:3]:
        sig = zsc.get_signal(df.iloc[: i + 1])
        assert sig["side"] == ("BUY" if side == "LONG" else "SELL")
        assert sig["sl_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["tp_dist"] == pytest.approx(2.0 * atr[i])
        assert sig["rr_ratio"] == pytest.approx(1.0)
        assert "win_rate_prior" not in sig
    assert zsc.WIN_RATE_PRIOR is None
    assert not hasattr(zsc, "_OOS_WIN_RATE_PRIOR")


def test_quiet_bars_return_no_signal():
    # A bar with no judged entry is quiet for every gap module.
    df = _load("BTCUSDT_1d.csv")
    judged_dual = {i for i, _ in families2.sig_dual_momentum(df, 90, 260)}
    quiet = next(i for i in range(260, len(df) - 2) if i not in judged_dual)
    assert dual.get_signal(df.iloc[: quiet + 1])["side"] is None
    df = _load("BTCUSDT_1wk.csv")
    judged_shw = {i for i, _ in families3.sig_shock(df, 1.0, 104)}
    quiet = next(i for i in range(104, len(df) - 2) if i not in judged_shw)
    assert shw.get_signal(df.iloc[: quiet + 1])["side"] is None
    df = _load("FX_EURUSD_1d.csv")
    judged_zsc = {i for i, _ in families2.sig_zscore(df, 50, 2.5, True, 260)}
    quiet = next(i for i in range(260, len(df) - 2) if i not in judged_zsc)
    assert zsc.get_signal(df.iloc[: quiet + 1])["side"] is None


# ---------------------------------------------------------------------------
# 2. Engine context passing
# ---------------------------------------------------------------------------

def _member(module, key, panel="crypto30", timeframe="1d", sl=2.0, tp=4.0,
            universe=("BTCUSDT", "ETHUSDT")):
    return Member(
        module=module,
        key=key,
        cell="test",
        panel=panel,
        timeframe=timeframe,
        venue="binance_futures" if panel == "crypto30" else "oanda",
        sl_atr=sl,
        tp_atr=tp,
        universe=tuple(universe),
    )


def _book(key, members):
    return Book(key=key, trial=None, verdict="FORWARD_TEST", source="TEST",
                members=tuple(members))


def test_context_aware_member_receives_symbol_timeframe_venue(monkeypatch):
    from types import SimpleNamespace

    seen = {}

    def _get_signal(df, symbol=None, timeframe=None, venue=None):
        seen.update(symbol=symbol, timeframe=timeframe, venue=venue)
        return {"side": "BUY", "sl_dist": 10.0, "tp_dist": 30.0}

    monkeypatch.setitem(
        sys.modules, "strategy_fake_ctx",
        SimpleNamespace(get_signal=_get_signal),
    )
    monkeypatch.setattr(
        "strategies.ensemble_book._governance_status",
        lambda _module_name: "FORWARD_TEST",
    )
    book = _book("test_book", [_member("strategy_fake_ctx", "ctx")])
    out = evaluate_book(book, _flat_frame(), symbol="BTCUSDT",
                        timeframe="1d", venue="binance_futures",
                        state=BookState())
    assert out is not None and out["side"] == "BUY"
    assert seen == {"symbol": "BTCUSDT", "timeframe": "1d",
                    "venue": "binance_futures"}


def test_classic_member_still_called_with_df_only(monkeypatch):
    from types import SimpleNamespace

    calls = []

    def _get_signal(df):
        calls.append("classic")
        return {"side": "BUY", "sl_dist": 10.0, "tp_dist": 30.0}

    monkeypatch.setitem(
        sys.modules, "strategy_fake_classic",
        SimpleNamespace(get_signal=_get_signal),
    )
    monkeypatch.setattr(
        "strategies.ensemble_book._governance_status",
        lambda _module_name: "FORWARD_TEST",
    )
    book = _book("test_book", [_member("strategy_fake_classic", "classic")])
    out = evaluate_book(book, _flat_frame(), symbol="BTCUSDT",
                        timeframe="1d", venue="binance_futures",
                        state=BookState())
    assert out is not None and out["side"] == "BUY"
    assert calls == ["classic"]


def test_xs_member_signals_through_panel_membership(monkeypatch):
    # The xs leg contributes to the book once the engine passes it
    # the symbol: with a persisted membership entry for BTCUSDT at
    # the frame's last closed bar, book 3933 signals BUY from the
    # xs leg alone (the per-symbol members are quiet on the flat
    # fixture) with the judged bracket.
    frame = _flat_frame()
    epoch = int(frame.index[-1].timestamp())
    monkeypatch.setattr(
        xsl_module, "current_membership",
        lambda: {"ok": True, "entries": {
            "BTCUSDT": {"side": "LONG", "signal_bar_epoch": epoch},
        }},
    )
    book = BOOKS["ensemble_book_3933"]
    out = evaluate_book(book, frame, symbol="BTCUSDT", timeframe="1d",
                        venue="binance_futures", state=BookState())
    assert out is not None and out["side"] == "BUY"
    assert out["members_signalled"] == [("xs_lowvol", "BUY")]
    assert out["sl_dist"] == pytest.approx(4.0)
    assert out["tp_dist"] == pytest.approx(8.0)


def test_xs_member_abstains_without_membership(monkeypatch):
    # No persisted membership: the xs leg abstains, the book still
    # evaluates (no refusal is recorded) and returns NO_SIGNAL on
    # the flat fixture.
    monkeypatch.setattr(
        xsl_module, "current_membership", lambda: None,
    )
    book = BOOKS["ensemble_book_3933"]
    state = BookState()
    assert evaluate_book(book, _flat_frame(), symbol="BTCUSDT",
                         timeframe="1d", venue="binance_futures",
                         state=state) is None
    assert state.refusal_reason("ensemble_book_3933") is None


def test_xs_member_abstains_without_symbol(monkeypatch):
    # Without a symbol the engine has no symbol to pass the xs
    # member, so it abstains — the book still evaluates its other
    # members and records no refusal.
    monkeypatch.setattr(
        xsl_module, "current_membership",
        lambda: {"ok": True, "entries": {
            "BTCUSDT": {"side": "LONG", "signal_bar_epoch": 0},
        }},
    )
    book = BOOKS["ensemble_book_3933"]
    state = BookState()
    assert evaluate_book(book, _flat_frame(), timeframe="1d",
                         venue="binance_futures", state=state) is None
    assert state.refusal_reason("ensemble_book_3933") is None


# ---------------------------------------------------------------------------
# 3. Registry / partition
# ---------------------------------------------------------------------------

def test_registry_partition_and_priors():
    import config_strategy as cs

    for key, (_mod, tf, universe, wr, edge, _meas, _stop) in KEYS.items():
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        assert entry["status"] == "FORWARD_TEST", key
        assert entry["forward_protocol"] is True, key
        assert entry["forward_lane"] == "FORWARD_TEST", key
        assert entry["timeframe"] == tf, key
        assert entry["lane_assets"] == getattr(cs, universe), key
        assert entry["validated_assets"] == [], key
        assert entry["risk_per_trade_pct"] == 0.001, key
        assert entry["max_heat_pct"] == 0.02, key
        assert entry["runtime_priors_nulled"] is False, key
        if wr is None:
            # No win rate was published for this cell — none is
            # recorded (same precedent as the RD-003 documentary
            # cells, which assert oos_win_rate_prior is None).
            assert entry.get("oos_win_rate_prior") is None, key
        else:
            assert entry["oos_win_rate_prior"] == pytest.approx(wr), key
        assert entry["expected_net_edge_bps"] == pytest.approx(edge), key
        assert entry["total_friction_bps"] > 0, key
        assert "TASK-STR-FWD-030" in entry["reason"], key
    validated = {
        k for k, e in cs.PRODUCTION_STRATEGY_REGISTRY.items() if e["status"] == "VALIDATED"
    }
    assert validated == BASE_VALIDATED
    assert not (set(KEYS) & validated)


# ---------------------------------------------------------------------------
# 4. Stop-cap (FWD-012)
# ---------------------------------------------------------------------------

def test_stop_cap_consistency():
    import config_strategy as cs

    for key, (_mod, _tf, _u, _wr, _e, measured, stop) in KEYS.items():
        entry = cs.PRODUCTION_STRATEGY_REGISTRY[key]
        if stop is None:
            assert "max_stop_pct" not in entry, key
            assert measured <= 0.15, key
        else:
            assert entry["max_stop_pct"] == pytest.approx(stop), key
            assert entry["max_stop_pct"] > 0.15, key
            assert entry["max_stop_pct"] >= measured, key


def test_stop_cap_fixture_cross_checks():
    # The panel maxima in KEYS are capcheck_books.json figures; the
    # fixture slices must not exceed them at entry bars.
    df = _load("SOLUSDT_1d.csv")
    ent = families2.sig_dual_momentum(df, 90, 260)
    assert _entries_stop_max(df, ent, 2.5) <= 0.4246
    df = _load("SUIUSDT_1wk.csv")
    ent = families3.sig_shock(df, 1.0, 104)
    assert _entries_stop_max(df, ent, 2.0) <= 0.8716
    for f in ("FX_EURUSD_1d.csv", "FX_GBPJPY_1d.csv", "FX_USDJPY_1d.csv"):
        df = _load(f)
        ent = families2.sig_zscore(df, 50, 2.5, True, 260)
        assert _entries_stop_max(df, ent, 2.0) <= 0.0694


# ---------------------------------------------------------------------------
# 5. Discovery
# ---------------------------------------------------------------------------

def test_modules_discovered_and_demo_executable():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    reg = UnifiedStrategyRegistry()
    reg.set_demo_venues({"binance_futures", "oanda"})
    try:
        for key, (mod, tf, universe, _wr, _e, _m, _s) in KEYS.items():
            assert reg.get(mod.__name__) is not None, key
            assert reg.governance_status(mod.__name__) == "FORWARD_TEST", key
            symbol = "BTCUSDT" if universe == "CRYPTO30_SYMBOLS" else "EURUSD"
            venue = "binance_futures" if universe == "CRYPTO30_SYMBOLS" else "oanda"
            ok, _reason = reg.executable(mod.__name__, tf, symbol, venue=venue)
            assert ok, key
        # The registry detects the xs module as context-aware (its
        # get_signal takes symbol/timeframe/venue); the three gap
        # modules are classic single-argument modules.
        assert reg._accepts_context.get("strategy_xs_lowvol") is True
        for mod in (dual, shw, zsc):
            assert reg._accepts_context.get(mod.__name__) is False, mod.__name__
    finally:
        reg.set_demo_venues(set())


# ---------------------------------------------------------------------------
# 6. Books evaluate through the registry path
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def registry():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    return UnifiedStrategyRegistry()


def test_books_evaluate_through_execute_strategy(registry, monkeypatch):
    # No persisted panel membership in this process: the xs leg
    # abstains, the books still evaluate (NO_SIGNAL on flat fixtures,
    # never a refusal ERROR) — at 1d for both books.
    monkeypatch.setattr(xsl_module, "current_membership", lambda: None)
    registry.set_demo_venues({"binance_futures", "oanda"})
    try:
        for key in ("ensemble_book_3933", "ensemble_book_3978"):
            for _ in range(2):
                out = registry.execute_strategy(
                    "strategy_" + key, _flat_frame(), "1d", "BTCUSDT",
                    venue="binance_futures",
                )
                assert out["status"] == "NO_SIGNAL", (key, out)
    finally:
        registry.set_demo_venues(set())


def test_book_3978_evaluates_at_weekly_venue_label(registry, monkeypatch):
    # Book 3978 at the venue label '1w': the weekly member evaluates
    # on the weekly frame; the 1d members have no cached signal yet,
    # so the book is not ready — NO_SIGNAL, not a refusal.
    monkeypatch.setattr(xsl_module, "current_membership", lambda: None)
    registry.set_demo_venues({"binance_futures", "oanda"})
    try:
        out = registry.execute_strategy(
            "strategy_ensemble_book_3978", _flat_frame(n=150, freq="7D"),
            "1w", "BTCUSDT", venue="binance_futures",
        )
        assert out["status"] == "NO_SIGNAL", out
    finally:
        registry.set_demo_venues(set())
