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
        "reason": "TASK-STR-RD-002 winner: ichimoku_trend/tk_cloud @ CRYPTO30 4h passed the full bar (expectancy>0, PF 1.278 >= 1.2, 2,302 OOS trades, >=80% folds, untouched holdout), Bonferroni at N=1,557 and the 2x-cost stress (PF 1.222). Owner approved forward demo trading 2026-11-15 (TASK-STR-FWD-002). Phase-3 protocol: 1% risk cap, 3% daily breaker, kill criteria (expectancy<0 or PF<1.0 after >=50 closed trades, or strategy drawdown >5% of equity) auto-pause via measurement/forward_guard.py. DEMO venue only; live trading prohibited.",
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
        "reason": "TASK-STR-RD-002 winner: dow_effect/reversal @ CRYPTO30 1d passed the full bar (expectancy>0, PF 1.257 >= 1.2, 3,660 OOS trades, >=80% folds, untouched holdout), Bonferroni at N=1,557 and the 2x-cost stress (PF 1.206). Calendar effect — flagged in RD-002 as most prone to era decay; the forward window is the arbiter. Owner approved forward demo trading 2026-11-15 (TASK-STR-FWD-002). Time exit (max_bars=5) enforced by the daemon (no broker-native equivalent). Phase-3 protocol as for ichimoku_trend. DEMO venue only; live trading prohibited.",
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
