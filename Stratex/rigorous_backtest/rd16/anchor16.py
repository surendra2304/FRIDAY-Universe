"""Sanity anchor for TASK-STR-RD-016: reproduce RD-001's published
ts_momentum/roc42_4h pooled OOS row bit-identically through this
crew's harness copy before any RD-016 number is trusted.

Published row (results_rd/stage3_rows/ts_momentum__roc42_4h.json):
  trades 303, expectancy_net 0.0024275740638451445,
  profit_factor_net 1.0969220482985518.

Construction (RD-001's own): rd.common.load_timeframe('4h') over
BTCUSDT/ETHUSDT/SOLUSDT (1h 2023-10..2026-10 from RD-001's cache,
resampled to 4h), rd2.families2.sig_ts_momentum(roc 42, warmup 260),
rd.fastsim BR24 bracket (sl 2.0 / tp 4.0 ATR), rd.common COSTS
(16 bps RT), walkforward.oos_report pooled.

Fallback construction (only if RD-001's cache file is unusable):
RD-002's cache2 1h 2022-01..2026-10 files (hash-verified by
data_feed.load_dataset), sliced to bars >= 2023-10-01, then identical
downstream. Both constructions are reported; the anchor passes only
if one reproduces the published floats EXACTLY.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..data_feed import Dataset, load_dataset, resample_dataset
from ..rd.common import COSTS, atr, load_timeframe
from ..rd.fastsim import simulate_entries
from ..rd2.families2 import sig_ts_momentum, warmup_for
from ..walkforward import oos_report

EXPECTED = {"trades": 303,
            "expectancy_net": 0.0024275740638451445,
            "profit_factor_net": 1.0969220482985518}
SPEC = {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
RD1_CACHE = Path("/home/hatch/workspace/stratex-rd/cache")
RD2_CACHE = Path("/home/hatch/workspace/str-rd2/cache2")
OUT = Path("/home/hatch/workspace/rd-016/results_rd16/anchor.json")


def run(datasets: dict[str, Dataset]) -> dict:
    trades = []
    warmup = warmup_for("4h")
    for sym in SYMBOLS:
        ds = datasets[sym]
        entries = sig_ts_momentum(ds.df, 42, warmup)
        a = atr(ds.df, 14).to_numpy(dtype=float)
        trades.extend(simulate_entries(ds.df, entries, a, SPEC, sym, COSTS))
    return oos_report(trades)["pooled_oos"]


def matches(po: dict) -> bool:
    return (po["trades"] == EXPECTED["trades"]
            and po["expectancy_net"] == EXPECTED["expectancy_net"]
            and po["profit_factor_net"] == EXPECTED["profit_factor_net"])


def main() -> int:
    attempts = []
    ok = False
    try:
        po = run(load_timeframe("4h", RD1_CACHE))
        attempts.append({"construction": "rd.common.load_timeframe over "
                                         "RD-001 cache (stratex-rd/cache)",
                         "pooled_oos": po, "bit_identical": matches(po)})
        ok = ok or attempts[-1]["bit_identical"]
    except Exception as exc:  # noqa: BLE001
        attempts.append({"construction": "rd.common.load_timeframe over "
                                         "RD-001 cache",
                         "error": f"{type(exc).__name__}: {exc}",
                         "bit_identical": False})
    if not ok:
        try:
            datasets = {}
            for sym in SYMBOLS:
                base = load_dataset(sym, "1h", "2022-01", "2026-10",
                                    cache_dir=RD2_CACHE)
                df = base.df[base.df.index >= pd.Timestamp(
                    "2023-10-01", tz="UTC")]
                sliced = Dataset(sym, "1h", df, base.manifest)
                datasets[sym] = resample_dataset(sliced, "4h")
            po = run(datasets)
            attempts.append({"construction": "RD-002 cache2 1h sliced to "
                                             ">= 2023-10-01, resampled 4h",
                             "pooled_oos": po, "bit_identical": matches(po)})
            ok = ok or attempts[-1]["bit_identical"]
        except Exception as exc:  # noqa: BLE001
            attempts.append({"construction": "RD-002 cache2 sliced",
                             "error": f"{type(exc).__name__}: {exc}",
                             "bit_identical": False})
    result = {"anchor": "ts_momentum/roc42_4h (RD-001 published row)",
              "expected": EXPECTED, "attempts": attempts,
              "anchor_passed": ok}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps(result, indent=2, default=str))
    print("ANCHOR", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
