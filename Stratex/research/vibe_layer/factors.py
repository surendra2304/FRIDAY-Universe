"""Alpha-factor zoo subset (TASK-IG2-STR-03).

Pattern adapted from HKUDS Vibe-Trading (MIT): a library of testable alpha
factors scored by information coefficient before any backtest is trusted.
The upstream stack needs Python 3.11+ and a FastAPI/React/agent runtime far
over the fleet's ~180MB service cap, so ONLY the research-layer pattern is
ported here — FRIDAY-native, NumPy-only, Python 3.10, research-only.
Upstream's headline backtest figures are screenshots, not forward records;
every factor here must earn its place on Stratex's own forward scorecard.
"""
from __future__ import annotations

import numpy as np


def _safe_div(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.divide(a, b, out=np.zeros_like(a, dtype=float), where=b != 0)


def momentum(close: np.ndarray, window: int = 20) -> np.ndarray:
    out = np.zeros_like(close, dtype=float)
    out[window:] = close[window:] / close[:-window] - 1.0
    return out


def reversal(close: np.ndarray, window: int = 5) -> np.ndarray:
    return -momentum(close, window)


def volatility(close: np.ndarray, window: int = 20) -> np.ndarray:
    """Negative realized vol (low-vol premium direction)."""
    ret = np.zeros_like(close, dtype=float)
    ret[1:] = close[1:] / close[:-1] - 1.0
    out = np.zeros_like(close, dtype=float)
    for i in range(window, len(close)):
        out[i] = -float(np.std(ret[i - window + 1:i + 1]))
    return out


def volume_surge(volume: np.ndarray, window: int = 20) -> np.ndarray:
    out = np.zeros_like(volume, dtype=float)
    for i in range(window, len(volume)):
        base = float(np.mean(volume[i - window:i]))
        out[i] = volume[i] / base - 1.0 if base > 0 else 0.0
    return out


def amihud_illiquidity(close: np.ndarray, volume: np.ndarray,
                       window: int = 20) -> np.ndarray:
    """|return| / dollar-volume, windowed mean — liquidity factor."""
    ret = np.zeros_like(close, dtype=float)
    ret[1:] = np.abs(close[1:] / close[:-1] - 1.0)
    dollar = close * np.maximum(volume, 0.0)
    daily = _safe_div(ret, dollar) * 1e6
    out = np.zeros_like(close, dtype=float)
    for i in range(window, len(close)):
        out[i] = float(np.mean(daily[i - window + 1:i + 1]))
    return out


def bollinger_z(close: np.ndarray, window: int = 20) -> np.ndarray:
    out = np.zeros_like(close, dtype=float)
    for i in range(window - 1, len(close)):
        seg = close[i - window + 1:i + 1]
        sd = float(np.std(seg))
        out[i] = (close[i] - float(np.mean(seg))) / sd if sd > 0 else 0.0
    return out


def rsi_factor(close: np.ndarray, window: int = 14) -> np.ndarray:
    """RSI mapped to [-1, 1] (oversold positive — mean-reversion direction)."""
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    out = np.zeros_like(close, dtype=float)
    for i in range(window, len(close)):
        ag = float(np.mean(gain[i - window + 1:i + 1]))
        al = float(np.mean(loss[i - window + 1:i + 1]))
        rsi = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
        out[i] = (50.0 - rsi) / 50.0
    return out


FACTOR_ZOO = {
    "momentum": momentum,
    "reversal": reversal,
    "volatility": volatility,
    "bollinger_z": bollinger_z,
    "rsi_factor": rsi_factor,
}


def compute_factor(name: str, close: np.ndarray,
                   volume: np.ndarray | None = None,
                   window: int = 20) -> np.ndarray:
    close = np.asarray(close, dtype=float)
    if name in ("volume_surge", "amihud_illiquidity"):
        if volume is None:
            raise ValueError(f"factor {name!r} needs a volume series")
        volume = np.asarray(volume, dtype=float)
        return (volume_surge(volume, window) if name == "volume_surge"
                else amihud_illiquidity(close, volume, window))
    if name not in FACTOR_ZOO:
        raise ValueError(f"unknown factor {name!r}; zoo: "
                         f"{sorted(FACTOR_ZOO) + ['volume_surge', 'amihud_illiquidity']}")
    return FACTOR_ZOO[name](close, window)


def information_coefficient(factor: np.ndarray, close: np.ndarray,
                            horizon: int = 5) -> float:
    """Spearman-style IC: rank correlation of factor vs forward returns.

    Computed as Pearson correlation on ranks (exact Spearman without scipy).
    Returns 0.0 when either side has no variance — never an invented score.
    """
    factor = np.asarray(factor, dtype=float)
    fwd = np.zeros_like(factor)
    if len(close) <= horizon:
        return 0.0
    fwd[:-horizon] = close[horizon:] / close[:-horizon] - 1.0
    mask = np.zeros_like(factor, dtype=bool)
    mask[horizon:-horizon if horizon else None] = True
    x, y = factor[mask], fwd[mask]
    if len(x) < 10 or np.std(x) == 0 or np.std(y) == 0:
        return 0.0
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    return float(np.corrcoef(rx, ry)[0, 1])


def zscore(values: np.ndarray) -> np.ndarray:
    sd = float(np.std(values))
    return (values - float(np.mean(values))) / sd if sd > 0 else np.zeros_like(values)
