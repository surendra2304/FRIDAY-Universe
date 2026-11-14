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
# is not governed here and is excluded pending its RD-002 retest.
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
    }
}

# Stored research estimates are not runtime priors unless a strategy has been
# explicitly promoted after a reproducible validation review. This also keeps
# stale metrics from disabled or observe-only candidates out of accidental
# direct callers that inspect the registry without applying governance.
for _strategy_entry in PRODUCTION_STRATEGY_REGISTRY.values():
    if _strategy_entry.get("status") != "VALIDATED":
        _strategy_entry["oos_win_rate_prior"] = None
        _strategy_entry["expected_net_edge_bps"] = None
        _strategy_entry["validated_assets"] = []
