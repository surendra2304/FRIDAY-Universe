"""Panel loading for TASK-STR-RD-016 (forex_cross41).

Mirrors rd2/panels.py's Yahoo loader, with three RD-016 specifics, all
pre-declared in results_rd16/declaration.json (frozen + hashed before
any cell ran):

- the cache is the crew's re-fetch of TASK-STR-DATA-001's expansion
  series (rd_data1/fetch_expansion.py, RD-002 Stage-A cache contract),
  verified per series against DATA-001's manifests.json BEFORE use —
  only series whose verification status is FULL_MATCH or
  TRUNCATED_MATCH are loadable; anything else is excluded and the
  runner reports the panel short-handed (never substituted);
- the final in-progress daily bar (dated 2026-11-15, a Sunday stub
  whose timestamp is fetch-time dependent) is dropped at load;
  verification happens on the fetched CSV before the drop;
- fold profiles: 1d STANDARD (W1..W5), 1h/4h LATE (W2..W5) — the 1h
  history starts 2024-11-18, after W1 opens (RD-002's LATE rule).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from ..data_feed import Dataset, resample_dataset

CACHE16 = Path(os.environ.get(
    "RD16_CACHE", "/home/hatch/workspace/rd-016/cache16"))
VERIFICATION = Path(os.environ.get(
    "RD16_VERIFICATION",
    "/home/hatch/workspace/rd-016/results_rd16/data_verification.json"))

CROSS41 = ["AUDCAD", "AUDCHF", "AUDHKD", "AUDSGD", "CADCHF", "CADHKD",
           "CADSGD", "CHFHKD", "CHFZAR", "EURCAD", "EURCZK", "EURDKK",
           "EURHKD", "EURHUF", "EURNOK", "EURSEK", "EURSGD", "EURTRY",
           "EURZAR", "GBPCAD", "GBPCHF", "GBPHKD", "GBPNZD", "GBPPLN",
           "GBPSGD", "GBPZAR", "HKDJPY", "NZDCAD", "NZDCHF", "NZDHKD",
           "NZDSGD", "SGDCHF", "SGDJPY", "TRYJPY", "USDCZK", "USDDKK",
           "USDHUF", "USDNOK", "USDPLN", "USDTHB", "ZARJPY"]

PANEL = "forex_cross41"
STANDARD = ["W1", "W2", "W3", "W4", "W5"]
LATE = ["W2", "W3", "W4", "W5"]
LOADABLE = {"FULL_MATCH", "TRUNCATED_MATCH"}
PARTIAL_BAR_CUT = pd.Timestamp("2026-11-15", tz="UTC")


def fold_profile16(tf: str) -> list[str]:
    return STANDARD if tf == "1d" else LATE


def _verified() -> dict[str, str]:
    data = json.loads(VERIFICATION.read_text())
    return {k: v["status"] for k, v in data["series"].items()}


def _dataset(symbol: str, tf: str, verified: dict[str, str]) -> Dataset:
    base_tf = "1d" if tf == "1d" else "1h"
    key = f"YH_{symbol}_{base_tf}"
    if verified.get(key) not in LOADABLE:
        raise FileNotFoundError(f"{key} not verified ({verified.get(key)})")
    f = CACHE16 / f"{key}.csv"
    meta = json.loads(f.with_suffix(".csv.json").read_text())
    df = pd.read_csv(f, index_col=0, parse_dates=True)
    if getattr(df.index, "tz", None) is None:
        df.index = df.index.tz_localize("UTC")
    meta = dict(meta)
    if base_tf == "1d":
        n0 = len(df)
        df = df[df.index < PARTIAL_BAR_CUT]
        meta["rd16_partial_bar_drop"] = {
            "rule": "daily bars dated >= 2026-11-15 dropped at load "
                    "(in-progress Sunday stub; verification was "
                    "performed on the fetched CSV before the drop)",
            "bars_dropped": int(n0 - len(df)),
        }
    ds = Dataset(symbol, base_tf, df, meta)
    if tf == base_tf:
        return ds
    if tf == "4h":
        return resample_dataset(ds, "4h")
    raise ValueError(f"cannot derive {tf} from {base_tf}")


def load_panel16(tf: str) -> dict[str, Dataset]:
    """Load every verified series of forex_cross41 at a timeframe.
    Unverified series are SKIPPED (the runner reports coverage from
    the returned dict's keys) — never substituted, never synthetic."""
    verified = _verified()
    out: dict[str, Dataset] = {}
    for sym in CROSS41:
        try:
            out[sym] = _dataset(sym, tf, verified)
        except FileNotFoundError:
            continue
    return out


def uncovered(tf: str) -> list[str]:
    verified = _verified()
    base_tf = "1d" if tf == "1d" else "1h"
    return [s for s in CROSS41
            if verified.get(f"YH_{s}_{base_tf}") not in LOADABLE]
