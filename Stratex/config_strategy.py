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
        "forward_lane": "FORWARD_TEST",
        "reason": "TASK-STR-RD-002 WATCHLIST: bollinger_trend/p50_sd2.0 @ CRYPTO30 1d passed the mechanical bar (expectancy +3.5448%/trade, PF 1.4562, 420 OOS trades, 5/5 positive folds, holdout) but FAILED Bonferroni significance at N=1,557 — not a promotion. Owner directed 2026-11-15 (TASK-STR-FWD-003) that near-bar configurations be decided by real demo forward evidence. FORWARD_TEST lane: DEMO venues only, phase-3 protocol (TASK-STR-FWD-006 package: 0.1% per-trade risk on venue equity, 2% aggregate heat cap, 3% daily breaker, kill criteria expectancy<0 or PF<1.0 after >=50 closed trades or mark-to-market drawdown >5% of venue equity), fills tagged FORWARD_TEST, never blended with the VALIDATED entrants' scorecards.",
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
        "forward_lane": "FORWARD_TEST",
        "reason": "TASK-STR-RD-002 WATCHLIST: shock_breakout/k1.0 @ CRYPTO30 1d passed the mechanical bar (expectancy +2.6957%/trade, PF 1.3179, 732 OOS trades, 4/5 positive folds, holdout) but FAILED Bonferroni significance at N=1,557 — not a promotion. Owner directed 2026-11-15 (TASK-STR-FWD-003) that near-bar configurations be decided by real demo forward evidence. FORWARD_TEST lane terms as for bollinger_trend. (Distinct from sleeve_shock_breakout, the sleeve's own component module/configuration — different judged object, different records.)",
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
    }
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
