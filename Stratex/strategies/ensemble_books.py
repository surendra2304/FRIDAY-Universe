"""Canonical ensemble-book definitions — TASK-STR-EXP-002 (slice 2).

The single source of truth for the 8 books wired in this slice: the 7
PROVEN RD-025 books (trials 3905, 3906, 3927, 3928, 3929, 3933, 3978)
plus the self-experiment loop's first-light book (loop trial 3900).
Every figure below is the judged pooled figure, recomputed offline from
the saved RD-002 trade lists (~/workspace/str-slice2/verify_books.py):
trades / expectancy / PF match the recorded RD-025 rows exactly
(3900 matches the loop's recorded PF 1.2643).

Per-book execution state (what still blocks the book from trading):
  * 3905, 3906, 3927, 3928, 3929: every member module is in flight in
    an open wave-2 PR; the book refuses until those PRs merge AND the
    book module is appended to S1's STRATEX_STRATEGY_ALLOWLIST at deploy.
  * 3900: same, for its three members (shock k1.0 is already on main).
  * 3933: blocked on xs_lowvol — a cross-sectional rotation, not a
    per-symbol signal strategy (see XSL below); plus the wave-2 PRs.
  * 3978: blocked on four members — DUAL 1d (no standalone module;
    PR #991 built the 4h cell only), SHW (no 1wk module), ZSC (no
    module), XSL (cross-sectional) — plus HA1d's wave-2 PR #993.

Stop-cap overrides (FWD-012 method, measured 2026-11-18 from the judged
signal bars via the harness fns, production Wilder ATR(14); see
~/workspace/str-slice2/capcheck_books.json):
  * 0.50 for books whose members' judged stops top out at ~36%
    (3905, 3906, 3928, 3929) — the wave-1 value for the same 1d universe.
  * 0.60 for books containing vol_adaptive (3927, 3933, 3900): its
    judged stops reach 49.22% (50.14% of its signals above the 0.15 env
    cap) — 0.50 would leave a 0.78pp margin and reject future tail
    signals; 0.60 covers the measured distribution with headroom.
  * 0.90 for 3978: its weekly member (shock k1.0 @ 1wk) has judged stops
    to 87.16% (94.97% of its 199 signals above the cap; median 28.18%).
    0.90 is the sleeve precedent for weekly geometry.
  * STO-forex (max 20.03%, 0.02% of signals above cap) and ZSC (max
    6.94%, none above cap) need no override on their own; the book-level
    override covers the book because its bracket comes from whichever
    member signals (mostly crypto 1d).

XSL (xs_lowvol lv20_r10): a CROSS-SECTIONAL rotation — rank all 30
symbols by 20d volatility, hold the 3 lowest, rebalance every 10 bars
(families3.py xs_lowvol_fn; bracket SL 2.0 / TP 4.0, max_bars 10). It is
NOT a per-symbol signal strategy and cannot be a member of a per-symbol
ensemble book without xs rotation machinery. It is therefore declared
with module=None: the engine refuses any book containing it (whole
book, never a subset) until that machinery is built. Its trades ARE in
the judged pooled figures (510 trades, 275 wins) — the entry reasons
say so.
"""

from __future__ import annotations

from config_strategy import CRYPTO30_SYMBOLS, FOREX28_SYMBOLS
from strategies.ensemble_book import Book, Member

CRYPTO = tuple(CRYPTO30_SYMBOLS)
FOREX = tuple(FOREX28_SYMBOLS)


def _m(module, key, cell, panel, timeframe, sl_atr, tp_atr, reason=""):
    return Member(
        module=module,
        key=key,
        cell=cell,
        panel=panel,
        timeframe=timeframe,
        venue="binance_futures" if panel == "crypto30" else "oanda",
        sl_atr=sl_atr,
        tp_atr=tp_atr,
        universe=CRYPTO if panel == "crypto30" else FOREX,
        unavailable_reason=reason,
    )


VA = _m("strategy_vol_adaptive_trend", "vol_adaptive_trend",
        "ema12_26_nogate", "crypto30", "1d", 2.5, 5.0)
DON = _m("strategy_donchian_turtle", "donchian_turtle",
         "n55_b26", "crypto30", "1d", 2.0, 6.0)
TSM = _m("strategy_ts_momentum", "ts_momentum",
         "roc72", "crypto30", "1d", 2.0, 4.0)
SHK15 = _m("strategy_shock_breakout_k15", "shock_breakout",
           "k1.5", "crypto30", "1d", 2.0, 4.0)
SHK10 = _m("strategy_shock_breakout", "shock_breakout",
           "k1.0", "crypto30", "1d", 2.0, 4.0)
STO_FX = _m("strategy_stoch_reversion", "stoch_reversion",
            "k14_raw", "forex28", "1d", 2.0, 4.0)
STO_CRYPTO = _m("strategy_stoch_reversion_crypto", "stoch_reversion",
                "k14_raw", "crypto30", "1d", 2.0, 4.0)
DUAL_1D = _m("strategy_tsmom2_dual_crypto_1d", "tsmom2_dual",
            "roc90_ema200", "crypto30", "1d", 2.5, 5.0)
SHW = _m("strategy_shock_breakout_1wk", "shock_breakout",
         "k1.0", "crypto30", "1wk", 2.0, 4.0)
ZSC = _m("strategy_zscore_reversion", "zscore_reversion",
         "w50_t2.5_filt", "forex28", "1d", 2.0, 2.0)
HA1D = _m("strategy_ha_trend", "ha_trend",
          "two_candle", "crypto30", "1d", 2.0, 4.0)
XSL = _m(None, "xs_lowvol", "lv20_r10", "crypto30", "1d", 2.0, 4.0,
         reason="xs_lowvol is a cross-sectional rotation (rank 30 symbols "
         "by 20d vol, hold 3 lowest, rebalance every 10 bars), not a "
         "per-symbol signal strategy; it cannot be a member of a "
         "per-symbol ensemble book without xs rotation machinery")

BOOKS: dict[str, Book] = {
    "ensemble_book_3905": Book(
        key="ensemble_book_3905", trial=3905, verdict="PROVEN",
        source="RD-025", members=(SHK15, DON),
        trades=784, expectancy=0.019383, pf=1.4548, win_rate=0.3839,
        edge_bps=193.8, folds="4/5", max_stop_pct=0.50,
        execution="PENDING_WAVE_PR_MERGE: #996 (shock k1.5), #987 (donchian)",
    ),
    "ensemble_book_3906": Book(
        key="ensemble_book_3906", trial=3906, verdict="PROVEN",
        source="RD-025", members=(SHK15, TSM),
        trades=820, expectancy=0.017244, pf=1.4333, win_rate=0.4122,
        edge_bps=172.4, folds="4/5", max_stop_pct=0.50,
        execution="PENDING_WAVE_PR_MERGE: #996 (shock k1.5), #991 (ts_momentum)",
    ),
    "ensemble_book_3927": Book(
        key="ensemble_book_3927", trial=3927, verdict="PROVEN",
        source="RD-025", members=(VA, SHK15, STO_FX),
        trades=1150, expectancy=0.009665, pf=1.4639, win_rate=0.4096,
        edge_bps=96.7, folds="4/5", max_stop_pct=0.60,
        execution="PENDING_WAVE_PR_MERGE: #983 (vol_adaptive), #996 (shock k1.5), "
        "#994 (stoch_reversion)",
    ),
    "ensemble_book_3928": Book(
        key="ensemble_book_3928", trial=3928, verdict="PROVEN",
        source="RD-025", members=(DON, SHK15, STO_FX),
        trades=1149, expectancy=0.009120, pf=1.4440, win_rate=0.3847,
        edge_bps=91.2, folds="4/5", max_stop_pct=0.50,
        execution="PENDING_WAVE_PR_MERGE: #987 (donchian), #996 (shock k1.5), "
        "#994 (stoch_reversion)",
    ),
    "ensemble_book_3929": Book(
        key="ensemble_book_3929", trial=3929, verdict="PROVEN",
        source="RD-025", members=(TSM, SHK15, STO_FX),
        trades=1185, expectancy=0.008249, pf=1.4235, win_rate=0.4042,
        edge_bps=82.5, folds="4/5", max_stop_pct=0.50,
        execution="PENDING_WAVE_PR_MERGE: #991 (ts_momentum), #996 (shock k1.5), "
        "#994 (stoch_reversion)",
    ),
    "ensemble_book_3933": Book(
        key="ensemble_book_3933", trial=3933, verdict="PROVEN",
        source="RD-025", members=(VA, SHK15, XSL),
        trades=1295, expectancy=0.009253, pf=1.4072, win_rate=0.4672,
        edge_bps=92.5, folds="4/5", max_stop_pct=0.60,
        execution="PENDING_XS_ROTATION_MACHINERY: xs_lowvol (cross-sectional; "
        "not a per-symbol member) + PENDING_WAVE_PR_MERGE: #983 (vol_adaptive), "
        "#996 (shock k1.5)",
    ),
    "ensemble_book_3978": Book(
        key="ensemble_book_3978", trial=3978, verdict="PROVEN",
        source="RD-025", members=(DUAL_1D, SHW, ZSC, HA1D, XSL),
        trades=1698, expectancy=0.004728, pf=1.3262, win_rate=0.4441,
        edge_bps=47.3, folds="4/5", max_stop_pct=0.90,
        execution="PENDING_MEMBER_MODULES: strategy_tsmom2_dual_crypto_1d "
        "(DUAL 1d cell; PR #991 built the 4h cell only), "
        "strategy_shock_breakout_1wk (SHW), strategy_zscore_reversion (ZSC) + "
        "PENDING_XS_ROTATION_MACHINERY: xs_lowvol + PENDING_WAVE_PR_MERGE: "
        "#993 (ha_trend)",
    ),
    "ensemble_book_3900": Book(
        key="ensemble_book_3900", trial=3900, verdict="PROVEN",
        source="LOOP", members=(VA, SHK10, STO_CRYPTO),
        trades=1719, expectancy=0.008131, pf=1.2643, win_rate=0.3921,
        edge_bps=81.3, folds="4/5", max_stop_pct=0.60,
        execution="PENDING_WAVE_PR_MERGE: #983 (vol_adaptive), #994 "
        "(stoch_reversion crypto variant); shock k1.0 is on main",
    ),
}
