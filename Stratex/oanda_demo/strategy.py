"""
oanda_demo/strategy.py — Stratex Momentum-Trend v2 (SMT-v2).

A risk-first trend-following strategy for the OANDA demo account.

Owner directive (2026-11-13): "make Stratex take profitable trades."

Design:
  1. Trade WITH the trend — EMA 20/50/200 stack, slope-confirmed.
  2. Momentum gate — RSI(14) must agree (>=52 long / <=48 short).
  3. Every signal ships with an ATR risk box:
       stop-loss  = 1.5 x ATR (adverse)
       take-profit = 2.25 x ATR (favourable, 1.5:1 reward:risk)
  4. Regime filters — skip dead markets (ATR% floor), news chaos
     (ATR% ceiling) and wide spreads (spread > 35% of ATR).
  5. Breakeven move at +1R turns winners into risk-free runners.

The same code path powers the backtest and the live trader, so what is
validated is what trades.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class StrategyConfig:
    ema_fast: int = 20
    ema_mid: int = 50
    ema_slow: int = 200
    rsi_period: int = 14
    rsi_long_min: float = 52.0
    rsi_short_max: float = 48.0
    atr_period: int = 14
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 2.25
    breakeven_r: float = 1.0
    min_atr_pct: float = 0.0003     # 0.03% of price — dead-market floor
    max_atr_pct: float = 0.0040     # 0.40% of price — chaos ceiling
    max_spread_frac_atr: float = 0.35
    slope_bars: int = 5
    min_bars: int = 260
    # --- v2.1 trade-quality filters (2026-11-13 backtest-driven) ------------
    max_extension_atr: float = 1.2   # entry within 1.2 ATR of EMA-fast (no chasing)
    min_trend_strength: float = 0.10  # |EMA fast - EMA mid| >= 0.10 ATR
    # --- v2.2 trailing exit (None = TP-cap mode) ----------------------------
    trailing_atr: Optional[float] = None  # chandelier multiple; disables TP cap


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


class StratexTrendStrategy:
    """SMT-v2 — deterministic signal engine (no network, no state)."""

    name = "SMT-v2"

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.cfg = config or StrategyConfig()

    # ------------------------------------------------------------------
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        c = self.cfg
        d = df.copy()
        d["ema_f"] = ema(d["close"], c.ema_fast)
        d["ema_m"] = ema(d["close"], c.ema_mid)
        d["ema_s"] = ema(d["close"], c.ema_slow)
        d["rsi"] = rsi(d["close"], c.rsi_period)
        d["atr"] = atr(d, c.atr_period)
        d["atr_pct"] = d["atr"] / d["close"]
        d["slope"] = d["ema_m"] - d["ema_m"].shift(c.slope_bars)
        return d

    # ------------------------------------------------------------------
    def signal_at(self, row) -> Tuple[Optional[str], Dict[str, bool]]:
        """Evaluate one indicator row. Returns ("LONG"|"SHORT"|None, checks)."""
        c = self.cfg
        checks = {
            "stack_up": bool(row.ema_f > row.ema_m > row.ema_s),
            "stack_dn": bool(row.ema_f < row.ema_m < row.ema_s),
            "above_fast": bool(row.close > row.ema_f),
            "below_fast": bool(row.close < row.ema_f),
            "slope_up": bool(row.slope > 0),
            "slope_dn": bool(row.slope < 0),
            "rsi_long": bool(row.rsi >= c.rsi_long_min),
            "rsi_short": bool(row.rsi <= c.rsi_short_max),
            "vol_ok": bool(c.min_atr_pct <= row.atr_pct <= c.max_atr_pct),
        }
        if row.atr > 0:
            checks["not_extended_long"] = bool(
                row.close - row.ema_f <= c.max_extension_atr * row.atr
            )
            checks["not_extended_short"] = bool(
                row.ema_f - row.close <= c.max_extension_atr * row.atr
            )
            checks["strength_long"] = bool(
                (row.ema_f - row.ema_m) / row.atr >= c.min_trend_strength
            )
            checks["strength_short"] = bool(
                (row.ema_m - row.ema_f) / row.atr >= c.min_trend_strength
            )
        else:
            checks["not_extended_long"] = False
            checks["not_extended_short"] = False
            checks["strength_long"] = False
            checks["strength_short"] = False
        long_ok = (
            checks["stack_up"] and checks["above_fast"] and checks["slope_up"]
            and checks["rsi_long"] and checks["vol_ok"]
            and checks["not_extended_long"] and checks["strength_long"]
        )
        short_ok = (
            checks["stack_dn"] and checks["below_fast"] and checks["slope_dn"]
            and checks["rsi_short"] and checks["vol_ok"]
            and checks["not_extended_short"] and checks["strength_short"]
        )
        if long_ok:
            return "LONG", checks
        if short_ok:
            return "SHORT", checks
        return None, checks

    # ------------------------------------------------------------------
    def evaluate(self, instrument: str, df: Optional[pd.DataFrame], spread: Optional[float] = None) -> Signal:
        """Full evaluation on the latest closed bar."""
        c = self.cfg
        if df is None or len(df) < c.min_bars:
            return Signal(instrument, None, reason="insufficient history")

        d = self.add_indicators(df)
        row = d.iloc[-1]
        side, checks = self.signal_at(row)

        if side and spread is not None and spread > c.max_spread_frac_atr * float(row.atr):
            return Signal(
                instrument, None,
                entry=float(row.close), atr=float(row.atr),
                reason=f"spread too wide ({spread:.5f} > {c.max_spread_frac_atr:.2f} x ATR)",
                checks=checks,
            )
        if not side:
            return Signal(
                instrument, None,
                entry=float(row.close), atr=float(row.atr),
                reason="no trend/momentum alignment",
                checks=checks,
            )

        entry = float(row.close)
        a = float(row.atr)
        if side == "LONG":
            sl = entry - c.sl_atr_mult * a
            tp = entry + c.tp_atr_mult * a if c.trailing_atr is None else 0.0
        else:
            sl = entry + c.sl_atr_mult * a
            tp = entry - c.tp_atr_mult * a if c.trailing_atr is None else 0.0
        return Signal(
            instrument, side,
            entry=entry, stop=sl, take=tp, atr=a,
            reason="trend + momentum aligned, risk box attached",
            checks=checks,
        )


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
    # compatibility with the SMT config surface used by backtest/trader
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
