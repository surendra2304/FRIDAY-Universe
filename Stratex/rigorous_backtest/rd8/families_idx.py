"""Index-strategy families for TASK-STR-RD-008 (pre-declared).

Panel: idx2 = {NDX (OANDA NAS100), SPX (OANDA US500)} on provenanced
Yahoo cash-index series. All specs are frozen in
results_rd8/declaration.json; this module implements exactly that
declaration and nothing else.

Conventions (programme-standard unless the declaration says otherwise):
- entries are (signal_bar, side); the harness fastsim fills at the open
  of signal_bar + 1 with ATR(14) brackets anchored to the entry price;
- GAP families use the declared open-auction deviation (RD-003 Stage-2B
  precedent): the gap is computed from the fill bar's own open vs the
  previous session's close — both known at that open — and the entry is
  emitted on the last bar before the fill so the fill lands on the open;
- sessions are America/New_York calendar dates (Yahoo cash-index bars
  cover the US regular session only);
- ts_momentum and donchian signals are the harness's own functions,
  imported verbatim (families2.sig_ts_momentum / sig_donchian).
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from ..rd.common import ema, rsi
from ..rd2.families2 import _entries, sig_donchian, sig_ts_momentum

ET = ZoneInfo("America/New_York")

BR24 = {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}


# ---------------------------------------------------------------- sessions

def session_keys(df: pd.DataFrame) -> np.ndarray:
    """America/New_York calendar date per bar (session identifier)."""
    return df.index.tz_convert(ET).date


def session_first_mask(df: pd.DataFrame) -> np.ndarray:
    keys = session_keys(df)
    mask = np.ones(len(df), dtype=bool)
    mask[1:] = keys[1:] != keys[:-1]
    return mask


# ---------------------------------------------------------------- gap

def _gap_entries(df: pd.DataFrame, theta: float, mode: str, warmup: int,
                 session_first_only: bool):
    opens = df["open"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    firsts = session_first_mask(df) if session_first_only else None
    out = []
    for t in range(1, len(df)):
        if firsts is not None and not firsts[t]:
            continue
        gap = opens[t] / closes[t - 1] - 1.0
        if gap >= theta:
            side = "LONG" if mode == "follow" else "SHORT"
        elif gap <= -theta:
            side = "SHORT" if mode == "follow" else "LONG"
        else:
            continue
        if t - 1 >= warmup:
            out.append((t - 1, side))
    return out


def sig_gap_daily(df, theta, mode, warmup):
    """Overnight gap on daily bars; signal bar = previous session."""
    return _gap_entries(df, theta, mode, warmup, session_first_only=False)


def sig_gap_intra(df, theta, mode, warmup):
    """Overnight gap traded in the following session; signal bar = the
    previous session's last bar, fill = the session's first bar open."""
    return _gap_entries(df, theta, mode, warmup, session_first_only=True)


# ---------------------------------------------------------------- mean reversion

def sig_zrev(df, window, k, warmup):
    """Z-score cross-in reversion (crossing convention identical to the
    harness sig_zscore, without its optional ADX filter)."""
    mid = df["close"].rolling(window).mean()
    sd = df["close"].rolling(window).std()
    z = (df["close"] - mid) / sd
    prev = z.shift(1)
    long_sig = (prev >= -k) & (z < -k)
    short_sig = (prev <= k) & (z > k)
    return _entries(long_sig, short_sig, warmup)


def sig_rsi_rev(df, period, lo, hi, warmup):
    r = rsi(df["close"], period)
    prev = r.shift(1)
    long_sig = (prev >= lo) & (r < lo)
    short_sig = (prev <= hi) & (r > hi)
    return _entries(long_sig, short_sig, warmup)


# ---------------------------------------------------------------- momentum

def sig_ema_cross(df, fast, slow, warmup):
    d = ema(df["close"], fast) - ema(df["close"], slow)
    prev = d.shift(1)
    long_sig = (prev <= 0) & (d > 0)
    short_sig = (prev >= 0) & (d < 0)
    return _entries(long_sig, short_sig, warmup)


# ---------------------------------------------------------------- registry

def _gap_spec(tf):
    if tf == "1d":
        return {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 3.0,
                "max_bars": 1}
    return {"type": "bracket_time", "sl_atr": 1.5, "tp_atr": 2.5,
            "max_bars": 7 if tf == "1h" else 26}


def _mr_spec(tf):
    return {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 2.0,
            "max_bars": 7 if tf == "1h" else 26}


def build_configs_rd8() -> list[dict]:
    """The 43 declared cells. One config here = one (family, variant,
    panel, timeframe) cell = one trial."""
    C: list[dict] = []

    def add(family, variant, kind, fn, spec_by_tf, session_flat=False):
        for tf, spec in spec_by_tf.items():
            C.append({"family": family, "variant": variant, "kind": kind,
                      "fn": fn, "spec": spec, "tf": tf,
                      "session_flat": session_flat})

    for mode in ("follow", "fade"):
        for th, tname in ((0.003, "03"), (0.006, "06")):
            add("gap_daily", f"{mode}_{tname}", "gap_daily",
                (lambda m, t: lambda df, w: sig_gap_daily(df, t, m, w))(mode, th),
                {"1d": _gap_spec("1d")})
            add("gap_intra", f"{mode}_{tname}", "gap_intra",
                (lambda m, t: lambda df, w: sig_gap_intra(df, t, m, w))(mode, th),
                {"1h": _gap_spec("1h"), "15m": _gap_spec("15m")},
                session_flat=True)
    for w_ in (20, 50):
        for k in (2.0, 2.5):
            add("zrev", f"w{w_}_t{k}", "zrev",
                (lambda ww, kk: lambda df, w: sig_zrev(df, ww, kk, w))(w_, k),
                {"1h": _mr_spec("1h"), "15m": _mr_spec("15m")},
                session_flat=True)
    for pname, period, lo, hi in (("rsi2", 2, 10.0, 90.0),
                                  ("rsi7", 7, 25.0, 75.0)):
        add("rsi_rev", pname, "rsi_rev",
            (lambda p, l, h: lambda df, w: sig_rsi_rev(df, p, l, h, w))(period, lo, hi),
            {"1h": _mr_spec("1h"), "15m": _mr_spec("15m")},
            session_flat=True)
    for lb, tfs in ((21, ("1d",)), (63, ("1d",)), (126, ("1d",)),
                    (12, ("1h",)), (48, ("1h",)),
                    (16, ("15m",)), (64, ("15m",))):
        add("tsmom", f"roc{lb}", "tsmom",
            (lambda ll: lambda df, w: sig_ts_momentum(df, ll, w))(lb),
            {tf: dict(BR24) for tf in tfs})
    for n in (20, 55):
        add("donchian", f"n{n}", "donchian",
            (lambda nn: lambda df, w: sig_donchian(df, nn, w))(n),
            {"1d": dict(BR24), "1h": dict(BR24), "15m": dict(BR24)})
    for fast, slow, tfs in ((10, 50, ("1d",)), (20, 100, ("1d",)),
                            (12, 48, ("1h",)), (24, 96, ("1h",)),
                            (16, 64, ("15m",)), (32, 128, ("15m",))):
        add("ema_cross", f"ema{fast}_{slow}", "ema",
            (lambda f, s: lambda df, w: sig_ema_cross(df, f, s, w))(fast, slow),
            {tf: dict(BR24) for tf in tfs})
    return C
