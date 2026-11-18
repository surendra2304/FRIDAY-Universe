"""
config_strategy.py — Non-secret, version-controlled strategy configuration.

This file contains ONLY non-sensitive strategy parameters.
It is safe to commit to version control.

Secrets (API_KEY, SECRET_KEY) MUST remain in .env / environment variables.
Runtime mode (TRADING_MODE) remains in config.py / environment.
"""

from typing import Any


# ==============================================================================
# ADX + EMA TREND FOLLOWING STRATEGY (OBSERVE ONLY)
# Historical result files are present, but the source candle dataset is absent
# from this checkout. Treat the recorded metrics as unverified until the exact
# inputs and provenance are restored and the study is reproduced.
# ==============================================================================

ADX_EMA_STRATEGY = {
    # ---- Timeframe ----
    "TIMEFRAME":              "4h",

    # ---- Indicator periods ----
    "EMA_FAST_PERIOD":        20,
    "EMA_SLOW_PERIOD":        50,
    "EMA_DIRECTION_PERIOD":   200,
    "ADX_PERIOD":             14,
    "ATR_PERIOD":             14,

    # ---- Signal thresholds ----
    "ADX_THRESHOLD":          25,       # Minimum ADX for trend strength

    # ---- Trade sizing ----
    "SL_ATR_MULTIPLIER":      2.0,      # Stop = 2×ATR below/above entry
    "TP_ATR_MULTIPLIER":      3.0,      # Target = 3×ATR above/below entry
    "RISK_REWARD_RATIO":      1.5,      # TP/SL ratio (3 / 2)

    # Unverified historical values are deliberately unavailable to runtime gates.
    "OOS_WIN_RATE_PRIOR":     None,
    "OOS_PROFIT_FACTOR":      None,
    "OOS_EXPECTANCY_PER_TRADE": None,
    "OOS_MAX_DRAWDOWN_PCT":   None,
    "OOS_VALIDATED_ASSETS":   [],
    "OOS_VALIDATION_STATUS":  "UNVERIFIED",
}

# ==============================================================================
# ADX + EMA V2 — OBSERVE-ONLY CANDIDATE (2026-08-22, rev 3)
# The strategy parameters below are retained so the candidate can be inspected.
# Historical comments and reports made OOS performance claims, but the source
# OHLCV inputs are absent. The checked-in walk-forward report has only 34
# frozen-config trades in its 2024–2026 fold and labels selection FRAGILE.
# Treat all old OOS statistics as unverified; they are not runtime priors.
# ==============================================================================

ADX_EMA_STRATEGY_V2 = {
    "TIMEFRAME":              "4h",
    "EMA_FAST_PERIOD":        20,
    "EMA_SLOW_PERIOD":        50,
    "EMA_DIRECTION_PERIOD":   200,
    "ADX_PERIOD":             14,
    "ATR_PERIOD":             14,
    "ADX_THRESHOLD":          20,
    "SL_ATR_MULTIPLIER":      3.0,
    "TP_ATR_MULTIPLIER":      3.0,
    "RISK_REWARD_RATIO":      1.0,
    "ENABLE_PULLBACK_ENTRY":  False,   # net-negative 2021-2026 — do not re-enable without new OOS proof
    "ENABLE_RETEST_ENTRY":    True,    # rev 3: first EMA20 touch within 10 bars after qualified cross
    "RETEST_WINDOW_BARS":     10,
    "BTC_REGIME_FILTER":      True,    # BUY only when BTCUSDT 4h close > EMA200
    "OOS_WIN_RATE_PRIOR":     None,
    "OOS_PROFIT_FACTOR":      None,
    "OOS_TRADE_COUNT":        None,
    "OOS_EXPECTANCY_PER_TRADE": None,
    "OOS_MAX_DRAWDOWN_PCT":   None,
    "OOS_VALIDATED_ASSETS":   [],
    "OOS_VALIDATION_STATUS":  "UNVERIFIED",
    "SUPERSEDES":             "ADX_EMA_STRATEGY (V1)",
}

# ==============================================================================
# BACKTESTING ASSUMPTIONS (shared across all strategies)
# Must match live execution assumptions for benchmark fidelity.
# ==============================================================================

BACKTEST_ASSUMPTIONS = {
    "FEE_RATE":               0.001,    # 0.1% per side (Binance Spot taker)
    "SLIPPAGE_RATE":          0.0005,   # 0.05% per side
    "STARTING_BALANCE":       10000.0,
    "EXECUTION_MODEL":        "next_candle_open",  # No same-candle entry
    "INTRABAR_RESOLUTION":    "conservative",
}

# ==============================================================================
# TESTNET RISK LIMITS
# ==============================================================================

TESTNET_RISK = {
    "MAX_RISK_PER_TRADE":     0.005,    # 0.5% of equity
    "MAX_TOTAL_EXPOSURE":     0.05,     # 5% total exposure
    "MAX_SINGLE_ASSET":       0.02,     # 2% per asset
    "MAX_DIRECTIONAL_NET":    0.04,     # 4% net directional
    "MAX_OPEN_POSITIONS":     5,
    "MAX_DAILY_LOSS_PCT":     0.02,
    "MAX_DRAWDOWN_PCT":       0.05,
    "MINIMUM_EXPECTED_EDGE":  0.0005,   # 0.05% min net edge at gate
}

# ==============================================================================
# TASK-STR-FWD-002 (2026-11-15): phase-3 forward entrants.
# The two TASK-STR-RD-002 winners, approved for governed DEMO trading by
# the owner 2026-11-15. The parameter sets below ARE the judged
# configurations (rigorous_backtest/rd2) — the production modules
# strategy_ichimoku_trend.py / strategy_dow_effect.py read them from
# here, and tests/test_fwd002_forward_strategies.py proves the modules
# reproduce the judged harness entry-for-entry on real historical data.
#
# TASK-STR-FWD-006 AMENDMENT (2026-11-15): the phase-3 SIZING package
# was settled by TASK-STR-RD-011 and the coordinator's decision (owner
# mandate: all risk parameters are the coordinator's to set). The
# written "1% risk cap" the entrants launched with was arithmetically
# inconsistent with the 5% drawdown kill on pooled multi-symbol books
# (RD-011: 1% x concurrency 11.9-21.3 = 12-21% heat; the kill tripped
# on day 2-4 of the judged OOS streams). The decided package — stated
# in full in Stratex/docs/PHASE3_FORWARD_PROTOCOL.md and carried in
# each governed entry below as risk_per_trade_pct / max_heat_pct — is:
# 0.1% per-trade risk on VENUE equity, 2% aggregate heat cap per
# strategy, 5% mark-to-market drawdown kill on venue equity evaluated
# on the scan cadence, 3% daily breaker (pause, not kill), leverage
# pinned at 3x, performance kills unchanged. Vol-targeting is BANNED
# for dow_effect.
# ==============================================================================

# The judged CRYPTO30 panel (rigorous_backtest/rd2/panels.py CRYPTO30).
CRYPTO30_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "LTCUSDT", "LINKUSDT", "DOTUSDT", "TRXUSDT", "AVAXUSDT",
    "NEARUSDT", "ATOMUSDT", "UNIUSDT", "ETCUSDT", "BCHUSDT", "FILUSDT",
    "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT", "XLMUSDT",
    "HBARUSDT", "ALGOUSDT", "VETUSDT", "SANDUSDT", "MANAUSDT", "AAVEUSDT",
]

ICHIMOKU_TREND_STRATEGY = {
    "NAME": "Ichimoku Trend (TK cross + cloud filter)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-002)",
    "TIMEFRAME": "4h",
    "TENKAN_PERIOD": 9,
    "KIJUN_PERIOD": 26,
    "SENKOU_B_PERIOD": 52,
    "CLOUD_SHIFT": 26,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("4h")
    # TASK-STR-RD-002 pooled OOS evidence (2,302 trades, 26/30 breadth):
    "OOS_WIN_RATE": 0.4010,
    "OOS_PROFIT_FACTOR": 1.278,
    "OOS_EXPECTANCY_PCT": 0.894,
}

ICHIMOKU_TREND_1D_STRATEGY = {
    "NAME": "Ichimoku Trend 1d (TK cross + cloud filter) — FORWARD_TEST wave 1",
    "VERSION": "v1.0.0 (TASK-STR-FWD-018)",
    "TIMEFRAME": "1d",
    "TENKAN_PERIOD": 9,
    "KIJUN_PERIOD": 26,
    "SENKOU_B_PERIOD": 52,
    "CLOUD_SHIFT": 26,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (grid_rows pooled_oos:
    # ichimoku_trend__tk_cloud__crypto30__1d — 398 trades, 4/5
    # folds; near-miss re-audit 2026-11-18, second-tier admission):
    "OOS_WIN_RATE": 0.3970,
    "OOS_PROFIT_FACTOR": 1.367,
    "OOS_EXPECTANCY_PCT": 3.013,
}

ICHIMOKU_TREND_RAW_STRATEGY = {
    "NAME": "Ichimoku Trend Raw 4h (TK cross, NO cloud filter) — FORWARD_TEST wave 1",
    "VERSION": "v1.0.0 (TASK-STR-FWD-018)",
    "TIMEFRAME": "4h",
    "TENKAN_PERIOD": 9,
    "KIJUN_PERIOD": 26,
    "SENKOU_B_PERIOD": 52,
    "CLOUD_SHIFT": 26,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("4h")
    # TASK-STR-RD-002 pooled OOS evidence (grid_rows pooled_oos:
    # ichimoku_trend__tk_raw__crypto30__4h — 3,630 trades, 3/5
    # folds; near-miss re-audit 2026-11-18, second-tier admission):
    "OOS_WIN_RATE": 0.3741,
    "OOS_PROFIT_FACTOR": 1.114,
    "OOS_EXPECTANCY_PCT": 0.411,
}

DOW_EFFECT_STRATEGY = {
    "NAME": "Dow Effect (Monday reversal of trailing 5-day move)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-002)",
    "TIMEFRAME": "1d",
    "ROC_LOOKBACK": 5,
    "ENTRY_WEEKDAY": 0,     # Monday, UTC bar open
    "ATR_PERIOD": 14,
    "SL_ATR": 3.0,          # judged bracket_time spec (families2)
    "TP_ATR": 6.0,          # judged bracket_time spec (families2)
    "MAX_BARS": 5,          # judged bracket_time max_bars (time exit)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (3,660 trades, 27/30 breadth):
    "OOS_WIN_RATE": 0.5227,
    "OOS_PROFIT_FACTOR": 1.257,
    "OOS_EXPECTANCY_PCT": 0.878,
}

# ==============================================================================
# TASK-STR-FWD-002 sleeve extension (2026-11-15): the RD-002 Stage-C
# best-per-class portfolio sleeve, approved by the owner as third forward
# entrant (~11:46 IST). Judged set (synthesis.json stage_c, EQUAL weight,
# +18.8% compounded / -11.5% max DD in-window, mean corr 0.01):
#   shock_breakout/k1.0 @ crypto30 1wk          -> Binance daemon (BELOW)
#   tsmom2_dual/roc90_ema200 @ forex28 1d       -> OANDA sleeve runner
#   vol_adaptive_trend/ema20_50_gate @ comm7 4h -> EXCLUDED (see registry)
#   keltner_breakout/ema20_m2.0 @ idx7 1d       -> EXCLUDED (see registry)
# Venue fidelity verified live 2026-11-15: the OANDA practice account
# holds exactly 68 instruments, ALL currency pairs (all 28 FOREX28
# available; ZERO commodity or index instruments). The traded sleeve is
# therefore a REDUCED 2-of-4-leg sleeve (crypto + forex; the two kept
# legs' in-window pairwise correlation was -0.0006) and is named as such
# everywhere. It is judged on compounded equity + max drawdown ONLY;
# its kill rule is the sleeve-level drawdown rule in
# measurement/forward_guard.py (DD > 5% of equity from the sleeve's
# forward peak -> auto-pause ALL sleeve components).
# ==============================================================================

SLEEVE_NAME = "best_per_class"

SLEEVE_SHOCK_BREAKOUT_STRATEGY = {
    "NAME": "Sleeve leg: Shock Breakout (k=1.0 ATR shock, weekly)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-002 sleeve)",
    "TIMEFRAME": "1wk",
    "SHOCK_K": 1.0,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 104,     # judged warmup_for("1wk")
    # Ranked-table cell (NOT a bar passer alone: 109 OOS trades, 3/5
    # folds — it enters as a portfolio component, judged on the sleeve):
    "OOS_TRADES": 109,
    "OOS_PROFIT_FACTOR": 1.575,
    "OOS_EXPECTANCY_PCT": 9.04,
    # Win rate computed by the FWD-002 crew running the judged pipeline
    # (sig_shock + BR24 + fastsim, crypto costs) over the full RD-002
    # cache series, all 30 symbols: 150 simulated trades, WR 0.4267.
    # Used ONLY as the daemon expectancy-gate prior.
    "OOS_WIN_RATE": 0.4267,
}

WF_SELECT_TSMOM_STRATEGY = {
    "NAME": "WF-Select ts_momentum (walk-forward selection procedure, CRYPTO30 1d)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-022)",
    "PROCEDURE": "ts_momentum__crypto30__1d",
    "TIMEFRAME": "1d",
    "SL_ATR": 2.0,          # judged bracket BR24
    "TP_ATR": 4.0,          # judged bracket BR24
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 walk-forward selection record (wf_select_judge:
    # expanding in-sample window, rank by PF then win rate, top 1;
    # pooled over the picks roc24/roc168/roc72/roc42/roc42):
    "OOS_WIN_RATE": 0.3664,
    "OOS_PROFIT_FACTOR": 1.1694,
    "OOS_EXPECTANCY_PCT": 1.4096,
}

SLEEVE_TSMOM2_DUAL_STRATEGY = {
    "NAME": "Sleeve leg: Dual Momentum (ROC90 zero-cross + EMA200 filter)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-002 sleeve)",
    "TIMEFRAME": "1d",
    "ROC_LOOKBACK": 90,
    "TREND_EMA": 200,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.5,          # judged bracket (families2 tsmom2_dual)
    "TP_ATR": 5.0,          # judged bracket (families2 tsmom2_dual)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # Ranked-table cell (portfolio component; sleeve-judged):
    "OOS_TRADES": 127,
    "OOS_PROFIT_FACTOR": 1.505,
    "OOS_EXPECTANCY_PCT": 0.62,
}

# Judged weekly-bar anchors: the RD-002 harness built weekly bars as
# 7-day buckets (panels._to_weekly: resample "7D", origin=start_day,
# buckets with all 7 daily bars) anchored at each symbol's judged 1d
# series start. Binance native weekly klines are Monday-anchored and
# are NOT the judged bars; the daemon rebuilds the judged buckets from
# daily bars using these per-symbol anchors (epoch seconds, UTC).
# Values = first bar of each symbol's RD-002 cache 1d series.
WEEKLY_BUCKET_ANCHORS = {
    "BTCUSDT": 1640995200, "ETHUSDT": 1640995200, "SOLUSDT": 1640995200,
    "BNBUSDT": 1640995200, "XRPUSDT": 1640995200, "DOGEUSDT": 1640995200,
    "ADAUSDT": 1640995200, "LTCUSDT": 1640995200, "LINKUSDT": 1640995200,
    "DOTUSDT": 1640995200, "TRXUSDT": 1640995200, "AVAXUSDT": 1640995200,
    "NEARUSDT": 1640995200, "ATOMUSDT": 1640995200, "UNIUSDT": 1640995200,
    "ETCUSDT": 1640995200, "BCHUSDT": 1640995200, "FILUSDT": 1640995200,
    "APTUSDT": 1666224000, "ARBUSDT": 1679616000, "OPUSDT": 1654128000,
    "INJUSDT": 1660780800, "SUIUSDT": 1683158400, "XLMUSDT": 1640995200,
    "HBARUSDT": 1640995200, "ALGOUSDT": 1640995200, "VETUSDT": 1640995200,
    "SANDUSDT": 1640995200, "MANAUSDT": 1640995200, "AAVEUSDT": 1640995200,
}

# The judged FOREX28 panel (rigorous_backtest/rd2/panels.py FOREX28) —
# all 28 verified present on the OANDA practice account 2026-11-15.
FOREX28_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD",
    "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "EURCHF", "AUDJPY",
    "CADJPY", "CHFJPY", "EURAUD", "EURNZD", "GBPAUD", "AUDNZD",
    "NZDJPY", "USDSEK", "USDNOK", "USDMXN", "USDZAR", "USDTRY",
    "USDCNH", "USDSGD", "USDHKD", "EURPLN",
]

# The judged FOREX12 panel (rigorous_backtest/rd2/panels.py FOREX12) —
# the 12 majors of FOREX28; every symbol is a member of FOREX28_SYMBOLS
# above (verified present on the OANDA practice account with it) and is
# exactly the costs2.py FX_MAJORS cost set (6 bps round trip).
FOREX12_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD",
    "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURCHF",
]

# The judged FOREX12 panel (rigorous_backtest/rd2/panels.py FOREX12) —
# the 12 majors of FOREX28; every symbol is a member of FOREX28_SYMBOLS
# above (verified present on the OANDA practice account with it) and is
# exactly the costs2.py FX_MAJORS cost set (6 bps round trip).
FOREX12_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD",
    "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURCHF",
]

# ==============================================================================
# TASK-STR-FWD-003 (2026-11-15): the FORWARD-TEST lane.
# Owner directive 2026-11-15 ~11:47 IST: "Create more and more strategies
# and test them in my demo account — no money will be lost on demo."
# TASK-STR-RD-002's four WATCHLIST configurations passed the mechanical
# bar (expectancy>0, PF>=1.2, >=200 OOS trades, >=80% folds, holdout)
# but failed Bonferroni multiple-testing significance at N=1,557. They
# were NOT promoted; instead they forward-test with real demo orders
# under a governance classification DISTINCT from the VALIDATED
# entrants: FORWARD_TEST — executable on DEMO venues only (fail-closed
# in strategies/strategy_registry.py; the daemon attests which venues
# are demo from the venue adapters' base URLs, and a FORWARD_TEST
# strategy can never execute without that attestation), same phase-3
# protections (decided sizing package, TASK-STR-FWD-006 —
# docs/PHASE3_FORWARD_PROTOCOL.md: 0.1% per-trade risk on venue
# equity, 2% heat cap per strategy, 3% daily breaker, kill criteria
# via measurement/forward_guard.py), and every fill tagged FORWARD_TEST in
# the Phase-2 ledger so scorecards never blend this lane with the
# passed entrants (ichimoku/dow/sleeve).
#
# HOW TO ADD A FUTURE LANE CANDIDATE (the reusable pattern — e.g.
# TASK-STR-RD-003 near-bar passers):
#   1. Port the judged signal logic line-faithfully into a production
#      module Stratex/strategy_<key>.py (get_signal +
#      entries_for_frame), parameters read from a <KEY>_STRATEGY dict
#      below whose values ARE the judged configuration.
#   2. Equivalence-test the module against the research harness on
#      fixed historical slices (the test_fwd002/test_fwd003 standard:
#      identical entry lists and bracket distances).
#   3. Add a registry entry below with status "FORWARD_TEST",
#      forward_protocol: True, forward_lane: "FORWARD_TEST",
#      lane_assets = the judged universe, and the RD evidence
#      (oos_win_rate_prior / expected_net_edge_bps from the judged
#      pooled OOS row — never invented).
#   4. Add the module name to STRATEX_STRATEGY_ALLOWLIST in the
#      Server-1 Stratex/.env at deploy time.
# A candidate whose judged universe cannot be traded faithfully on a
# demo venue is registered with lane_assets = [] and
# forward_protocol: False, its exclusion reason recorded, and NO
# module is written (see tsmom2_dual below) — never substituted.
#
# RD-003 ADDITIONS (2026-11-15, coordinator handoff from
# TASK-STR-RD-003, RESULTS_RD3.md merged via PR #294): four more comm7
# 1d cells join the lane as DOCUMENTARY registrations —
# vol_regime_switch/switch_a (151 OOS trades, +1.173%/trade, PF 1.372,
# 5 positive folds), vol_regime_switch/switch_b (124, +0.793%, PF
# 1.237, 5 folds), trend_pullback/pb_ema100 (113, +0.766%, PF 1.217,
# 3 folds) and trend_pullback/pb_ema200 (109, +0.642%, PF 1.182,
# 3 folds). Each failed ONLY the >=200-trade floor — a data-span
# limit of the Yahoo comm7 history, not a performance failure — and
# each carries the lane note "entered sample-starved; forward
# evidence is the settler". They share tsmom2_dual's exclusion: the
# judged comm7 universe (Yahoo continuous futures GOLD/SILVER/WTI/
# BRENT/NATGAS/COPPER/PLATINUM) cannot be traded faithfully on either
# demo venue (demo-fapi is crypto-only; the OANDA practice account
# holds 68 FX-only instruments, verified live 2026-11-15), so no
# module is written and nothing is substituted. RD-003 also confirmed
# tsmom2_dual @ comm7 4h as the programme's only "mechanical bar
# passed, significance pending" configuration, reproduced
# bit-identically, and recorded its 2x-cost PF of 1.149 — below the
# 1.2 sensitivity line — as COST-FRAGILE in its registry entry below.
# ==============================================================================

BOLLINGER_TREND_STRATEGY = {
    "NAME": "Bollinger Trend (close crosses SMA(50) +/- 2.0 sd band)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-003)",
    "TIMEFRAME": "1d",
    "SMA_PERIOD": 50,
    "SD_MULT": 2.0,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (420 trades, 5/5 folds,
    # Bonferroni FAIL — watchlist, not a promotion):
    "OOS_WIN_RATE": 0.3929,
    "OOS_PROFIT_FACTOR": 1.456,
    "OOS_EXPECTANCY_PCT": 3.545,
}

BOLLINGER_TREND_4H_STRATEGY = {
    "NAME": "Bollinger Trend 4h (close crosses SMA(50) +/- 2.0 sd band) — FORWARD_TEST wave 1",
    "VERSION": "v1.0.0 (TASK-STR-FWD-018)",
    "TIMEFRAME": "4h",
    "SMA_PERIOD": 50,
    "SD_MULT": 2.0,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("4h")
    # TASK-STR-RD-002 pooled OOS evidence (grid_rows pooled_oos:
    # bollinger_trend__p50_sd2.0__crypto30__4h — 3,211 trades, 4/5
    # folds; near-miss re-audit 2026-11-18, second-tier admission):
    "OOS_WIN_RATE": 0.3759,
    "OOS_PROFIT_FACTOR": 1.137,
    "OOS_EXPECTANCY_PCT": 0.465,
}

BOLLINGER_TREND_P20_STRATEGY = {
    "NAME": "Bollinger Trend p20 (close crosses SMA(20) +/- 2.0 sd band) — FORWARD_TEST wave 1",
    "VERSION": "v1.0.0 (TASK-STR-FWD-018)",
    "TIMEFRAME": "1d",
    "SMA_PERIOD": 20,
    "SD_MULT": 2.0,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (grid_rows pooled_oos:
    # bollinger_trend__p20_sd2.0__crypto30__1d — 632 trades, 3/5
    # folds; near-miss re-audit 2026-11-18, second-tier admission):
    "OOS_WIN_RATE": 0.3513,
    "OOS_PROFIT_FACTOR": 1.147,
    "OOS_EXPECTANCY_PCT": 1.265,
}

SHOCK_BREAKOUT_STRATEGY = {
    "NAME": "Shock Breakout (one-bar close move > 1.0 x ATR(14))",
    "VERSION": "v1.0.0 (TASK-STR-FWD-003)",
    "TIMEFRAME": "1d",
    "SHOCK_K": 1.0,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (732 trades, 4/5 folds,
    # Bonferroni FAIL — watchlist, not a promotion):
    "OOS_WIN_RATE": 0.3893,
    "OOS_PROFIT_FACTOR": 1.318,
    "OOS_EXPECTANCY_PCT": 2.696,
}

SHOCK_BREAKOUT_K15_STRATEGY = {
    "NAME": "Shock Breakout k1.5 (one-bar close move > 1.5 x ATR(14)) — FORWARD_TEST wave 1",
    "VERSION": "v1.0.0 (TASK-STR-FWD-018)",
    "TIMEFRAME": "1d",
    "SHOCK_K": 1.5,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (grid_rows pooled_oos:
    # shock_breakout__k1.5__crypto30__1d — 486 trades, 3/5 folds;
    # near-miss re-audit 2026-11-18, second-tier admission):
    "OOS_WIN_RATE": 0.4033,
    "OOS_PROFIT_FACTOR": 1.333,
    "OOS_EXPECTANCY_PCT": 2.811,
}

ADX_EMA_BARE_STRATEGY = {
    "NAME": "ADX+EMA Bare (production module signals, NO downstream filter)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-003)",
    "TIMEFRAME": "4h",
    "WINDOW": 500,          # judged gov2/module_eval sliding window
    "SL_ATR": 3.0,          # module bracket (ADX_EMA_STRATEGY_V2)
    "TP_ATR": 3.0,          # module bracket (ADX_EMA_STRATEGY_V2)
    "WARMUP_BARS": 260,     # judged WARMUP_BARS (module_eval)
    # TASK-STR-RD-002 pooled OOS evidence for the BARE configuration
    # (837 trades, 4/5 folds, holdout expectancy +0.9428%,
    # Bonferroni FAIL — watchlist, not a promotion):
    "OOS_WIN_RATE": 0.5699,
    "OOS_PROFIT_FACTOR": 1.233,
    "OOS_EXPECTANCY_PCT": 0.796,
}

TSMOM2_DUAL_STRATEGY = {
    "NAME": "Dual Momentum (ROC(30) sign cross + EMA(200) gate) — EXCLUDED, see registry",
    "VERSION": "v1.0.0 (TASK-STR-FWD-003)",
    "TIMEFRAME": "4h",
    "ROC_LOOKBACK": 30,
    "EMA_PERIOD": 200,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.5,          # judged bracket (families2 build_configs)
    "TP_ATR": 5.0,          # judged bracket (families2 build_configs)
    "WARMUP_BARS": 260,     # judged warmup_for("4h")
    # TASK-STR-RD-002 pooled OOS evidence (205 trades, 4/5 folds,
    # Bonferroni FAIL — watchlist, not a promotion):
    "OOS_WIN_RATE": 0.3951,
    "OOS_PROFIT_FACTOR": 1.203,
    "OOS_EXPECTANCY_PCT": 0.558,
}

# TASK-STR-RD-003 comm7 1d near-miss cells (RESULTS_RD3.md SS2/SS3/SS5
# watchlist). Documentary only — no production module exists for these
# entries (judged universe unmappable on the demo venues; see the
# registry reasons). Win rates were not published for these cells, so
# no win-rate figure is recorded — never invented.
VOL_REGIME_SWITCH_A_STRATEGY = {
    "NAME": "Vol-Regime Switch A @ comm7 1d — EXCLUDED (unmappable), see registry",
    "VERSION": "v1.0.0 (TASK-STR-FWD-003 RD-003 additions)",
    "TIMEFRAME": "1d",
    "OOS_TRADES": 151,
    "OOS_PROFIT_FACTOR": 1.372,
    "OOS_EXPECTANCY_PCT": 1.173,
    "OOS_POSITIVE_FOLDS": 5,
}

VOL_REGIME_SWITCH_B_STRATEGY = {
    "NAME": "Vol-Regime Switch B @ comm7 1d — EXCLUDED (unmappable), see registry",
    "VERSION": "v1.0.0 (TASK-STR-FWD-003 RD-003 additions)",
    "TIMEFRAME": "1d",
    "OOS_TRADES": 124,
    "OOS_PROFIT_FACTOR": 1.237,
    "OOS_EXPECTANCY_PCT": 0.793,
    "OOS_POSITIVE_FOLDS": 5,
}

TREND_PULLBACK_EMA100_STRATEGY = {
    "NAME": "Trend Pullback EMA100 @ comm7 1d — EXCLUDED (unmappable), see registry",
    "VERSION": "v1.0.0 (TASK-STR-FWD-003 RD-003 additions)",
    "TIMEFRAME": "1d",
    "OOS_TRADES": 113,
    "OOS_PROFIT_FACTOR": 1.217,
    "OOS_EXPECTANCY_PCT": 0.766,
    "OOS_POSITIVE_FOLDS": 3,
}

TREND_PULLBACK_EMA200_STRATEGY = {
    "NAME": "Trend Pullback EMA200 @ comm7 1d — EXCLUDED (unmappable), see registry",
    "VERSION": "v1.0.0 (TASK-STR-FWD-003 RD-003 additions)",
    "TIMEFRAME": "1d",
    "OOS_TRADES": 109,
    "OOS_PROFIT_FACTOR": 1.182,
    "OOS_EXPECTANCY_PCT": 0.642,
    "OOS_POSITIVE_FOLDS": 3,
}

# ==============================================================================
# TASK-STR-FWD-019 WAVE-2 gap-fill (2026-11-18): the two ts_momentum
# FOREX cells missed by the original slice plan (near-miss audit
# REPORT.md §1.4 rows 30 and 68; §3 forex group). Both were judged by
# RD-002's rigorous_backtest/rd2/families2.py sig_ts_momentum under the
# BR24 bracket recorded in each cell's own grid row (spec sl_atr 2.0 /
# tp_atr 4.0), warmup 260 bars (families2 WARMUP / warmup_for). The
# lane modules are SELF-CONTAINED ports of that harness function —
# Crew A's crypto30 ts_momentum modules (PR #991) are not merged at
# this base and are not imported.
# ==============================================================================

TS_MOMENTUM_ROC72_FX28_STRATEGY = {
    "NAME": "TS Momentum ROC(72) zero-cross — FOREX28",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "ROC_LOOKBACK": 72,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (cell grid-row spec)
    "TP_ATR": 4.0,          # judged bracket BR24 (cell grid-row spec)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (226 trades, 3/5 folds,
    # PF @2x costs 1.0944, Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3673,
    "OOS_PROFIT_FACTOR": 1.1735,
    "OOS_EXPECTANCY_PCT": 0.185,
}

TS_MOMENTUM_ROC24_FX12_STRATEGY = {
    "NAME": "TS Momentum ROC(24) zero-cross — FOREX12",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "ROC_LOOKBACK": 24,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (cell grid-row spec)
    "TP_ATR": 4.0,          # judged bracket BR24 (cell grid-row spec)
    "WARMUP_BARS": 260,     # judged warmup_for("4h")
    # TASK-STR-RD-002 pooled OOS evidence (715 trades, 2/5 folds,
    # Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3790,
    "OOS_PROFIT_FACTOR": 1.1001,
    "OOS_EXPECTANCY_PCT": 0.039,
}

# ==============================================================================
# TASK-STR-FWD-019 WAVE-2 (2026-11-18): governed forex12 cells + the
# bollinger p20 forex28 cell (near-miss audit REPORT.md §1.4). The
# governed cells were judged "as coded" from live modules via
# rigorous_backtest/rd2/gov2.py (bare configuration: module.add_features
# pipeline, get_signal on trailing <=500-bar windows, warmup 260 bars —
# module_eval WARMUP_BARS/WINDOW). Those live modules were deleted from
# main by TASK-STR-CLEANUP-001; the lane modules restore the judged code
# verbatim from the pre-cleanup blobs (see each module's docstring).
# ==============================================================================

FACTORY_WINNER_4_STRATEGY = {
    "NAME": "Factory Winner 4 Bare (MACD+BB confluence, judged live module)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "WINDOW": 500,          # judged gov2/module_eval sliding window
    "SL_ATR": 2.0,          # judged module bracket (get_signal_winner_4)
    "TP_ATR": 4.0,          # judged module bracket (get_signal_winner_4)
    "WARMUP_BARS": 260,     # judged WARMUP_BARS (module_eval)
    # TASK-STR-RD-002 pooled OOS evidence, forex12 4h cell (682 trades,
    # 3/5 folds, Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3856,
    "OOS_PROFIT_FACTOR": 1.1394,
    "OOS_EXPECTANCY_PCT": 0.0513,
}

FACTORY_WINNER_3_STRATEGY = {
    "NAME": "Factory Winner 3 Bare (MACD+BB confluence, judged live module)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "WINDOW": 500,          # judged gov2/module_eval sliding window
    "SL_ATR": 1.5,          # judged module bracket (get_signal_winner_3)
    "TP_ATR": 4.5,          # judged module bracket (get_signal_winner_3)
    "WARMUP_BARS": 260,     # judged WARMUP_BARS (module_eval)
    # TASK-STR-RD-002 pooled OOS evidence, forex12 4h cell (702 trades,
    # 2/5 folds, Bonferroni FAIL — near-miss, not a promotion).
    # factory_winner_5:bare @ forex12 4h is this stream's EXACT
    # duplicate (identical trades/PF/expectancy) — NOT separately wired.
    "OOS_WIN_RATE": 0.2863,
    "OOS_PROFIT_FACTOR": 1.0738,
    "OOS_EXPECTANCY_PCT": 0.0245,
}

BB_REVERSION_STRATEGY = {
    "NAME": "Bollinger Reversion Bare (BB(20,2) pierce-and-reenter, judged live module)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "WINDOW": 500,          # judged gov2/module_eval sliding window
    "SL_ATR": 1.5,          # judged module bracket (code constants)
    "TP_ATR": 3.0,          # judged module bracket (code constants)
    "WARMUP_BARS": 260,     # judged WARMUP_BARS (module_eval)
    # TASK-STR-RD-002 pooled OOS evidence, forex12 1d cell (308 trades,
    # 3/5 folds, Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3571,
    "OOS_PROFIT_FACTOR": 1.0911,
    "OOS_EXPECTANCY_PCT": 0.0730,
}

BOLLINGER_TREND_P20_FX28_STRATEGY = {
    "NAME": "Bollinger Trend p20 (close crosses SMA(20) +/- 2.0 sd band) — FOREX28",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "SMA_PERIOD": 20,
    "SD_MULT": 2.0,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (355 trades, 3/5 folds,
    # Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3915,
    "OOS_PROFIT_FACTOR": 1.1177,
    "OOS_EXPECTANCY_PCT": 0.1300,
}

# ==============================================================================
# TASK-STR-FWD-019 WAVE-2 (2026-11-18): RD-004 vol_regime_trend gate_lo
# family @ CRYPTO30 2h (near-miss audit ~/workspace/str-nearmiss/
# REPORT.md §1.2). Judged harness: rigorous_backtest/rd4/
# families_rd4.py (base trend signal gated by the daily
# volatility-regime rank; gate_lo = entries only when R(d) < 0.50).
# Judged bracket is RD-004's own (families_rd4 docstring + rd4/
# sim_rd4.py SL_BASE/TP_BASE): SL 2.0 x ATR(14), TP 4.0 x ATR(14);
# warmup 260 bars (families_rd4 WARMUP); costs 16 bps round trip
# (rd2/costs2 CRYPTO). The RD-004 WF-2h procedure's pooled stream is
# identical to the ema24_96_gate_lo cell (picked in all 5 folds) —
# NOT a separate config; not wired twice.
# ==============================================================================
VOL_REGIME_TREND_STRATEGY = {
    "NAME": "Vol-Regime Trend (EMA 24/96 cross, low-vol regime gate)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "2h",
    "SIGNAL": "ema24_96",
    "MODE": "gate_lo",
    "EMA_FAST": 24,
    "EMA_SLOW": 96,
    "REGIME_DAYS": 180,     # judged REGIME_DAYS (families_rd4)
    "GATE_THRESHOLD": 0.50,  # gate_lo: entries only when R(d) < 0.50
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged RD-004 bracket (sim_rd4 SL_BASE)
    "TP_ATR": 4.0,          # judged RD-004 bracket (sim_rd4 TP_BASE)
    "WARMUP_BARS": 260,     # judged WARMUP (families_rd4)
    # TASK-STR-RD-004 pooled OOS evidence (2,286 trades, 2/5 folds,
    # full frozen bar FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3675,
    "OOS_PROFIT_FACTOR": 1.107,
    "OOS_EXPECTANCY_PCT": 0.203,
    "OOS_TRADES": 2286,
}

VOL_REGIME_TREND_DON20_GATE_LO_STRATEGY = {
    "NAME": "Vol-Regime Trend (Donchian 20 breakout, low-vol regime gate)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "2h",
    "SIGNAL": "don20",
    "MODE": "gate_lo",
    "DONCHIAN_PERIOD": 20,
    "REGIME_DAYS": 180,
    "GATE_THRESHOLD": 0.50,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,
    "TP_ATR": 4.0,
    "WARMUP_BARS": 260,
    # TASK-STR-RD-004 pooled OOS evidence (6,313 trades, 3/5 folds,
    # full frozen bar FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3681,
    "OOS_PROFIT_FACTOR": 1.074,
    "OOS_EXPECTANCY_PCT": 0.148,
    "OOS_TRADES": 6313,
}

VOL_REGIME_TREND_EMA12_48_GATE_LO_STRATEGY = {
    "NAME": "Vol-Regime Trend (EMA 12/48 cross, low-vol regime gate)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "2h",
    "SIGNAL": "ema12_48",
    "MODE": "gate_lo",
    "EMA_FAST": 12,
    "EMA_SLOW": 48,
    "REGIME_DAYS": 180,
    "GATE_THRESHOLD": 0.50,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,
    "TP_ATR": 4.0,
    "WARMUP_BARS": 260,
    # TASK-STR-RD-004 pooled OOS evidence (3,471 trades, 2/5 folds,
    # full frozen bar FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3598,
    "OOS_PROFIT_FACTOR": 1.055,
    "OOS_EXPECTANCY_PCT": 0.107,
    "OOS_TRADES": 3471,
}

# ==============================================================================
# TASK-STR-FWD-019 WAVE-2 (2026-11-18): vol_adaptive_trend near-miss cells
# (RD-002, near-miss audit REPORT.md §1.4). FORWARD_TEST lane — see the
# registry entries below and the FWD-003 lane block above for governance.
# ==============================================================================
VOL_ADAPTIVE_TREND_STRATEGY = {
    "NAME": "Vol-Adaptive Trend (EMA(12) crosses EMA(26), no vol gate)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "FAST_EMA": 12,
    "SLOW_EMA": 26,
    "GATE": False,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.5,          # judged bracket (families2 build_configs)
    "TP_ATR": 5.0,          # judged bracket (families2 build_configs)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (299 trades, 4/5 folds,
    # PF @2x costs 1.6721, Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.4482,
    "OOS_PROFIT_FACTOR": 1.6956,
    "OOS_EXPECTANCY_PCT": 6.233,
}

VOL_ADAPTIVE_TREND_EMA20_50_NOGATE_STRATEGY = {
    "NAME": "Vol-Adaptive Trend (EMA(20) crosses EMA(50), no vol gate)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "FAST_EMA": 20,
    "SLOW_EMA": 50,
    "GATE": False,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.5,          # judged bracket (families2 build_configs)
    "TP_ATR": 5.0,          # judged bracket (families2 build_configs)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (246 trades, 4/5 folds,
    # PF @2x costs 1.6124, Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.4268,
    "OOS_PROFIT_FACTOR": 1.6359,
    "OOS_EXPECTANCY_PCT": 5.608,
}

VOL_ADAPTIVE_TREND_EMA20_50_NOGATE_4H_STRATEGY = {
    "NAME": "Vol-Adaptive Trend (EMA(20) crosses EMA(50), no vol gate) @ 4h",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "FAST_EMA": 20,
    "SLOW_EMA": 50,
    "GATE": False,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.5,          # judged bracket (families2 build_configs)
    "TP_ATR": 5.0,          # judged bracket (families2 build_configs)
    "WARMUP_BARS": 260,     # judged warmup_for("4h")
    # TASK-STR-RD-002 pooled OOS evidence (1,901 trades, 2/5 folds,
    # Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3709,
    "OOS_PROFIT_FACTOR": 1.1425,
    "OOS_EXPECTANCY_PCT": 0.591,
}

VOL_ADAPTIVE_TREND_EMA12_26_NOGATE_4H_STRATEGY = {
    "NAME": "Vol-Adaptive Trend (EMA(12) crosses EMA(26), no vol gate) @ 4h",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "FAST_EMA": 12,
    "SLOW_EMA": 26,
    "GATE": False,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.5,          # judged bracket (families2 build_configs)
    "TP_ATR": 5.0,          # judged bracket (families2 build_configs)
    "WARMUP_BARS": 260,     # judged warmup_for("4h")
    # TASK-STR-RD-002 pooled OOS evidence (2,073 trades, 2/5 folds,
    # Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3763,
    "OOS_PROFIT_FACTOR": 1.1348,
    "OOS_EXPECTANCY_PCT": 0.588,
}

VOL_ADAPTIVE_TREND_EMA20_50_GATE_4H_STRATEGY = {
    "NAME": "Vol-Adaptive Trend (EMA(20) crosses EMA(50), ATR-percentile vol gate) @ 4h",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "FAST_EMA": 20,
    "SLOW_EMA": 50,
    "GATE": True,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.5,          # judged bracket (families2 build_configs)
    "TP_ATR": 5.0,          # judged bracket (families2 build_configs)
    "WARMUP_BARS": 260,     # judged warmup_for("4h")
    # TASK-STR-RD-002 pooled OOS evidence (1,293 trades, 4/5 folds,
    # Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3743,
    "OOS_PROFIT_FACTOR": 1.1346,
    "OOS_EXPECTANCY_PCT": 0.550,
}

# ==============================================================================
# FX MEAN REVERSION v4 — OANDA PRACTICE VENUE (TASK-STR-FWD-004, 2026-11-15)
# Connors RSI(2) reversion behind an EMA(200) regime gate. The runtime
# parameters live in oanda_demo/strategy.py (MeanReversionConfig) — the SAME
# code path powers oanda_demo/backtest.py, so what was validated is what
# trades. This block is the governance record of that configuration, not a
# second source of runtime truth.
# ==============================================================================
FX_MR_V4_STRATEGY = {
    "NAME": "FX Mean Reversion v4 (Connors RSI-2, EMA200 regime gate)",
    "VERSION": "FX-MR-v4 (oanda_demo)",
    "TIMEFRAME": "1d",
    "RSI_PERIOD": 2,
    "RSI_BUY": 10.0,            # long when RSI(2) < 10 (oversold dip)
    "RSI_SELL": 90.0,           # short when RSI(2) > 90 (overbought pop)
    "EMA_REGIME_PERIOD": 200,   # only revert WITH the long-term trend
    "EMA_EXIT_PERIOD": 5,       # rule exit: close re-crosses EMA(5)
    "ATR_PERIOD": 14,
    "SL_ATR_MULTIPLIER": 4.0,   # disaster stop only (not the exit)
    "MAX_HOLD_BARS": 10,        # time stop
    "MIN_BARS": 260,
    "MAX_SPREAD_FRAC_ATR": 0.15,
}

# ==============================================================================
# PRODUCTION STRATEGY REGISTRY
# Explicit classification of all candidate strategies
# ==============================================================================

KELTNER_BREAKOUT_FOREX_STRATEGY = {
    "NAME": "Keltner Breakout (close crosses EMA(20) +/- 2.0 x ATR(14) band) — FOREX28 / OANDA",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "EMA_PERIOD": 20,
    "BAND_MULT": 2.0,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for (families2)
    # TASK-STR-RD-002 pooled OOS evidence (241 trades, 3/5 folds,
    # second tier only — Bonferroni FAIL at N=3,899, not a promotion):
    "OOS_WIN_RATE": 0.3900,
    "OOS_PROFIT_FACTOR": 1.1273,
    "OOS_EXPECTANCY_PCT": 0.137,
    "OOS_TRADES": 241,
    "OOS_POSITIVE_FOLDS": 3,
}

KELTNER_BREAKOUT_EMA20_M15_4H_STRATEGY = {
    "NAME": "Keltner Breakout (close crosses EMA(20) +/- 1.5 x ATR(14) band)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "EMA_PERIOD": 20,
    "BAND_MULT": 1.5,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for (families2)
    # TASK-STR-RD-002 pooled OOS evidence (4336 trades, 3/5 folds,
    # second tier only — Bonferroni FAIL at N=3,899, not a promotion):
    "OOS_WIN_RATE": 0.3605,
    "OOS_PROFIT_FACTOR": 1.0731,
    "OOS_EXPECTANCY_PCT": 0.256,
    "OOS_TRADES": 4336,
    "OOS_POSITIVE_FOLDS": 3,
}

KELTNER_BREAKOUT_EMA20_M2_4H_STRATEGY = {
    "NAME": "Keltner Breakout (close crosses EMA(20) +/- 2.0 x ATR(14) band)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "EMA_PERIOD": 20,
    "BAND_MULT": 2.0,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for (families2)
    # TASK-STR-RD-002 pooled OOS evidence (3314 trades, 2/5 folds,
    # second tier only — Bonferroni FAIL at N=3,899, not a promotion):
    "OOS_WIN_RATE": 0.3669,
    "OOS_PROFIT_FACTOR": 1.0816,
    "OOS_EXPECTANCY_PCT": 0.288,
    "OOS_TRADES": 3314,
    "OOS_POSITIVE_FOLDS": 2,
}

KELTNER_BREAKOUT_EMA20_M15_STRATEGY = {
    "NAME": "Keltner Breakout (close crosses EMA(20) +/- 1.5 x ATR(14) band)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "EMA_PERIOD": 20,
    "BAND_MULT": 1.5,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for (families2)
    # TASK-STR-RD-002 pooled OOS evidence (605 trades, 3/5 folds,
    # second tier only — Bonferroni FAIL at N=3,899, not a promotion):
    "OOS_WIN_RATE": 0.3471,
    "OOS_PROFIT_FACTOR": 1.1424,
    "OOS_EXPECTANCY_PCT": 1.215,
    "OOS_TRADES": 605,
    "OOS_POSITIVE_FOLDS": 3,
}

KELTNER_BREAKOUT_EMA50_M2_STRATEGY = {
    "NAME": "Keltner Breakout (close crosses EMA(50) +/- 2.0 x ATR(14) band)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "EMA_PERIOD": 50,
    "BAND_MULT": 2.0,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for (families2)
    # TASK-STR-RD-002 pooled OOS evidence (501 trades, 3/5 folds,
    # second tier only — Bonferroni FAIL at N=3,899, not a promotion):
    "OOS_WIN_RATE": 0.3593,
    "OOS_PROFIT_FACTOR": 1.1696,
    "OOS_EXPECTANCY_PCT": 1.465,
    "OOS_TRADES": 501,
    "OOS_POSITIVE_FOLDS": 3,
}

KELTNER_BREAKOUT_STRATEGY = {
    "NAME": "Keltner Breakout (close crosses EMA(20) +/- 2.0 x ATR(14) band)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "EMA_PERIOD": 20,
    "BAND_MULT": 2.0,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for (families2)
    # TASK-STR-RD-002 pooled OOS evidence (437 trades, 3/5 folds,
    # second tier only — Bonferroni FAIL at N=3,899, not a promotion):
    "OOS_WIN_RATE": 0.3753,
    "OOS_PROFIT_FACTOR": 1.2284,
    "OOS_EXPECTANCY_PCT": 1.941,
    "OOS_TRADES": 437,
    "OOS_POSITIVE_FOLDS": 3,
}

TURTLE2_N20_TRAIL_FILT_4H_STRATEGY = {
    "NAME": "turtle2 / n20_trail_filt @ CRYPTO30 4h (TASK-STR-FWD-019)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "CHANNEL_N": 20,
    "USE_FILTER": True,   # trail_filt: EMA(200) trend filter (sig_turtle2)
    "EMA_PERIOD": 200,
    "ATR_PERIOD": 14,
    "SPEC_TYPE": "trail",
    "SL_ATR": 2.0,          # judged TRAIL spec (families2 build_configs)
    "TP_ATR": None,         # judged TRAIL spec has NO fixed take-profit
    "TRAIL_ATR": 2.5,       # judged trailing-stop distance (families2 TRAIL)
    "WARMUP_BARS": 260,     # judged warmup_for("4h") (families2)
    # TASK-STR-RD-002 pooled OOS evidence (4369 trades, 3/5 folds,
    # Bonferroni FAIL at programme N=3,899 — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3809,
    "OOS_PROFIT_FACTOR": 1.1421,
    "OOS_EXPECTANCY_PCT": 0.33,
}

TURTLE2_N55_TRAIL_FILT_4H_STRATEGY = {
    "NAME": "turtle2 / n55_trail_filt @ CRYPTO30 4h (TASK-STR-FWD-019)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "CHANNEL_N": 55,
    "USE_FILTER": True,   # trail_filt: EMA(200) trend filter (sig_turtle2)
    "EMA_PERIOD": 200,
    "ATR_PERIOD": 14,
    "SPEC_TYPE": "trail",
    "SL_ATR": 2.0,          # judged TRAIL spec (families2 build_configs)
    "TP_ATR": None,         # judged TRAIL spec has NO fixed take-profit
    "TRAIL_ATR": 2.5,       # judged trailing-stop distance (families2 TRAIL)
    "WARMUP_BARS": 260,     # judged warmup_for("4h") (families2)
    # TASK-STR-RD-002 pooled OOS evidence (2966 trades, 4/5 folds,
    # Bonferroni FAIL at programme N=3,899 — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3911,
    "OOS_PROFIT_FACTOR": 1.1585,
    "OOS_EXPECTANCY_PCT": 0.366,
}

TURTLE2_N20_TRAIL_FILT_STRATEGY = {
    "NAME": "turtle2 / n20_trail_filt @ CRYPTO30 1d (TASK-STR-FWD-019)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "CHANNEL_N": 20,
    "USE_FILTER": True,   # trail_filt: EMA(200) trend filter (sig_turtle2)
    "EMA_PERIOD": 200,
    "ATR_PERIOD": 14,
    "SPEC_TYPE": "trail",
    "SL_ATR": 2.0,          # judged TRAIL spec (families2 build_configs)
    "TP_ATR": None,         # judged TRAIL spec has NO fixed take-profit
    "TRAIL_ATR": 2.5,       # judged trailing-stop distance (families2 TRAIL)
    "WARMUP_BARS": 260,     # judged warmup_for("1d") (families2)
    # TASK-STR-RD-002 pooled OOS evidence (558 trades, 3/5 folds,
    # Bonferroni FAIL at programme N=3,899 — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.371,
    "OOS_PROFIT_FACTOR": 1.159,
    "OOS_EXPECTANCY_PCT": 0.892,
}

TURTLE2_STRATEGY = {
    "NAME": "turtle2 / n55_trail_filt @ CRYPTO30 1d (TASK-STR-FWD-019)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "CHANNEL_N": 55,
    "USE_FILTER": True,   # trail_filt: EMA(200) trend filter (sig_turtle2)
    "EMA_PERIOD": 200,
    "ATR_PERIOD": 14,
    "SPEC_TYPE": "trail",
    "SL_ATR": 2.0,          # judged TRAIL spec (families2 build_configs)
    "TP_ATR": None,         # judged TRAIL spec has NO fixed take-profit
    "TRAIL_ATR": 2.5,       # judged trailing-stop distance (families2 TRAIL)
    "WARMUP_BARS": 260,     # judged warmup_for("1d") (families2)
    # TASK-STR-RD-002 pooled OOS evidence (400 trades, 3/5 folds,
    # Bonferroni FAIL at programme N=3,899 — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3725,
    "OOS_PROFIT_FACTOR": 1.2037,
    "OOS_EXPECTANCY_PCT": 1.17,
}

DONCHIAN_TURTLE_N55_B24_STRATEGY = {
    "NAME": "donchian_turtle / n55_b24 @ CRYPTO30 1d (TASK-STR-FWD-019)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "CHANNEL_N": 55,
    "ATR_PERIOD": 14,
    "SPEC_TYPE": "bracket",
    "SL_ATR": 2.0,          # judged bracket BR24 (families2 build_configs)
    "TP_ATR": 4.0,          # judged bracket BR24 (families2 build_configs)
    "WARMUP_BARS": 260,     # judged warmup_for("1d") (families2)
    # TASK-STR-RD-002 pooled OOS evidence (496 trades, 2/5 folds,
    # Bonferroni FAIL at programme N=3,899 — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3468,
    "OOS_PROFIT_FACTOR": 1.0581,
    "OOS_EXPECTANCY_PCT": 0.525,
}

DONCHIAN_TURTLE_N20_B26_4H_STRATEGY = {
    "NAME": "donchian_turtle / n20_b26 @ CRYPTO30 4h (TASK-STR-FWD-019)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "CHANNEL_N": 20,
    "ATR_PERIOD": 14,
    "SPEC_TYPE": "bracket",
    "SL_ATR": 2.0,          # judged bracket BR26 (families2 build_configs)
    "TP_ATR": 6.0,          # judged bracket BR26 (families2 build_configs)
    "WARMUP_BARS": 260,     # judged warmup_for("4h") (families2)
    # TASK-STR-RD-002 pooled OOS evidence (3583 trades, 3/5 folds,
    # Bonferroni FAIL at programme N=3,899 — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.276,
    "OOS_PROFIT_FACTOR": 1.0613,
    "OOS_EXPECTANCY_PCT": 0.26,
}

DONCHIAN_TURTLE_N20_B24_STRATEGY = {
    "NAME": "donchian_turtle / n20_b24 @ CRYPTO30 1d (TASK-STR-FWD-019)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "CHANNEL_N": 20,
    "ATR_PERIOD": 14,
    "SPEC_TYPE": "bracket",
    "SL_ATR": 2.0,          # judged bracket BR24 (families2 build_configs)
    "TP_ATR": 4.0,          # judged bracket BR24 (families2 build_configs)
    "WARMUP_BARS": 260,     # judged warmup_for("1d") (families2)
    # TASK-STR-RD-002 pooled OOS evidence (727 trades, 2/5 folds,
    # Bonferroni FAIL at programme N=3,899 — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3466,
    "OOS_PROFIT_FACTOR": 1.1016,
    "OOS_EXPECTANCY_PCT": 0.87,
}

DONCHIAN_TURTLE_N20_TRAIL_4H_STRATEGY = {
    "NAME": "donchian_turtle / n20_trail @ CRYPTO30 4h (TASK-STR-FWD-019)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "CHANNEL_N": 20,
    "ATR_PERIOD": 14,
    "SPEC_TYPE": "trail",
    "SL_ATR": 2.0,          # judged TRAIL spec (families2 build_configs)
    "TP_ATR": None,         # judged TRAIL spec has NO fixed take-profit
    "TRAIL_ATR": 2.5,       # judged trailing-stop distance (families2 TRAIL)
    "WARMUP_BARS": 260,     # judged warmup_for("4h") (families2)
    # TASK-STR-RD-002 pooled OOS evidence (5413 trades, 3/5 folds,
    # Bonferroni FAIL at programme N=3,899 — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3747,
    "OOS_PROFIT_FACTOR": 1.1043,
    "OOS_EXPECTANCY_PCT": 0.245,
}

DONCHIAN_TURTLE_N55_TRAIL_4H_STRATEGY = {
    "NAME": "donchian_turtle / n55_trail @ CRYPTO30 4h (TASK-STR-FWD-019)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "CHANNEL_N": 55,
    "ATR_PERIOD": 14,
    "SPEC_TYPE": "trail",
    "SL_ATR": 2.0,          # judged TRAIL spec (families2 build_configs)
    "TP_ATR": None,         # judged TRAIL spec has NO fixed take-profit
    "TRAIL_ATR": 2.5,       # judged trailing-stop distance (families2 TRAIL)
    "WARMUP_BARS": 260,     # judged warmup_for("4h") (families2)
    # TASK-STR-RD-002 pooled OOS evidence (3176 trades, 4/5 folds,
    # Bonferroni FAIL at programme N=3,899 — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.392,
    "OOS_PROFIT_FACTOR": 1.139,
    "OOS_EXPECTANCY_PCT": 0.32,
}

DONCHIAN_TURTLE_N55_TRAIL_STRATEGY = {
    "NAME": "donchian_turtle / n55_trail @ CRYPTO30 1d (TASK-STR-FWD-019)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "CHANNEL_N": 55,
    "ATR_PERIOD": 14,
    "SPEC_TYPE": "trail",
    "SL_ATR": 2.0,          # judged TRAIL spec (families2 build_configs)
    "TP_ATR": None,         # judged TRAIL spec has NO fixed take-profit
    "TRAIL_ATR": 2.5,       # judged trailing-stop distance (families2 TRAIL)
    "WARMUP_BARS": 260,     # judged warmup_for("1d") (families2)
    # TASK-STR-RD-002 pooled OOS evidence (435 trades, 3/5 folds,
    # Bonferroni FAIL at programme N=3,899 — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3632,
    "OOS_PROFIT_FACTOR": 1.1509,
    "OOS_EXPECTANCY_PCT": 0.864,
}

DONCHIAN_TURTLE_N20_B26_STRATEGY = {
    "NAME": "donchian_turtle / n20_b26 @ CRYPTO30 1d (TASK-STR-FWD-019)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "CHANNEL_N": 20,
    "ATR_PERIOD": 14,
    "SPEC_TYPE": "bracket",
    "SL_ATR": 2.0,          # judged bracket BR26 (families2 build_configs)
    "TP_ATR": 6.0,          # judged bracket BR26 (families2 build_configs)
    "WARMUP_BARS": 260,     # judged warmup_for("1d") (families2)
    # TASK-STR-RD-002 pooled OOS evidence (400 trades, 3/5 folds,
    # Bonferroni FAIL at programme N=3,899 — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.275,
    "OOS_PROFIT_FACTOR": 1.1641,
    "OOS_EXPECTANCY_PCT": 1.596,
}

DONCHIAN_TURTLE_N20_TRAIL_STRATEGY = {
    "NAME": "donchian_turtle / n20_trail @ CRYPTO30 1d (TASK-STR-FWD-019)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "CHANNEL_N": 20,
    "ATR_PERIOD": 14,
    "SPEC_TYPE": "trail",
    "SL_ATR": 2.0,          # judged TRAIL spec (families2 build_configs)
    "TP_ATR": None,         # judged TRAIL spec has NO fixed take-profit
    "TRAIL_ATR": 2.5,       # judged trailing-stop distance (families2 TRAIL)
    "WARMUP_BARS": 260,     # judged warmup_for("1d") (families2)
    # TASK-STR-RD-002 pooled OOS evidence (677 trades, 3/5 folds,
    # Bonferroni FAIL at programme N=3,899 — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3885,
    "OOS_PROFIT_FACTOR": 1.1968,
    "OOS_EXPECTANCY_PCT": 1.087,
}

DONCHIAN_TURTLE_STRATEGY = {
    "NAME": "donchian_turtle / n55_b26 @ CRYPTO30 1d (TASK-STR-FWD-019)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "CHANNEL_N": 55,
    "ATR_PERIOD": 14,
    "SPEC_TYPE": "bracket",
    "SL_ATR": 2.0,          # judged bracket BR26 (families2 build_configs)
    "TP_ATR": 6.0,          # judged bracket BR26 (families2 build_configs)
    "WARMUP_BARS": 260,     # judged warmup_for("1d") (families2)
    # TASK-STR-RD-002 pooled OOS evidence (298 trades, 4/5 folds,
    # Bonferroni FAIL at programme N=3,899 — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3523,
    "OOS_PROFIT_FACTOR": 1.6502,
    "OOS_EXPECTANCY_PCT": 5.614,
}

RSI_MOMENTUM_FOREX_STRATEGY = {
    "NAME": "RSI Momentum (RSI(14) crosses 55 up / 45 down) — FOREX28 / OANDA",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "RSI_PERIOD": 14,
    "RSI_HI": 55.0,
    "RSI_LO": 45.0,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    "OOS_TRADES": 344,
    "OOS_WIN_RATE": 0.3721,
    "OOS_PROFIT_FACTOR": 1.0761,
    "OOS_EXPECTANCY_PCT": 0.089,
}

RSI_MOMENTUM_RSI7_60_40_STRATEGY = {
    "NAME": "RSI Momentum (RSI(7) crosses 60 up / 40 down)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "RSI_PERIOD": 7,
    "RSI_HI": 60.0,
    "RSI_LO": 40.0,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    "OOS_TRADES": 709,
    "OOS_WIN_RATE": 0.3470,
    "OOS_PROFIT_FACTOR": 1.0932,
    "OOS_EXPECTANCY_PCT": 0.856,
}

RSI_MOMENTUM_STRATEGY = {
    "NAME": "RSI Momentum (RSI(14) crosses 55 up / 45 down)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "RSI_PERIOD": 14,
    "RSI_HI": 55.0,
    "RSI_LO": 45.0,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (grid_rows record):
    "OOS_TRADES": 648,
    "OOS_WIN_RATE": 0.3642,
    "OOS_PROFIT_FACTOR": 1.1016,
    "OOS_EXPECTANCY_PCT": 0.913,
}

CHOPPINESS_BREAKOUT_STRATEGY = {
    "NAME": "Choppiness Breakout (Donchian 20 breakout, CHOP(14) < 45 trend gate)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1h",
    "WINDOW": 500,          # judged module_eval sliding window
    "DONCHIAN_PERIOD": 20,
    "CHOP_PERIOD": 14,
    "CHOP_MAX": 45.0,       # entries only when CHOP(14) < 45 (trending)
    "EMA_PERIOD": 200,
    "ATR_PERIOD": 20,
    "SL_ATR": 2.0,          # judged module's OWN bracket (module_eval kept it)
    "TP_ATR": 4.5,          # judged module's OWN bracket
    "WARMUP_BARS": 260,     # judged WARMUP_BARS (module_eval)
    # TASK-STR-RD-001 stage-1 pooled OOS evidence (940 trades, 3/5
    # folds, full frozen bar FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3564,
    "OOS_PROFIT_FACTOR": 1.055,
    "OOS_EXPECTANCY_PCT": 0.074,
    "OOS_TRADES": 940,
}

# ==============================================================================
# TASK-STR-FWD-019 WAVE-2 (2026-11-18): RD-001 stage-1 discovery
# modules (near-miss audit ~/workspace/str-nearmiss/REPORT.md §1.1).
# Judged harness: rigorous_backtest/rd/stage1.py via
# rigorous_backtest/module_eval.py — the module's OWN get_signal()
# on trailing <=500-bar windows from bar 260 (WARMUP_BARS), MODULE
# simulation convention keeping the module's OWN bracket, 16 bps
# round-trip costs (rd/common COSTS). Timeframe: JUDGED AT 1h —
# stage1.py evaluated on load_timeframe("1h"), the dataset selected
# by run_all._infer_primary_timeframe (default "1h"; neither module
# names a timeframe); the stage-1 row JSONs record timeframe "1h"
# with 27,048 hourly rows per symbol. Both are wired at 1h (see the
# registry reasons; corrected 2026-11-18 per the wave-2 review —
# the original 1d wiring rested on the near-miss audit REPORT
# §1.1 footnote, which the primary records contradict). The judged
# module files were deleted by TASK-STR-CLEANUP-001 after
# judgement; the lane modules are line-faithful ports of the
# judged sources (volatility bd9585c97b, choppiness 8b6ec77a4).
# ==============================================================================
VOLATILITY_BREAKOUT_STRATEGY = {
    "NAME": "Volatility Breakout (ATR expansion + 10-bar breakout, EMA trend gate)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1h",
    "WINDOW": 500,          # judged module_eval sliding window
    "EMA_FAST": 50,
    "EMA_SLOW": 200,
    "DONCHIAN_PERIOD": 10,
    "ATR_PERIOD": 14,
    "ATR_AVG_PERIOD": 20,
    "EXPANSION_MULT": 1.2,  # ATR > 1.2 x its 20-bar average = expanding
    "SL_ATR": 2.5,          # judged module's OWN bracket (module_eval kept it)
    "TP_ATR": 6.0,          # judged module's OWN bracket
    "WARMUP_BARS": 260,     # judged WARMUP_BARS (module_eval)
    # TASK-STR-RD-001 stage-1 pooled OOS evidence (520 trades, 3/5
    # folds, full frozen bar FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3519,
    "OOS_PROFIT_FACTOR": 1.067,
    "OOS_EXPECTANCY_PCT": 0.131,
    "OOS_TRADES": 520,
}

PSAR_TREND_AF002_MAX020_STRATEGY = {
    "NAME": "PSAR Trend (Parabolic SAR flips, step 0.02, max AF 0.20)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "AF_STEP": 0.02,
    "AF_MAX": 0.20,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for (families2)
    # TASK-STR-RD-002 pooled OOS evidence (651 trades, 2/5 folds,
    # second tier only — Bonferroni FAIL at N=3,899, not a promotion):
    "OOS_WIN_RATE": 0.3671,
    "OOS_PROFIT_FACTOR": 1.1526,
    "OOS_EXPECTANCY_PCT": 1.447,
    "OOS_TRADES": 651,
    "OOS_POSITIVE_FOLDS": 2,
}

PSAR_TREND_AF001_MAX010_STRATEGY = {
    "NAME": "PSAR Trend (Parabolic SAR flips, step 0.01, max AF 0.10)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "AF_STEP": 0.01,
    "AF_MAX": 0.10,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for (families2)
    # TASK-STR-RD-002 pooled OOS evidence (648 trades, 3/5 folds,
    # second tier only — Bonferroni FAIL at N=3,899, not a promotion):
    "OOS_WIN_RATE": 0.3765,
    "OOS_PROFIT_FACTOR": 1.2165,
    "OOS_EXPECTANCY_PCT": 1.828,
    "OOS_TRADES": 648,
    "OOS_POSITIVE_FOLDS": 3,
}

TSMOM2_DUAL_CRYPTO_STRATEGY = {
    "NAME": "Dual Momentum (ROC(90) zero-cross + EMA(200) gate) @ CRYPTO30 4h",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "ROC_LOOKBACK": 90,
    "EMA_PERIOD": 200,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.5,          # judged bracket (families2 build_configs; verified in this cell's row record)
    "TP_ATR": 5.0,          # judged bracket (families2 build_configs; verified in this cell's row record)
    "WARMUP_BARS": 260,     # judged warmup_for("4h")
    # TASK-STR-RD-002 pooled OOS evidence (1,580 trades, 3/5 folds,
    # Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3627,
    "OOS_PROFIT_FACTOR": 1.0965,
    "OOS_EXPECTANCY_PCT": 0.402,
}

TS_MOMENTUM_ROC168_RD001_STRATEGY = {
    "NAME": "Time-Series Momentum (ROC(168) zero-cross) @ 1h — RD-001 row",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1h",
    "ROC_LOOKBACK": 168,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket (rd/stage3.py roc168_1h)
    "TP_ATR": 4.0,          # judged bracket (rd/stage3.py roc168_1h)
    "WARMUP_BARS": 260,     # judged WARMUP (rd/stage3.py)
    # TASK-STR-RD-001 pooled OOS evidence (678 trades, 4/5 folds,
    # holdout FAIL, SOL = 84% of profit — stage5_synthesis ranked row):
    "OOS_WIN_RATE": 0.3805,
    "OOS_PROFIT_FACTOR": 1.0663,
    "OOS_EXPECTANCY_PCT": 0.082,
}

TS_MOMENTUM_ROC42_4H_STRATEGY = {
    "NAME": "Time-Series Momentum (ROC(42) zero-cross) @ 4h",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "ROC_LOOKBACK": 42,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families2)
    "TP_ATR": 4.0,          # judged bracket BR24 (families2)
    "WARMUP_BARS": 260,     # judged warmup_for("4h")
    # TASK-STR-RD-002 pooled OOS evidence (2,906 trades, 3/5 folds,
    # Bonferroni FAIL — near-miss, not a promotion). RD-001's roc42_4h
    # row is the same judged stream — see the registry reason (alias).
    "OOS_WIN_RATE": 0.3672,
    "OOS_PROFIT_FACTOR": 1.0993,
    "OOS_EXPECTANCY_PCT": 0.338,
}

TS_MOMENTUM_ROC168_STRATEGY = {
    "NAME": "Time-Series Momentum (ROC(168) zero-cross)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "ROC_LOOKBACK": 168,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families2)
    "TP_ATR": 4.0,          # judged bracket BR24 (families2)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (265 trades, 3/5 folds,
    # PF @2x costs 1.1580, Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.3925,
    "OOS_PROFIT_FACTOR": 1.1776,
    "OOS_EXPECTANCY_PCT": 1.579,
}

TS_MOMENTUM_ROC42_STRATEGY = {
    "NAME": "Time-Series Momentum (ROC(42) zero-cross)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "ROC_LOOKBACK": 42,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families2)
    "TP_ATR": 4.0,          # judged bracket BR24 (families2)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (460 trades, 4/5 folds,
    # PF @2x costs 1.4088, Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.4283,
    "OOS_PROFIT_FACTOR": 1.4354,
    "OOS_EXPECTANCY_PCT": 3.213,
}

# ==============================================================================
# TASK-STR-FWD-019 WAVE-2 (2026-11-18): ts_momentum (RD-002 + RD-001 rows)
# and the tsmom2_dual crypto30 4h cell. FORWARD_TEST lane — see the registry
# entries below and the FWD-003 lane block above for governance.
# ==============================================================================
TS_MOMENTUM_STRATEGY = {
    "NAME": "Time-Series Momentum (ROC(72) zero-cross)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "ROC_LOOKBACK": 72,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families2)
    "TP_ATR": 4.0,          # judged bracket BR24 (families2)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (334 trades, 5/5 folds,
    # PF @2x costs 1.5760, Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.4251,
    "OOS_PROFIT_FACTOR": 1.6049,
    "OOS_EXPECTANCY_PCT": 4.376,
}

HA_TREND_ONE_CANDLE_4H_STRATEGY = {
    "NAME": "HA Trend (single wickless Heikin-Ashi candle)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "TWO_CANDLE": False,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for (families2)
    # TASK-STR-RD-002 pooled OOS evidence (6082 trades, 3/5 folds,
    # second tier only — Bonferroni FAIL at N=3,899, not a promotion):
    "OOS_WIN_RATE": 0.3671,
    "OOS_PROFIT_FACTOR": 1.0625,
    "OOS_EXPECTANCY_PCT": 0.239,
    "OOS_TRADES": 6082,
    "OOS_POSITIVE_FOLDS": 3,
}

HA_TREND_ONE_CANDLE_STRATEGY = {
    "NAME": "HA Trend (single wickless Heikin-Ashi candle)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "TWO_CANDLE": False,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for (families2)
    # TASK-STR-RD-002 pooled OOS evidence (877 trades, 2/5 folds,
    # second tier only — Bonferroni FAIL at N=3,899, not a promotion):
    "OOS_WIN_RATE": 0.3455,
    "OOS_PROFIT_FACTOR": 1.0684,
    "OOS_EXPECTANCY_PCT": 0.634,
    "OOS_TRADES": 877,
    "OOS_POSITIVE_FOLDS": 2,
}

HA_TREND_TWO_CANDLE_4H_STRATEGY = {
    "NAME": "HA Trend (two consecutive wickless Heikin-Ashi candles)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "TWO_CANDLE": True,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for (families2)
    # TASK-STR-RD-002 pooled OOS evidence (5639 trades, 4/5 folds,
    # second tier only — Bonferroni FAIL at N=3,899, not a promotion):
    "OOS_WIN_RATE": 0.3685,
    "OOS_PROFIT_FACTOR": 1.0764,
    "OOS_EXPECTANCY_PCT": 0.290,
    "OOS_TRADES": 5639,
    "OOS_POSITIVE_FOLDS": 4,
}

HA_TREND_STRATEGY = {
    "NAME": "HA Trend (two consecutive wickless Heikin-Ashi candles)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "TWO_CANDLE": True,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for (families2)
    # TASK-STR-RD-002 pooled OOS evidence (775 trades, 3/5 folds,
    # second tier only — Bonferroni FAIL at N=3,899, not a promotion):
    "OOS_WIN_RATE": 0.3639,
    "OOS_PROFIT_FACTOR": 1.1878,
    "OOS_EXPECTANCY_PCT": 1.671,
    "OOS_TRADES": 775,
    "OOS_POSITIVE_FOLDS": 3,
}

STOCH_REVERSION_CRYPTO_STRATEGY = {
    "NAME": "Stochastic Reversion (%K(14) SMA3 crosses 20 up / 80 down) — CRYPTO30",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "STOCH_PERIOD": 14,
    "STOCH_SMOOTH": 3,
    "STOCH_LO": 20.0,
    "STOCH_HI": 80.0,
    "FILTERED": False,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    "OOS_TRADES": 688,
    "OOS_WIN_RATE": 0.3706,
    "OOS_PROFIT_FACTOR": 1.0510,
    "OOS_EXPECTANCY_PCT": 0.518,
}

STOCH_REVERSION_K14_FILT_STRATEGY = {
    "NAME": "Stochastic Reversion (%K(14) SMA3 crosses, EMA200-gated) — FOREX28 / OANDA",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "STOCH_PERIOD": 14,
    "STOCH_SMOOTH": 3,
    "STOCH_LO": 20.0,
    "STOCH_HI": 80.0,
    "FILTERED": True,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    "OOS_TRADES": 216,
    "OOS_WIN_RATE": 0.3519,
    "OOS_PROFIT_FACTOR": 1.0613,
    "OOS_EXPECTANCY_PCT": 0.072,
}

STOCH_REVERSION_STRATEGY = {
    "NAME": "Stochastic Reversion (%K(14) SMA3 crosses 20 up / 80 down) — FOREX28 / OANDA",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "STOCH_PERIOD": 14,
    "STOCH_SMOOTH": 3,
    "STOCH_LO": 20.0,
    "STOCH_HI": 80.0,
    "FILTERED": False,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (grid_rows record):
    "OOS_TRADES": 365,
    "OOS_WIN_RATE": 0.3863,
    "OOS_PROFIT_FACTOR": 1.2623,
    "OOS_EXPECTANCY_PCT": 0.286,
}

BAR_PATTERNS_INSIDE_BAR_4H_STRATEGY = {
    "NAME": "Bar Patterns (inside-bar breakout)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "PATTERN": "inside_bar",
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for (families2)
    # TASK-STR-RD-002 pooled OOS evidence (3481 trades, 3/5 folds,
    # second tier only — Bonferroni FAIL at N=3,899, not a promotion):
    "OOS_WIN_RATE": 0.3617,
    "OOS_PROFIT_FACTOR": 1.0556,
    "OOS_EXPECTANCY_PCT": 0.209,
    "OOS_TRADES": 3481,
    "OOS_POSITIVE_FOLDS": 3,
}

BAR_PATTERNS_STRATEGY = {
    "NAME": "Bar Patterns (engulfing candles)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "PATTERN": "engulfing",
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for (families2)
    # TASK-STR-RD-002 pooled OOS evidence (548 trades, 3/5 folds,
    # second tier only — Bonferroni FAIL at N=3,899, not a promotion):
    "OOS_WIN_RATE": 0.3850,
    "OOS_PROFIT_FACTOR": 1.1743,
    "OOS_EXPECTANCY_PCT": 1.587,
    "OOS_TRADES": 548,
    "OOS_POSITIVE_FOLDS": 3,
}

# ==============================================================================
# TASK-STR-FWD-019 WAVE-2 (2026-11-18): macd_trend near-miss cell (RD-002,
# near-miss audit REPORT.md §1.4 row 6). FORWARD_TEST lane — see the registry
# entry below and the FWD-003 lane block above for governance.
# ==============================================================================
MACD_TREND_STRATEGY = {
    "NAME": "MACD Trend (MACD(12,26,9) histogram zero-cross, unfiltered)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "MACD_FAST": 12,
    "MACD_SLOW": 26,
    "MACD_SIGNAL": 9,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.5,          # judged bracket BR25 (families3)
    "TP_ATR": 5.0,          # judged bracket BR25 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (369 trades, 2/5 folds — weak,
    # PF @2x costs 1.5330, Bonferroni FAIL — near-miss, not a promotion):
    "OOS_WIN_RATE": 0.4201,
    "OOS_PROFIT_FACTOR": 1.5522,
    "OOS_EXPECTANCY_PCT": 5.840,
}

VOL_COMPRESSION_SQUEEZE_RAW_STRATEGY = {
    "NAME": "Vol Compression (ATR7 squeeze breakout, ungated) — 1h",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1h",
    "ATR_FAST_PERIOD": 7,
    "SQUEEZE_WINDOW": 50,
    "BREAKOUT_BARS": 10,
    "FILTERED": False,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1h")
    "OOS_TRADES": 1926,
    "OOS_WIN_RATE": 0.3655,
    "OOS_PROFIT_FACTOR": 1.0502,
    "OOS_EXPECTANCY_PCT": 0.076,
}

VOL_COMPRESSION_STRATEGY = {
    "NAME": "Vol Compression (ATR7 squeeze breakout, EMA200-gated) — 1h",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1h",
    "ATR_FAST_PERIOD": 7,
    "SQUEEZE_WINDOW": 50,
    "BREAKOUT_BARS": 10,
    "FILTERED": True,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families3)
    "TP_ATR": 4.0,          # judged bracket BR24 (families3)
    "WARMUP_BARS": 260,     # judged warmup_for("1h")
    # TASK-STR-RD-002 pooled OOS evidence (grid_rows record):
    "OOS_TRADES": 1104,
    "OOS_WIN_RATE": 0.3732,
    "OOS_PROFIT_FACTOR": 1.1310,
    "OOS_EXPECTANCY_PCT": 0.182,
}

VOLUME_BREAKOUT_STRATEGY = {
    "NAME": "Volume Breakout (Donchian(20) break, volume > 1.5x SMA(20) volume)",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "DONCHIAN_BARS": 20,
    "VOLUME_WINDOW": 20,
    "VOLUME_CONFIRM": 1.5,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families2)
    "TP_ATR": 4.0,          # judged bracket BR24 (families2)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    # TASK-STR-RD-002 pooled OOS evidence (grid_rows record):
    "OOS_TRADES": 558,
    "OOS_WIN_RATE": 0.3925,
    "OOS_PROFIT_FACTOR": 1.3038,
    "OOS_EXPECTANCY_PCT": 2.417,
}

MTF_CONFLUENCE_1D_STRATEGY = {
    "NAME": "MTF Confluence (EMA20/50 cross + EMA200 gate, native series) — 1d",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "1d",
    "EMA_FAST": 20,
    "EMA_SLOW": 50,
    "EMA_TREND": 200,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families2)
    "TP_ATR": 4.0,          # judged bracket BR24 (families2)
    "WARMUP_BARS": 260,     # judged warmup_for("1d")
    "OOS_TRADES": 217,
    "OOS_WIN_RATE": 0.3779,
    "OOS_PROFIT_FACTOR": 1.1902,
    "OOS_EXPECTANCY_PCT": 1.472,
}

MTF_CONFLUENCE_STRATEGY = {
    "NAME": "MTF Confluence (EMA20/50 cross + EMA200 gate, native series) — 4h",
    "VERSION": "v1.0.0 (TASK-STR-FWD-019)",
    "TIMEFRAME": "4h",
    "EMA_FAST": 20,
    "EMA_SLOW": 50,
    "EMA_TREND": 200,
    "ATR_PERIOD": 14,
    "SL_ATR": 2.0,          # judged bracket BR24 (families2)
    "TP_ATR": 4.0,          # judged bracket BR24 (families2)
    "WARMUP_BARS": 260,     # judged warmup_for("4h")
    # TASK-STR-RD-002 pooled OOS evidence (grid_rows record):
    "OOS_TRADES": 1668,
    "OOS_WIN_RATE": 0.3807,
    "OOS_PROFIT_FACTOR": 1.1538,
    "OOS_EXPECTANCY_PCT": 0.490,
}

# ==============================================================================
# TASK-STR-CLEANUP-001 (owner directive, 2026-11-15): every strategy whose
# verified out-of-sample profit factor (net of costs, TASK-STR-BT-001 /
# TASK-STR-RD-001 walk-forward evidence) is below 1.2 has been DELETED —
# code, registry entry and config. Removed: bb_reversion (PF 0.68),
# factory_winner_1..5 (PF 0.54-0.73), supertrend (PF 0.82), adx_ema_mtf
# (0.74), aggressive_scalper (0.34), aggressor (0.93), rsi_burst (0.59),
# scalper (0.86), swing (0.94), vwap_trend (0.71). Survivors below:
# adx_ema (PF 1.46 production-faithful / 1.57 bare — the only governed
# strategy at or above the bar) and ml (DISABLED; never honestly
# backtested, so not removable under the evidence rule). SMT-v2 (OANDA)
# was never governed here; its TASK-STR-RD-002 retest measured OOS
# PF 0.655 (627 trades, -30.0R) and TASK-STR-CLEANUP-002 (2026-11-15)
# DELETED it under the same rule — code, config and dedicated tests.
# ==============================================================================
PRODUCTION_STRATEGY_REGISTRY: dict[str, dict[str, Any]] = {
    "adx_ema": {
        "status": "OBSERVE_ONLY",
        "version": "V2-spot rev3 (2026-08-22)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: (a) EMA(20) crosses above EMA(50), Close > EMA(200), ADX(14) > 20; or (b) qualified retest — first EMA20 touch within 10 bars of a qualified cross, bullish close. AND BTCUSDT 4h close > its EMA(200) (market regime gate). SELL signals blocked by LONG_ONLY spot constraint. V1 pullback entry REMOVED (net-negative 2021-2026).",
        "sl_method": "3.0 * ATR(14)",
        "tp_method": "3.0 * ATR(14)",
        "rr_ratio": 1.0,
        "oos_win_rate_prior": None,
        "total_friction_bps": 31.0,
        "expected_net_edge_bps": None,
        "minimum_required_edge": 0.0005,
        "validated_assets": [],
        "reason": "Observe only: historical OOS claims are not reproducible because the referenced OHLCV inputs are absent; the checked-in walk-forward report records 34 frozen-config holdout trades and a FRAGILE verdict.",
    },
    "ml": {
        "status": "DISABLED",
        "timeframe": "15m",
        "execution_model": "PROBABILISTIC",
        "reason": "Disabled: Requires trained model artifacts with calibrated predict_proba >= 43.0%."
    },
    "ichimoku_trend": {
        "status": "VALIDATED",
        "version": "v1.0.0 (TASK-STR-FWD-002)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: Tenkan(9) crosses above Kijun(26) (windows include current bar) AND close above the cloud (max of span A/B, both shifted 26). SHORT: cross down AND close below the cloud. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_ichimoku(cloud=True), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.4010,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 89.4,
        "minimum_required_edge": 0.0005,
        "validated_assets": CRYPTO30_SYMBOLS,
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "reason": "TASK-STR-RD-002 winner: ichimoku_trend/tk_cloud @ CRYPTO30 4h passed the full bar (expectancy>0, PF 1.278 >= 1.2, 2,302 OOS trades, >=80% folds, untouched holdout), Bonferroni at N=1,557 and the 2x-cost stress (PF 1.222). Owner approved forward demo trading 2026-11-15 (TASK-STR-FWD-002). Phase-3 protocol (TASK-STR-FWD-006 decided package, docs/PHASE3_FORWARD_PROTOCOL.md): 0.1% per-trade risk on VENUE equity, 2% aggregate heat cap per strategy, 3% daily breaker (pause, not kill), kill criteria (expectancy<0 or PF<1.0 after >=50 closed trades, or mark-to-market strategy drawdown >5% of venue equity, evaluated on the scan cadence) auto-pause via measurement/forward_guard.py. DEMO venue only; live trading prohibited.",
    },
    "ichimoku_trend_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-018)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: Tenkan(9) crosses above Kijun(26) (windows include current bar) AND close above the cloud (max of span A/B, both shifted 26). SHORT: cross down AND close below the cloud. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_ichimoku(df, cloud=True, warmup) on CRYPTO30 1d bars, warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3970,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 301.3,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "max_stop_pct": 0.50,
        "forward_lane": "FORWARD_TEST",
        "reason": "TASK-STR-RD-002 near-miss re-audit 2026-11-18 (TASK-STR-FWD-018 wave 1): ichimoku_trend/tk_cloud @ CRYPTO30 1d — expectancy +3.0131%/trade, PF 1.3674, 398 pooled OOS trades, 4/5 positive folds, max symbol share 0.089 (grid_rows pooled_oos: ichimoku_trend__tk_cloud__crypto30__1d). Admitted under the owner's second-tier demo-admission bar (2026-11-18: OOS expectancy>0, PF>=1.05, >=200 OOS trades, pre-Bonferroni); it does NOT pass the frozen promotion bar (Bonferroni + holdout) — not a promotion, and a different judged object from the VALIDATED ichimoku_trend (tk_cloud @ 4h), whose record is untouched. FORWARD_TEST lane terms as for bollinger_trend. FWD-012 stop-cap check (2026-11-18, harness signal bars over the full CRYPTO30 universe): signal-day judged stops (2.0 x ATR(14)) median 13.41%, p99 27.46%, max 36.92%, with 36.2% of judged signals above the 0.15 global cap — max_stop_pct 0.50 is set so the judged bracket is not silently clipped (a sanity bound above the measured distribution; under FWD-006 a wider stop shrinks the position, it does not add risk).",
    },
    "ichimoku_trend_raw": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-018)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: Tenkan(9) crosses above Kijun(26) (windows include current bar), NO cloud filter. SHORT: cross down. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_ichimoku(df, cloud=False, warmup) on CRYPTO30 4h bars, warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3741,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 41.1,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": "TASK-STR-RD-002 near-miss re-audit 2026-11-18 (TASK-STR-FWD-018 wave 1): ichimoku_trend/tk_raw @ CRYPTO30 4h — expectancy +0.4106%/trade, PF 1.1144, 3,630 pooled OOS trades, 3/5 positive folds, max symbol share 0.120 (grid_rows pooled_oos: ichimoku_trend__tk_raw__crypto30__4h). Admitted under the owner's second-tier demo-admission bar (2026-11-18: OOS expectancy>0, PF>=1.05, >=200 OOS trades, pre-Bonferroni); it does NOT pass the frozen promotion bar (PF>=1.2, >=4/5 folds, Bonferroni, holdout) — not a promotion. FORWARD_TEST lane terms as for bollinger_trend. FWD-012 stop-cap check (2026-11-18, harness signal bars over the full CRYPTO30 universe): signal-day judged stops (2.0 x ATR(14)) median 4.06%, p99 10.41%, max 16.85%, only 0.11% of judged signals above the 0.15 global cap — NO max_stop_pct override; the global cap binds as the sanity bound, as for the VALIDATED ichimoku_trend.",
    },
    "dow_effect": {
        "status": "VALIDATED",
        "version": "v1.0.0 (TASK-STR-FWD-002)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Monday bars only (UTC bar open): SHORT if trailing 5-bar return (close/close[-5]-1) > 0, LONG otherwise (reversal). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_dow(kind='reversal'), warmup 260 bars.",
        "sl_method": "3.0 * ATR(14) at signal bar (judged bracket_time)",
        "tp_method": "6.0 * ATR(14) at signal bar (judged bracket_time)",
        "rr_ratio": 2.0,
        "max_bars": 5,
        "oos_win_rate_prior": 0.5227,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 87.8,
        "minimum_required_edge": 0.0005,
        "validated_assets": CRYPTO30_SYMBOLS,
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        # TASK-STR-FWD-012: judged stop is 3.0 x daily ATR — genuine stops
        # observed 16.07-36.00% across CRYPTO30, structurally above the
        # 15% engine-global cap, which blocked 27 of 30 symbols at the
        # 2026-11-17 firing. 0.90 = sanity bound only (FWD-006 sizes by
        # risk / stop distance; binding would need ATR > 30% of price
        # sustained 14 days — never observed in this universe).
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-RD-002 winner: dow_effect/reversal @ CRYPTO30 1d passed the full bar (expectancy>0, PF 1.257 >= 1.2, 3,660 OOS trades, >=80% folds, untouched holdout), Bonferroni at N=1,557 and the 2x-cost stress (PF 1.206). Calendar effect — flagged in RD-002 as most prone to era decay; the forward window is the arbiter. Owner approved forward demo trading 2026-11-15 (TASK-STR-FWD-002). Time exit (max_bars=5) enforced by the daemon (no broker-native equivalent). Phase-3 protocol as for ichimoku_trend (TASK-STR-FWD-006 package). Vol-targeting is BANNED for dow_effect (TASK-STR-RD-011 settlement): no volatility-scaled position sizing may ever be applied to this strategy. DEMO venue only; live trading prohibited.",
    },
    "fx_mr_v4": {
        "status": "VALIDATED",
        "version": "FX-MR-v4 (oanda_demo, TASK-STR-FWD-004)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "venue": "oanda_practice",
        "engine": "oanda_demo",
        "entry_conditions": "LONG: RSI(2) < 10 AND close > EMA(200). SHORT: RSI(2) > 90 AND close < EMA(200). Spread <= 15% of ATR(14); >= 260 daily bars. Watchlist (the practice account's FX basket): EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, NZDUSD, EURJPY, EURGBP. Signal code: oanda_demo/strategy.py MeanReversionStrategy — the identical code path oanda_demo/backtest.py validates.",
        "sl_method": "4.0 * ATR(14) disaster stop (broker-native SL attached on fill). Exits are engine-managed: EMA(5) re-cross rule exit or the 10-bar time stop. No take-profit.",
        "tp_method": "none (rule exit / time stop)",
        "oos_win_rate_prior": None,
        "total_friction_bps": None,
        "expected_net_edge_bps": None,
        "minimum_required_edge": 0.0005,
        "validated_assets": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "EURJPY", "EURGBP"],
        "forward_protocol": True,
        "forward_venues": ["oanda_practice"],
        "reason": "OANDA venue activation (TASK-STR-FWD-004; owner directive 2026-11-15: Stratex must take trades on each and every venue — OANDA unpaused under measurement). Evidence state, stated plainly: backtest-validated in the oanda_demo programme on real OANDA practice data (2026-11-13 — the strategy class that survived when every trend variant measured net-negative on the FX basket), but it has NO forward record: 0 closed trades. The OANDA engine's 19-trade / -$167.00 lifetime record belongs to SMT-v2 (deleted by TASK-STR-CLEANUP-002), not to this strategy, and must never be attributed to it. The phase-3 forward window is therefore the arbiter: 1% per-trade risk cap, the engine's -3% day-start-NAV daily breaker, max 4 open trades, and the kill criteria (expectancy<0 or PF<1.0 after >=50 closed trades, or strategy drawdown >5% of equity) auto-pause via measurement/forward_guard.py, evaluated by the OANDA engine on its own scan cadence. Entries additionally require this registry entry: the OANDA engine fails closed for any unregistered or non-VALIDATED configuration. PRACTICE account only; live trading prohibited.",
    },
    "sleeve_shock_breakout": {
        "status": "VALIDATED",
        "version": "v1.0.0 (TASK-STR-FWD-002 sleeve)",
        "timeframe": "1wk",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Weekly bar close moves more than 1.0 x ATR(14) versus the prior weekly close: up-move -> LONG, down-move -> SHORT (rigorous_backtest/rd2/families3.py sig_shock k=1.0). Weekly bars are the JUDGED construction: 7-day buckets anchored per symbol at WEEKLY_BUCKET_ANCHORS (the RD-002 series starts), rebuilt by the daemon from daily bars — NOT Binance Monday-anchored native weekly klines. Warmup 104 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.4267,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 904.0,
        "minimum_required_edge": 0.0005,
        "validated_assets": CRYPTO30_SYMBOLS,
        "sleeve": SLEEVE_NAME,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        # TASK-STR-FWD-012: judged stop is 2.0 x weekly ATR — genuine
        # stops ~16-36% of price, structurally above the 15%
        # engine-global cap, which rejected every firing in the leg's
        # life (28 detections, 0 executions to 2026-11-17). 0.90 =
        # sanity bound only (FWD-006 sizes by risk / stop distance).
        "max_stop_pct": 0.90,
        "reason": "Crypto leg of the RD-002 Stage-C best-per-class sleeve (owner-approved third forward entrant 2026-11-15, TASK-STR-FWD-002 extension). As a standalone cell it did NOT pass the promotion bar (109 OOS trades, PF 1.575, 3/5 folds) — it trades ONLY as a sleeve component, judged on the sleeve's compounded equity + max drawdown, with the sleeve-level kill rule (combined sleeve MARK-TO-MARKET DD > 5% of the combined venue equity of the accounts the sleeve trades on -> auto-pause all sleeve components; TASK-STR-FWD-006). Sizing per the FWD-006 package: 0.1% per-trade risk on venue equity, 2% heat cap. DEMO venue only; live trading prohibited.",
    },
    "sleeve_tsmom2_dual": {
        "status": "VALIDATED",
        "version": "v1.0.0 (TASK-STR-FWD-002 sleeve)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "ROC(90) crosses zero with price on the same side of EMA(200): ROC up-cross + close > EMA200 -> LONG; ROC down-cross + close < EMA200 -> SHORT (rigorous_backtest/rd2/families2.py sig_dual_momentum lookback=90). Warmup 260 bars. Executed by oanda_demo/sleeve_runner.py (governed here, the single source); the Binance daemon never evaluates it (no daemon module exists by design).",
        "sl_method": "2.5 * ATR(14) at signal bar (judged bracket)",
        "tp_method": "5.0 * ATR(14) at signal bar (judged bracket)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": None,
        "total_friction_bps": 6.0,
        "expected_net_edge_bps": 62.0,
        "minimum_required_edge": 0.0005,
        "validated_assets": FOREX28_SYMBOLS,
        "sleeve": SLEEVE_NAME,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "reason": "Forex leg of the RD-002 Stage-C best-per-class sleeve (owner-approved 2026-11-15). Standalone cell: 127 OOS trades, PF 1.505, +0.62%/trade — sleeve component only, judged on the sleeve. All 28 FOREX28 instruments verified present on the OANDA practice account 2026-11-15. Production bars are OANDA UTC-midnight-aligned daily candles (dailyAlignment=0) vs Yahoo research bars — same alignment convention, venue-canonical price source (disclosed deviation). Sizing per the TASK-STR-FWD-006 package: 0.1% per-trade risk on account NAV, 2% aggregate heat cap across the leg's open trades; the sleeve is judged mark-to-market (closed + unrealized, both legs combined) by the daemon guard. DEMO (practice) only; live trading prohibited.",
    },
    "sleeve_vol_adaptive_trend": {
        "status": "DISABLED",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "reason": "EXCLUDED from the forward sleeve (TASK-STR-FWD-002, 2026-11-15): the commodities leg of the RD-002 Stage-C best-per-class set (vol_adaptive_trend/ema20_50_gate @ comm7 4h, judged stream +25.9%) cannot be traded — the OANDA practice account holds ZERO commodity instruments (verified live 2026-11-15: 68 instruments, all currency pairs; no XAU/XAG/oil/gas/copper/platinum). No substitute venue or instrument is used: a silently substituted leg under the judged sleeve's name is prohibited. Revisit only if the account gains commodity instruments.",
    },
    "sleeve_keltner_breakout": {
        "status": "DISABLED",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "reason": "EXCLUDED from the forward sleeve (TASK-STR-FWD-002, 2026-11-15): the indices leg of the RD-002 Stage-C best-per-class set (keltner_breakout/ema20_m2.0 @ idx7 1d, judged stream +4.1%) cannot be traded — the OANDA practice account holds ZERO index instruments (verified live 2026-11-15: 68 instruments, all currency pairs; no SPX/NDX/DJI/RUT/FTSE/NIKKEI/DAX CFDs). No substitute venue or instrument is used. Revisit only if the account gains index instruments.",
    },
    # ------------------------------------------------------------------
    # TASK-STR-FWD-003: FORWARD-TEST lane (see the lane block above).
    # These are WATCHLIST configurations, not winners: mechanical bar
    # passed, Bonferroni failed. FORWARD_TEST != VALIDATED — demo
    # venues only, forward evidence decides them.
    # ------------------------------------------------------------------
    "bollinger_trend": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-003)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close crosses above SMA(50) + 2.0 x rolling-std(50). SHORT: close crosses below SMA(50) - 2.0 x rolling-std(50). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_bollinger_trend(df, 50, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3929,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 354.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "max_stop_pct": 0.50,
        "forward_lane": "FORWARD_TEST",
        "reason": "TASK-STR-RD-002 WATCHLIST: bollinger_trend/p50_sd2.0 @ CRYPTO30 1d passed the mechanical bar (expectancy +3.5448%/trade, PF 1.4562, 420 OOS trades, 5/5 positive folds, holdout) but FAILED Bonferroni significance at N=1,557 — not a promotion. Owner directed 2026-11-15 (TASK-STR-FWD-003) that near-bar configurations be decided by real demo forward evidence. FORWARD_TEST lane: DEMO venues only, phase-3 protocol (TASK-STR-FWD-006 package: 0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill criteria expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with the VALIDATED entrants' scorecards.",
    },
    "bollinger_trend_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-018)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close crosses above SMA(50) + 2.0 x rolling-std(50). SHORT: close crosses below SMA(50) - 2.0 x rolling-std(50). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_bollinger_trend(df, 50, warmup) on CRYPTO30 4h bars, warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3759,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 46.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": "TASK-STR-RD-002 near-miss re-audit 2026-11-18 (TASK-STR-FWD-018 wave 1): bollinger_trend/p50_sd2.0 @ CRYPTO30 4h — expectancy +0.4650%/trade, PF 1.1371, 3,211 pooled OOS trades, 4/5 positive folds, max symbol share 0.106 (grid_rows pooled_oos: bollinger_trend__p50_sd2.0__crypto30__4h). Admitted under the owner's second-tier demo-admission bar (2026-11-18: OOS expectancy>0, PF>=1.05, >=200 OOS trades, pre-Bonferroni); it does NOT pass the frozen promotion bar (PF>=1.2, >=4/5 folds, Bonferroni, holdout) — not a promotion. FORWARD_TEST lane terms as for bollinger_trend (demo venues only; FWD-006 package: 0.1% per-trade risk on venue equity, 2% heat cap, 3% daily breaker; kill at expectancy<0 or PF<1.0 after >=50 closed trades or MTM drawdown >5%; fills tagged FORWARD_TEST, never blended with the VALIDATED entrants' scorecards). FWD-012 stop-cap check (2026-11-18, harness signal bars over the full CRYPTO30 universe): signal-day judged stops (2.0 x ATR(14)) median 4.33%, p99 9.88%, max 17.82%, only 0.07% of judged signals above the 0.15 global cap — NO max_stop_pct override; the global cap binds as the sanity bound, as for the VALIDATED ichimoku_trend.",
    },
    "bollinger_trend_p20": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-018)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close crosses above SMA(20) + 2.0 x rolling-std(20). SHORT: close crosses below SMA(20) - 2.0 x rolling-std(20). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_bollinger_trend(df, 20, warmup) on CRYPTO30 1d bars, warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3513,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 126.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "max_stop_pct": 0.50,
        "forward_lane": "FORWARD_TEST",
        "reason": "TASK-STR-RD-002 near-miss re-audit 2026-11-18 (TASK-STR-FWD-018 wave 1): bollinger_trend/p20_sd2.0 @ CRYPTO30 1d — expectancy +1.2651%/trade, PF 1.1474, 632 pooled OOS trades, 3/5 positive folds, max symbol share 0.103 (grid_rows pooled_oos: bollinger_trend__p20_sd2.0__crypto30__1d). Admitted under the owner's second-tier demo-admission bar (2026-11-18: OOS expectancy>0, PF>=1.05, >=200 OOS trades, pre-Bonferroni); it does NOT pass the frozen promotion bar (PF>=1.2, >=4/5 folds, Bonferroni, holdout) — not a promotion. FORWARD_TEST lane terms as for bollinger_trend. FWD-012 stop-cap check (2026-11-18, harness signal bars over the full CRYPTO30 universe): signal-day judged stops (2.0 x ATR(14)) median 13.22%, p99 31.37%, max 36.24%, with 37.8% of judged signals above the 0.15 global cap — max_stop_pct 0.50 is set so the judged bracket is not silently clipped (a sanity bound above the measured distribution; under FWD-006 a wider stop shrinks the position, it does not add risk).",
    },
    "shock_breakout": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-003)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: one-bar close rise (close - close[-1]) > 1.0 x ATR(14) at the signal bar. SHORT: one-bar close fall > 1.0 x ATR(14). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_shock(df, 1.0, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3893,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 269.6,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "max_stop_pct": 0.50,
        "forward_lane": "FORWARD_TEST",
        "reason": "TASK-STR-RD-002 WATCHLIST: shock_breakout/k1.0 @ CRYPTO30 1d passed the mechanical bar (expectancy +2.6957%/trade, PF 1.3179, 732 OOS trades, 4/5 positive folds, holdout) but FAILED Bonferroni significance at N=1,557 — not a promotion. Owner directed 2026-11-15 (TASK-STR-FWD-003) that near-bar configurations be decided by real demo forward evidence. FORWARD_TEST lane terms as for bollinger_trend. (Distinct from sleeve_shock_breakout, the sleeve's own component module/configuration — different judged object, different records.)",
    },
    "shock_breakout_k15": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-018)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: one-bar close rise (close - close[-1]) > 1.5 x ATR(14) at the signal bar. SHORT: one-bar close fall > 1.5 x ATR(14). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_shock(df, 1.5, warmup) on CRYPTO30 1d bars, warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.4033,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 281.1,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "max_stop_pct": 0.50,
        "forward_lane": "FORWARD_TEST",
        "reason": "TASK-STR-RD-002 near-miss re-audit 2026-11-18 (TASK-STR-FWD-018 wave 1): shock_breakout/k1.5 @ CRYPTO30 1d — expectancy +2.8113%/trade, PF 1.3325, 486 pooled OOS trades, 3/5 positive folds, max symbol share 0.120 (grid_rows pooled_oos: shock_breakout__k1.5__crypto30__1d). Admitted under the owner's second-tier demo-admission bar (2026-11-18: OOS expectancy>0, PF>=1.05, >=200 OOS trades, pre-Bonferroni); it does NOT pass the frozen promotion bar (PF>=1.2, >=4/5 folds, Bonferroni, holdout) — not a promotion. FORWARD_TEST lane terms as for bollinger_trend. The family's 4h cells are NOT admitted (k1.0@4h expectancy -0.0315% / PF 0.9918; k1.5@4h expectancy -0.0820% / PF 0.9786 — below the tier on their own records). FWD-012 stop-cap check (2026-11-18, harness signal bars over the full CRYPTO30 universe): signal-day judged stops (2.0 x ATR(14)) median 12.81%, p99 32.46%, max 36.24%, with 33.7% of judged signals above the 0.15 global cap — max_stop_pct 0.50 is set so the judged bracket is not silently clipped (a sanity bound above the measured distribution; under FWD-006 a wider stop shrinks the position, it does not add risk).",
    },
    "adx_ema_bare": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-003)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "The production strategy_adx_ema module's OWN signals (EMA20/50 cross + EMA200 trend gate + ADX(14) > 20, plus the qualified-retest entry), evaluated exactly as the judged harness did (module.add_features over the frame, get_signal on trailing <=500-bar windows), with NO downstream filter. The PRODUCTION configuration adds rd/stage2 LONG_ONLY + BTC-regime filtering and is a different judged object; it remains OBSERVE_ONLY under its own phase-3 measurement and its records are never blended with this lane's.",
        "sl_method": "3.0 * ATR(14) (module bracket, ADX_EMA_STRATEGY_V2)",
        "tp_method": "3.0 * ATR(14) (module bracket, ADX_EMA_STRATEGY_V2)",
        "rr_ratio": 1.0,
        "oos_win_rate_prior": 0.5699,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 79.6,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": "TASK-STR-RD-002 WATCHLIST: adx_ema BARE @ CRYPTO30 4h passed the mechanical bar (expectancy +0.7955%/trade, PF 1.2332, 837 OOS trades, 4/5 positive folds, untouched-holdout expectancy +0.9428%) but FAILED Bonferroni significance at N=1,557 — not a promotion. (The production configuration measured PF 1.197, sub-bar, and was not a candidate.) Owner directed 2026-11-15 (TASK-STR-FWD-003) that near-bar configurations be decided by real demo forward evidence. FORWARD_TEST lane terms as for bollinger_trend. Judged geometry is RR 1.0 by construction (3.0x/3.0x ATR bracket); forward-protocol strategies are exempt from the daemon's generic min-RR pre-filter for exactly this reason — the expectancy gate and kill criteria still apply.",
    },
    # ------------------------------------------------------------------
    # TASK-STR-FWD-021 (2026-11-18): RD-014 vol-target overlay lane.
    # The 21 two-tier rows of TASK-STR-RD-014 are signal + vol-target +
    # drawdown-brake OVERLAYS, not standalone configs (their standalone
    # backtest drawdowns run -0.79...-1.00; the brake is integral to
    # the judged object). They execute via the daemon's overlay
    # manager (execution_mode "overlay"; core overlay_service.py,
    # ported line-faithfully from rigorous_backtest/rd14/family14.py).
    # No strategy_*.py module exists for these entries and no SL/TP
    # bracket is invented for them. Admission record: the near-miss
    # re-audit (REPORT §1.3/§3) under the owner's two-tier rule.
    # ------------------------------------------------------------------
    "overlay_ema10_50_vt15_none_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "ema10_50", "vol_target": 0.15, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.15 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3079,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 25.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): ema10_50_vt15_none @ CRYPTO30 1d — 643 OOS episodes, expectancy +0.255%/episode, PF 1.1507, win rate 0.3079, 4/5 positive folds, standalone max drawdown -0.875 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_ema10_50_vt30_none_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "ema10_50", "vol_target": 0.3, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.3 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3033,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 47.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): ema10_50_vt30_none @ CRYPTO30 1d — 643 OOS episodes, expectancy +0.475%/episode, PF 1.1403, win rate 0.3033, 4/5 positive folds, standalone max drawdown -0.991 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_ema10_50_vt60_none_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "ema10_50", "vol_target": 0.6, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.6 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.2939,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 56.6,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): ema10_50_vt60_none @ CRYPTO30 1d — 643 OOS episodes, expectancy +0.566%/episode, PF 1.0889, win rate 0.2939, 3/5 positive folds, standalone max drawdown -1.000 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_ema20_100_vt15_none_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "ema20_100", "vol_target": 0.15, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.15 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3810,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 58.8,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): ema20_100_vt15_none @ CRYPTO30 1d — 273 OOS episodes, expectancy +0.588%/episode, PF 1.2997, win rate 0.3810, 2/5 positive folds, standalone max drawdown -0.811 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_ema20_100_vt30_none_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "ema20_100", "vol_target": 0.3, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.3 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3590,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 93.6,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): ema20_100_vt30_none @ CRYPTO30 1d — 273 OOS episodes, expectancy +0.936%/episode, PF 1.2370, win rate 0.3590, 2/5 positive folds, standalone max drawdown -0.978 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_ema20_100_vt60_half_10_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "ema20_100", "vol_target": 0.6, "brake": "half_10", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.6 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: half_10). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3480,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 54.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): ema20_100_vt60_half_10 @ CRYPTO30 1d — 273 OOS episodes, expectancy +0.545%/episode, PF 1.1424, win rate 0.3480, 3/5 positive folds, standalone max drawdown -0.988 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_ema20_100_vt60_none_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "ema20_100", "vol_target": 0.6, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.6 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3187,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 65.9,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): ema20_100_vt60_none @ CRYPTO30 1d — 273 OOS episodes, expectancy +0.659%/episode, PF 1.0852, win rate 0.3187, 3/5 positive folds, standalone max drawdown -1.000 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_tsmom42_vt15_half_10_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "tsmom42", "vol_target": 0.15, "brake": "half_10", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.15 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: half_10). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3402,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 9.4,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): tsmom42_vt15_half_10 @ CRYPTO30 1d — 1708 OOS episodes, expectancy +0.094%/episode, PF 1.1651, win rate 0.3402, 2/5 positive folds, standalone max drawdown -0.795 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_tsmom42_vt15_none_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "tsmom42", "vol_target": 0.15, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.15 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3396,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 20.8,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): tsmom42_vt15_none @ CRYPTO30 1d — 1708 OOS episodes, expectancy +0.208%/episode, PF 1.2474, win rate 0.3396, 3/5 positive folds, standalone max drawdown -0.873 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_tsmom42_vt30_half_10_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "tsmom42", "vol_target": 0.3, "brake": "half_10", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.3 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: half_10). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3320,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 14.7,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): tsmom42_vt30_half_10 @ CRYPTO30 1d — 1708 OOS episodes, expectancy +0.147%/episode, PF 1.1541, win rate 0.3320, 3/5 positive folds, standalone max drawdown -0.926 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_tsmom42_vt30_none_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "tsmom42", "vol_target": 0.3, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.3 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3355,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 42.1,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): tsmom42_vt30_none @ CRYPTO30 1d — 1708 OOS episodes, expectancy +0.421%/episode, PF 1.2501, win rate 0.3355, 3/5 positive folds, standalone max drawdown -0.988 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_tsmom42_vt60_half_10_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "tsmom42", "vol_target": 0.6, "brake": "half_10", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.6 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: half_10). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3314,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 28.1,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): tsmom42_vt60_half_10 @ CRYPTO30 1d — 1708 OOS episodes, expectancy +0.281%/episode, PF 1.1758, win rate 0.3314, 3/5 positive folds, standalone max drawdown -0.995 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_tsmom42_vt60_none_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "tsmom42", "vol_target": 0.6, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.6 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3285,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 74.1,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): tsmom42_vt60_none @ CRYPTO30 1d — 1708 OOS episodes, expectancy +0.741%/episode, PF 1.2366, win rate 0.3285, 3/5 positive folds, standalone max drawdown -1.000 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_tsmom126_vt15_none_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "tsmom126", "vol_target": 0.15, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.15 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.2983,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 2.8,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): tsmom126_vt15_none @ CRYPTO30 4h — 5961 OOS episodes, expectancy +0.028%/episode, PF 1.0639, win rate 0.2983, 3/5 positive folds, standalone max drawdown -0.969 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_tsmom126_vt30_none_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "tsmom126", "vol_target": 0.3, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.3 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.2961,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 5.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): tsmom126_vt30_none @ CRYPTO30 4h — 5961 OOS episodes, expectancy +0.055%/episode, PF 1.0637, win rate 0.2961, 3/5 positive folds, standalone max drawdown -0.999 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_tsmom126_vt60_half_10_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "tsmom126", "vol_target": 0.6, "brake": "half_10", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.6 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: half_10). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.2949,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 5.3,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): tsmom126_vt60_half_10 @ CRYPTO30 4h — 5961 OOS episodes, expectancy +0.053%/episode, PF 1.0690, win rate 0.2949, 3/5 positive folds, standalone max drawdown -0.998 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_tsmom126_vt60_none_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "tsmom126", "vol_target": 0.6, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.6 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.2907,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 11.2,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): tsmom126_vt60_none @ CRYPTO30 4h — 5961 OOS episodes, expectancy +0.112%/episode, PF 1.0730, win rate 0.2907, 3/5 positive folds, standalone max drawdown -1.000 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_tsmom42_vt15_none_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "tsmom42", "vol_target": 0.15, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.15 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3061,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 2.9,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): tsmom42_vt15_none @ CRYPTO30 4h — 10474 OOS episodes, expectancy +0.029%/episode, PF 1.0804, win rate 0.3061, 3/5 positive folds, standalone max drawdown -0.948 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_tsmom42_vt30_none_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "tsmom42", "vol_target": 0.3, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.3 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3044,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 5.8,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): tsmom42_vt30_none @ CRYPTO30 4h — 10474 OOS episodes, expectancy +0.058%/episode, PF 1.0810, win rate 0.3044, 3/5 positive folds, standalone max drawdown -0.998 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_tsmom42_vt60_half_10_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "tsmom42", "vol_target": 0.6, "brake": "half_10", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.6 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: half_10). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.3007,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 4.6,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): tsmom42_vt60_half_10 @ CRYPTO30 4h — 10474 OOS episodes, expectancy +0.046%/episode, PF 1.0689, win rate 0.3007, 4/5 positive folds, standalone max drawdown -0.999 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    "overlay_tsmom42_vt60_none_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-021)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "execution_mode": "overlay",
        "overlay": {"signal": "tsmom42", "vol_target": 0.6, "brake": "none", "cost_per_turnover": 0.0008},
        "overlay_capital_pct": 0.005,
        "entry_conditions": "Continuous target weight w = signal x min(1, 0.6 / sigma_42) fixed at each bar close and held over the next bar, scaled by the drawdown-brake multiplier m from the configuration's own unbraked (shadow) per-symbol equity drawdown (brake: none). Judged: rigorous_backtest/rd14/family14.py; live core: overlay_service.py (line-faithful port, equivalence-tested).",
        "sl_method": "None — the judged RD-014 object has no stop bracket; risk control is the vol-target sizing plus the drawdown brake. No bracket is invented.",
        "tp_method": "None — exits are signal- and brake-driven, per the judged object.",
        "oos_win_rate_prior": 0.2987,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 11.7,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": 'TASK-STR-RD-014 two-tier admission (owner rule 2026-11-18): tsmom42_vt60_none @ CRYPTO30 4h — 10474 OOS episodes, expectancy +0.117%/episode, PF 1.0908, win rate 0.2987, 4/5 positive folds, standalone max drawdown -1.000 (the overlay\'s vol-target sizing and drawdown brake are integral to the judged object — it is NOT admitted as a standalone config). Passed the second tier (expectancy>0, PF>=1.05, >=200 episodes, pre-Bonferroni); it did NOT pass the frozen full bar. FORWARD_TEST lane (TASK-STR-FWD-021): DEMO venues only, phase-3 protocol package, fills tagged FORWARD_TEST, never blended with the VALIDATED entrants\' scorecards. Execution is by the daemon\'s overlay manager (execution_mode "overlay"), NOT the bracket signal path — the judged object has no SL/TP and none is invented. Sizing: virtual book = overlay_capital_pct (0.005) x venue equity; a symbol\'s target notional is m x w x book. Disclosed translations: the judged books are per-symbol standalone equity curves while live the 21 configurations share one demo account and one venue position per symbol (contention is skipped and logged, never forced); at a 0.5% book the venue-level 5% MTM drawdown kill cannot bind on a single overlay configuration, so the operative protections are the judged brake itself and the expectancy/PF kill after >=50 closed fills; targets below the manager\'s $10 notional floor are skipped and logged. Kill criteria otherwise unchanged (expectancy<0 or PF<1.0 after >=50 closed, or MTM drawdown >5% of venue equity).',
    },
    # ------------------------------------------------------------------
    # TASK-STR-FWD-022 (2026-11-18): WF-SELECTION lane entrant. The
    # entrant is a selection PROCEDURE (Appendix A of the near-miss
    # re-audit), not a fixed configuration; wf_select_service.py runs
    # the judged selection rule per epoch and the module trades the
    # current pick. Its forward record is its own.
    # ------------------------------------------------------------------
    "wf_select_tsmom": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-022)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "execution_mode": "wf_select",
        "wf_select": {"procedure": "ts_momentum__crypto30__1d", "epoch": "calendar_month_utc"},
        "entry_conditions": "Walk-forward selection procedure, not a fixed config: at each calendar-month (UTC) epoch the judged rule (expanding in-sample window over bars closed before the epoch; rank variants roc24/roc42/roc72/roc168 by profit_factor_net, then win rate; top 1) picks the ts_momentum variant for the epoch; the module then trades that variant's ROC sign-cross entries. Judged: rigorous_backtest/rd/common.py wf_select_judge over rd2 grid streams; live machinery: wf_select_service.py (line-faithful ports, equivalence-tested).",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3664,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 141.0,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "reason": "TASK-STR-RD-002 WALK-FORWARD SELECTION PROCEDURE (near-miss re-audit Appendix A): ts_momentum @ CRYPTO30 1d, judged by rd/common.py wf_select_judge (expanding in-sample window; per fold, rank variants by profit_factor_net then win_rate, take top 1) — pooled OOS record of the picks (roc24/roc168/roc72/roc42/roc42): 453 trades, expectancy +1.4096%/trade, PF 1.1694, win rate 0.3664, 3/5 positive folds. Meets the owner's second tier (expectancy>0, PF>=1.05, >=200 trades, pre-Bonferroni); it is NOT a full-bar promotion. Owner directed 2026-11-18 (implement-all) that tier-meeting procedures run on demo as FORWARD_TEST entrants. Execution: wf_select_service.py re-runs the judged selection rule at each calendar-month (UTC) epoch over bars closed before the epoch start, persists the pick (data/wf_select/ state + append-only selection log with the full in-sample table), and strategy_wf_select_tsmom trades the picked variant's judged entries with the BR24 bracket. The procedure's fills carry its own strategy name — its forward record is never blended with fixed ts_momentum configurations. Disclosed translations: live in-sample history is the venue candle history (1500 bars requested), not the judged cache from 2022 — the span used is logged per selection; trades still open at an epoch boundary are marked at the last pre-epoch close (the simulator's END_OF_DATA rule) where the retrospective record used final outcomes; the monthly epoch cadence is a declared service parameter (the judged W1-W5 windows were the judgement calendar). FORWARD_TEST lane terms as for bollinger_trend (demo venues only, 0.1% per-trade risk, 2% heat cap, 3% daily breaker, kill criteria expectancy<0 or PF<1.0 after >=50 closed trades or MTM drawdown >5% of venue equity).",
    },
    # -- Ensemble books (TASK-STR-EXP-002, slice 2) ---------------------------
    # Equal-weight combinations of judged member streams (RD-025 §5 / the
    # self-experiment loop's first-light book). Each book trades ONE net
    # position per (strategy, symbol): net = #LONG members - #SHORT
    # members; the bracket is the equal-weight mean of the same-direction
    # signalling members' judged brackets. The judged pooled figures in
    # each reason are the UNION of member trades (incl. simultaneous
    # opposite legs on one symbol) — the live book is a different trading
    # object; its forward demo record, not the judged union, is its
    # evidence. All 8 books are registered but INERT until their member
    # modules merge (see each entry's "execution" stamp) and the book
    # module is appended to S1's STRATEX_STRATEGY_ALLOWLIST at deploy.
    "ensemble_book_3905": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-EXP-002)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Ensemble book SHK+DON: equal-weight combination of shock_breakout k1.5 and donchian_turtle n55_b26, both @ crypto30 1d. Per symbol: net = #LONG - #SHORT members; net > 0 -> LONG, net < 0 -> SHORT, net == 0 -> no position. Bracket = equal-weight mean of the same-direction signalling members' judged brackets.",
        "sl_method": "Equal-weight mean of signalling members' judged stop brackets (shock 2.0x ATR(14), donchian 2.0x ATR(14))",
        "tp_method": "Equal-weight mean of signalling members' judged target brackets (shock 4.0x ATR(14), donchian 6.0x ATR(14))",
        "rr_ratio": 2.5,
        "oos_win_rate_prior": 0.3839,
        "oos_trades": 784,
        "oos_profit_factor": 1.4548,
        "oos_folds": "4/5",
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 193.8,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "max_stop_pct": 0.50,
        "forward_lane": "FORWARD_TEST",
        "members": [
            {"module": "strategy_shock_breakout_k15", "key": "shock_breakout", "cell": "k1.5", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 4.0},
            {"module": "strategy_donchian_turtle", "key": "donchian_turtle", "cell": "n55_b26", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 6.0},
        ],
        "execution": "PENDING_WAVE_PR_MERGE: #996 (shock k1.5), #987 (donchian)",
        "reason": "TASK-STR-RD-025 PROVEN ensemble, RD-025 trial 3905, SHK+DON: pooled expectancy +1.9383%/trade, PF 1.4548, 784 OOS trades, 4/5 positive folds, Bonferroni pass at round N=3,979, holdout pass. Members judged on the RD-002 records (shock k1.5: 486 trades, PF 1.3325; donchian n55_b26: 298 trades, PF 1.6502). FORWARD_TEST lane terms (0.1% per-trade risk on venue equity, 2% heat cap, 3% daily breaker; kill at expectancy < 0 or PF < 1.0 after >= 50 closed trades). LIVE-EXECUTION NOTE: the judged figures are the UNION of member trades; the live book holds one net position per symbol — offline measurement (verify_books.py) puts the netting gap at 14.9% of judged member position-days cancelled (10.9% of active days fully conflicted). Stop-cap (FWD-012, measured 2026-11-18 from judged signal bars, production Wilder ATR(14)): shock 33.7% / donchian 36.6% of signals above the 0.15 env cap, max 36.2% — override 0.50 covers the measured distribution (wave-1 value for this 1d universe).",
    },
    "ensemble_book_3906": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-EXP-002)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Ensemble book SHK+TSM: equal-weight combination of shock_breakout k1.5 and ts_momentum roc72, both @ crypto30 1d. Per symbol: net = #LONG - #SHORT members; net > 0 -> LONG, net < 0 -> SHORT, net == 0 -> no position. Bracket = equal-weight mean of the same-direction signalling members' judged brackets.",
        "sl_method": "Equal-weight mean of signalling members' judged stop brackets (shock 2.0x ATR(14), ts_momentum 2.0x ATR(14))",
        "tp_method": "Equal-weight mean of signalling members' judged target brackets (shock 4.0x ATR(14), ts_momentum 4.0x ATR(14))",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.4122,
        "oos_trades": 820,
        "oos_profit_factor": 1.4333,
        "oos_folds": "4/5",
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 172.4,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "max_stop_pct": 0.50,
        "forward_lane": "FORWARD_TEST",
        "members": [
            {"module": "strategy_shock_breakout_k15", "key": "shock_breakout", "cell": "k1.5", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 4.0},
            {"module": "strategy_ts_momentum", "key": "ts_momentum", "cell": "roc72", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 4.0},
        ],
        "execution": "PENDING_WAVE_PR_MERGE: #996 (shock k1.5), #991 (ts_momentum)",
        "reason": "TASK-STR-RD-025 PROVEN ensemble, RD-025 trial 3906, SHK+TSM: pooled expectancy +1.7244%/trade, PF 1.4333, 820 OOS trades, 4/5 positive folds, Bonferroni pass at round N=3,979, holdout pass. Members judged on the RD-002 records (shock k1.5: 486 trades, PF 1.3325; ts_momentum roc72: 334 trades, PF 1.6049, 5/5 folds). FORWARD_TEST lane terms (0.1% per-trade risk on venue equity, 2% heat cap, 3% daily breaker; kill at expectancy < 0 or PF < 1.0 after >= 50 closed trades). LIVE-EXECUTION NOTE: the judged figures are the UNION of member trades; the live book holds one net position per symbol — offline measurement (verify_books.py) puts the netting gap at 7.9% of judged member position-days cancelled (5.1% of active days fully conflicted). Stop-cap (FWD-012, measured 2026-11-18): shock 33.7% / ts_momentum 23.6% of signals above the 0.15 env cap, max 36.2% — override 0.50 covers the measured distribution (wave-1 value for this 1d universe).",
    },
    "ensemble_book_3927": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-EXP-002)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Ensemble book VA+SHK+STO: equal-weight combination of vol_adaptive_trend ema12_26_nogate @ crypto30 1d, shock_breakout k1.5 @ crypto30 1d, and stoch_reversion k14_raw @ forex28 1d. Mixed panels: the book needs evaluation context (symbol/timeframe/venue). Per symbol: net = #LONG - #SHORT members; net > 0 -> LONG, net < 0 -> SHORT, net == 0 -> no position. Bracket = equal-weight mean of the same-direction signalling members' judged brackets.",
        "sl_method": "Equal-weight mean of signalling members' judged stop brackets (all members 2.0x ATR(14) except vol_adaptive 2.5x)",
        "tp_method": "Equal-weight mean of signalling members' judged target brackets (vol_adaptive 5.0x, shock 4.0x, stoch 4.0x ATR(14))",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.4096,
        "oos_trades": 1150,
        "oos_profit_factor": 1.4639,
        "oos_folds": "4/5",
        "total_friction_bps": [6.0, 10.0, 16.0],
        "expected_net_edge_bps": 96.7,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS + FOREX28_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "max_stop_pct": 0.60,
        "forward_lane": "FORWARD_TEST",
        "members": [
            {"module": "strategy_vol_adaptive_trend", "key": "vol_adaptive_trend", "cell": "ema12_26_nogate", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.5, "tp_atr": 5.0},
            {"module": "strategy_shock_breakout_k15", "key": "shock_breakout", "cell": "k1.5", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 4.0},
            {"module": "strategy_stoch_reversion", "key": "stoch_reversion", "cell": "k14_raw", "panel": "forex28", "timeframe": "1d", "venue": "oanda", "sl_atr": 2.0, "tp_atr": 4.0},
        ],
        "execution": "PENDING_WAVE_PR_MERGE: #983 (vol_adaptive), #996 (shock k1.5), #994 (stoch_reversion)",
        "reason": "TASK-STR-RD-025 PROVEN ensemble, RD-025 trial 3927, VA+SHK+STO: pooled expectancy +0.9665%/trade, PF 1.4639, 1150 OOS trades, 4/5 positive folds, Bonferroni pass at round N=3,979, holdout pass. Members judged on the RD-002 records (vol_adaptive: 299 trades, PF 1.6956; shock k1.5: 486 trades, PF 1.3325; stoch k14_raw @ forex28: 365 trades, PF 1.2623, best forex). FORWARD_TEST lane terms (0.1% per-trade risk on venue equity, 2% heat cap, 3% daily breaker; kill at expectancy < 0 or PF < 1.0 after >= 50 closed trades). LIVE-EXECUTION NOTE: the judged figures are the UNION of member trades; the live book holds one net position per symbol — offline measurement (verify_books.py) puts the netting gap at 7.2% of judged member position-days cancelled (4.4% of active days fully conflicted; the forex member never shares a symbol with the crypto members, so no partial days). Stop-cap (FWD-012, measured 2026-11-18): vol_adaptive 50.1% of signals above the 0.15 env cap (median stop 15.03%, max 49.22%) — override 0.60, not the wave-1 0.50, because 0.50 would leave a 0.78pp margin and reject future tail signals; shock 33.7% (max 36.2%); stoch-forex 0.02% (max 20.03%, no override needed on its own).",
    },
    "ensemble_book_3928": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-EXP-002)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Ensemble book DON+SHK+STO: equal-weight combination of donchian_turtle n55_b26 @ crypto30 1d, shock_breakout k1.5 @ crypto30 1d, and stoch_reversion k14_raw @ forex28 1d. Mixed panels: the book needs evaluation context (symbol/timeframe/venue). Per symbol: net = #LONG - #SHORT members; net > 0 -> LONG, net < 0 -> SHORT, net == 0 -> no position. Bracket = equal-weight mean of the same-direction signalling members' judged brackets.",
        "sl_method": "Equal-weight mean of signalling members' judged stop brackets (all members 2.0x ATR(14))",
        "tp_method": "Equal-weight mean of signalling members' judged target brackets (donchian 6.0x, shock 4.0x, stoch 4.0x ATR(14))",
        "rr_ratio": 2.3333,
        "oos_win_rate_prior": 0.3847,
        "oos_trades": 1149,
        "oos_profit_factor": 1.4440,
        "oos_folds": "4/5",
        "total_friction_bps": [6.0, 10.0, 16.0],
        "expected_net_edge_bps": 91.2,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS + FOREX28_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "max_stop_pct": 0.50,
        "forward_lane": "FORWARD_TEST",
        "members": [
            {"module": "strategy_donchian_turtle", "key": "donchian_turtle", "cell": "n55_b26", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 6.0},
            {"module": "strategy_shock_breakout_k15", "key": "shock_breakout", "cell": "k1.5", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 4.0},
            {"module": "strategy_stoch_reversion", "key": "stoch_reversion", "cell": "k14_raw", "panel": "forex28", "timeframe": "1d", "venue": "oanda", "sl_atr": 2.0, "tp_atr": 4.0},
        ],
        "execution": "PENDING_WAVE_PR_MERGE: #987 (donchian), #996 (shock k1.5), #994 (stoch_reversion)",
        "reason": "TASK-STR-RD-025 PROVEN ensemble, RD-025 trial 3928, DON+SHK+STO: pooled expectancy +0.9120%/trade, PF 1.4440, 1149 OOS trades, 4/5 positive folds, Bonferroni pass at round N=3,979, holdout pass. Members judged on the RD-002 records (donchian n55_b26: 298 trades, PF 1.6502; shock k1.5: 486 trades, PF 1.3325; stoch k14_raw @ forex28: 365 trades, PF 1.2623). FORWARD_TEST lane terms (0.1% per-trade risk on venue equity, 2% heat cap, 3% daily breaker; kill at expectancy < 0 or PF < 1.0 after >= 50 closed trades). LIVE-EXECUTION NOTE: the judged figures are the UNION of member trades; the live book holds one net position per symbol — offline measurement (verify_books.py) puts the netting gap at 9.2% of judged member position-days cancelled (5.7% of active days fully conflicted). Stop-cap (FWD-012, measured 2026-11-18): donchian 36.6% / shock 33.7% of signals above the 0.15 env cap, max 36.2% — override 0.50 covers the measured distribution (wave-1 value for this 1d universe); stoch-forex 0.02% (max 20.03%, no override needed on its own).",
    },
    "ensemble_book_3929": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-EXP-002)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Ensemble book TSM+SHK+STO: equal-weight combination of ts_momentum roc72 @ crypto30 1d, shock_breakout k1.5 @ crypto30 1d, and stoch_reversion k14_raw @ forex28 1d. Mixed panels: the book needs evaluation context (symbol/timeframe/venue). Per symbol: net = #LONG - #SHORT members; net > 0 -> LONG, net < 0 -> SHORT, net == 0 -> no position. Bracket = equal-weight mean of the same-direction signalling members' judged brackets.",
        "sl_method": "Equal-weight mean of signalling members' judged stop brackets (all members 2.0x ATR(14))",
        "tp_method": "Equal-weight mean of signalling members' judged target brackets (all members 4.0x ATR(14))",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.4042,
        "oos_trades": 1185,
        "oos_profit_factor": 1.4235,
        "oos_folds": "4/5",
        "total_friction_bps": [6.0, 10.0, 16.0],
        "expected_net_edge_bps": 82.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS + FOREX28_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "max_stop_pct": 0.50,
        "forward_lane": "FORWARD_TEST",
        "members": [
            {"module": "strategy_ts_momentum", "key": "ts_momentum", "cell": "roc72", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 4.0},
            {"module": "strategy_shock_breakout_k15", "key": "shock_breakout", "cell": "k1.5", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 4.0},
            {"module": "strategy_stoch_reversion", "key": "stoch_reversion", "cell": "k14_raw", "panel": "forex28", "timeframe": "1d", "venue": "oanda", "sl_atr": 2.0, "tp_atr": 4.0},
        ],
        "execution": "PENDING_WAVE_PR_MERGE: #991 (ts_momentum), #996 (shock k1.5), #994 (stoch_reversion)",
        "reason": "TASK-STR-RD-025 PROVEN ensemble, RD-025 trial 3929, TSM+SHK+STO: pooled expectancy +0.8249%/trade, PF 1.4235, 1185 OOS trades, 4/5 positive folds, Bonferroni pass at round N=3,979, holdout pass. Members judged on the RD-002 records (ts_momentum roc72: 334 trades, PF 1.6049, 5/5 folds; shock k1.5: 486 trades, PF 1.3325; stoch k14_raw @ forex28: 365 trades, PF 1.2623). FORWARD_TEST lane terms (0.1% per-trade risk on venue equity, 2% heat cap, 3% daily breaker; kill at expectancy < 0 or PF < 1.0 after >= 50 closed trades). LIVE-EXECUTION NOTE: the judged figures are the UNION of member trades; the live book holds one net position per symbol — offline measurement (verify_books.py) puts the netting gap at 4.3% of judged member position-days cancelled (2.4% of active days fully conflicted), the smallest of the 8 books. Stop-cap (FWD-012, measured 2026-11-18): ts_momentum 23.6% / shock 33.7% of signals above the 0.15 env cap, max 36.2% — override 0.50 covers the measured distribution (wave-1 value for this 1d universe); stoch-forex 0.02% (max 20.03%, no override needed on its own).",
    },
    "ensemble_book_3933": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-EXP-002)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Ensemble book VA+SHK+XSL: equal-weight combination of vol_adaptive_trend ema12_26_nogate @ crypto30 1d, shock_breakout k1.5 @ crypto30 1d, and xs_lowvol lv20_r10 @ crypto30 1d. Per symbol: net = #LONG - #SHORT members; net > 0 -> LONG, net < 0 -> SHORT, net == 0 -> no position. Bracket = equal-weight mean of the same-direction signalling members' judged brackets.",
        "sl_method": "Equal-weight mean of signalling members' judged stop brackets (vol_adaptive 2.5x, shock 2.0x, xs_lowvol 2.0x ATR(14))",
        "tp_method": "Equal-weight mean of signalling members' judged target brackets (vol_adaptive 5.0x, shock 4.0x, xs_lowvol 4.0x ATR(14))",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.4672,
        "oos_trades": 1295,
        "oos_profit_factor": 1.4072,
        "oos_folds": "4/5",
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 92.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "max_stop_pct": 0.60,
        "forward_lane": "FORWARD_TEST",
        "members": [
            {"module": "strategy_vol_adaptive_trend", "key": "vol_adaptive_trend", "cell": "ema12_26_nogate", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.5, "tp_atr": 5.0},
            {"module": "strategy_shock_breakout_k15", "key": "shock_breakout", "cell": "k1.5", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 4.0},
            {"module": None, "key": "xs_lowvol", "cell": "lv20_r10", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 4.0, "unavailable_reason": "xs_lowvol is a cross-sectional rotation (rank 30 symbols by 20d vol, hold 3 lowest, rebalance every 10 bars), not a per-symbol signal strategy; it cannot be a member of a per-symbol ensemble book without xs rotation machinery"},
        ],
        "execution": "PENDING_XS_ROTATION_MACHINERY: xs_lowvol (cross-sectional; not a per-symbol member) + PENDING_WAVE_PR_MERGE: #983 (vol_adaptive), #996 (shock k1.5)",
        "reason": "TASK-STR-RD-025 PROVEN ensemble, RD-025 trial 3933, VA+SHK+XSL: pooled expectancy +0.9253%/trade, PF 1.4072, 1295 OOS trades, 4/5 positive folds, Bonferroni pass at round N=3,979, holdout pass. Members judged on the RD-002 records (vol_adaptive: 299 trades, PF 1.6956; shock k1.5: 486 trades, PF 1.3325; xs_lowvol lv20_r10: 510 trades, 275 wins — a CROSS-SECTIONAL rotation, rank 30 symbols by 20d vol, hold 3 lowest, rebalance every 10 bars; its trades ARE in the pooled figures). BLOCKED: xs_lowvol cannot be a member of a per-symbol ensemble book without xs rotation machinery — the book refuses whole (fail-closed, never a subset) until that machinery exists. FORWARD_TEST lane terms (0.1% per-trade risk on venue equity, 2% heat cap, 3% daily breaker; kill at expectancy < 0 or PF < 1.0 after >= 50 closed trades). LIVE-EXECUTION NOTE: the judged figures are the UNION of member trades; the live book holds one net position per symbol — offline measurement (verify_books.py, per-symbol members only) puts the netting gap at 12.0% of judged member position-days cancelled (8.3% of active days fully conflicted). Stop-cap (FWD-012, measured 2026-11-18): vol_adaptive 50.1% of signals above the 0.15 env cap (median stop 15.03%, max 49.22%) — override 0.60; shock 33.7% (max 36.2%).",
    },
    "ensemble_book_3978": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-EXP-002)",
        "timeframes": ["1d", "1wk"],
        "execution_model": "RULE_BASED",
        "entry_conditions": "Ensemble book DUAL+SHW+ZSC+HA1d+XSL (size 5): equal-weight combination of tsmom2_dual roc90_ema200 @ crypto30 1d, shock_breakout k1.0 @ crypto30 1wk, zscore_reversion w50_t2.5_filt @ forex28 1d, ha_trend two_candle @ crypto30 1d, and xs_lowvol lv20_r10 @ crypto30 1d. Mixed panels AND mixed timeframes (1d + 1wk): the book needs evaluation context (symbol/timeframe/venue) and the engine keeps a per-member signal cache across scans. Per symbol: net = #LONG - #SHORT members; net > 0 -> LONG, net < 0 -> SHORT, net == 0 -> no position. Bracket = equal-weight mean of the same-direction signalling members' judged brackets.",
        "sl_method": "Equal-weight mean of signalling members' judged stop brackets (all members 2.0x ATR(14) except tsmom2_dual 2.5x)",
        "tp_method": "Equal-weight mean of signalling members' judged target brackets (tsmom2_dual 5.0x, shock 4.0x, zscore 2.0x, ha_trend 4.0x, xs_lowvol 4.0x ATR(14))",
        "rr_ratio": 1.8,
        "oos_win_rate_prior": 0.4441,
        "oos_trades": 1698,
        "oos_profit_factor": 1.3262,
        "oos_folds": "4/5",
        "total_friction_bps": [6.0, 10.0, 16.0],
        "expected_net_edge_bps": 47.3,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS + FOREX28_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "max_stop_pct": 0.90,
        "forward_lane": "FORWARD_TEST",
        "members": [
            {"module": "strategy_tsmom2_dual_crypto_1d", "key": "tsmom2_dual", "cell": "roc90_ema200", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.5, "tp_atr": 5.0},
            {"module": "strategy_shock_breakout_1wk", "key": "shock_breakout", "cell": "k1.0", "panel": "crypto30", "timeframe": "1wk", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 4.0},
            {"module": "strategy_zscore_reversion", "key": "zscore_reversion", "cell": "w50_t2.5_filt", "panel": "forex28", "timeframe": "1d", "venue": "oanda", "sl_atr": 2.0, "tp_atr": 2.0},
            {"module": "strategy_ha_trend", "key": "ha_trend", "cell": "two_candle", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 4.0},
            {"module": None, "key": "xs_lowvol", "cell": "lv20_r10", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 4.0, "unavailable_reason": "xs_lowvol is a cross-sectional rotation (rank 30 symbols by 20d vol, hold 3 lowest, rebalance every 10 bars), not a per-symbol signal strategy; it cannot be a member of a per-symbol ensemble book without xs rotation machinery"},
        ],
        "execution": "PENDING_MEMBER_MODULES: strategy_tsmom2_dual_crypto_1d (DUAL 1d cell; PR #991 built the 4h cell only), strategy_shock_breakout_1wk (SHW), strategy_zscore_reversion (ZSC) + PENDING_XS_ROTATION_MACHINERY: xs_lowvol + PENDING_WAVE_PR_MERGE: #993 (ha_trend)",
        "reason": "TASK-STR-RD-025 PROVEN ensemble, RD-025 trial 3978, DUAL+SHW+ZSC+HA1d+XSL (size 5, Section E1 cluster-champion): pooled expectancy +0.4728%/trade, PF 1.3262, 1698 OOS trades, 4/5 positive folds, Bonferroni pass at round N=3,979, holdout pass; book drawdown -0.168, the shallowest of any proven book. Members judged on the RD-002 records (tsmom2_dual roc90_ema200 @ crypto30 1d: 174 trades, PF 1.8470 — NOT the 4h cell PR #991 built, and NOT the sleeve's forex28 leg; shock k1.0 @ 1wk: 109 trades, PF 1.5750; zscore w50_t2.5_filt @ forex28: 130 trades, PF 1.4759; ha_trend two_candle @ 1d: 775 trades, PF 1.1878; xs_lowvol lv20_r10: 510 trades, 275 wins — cross-sectional rotation, its trades ARE in the pooled figures). BLOCKED on four members (DUAL 1d / SHW / ZSC have no production module; xs_lowvol needs rotation machinery) — the book refuses whole (fail-closed, never a subset) until all exist. FORWARD_TEST lane terms (0.1% per-trade risk on venue equity, 2% heat cap, 3% daily breaker; kill at expectancy < 0 or PF < 1.0 after >= 50 closed trades). LIVE-EXECUTION NOTE: the judged figures are the UNION of member trades; the live book holds one net position per symbol — offline measurement (verify_books.py, per-symbol members only) puts the netting gap at 17.4% of judged member position-days cancelled (10.2% of active days fully conflicted, 1866 partial days). Stop-cap (FWD-012, measured 2026-11-18): the weekly member's judged stops reach 87.16% (94.97% of its 199 signals above the 0.15 env cap, median 28.18%) — override 0.90 (sleeve precedent for weekly geometry); tsmom2_dual 60.4% / ha_trend 36.5% of signals above cap (max 42.5% / 39.4%); zscore 0.00% (max 6.94%, no override needed on its own).",
    },
    "ensemble_book_3900": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-EXP-002)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Ensemble book VA+SHK10+STOc (loop first-light): equal-weight combination of vol_adaptive_trend ema12_26_nogate, shock_breakout k1.0, and stoch_reversion k14_raw — all @ crypto30 1d, all judged on the self-experiment loop's fixture store. Per symbol: net = #LONG - #SHORT members; net > 0 -> LONG, net < 0 -> SHORT, net == 0 -> no position. Bracket = equal-weight mean of the same-direction signalling members' judged brackets.",
        "sl_method": "Equal-weight mean of signalling members' judged stop brackets (vol_adaptive 2.5x, shock 2.0x, stoch 2.0x ATR(14))",
        "tp_method": "Equal-weight mean of signalling members' judged target brackets (vol_adaptive 5.0x, shock 4.0x, stoch 4.0x ATR(14))",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3921,
        "oos_trades": 1719,
        "oos_profit_factor": 1.2643,
        "oos_folds": "4/5",
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 81.3,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "max_stop_pct": 0.60,
        "forward_lane": "FORWARD_TEST",
        "self_experiment": True,
        "self_experiment_verdict": "PROVEN",
        "members": [
            {"module": "strategy_vol_adaptive_trend", "key": "vol_adaptive_trend", "cell": "ema12_26_nogate", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.5, "tp_atr": 5.0},
            {"module": "strategy_shock_breakout", "key": "shock_breakout", "cell": "k1.0", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 4.0},
            {"module": "strategy_stoch_reversion_crypto", "key": "stoch_reversion", "cell": "k14_raw", "panel": "crypto30", "timeframe": "1d", "venue": "binance_futures", "sl_atr": 2.0, "tp_atr": 4.0},
        ],
        "execution": "PENDING_WAVE_PR_MERGE: #983 (vol_adaptive), #994 (stoch_reversion crypto variant); shock k1.0 is on main",
        "reason": "TASK-STR-EXP-001 SELF-EXPERIMENT first-light book, loop trial 3900, VA+SHK10+STOc: the loop's own judge on its fixture store (6 real crypto30 1d streams, exporter-verified against the RD-002 records): pooled expectancy +0.8131%/trade, PF 1.2643, 1719 OOS trades, 4/5 positive folds, p ~1.2e-05 vs Bonferroni 1.28e-05 at N=3,900, holdout +2.91% -> PROVEN. These are the LOOP's recorded cells — NOT RD-025's k1.5 shock cell (book 3905) and NOT the forex28 stoch cell (book 3927): related but not identical books. The loop will admit this book to its own data-dir registry at activation under its own key (selfexp_combo_<sha12>); this config entry is the daemon-side executable registration of the same book — the two records coexist (different keys, no collision). FORWARD_TEST lane terms (0.1% per-trade risk on venue equity, 2% heat cap, 3% daily breaker; kill at expectancy < 0 or PF < 1.0 after >= 50 closed trades). LIVE-EXECUTION WARNING: this book's judged union diverges most from live netting of all 8 books — 45.2% of its judged member position-days would be cancelled by the one-net-position rule (its three crypto-1d members, one a reversion stream, oppose each other on 20.8% of active days; 7117 partial days). Expect the live book to trade far less often than the judged union suggests; the forward demo record is the arbiter. Stop-cap (FWD-012, measured 2026-11-18): vol_adaptive 50.1% of signals above the 0.15 env cap (median stop 15.03%, max 49.22%) — override 0.60; shock k1.0 34.7% (max 36.2%); stoch-crypto 33.4% (max 33.5%).",
    },
    "tsmom2_dual": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-003)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: ROC(30) crosses up through 0 AND close > EMA(200). SHORT: ROC(30) crosses down AND close < EMA(200). Judged: rigorous_backtest/rd2/families2.py sig_dual_momentum(df, 30, warmup) on the COMM7 Yahoo-futures panel (GOLD, SILVER, WTI, BRENT, NATGAS, COPPER, PLATINUM), warmup 260 bars.",
        "sl_method": "2.5 * ATR(14) at signal bar (judged bracket)",
        "tp_method": "5.0 * ATR(14) at signal bar (judged bracket)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3951,
        "total_friction_bps": 12.0,
        "expected_net_edge_bps": 55.8,
        "minimum_required_edge": 0.0005,
        "lane_assets": [],
        "validated_assets": [],
        "forward_protocol": False,
        "forward_lane": "FORWARD_TEST",
        "cost_fragile": True,
        "reason": "EXCLUDED from the lane (TASK-STR-FWD-003): the judged universe is Yahoo continuous FUTURES series (GC/SI/CL/BZ/NG/HG/PL). Neither demo venue can trade it — demo-fapi is crypto perpetuals only, and the OANDA practice account's own instrument list (queried live 2026-11-15) contains 68 instruments, ALL FX pairs: no metals, energy or commodity instruments exist on the account at all (and spot CFDs, where offered elsewhere, would still be different instruments from the judged futures series — substitution prohibited). No production module exists for this entry and lane_assets is empty: the registration is documentary, preserving the RD-002 evidence (+0.5581%/trade, PF 1.2026, 205 OOS trades, 4/5 folds, Bonferroni FAIL) and the exclusion reason. It can only join the lane if a demo venue offers the judged futures series themselves. (sleeve_tsmom2_dual is a different judged object — the sleeve's forex component — and is unaffected by this exclusion.) RD-003 CONFIRMATION (RESULTS_RD3.md SS4, PR #294): this is the programme's only 'mechanical bar passed, significance pending' configuration, re-run deterministically and reproduced BIT-IDENTICALLY (205 trades, expectancy +0.558%, PF 1.203); its 2x-cost PF is 1.149 — BELOW the 1.2 sensitivity line — recorded here as COST-FRAGILE.",
    },
    "vol_regime_switch_a": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-003 RD-003 additions)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Judged: TASK-STR-RD-003 vol_regime_switch/switch_a on the COMM7 Yahoo-futures panel (GOLD, SILVER, WTI, BRENT, NATGAS, COPPER, PLATINUM) at 1d. No production module exists (unmappable universe — see reason).",
        "oos_win_rate_prior": None,
        "total_friction_bps": 12.0,
        "expected_net_edge_bps": 117.3,
        "minimum_required_edge": 0.0005,
        "lane_assets": [],
        "validated_assets": [],
        "forward_protocol": False,
        "forward_lane": "FORWARD_TEST",
        "lane_note": "entered sample-starved; forward evidence is the settler",
        "reason": "EXCLUDED from live lane execution (TASK-STR-FWD-003, RD-003 additions): TASK-STR-RD-003 watchlist cell vol_regime_switch/switch_a @ comm7 1d — 151 OOS trades, expectancy +1.173%/trade, PF 1.372, 5 positive folds, max symbol profit share 0.39. It failed ONLY the >=200-trade floor (a data-span limit of the Yahoo comm7 history, not a performance failure) and failed Bonferroni significance. Entered sample-starved; forward evidence is the settler. The judged universe cannot be traded faithfully on either demo venue — demo-fapi is crypto perpetuals only, and the OANDA practice account's instrument list (queried live 2026-11-15) contains 68 instruments, ALL FX pairs: no metals, energy or commodity instruments exist on the account (spot CFDs, where offered elsewhere, would still differ from the judged futures series — substitution prohibited). Documentary registration only: no module, lane_assets empty; it can join the executable lane only if a demo venue offers the judged futures series themselves.",
    },
    "vol_regime_switch_b": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-003 RD-003 additions)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Judged: TASK-STR-RD-003 vol_regime_switch/switch_b on the COMM7 Yahoo-futures panel (GOLD, SILVER, WTI, BRENT, NATGAS, COPPER, PLATINUM) at 1d. No production module exists (unmappable universe — see reason).",
        "oos_win_rate_prior": None,
        "total_friction_bps": 12.0,
        "expected_net_edge_bps": 79.3,
        "minimum_required_edge": 0.0005,
        "lane_assets": [],
        "validated_assets": [],
        "forward_protocol": False,
        "forward_lane": "FORWARD_TEST",
        "lane_note": "entered sample-starved; forward evidence is the settler",
        "reason": "EXCLUDED from live lane execution (TASK-STR-FWD-003, RD-003 additions): TASK-STR-RD-003 watchlist cell vol_regime_switch/switch_b @ comm7 1d — 124 OOS trades, expectancy +0.793%/trade, PF 1.237, 5 positive folds, max symbol profit share 0.32. It failed ONLY the >=200-trade floor (a data-span limit, not a performance failure) and failed Bonferroni significance. Entered sample-starved; forward evidence is the settler. Unmappable-universe exclusion exactly as for vol_regime_switch_a: demo-fapi is crypto-only and the OANDA practice account holds 68 FX-only instruments (verified live 2026-11-15); substitution prohibited. Documentary registration only.",
    },
    "trend_pullback_ema100": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-003 RD-003 additions)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Judged: TASK-STR-RD-003 trend_pullback/pb_ema100 on the COMM7 Yahoo-futures panel (GOLD, SILVER, WTI, BRENT, NATGAS, COPPER, PLATINUM) at 1d. No production module exists (unmappable universe — see reason).",
        "oos_win_rate_prior": None,
        "total_friction_bps": 12.0,
        "expected_net_edge_bps": 76.6,
        "minimum_required_edge": 0.0005,
        "lane_assets": [],
        "validated_assets": [],
        "forward_protocol": False,
        "forward_lane": "FORWARD_TEST",
        "lane_note": "entered sample-starved; forward evidence is the settler",
        "reason": "EXCLUDED from live lane execution (TASK-STR-FWD-003, RD-003 additions): TASK-STR-RD-003 watchlist cell trend_pullback/pb_ema100 @ comm7 1d — 113 OOS trades, expectancy +0.766%/trade, PF 1.217, 3 positive folds, max symbol profit share 0.41. It failed ONLY the >=200-trade floor (a data-span limit, not a performance failure) and failed Bonferroni significance. Entered sample-starved; forward evidence is the settler. Unmappable-universe exclusion exactly as for vol_regime_switch_a: demo-fapi is crypto-only and the OANDA practice account holds 68 FX-only instruments (verified live 2026-11-15); substitution prohibited. Documentary registration only.",
    },
    "trend_pullback_ema200": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-003 RD-003 additions)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Judged: TASK-STR-RD-003 trend_pullback/pb_ema200 on the COMM7 Yahoo-futures panel (GOLD, SILVER, WTI, BRENT, NATGAS, COPPER, PLATINUM) at 1d. No production module exists (unmappable universe — see reason).",
        "oos_win_rate_prior": None,
        "total_friction_bps": 12.0,
        "expected_net_edge_bps": 64.2,
        "minimum_required_edge": 0.0005,
        "lane_assets": [],
        "validated_assets": [],
        "forward_protocol": False,
        "forward_lane": "FORWARD_TEST",
        "lane_note": "entered sample-starved; forward evidence is the settler",
        "reason": "EXCLUDED from live lane execution (TASK-STR-FWD-003, RD-003 additions): TASK-STR-RD-003 watchlist cell trend_pullback/pb_ema200 @ comm7 1d — 109 OOS trades, expectancy +0.642%/trade, PF 1.182, 3 positive folds, max symbol profit share 0.37. It failed ONLY the >=200-trade floor (a data-span limit, not a performance failure) and failed Bonferroni significance; its PF of 1.182 is also marginally below the 1.2 line, recorded exactly as measured. Entered sample-starved; forward evidence is the settler. Unmappable-universe exclusion exactly as for vol_regime_switch_a: demo-fapi is crypto-only and the OANDA practice account holds 68 FX-only instruments (verified live 2026-11-15); substitution prohibited. Documentary registration only.",
    },
    # ------------------------------------------------------------------
    # TASK-STR-FWD-019 WAVE-2 gap-fill: the two ts_momentum FOREX cells
    # (near-miss audit §1.4 rows 30 and 68). Executable ONLY through
    # the OANDA forward-test runner (PR #980) on the practice venue —
    # forward_venues is the runner's discovery key.
    # ------------------------------------------------------------------
    "ts_momentum_roc72_fx28": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: ROC(72) = close/close[-72] - 1 crosses up through 0 (roc > 0 and prior-bar roc <= 0). SHORT: ROC(72) crosses down through 0 (roc < 0 and prior-bar roc >= 0). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_ts_momentum(df, 72, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3673,
        "total_friction_bps": 6.0,
        "expected_net_edge_bps": 18.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": FOREX28_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "forward_venues": ["oanda_practice"],
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): ts_momentum/roc72 @ FOREX28 1d meets the second tier (OOS expectancy +0.185%/trade, PF 1.1735, 226 OOS trades, 3/5 positive folds, PF @2x costs 1.0944) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Execution rides the OANDA FORWARD_TEST runner (PR #980); the module name strategy_ts_momentum_roc72_fx28 must be added to STRATEX_STRATEGY_ALLOWLIST on S1 at deploy. Distinct judged object from ts_momentum/roc72 @ CRYPTO30 1d (TASK-STR-FWD-019 crew A, PR #991) — same judged signal function (families2 sig_ts_momentum), different panel cell and records; never blended. RD-002 cost basis (rigorous_backtest/rd2/costs2.py, recorded per-symbol in the cell's grid row): 6 bps round trip on the majors, 10 bps on the crosses/minors; the registry friction field carries the 6.0 majors figure following the sleeve_tsmom2_dual / bollinger_trend_p20_fx28 precedent for this panel. FWD-012 stop check: measured max 2.0 x ATR(14)/close on the fwd002 FX fixtures (FX_EURUSD/FX_GBPJPY/FX_USDJPY 1d) is 2.94% over all bars and 2.71% at this config's entry bars — far under the 0.15 global cap, so no max_stop_pct override is set (the override changes admissibility only; FWD-006 sizes by risk / stop distance).",
    },
    "ts_momentum_roc24_fx12": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: ROC(24) = close/close[-24] - 1 crosses up through 0 (roc > 0 and prior-bar roc <= 0). SHORT: ROC(24) crosses down through 0 (roc < 0 and prior-bar roc >= 0). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_ts_momentum(df, 24, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3790,
        "total_friction_bps": 6.0,
        "expected_net_edge_bps": 3.9,
        "minimum_required_edge": 0.0005,
        "lane_assets": FOREX12_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "forward_venues": ["oanda_practice"],
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): ts_momentum/roc24 @ FOREX12 4h meets the second tier (OOS expectancy +0.039%/trade, PF 1.1001, 715 OOS trades, 2/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Execution rides the OANDA FORWARD_TEST runner (PR #980); the module name strategy_ts_momentum_roc24_fx12 must be added to STRATEX_STRATEGY_ALLOWLIST on S1 at deploy. Distinct judged object from the ts_momentum crypto30 cells (TASK-STR-FWD-019 crew A, PR #991) — same judged signal function (families2 sig_ts_momentum), different panel/timeframe cell and records; never blended. RD-002 cost basis (rigorous_backtest/rd2/costs2.py): the forex12 panel is exactly the costs2 majors set, 6 bps round trip on every symbol (recorded per-symbol in the cell's grid row). FWD-012 stop check: measured max 2.0 x ATR(14)/close on the fwd002 FX fixtures (FX_EURUSD/FX_GBPJPY/FX_USDJPY 1d) is 2.94% over all bars and 2.64% at this config's entry bars on the 1d slices — the judged 4h ATR is smaller than the 1d ATR, so the 1d measurement is a conservative upper bound for the 4h cell — far under the 0.15 global cap, so no max_stop_pct override is set (the override changes admissibility only; FWD-006 sizes by risk / stop distance).",
    },
    # ------------------------------------------------------------------
    # TASK-STR-FWD-019 WAVE-2: governed forex12 cells + bollinger p20
    # @ forex28 (near-miss audit §1.4). Executable ONLY through the
    # OANDA forward-test runner (PR 1 of this task) on the practice
    # venue — forward_venues is the runner's discovery key.
    # ------------------------------------------------------------------
    "factory_winner_4": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "MACD(12,26,9) cross confluence with the Bollinger(20,2) mid band, evaluated exactly as the judged live module strategy_factory_winners.get_signal_winner_4 (LONG: MACD crosses above signal AND close < BB mid; SHORT: cross below AND close > BB mid). Judged bare: rigorous_backtest/rd2/gov2.py eval_module_cell — module.add_features over the frame, get_signal on trailing <=500-bar windows, NO downstream filter, warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged module bracket)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged module bracket)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3856,
        "total_friction_bps": 6.0,
        "expected_net_edge_bps": 5.1,
        "minimum_required_edge": 0.0005,
        "lane_assets": FOREX12_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "forward_venues": ["oanda_practice"],
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): governed/strategy_factory_winner_4:bare @ FOREX12 4h meets the second tier (OOS expectancy +0.051%/trade, PF 1.1394, 682 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. The judged live module was deleted from main by TASK-STR-CLEANUP-001 under the earlier BT-001 evidence rule; the lane module restores its judged signal code verbatim from the pre-cleanup blob (see the module docstring) — the RD-002 forex12 cell recorded here, not the deleted configuration's earlier record, is the admission basis. RD-002 cost basis (rigorous_backtest/rd2/costs2.py): forex majors 6 bps round trip; the forex12 panel is exactly the costs2 majors set. FWD-012 stop check: measured max SL_ATR x ATR(14)/close on the fwd002 FX fixtures (FX_EURUSD/FX_GBPJPY/FX_USDJPY 1d) is 2.94% for the 2.0x stop at 1d (the judged 4h ATR is smaller than the 1d ATR, so the 1d measurement is a conservative upper bound) — far under the 0.15 global cap, so no max_stop_pct override is set (the override changes admissibility only; FWD-006 sizes by risk / stop distance).",
    },
    "factory_winner_3": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "MACD(12,26,9) cross confluence with the Bollinger(20,2) mid band, evaluated exactly as the judged live module strategy_factory_winners.get_signal_winner_3 (LONG: MACD crosses above signal AND close < BB mid; SHORT: cross below AND close > BB mid). Judged bare: rigorous_backtest/rd2/gov2.py eval_module_cell — module.add_features over the frame, get_signal on trailing <=500-bar windows, NO downstream filter, warmup 260 bars.",
        "sl_method": "1.5 * ATR(14) at signal bar (judged module bracket)",
        "tp_method": "4.5 * ATR(14) at signal bar (judged module bracket)",
        "rr_ratio": 3.0,
        "oos_win_rate_prior": 0.2863,
        "total_friction_bps": 6.0,
        "expected_net_edge_bps": 2.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": FOREX12_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "forward_venues": ["oanda_practice"],
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): governed/strategy_factory_winner_3:bare @ FOREX12 4h meets the second tier (OOS expectancy +0.025%/trade, PF 1.0738, 702 OOS trades, 2/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Duplicate-alias note: governed/strategy_factory_winner_5:bare @ FOREX12 4h is an identical trade stream to this row (702 trades, +0.025%/trade, PF 1.0738 — the judged modules differ only in win_rate_prior, which affects neither signals nor brackets), which is NOT separately wired — dedupe per audit §1.4. The judged live module was deleted from main by TASK-STR-CLEANUP-001 under the earlier BT-001 evidence rule; the lane module restores its judged signal code verbatim from the pre-cleanup blob (see the module docstring) — the RD-002 forex12 cell recorded here, not the deleted configuration's earlier record, is the admission basis. RD-002 cost basis (rigorous_backtest/rd2/costs2.py): forex majors 6 bps round trip; the forex12 panel is exactly the costs2 majors set. FWD-012 stop check: measured max SL_ATR x ATR(14)/close on the fwd002 FX fixtures (FX_EURUSD/FX_GBPJPY/FX_USDJPY 1d) is 2.20% for the 1.5x stop at 1d (the judged 4h ATR is smaller than the 1d ATR, so the 1d measurement is a conservative upper bound) — far under the 0.15 global cap, so no max_stop_pct override is set (the override changes admissibility only; FWD-006 sizes by risk / stop distance).",
    },
    "bb_reversion": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Bollinger(20,2) pierce-and-reenter mean reversion, evaluated exactly as the judged live module strategy_bb_reversion (LONG: prior bar pierced the lower band and the current close closes back inside, rising; SHORT mirrored at the upper band). Judged bare: rigorous_backtest/rd2/gov2.py eval_module_cell — module.add_features over the frame, get_signal on trailing <=500-bar windows, NO downstream filter, warmup 260 bars.",
        "sl_method": "1.5 * ATR(14) at signal bar (judged module bracket, code constants)",
        "tp_method": "3.0 * ATR(14) at signal bar (judged module bracket, code constants)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3571,
        "total_friction_bps": 6.0,
        "expected_net_edge_bps": 7.3,
        "minimum_required_edge": 0.0005,
        "lane_assets": FOREX12_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "forward_venues": ["oanda_practice"],
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): governed/strategy_bb_reversion:bare @ FOREX12 1d meets the second tier (OOS expectancy +0.073%/trade, PF 1.0911, 308 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. The judged live module was deleted from main by TASK-STR-CLEANUP-001 under the earlier BT-001 evidence rule; the lane module restores its judged signal code verbatim from the pre-cleanup blob (see the module docstring) — the RD-002 forex12 cell recorded here, not the deleted configuration's earlier record, is the admission basis. RD-002 cost basis (rigorous_backtest/rd2/costs2.py): forex majors 6 bps round trip; the forex12 panel is exactly the costs2 majors set. FWD-012 stop check: measured max SL_ATR x ATR(14)/close on the fwd002 FX fixtures (FX_EURUSD/FX_GBPJPY/FX_USDJPY 1d) is 2.20% for the 1.5x stop at 1d — far under the 0.15 global cap, so no max_stop_pct override is set (the override changes admissibility only; FWD-006 sizes by risk / stop distance).",
    },
    "bollinger_trend_p20_fx28": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close crosses above SMA(20) + 2.0 x rolling-std(20). SHORT: close crosses below SMA(20) - 2.0 x rolling-std(20). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_bollinger_trend(df, 20, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3915,
        "total_friction_bps": 6.0,
        "expected_net_edge_bps": 13.0,
        "minimum_required_edge": 0.0005,
        "lane_assets": FOREX28_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "forward_venues": ["oanda_practice"],
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): bollinger_trend/p20_sd2.0 @ FOREX28 1d meets the second tier (OOS expectancy +0.130%/trade, PF 1.1177, 355 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. RD-002 cost basis (rigorous_backtest/rd2/costs2.py): forex majors 6 bps / minors and crosses 10 bps round trip; the registry friction field carries the 6.0 majors figure following the sleeve_tsmom2_dual precedent for this same panel. FWD-012 stop check: measured max SL_ATR x ATR(14)/close on the fwd002 FX fixtures (FX_EURUSD/FX_GBPJPY/FX_USDJPY 1d) is 2.94% for the 2.0x stop at 1d — far under the 0.15 global cap, so no max_stop_pct override is set (the override changes admissibility only; FWD-006 sizes by risk / stop distance).",
    },
    # ------------------------------------------------------------------
    # TASK-STR-FWD-019 WAVE-2: RD-004 vol_regime_trend gate_lo family
    # @ CRYPTO30 2h (near-miss audit REPORT.md §1.2). FORWARD_TEST —
    # demo venues only, forward evidence decides them.
    # ------------------------------------------------------------------
    "vol_regime_trend": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "2h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: EMA(24) crosses above EMA(96) on the signal bar AND the daily volatility-regime rank R(d) < 0.50 (gate_lo). SHORT: EMA(24) crosses below EMA(96) AND R(d) < 0.50. R(d): bar ATR%(14) averaged per UTC day = V(d); R(d) = share of the prior 180 days' V values <= V(d-1); all bars of day d use R(d); no entries while R is NaN (first 181 days). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd4/families_rd4.py base_entries('ema24_96') + regime_rank_by_bar + apply_mode(..., 'gate_lo', ...), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged RD-004 bracket: families_rd4 docstring, rd4/sim_rd4.py SL_BASE)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged RD-004 bracket: rd4/sim_rd4.py TP_BASE)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3675,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 20.3,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        # TASK-STR-FWD-012 stop-cap check (wave-2 brief method): the
        # judged stop (2.0 x ATR(14) / price) measured on the fwd002
        # 4h fixtures — 2h configs are measured on 4h slices because
        # per-bar ATR only shrinks with timeframe, so the 4h figure
        # is a conservative upper bound for 2h: max 0.0477 over gated
        # entry bars, 0.1300 over all bars >= warmup (SOLUSDT), and
        # 0.5604 over the full SOLUSDT 4h history. The CRYPTO30 tail
        # (INJ/SUI/APT-class names) plausibly exceeds the 0.15
        # engine-global cap, so the override is set at 0.60 —
        # admissibility only; FWD-006 sizes by risk / stop distance.
        "max_stop_pct": 0.60,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): vol_regime_trend/ema24_96_gate_lo @ CRYPTO30 2h meets the second tier (OOS expectancy +0.203%/trade, PF 1.1072, 2286 OOS trades, 2/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Stop-cap override max_stop_pct=0.60 per the FWD-012 check recorded in this entry (measured 4h-fixture max stop 0.1300 over bars >= warmup, 0.5604 over the full SOLUSDT 4h history; override changes admissibility only). The RD-004 WF-2h walk-forward-select procedure's pooled stream is identical to this cell (it picked ema24_96_gate_lo in all 5 folds) and is NOT separately wired.",
    },
    "vol_regime_trend_don20_gate_lo": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "2h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close crosses above the prior-20-bar Donchian high on the signal bar AND the daily volatility-regime rank R(d) < 0.50 (gate_lo). SHORT: close crosses below the prior-20-bar Donchian low AND R(d) < 0.50. R(d) as for vol_regime_trend (180-day rank of daily mean bar ATR%(14); no entries while NaN). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd4/families_rd4.py base_entries('don20') + regime_rank_by_bar + apply_mode(..., 'gate_lo', ...), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged RD-004 bracket: families_rd4 docstring, rd4/sim_rd4.py SL_BASE)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged RD-004 bracket: rd4/sim_rd4.py TP_BASE)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3681,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 14.8,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.60,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): vol_regime_trend/don20_gate_lo @ CRYPTO30 2h meets the second tier (OOS expectancy +0.148%/trade, PF 1.0741, 6313 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. This is the fastest independent-family accumulator in the audit (6,313 OOS trades, approx 3,157/year) — expected to reach the lane's 50-closed-trade kill threshold quickest. Stop-cap override max_stop_pct=0.60 per the family FWD-012 check recorded in the vol_regime_trend entry (measured 4h-fixture max stop 0.1300 over bars >= warmup, 0.5604 over the full SOLUSDT 4h history; override changes admissibility only).",
    },
    "vol_regime_trend_ema12_48_gate_lo": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "2h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: EMA(12) crosses above EMA(48) on the signal bar AND the daily volatility-regime rank R(d) < 0.50 (gate_lo). SHORT: EMA(12) crosses below EMA(48) AND R(d) < 0.50. R(d) as for vol_regime_trend (180-day rank of daily mean bar ATR%(14); no entries while NaN). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd4/families_rd4.py base_entries('ema12_48') + regime_rank_by_bar + apply_mode(..., 'gate_lo', ...), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged RD-004 bracket: families_rd4 docstring, rd4/sim_rd4.py SL_BASE)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged RD-004 bracket: rd4/sim_rd4.py TP_BASE)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3598,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 10.7,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.60,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): vol_regime_trend/ema12_48_gate_lo @ CRYPTO30 2h meets the second tier (OOS expectancy +0.107%/trade, PF 1.0550, 3471 OOS trades, 2/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Stop-cap override max_stop_pct=0.60 per the family FWD-012 check recorded in the vol_regime_trend entry (measured 4h-fixture max stop 0.1300 over bars >= warmup, 0.5604 over the full SOLUSDT 4h history; override changes admissibility only).",
    },
    "vol_adaptive_trend": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: EMA(12) crosses above EMA(26). SHORT: EMA(12) crosses below EMA(26). No volatility gate. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_vol_trend(df, 12, 26, False, warmup), warmup 260 bars.",
        "sl_method": "2.5 * ATR(14) at signal bar (judged bracket, families2 vol_adaptive_trend spec)",
        "tp_method": "5.0 * ATR(14) at signal bar (judged bracket, families2 vol_adaptive_trend spec)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.4482,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 623.3,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): vol_adaptive_trend/ema12_26_nogate @ CRYPTO30 1d meets the second tier (OOS expectancy +6.233%/trade, PF 1.6956, 299 OOS trades, 4/5 positive folds, PF @2x costs 1.6721) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. This stream is also a member of the live Stage-C sleeve book under its sleeve key — a distinct judged object; records never blended. FWD-012 stop-cap: judged stop 2.5 x ATR(14) measured up to 89.1% of price over all post-warmup bars on the fwd002 SOLUSDT 1d fixture slice (35.5% at entry bars) — above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.90 (sanity bound only; FWD-006 sizes by risk / stop distance).",
    },
    "vol_adaptive_trend_ema20_50_nogate": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: EMA(20) crosses above EMA(50). SHORT: EMA(20) crosses below EMA(50). No volatility gate. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_vol_trend(df, 20, 50, False, warmup), warmup 260 bars.",
        "sl_method": "2.5 * ATR(14) at signal bar (judged bracket, families2 vol_adaptive_trend spec)",
        "tp_method": "5.0 * ATR(14) at signal bar (judged bracket, families2 vol_adaptive_trend spec)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.4268,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 560.8,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): vol_adaptive_trend/ema20_50_nogate @ CRYPTO30 1d meets the second tier (OOS expectancy +5.608%/trade, PF 1.6359, 246 OOS trades, 4/5 positive folds, PF @2x costs 1.6124) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.5 x ATR(14) measured up to 89.1% of price over all post-warmup bars on the fwd002 SOLUSDT 1d fixture slice (23.3% at entry bars) — above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.90 (sanity bound only; FWD-006 sizes by risk / stop distance).",
    },
    "vol_adaptive_trend_ema20_50_nogate_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: EMA(20) crosses above EMA(50). SHORT: EMA(20) crosses below EMA(50). No volatility gate. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_vol_trend(df, 20, 50, False, warmup), warmup 260 bars.",
        "sl_method": "2.5 * ATR(14) at signal bar (judged bracket, families2 vol_adaptive_trend spec)",
        "tp_method": "5.0 * ATR(14) at signal bar (judged bracket, families2 vol_adaptive_trend spec)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3709,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 59.1,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.25,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): vol_adaptive_trend/ema20_50_nogate @ CRYPTO30 4h meets the second tier (OOS expectancy +0.591%/trade, PF 1.1425, 1,901 OOS trades, 2/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.5 x ATR(14) measured up to 16.3% of price over all post-warmup bars on the fwd002 SOLUSDT 4h fixture slice (10.2% at entry bars) — above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.25 (sanity bound only; FWD-006 sizes by risk / stop distance).",
    },
    "vol_adaptive_trend_ema12_26_nogate_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: EMA(12) crosses above EMA(26). SHORT: EMA(12) crosses below EMA(26). No volatility gate. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_vol_trend(df, 12, 26, False, warmup), warmup 260 bars.",
        "sl_method": "2.5 * ATR(14) at signal bar (judged bracket, families2 vol_adaptive_trend spec)",
        "tp_method": "5.0 * ATR(14) at signal bar (judged bracket, families2 vol_adaptive_trend spec)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3763,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 58.8,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.25,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): vol_adaptive_trend/ema12_26_nogate @ CRYPTO30 4h meets the second tier (OOS expectancy +0.588%/trade, PF 1.1348, 2,073 OOS trades, 2/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.5 x ATR(14) measured up to 16.3% of price over all post-warmup bars on the fwd002 SOLUSDT 4h fixture slice (13.6% at entry bars) — above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.25 (sanity bound only; FWD-006 sizes by risk / stop distance).",
    },
    "vol_adaptive_trend_ema20_50_gate_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: EMA(20) crosses above EMA(50). SHORT: EMA(20) crosses below EMA(50). Volatility gate: the ATR(14)/close 200-bar percentile rank must lie within [0.2, 0.8] at the signal bar. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_vol_trend(df, 20, 50, True, warmup), warmup 260 bars.",
        "sl_method": "2.5 * ATR(14) at signal bar (judged bracket, families2 vol_adaptive_trend spec)",
        "tp_method": "5.0 * ATR(14) at signal bar (judged bracket, families2 vol_adaptive_trend spec)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3743,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 55.0,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.25,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): vol_adaptive_trend/ema20_50_gate @ CRYPTO30 4h meets the second tier (OOS expectancy +0.550%/trade, PF 1.1346, 1,293 OOS trades, 4/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.5 x ATR(14) measured up to 16.3% of price over all post-warmup bars on the fwd002 SOLUSDT 4h fixture slice (8.9% at entry bars) — above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.25 (sanity bound only; FWD-006 sizes by risk / stop distance).",
    },
    "keltner_breakout": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close crosses above EMA(20) + 2.0 x ATR(14). SHORT: close crosses below EMA(20) - 2.0 x ATR(14). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_keltner(df, 20, 2.0, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3753,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 194.1,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): keltner_breakout/ema20_m2.0 @ CRYPTO30 1d meets the second tier (OOS expectancy +1.941%/trade, PF 1.2284, 437 OOS trades, 3/5 positive folds, PF @2x costs 1.2072) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. TASK-STR-FWD-012 stop check: judged stop 2.0 x ATR(14) on 1d crypto fixtures reaches 28.4% of price at entry bars (SOL 1d) and 71.28% across all fixture bars — structurally above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.90 (sanity bound above the measured max; the override changes admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "keltner_breakout_ema50_m2": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close crosses above EMA(50) + 2.0 x ATR(14). SHORT: close crosses below EMA(50) - 2.0 x ATR(14). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_keltner(df, 50, 2.0, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3593,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 146.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): keltner_breakout/ema50_m2.0 @ CRYPTO30 1d meets the second tier (OOS expectancy +1.465%/trade, PF 1.1696, 501 OOS trades, 3/5 positive folds, PF @2x costs 1.1496) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. TASK-STR-FWD-012 stop check: judged stop 2.0 x ATR(14) on 1d crypto fixtures reaches 28.4% of price at entry bars (SOL 1d) and 71.28% across all fixture bars — structurally above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.90 (sanity bound above the measured max; the override changes admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "keltner_breakout_ema20_m15": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close crosses above EMA(20) + 1.5 x ATR(14). SHORT: close crosses below EMA(20) - 1.5 x ATR(14). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_keltner(df, 20, 1.5, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3471,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 121.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): keltner_breakout/ema20_m1.5 @ CRYPTO30 1d meets the second tier (OOS expectancy +1.215%/trade, PF 1.1424, 605 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. TASK-STR-FWD-012 stop check: judged stop 2.0 x ATR(14) on 1d crypto fixtures reaches 28.4% of price at entry bars (SOL 1d) and 71.28% across all fixture bars — structurally above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.90 (sanity bound above the measured max; the override changes admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "keltner_breakout_ema20_m2_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close crosses above EMA(20) + 2.0 x ATR(14). SHORT: close crosses below EMA(20) - 2.0 x ATR(14). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_keltner(df, 20, 2.0, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3669,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 28.8,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.30,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): keltner_breakout/ema20_m2.0 @ CRYPTO30 4h meets the second tier (OOS expectancy +0.288%/trade, PF 1.0816, 3,314 OOS trades, 2/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. TASK-STR-FWD-012 stop check: judged stop 2.0 x ATR(14) on 4h fixtures measures at most 13.0% of price across all BTC/SOL bars (entry-bar max in this entry's record), under the 0.15 engine-global cap on the fixtures — but the CRYPTO30 tail (INJ/SUI/APT-class names) plausibly exceeds it, so this entry carries max_stop_pct 0.30 (rounded sanity bound above the measured max; admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "keltner_breakout_ema20_m15_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close crosses above EMA(20) + 1.5 x ATR(14). SHORT: close crosses below EMA(20) - 1.5 x ATR(14). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_keltner(df, 20, 1.5, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3605,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 25.6,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.30,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): keltner_breakout/ema20_m1.5 @ CRYPTO30 4h meets the second tier (OOS expectancy +0.256%/trade, PF 1.0731, 4,336 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. TASK-STR-FWD-012 stop check: judged stop 2.0 x ATR(14) on 4h fixtures measures at most 13.0% of price across all BTC/SOL bars (entry-bar max in this entry's record), under the 0.15 engine-global cap on the fixtures — but the CRYPTO30 tail (INJ/SUI/APT-class names) plausibly exceeds it, so this entry carries max_stop_pct 0.30 (rounded sanity bound above the measured max; admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "keltner_breakout_forex": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close crosses above EMA(20) + 2.0 x ATR(14). SHORT: close crosses below EMA(20) - 2.0 x ATR(14). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_keltner(df, 20, 2.0, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3900,
        "total_friction_bps": 10.0,
        "expected_net_edge_bps": 13.7,
        "minimum_required_edge": 0.0005,
        "lane_assets": FOREX28_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "forward_venues": ["oanda_practice"],
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): keltner_breakout/ema20_m2.0 @ FOREX28 1d meets the second tier (OOS expectancy +0.137%/trade, PF 1.1273, 241 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. TASK-STR-FWD-012 stop check: daily FX 2.0 x ATR(14) stops measure at most 2.94% of price across all bars of the FX fixture slices (EURUSD/GBPJPY/USDJPY 1d) — far under the 0.15 engine-global cap — so no max_stop_pct override is carried. Friction: the RD-002 forex28 record carries per-symbol round-trip costs of 6.0-10.0 bps; this entry records the conservative maximum, 10.0. DEPENDENCY: this config trades on the OANDA practice venue via the OANDA runner (a separate crew's FWD-019 runner PR); the Binance daemon will not execute it.",
    },
    "donchian_turtle": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close > prior-55-bar highest high (rolling(55) max of high, shifted 1). SHORT: close < prior-55-bar lowest low. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_donchian(df, 55, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR26)",
        "tp_method": "6.0 * ATR(14) at signal bar (judged bracket BR26)",
        "rr_ratio": 3.0,
        "oos_win_rate_prior": 0.3523,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 561.4,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.9,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): donchian_turtle/n55_b26 @ CRYPTO30 1d meets the second tier (OOS expectancy +5.614%/trade, PF 1.6502, 298 OOS trades, 4/5 positive folds, PF @2x costs 1.6246) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) \u2014 not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. This stream is also a member of the live Stage-C sleeve book under its sleeve key \u2014 a distinct judged object; records never blended. FWD-012 stop-cap: judged stop 2.0 x ATR(14); measured max stop on the fwd002 fixture slices at 1d = 71.28% of price (SOLUSDT 1d slice; BTCUSDT lower), above the 0.15 engine-global cap, so this entry carries max_stop_pct=0.9 (sanity bound above the measured max; FWD-006 sizes by risk / stop distance, the override changes admissibility only).",
    },
    "donchian_turtle_n20_trail": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close > prior-20-bar highest high (rolling(20) max of high, shifted 1). SHORT: close < prior-20-bar lowest low. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_donchian(df, 20, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged TRAIL spec, families2)",
        "tp_method": "NONE \u2014 judged TRAIL spec: trailing stop 2.5 * ATR(14), no fixed take-profit (see reason)",
        "rr_ratio": None,
        "oos_win_rate_prior": 0.3885,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 108.7,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.9,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): donchian_turtle/n20_trail @ CRYPTO30 1d meets the second tier (OOS expectancy +1.087%/trade, PF 1.1968, 677 OOS trades, 3/5 positive folds, PF @2x costs 1.1647) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) \u2014 not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Identical trade stream to turtle2/n20_trail 1d (audit S1.4 dup flag), which is NOT separately wired \u2014 dedupe per audit S1.4; this is the single wired copy. FWD-012 stop-cap: judged stop 2.0 x ATR(14); measured max stop on the fwd002 fixture slices at 1d = 71.28% of price (SOLUSDT 1d slice; BTCUSDT lower), above the 0.15 engine-global cap, so this entry carries max_stop_pct=0.9 (sanity bound above the measured max; FWD-006 sizes by risk / stop distance, the override changes admissibility only). EXIT GEOMETRY NOTE: the judged spec is TRAIL (families2 TRAIL: SL 2.0 x ATR(14), trailing stop 2.5 x ATR(14), NO fixed take-profit \u2014 rigorous_backtest/rd/fastsim.py). The daemon's execution path requires a fixed TP distance, so this config's trailing exit is NOT faithfully executable until the daemon gains trailing-exit support; do NOT add its module to STRATEX_STRATEGY_ALLOWLIST before that support exists. Entry signal and initial stop are the judged ones, equivalence-tested.",
    },
    "donchian_turtle_n20_b26": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close > prior-20-bar highest high (rolling(20) max of high, shifted 1). SHORT: close < prior-20-bar lowest low. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_donchian(df, 20, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR26)",
        "tp_method": "6.0 * ATR(14) at signal bar (judged bracket BR26)",
        "rr_ratio": 3.0,
        "oos_win_rate_prior": 0.275,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 159.6,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.9,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): donchian_turtle/n20_b26 @ CRYPTO30 1d meets the second tier (OOS expectancy +1.596%/trade, PF 1.1641, 400 OOS trades, 3/5 positive folds, PF @2x costs 1.1459) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) \u2014 not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.0 x ATR(14); measured max stop on the fwd002 fixture slices at 1d = 71.28% of price (SOLUSDT 1d slice; BTCUSDT lower), above the 0.15 engine-global cap, so this entry carries max_stop_pct=0.9 (sanity bound above the measured max; FWD-006 sizes by risk / stop distance, the override changes admissibility only).",
    },
    "donchian_turtle_n55_trail": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close > prior-55-bar highest high (rolling(55) max of high, shifted 1). SHORT: close < prior-55-bar lowest low. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_donchian(df, 55, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged TRAIL spec, families2)",
        "tp_method": "NONE \u2014 judged TRAIL spec: trailing stop 2.5 * ATR(14), no fixed take-profit (see reason)",
        "rr_ratio": None,
        "oos_win_rate_prior": 0.3632,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 86.4,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.9,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): donchian_turtle/n55_trail @ CRYPTO30 1d meets the second tier (OOS expectancy +0.864%/trade, PF 1.1509, 435 OOS trades, 3/5 positive folds, PF @2x costs 1.1208) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) \u2014 not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Identical trade stream to turtle2/n55_trail 1d (audit S1.4 dup flag), which is NOT separately wired \u2014 dedupe per audit S1.4; this is the single wired copy. FWD-012 stop-cap: judged stop 2.0 x ATR(14); measured max stop on the fwd002 fixture slices at 1d = 71.28% of price (SOLUSDT 1d slice; BTCUSDT lower), above the 0.15 engine-global cap, so this entry carries max_stop_pct=0.9 (sanity bound above the measured max; FWD-006 sizes by risk / stop distance, the override changes admissibility only). EXIT GEOMETRY NOTE: the judged spec is TRAIL (families2 TRAIL: SL 2.0 x ATR(14), trailing stop 2.5 x ATR(14), NO fixed take-profit \u2014 rigorous_backtest/rd/fastsim.py). The daemon's execution path requires a fixed TP distance, so this config's trailing exit is NOT faithfully executable until the daemon gains trailing-exit support; do NOT add its module to STRATEX_STRATEGY_ALLOWLIST before that support exists. Entry signal and initial stop are the judged ones, equivalence-tested.",
    },
    "donchian_turtle_n55_trail_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close > prior-55-bar highest high (rolling(55) max of high, shifted 1). SHORT: close < prior-55-bar lowest low. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_donchian(df, 55, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged TRAIL spec, families2)",
        "tp_method": "NONE \u2014 judged TRAIL spec: trailing stop 2.5 * ATR(14), no fixed take-profit (see reason)",
        "rr_ratio": None,
        "oos_win_rate_prior": 0.392,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 32.0,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.2,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): donchian_turtle/n55_trail @ CRYPTO30 4h meets the second tier (OOS expectancy +0.32%/trade, PF 1.139, 3176 OOS trades, 4/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) \u2014 not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Identical trade stream to turtle2/n55_trail 4h (audit S1.4 dup flag), which is NOT separately wired \u2014 dedupe per audit S1.4; this is the single wired copy. FWD-012 stop-cap: judged stop 2.0 x ATR(14); measured max stop on the fwd002 fixture slices at 4h = 11.12% of price (SOLUSDT 4h slice; BTCUSDT lower), above the 0.15 engine-global cap, so this entry carries max_stop_pct=0.2 (sanity bound above the measured max; FWD-006 sizes by risk / stop distance, the override changes admissibility only). EXIT GEOMETRY NOTE: the judged spec is TRAIL (families2 TRAIL: SL 2.0 x ATR(14), trailing stop 2.5 x ATR(14), NO fixed take-profit \u2014 rigorous_backtest/rd/fastsim.py). The daemon's execution path requires a fixed TP distance, so this config's trailing exit is NOT faithfully executable until the daemon gains trailing-exit support; do NOT add its module to STRATEX_STRATEGY_ALLOWLIST before that support exists. Entry signal and initial stop are the judged ones, equivalence-tested.",
    },
    "donchian_turtle_n20_trail_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close > prior-20-bar highest high (rolling(20) max of high, shifted 1). SHORT: close < prior-20-bar lowest low. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_donchian(df, 20, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged TRAIL spec, families2)",
        "tp_method": "NONE \u2014 judged TRAIL spec: trailing stop 2.5 * ATR(14), no fixed take-profit (see reason)",
        "rr_ratio": None,
        "oos_win_rate_prior": 0.3747,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 24.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.2,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): donchian_turtle/n20_trail @ CRYPTO30 4h meets the second tier (OOS expectancy +0.245%/trade, PF 1.1043, 5413 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) \u2014 not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Identical trade stream to turtle2/n20_trail 4h (audit S1.4 dup flag), which is NOT separately wired \u2014 dedupe per audit S1.4; this is the single wired copy. FWD-012 stop-cap: judged stop 2.0 x ATR(14); measured max stop on the fwd002 fixture slices at 4h = 11.12% of price (SOLUSDT 4h slice; BTCUSDT lower), above the 0.15 engine-global cap, so this entry carries max_stop_pct=0.2 (sanity bound above the measured max; FWD-006 sizes by risk / stop distance, the override changes admissibility only). EXIT GEOMETRY NOTE: the judged spec is TRAIL (families2 TRAIL: SL 2.0 x ATR(14), trailing stop 2.5 x ATR(14), NO fixed take-profit \u2014 rigorous_backtest/rd/fastsim.py). The daemon's execution path requires a fixed TP distance, so this config's trailing exit is NOT faithfully executable until the daemon gains trailing-exit support; do NOT add its module to STRATEX_STRATEGY_ALLOWLIST before that support exists. Entry signal and initial stop are the judged ones, equivalence-tested.",
    },
    "donchian_turtle_n20_b24": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close > prior-20-bar highest high (rolling(20) max of high, shifted 1). SHORT: close < prior-20-bar lowest low. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_donchian(df, 20, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3466,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 87.0,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.9,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): donchian_turtle/n20_b24 @ CRYPTO30 1d meets the second tier (OOS expectancy +0.87%/trade, PF 1.1016, 727 OOS trades, 2/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) \u2014 not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Identical trade stream to volume_breakout/donch20_novol 1d (audit S1.4 dup flag), which is NOT separately wired \u2014 dedupe per audit S1.4; this is the single wired copy. FWD-012 stop-cap: judged stop 2.0 x ATR(14); measured max stop on the fwd002 fixture slices at 1d = 71.28% of price (SOLUSDT 1d slice; BTCUSDT lower), above the 0.15 engine-global cap, so this entry carries max_stop_pct=0.9 (sanity bound above the measured max; FWD-006 sizes by risk / stop distance, the override changes admissibility only).",
    },
    "donchian_turtle_n20_b26_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close > prior-20-bar highest high (rolling(20) max of high, shifted 1). SHORT: close < prior-20-bar lowest low. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_donchian(df, 20, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR26)",
        "tp_method": "6.0 * ATR(14) at signal bar (judged bracket BR26)",
        "rr_ratio": 3.0,
        "oos_win_rate_prior": 0.276,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 26.0,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.2,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): donchian_turtle/n20_b26 @ CRYPTO30 4h meets the second tier (OOS expectancy +0.26%/trade, PF 1.0613, 3583 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) \u2014 not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.0 x ATR(14); measured max stop on the fwd002 fixture slices at 4h = 11.12% of price (SOLUSDT 4h slice; BTCUSDT lower), above the 0.15 engine-global cap, so this entry carries max_stop_pct=0.2 (sanity bound above the measured max; FWD-006 sizes by risk / stop distance, the override changes admissibility only).",
    },
    "donchian_turtle_n55_b24": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close > prior-55-bar highest high (rolling(55) max of high, shifted 1). SHORT: close < prior-55-bar lowest low. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_donchian(df, 55, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3468,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 52.5,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.9,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): donchian_turtle/n55_b24 @ CRYPTO30 1d meets the second tier (OOS expectancy +0.525%/trade, PF 1.0581, 496 OOS trades, 2/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) \u2014 not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.0 x ATR(14); measured max stop on the fwd002 fixture slices at 1d = 71.28% of price (SOLUSDT 1d slice; BTCUSDT lower), above the 0.15 engine-global cap, so this entry carries max_stop_pct=0.9 (sanity bound above the measured max; FWD-006 sizes by risk / stop distance, the override changes admissibility only).",
    },
    "turtle2": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG/SHORT: donchian_turtle n=55 channel breakout (sig_donchian) AND the EMA(200) trend filter \u2014 longs only above EMA(200), shorts only below. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_turtle2(df, 55, True, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged TRAIL spec, families2)",
        "tp_method": "NONE \u2014 judged TRAIL spec: trailing stop 2.5 * ATR(14), no fixed take-profit (see reason)",
        "rr_ratio": None,
        "oos_win_rate_prior": 0.3725,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 117.0,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.9,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): turtle2/n55_trail_filt @ CRYPTO30 1d meets the second tier (OOS expectancy +1.17%/trade, PF 1.2037, 400 OOS trades, 3/5 positive folds, PF @2x costs 1.1727) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) \u2014 not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.0 x ATR(14); measured max stop on the fwd002 fixture slices at 1d = 71.28% of price (SOLUSDT 1d slice; BTCUSDT lower), above the 0.15 engine-global cap, so this entry carries max_stop_pct=0.9 (sanity bound above the measured max; FWD-006 sizes by risk / stop distance, the override changes admissibility only). EXIT GEOMETRY NOTE: the judged spec is TRAIL (families2 TRAIL: SL 2.0 x ATR(14), trailing stop 2.5 x ATR(14), NO fixed take-profit \u2014 rigorous_backtest/rd/fastsim.py). The daemon's execution path requires a fixed TP distance, so this config's trailing exit is NOT faithfully executable until the daemon gains trailing-exit support; do NOT add its module to STRATEX_STRATEGY_ALLOWLIST before that support exists. Entry signal and initial stop are the judged ones, equivalence-tested.",
    },
    "turtle2_n20_trail_filt": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG/SHORT: donchian_turtle n=20 channel breakout (sig_donchian) AND the EMA(200) trend filter \u2014 longs only above EMA(200), shorts only below. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_turtle2(df, 20, True, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged TRAIL spec, families2)",
        "tp_method": "NONE \u2014 judged TRAIL spec: trailing stop 2.5 * ATR(14), no fixed take-profit (see reason)",
        "rr_ratio": None,
        "oos_win_rate_prior": 0.371,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 89.2,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.9,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): turtle2/n20_trail_filt @ CRYPTO30 1d meets the second tier (OOS expectancy +0.892%/trade, PF 1.159, 558 OOS trades, 3/5 positive folds, PF @2x costs 1.1281) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) \u2014 not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.0 x ATR(14); measured max stop on the fwd002 fixture slices at 1d = 71.28% of price (SOLUSDT 1d slice; BTCUSDT lower), above the 0.15 engine-global cap, so this entry carries max_stop_pct=0.9 (sanity bound above the measured max; FWD-006 sizes by risk / stop distance, the override changes admissibility only). EXIT GEOMETRY NOTE: the judged spec is TRAIL (families2 TRAIL: SL 2.0 x ATR(14), trailing stop 2.5 x ATR(14), NO fixed take-profit \u2014 rigorous_backtest/rd/fastsim.py). The daemon's execution path requires a fixed TP distance, so this config's trailing exit is NOT faithfully executable until the daemon gains trailing-exit support; do NOT add its module to STRATEX_STRATEGY_ALLOWLIST before that support exists. Entry signal and initial stop are the judged ones, equivalence-tested.",
    },
    "turtle2_n55_trail_filt_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG/SHORT: donchian_turtle n=55 channel breakout (sig_donchian) AND the EMA(200) trend filter \u2014 longs only above EMA(200), shorts only below. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_turtle2(df, 55, True, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged TRAIL spec, families2)",
        "tp_method": "NONE \u2014 judged TRAIL spec: trailing stop 2.5 * ATR(14), no fixed take-profit (see reason)",
        "rr_ratio": None,
        "oos_win_rate_prior": 0.3911,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 36.6,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.2,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): turtle2/n55_trail_filt @ CRYPTO30 4h meets the second tier (OOS expectancy +0.366%/trade, PF 1.1585, 2966 OOS trades, 4/5 positive folds, PF @2x costs 1.0858) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) \u2014 not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.0 x ATR(14); measured max stop on the fwd002 fixture slices at 4h = 11.12% of price (SOLUSDT 4h slice; BTCUSDT lower), above the 0.15 engine-global cap, so this entry carries max_stop_pct=0.2 (sanity bound above the measured max; FWD-006 sizes by risk / stop distance, the override changes admissibility only). EXIT GEOMETRY NOTE: the judged spec is TRAIL (families2 TRAIL: SL 2.0 x ATR(14), trailing stop 2.5 x ATR(14), NO fixed take-profit \u2014 rigorous_backtest/rd/fastsim.py). The daemon's execution path requires a fixed TP distance, so this config's trailing exit is NOT faithfully executable until the daemon gains trailing-exit support; do NOT add its module to STRATEX_STRATEGY_ALLOWLIST before that support exists. Entry signal and initial stop are the judged ones, equivalence-tested.",
    },
    "turtle2_n20_trail_filt_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG/SHORT: donchian_turtle n=20 channel breakout (sig_donchian) AND the EMA(200) trend filter \u2014 longs only above EMA(200), shorts only below. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_turtle2(df, 20, True, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged TRAIL spec, families2)",
        "tp_method": "NONE \u2014 judged TRAIL spec: trailing stop 2.5 * ATR(14), no fixed take-profit (see reason)",
        "rr_ratio": None,
        "oos_win_rate_prior": 0.3809,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 33.0,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.2,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): turtle2/n20_trail_filt @ CRYPTO30 4h meets the second tier (OOS expectancy +0.33%/trade, PF 1.1421, 4369 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) \u2014 not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.0 x ATR(14); measured max stop on the fwd002 fixture slices at 4h = 11.12% of price (SOLUSDT 4h slice; BTCUSDT lower), above the 0.15 engine-global cap, so this entry carries max_stop_pct=0.2 (sanity bound above the measured max; FWD-006 sizes by risk / stop distance, the override changes admissibility only). EXIT GEOMETRY NOTE: the judged spec is TRAIL (families2 TRAIL: SL 2.0 x ATR(14), trailing stop 2.5 x ATR(14), NO fixed take-profit \u2014 rigorous_backtest/rd/fastsim.py). The daemon's execution path requires a fixed TP distance, so this config's trailing exit is NOT faithfully executable until the daemon gains trailing-exit support; do NOT add its module to STRATEX_STRATEGY_ALLOWLIST before that support exists. Entry signal and initial stop are the judged ones, equivalence-tested.",
    },
    "rsi_momentum": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: RSI(14) crosses up through 55. SHORT: RSI(14) crosses down through 45. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_rsi_momentum(df, 14, 55.0, 45.0, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3642,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 91.3,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): rsi_momentum/rsi14_55_45 @ CRYPTO30 1d meets the second tier (OOS expectancy +0.913%/trade, PF 1.1016, 648 OOS trades, 4/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Stop-cap override (TASK-STR-FWD-012): judged 2.0 x ATR(14) stops measured up to 20.21% of price at entry bars on the SOLUSDT 1d fixture (BTCUSDT 9.87%) — above the 0.15 engine-global cap — so max_stop_pct 0.90 is declared (sanity bound only; the override changes admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "rsi_momentum_rsi7_60_40": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: RSI(7) crosses up through 60. SHORT: RSI(7) crosses down through 40. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_rsi_momentum(df, 7, 60.0, 40.0, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3470,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 85.6,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): rsi_momentum/rsi7_60_40 @ CRYPTO30 1d meets the second tier (OOS expectancy +0.856%/trade, PF 1.0932, 709 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Stop-cap override (TASK-STR-FWD-012): judged stops measured up to 32.94% of price at entry bars on the SOLUSDT 1d fixture (BTCUSDT 10.82%) — above the 0.15 engine-global cap — so max_stop_pct 0.90 is declared (sanity bound only; admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "rsi_momentum_forex": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: RSI(14) crosses up through 55. SHORT: RSI(14) crosses down through 45. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_rsi_momentum(df, 14, 55.0, 45.0, warmup) on the FOREX28 panel, warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3721,
        "total_friction_bps": 10.0,
        "expected_net_edge_bps": 8.9,
        "minimum_required_edge": 0.0005,
        "lane_assets": FOREX28_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "forward_venues": ["oanda_practice"],
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): rsi_momentum/rsi14_55_45 @ FOREX28 1d meets the second tier (OOS expectancy +0.089%/trade, PF 1.0761, 344 OOS trades, 2/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Judged cost basis is the RD-002 forex model (rigorous_backtest/rd2/costs2.py: 6 bps round trip majors, 10 bps minors/crosses); total_friction_bps carries the 10.0 panel maximum. Stop check (TASK-STR-FWD-012): judged 2.0 x ATR(14) stops measured 1.58% (EURUSD), 1.65% (USDJPY), 2.64% (GBPJPY) max at entry bars on the fwd002 FX fixtures — far below the 0.15 engine-global cap, so no max_stop_pct override. OANDA entry: execution rides the governed OANDA runner (separate PR); this entry carries forward_venues [oanda_practice] so that runner can discover it.",
    },
    "volatility_breakout": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close breaks above the prior-10-bar high AND ATR(14) (simple rolling mean of true range) > 1.2 x its 20-bar average (volatility expanding) AND EMA(50) > EMA(200). SHORT: close breaks below the prior-10-bar low AND ATR expanding AND EMA(50) < EMA(200). Judged exactly as the module's own get_signal() evaluated by rigorous_backtest/module_eval.py (stage-1 harness): trailing <=500-bar windows, bars from 260, signal on close of bar i, entry at open of bar i+1 under the MODULE convention.",
        "sl_method": "2.5 * ATR(14) at signal bar (the module's OWN judged bracket — module_eval kept the module's sl/tp; NOT the BR24 bracket)",
        "tp_method": "6.0 * ATR(14) at signal bar (the module's OWN judged bracket)",
        "rr_ratio": 2.4,
        "oos_win_rate_prior": 0.3519,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 13.1,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        # TASK-STR-FWD-012 stop-cap check, RE-MEASURED at the judged
        # 1h on the judged datasets (BTC/ETH/SOL 1h, 27,048 bars
        # each, 2023-10 to 2026-10): judged stop 2.5 x ATR(14) /
        # price — max 0.1284 over entry bars and 0.1665 over all
        # bars >= warmup (pooled; SOLUSDT is the max on both).
        # Above the 0.15 engine-global cap: without an override the
        # widest judged stops would be cap-blocked (the sleeve_shock
        # failure mode). Override 0.25 = rounded sanity bound above
        # the measured 1h max; admissibility only, FWD-006 sizes by
        # risk / stop distance. (The original 1.20 override rested
        # on a measurement over the fwd002 1d fixtures — max 0.9640 —
        # not at the judged timeframe; superseded by this 1h
        # re-measurement, 2026-11-18.)
        "max_stop_pct": 0.25,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): volatility_breakout @ CRYPTO30 1h meets the second tier (OOS expectancy +0.131%/trade, PF 1.0669, 520 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Timeframe provenance: JUDGED AT 1h — the stage-1 row record's timeframe field is '1h' and its data_provenance is keyed BTCUSDT_1h/ETHUSDT_1h/SOLUSDT_1h with 27,048 hourly rows per symbol (2023-10 to 2026-10); the harness's timeframe inference (run_all._infer_primary_timeframe, default '1h' — neither module's text names a timeframe) SELECTED the 1h dataset in stage1.py's load_timeframe call, so the tier figures are 1h figures. Wired at 1h (corrected 2026-11-18 per the wave-2 review; the original 1d wiring rested on REPORT §1.1's footnote, which the primary records contradict). The judged datasets were BTC/ETH/SOL only; the round's judged universe per RESULTS_RD.md is crypto30, registered here as the lane universe. Deploy note: the 1h lane requires STRATEX_TIMEFRAMES to include 1h and a >=262-bar 1h fetch at deploy; until then this entry stays registered-but-not-allowlisted. Judged bracket is the module's own (SL 2.5 x ATR(14), TP 6.0 x ATR(14), extracted by module_eval), not BR24. Stop-cap override max_stop_pct=0.25 per the FWD-012 check recorded in this entry (re-measured at the judged 1h on the judged datasets: max stop 0.1665 of price over all bars >= warmup, 0.1284 over entry bars; the original 1.20 rested on a 1d-fixture measurement and is superseded; override changes admissibility only).",
    },
    "choppiness_breakout": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close breaks above the prior-20-bar Donchian high AND Choppiness Index (14) < 45 (trending regime) AND close > EMA(200). SHORT: close breaks below the prior-20-bar Donchian low AND CHOP(14) < 45 AND close < EMA(200). Judged exactly as the module's own get_signal() evaluated by rigorous_backtest/module_eval.py (stage-1 harness): trailing <=500-bar windows, bars from 260, signal on close of bar i, entry at open of bar i+1 under the MODULE convention.",
        "sl_method": "2.0 * ATR(20) at signal bar (the module's OWN judged bracket — module_eval kept the module's sl/tp; the judged source's governor clamp helper was never called by its get_signal and is NOT applied here)",
        "tp_method": "4.5 * ATR(20) at signal bar (the module's OWN judged bracket)",
        "rr_ratio": 2.25,
        "oos_win_rate_prior": 0.3564,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 7.4,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        # TASK-STR-FWD-012 stop-cap check, RE-MEASURED at the judged
        # 1h on the judged datasets (BTC/ETH/SOL 1h, 27,048 bars
        # each, 2023-10 to 2026-10): judged stop 2.0 x ATR(20) /
        # price — max 0.0853 over entry bars and 0.1152 over all
        # bars >= warmup (pooled; SOLUSDT is the max on both).
        # BELOW the 0.15 engine-global cap, so NO max_stop_pct
        # override is carried: at the judged timeframe the judged
        # stops never reach the cap on the judged universe. (The
        # original 0.80 override rested on a measurement over the
        # fwd002 1d fixtures — max 0.6667 — not at the judged
        # timeframe; superseded by this 1h re-measurement,
        # 2026-11-18.)
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): choppiness_breakout @ CRYPTO30 1h meets the second tier (OOS expectancy +0.074%/trade, PF 1.0550, 940 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Timeframe provenance: JUDGED AT 1h — the stage-1 row record's timeframe field is '1h' and its data_provenance is keyed BTCUSDT_1h/ETHUSDT_1h/SOLUSDT_1h with 27,048 hourly rows per symbol (2023-10 to 2026-10); the harness's timeframe inference (run_all._infer_primary_timeframe, default '1h' — neither module's text names a timeframe) SELECTED the 1h dataset in stage1.py's load_timeframe call, so the tier figures are 1h figures. Wired at 1h (corrected 2026-11-18 per the wave-2 review; the original 1d wiring rested on REPORT §1.1's footnote, which the primary records contradict). The judged datasets were BTC/ETH/SOL only; the round's judged universe per RESULTS_RD.md is crypto30, registered here as the lane universe. Deploy note: the 1h lane requires STRATEX_TIMEFRAMES to include 1h and a >=262-bar 1h fetch at deploy; until then this entry stays registered-but-not-allowlisted. Judged bracket is the module's own (SL 2.0 x ATR(20), TP 4.5 x ATR(20), extracted by module_eval); the judged source's uncalled governor-clamp helper is not applied. No stop-cap override: the FWD-012 check recorded in this entry was re-measured at the judged 1h on the judged datasets and the judged stop reaches at most 0.1152 of price (0.0853 over entry bars) — below the 0.15 engine-global cap (the original 0.80 override rested on a 1d-fixture measurement and is superseded).",
    },
    "psar_trend_af001_max010": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Entries on Parabolic SAR trend flips (step 0.01, max AF 0.10): the SAR state machine is computed over the whole frame from bar 0; a flip to uptrend enters LONG, a flip to downtrend enters SHORT. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py _psar_flip_entries(df, 0.01, 0.10, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3765,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 182.8,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): psar_trend/af0.01_max0.10 @ CRYPTO30 1d meets the second tier (OOS expectancy +1.828%/trade, PF 1.2165, 648 OOS trades, 3/5 positive folds, PF @2x costs 1.1957) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. TASK-STR-FWD-012 stop check: judged stop 2.0 x ATR(14) on 1d crypto fixtures reaches 28.4% of price at entry bars (SOL 1d) and 71.28% across all fixture bars — structurally above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.90 (sanity bound above the measured max; the override changes admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "psar_trend_af002_max020": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Entries on Parabolic SAR trend flips (step 0.02, max AF 0.20): the SAR state machine is computed over the whole frame from bar 0; a flip to uptrend enters LONG, a flip to downtrend enters SHORT. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py _psar_flip_entries(df, 0.02, 0.20, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3671,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 144.7,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): psar_trend/af0.02_max0.20 @ CRYPTO30 1d meets the second tier (OOS expectancy +1.447%/trade, PF 1.1526, 651 OOS trades, 2/5 positive folds, PF @2x costs 1.1346) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. TASK-STR-FWD-012 stop check: judged stop 2.0 x ATR(14) on 1d crypto fixtures reaches 28.4% of price at entry bars (SOL 1d) and 71.28% across all fixture bars — structurally above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.90 (sanity bound above the measured max; the override changes admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "ts_momentum": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: ROC(72) crosses up through 0 (close/close[-72] - 1 moves from <= 0 to > 0). SHORT: ROC(72) crosses down through 0. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_ts_momentum(df, 72, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.4251,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 437.6,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): ts_momentum/roc72 @ CRYPTO30 1d meets the second tier (OOS expectancy +4.376%/trade, PF 1.6049, 334 OOS trades, 5/5 positive folds, PF @2x costs 1.5760) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.0 x ATR(14) measured up to 71.3% of price over all post-warmup bars on the fwd002 SOLUSDT 1d fixture slice (11.0% at entry bars) — above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.90 (sanity bound only; FWD-006 sizes by risk / stop distance).",
    },
    "ts_momentum_roc42": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: ROC(42) crosses up through 0 (close/close[-42] - 1 moves from <= 0 to > 0). SHORT: ROC(42) crosses down through 0. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_ts_momentum(df, 42, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.4283,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 321.3,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): ts_momentum/roc42 @ CRYPTO30 1d meets the second tier (OOS expectancy +3.213%/trade, PF 1.4354, 460 OOS trades, 4/5 positive folds, PF @2x costs 1.4088) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.0 x ATR(14) measured up to 71.3% of price over all post-warmup bars on the fwd002 SOLUSDT 1d fixture slice (18.4% at entry bars) — above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.90 (sanity bound only; FWD-006 sizes by risk / stop distance).",
    },
    "ts_momentum_roc168": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: ROC(168) crosses up through 0 (close/close[-168] - 1 moves from <= 0 to > 0). SHORT: ROC(168) crosses down through 0. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_ts_momentum(df, 168, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3925,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 157.9,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): ts_momentum/roc168 @ CRYPTO30 1d meets the second tier (OOS expectancy +1.579%/trade, PF 1.1776, 265 OOS trades, 3/5 positive folds, PF @2x costs 1.1580) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.0 x ATR(14) measured up to 71.3% of price over all post-warmup bars on the fwd002 SOLUSDT 1d fixture slice (17.1% at entry bars) — above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.90 (sanity bound only; FWD-006 sizes by risk / stop distance).",
    },
    "ts_momentum_roc42_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: ROC(42) crosses up through 0 (close/close[-42] - 1 moves from <= 0 to > 0). SHORT: ROC(42) crosses down through 0. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_ts_momentum(df, 42, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3672,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 33.8,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.25,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): ts_momentum/roc42 @ CRYPTO30 4h meets the second tier (OOS expectancy +0.338%/trade, PF 1.0993, 2,906 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.0 x ATR(14) measured up to 13.0% of price over all post-warmup bars on the fwd002 SOLUSDT 4h fixture slice (8.5% at entry bars) — close to the 0.15 engine-global cap on only two fixture symbols, and the CRYPTO30 volatile tail plausibly exceeds it — so this entry carries max_stop_pct 0.25 as a pre-emptive sanity bound (FWD-006 sizes by risk / stop distance). Duplicate-stream alias: RD-001's ts_momentum/roc42_4h row (303 OOS trades, +0.243%/trade, PF 1.0969, 2/5 positive folds; flags: holdout FAIL, SOL = 97% of profit) is the SAME judged stream — identical signal (rd/stage3.py fam_ts_momentum is the same ROC-cross logic as families2 sig_ts_momentum; RD-002's harness reproduced RD-001's published roc42_4h row BIT-IDENTICALLY — results_rd2/sanity_checks.json), identical bracket (2.0/4.0) and warmup (260) — and is NOT separately wired (dedupe per audit §1.4); this crypto30 config is its single lane admission.",
    },
    "ts_momentum_roc168_rd001": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: ROC(168) crosses up through 0. SHORT: ROC(168) crosses down through 0. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd/stage3.py fam_ts_momentum(df, 168) at 1h (identical ROC-cross logic to rd2/families2.py sig_ts_momentum), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3805,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 8.2,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.25,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md §1.1): ts_momentum/roc168_1h @ CRYPTO30 1h — a TASK-STR-RD-001 row — meets the second tier (OOS expectancy +0.082%/trade, PF 1.0663, 678 OOS trades, 4/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. Flags from the RD-001 record: holdout FAIL; SOL = 84% of profit (concentration). Judged by RD-001's stage-3 code (rigorous_backtest/rd/stage3.py fam_ts_momentum(df, 168), bracket 2.0/4.0, warmup 260) on its stage-3 cache panel (BTC/ETH/SOL — rd/common.py SYMBOLS); the identical signal was later re-judged by RD-002 on crypto30, and this admission trades the CRYPTO30 universe. Cost basis 16.0 bps round trip (rd/common.py harness standard). FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.0 x ATR(14) measured up to 13.0% of price over all post-warmup bars on the fwd002 SOLUSDT 4h fixture slice (9.1% at entry bars) — close to the 0.15 engine-global cap on only two fixture symbols, and the CRYPTO30 volatile tail plausibly exceeds it — so this entry carries max_stop_pct 0.25 as a pre-emptive sanity bound (FWD-006 sizes by risk / stop distance). Stop measured on the 4h fixtures: per-bar ATR% only shrinks as the timeframe shortens, so the 4h figure is a conservative upper bound for this 1h config.",
    },
    "tsmom2_dual_crypto": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: ROC(90) crosses up through 0 AND close > EMA(200). SHORT: ROC(90) crosses down through 0 AND close < EMA(200). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_dual_momentum(df, 90, warmup), warmup 260 bars.",
        "sl_method": "2.5 * ATR(14) at signal bar (judged bracket, families2 tsmom2_dual spec)",
        "tp_method": "5.0 * ATR(14) at signal bar (judged bracket, families2 tsmom2_dual spec)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3627,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 40.2,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.25,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): tsmom2_dual/roc90_ema200 @ CRYPTO30 4h meets the second tier (OOS expectancy +0.402%/trade, PF 1.0965, 1,580 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. FWD-012 stop-cap: judged stop 2.5 x ATR(14) measured up to 16.3% of price over all post-warmup bars on the fwd002 SOLUSDT 4h fixture slice (10.4% at entry bars) — above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.25 (sanity bound only; FWD-006 sizes by risk / stop distance). Registry key is tsmom2_dual_crypto because the plain tsmom2_dual key is taken by the EXCLUDED comm7 documentary registration (roc30_ema200 @ comm7 4h) — a different judged object; records never blended.",
    },
    "ha_trend": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Heikin-Ashi trend (HA candles recursive from the frame start): LONG after TWO consecutive bull HA candles with no lower wick (HA-close > HA-open and HA-open == HA-low); SHORT after two consecutive bear HA candles with no upper wick (HA-close < HA-open and HA-open == HA-high). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_ha(df, True, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3639,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 167.1,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): ha_trend/two_candle @ CRYPTO30 1d meets the second tier (OOS expectancy +1.671%/trade, PF 1.1878, 775 OOS trades, 3/5 positive folds, PF @2x costs 1.1682) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. TASK-STR-FWD-012 stop check: judged stop 2.0 x ATR(14) on 1d crypto fixtures reaches 71.28% of price at an entry bar (SOL 1d crash bar) — structurally above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.90 (sanity bound above the measured max; the override changes admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "ha_trend_two_candle_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Heikin-Ashi trend (HA candles recursive from the frame start): LONG after TWO consecutive bull HA candles with no lower wick (HA-close > HA-open and HA-open == HA-low); SHORT after two consecutive bear HA candles with no upper wick (HA-close < HA-open and HA-open == HA-high). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_ha(df, True, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3685,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 29.0,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.30,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): ha_trend/two_candle @ CRYPTO30 4h meets the second tier (OOS expectancy +0.290%/trade, PF 1.0764, 5,639 OOS trades, 4/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. TASK-STR-FWD-012 stop check: judged stop 2.0 x ATR(14) on 4h fixtures measures at most 13.0% of price across all BTC/SOL bars (entry-bar max in this entry's record), under the 0.15 engine-global cap on the fixtures — but the CRYPTO30 tail (INJ/SUI/APT-class names) plausibly exceeds it, so this entry carries max_stop_pct 0.30 (rounded sanity bound above the measured max; admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "ha_trend_one_candle": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Heikin-Ashi trend (HA candles recursive from the frame start): LONG on a bull HA candle with no lower wick (HA-close > HA-open and HA-open == HA-low); SHORT on a bear HA candle with no upper wick (HA-close < HA-open and HA-open == HA-high). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_ha(df, False, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3455,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 63.4,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): ha_trend/one_candle @ CRYPTO30 1d meets the second tier (OOS expectancy +0.634%/trade, PF 1.0684, 877 OOS trades, 2/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. TASK-STR-FWD-012 stop check: judged stop 2.0 x ATR(14) on 1d crypto fixtures reaches 71.28% of price at an entry bar (SOL 1d crash bar) — structurally above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.90 (sanity bound above the measured max; the override changes admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "ha_trend_one_candle_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "Heikin-Ashi trend (HA candles recursive from the frame start): LONG on a bull HA candle with no lower wick (HA-close > HA-open and HA-open == HA-low); SHORT on a bear HA candle with no upper wick (HA-close < HA-open and HA-open == HA-high). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_ha(df, False, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3671,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 23.9,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.30,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): ha_trend/one_candle @ CRYPTO30 4h meets the second tier (OOS expectancy +0.239%/trade, PF 1.0625, 6,082 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. TASK-STR-FWD-012 stop check: judged stop 2.0 x ATR(14) on 4h fixtures measures at most 13.0% of price across all BTC/SOL bars (entry-bar max in this entry's record), under the 0.15 engine-global cap on the fixtures — but the CRYPTO30 tail (INJ/SUI/APT-class names) plausibly exceeds it, so this entry carries max_stop_pct 0.30 (rounded sanity bound above the measured max; admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "stoch_reversion": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: stochastic %K(14, window includes current bar) smoothed by SMA(3) crosses up through 20. SHORT: %K crosses down through 80. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_stoch(df, filtered=False, warmup) on the FOREX28 panel, warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3863,
        "total_friction_bps": 10.0,
        "expected_net_edge_bps": 28.6,
        "minimum_required_edge": 0.0005,
        "lane_assets": FOREX28_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "forward_venues": ["oanda_practice"],
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): stoch_reversion/k14_raw @ FOREX28 1d meets the second tier (OOS expectancy +0.286%/trade, PF 1.2623, 365 OOS trades, 4/5 positive folds, PF @2x costs 1.1796) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. This is the BEST forex row in the audit and a measured member of the low-correlation forex28 3-stream combo (mean correlation 0.083, audit §4). Judged cost basis is the RD-002 forex model (rigorous_backtest/rd2/costs2.py: 6 bps round trip majors, 10 bps minors/crosses); total_friction_bps carries the 10.0 panel maximum. Stop check (TASK-STR-FWD-012): judged stops measured max 2.06% (EURUSD), 2.64% (GBPJPY), 1.74% (USDJPY) at entry bars on the fwd002 FX fixtures — far below the 0.15 engine-global cap, so no max_stop_pct override. OANDA entry: execution rides the governed OANDA runner (separate PR); this entry carries forward_venues [oanda_practice] so that runner can discover it.",
    },
    "stoch_reversion_k14_filt": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: stochastic %K(14, window includes current bar) smoothed by SMA(3) crosses up through 20 AND close > EMA(200). SHORT: %K crosses down through 80 AND close < EMA(200). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_stoch(df, filtered=True, warmup) on the FOREX28 panel, warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3519,
        "total_friction_bps": 10.0,
        "expected_net_edge_bps": 7.2,
        "minimum_required_edge": 0.0005,
        "lane_assets": FOREX28_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "forward_venues": ["oanda_practice"],
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): stoch_reversion/k14_filt @ FOREX28 1d meets the second tier (OOS expectancy +0.072%/trade, PF 1.0613, 216 OOS trades, 2/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Judged cost basis is the RD-002 forex model (costs2.py: 6 bps majors, 10 bps minors/crosses); total_friction_bps carries the 10.0 panel maximum. Stop check (TASK-STR-FWD-012): judged stops measured max 1.27% (EURUSD), 2.14% (GBPJPY), 1.39% (USDJPY) at entry bars on the fwd002 FX fixtures — no max_stop_pct override needed. OANDA entry: execution rides the governed OANDA runner (separate PR); forward_venues [oanda_practice] carried for discovery.",
    },
    "stoch_reversion_crypto": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: stochastic %K(14, window includes current bar) smoothed by SMA(3) crosses up through 20. SHORT: %K crosses down through 80. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_stoch(df, filtered=False, warmup) on the CRYPTO30 panel, warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3706,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 51.8,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): stoch_reversion/k14_raw @ CRYPTO30 1d meets the second tier (OOS expectancy +0.518%/trade, PF 1.0510, 688 OOS trades, 2/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Stop-cap override (TASK-STR-FWD-012): judged 2.0 x ATR(14) stops measured up to 58.74% of price at entry bars on the SOLUSDT 1d fixture (BTCUSDT 12.38%) — above the 0.15 engine-global cap — so max_stop_pct 0.90 is declared (sanity bound only; admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "bar_patterns": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: bullish engulfing candle (bull candle whose body fully engulfs the prior bear candle's body). SHORT: bearish engulfing (bear candle whose body fully engulfs the prior bull candle's body). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_engulfing(df, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3850,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 158.7,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): bar_patterns/engulfing @ CRYPTO30 1d meets the second tier (OOS expectancy +1.587%/trade, PF 1.1743, 548 OOS trades, 3/5 positive folds, PF @2x costs 1.1555) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. TASK-STR-FWD-012 stop check: judged stop 2.0 x ATR(14) on 1d crypto fixtures reaches 28.4% of price at entry bars (SOL 1d) and 71.28% across all fixture bars — structurally above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.90 (sanity bound above the measured max; the override changes admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "bar_patterns_inside_bar_4h": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: bar i-1 is an inside bar (wholly inside bar i-2) and the close of bar i breaks above bar i-2's high. SHORT: close of bar i breaks below bar i-2's low. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_inside_bar(df, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3617,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 20.9,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.30,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): bar_patterns/inside_bar @ CRYPTO30 4h meets the second tier (OOS expectancy +0.209%/trade, PF 1.0556, 3,481 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. TASK-STR-FWD-012 stop check: judged stop 2.0 x ATR(14) on 4h fixtures measures at most 13.0% of price across all BTC/SOL bars (entry-bar max in this entry's record), under the 0.15 engine-global cap on the fixtures — but the CRYPTO30 tail (INJ/SUI/APT-class names) plausibly exceeds it, so this entry carries max_stop_pct 0.30 (rounded sanity bound above the measured max; admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "macd_trend": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: MACD(12,26) histogram crosses up through 0. SHORT: histogram crosses down through 0. No EMA(200) filter (hist_raw). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_macd(df, False, warmup), warmup 260 bars.",
        "sl_method": "2.5 * ATR(14) at signal bar (judged bracket BR25)",
        "tp_method": "5.0 * ATR(14) at signal bar (judged bracket BR25)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.4201,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 584.0,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): macd_trend/hist_raw @ CRYPTO30 1d meets the second tier (OOS expectancy +5.840%/trade, PF 1.5522, 369 OOS trades, 2/5 positive folds, PF @2x costs 1.5330) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. Fold support is WEAK (2/5 positive folds) — flagged here as judged; its PF @2x costs of 1.5330 is the most cost-robust figure in the audit. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. This stream is also a member of the live Stage-C sleeve book under its sleeve key — a distinct judged object; records never blended. FWD-012 stop-cap: judged stop 2.5 x ATR(14) measured up to 89.1% of price over all post-warmup bars on the fwd002 SOLUSDT 1d fixture slice (48.0% at entry bars) — above the 0.15 engine-global cap — so this entry carries max_stop_pct 0.90 (sanity bound only; FWD-006 sizes by risk / stop distance).",
    },
    "vol_compression": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: ATR(7) at its trailing 50-bar rolling minimum (squeeze) AND close above the prior 10-bar high AND close > EMA(200). SHORT: squeeze AND close below the prior 10-bar low AND close < EMA(200). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_vol_compression(df, filtered=True, warmup) on CRYPTO30 1h bars, warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3732,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 18.2,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): vol_compression/squeeze_ema200 @ CRYPTO30 1h meets the second tier (OOS expectancy +0.182%/trade, PF 1.1310, 1,104 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Stop-cap override (TASK-STR-FWD-012): measured on the 4h fixture frame (conservative upper bound for the judged 1h — per-bar ATR shrinks with timeframe), entry-bar stops reach only 4.97% but the all-bar 4h stop distribution reaches 56.04% on SOLUSDT, so a 1h stop plausibly exceeds the 0.15 engine-global cap on the volatile tail; max_stop_pct 0.90 declared (sanity bound only; admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "vol_compression_squeeze_raw": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: ATR(7) at its trailing 50-bar rolling minimum (squeeze) AND close above the prior 10-bar high. SHORT: squeeze AND close below the prior 10-bar low. No EMA(200) gate. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families3.py sig_vol_compression(df, filtered=False, warmup) on CRYPTO30 1h bars, warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3655,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 7.6,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): vol_compression/squeeze_raw @ CRYPTO30 1h meets the second tier (OOS expectancy +0.076%/trade, PF 1.0502, 1,926 OOS trades, 3/5 positive folds) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Stop-cap override (TASK-STR-FWD-012): as for vol_compression (4h-fixture measurement; entry-bar max 4.97% on SOLUSDT 4h, all-bar tail 56.04%) — max_stop_pct 0.90 declared (sanity bound only; admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "volume_breakout": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: close above the prior 20-bar high AND volume > 1.5 x the trailing 20-bar mean volume. SHORT: close below the prior 20-bar low AND the same volume confirmation. Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_volume_breakout(df, confirm=1.5, warmup), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3925,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 241.7,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): volume_breakout/donch20_vol1.5 @ CRYPTO30 1d meets the second tier (OOS expectancy +2.417%/trade, PF 1.3038, 558 OOS trades, 3/5 positive folds, PF @2x costs 1.2801) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Duplicate-alias note: volume_breakout/donch20_novol @ CRYPTO30 1d is an identical trade stream to donchian_turtle/n20_b24 (audit §1.4), which is NOT separately wired here — dedupe per audit §1.4; the donchian crew wires that stream canonically. Stop-cap override (TASK-STR-FWD-012): judged stops measured up to 71.28% of price at entry bars on the SOLUSDT 1d fixture (the 2022-11-09 FTX-collapse bar; BTCUSDT max 12.89%) — above the 0.15 engine-global cap — so max_stop_pct 0.90 is declared (sanity bound only; admissibility only, FWD-006 sizes by risk / stop distance). Module note: the pre-existing strategy_volume_breakout.py was a different, never-judged, governance-UNREGISTERED module (prior-10-bar break + EMA50/200 filter); the judged port replaces its logic — see the module docstring and PR body.",
    },
    "mtf_confluence": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "4h",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: EMA(20) crosses above EMA(50) AND close > EMA(200), all on the cell's own 4h series. SHORT: cross down AND close < EMA(200). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_mtf_native(df, warmup) — the h4_native_ema200 configuration consumes NO higher-timeframe series (its fn ignores the aux frame; rd2/grid.py loads aux only for 15m/1h cells), warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3807,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 49.0,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): mtf_confluence/h4_native_ema200 @ CRYPTO30 4h meets the second tier (OOS expectancy +0.490%/trade, PF 1.1538, 1,668 OOS trades, 4/5 positive folds, PF @2x costs 1.1006) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Stop-cap override (TASK-STR-FWD-012): entry-bar stops measured max 8.13% (SOLUSDT 4h fixture) but the all-bar 4h stop distribution reaches 56.04% on SOLUSDT, so a stop plausibly exceeds the 0.15 engine-global cap on the volatile tail — max_stop_pct 0.90 declared (sanity bound only; admissibility only, FWD-006 sizes by risk / stop distance).",
    },
    "mtf_confluence_1d": {
        "status": "FORWARD_TEST",
        "version": "v1.0.0 (TASK-STR-FWD-019)",
        "timeframe": "1d",
        "execution_model": "RULE_BASED",
        "entry_conditions": "LONG: EMA(20) crosses above EMA(50) AND close > EMA(200), all on the cell's own 1d series. SHORT: cross down AND close < EMA(200). Signal on close of bar i, entry at open of bar i+1. Judged: rigorous_backtest/rd2/families2.py sig_mtf_native(df, warmup) at 1d — the h4_native_ema200 fn ignores the aux frame and grid.py loads aux only for 15m/1h cells, so the judged 1d cell ran on 1d bars natively (NOT on a 4h series); this entry wires exactly that construction, warmup 260 bars.",
        "sl_method": "2.0 * ATR(14) at signal bar (judged bracket BR24)",
        "tp_method": "4.0 * ATR(14) at signal bar (judged bracket BR24)",
        "rr_ratio": 2.0,
        "oos_win_rate_prior": 0.3779,
        "total_friction_bps": 16.0,
        "expected_net_edge_bps": 147.2,
        "minimum_required_edge": 0.0005,
        "lane_assets": CRYPTO30_SYMBOLS,
        "validated_assets": [],
        "forward_protocol": True,
        "risk_per_trade_pct": 0.001,
        "max_heat_pct": 0.02,
        "forward_lane": "FORWARD_TEST",
        "max_stop_pct": 0.90,
        "reason": "TASK-STR-FWD-019 WAVE-2 near-miss admission (owner implement-all directive 2026-11-18; audit ~/workspace/str-nearmiss/REPORT.md): mtf_confluence/h4_native_ema200 @ CRYPTO30 1d meets the second tier (OOS expectancy +1.472%/trade, PF 1.1902, 217 OOS trades, 2/5 positive folds, PF @2x costs 1.1679) but did NOT pass the full frozen bar (Bonferroni at programme N=3,899) — not a promotion, not VALIDATED. FORWARD_TEST lane terms as for bollinger_trend (0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill at expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with VALIDATED scorecards. Faithfulness note: the judged 1d cell was computed by sig_mtf_native on 1d bars (the h4_native fn consumes no 4h series — see entry_conditions), so this entry wires the judged construction itself, not a re-judgement. Stop-cap override (TASK-STR-FWD-012): judged stops measured up to 18.66% of price at entry bars on the SOLUSDT 1d fixture (BTCUSDT 12.89%) — above the 0.15 engine-global cap — so max_stop_pct 0.90 is declared (sanity bound only; admissibility only, FWD-006 sizes by risk / stop distance).",
    },
}

# Stored research estimates are not runtime priors unless a strategy has been
# explicitly promoted after a reproducible validation review. This also keeps
# stale metrics from disabled or observe-only candidates out of accidental
# direct callers that inspect the registry without applying governance.
# TASK-STR-FWD-003: FORWARD_TEST lane entries keep their (judged, disclosed)
# priors and edge estimates for the same reason VALIDATED entries do — the
# daemon's expectancy gate reads them — but their tradable universe lives
# under "lane_assets", never "validated_assets": the lane is not a
# validation, and nothing may mistake it for one.
# TASK-STR-FWD-003 FOLLOW-UP (2026-11-16): that exemption was scoped to the
# FORWARD_TEST *label*, so it also covered the lane's non-tradable
# registrations (tsmom2_dual and the four RD-003 comm7 cells —
# forward_protocol False, lane_assets empty, no production module). Those
# records carried live-looking priors/edges in the runtime registry even
# though they can never execute, indistinguishable from the three
# executable entrants to any consumer counting registry records. The
# exemption is now scoped to tradability: only a lane-EXECUTABLE
# FORWARD_TEST entry (forward_protocol True AND a non-empty lane_assets)
# keeps its runtime prior/edge. Every FORWARD_TEST entry is stamped
# "runtime_priors_nulled" so the record itself shows whether its numbers
# are live runtime claims (False) or withdrawn (True) — visibly nulled,
# never silently counted. The judged evidence itself is NOT deleted: it
# stays in the *_STRATEGY config dicts above and in each entry's reason.
def _lane_executable(_entry: dict[str, Any]) -> bool:
    return (
        _entry.get("status") == "FORWARD_TEST"
        and _entry.get("forward_protocol") is True
        and bool(_entry.get("lane_assets"))
    )


for _strategy_entry in PRODUCTION_STRATEGY_REGISTRY.values():
    if _strategy_entry.get("status") == "FORWARD_TEST":
        _strategy_entry["runtime_priors_nulled"] = not _lane_executable(
            _strategy_entry
        )
    if _strategy_entry.get("status") == "VALIDATED" or _lane_executable(
        _strategy_entry
    ):
        continue
    _strategy_entry["oos_win_rate_prior"] = None
    _strategy_entry["expected_net_edge_bps"] = None
    _strategy_entry["validated_assets"] = []
