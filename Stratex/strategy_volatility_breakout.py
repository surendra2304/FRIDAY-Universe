"""strategy_volatility_breakout — TASK-STR-FWD-019 FORWARD-TEST lane
entrant (RD-001 stage-1 discovery module, previously UNREGISTERED).

Judged configuration (TASK-STR-RD-001 stage 1, discovery):
strategy_volatility_breakout @ CRYPTO30 — 520 pooled OOS trades,
+0.131%/trade, PF 1.0669, win rate 0.3519, 3/5 positive folds
(results_rd/stage5_synthesis.json ranked_table; stage-1 row in
results_rd/stage1_rows/strategy_volatility_breakout.json). It meets
the owner's second tier (expectancy > 0, PF >= 1.05, >= 200 OOS
trades, pre-Bonferroni) but did NOT pass the full frozen bar — not
a promotion, not VALIDATED.

Timeframe provenance (stated exactly): the tier figures are 1h
figures, and this module is wired at 1h. The stage-1 harness
selected each module's dataset by timeframe inference
(run_all._infer_primary_timeframe scans the module text for a
timeframe name and defaults to "1h"; neither discovery module
names one) and rd/stage1.py evaluated on load_timeframe("1h") —
the inference SELECTED the dataset, it did not merely label it.
The stage-1 row JSON records timeframe "1h" and data_provenance
keyed BTCUSDT_1h / ETHUSDT_1h / SOLUSDT_1h with 27,048 hourly
rows per symbol (2023-10 → 2026-10; a 1d set over the same span
has ~1,127 rows). The judged datasets were BTC/ETH/SOL (stage-1
SYMBOLS); the round's judged universe per RESULTS_RD.md Stages
1/3 is crypto30, which is the lane universe registered here.
CORRECTION (2026-11-18, wave-2 review comment 6975928782): this
module was originally wired at 1d on the basis of the near-miss
audit REPORT §1.1 footnote claiming stage-1 "ran one daily
configuration per module" — the primary records contradict that
footnote, and the wiring now matches the judged 1h
configuration.

Judged semantics (rigorous_backtest/module_eval.py, the stage-1
harness): the module's OWN get_signal() was called on trailing
<=500-bar windows (WINDOW = 500) from bar 260 (WARMUP_BARS), and
the MODULE simulation convention kept the module's own bracket —
so the judged bracket is this module's own: SL 2.5 x ATR(14),
TP 6.0 x ATR(14), ATR as a simple rolling mean of true range (NOT
the EWM ATR of rd/common). Costs: 16 bps round trip (rd/common
COSTS, harness standard). The judged module file was deleted from
the tree by TASK-STR-CLEANUP-001 (2026-11-14) after judgement; this
port is line-faithful to the judged source (last pre-deletion
revision, commit bd9585c97b). The judged get_signal dropped a
still-forming final bar by calendar date; the lane-standard
equivalent used here is the bollinger template's _closed_frame
timestamp drop. The shared features.add_features pipeline chosen
by the harness adds columns only and does not alter the OHLC this
signal reads, so the identity pipeline used here is equivalent.

Governance: registered FORWARD_TEST in config_strategy.py —
executable on DEMO venues only (fail-closed in
strategies/strategy_registry.py), phase-3 forward protocol
protections (TASK-STR-FWD-006 package), fills tagged FORWARD_TEST.
Scorecards must never blend this lane with the VALIDATED entrants.
Equivalence is pinned by tests/test_fwd019_rd001_discovery_lane.py
against a transcription of the judged module evaluated exactly as
module_eval evaluated it, on the fwd002 fixture slices.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import VOLATILITY_BREAKOUT_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1h"))
BAR_SECONDS = 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
WINDOW = int(_CFG.get("WINDOW", 500))
ATR_PERIOD = int(_CFG.get("ATR_PERIOD", 14))
ATR_AVG_PERIOD = int(_CFG.get("ATR_AVG_PERIOD", 20))
EXPANSION_MULT = float(_CFG.get("EXPANSION_MULT", 1.2))
DONCHIAN_PERIOD = int(_CFG.get("DONCHIAN_PERIOD", 10))
EMA_FAST = int(_CFG.get("EMA_FAST", 50))
EMA_SLOW = int(_CFG.get("EMA_SLOW", 200))
SL_ATR = float(_CFG.get("SL_ATR", 2.5))
TP_ATR = float(_CFG.get("TP_ATR", 6.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3519))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged-logic port (strategy_volatility_breakout.py @ bd9585c97b,
# evaluated via rigorous_backtest/module_eval.py)
# ---------------------------------------------------------------------------

def _true_range(df: pd.DataFrame) -> pd.Series:
    """True range exactly as the judged module computes it."""
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    prev_close = close.shift(1)
    return pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)


def atr_sma(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """The judged module's ATR: simple rolling mean of true range."""
    return _true_range(df).rolling(period).mean()


def _signal_on_window(work: pd.DataFrame) -> Optional[Tuple[str, float, float]]:
    """The judged get_signal body on one trailing window (closed bars
    only — the judged calendar-date forming-bar drop is handled by
    _closed_frame on the live path and is a no-op on the harness's
    historical windows). Returns (side, sl_dist, tp_dist) or None."""
    if work is None or len(work) < 205:
        return None
    if not {"close", "high", "low"}.issubset(work.columns):
        return None
    close = work["close"].astype(float)
    high = work["high"].astype(float)
    low = work["low"].astype(float)

    ema_fast = close.ewm(span=EMA_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=EMA_SLOW, adjust=False).mean()

    atr = _true_range(work).rolling(ATR_PERIOD).mean()
    atr_avg = atr.rolling(ATR_AVG_PERIOD).mean()

    prior_high = high.rolling(DONCHIAN_PERIOD).max().shift(1)
    prior_low = low.rolling(DONCHIAN_PERIOD).min().shift(1)

    c = float(close.iloc[-1])
    a = float(atr.iloc[-1])
    a_avg = float(atr_avg.iloc[-1])
    ef = float(ema_fast.iloc[-1])
    es = float(ema_slow.iloc[-1])
    ph = float(prior_high.iloc[-1])
    pl = float(prior_low.iloc[-1])

    if any(math.isnan(v) for v in (a, a_avg, ef, es, ph, pl)) or a <= 0 or c <= 0 or a_avg <= 0:
        return None

    vol_expanding = a > EXPANSION_MULT * a_avg
    trend_up = ef > es
    trend_down = ef < es

    if c > ph and vol_expanding and trend_up:
        return "BUY", SL_ATR * a, TP_ATR * a
    if c < pl and vol_expanding and trend_down:
        return "SELL", SL_ATR * a, TP_ATR * a
    return None


def signal_masks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """(long_mask, short_mask) — per-bar judged signals, each bar
    evaluated on its trailing <=500-bar window exactly as
    module_eval did (bars before WARMUP_BARS are always False)."""
    long_mask = pd.Series(False, index=df.index)
    short_mask = pd.Series(False, index=df.index)
    for i in range(WARMUP_BARS, len(df)):
        res = _signal_on_window(df.iloc[max(0, i - WINDOW + 1): i + 1])
        if res is None:
            continue
        if res[0] == "BUY":
            long_mask.iloc[i] = True
        elif res[0] == "SELL":
            short_mask.iloc[i] = True
    return long_mask, short_mask


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str]]:
    """Entry list identical to the judged module_eval extraction:
    bars [warmup, len-2] (the harness never evaluates the final bar
    as a signal bar), long before short."""
    out: List[Tuple[int, str]] = []
    for i in range(warmup, len(df) - 1):
        res = _signal_on_window(df.iloc[max(0, i - WINDOW + 1): i + 1])
        if res is None:
            continue
        out.append((i, "LONG" if res[0] == "BUY" else "SHORT"))
    return out


# ---------------------------------------------------------------------------
# Daemon entry point
# ---------------------------------------------------------------------------

def _closed_frame(df: pd.DataFrame, now_s: Optional[float] = None) -> pd.DataFrame:
    """Drop still-forming trailing bars (bar open + duration > now).

    Epoch seconds are computed by timedelta division (resolution-
    independent); the index's int64 view returns its native unit
    (microseconds under pandas 3), which silently disables the
    drop when divided by 1e9 (TASK-STR-FWD-025).
    """
    if df is None or len(df) == 0:
        return df
    now = time.time() if now_s is None else now_s
    idx = df.index
    try:
        epoch = pd.Timestamp("1970-01-01", tz=idx.tz)
        opens = (idx - epoch).total_seconds().to_numpy(dtype=float)
    except Exception:
        return df
    keep = int(np.sum(opens + BAR_SECONDS <= now))
    if keep < len(df):
        return df.iloc[:keep]
    return df


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Evaluate the last closed 1h bar (trailing <=500-bar window,
    as judged); return the daemon signal dict."""
    none_signal: Dict[str, Any] = {"side": None}
    try:
        if df is None or len(df) < WARMUP_BARS + 1:
            return none_signal
        frame = _closed_frame(df)
        if len(frame) < WARMUP_BARS + 1:
            return none_signal
        res = _signal_on_window(frame.iloc[-WINDOW:])
        if res is None:
            return none_signal
        side, sl_dist, tp_dist = res
        return {
            "side": side,
            "sl_dist": sl_dist,
            "tp_dist": tp_dist,
            "win_rate_prior": WIN_RATE_PRIOR,
            "rr_ratio": RR_RATIO,
            "strategy_type": _STRATEGY_TYPE,
        }
    except Exception:
        return none_signal
