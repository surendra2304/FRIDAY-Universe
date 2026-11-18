"""strategy_bb_reversion — TASK-STR-FWD-019 FORWARD-TEST lane entrant.

Judged configuration (TASK-STR-RD-002, governed family, judged "as
coded" from the live module via rigorous_backtest/rd2/gov2.py
``eval_module_cell``, config "bare"): strategy_bb_reversion:bare
@ FOREX12 1d — 308 pooled OOS trades, +0.0730%/trade, PF 1.0911,
win rate 0.3571, 3/5 positive folds. It meets the owner's second
tier (expectancy > 0, PF >= 1.05, >= 200 OOS trades, pre-Bonferroni)
but did NOT pass the full frozen bar (Bonferroni at programme
N=3,899) — not a promotion, not VALIDATED. The owner directed
2026-11-18 (implement-all) that such near-miss candidates be decided
by real demo forward evidence in the FORWARD_TEST lane.

JUDGED-MODULE STATE (read before touching this file): the live
module gov2 judged (strategy_bb_reversion.py) was DELETED from main
by TASK-STR-CLEANUP-001 under the earlier BT-001 evidence rule (its
record there, PF 0.68, was a different, earlier measurement). The
judged signal code is restored VERBATIM in this wrapper from the
pre-cleanup blob (strategy_bb_reversion.py blob
6188e30d148f578ca136901d28502133ab58d7d1 — the deletion commit
020ea57b's parent), so the code path below is byte-equivalent in
logic to what gov2 evaluated: Bollinger(20, 2) pierce-and-reenter
mean reversion, with the module's coded bracket SL 1.5 x ATR(14),
TP 3.0 x ATR(14) (the deleted file's docstring said 0.5/1.5 — the
CODE constants _SL_ATR=1.5 / _TP_ATR=3.0 are what gov2 simulated,
and they are what is restored here).

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
key "bb_reversion" — the key strategies/strategy_registry.py's
governance_key_for maps this module name to (it strips the
"strategy_" prefix). Executable on the OANDA practice venue only
via oanda_demo/forward_test_runner.py, phase-3 forward protocol
protections, fills tagged FORWARD_TEST. It is NOT a VALIDATED
entrant.

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
    from config_strategy import BB_REVERSION_STRATEGY as _CFG
except Exception:  # pragma: no cover - standalone fallback
    _CFG = {}

TIMEFRAME = str(_CFG.get("TIMEFRAME", "1d"))
BAR_SECONDS = 24 * 3600
WARMUP_BARS = int(_CFG.get("WARMUP_BARS", 260))
WINDOW = int(_CFG.get("WINDOW", 500))
SL_ATR = float(_CFG.get("SL_ATR", 1.5))
TP_ATR = float(_CFG.get("TP_ATR", 3.0))
WIN_RATE_PRIOR = float(_CFG.get("OOS_WIN_RATE", 0.3571))
RR_RATIO = TP_ATR / SL_ATR

_STRATEGY_TYPE = "RULE_BASED"
_RR_RATIO = RR_RATIO
_OOS_WIN_RATE_PRIOR = WIN_RATE_PRIOR


# ---------------------------------------------------------------------------
# Judged module code, restored verbatim from the pre-cleanup blob
# (strategy_bb_reversion.py 6188e30d...).
# ---------------------------------------------------------------------------

class SignalResult(namedtuple("SignalResult", ["side", "sl", "tp", "strategy_type", "win_rate_prior", "rr_ratio"])):
    @property
    def confidence(self):
        return self.win_rate_prior


_JUDGED_OOS_WIN_RATE_PRIOR = 0.55
_JUDGED_RR_RATIO = 2.0
_SL_ATR = 1.5
_TP_ATR = 3.0


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR(period) using Wilder's EWM smoothing (judged module)."""
    tr = pd.concat([
        df['high'] - df['low'],
        abs(df['high'] - df['close'].shift(1)),
        abs(df['low'] - df['close'].shift(1))
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Computes Bollinger Bands (20, 2) and ATR(14) (judged module)."""
    df = df.copy()
    df['bb_mid'] = df['close'].rolling(window=20).mean()
    df['bb_std'] = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_mid'] + (2.0 * df['bb_std'])
    df['bb_lower'] = df['bb_mid'] - (2.0 * df['bb_std'])
    df['atr'] = compute_atr(df, 14)
    return df


def judged_get_signal(df: pd.DataFrame, **kwargs) -> SignalResult:
    """Bollinger Band Mean Reversion signal generator (judged module)."""
    _NO_SIGNAL = SignalResult(None, None, None, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)

    if df is None or len(df) < 25:
        return _NO_SIGNAL

    if 'bb_upper' not in df.columns or 'bb_lower' not in df.columns or 'atr' not in df.columns:
        df = add_features(df)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    if pd.isna(last['bb_upper']) or pd.isna(last['bb_lower']) or pd.isna(last['atr']):
        return _NO_SIGNAL

    atr_val = last['atr']
    if atr_val <= 0:
        return _NO_SIGNAL

    close_p = last['close']

    # Long: Pierced below lower band, now closes back above lower band
    pierce_lower = (prev['low'] < prev['bb_lower']) or (prev['close'] < prev['bb_lower'])
    reenter_long = (close_p > last['bb_lower']) and (close_p > prev['close'])

    # Short: Pierced above upper band, now closes back below upper band
    pierce_upper = (prev['high'] > prev['bb_upper']) or (prev['close'] > prev['bb_upper'])
    reenter_short = (close_p < last['bb_upper']) and (close_p < prev['close'])

    if pierce_lower and reenter_long:
        sl = close_p - (_SL_ATR * atr_val)
        tp = close_p + (_TP_ATR * atr_val)
        return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)

    if pierce_upper and reenter_short:
        sl = close_p + (_SL_ATR * atr_val)
        tp = close_p - (_TP_ATR * atr_val)
        return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, _JUDGED_OOS_WIN_RATE_PRIOR, _JUDGED_RR_RATIO)

    return _NO_SIGNAL


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
    """Drop still-forming trailing bars (bar open + duration > now)."""
    if df is None or len(df) == 0:
        return df
    now = time.time() if now_s is None else now_s
    idx = df.index
    try:
        opens = idx.asi8 / 1e9
    except Exception:
        return df
    keep = int(np.sum(opens + BAR_SECONDS <= now))
    if keep < len(df):
        return df.iloc[:keep]
    return df


def get_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Evaluate the last closed 1d bar; return the daemon signal dict."""
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
