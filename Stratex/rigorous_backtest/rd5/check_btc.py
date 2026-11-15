#!/usr/bin/env python3
"""Independent cross-check for TASK-STR-RD-005 (not part of the runner).

Recomputes ONE config on ONE symbol with deliberately different mechanics
(pandas asof lookups over calendar days instead of the runner's
searchsorted event loop) and compares against the runner's saved
per-symbol expectancy for that config:
  crypto30_1h / SOI_TOKYO_MOM_L4h_H4h / BTCUSDT
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path("/home/hatch/workspace/str-rd2/cache2")
df = pd.read_csv(CACHE / "BTCUSDT_1h_2022-01_2026-10.csv",
                 parse_dates=["ts"], index_col="ts")
if df.index.tz is None:
    df.index = df.index.tz_localize("UTC")
df = df.sort_index()

RT = 16.0
r = (RT / 2) / 10000.0
trades = []
busy_until = pd.Timestamp.min.tz_localize("UTC")
days = pd.date_range(df.index[0].normalize(), df.index[-1].normalize(),
                     freq="D", tz="UTC")
for day in days:
    anchor = day  # TOKYO 09:00 JST == 00:00 UTC
    if anchor < busy_until:
        continue
    sub = df.loc[df.index >= anchor]
    if len(sub) == 0:
        break
    entry_time = sub.index[0]
    if entry_time - anchor >= pd.Timedelta(hours=1):
        continue
    ei = df.index.get_loc(entry_time)
    if ei < 5:
        continue
    # contiguity of the 4h lookback (runner rule for crypto)
    if df.index[ei - 1] - df.index[ei - 5] != pd.Timedelta(hours=4):
        continue
    prior = df["close"].iloc[ei - 1] / df["close"].iloc[ei - 5] - 1.0
    if prior == 0:
        continue
    side = 1 if prior > 0 else -1  # MOM
    entry = float(df["open"].iloc[ei])
    target = entry_time + pd.Timedelta(hours=4)
    xsub = df.loc[df.index >= target]
    if len(xsub) == 0 or xsub.index[0] - target > pd.Timedelta(hours=96):
        exit_price = float(df["close"].iloc[-1])
        exit_time = df.index[-1]
    else:
        exit_price = float(xsub["open"].iloc[0])
        exit_time = xsub.index[0]
    if side > 0:
        ea, xa = entry * (1 + r), exit_price * (1 - r)
        net = (xa - ea) / ea
    else:
        ea, xa = entry * (1 - r), exit_price * (1 + r)
        net = (ea - xa) / ea
    trades.append((entry_time, net))
    busy_until = exit_time

oos = [(t, n) for t, n in trades
       if pd.Timestamp("2024-07-01", tz="UTC") <= t < pd.Timestamp("2026-11-01", tz="UTC")]
exp = float(np.mean([n for _, n in oos]))
rows = json.load(open("/home/hatch/workspace/rd-005/results_rd5/rows_crypto30_1h.json"))
runner = [x for x in rows if x["config"] == "SOI_TOKYO_MOM_L4h_H4h"][0]
want = runner["breadth"]["per_symbol_expectancy"]["BTCUSDT"]
print(f"independent: n={len(oos)} expectancy={exp:.16f}")
print(f"runner     : expectancy={want:.16f}")
print("MATCH" if abs(exp - want) < 1e-12 else "MISMATCH")
