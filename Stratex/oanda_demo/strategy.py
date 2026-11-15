"""
oanda_demo/strategy.py — signal engines for the OANDA demo account.

Two engines live here:
  - DonchianTrendStrategy (v3) — breakout + chandelier trailing exit.
  - MeanReversionStrategy (FX-MR-v4) — Connors RSI-2 reversion, the
    validated default the live trader runs (STRATEX_OANDA_STRATEGY=mr).

Shared building blocks: the Signal dataclass and the ema/rsi/atr
indicators. The same code path powers the backtest and the live trader,
so what is validated is what trades.

SMT-v2 (the original EMA-stack engine, StratexTrendStrategy) was
DELETED on 2026-11-15 by TASK-STR-CLEANUP-002 under the owner's strict
removal rule (verified OOS profit factor < 1.2 -> delete completely):
its TASK-STR-RD-002 mega-grid retest measured 627 OOS trades,
expectancy -0.081%/trade, PF 0.655 (RESULTS_RD2.md is the record).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class Signal:
    instrument: str
    side: Optional[str]            # "LONG" | "SHORT" | None
    entry: float = 0.0
    stop: float = 0.0
    take: float = 0.0
    atr: float = 0.0
    reason: str = ""
    checks: Dict[str, bool] = field(default_factory=dict)

    @property
    def rr(self) -> float:
        if not self.side or not self.stop:
            return 0.0
        risk = abs(self.entry - self.stop)
        if risk <= 0:
            return 0.0
        return abs(self.take - self.entry) / risk


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI. One-sided momentum (avg_loss == 0) correctly yields 100,
    a flat series yields 50, and leading NaN rows are filled to 50."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    out = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss.replace(0.0, np.nan))
    out = out.where(avg_loss > 0, 100.0)                     # pure uptrend
    out = out.where((avg_gain > 0) | (avg_loss > 0), 50.0)   # dead flat
    return out.fillna(50.0)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


# ---------------------------------------------------------------------------
# v3 — Donchian breakout + chandelier trailing (classic turtle structure)
# ---------------------------------------------------------------------------

@dataclass
class DonchianConfig:
    entry_bars: int = 55          # breakout channel length (turtle 55)
    atr_period: int = 20
    sl_atr_mult: float = 2.0      # initial stop
    trailing_atr: float = 3.0     # chandelier trail from extreme close
    regime_filter: bool = True    # only breakouts in the direction of EMA200
    min_bars: int = 260
    max_spread_frac_atr: float = 0.50
    # compatibility with the shared config surface used by backtest/trader
    tp_atr_mult: Optional[float] = None
    breakeven_r: float = 0.0


class DonchianTrendStrategy:
    """Donchian breakout with ATR chandelier trailing exit.

    Why: EMA-stack entries bled on 2024-2026 FX chop (-302R over 2.9y on H4)
    while capping winners with a fixed TP. The turtle structure (breakout
    entry, wide initial stop, trailing exit, no profit cap) is the classic
    robust trend-capture design: many small losses, few large wins.
    """

    name = "Donchian-Trend-v3"

    def __init__(self, config: Optional[DonchianConfig] = None):
        self.cfg = config or DonchianConfig()

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        c = self.cfg
        d = df.copy()
        d["ema_s"] = ema(d["close"], 200)
        d["atr"] = atr(d, c.atr_period)
        d["atr_pct"] = d["atr"] / d["close"]
        d["don_h"] = d["high"].rolling(c.entry_bars).max().shift(1)
        d["don_l"] = d["low"].rolling(c.entry_bars).min().shift(1)
        return d

    def signal_at(self, row) -> Tuple[Optional[str], Dict[str, bool]]:
        c = self.cfg
        checks = {
            "brk_up": bool(row.don_h and row.close > row.don_h),
            "brk_dn": bool(row.don_l and row.close < row.don_l),
            "regime_up": bool(row.close > row.ema_s),
            "regime_dn": bool(row.close < row.ema_s),
            "vol_ok": bool(row.atr > 0),
        }
        if checks["brk_up"] and checks["vol_ok"] and (not c.regime_filter or checks["regime_up"]):
            return "LONG", checks
        if checks["brk_dn"] and checks["vol_ok"] and (not c.regime_filter or checks["regime_dn"]):
            return "SHORT", checks
        return None, checks

    def evaluate(self, instrument: str, df: Optional[pd.DataFrame], spread: Optional[float] = None) -> Signal:
        c = self.cfg
        if df is None or len(df) < c.min_bars:
            return Signal(instrument, None, reason="insufficient history")
        d = self.add_indicators(df)
        row = d.iloc[-1]
        side, checks = self.signal_at(row)
        if side and spread is not None and spread > c.max_spread_frac_atr * float(row.atr):
            return Signal(instrument, None, entry=float(row.close), atr=float(row.atr),
                          reason=f"spread too wide ({spread:.5f})", checks=checks)
        if not side:
            return Signal(instrument, None, entry=float(row.close), atr=float(row.atr),
                          reason="no breakout", checks=checks)
        entry = float(row.close)
        a = float(row.atr)
        if side == "LONG":
            sl = entry - c.sl_atr_mult * a
        else:
            sl = entry + c.sl_atr_mult * a
        return Signal(
            instrument, side,
            entry=entry, stop=sl, take=0.0, atr=a,     # take=0: trailing exit
            reason=f"Donchian{c.entry_bars} breakout, {c.trailing_atr}xATR chandelier trail",
            checks=checks,
        )


# ---------------------------------------------------------------------------
# v4 — FX mean reversion (Connors RSI-2 with regime filter)
# ---------------------------------------------------------------------------
# Evidence (2026-11-13, real OANDA practice data): every trend variant
# (EMA-stack SMT-v2, Donchian v3) is net-negative on the 8-pair FX basket
# over 2.9y H4 (-206R) and 20y D1 (-97R) — except USDJPY (+9.5R, PF 1.18).
# The same data shows the majors are range-reverting: the strategy class
# that matches this behaviour is short-horizon mean reversion in the
# direction of the long-term trend.

@dataclass
class MeanReversionConfig:
    rsi_period: int = 2
    rsi_buy: float = 10.0          # long when RSI(2) < 10 (oversold dip)
    rsi_sell: float = 90.0         # short when RSI(2) > 90 (overbought pop)
    ema_regime: int = 200          # only revert WITH the long-term trend
    ema_exit: int = 5              # rule exit: close crosses back over EMA5
    atr_period: int = 14
    sl_atr_mult: float = 4.0       # disaster stop only (not the exit)
    max_hold_bars: int = 10        # time stop
    min_bars: int = 260
    max_spread_frac_atr: float = 0.15   # spread is the #1 MR cost
    exit_rule: str = "mr"          # consumed by backtest + live trader
    tp_atr_mult: Optional[float] = None
    trailing_atr: Optional[float] = None


class MeanReversionStrategy:
    """Connors-style RSI(2) reversion, trend-gated by EMA200.

    Long:  RSI(2) < 10  AND close > EMA200  -> exit when close > EMA5
    Short: RSI(2) > 90  AND close < EMA200  -> exit when close < EMA5
    Hard 4xATR disaster stop + 10-bar time stop. No profit cap.
    """

    name = "FX-MR-v4"

    def __init__(self, config: Optional[MeanReversionConfig] = None):
        self.cfg = config or MeanReversionConfig()

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        c = self.cfg
        d = df.copy()
        d["ema_regime"] = ema(d["close"], c.ema_regime)
        d["ema_exit"] = ema(d["close"], c.ema_exit)
        d["rsi_fast"] = rsi(d["close"], c.rsi_period)
        d["atr"] = atr(d, c.atr_period)
        d["atr_pct"] = d["atr"] / d["close"]
        return d

    def signal_at(self, row) -> Tuple[Optional[str], Dict[str, bool]]:
        c = self.cfg
        checks = {
            "oversold": bool(row.rsi_fast < c.rsi_buy),
            "overbought": bool(row.rsi_fast > c.rsi_sell),
            "regime_up": bool(row.close > row.ema_regime),
            "regime_dn": bool(row.close < row.ema_regime),
            "vol_ok": bool(row.atr > 0),
        }
        if checks["oversold"] and checks["regime_up"] and checks["vol_ok"]:
            return "LONG", checks
        if checks["overbought"] and checks["regime_dn"] and checks["vol_ok"]:
            return "SHORT", checks
        return None, checks

    def evaluate(self, instrument: str, df: Optional[pd.DataFrame], spread: Optional[float] = None) -> Signal:
        c = self.cfg
        if df is None or len(df) < c.min_bars:
            return Signal(instrument, None, reason="insufficient history")
        d = self.add_indicators(df)
        row = d.iloc[-1]
        side, checks = self.signal_at(row)
        if side and spread is not None and spread > c.max_spread_frac_atr * float(row.atr):
            return Signal(instrument, None, entry=float(row.close), atr=float(row.atr),
                          reason=f"spread too wide ({spread:.5f})", checks=checks)
        if not side:
            return Signal(instrument, None, entry=float(row.close), atr=float(row.atr),
                          reason="no reversion setup", checks=checks)
        entry = float(row.close)
        a = float(row.atr)
        if side == "LONG":
            sl = entry - c.sl_atr_mult * a
        else:
            sl = entry + c.sl_atr_mult * a
        return Signal(
            instrument, side,
            entry=entry, stop=sl, take=0.0, atr=a,   # rule exit, no TP
            reason=f"RSI({c.rsi_period}) reversion, EMA{c.ema_regime} regime gate",
            checks=checks,
        )
