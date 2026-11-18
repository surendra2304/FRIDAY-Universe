"""strategy_factory_winner_3 — TASK-STR-FWD-019 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002, governed family, judged "as
coded" from the live module via rigorous_backtest/rd2/gov2.py
``eval_module_cell``, config "bare"): strategy_factory_winner_3:bare
@ FOREX12 4h — 702 pooled OOS trades, +0.0245%/trade, PF 1.0738,
win rate 0.2863, 2/5 positive folds. It meets the owner's second
tier (expectancy > 0, PF >= 1.05, >= 200 OOS trades, pre-Bonferroni)
but did NOT pass the full frozen bar (Bonferroni at programme
N=3,899) — not a promotion, not VALIDATED. The owner directed
2026-11-18 (implement-all) that such near-miss candidates be decided
by real demo forward evidence in the FORWARD_TEST lane.

JUDGED-MODULE STATE (read before touching this file): the live
module gov2 judged (strategy_factory_winners.py +
strategy_factory_winner_3.py) was DELETED from main by
TASK-STR-CLEANUP-001 under the earlier BT-001 evidence rule (its
record there was a different, earlier measurement). The judged
signal code is restored VERBATIM in this wrapper from the
pre-cleanup blobs (strategy_factory_winners.py blob
76d2aeee9a2599c649eddaa0d23b45f66863e4d7; strategy_factory_winner_3.py
blob 418372c9af3c8168c5e9fa916ea99f37f1f69ba2 — the deletion commit
020ea57b's parent), so the code path below is byte-equivalent in
logic to what gov2 evaluated: MACD(12,26,9) cross confluence with
the Bollinger(20,2) mid band, SL 1.5 x ATR(14), TP 4.5 x ATR(14).

DEDUPE: strategy_factory_winner_5:bare @ FOREX12 4h is an EXACT
duplicate of this stream (702 trades, +0.0245%/trade, PF 1.0738 —
its judged module differs from winner 3 only in win_rate_prior
0.305 vs 0.334, which affects neither signals nor brackets). It
is NOT separately wired; this module is the single wire for the
stream (audit ~/workspace/str-nearmiss/REPORT.md §1.4).

BARE means the module's OWN signals with NO downstream filter: the
judged harness called the module's get_signal on sliding windows of
the module-featured frame (feature pipeline "module.add_features",
recorded in the row detail) and simulated the module's absolute
SL/TP. This wrapper reproduces that evaluation exactly
(``entries_for_frame``) and adds the daemon/OANDA contract
(``get_signal`` evaluating ONLY the last closed bar, returning
bracket distances from the signal bar's close; the engine
re-anchors them to the fill price, exactly as the judged simulator
anchors the absolute levels to the entry price).

Governance: registered FORWARD_TEST in config_strategy.py under the
key "factory_winner_3" — the key strategies/strategy_registry.py's
governance_key_for maps this module name to (it strips the
"strategy_" prefix; the registry's discovery loop special-cases
strategy_factory_winner* modules by skipping auto-discovery, so
this module is governed through config_strategy + the OANDA
forward-test runner, never through auto-discovery). Executable on
the OANDA practice venue only via oanda_demo/forward_test_runner.py,
phase-3 forward protocol protections, fills tagged FORWARD_TEST.
It is NOT a VALIDATED entrant.

Equivalence is pinned by tests/test_fwd019_forex_governed_lane.py,
which re-implements the gov2 evaluation loop inline (with an
independent transcription of the judged module) and requires
identical entries on the fwd002 FX fixture slices.
"""

from __future__ import annotations

import time
from collections import namedtuple
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from config_strategy import FACTORY_WINNER_3_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "4h"))
BAR_SECONDS = 4 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
WINDOW = int(_CFG.get("WINDOW", 500))
SL_ATR = float(_CFG.get("SL_ATR", 1.5))
TP_ATR = float(_CFG.get("TP_ATR", 4.5))
FACTORY_WIN_RATE_PRIOR = 0.334  # judged module's own prior (winner 3)
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.2863))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged module code, restored verbatim from the pre-cleanup blobs
# (strategy_factory_winners.py 76d2aeee..., winner-4 parameters).
# ---------------------------------------------------------------------------

class SignalResult(namedtuple("SignalResult", ["side", "sl", "tp", "strategy_type", "win_rate_prior", "rr_ratio"])):
    @property
    def confidence(self):
        return self.win_rate_prior


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR(period) with Wilder's EWM smoothing (judged module)."""
    tr = pd.concat([
        df['high'] - df['low'],
        abs(df['high'] - df['close'].shift(1)),
        abs(df['low'] - df['close'].shift(1))
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Computes MACD(12, 26, 9), Bollinger Bands(20, 2), and ATR(14)."""
    df = df.copy()
    macd_line, sig_line = compute_macd(df['close'], 12, 26, 9)
    df['macd'] = macd_line
    df['macd_signal'] = sig_line

    df['bb_mid'] = df['close'].rolling(window=20).mean()
    df['bb_std'] = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_mid'] + (2.0 * df['bb_std'])
    df['bb_lower'] = df['bb_mid'] - (2.0 * df['bb_std'])

    df['atr'] = compute_atr(df, 14)
    return df


def _evaluate_macd_bb_confluence(df: pd.DataFrame, sl_atr: float, tp_atr: float, rr_ratio: float, win_rate_prior: float) -> SignalResult:
    _NO_SIGNAL = SignalResult(None, None, None, _STRATEGY_TYPE, win_rate_prior, rr_ratio)

    if df is None or len(df) < 30:
        return _NO_SIGNAL

    if 'macd' not in df.columns or 'bb_mid' not in df.columns or 'atr' not in df.columns:
        df = add_features(df)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    if pd.isna(last['macd']) or pd.isna(last['macd_signal']) or pd.isna(last['bb_mid']) or pd.isna(last['atr']):
        return _NO_SIGNAL

    atr_val = last['atr']
    if atr_val <= 0:
        return _NO_SIGNAL

    close_p = last['close']

    # Long: MACD crosses above signal line AND price is below/at middle Bollinger Band (buying dip in trend)
    cross_above = (last['macd'] > last['macd_signal']) and (prev['macd'] <= prev['macd_signal'])
    long_confluence = cross_above and (close_p < last['bb_mid'])

    # Short: MACD crosses below signal line AND price is above/at middle Bollinger Band (selling rally in trend)
    cross_below = (last['macd'] < last['macd_signal']) and (prev['macd'] >= prev['macd_signal'])
    short_confluence = cross_below and (close_p > last['bb_mid'])

    if long_confluence:
        sl = close_p - (sl_atr * atr_val)
        tp = close_p + (tp_atr * atr_val)
        return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, win_rate_prior, rr_ratio)

    if short_confluence:
        sl = close_p + (sl_atr * atr_val)
        tp = close_p - (tp_atr * atr_val)
        return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, win_rate_prior, rr_ratio)

    return _NO_SIGNAL


def judged_get_signal(df: pd.DataFrame, **kwargs) -> SignalResult:
    """Winner #3: 5m MACD+BB Confluence (SL 1.5x ATR, TP 4.5x ATR, RR 3.0, Net PF 1.433) — the judged entry point."""
    return _evaluate_macd_bb_confluence(df, sl_atr=1.5, tp_atr=4.5, rr_ratio=3.0, win_rate_prior=0.334)


# ---------------------------------------------------------------------------
# Judged evaluation (rigorous_backtest/rd2/gov2.py, bare configuration)
# ---------------------------------------------------------------------------

def _extract(res) -> Optional[Tuple[str, float, float]]:
    """(side, sl, tp) from a judged SignalResult, or None."""
    if res is None:
        return None
    side = res.get("side") if isinstance(res, dict) else getattr(res, "side", None)
    if side not in ("BUY", "SELL"):
        return None
    sl = res.get("sl") if isinstance(res, dict) else getattr(res, "sl", None)
    tp = res.get("tp") if isinstance(res, dict) else getattr(res, "tp", None)
    if sl is None or tp is None:
        return None
    return side, float(sl), float(tp)


def entries_for_frame(
    df: pd.DataFrame, warmup: int = WARMUP_BARS
) -> List[Tuple[int, str, float, float]]:
    """(bar, side, sl_dist, tp_dist) identical to the gov2 bare
    evaluation: features computed once over the frame with the
    module's add_features, judged get_signal on trailing <=WINDOW-bar
    windows, bars [warmup, len-2], NO signal filter. Distances are
    measured from the signal bar's close (the judged simulator
    anchors the module's absolute levels to the entry price; the
    engine re-anchors these distances to the fill)."""
    featured = add_features(df)
    closes = df["close"].to_numpy(dtype=float)
    out: List[Tuple[int, str, float, float]] = []
    for i in range(warmup, len(df) - 1):
        window = featured.iloc[max(0, i - WINDOW + 1): i + 1].copy()
        ex = _extract(judged_get_signal(window))
        if ex is None:
            continue
        side, sl, tp = ex
        close_i = closes[i]
        if side == "BUY":
            out.append((i, "LONG", close_i - sl, tp - close_i))
        else:
            out.append((i, "SHORT", sl - close_i, close_i - tp))
    return out


# ---------------------------------------------------------------------------
# Daemon / OANDA-runner entry point
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
    """Evaluate the last closed 4h bar; return the daemon signal dict."""
    none_signal: Dict[str, Any] = {"side": None}
    try:
        if df is None or len(df) < WARMUP_BARS + 1:
            return none_signal
        frame = _closed_frame(df)
        if len(frame) < WARMUP_BARS + 1:
            return none_signal
        featured = add_features(frame)
        window = featured.iloc[-WINDOW:].copy()
        ex = _extract(judged_get_signal(window))
        if ex is None:
            return none_signal
        side, sl, tp = ex
        close_last = float(frame["close"].iloc[-1])
        if side == "BUY":
            sl_dist, tp_dist = close_last - sl, tp - close_last
        else:
            sl_dist, tp_dist = sl - close_last, close_last - tp
        if sl_dist <= 0 or tp_dist <= 0:
            return none_signal
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
