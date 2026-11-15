"""Volatility-targeted trend + drawdown brake engine (TASK-STR-RD-014).

Implements the frozen declaration (results_rd14/declaration.json,
SHA-256 posted on issue #35 before the first run):

- signals (close of bar t, held over bar t+1): tsmom42, tsmom126,
  ema10_50, ema20_100 — long/short symmetric;
- sizing: w_t = s_t * min(1, sigma_target / sigma_t), sigma_t = sample
  stdev (ddof=1) of the trailing 42 bar log returns, annualized;
- brake: multiplier m driven causally by the same configuration's
  UNBRAKED (shadow) per-symbol equity drawdown — none / flat_05 /
  flat_10 / half_10 with half-threshold hysteresis release;
- costs: c per unit of |delta position| turnover (0.0008 = the harness
  crypto standard 8 bps per side; 2x sensitivity at 0.0016);
- judgement unit: position episodes (maximal constant-sign non-zero
  runs) as simulator.Trade objects with turnover accounting split at
  sign flips, so total turnover cost = sum |delta pos| * c exactly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..simulator import Trade

SIGNALS = ["tsmom42", "tsmom126", "ema10_50", "ema20_100"]
VOL_TARGETS = [0.15, 0.30, 0.60]
BRAKES = ["none", "flat_05", "flat_10", "half_10"]
TIMEFRAMES = ["4h", "1d"]
VOL_WINDOW = 42
COST_PER_TURNOVER = 0.0008          # 8 bps per side (costs2.CRYPTO)
BARS_PER_YEAR = {"4h": 2190.0, "1d": 365.0}
_BRAKE_PARAMS = {                   # name -> (threshold, multiplier while braked)
    "flat_05": (0.05, 0.0),
    "flat_10": (0.10, 0.0),
    "half_10": (0.10, 0.5),
}


def build_configs() -> list[dict]:
    """The declared 96-cell grid: 4 signals x 3 vol targets x 4 brakes
    x 2 timeframes. One cell = one trial in the global counter."""
    out = []
    for tf in TIMEFRAMES:
        for sig in SIGNALS:
            for vt in VOL_TARGETS:
                for br in BRAKES:
                    out.append({"family": "vol_targeted_trend",
                                "variant": f"{sig}_vt{int(vt * 100):02d}_{br}",
                                "signal": sig, "vol_target": vt,
                                "brake": br, "panel": "crypto30", "tf": tf})
    return out


def _signal(close: pd.Series, name: str) -> np.ndarray:
    """Signal per bar close: -1 / 0 / +1 (warm-up -> 0)."""
    if name.startswith("tsmom"):
        look = int(name[5:])
        s = np.sign(np.log(close).diff(look))
    elif name.startswith("ema"):
        fast, slow = (int(x) for x in name[3:].split("_"))
        ef = close.ewm(span=fast, adjust=False).mean()
        es = close.ewm(span=slow, adjust=False).mean()
        s = np.sign(ef - es)
    else:
        raise ValueError(f"unknown signal {name}")
    return s.fillna(0.0).to_numpy(dtype=float)


def raw_weights(close: pd.Series, signal: str, vol_target: float,
                tf: str) -> np.ndarray:
    """w_t fixed at close of bar t: signal * min(1, target / sigma_t)."""
    logret = np.log(close).diff()
    sigma = (logret.rolling(VOL_WINDOW).std(ddof=1)
             * np.sqrt(BARS_PER_YEAR[tf]))
    s = _signal(close, signal)
    sig = sigma.to_numpy(dtype=float)
    ok = (sig > 0) & np.isfinite(sig)
    scale = np.where(ok, np.minimum(1.0, vol_target / np.where(ok, sig, 1.0)),
                     0.0)
    return s * scale


def shadow_equity(close: pd.Series, w: np.ndarray, cost: float):
    """Unbraked positions (pos[i] holds w[i-1]) and the shadow equity
    drawdown series dd[t] (known at the close of bar t)."""
    n = len(close)
    ret = close.pct_change().fillna(0.0).to_numpy(dtype=float)
    pos = np.zeros(n)
    pos[1:] = w[:-1]
    prev = np.concatenate([[0.0], pos[:-1]])
    r = pos * ret - np.abs(pos - prev) * cost
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(eq)
    return pos, eq / peak - 1.0


def brake_multiplier(dd: np.ndarray, brake: str) -> np.ndarray:
    """m[t] set at the close of bar t from dd[t]: engages at
    dd <= -threshold, releases at dd >= -threshold/2 (hysteresis)."""
    if brake == "none":
        return np.ones(len(dd))
    thr, mult = _BRAKE_PARAMS[brake]
    m = np.ones(len(dd))
    braked = False
    for t in range(len(dd)):
        d = dd[t]
        if np.isfinite(d):
            if not braked and d <= -thr:
                braked = True
            elif braked and d >= -thr / 2.0:
                braked = False
        m[t] = mult if braked else 1.0
    return m


def positions(w: np.ndarray, dd: np.ndarray, brake: str) -> np.ndarray:
    """Position held over bar i: m[i-1] * w[i-1] (both fixed at close
    of bar i-1). For brake == 'none' this is the shadow position."""
    n = len(w)
    if brake == "none":
        pos = np.zeros(n)
        pos[1:] = w[:-1]
        return pos
    m = brake_multiplier(dd, brake)
    pos = np.zeros(n)
    pos[1:] = (m * w)[:-1]
    return pos


def episodes_from_positions(df: pd.DataFrame, pos: np.ndarray, symbol: str,
                            cost: float) -> list[Trade]:
    """Episodes of a position series, with boundary turnover accounting
    (exits charged to the closing episode; flips split entry/exit)."""
    close = df["close"]
    ret = close.pct_change().fillna(0.0).to_numpy(dtype=float)
    n = len(close)
    prev = np.concatenate([[0.0], pos[:-1]])
    adj = pos * ret - np.abs(pos - prev) * cost
    for i in range(1, n):
        if pos[i - 1] != 0.0 and pos[i] == 0.0:
            adj[i - 1] -= abs(pos[i - 1]) * cost
        elif (pos[i - 1] != 0.0 and pos[i] != 0.0
              and np.sign(pos[i]) != np.sign(pos[i - 1])):
            adj[i] = pos[i] * ret[i] - abs(pos[i]) * cost
            adj[i - 1] -= abs(pos[i - 1]) * cost
    if n and pos[n - 1] != 0.0:      # end-of-data close-out
        adj[n - 1] -= abs(pos[n - 1]) * cost
    trades: list[Trade] = []
    index = df.index
    closes = close.to_numpy(dtype=float)
    i = 0
    while i < n:
        if pos[i] == 0.0:
            i += 1
            continue
        j = i
        sgn = np.sign(pos[i])
        while j + 1 < n and pos[j + 1] != 0.0 and np.sign(pos[j + 1]) == sgn:
            j += 1
        net = float(np.prod(1.0 + adj[i:j + 1]) - 1.0)
        reason = "SIGNAL_OFF"
        if j == n - 1:
            reason = "END_OF_DATA"
        elif pos[j + 1] != 0.0:
            reason = "FLIP"
        trades.append(Trade(symbol, index[i], index[j],
                            "LONG" if sgn > 0 else "SHORT",
                            float(closes[i - 1]) if i > 0 else float(closes[i]),
                            float(closes[j]), net, reason))
        i = j + 1
    return trades


def eval_config(cfg: dict, datasets: dict, cost: float = COST_PER_TURNOVER,
                cache: dict | None = None) -> list[Trade]:
    """All episodes of one grid cell, pooled over the panel. `cache`
    memoizes (raw weights, shadow drawdown) per (symbol, signal,
    vol_target, tf, cost) across the brake variants of a cell group."""
    trades: list[Trade] = []
    for sym in sorted(datasets.keys()):
        df = datasets[sym].df
        key = (sym, cfg["signal"], cfg["vol_target"], cfg["tf"], cost)
        if cache is not None and key in cache:
            w, dd = cache[key]
        else:
            w = raw_weights(df["close"], cfg["signal"], cfg["vol_target"],
                            cfg["tf"])
            _pos_sh, dd = shadow_equity(df["close"], w, cost)
            if cache is not None:
                cache[key] = (w, dd)
        pos = positions(w, dd, cfg["brake"])
        trades.extend(episodes_from_positions(df, pos, sym, cost))
    return trades
