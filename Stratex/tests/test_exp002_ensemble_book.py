"""TASK-STR-EXP-002: ensemble-book execution module tests.

Covers, in order:
  1. Book construction from the RD-025 / loop figures (pinned literals —
     every figure was recomputed offline from the saved RD-002 trade
     lists and matches the recorded rows/<trial>.json exactly; see
     ~/workspace/str-slice2/verify_books.py).
  2. Equal-weight combination arithmetic (synthetic member modules).
  3. Fail-closed on missing / disabled / module-less members, and on
     missing context for mixed books (incl. the test-pinned XSL
     exclusion: books 3933 and 3978 refuse until xs rotation machinery
     exists).
  4. Venue mapping per member (wrong venue / unknown panel refuse;
     a member not applicable to the frame's panel abstains, not fails).
  5. Stop-cap assertions (measured maxima pinned from
     ~/workspace/str-slice2/capcheck_books.json; every book's override
     exceeds every member's measured maximum stop).
  6. Governance classification: every book resolves to FORWARD_TEST via
     the daemon's own governance_status_for, with lane-executable priors
     intact; config entries agree with the canonical BOOKS dict.
  7. Registry integration: merged_registry_view (same shape as the
     loop's merged_registry, PR #986) + book_from_admission.
  8. Equivalence: the book's pooled signal stream on a stored slice of
     REAL trades (fixtures/exp002_book_3905_slice.json — 339 OOS trades,
     2024-07-01 -> 2025-06-30) reproduces the RD-025 recorded pooled
     metrics within rounding, and the netting gap on that slice matches
     the offline measurement. The full-book equivalence (all 8 books,
     exact match on trades/expectancy/PF) is the offline verify_books.py
     run, recorded in ~/workspace/str-selfexp/SLICE2.md — it needs the
     full trade lists, which do not ship in the repo.
  9. Registry context passing (get_signal receives symbol/timeframe/
     venue) and the raise-once-then-quiet refusal through
     execute_strategy.
 10. Daemon wiring: the 8 books are forward-protocol entries and map to
     the FORWARD_TEST lane.

No test touches the network, the bridge, or a live venue. Everything
runs on synthetic frames, fake member modules, or shipped fixtures.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from strategies.ensemble_book import (  # noqa: E402
    Book,
    BookState,
    EnsembleBookError,
    Member,
    RegistryCollisionError,
    book_from_admission,
    book_from_registry_entry,
    evaluate_book,
    merged_registry_view,
)
from strategies.ensemble_books import BOOKS  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

BOOK_KEYS = [
    "ensemble_book_3905",
    "ensemble_book_3906",
    "ensemble_book_3927",
    "ensemble_book_3928",
    "ensemble_book_3929",
    "ensemble_book_3933",
    "ensemble_book_3978",
    "ensemble_book_3900",
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _frame(n=300, close=100.0, start="2024-01-01"):
    idx = pd.date_range(start, periods=n, freq="D", tz="UTC")
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


def _fake_module(signal, calls=None):
    """A member module whose get_signal always returns `signal`."""
    def _get_signal(df):
        if calls is not None:
            calls.append(1)
        return dict(signal) if isinstance(signal, dict) else signal

    return SimpleNamespace(get_signal=_get_signal)


def _install_fake(monkeypatch, name, signal, calls=None):
    module = _fake_module(signal, calls)
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(
        "strategies.ensemble_book._governance_status",
        lambda _module_name: "FORWARD_TEST",
    )
    return module


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


# ---------------------------------------------------------------------------
# 1. Book construction from the RD-025 / loop figures
# ---------------------------------------------------------------------------

# Recorded pooled figures (rows/<trial>.json + the loop's first-light
# record), recomputed offline from the saved trade lists — exact match
# on trades / expectancy / PF (see verify_books.py).
RECORDED = {
    "ensemble_book_3905": dict(trades=784, expectancy=0.019383, pf=1.4548,
                               win_rate=0.3839, edge_bps=193.8, folds="4/5"),
    "ensemble_book_3906": dict(trades=820, expectancy=0.017244, pf=1.4333,
                               win_rate=0.4122, edge_bps=172.4, folds="4/5"),
    "ensemble_book_3927": dict(trades=1150, expectancy=0.009665, pf=1.4639,
                               win_rate=0.4096, edge_bps=96.7, folds="4/5"),
    "ensemble_book_3928": dict(trades=1149, expectancy=0.009120, pf=1.4440,
                               win_rate=0.3847, edge_bps=91.2, folds="4/5"),
    "ensemble_book_3929": dict(trades=1185, expectancy=0.008249, pf=1.4235,
                               win_rate=0.4042, edge_bps=82.5, folds="4/5"),
    "ensemble_book_3933": dict(trades=1295, expectancy=0.009253, pf=1.4072,
                               win_rate=0.4672, edge_bps=92.5, folds="4/5"),
    "ensemble_book_3978": dict(trades=1698, expectancy=0.004728, pf=1.3262,
                               win_rate=0.4441, edge_bps=47.3, folds="4/5"),
    "ensemble_book_3900": dict(trades=1719, expectancy=0.008131, pf=1.2643,
                               win_rate=0.3921, edge_bps=81.3, folds="4/5"),
}

EXPECTED_MEMBERS = {
    "ensemble_book_3905": ("shock_breakout", "donchian_turtle"),
    "ensemble_book_3906": ("shock_breakout", "ts_momentum"),
    "ensemble_book_3927": ("vol_adaptive_trend", "shock_breakout",
                           "stoch_reversion"),
    "ensemble_book_3928": ("donchian_turtle", "shock_breakout",
                           "stoch_reversion"),
    "ensemble_book_3929": ("ts_momentum", "shock_breakout",
                           "stoch_reversion"),
    "ensemble_book_3933": ("vol_adaptive_trend", "shock_breakout",
                           "xs_lowvol"),
    "ensemble_book_3978": ("tsmom2_dual", "shock_breakout",
                           "zscore_reversion", "ha_trend", "xs_lowvol"),
    "ensemble_book_3900": ("vol_adaptive_trend", "shock_breakout",
                           "stoch_reversion"),
}


@pytest.mark.parametrize("key", BOOK_KEYS)
def test_book_figures_match_recorded(key):
    book = BOOKS[key]
    rec = RECORDED[key]
    assert book.trades == rec["trades"], key
    assert book.expectancy == pytest.approx(rec["expectancy"], abs=1e-6), key
    assert book.pf == pytest.approx(rec["pf"], abs=1e-4), key
    assert book.win_rate == pytest.approx(rec["win_rate"], abs=1e-4), key
    assert book.edge_bps == pytest.approx(rec["edge_bps"], abs=0.05), key
    assert book.folds == rec["folds"], key
    assert book.verdict == "PROVEN", key
    assert tuple(m.key for m in book.members) == EXPECTED_MEMBERS[key], key


def test_first_light_uses_loop_cells_not_rd025_cells():
    book = BOOKS["ensemble_book_3900"]
    assert book.source == "LOOP", "first-light is a loop book, not RD-025"
    by_key = {m.key: m for m in book.members}
    # The loop's shock cell is k1.0 (book 3905 uses k1.5) and its stoch
    # cell is the CRYPTO30 panel (book 3927 uses forex28).
    assert by_key["shock_breakout"].cell == "k1.0"
    assert by_key["stoch_reversion"].panel == "crypto30"
    assert by_key["shock_breakout"].module == "strategy_shock_breakout"
    assert by_key["stoch_reversion"].module == "strategy_stoch_reversion_crypto"


# ---------------------------------------------------------------------------
# 2. Equal-weight combination arithmetic
# ---------------------------------------------------------------------------

BUY_10_30 = {"side": "BUY", "sl_dist": 10.0, "tp_dist": 30.0}
BUY_20_40 = {"side": "BUY", "sl_dist": 20.0, "tp_dist": 40.0}
SELL_100_200 = {"side": "SELL", "sl_dist": 100.0, "tp_dist": 200.0}
ABSTAIN = {"side": None}


def test_two_longs_combine_to_long_with_mean_bracket(monkeypatch):
    _install_fake(monkeypatch, "strategy_fake_a", BUY_10_30)
    _install_fake(monkeypatch, "strategy_fake_b", BUY_20_40)
    book = _book("test_book", [
        _member("strategy_fake_a", "a"),
        _member("strategy_fake_b", "b"),
    ])
    out = evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                        venue="binance_futures", state=BookState())
    assert out is not None
    assert out["side"] == "BUY"
    assert out["sl_dist"] == pytest.approx(15.0)
    assert out["tp_dist"] == pytest.approx(35.0)
    assert out["rr_ratio"] == pytest.approx(35.0 / 15.0)
    assert out["net"] == 2
    assert out["strategy_type"] == "ENSEMBLE_BOOK"


def test_opposite_signals_cancel_to_no_signal(monkeypatch):
    _install_fake(monkeypatch, "strategy_fake_a", BUY_10_30)
    _install_fake(monkeypatch, "strategy_fake_b", SELL_100_200)
    book = _book("test_book", [
        _member("strategy_fake_a", "a"),
        _member("strategy_fake_b", "b"),
    ])
    out = evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                        venue="binance_futures", state=BookState())
    assert out is None


def test_bracket_uses_only_net_direction_members(monkeypatch):
    _install_fake(monkeypatch, "strategy_fake_a", BUY_10_30)
    _install_fake(monkeypatch, "strategy_fake_b", BUY_20_40)
    _install_fake(monkeypatch, "strategy_fake_c", SELL_100_200)
    book = _book("test_book", [
        _member("strategy_fake_a", "a"),
        _member("strategy_fake_b", "b"),
        _member("strategy_fake_c", "c"),
    ])
    out = evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                        venue="binance_futures", state=BookState())
    assert out is not None
    assert out["side"] == "BUY"
    assert out["net"] == 1
    # The SHORT member's 100/200 bracket must NOT enter the mean.
    assert out["sl_dist"] == pytest.approx(15.0)
    assert out["tp_dist"] == pytest.approx(35.0)


def test_all_abstain_is_no_signal(monkeypatch):
    _install_fake(monkeypatch, "strategy_fake_a", ABSTAIN)
    _install_fake(monkeypatch, "strategy_fake_b", ABSTAIN)
    book = _book("test_book", [
        _member("strategy_fake_a", "a"),
        _member("strategy_fake_b", "b"),
    ])
    out = evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                        venue="binance_futures", state=BookState())
    assert out is None


def test_sl_tp_prices_derive_dists(monkeypatch):
    # A member returning absolute sl/tp prices (no dists) still yields a
    # usable bracket, derived at the signal bar's close (100.0).
    _install_fake(monkeypatch, "strategy_fake_a",
                  {"side": "BUY", "sl": 90.0, "tp": 130.0})
    book = _book("test_book", [_member("strategy_fake_a", "a")])
    out = evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                        venue="binance_futures", state=BookState())
    assert out is not None
    assert out["sl_dist"] == pytest.approx(10.0)
    assert out["tp_dist"] == pytest.approx(30.0)
    assert out["sl"] == pytest.approx(90.0)
    assert out["tp"] == pytest.approx(130.0)


def test_mixed_timeframe_cache(monkeypatch):
    """A 1wk member contributes its last cached signal on a 1d scan;
    until its own timeframe has been scanned the book is not ready."""
    _install_fake(monkeypatch, "strategy_fake_a", BUY_10_30)
    _install_fake(monkeypatch, "strategy_fake_b", BUY_20_40)
    book = _book("test_book", [
        _member("strategy_fake_a", "a", timeframe="1d"),
        _member("strategy_fake_b", "b", timeframe="1wk"),
    ])
    state = BookState()
    frame_1d = _frame(start="2024-01-01")
    frame_1wk = _frame(n=60, start="2024-01-01")
    # 1d scan first: the 1wk member has never been evaluated -> not ready.
    assert evaluate_book(book, frame_1d, symbol="BTCUSDT", timeframe="1d",
                         venue="binance_futures", state=state) is None
    # 1wk scan: the 1wk member evaluates now; the 1d member contributes
    # its cached signal from the earlier 1d scan.
    out = evaluate_book(book, frame_1wk, symbol="BTCUSDT", timeframe="1wk",
                        venue="binance_futures", state=state)
    assert out is not None and out["side"] == "BUY" and out["net"] == 2
    # A later 1d scan reuses the 1wk member's cached signal.
    out = evaluate_book(book, _frame(start="2024-02-01"), symbol="BTCUSDT",
                        timeframe="1d", venue="binance_futures", state=state)
    assert out is not None and out["side"] == "BUY" and out["net"] == 2


# ---------------------------------------------------------------------------
# 3. Fail-closed
# ---------------------------------------------------------------------------

def test_missing_member_module_refuses_once_then_quiet(monkeypatch):
    monkeypatch.setattr(
        "strategies.ensemble_book._governance_status",
        lambda _module_name: "FORWARD_TEST",
    )
    book = _book("test_book", [_member("strategy_does_not_exist_xyz", "a")])
    state = BookState()
    with pytest.raises(EnsembleBookError, match="cannot be imported"):
        evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                      venue="binance_futures", state=state)
    assert state.refusal_reason("test_book") is not None
    # Later calls return NO_SIGNAL (no error spam, no UNHEALTHY flip).
    assert evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                         venue="binance_futures", state=state) is None


def test_disabled_member_refuses_whole_book(monkeypatch):
    _install_fake(monkeypatch, "strategy_fake_a", BUY_10_30)

    def _status(name):
        return "DISABLED" if name == "strategy_fake_a" else "FORWARD_TEST"

    monkeypatch.setattr("strategies.ensemble_book._governance_status", _status)
    book = _book("test_book", [
        _member("strategy_fake_a", "a"),
        _member("strategy_fake_b", "b"),
    ])
    with pytest.raises(EnsembleBookError, match="governed DISABLED"):
        evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                      venue="binance_futures", state=BookState())


def test_member_without_bracket_raises(monkeypatch):
    _install_fake(monkeypatch, "strategy_fake_a", {"side": "BUY"})
    book = _book("test_book", [_member("strategy_fake_a", "a")])
    with pytest.raises(EnsembleBookError, match="no usable bracket"):
        evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                      venue="binance_futures", state=BookState())


def test_xs_lowvol_member_has_no_module():
    for key in ("ensemble_book_3933", "ensemble_book_3978"):
        xsl = [m for m in BOOKS[key].members if m.key == "xs_lowvol"]
        assert len(xsl) == 1, key
        assert xsl[0].module is None, key
        assert "cross-sectional" in xsl[0].unavailable_reason, key
        assert "PENDING_XS_ROTATION_MACHINERY" in BOOKS[key].execution, key


def test_xs_books_refuse_whole_book(monkeypatch):
    # A book whose only member is the module-less xs rotation refuses
    # (never silently trades the remaining members).
    book = _book("test_book", [
        Member(module=None, key="xs_lowvol", cell="lv20_r10",
               panel="crypto30", timeframe="1d", venue="binance_futures",
               sl_atr=2.0, tp_atr=4.0,
               universe=("BTCUSDT",),
               unavailable_reason="xs_lowvol is a cross-sectional rotation"),
    ])
    with pytest.raises(EnsembleBookError, match="xs_lowvol"):
        evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                      venue="binance_futures", state=BookState())


def test_mixed_book_without_context_refuses(monkeypatch):
    _install_fake(monkeypatch, "strategy_fake_a", BUY_10_30)
    _install_fake(monkeypatch, "strategy_fake_fx", BUY_10_30)
    book = _book("test_book", [
        _member("strategy_fake_a", "a", panel="crypto30"),
        _member("strategy_fake_fx", "fx", panel="forex28",
                universe=("EURUSD",)),
    ])
    with pytest.raises(EnsembleBookError, match="without symbol or venue"):
        evaluate_book(book, _frame(), state=BookState())


# Post-lane-4 partition of the real books (verified per book on main
# c52933e1): the wave-2 member PRs merged in lane 4, so six books now
# have every member module on main and EVALUATE; two still refuse
# because a member is genuinely absent. The partition is pinned
# exactly -- when a refusing book's remaining members land, move its
# key into REAL_BOOKS_EVALUATING in the same change;
# test_real_books_partition_covers_all_books forces that deliberate
# update instead of a silent behaviour change.
REAL_BOOKS_EVALUATING = [
    "ensemble_book_3905",  # SHK k1.5 (#996) + DON n55 (#987)
    "ensemble_book_3906",  # SHK k1.5 (#996) + TSM roc72 (#991)
    "ensemble_book_3927",  # VA (#983) + SHK k1.5 (#996) + STO fx (#994)
    "ensemble_book_3928",  # DON (#987) + SHK k1.5 (#996) + STO fx (#994)
    "ensemble_book_3929",  # TSM (#991) + SHK k1.5 (#996) + STO fx (#994)
    "ensemble_book_3900",  # VA (#983) + SHK k1.0 (was on main) + STO crypto (#994)
]
# key -> substring the refusal reason must name (the first member that
# cannot be resolved, in declaration order).
REAL_BOOKS_REFUSING = {
    # XSL is declared module=None: a cross-sectional rotation cannot
    # be a per-symbol member until the engine passes it panel context
    # (books still refuse even though strategy_xs_lowvol exists).
    "ensemble_book_3933": "xs_lowvol",
    # DUAL 1d has no module yet (PR #991 built the 4h cell only); the
    # SHW and ZSC modules also do not exist, and XSL is module=None.
    "ensemble_book_3978": "strategy_tsmom2_dual_crypto_1d",
}


def test_real_books_partition_covers_all_books():
    assert sorted(REAL_BOOKS_EVALUATING + list(REAL_BOOKS_REFUSING)) \
        == sorted(BOOK_KEYS)


def test_real_books_with_all_members_present_evaluate():
    # Every member module exists on main, so the book evaluates. On
    # the flat fixture no member signals: the neutral outcome is None
    # (NO_SIGNAL) on both calls and NO refusal is recorded -- the exact
    # opposite of the pre-lane-4 behaviour the old version of
    # test_real_books_refuse_until_members_land pinned for all books.
    for key in REAL_BOOKS_EVALUATING:
        book = BOOKS[key]
        state = BookState()
        assert evaluate_book(book, _frame(), symbol="BTCUSDT",
                             timeframe="1d", venue="binance_futures",
                             state=state) is None, key
        assert state.refusal_reason(key) is None, key
        assert evaluate_book(book, _frame(), symbol="BTCUSDT",
                             timeframe="1d", venue="binance_futures",
                             state=state) is None, key


def test_real_books_refuse_until_members_land():
    # The books whose members have NOT all landed still refuse,
    # fail-closed: the first call raises naming the missing member,
    # the refusal is recorded, and the second call is quiet NO_SIGNAL.
    for key, marker in REAL_BOOKS_REFUSING.items():
        book = BOOKS[key]
        state = BookState()
        with pytest.raises(EnsembleBookError, match="member"):
            evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                          venue="binance_futures", state=state)
        reason = state.refusal_reason(key)
        assert reason is not None and marker in reason, key
        assert evaluate_book(book, _frame(), symbol="BTCUSDT",
                             timeframe="1d", venue="binance_futures",
                             state=state) is None


def test_book_with_all_members_missing_refuses(monkeypatch):
    # Independent of which real books happen to be incomplete: a book
    # whose members ALL point at modules that do not exist refuses on
    # the first missing member, records the refusal, and is quiet
    # NO_SIGNAL afterwards.
    monkeypatch.setattr(
        "strategies.ensemble_book._governance_status",
        lambda _module_name: "FORWARD_TEST",
    )
    book = _book("test_book", [
        _member("strategy_missing_one_xyz", "a"),
        _member("strategy_missing_two_xyz", "b"),
    ])
    state = BookState()
    with pytest.raises(EnsembleBookError, match="cannot be imported"):
        evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                      venue="binance_futures", state=state)
    assert state.refusal_reason("test_book") is not None
    assert evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                         venue="binance_futures", state=state) is None


def test_book_never_partially_evaluates_with_a_missing_member(monkeypatch):
    # One member present and signalling, one member missing: the whole
    # book refuses, and the present member is never even evaluated --
    # the engine resolves EVERY member before evaluating ANY -- so no
    # subset of a book can ever produce a signal.
    calls = []
    _install_fake(monkeypatch, "strategy_fake_a", BUY_10_30, calls)
    book = _book("test_book", [
        _member("strategy_fake_a", "a"),
        _member("strategy_missing_xyz", "b"),
    ])
    state = BookState()
    with pytest.raises(EnsembleBookError, match="cannot be imported"):
        evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                      venue="binance_futures", state=state)
    assert calls == []
    assert state.refusal_reason("test_book") is not None


# ---------------------------------------------------------------------------
# 4. Venue mapping per member
# ---------------------------------------------------------------------------

def test_member_venue_mismatch_refuses(monkeypatch):
    _install_fake(monkeypatch, "strategy_fake_a", BUY_10_30)
    member = Member(module="strategy_fake_a", key="a", cell="test",
                    panel="crypto30", timeframe="1d", venue="oanda",
                    sl_atr=2.0, tp_atr=4.0, universe=("BTCUSDT",))
    with pytest.raises(EnsembleBookError, match="does not match its panel"):
        evaluate_book(_book("test_book", [member]), _frame(),
                      symbol="BTCUSDT", timeframe="1d", venue="oanda",
                      state=BookState())


def test_unknown_panel_refuses(monkeypatch):
    _install_fake(monkeypatch, "strategy_fake_a", BUY_10_30)
    member = Member(module="strategy_fake_a", key="a", cell="test",
                    panel="comm7", timeframe="1d", venue="binance_futures",
                    sl_atr=2.0, tp_atr=4.0, universe=("GOLD",))
    with pytest.raises(EnsembleBookError, match="no demo venue mapping"):
        evaluate_book(_book("test_book", [member]), _frame(),
                      symbol="GOLD", timeframe="1d",
                      venue="binance_futures", state=BookState())


def test_inapplicable_member_abstains_not_fails(monkeypatch):
    calls = []
    _install_fake(monkeypatch, "strategy_fake_a", BUY_10_30)
    _install_fake(monkeypatch, "strategy_fake_fx", BUY_10_30, calls)
    book = _book("test_book", [
        _member("strategy_fake_a", "a", panel="crypto30"),
        _member("strategy_fake_fx", "fx", panel="forex28",
                universe=("EURUSD",)),
    ])
    # A crypto frame: the forex member is never evaluated (it never
    # traded BTC in the judgement either) and the book still signals.
    out = evaluate_book(book, _frame(), symbol="BTCUSDT", timeframe="1d",
                        venue="binance_futures", state=BookState())
    assert out is not None and out["side"] == "BUY"
    assert calls == []


# ---------------------------------------------------------------------------
# 5. Stop-cap assertions
# ---------------------------------------------------------------------------

# Measured maximum judged stop (fraction of price) per member cell,
# FWD-012 method: harness signal bars x production Wilder ATR(14),
# crypto 1d/1wk from Binance Vision klines, forex 1d from local Yahoo
# caches (~/workspace/str-slice2/capcheck_books.json).
MEASURED_MAX_STOP = {
    ("vol_adaptive_trend", "ema12_26_nogate", "crypto30", "1d"): 0.4922,
    ("donchian_turtle", "n55_b26", "crypto30", "1d"): 0.3624,
    ("ts_momentum", "roc72", "crypto30", "1d"): 0.3601,
    ("macd_trend", "hist_raw", "crypto30", "1d"): 0.4438,
    ("stoch_reversion", "k14_raw", "forex28", "1d"): 0.2003,
    ("stoch_reversion", "k14_raw", "crypto30", "1d"): 0.3347,
    ("shock_breakout", "k1.5", "crypto30", "1d"): 0.3624,
    ("shock_breakout", "k1.0", "crypto30", "1d"): 0.3624,
    ("shock_breakout", "k1.0", "crypto30", "1wk"): 0.8716,
    ("tsmom2_dual", "roc90_ema200", "crypto30", "1d"): 0.4246,
    ("ha_trend", "two_candle", "crypto30", "1d"): 0.3938,
    ("bollinger_trend", "p20_sd2.0", "crypto30", "1d"): 0.3624,
    ("ichimoku_trend", "tk_cloud", "crypto30", "1d"): 0.3692,
    ("zscore_reversion", "w50_t2.5_filt", "forex28", "1d"): 0.0694,
}


@pytest.mark.parametrize("key", BOOK_KEYS)
def test_book_stop_override_covers_measured_maxima(key):
    book = BOOKS[key]
    maxima = []
    for m in book.members:
        if m.key == "xs_lowvol":
            continue  # cross-sectional: no per-symbol judged stop exists
        maxima.append(MEASURED_MAX_STOP[(m.key, m.cell, m.panel, m.timeframe)])
    assert maxima, key
    assert book.max_stop_pct > max(maxima), (
        f"{key}: override {book.max_stop_pct} does not cover measured "
        f"max {max(maxima)}"
    )


@pytest.mark.parametrize(
    "key,override",
    [
        ("ensemble_book_3905", 0.50),
        ("ensemble_book_3906", 0.50),
        ("ensemble_book_3927", 0.60),
        ("ensemble_book_3928", 0.50),
        ("ensemble_book_3929", 0.50),
        ("ensemble_book_3933", 0.60),
        ("ensemble_book_3978", 0.90),
        ("ensemble_book_3900", 0.60),
    ],
)
def test_book_stop_override_values(key, override):
    assert BOOKS[key].max_stop_pct == pytest.approx(override), key


# ---------------------------------------------------------------------------
# 6. Governance classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", BOOK_KEYS)
def test_governance_classification_is_forward_test(key):
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY
    from strategies.strategy_registry import governance_status_for

    assert governance_status_for("strategy_" + key) == "FORWARD_TEST", key
    entry = PRODUCTION_STRATEGY_REGISTRY[key]
    assert entry["status"] == "FORWARD_TEST", key
    assert entry["forward_protocol"] is True, key
    assert entry["forward_lane"] == "FORWARD_TEST", key
    assert entry["runtime_priors_nulled"] is False, key
    assert entry["oos_win_rate_prior"] == pytest.approx(
        BOOKS[key].win_rate, abs=1e-4), key
    assert entry["expected_net_edge_bps"] == pytest.approx(
        BOOKS[key].edge_bps, abs=0.05), key
    assert entry["max_stop_pct"] == pytest.approx(BOOKS[key].max_stop_pct), key
    assert entry["execution"] == BOOKS[key].execution, key
    assert not entry.get("validated_assets"), key


def test_config_entries_agree_with_canonical_books():
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY

    for key in BOOK_KEYS:
        entry = PRODUCTION_STRATEGY_REGISTRY[key]
        rebuilt = book_from_registry_entry(key, entry)
        canonical = BOOKS[key]
        assert rebuilt.trial == canonical.trial, key
        assert rebuilt.verdict == canonical.verdict, key
        assert rebuilt.source == canonical.source, key
        assert rebuilt.trades == canonical.trades, key
        assert rebuilt.pf == pytest.approx(canonical.pf, abs=1e-4), key
        assert rebuilt.win_rate == pytest.approx(canonical.win_rate,
                                                 abs=1e-4), key
        assert rebuilt.max_stop_pct == pytest.approx(
            canonical.max_stop_pct), key
        assert len(rebuilt.members) == len(canonical.members), key
        for got, want in zip(rebuilt.members, canonical.members):
            assert got.module == want.module, key
            assert got.key == want.key, key
            assert got.cell == want.cell, key
            assert got.panel == want.panel, key
            assert got.timeframe == want.timeframe, key
            assert got.venue == want.venue, key
            assert got.sl_atr == want.sl_atr, key
            assert got.tp_atr == want.tp_atr, key


def test_book_3978_uses_timeframes_list():
    from config_strategy import PRODUCTION_STRATEGY_REGISTRY

    entry = PRODUCTION_STRATEGY_REGISTRY["ensemble_book_3978"]
    assert entry["timeframes"] == ["1d", "1wk"]
    assert "timeframe" not in entry


# ---------------------------------------------------------------------------
# 7. Registry integration (loop admissions)
# ---------------------------------------------------------------------------

def _loop_admission_3900():
    """A loop admission entry in exactly the shape admit() produces
    (TASK-STR-EXP-001), for the first-light book."""
    return {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-EXP-001)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "oos_win_rate_prior": 0.3921,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 81.3,
        "minimum_required_edge": 0.0005,
        "lane_assets": ["BTCUSDT"],
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "self_experiment": True,
        "self_experiment_verdict": "PROVEN",
        "declaration_id": "decl-test-3900",
        "members": [
            "vol_adaptive_trend__ema12_26_nogate__at__crypto30__1d",
            "shock_breakout__k1.0__at__crypto30__1d",
            "stoch_reversion__k14_raw__at__crypto30__1d",
        ],
        "execution": "PENDING_ENSEMBLE_MODULE",
        "reason": (
            "TASK-STR-EXP-001 SELF-EXPERIMENT admission (PROVEN): "
            "combination of vol_adaptive_trend__ema12_26_nogate__at__"
            "crypto30__1d, shock_breakout__k1.0__at__crypto30__1d, "
            "stoch_reversion__k14_raw__at__crypto30__1d @ crypto30 1d "
            "judged pooled on stored OOS trades (declaration "
            "decl-test-3900, global trial N=3900): expectancy "
            "+0.8131%/trade, PF 1.2643, 1719 OOS trades, 4/5 positive "
            "folds."
        ),
    }


def test_book_from_loop_admission():
    entry = _loop_admission_3900()
    metrics = {"trades": 1719, "expectancy": 0.008131, "pf": 1.2643,
               "win_rate": 0.3921, "folds": "4/5"}
    book = book_from_admission(entry, "selfexp_combo_test3900",
                               metrics=metrics)
    canonical = BOOKS["ensemble_book_3900"]
    assert book.trial == 3900
    assert book.verdict == "PROVEN"
    assert book.source == "LOOP"
    assert book.trades == 1719
    assert book.pf == pytest.approx(1.2643, abs=1e-4)
    assert book.win_rate == pytest.approx(0.3921, abs=1e-4)
    assert len(book.members) == len(canonical.members)
    for got, want in zip(book.members, canonical.members):
        assert got.module == want.module
        assert got.key == want.key
        assert got.cell == want.cell
        assert got.panel == want.panel
        assert got.timeframe == want.timeframe


def test_book_from_admission_refuses_unknown_stream():
    entry = _loop_admission_3900()
    entry["members"] = [
        "xs_lowvol__lv20_r10__at__crypto30__1d",
    ]
    with pytest.raises(EnsembleBookError, match="no production module"):
        book_from_admission(entry, "selfexp_combo_test_xsl")


def test_merged_registry_view():
    base = {"ichimoku_trend": {"status": "VALIDATED"}}
    admissions = {"selfexp_combo_abc": _loop_admission_3900()}
    merged = merged_registry_view(base, admissions)
    assert merged["ichimoku_trend"] == {"status": "VALIDATED"}
    assert merged["selfexp_combo_abc"]["status"] == "FORWARD_TEST"
    assert base == {"ichimoku_trend": {"status": "VALIDATED"}}, \
        "the base registry is never mutated"
    assert merged is not base


def test_merged_registry_view_collision_refuses():
    base = {"selfexp_combo_abc": {"status": "VALIDATED"}}
    with pytest.raises(RegistryCollisionError, match="collides"):
        merged_registry_view(base, {"selfexp_combo_abc": _loop_admission_3900()})


def test_merged_registry_view_agrees_with_loop_when_present():
    pytest.importorskip("self_experiments.admissions")
    from self_experiments.admissions import merged_registry

    base = {"ichimoku_trend": {"status": "VALIDATED"}}
    admissions = {"selfexp_combo_abc": _loop_admission_3900()}

    class _Stub:
        def entries(self):
            return dict(admissions)

    assert merged_registry(base, _Stub()) == merged_registry_view(
        base, admissions)


# ---------------------------------------------------------------------------
# 8. Equivalence on a stored slice of real trades
# ---------------------------------------------------------------------------

def _pooled(trades, k):
    """Equal-weight pooled metrics (independent re-implementation of the
    RD-025 pooling: each member trade's net_return scaled by 1/k)."""
    n = len(trades)
    wins = sum(1 for t in trades if t["net_return"] > 0)
    gross_win = sum(t["net_return"] for t in trades if t["net_return"] > 0) / k
    gross_loss = sum(-t["net_return"] for t in trades if t["net_return"] < 0) / k
    expectancy = (sum(t["net_return"] for t in trades) / k) / n
    return {
        "trades": n,
        "wins": wins,
        "win_rate": wins / n,
        "expectancy": expectancy,
        "pf": gross_win / gross_loss,
        "edge_bps": round(expectancy * 10000, 1),
    }


def _netting(member_trades):
    """Union-vs-netting gap from trade lists (independent
    re-implementation: a member holds its position on days
    entry_date <= d < exit_date)."""
    from collections import defaultdict
    from datetime import date

    pos = defaultdict(dict)
    for code, trades in member_trades.items():
        for t in trades:
            d0 = date.fromisoformat(t["entry_time"][:10])
            d1 = date.fromisoformat(t["exit_time"][:10])
            if d1 <= d0:
                d1 = date.fromordinal(d0.toordinal() + 1)
            d = d0
            while d < d1:
                pos[(t["symbol"], d)][code] = 1 if t["side"] == "LONG" else -1
                d = date.fromordinal(d.toordinal() + 1)
    member_days = sum(len(legs) for legs in pos.values())
    netted_days = sum(abs(sum(legs.values())) for legs in pos.values())
    conflict_days = sum(1 for legs in pos.values()
                        if sum(legs.values()) == 0)
    live_entries = 0
    by_sym = defaultdict(list)
    for (sym, d), legs in pos.items():
        by_sym[sym].append((d, sum(legs.values())))
    for series in by_sym.values():
        series.sort()
        prev = 0
        for _d, net in series:
            s = 1 if net > 0 else (-1 if net < 0 else 0)
            if s != prev and s != 0:
                live_entries += 1
            prev = s
    return {
        "active_symbol_days": len(pos),
        "member_position_days": member_days,
        "netted_position_days": netted_days,
        "cancelled_leg_days": member_days - netted_days,
        "cancelled_pct": round(100 * (member_days - netted_days) / member_days, 2),
        "conflict_days": conflict_days,
        "conflict_pct": round(100 * conflict_days / len(pos), 2),
        "partial_days": sum(
            1 for legs in pos.values()
            if sum(legs.values()) != 0
            and any(v != (1 if sum(legs.values()) > 0 else -1)
                    for v in legs.values())),
        "live_trade_entries_approx": live_entries,
    }


def test_equivalence_on_stored_slice():
    with open(os.path.join(FIXTURES, "exp002_book_3905_slice.json")) as fh:
        fixture = json.load(fh)
    assert fixture["book"] == "ensemble_book_3905"
    assert fixture["slice"] == ["2024-07-01", "2025-06-30"]
    members = fixture["members"]
    assert set(members) == {"VA", "SHK"}
    pooled = _pooled(members["VA"] + members["SHK"], 2)
    expected = fixture["expected_pooled"]
    assert pooled["trades"] == expected["trades"] == 339
    assert pooled["wins"] == expected["wins"]
    assert pooled["win_rate"] == pytest.approx(expected["win_rate"], abs=1e-9)
    assert pooled["expectancy"] == pytest.approx(expected["expectancy"],
                                                abs=1e-9)
    assert pooled["pf"] == pytest.approx(expected["pf"], abs=1e-6)
    assert pooled["edge_bps"] == pytest.approx(expected["edge_bps"], abs=0.05)
    gap = _netting(members)
    assert gap == fixture["expected_netting"]
    # The slice has real conflicts: the live net book would NOT hold
    # 8.24% of the judged union's position-days.
    assert gap["cancelled_pct"] == pytest.approx(8.24, abs=0.01)
    assert gap["conflict_pct"] == pytest.approx(5.48, abs=0.01)
    assert gap["live_trade_entries_approx"] == 154


# ---------------------------------------------------------------------------
# 9. Registry context passing
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def registry():
    from strategies.strategy_registry import UnifiedStrategyRegistry

    return UnifiedStrategyRegistry()


def test_registry_detects_context_aware_books(registry):
    for key in BOOK_KEYS:
        module = "strategy_" + key
        assert registry._accepts_context.get(module) is True, module
        spec = registry.get(module)
        assert spec is not None, module
        assert spec.status == "FORWARD_TEST", module
    # Classic single-argument modules are called exactly as before.
    assert registry._accepts_context.get("strategy_shock_breakout") is False


def test_registry_book_specs_carry_lane_universe(registry):
    from config_strategy import CRYPTO30_SYMBOLS, FOREX28_SYMBOLS

    for key in ("ensemble_book_3905", "ensemble_book_3906",
                "ensemble_book_3933", "ensemble_book_3900"):
        spec = registry.get("strategy_" + key)
        assert tuple(spec.symbols) == tuple(CRYPTO30_SYMBOLS), key
        assert spec.timeframes == ("1d",), key
    for key in ("ensemble_book_3927", "ensemble_book_3928",
                "ensemble_book_3929"):
        spec = registry.get("strategy_" + key)
        assert tuple(spec.symbols) == tuple(
            CRYPTO30_SYMBOLS + FOREX28_SYMBOLS), key
    spec = registry.get("strategy_ensemble_book_3978")
    assert set(spec.timeframes) == {"1d", "1wk"}


def test_execute_strategy_refusal_raises_once_then_quiet(registry):
    # NOTE: this is the only test that calls THIS thin book module's
    # get_signal, so the first call is genuinely the first evaluation
    # of ensemble_book_3933 in this process. Book 3933 still refuses
    # (its xs_lowvol member is declared module=None). Before lane 4
    # this test targeted book 3905; 3905's members have since landed
    # and it now evaluates -- see
    # test_execute_strategy_evaluates_landed_book.
    registry.set_demo_venues({"binance_futures", "oanda"})
    try:
        first = registry.execute_strategy(
            "strategy_ensemble_book_3933", _frame(), "1d", "BTCUSDT",
            venue="binance_futures",
        )
        assert first["status"] == "ERROR", first
        assert "xs_lowvol" in first["error"], first
        second = registry.execute_strategy(
            "strategy_ensemble_book_3933", _frame(), "1d", "BTCUSDT",
            venue="binance_futures",
        )
        assert second["status"] == "NO_SIGNAL", second
    finally:
        registry.set_demo_venues(set())


def test_execute_strategy_evaluates_landed_book(registry):
    # Book 3905's members landed in lane 4 (#996 shock k1.5, #987
    # donchian): through the daemon's own execute path it now
    # evaluates -- NO_SIGNAL on the flat fixture on every call, never
    # the refusal ERROR this suite pinned for it before the merge.
    registry.set_demo_venues({"binance_futures", "oanda"})
    try:
        for _ in range(2):
            out = registry.execute_strategy(
                "strategy_ensemble_book_3905", _frame(), "1d", "BTCUSDT",
                venue="binance_futures",
            )
            assert out["status"] == "NO_SIGNAL", out
    finally:
        registry.set_demo_venues(set())


# ---------------------------------------------------------------------------
# 10. Daemon wiring
# ---------------------------------------------------------------------------

def _daemon_bare():
    from autonomy.run_daemon import StratexTradingEngine

    return StratexTradingEngine.__new__(StratexTradingEngine)


def test_daemon_forward_protocol_entries_cover_books():
    daemon = _daemon_bare()
    entries = daemon._forward_protocol_entries()
    for key in BOOK_KEYS:
        assert "strategy_" + key in entries, key
    assert "strategy_tsmom2_dual" not in entries


def test_daemon_lane_tag_mapping_for_books():
    daemon = _daemon_bare()
    for key in BOOK_KEYS:
        assert daemon._lane_for_strategy("strategy_" + key) == "FORWARD_TEST", key
    assert daemon._lane_for_strategy("strategy_ichimoku_trend") is None
