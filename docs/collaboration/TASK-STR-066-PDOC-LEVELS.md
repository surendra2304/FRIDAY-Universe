# TASK-STR-066 — PDO/PDC + current-day 5-minute levels in S/R annotation records

— Muse 15, 2026-11-25

## Claim

- Board record verified first-hand on main `4bed6107` (re-checked on `80b75649`
  after main moved): `TASK-STR-066` AVAILABLE, owner null, P2, no hub
  claim, no branch, no open PR.
- Hub claim comment `7146070918` on issue #1483; branch
  `muse15/task-str-066-pdoc-levels` from main `4bed6107`, rebased onto
  `80b75649` (PR #1735, VYR-073, merged during the run).
- Board flip AVAILABLE → IN_REVIEW rides in this PR (one work PR, live
  evidence, per owner order 7143628341).

## Implementation

`Stratex/rigorous_backtest/ig/levels.py` — new `annotate_levels()` (TASK-STR-066),
`find_levels()` (TASK-IG-STR-03) untouched:

- Base S/R records from `find_levels()` on the base series, unchanged.
- `prev_day` (dict with `"open"` / `"close"`) adds one PDO record
  (`kind: "pdo"`, `origin: "prev_day"`) and one PDC record (`kind: "pdc"`),
  each a single-touch reference level (`first_index` / `last_index` null,
  `at_price` vs the last close). Missing keys raise `ValueError`.
- `today_5m` (the current day's 5-minute candles) adds S/R levels
  recomputed from that series; those records carry `"timeframe": "5m"` and
  indices relative to the 5-minute series.
- With neither extra input the output is identical to `find_levels()`.
  Strength is normalised across the combined set (most-tested level = 1.0);
  records are sorted by price; all records are JSON-serialisable plain data.
- Stdlib only, no new dependencies. Annotation aid only — no signals, no
  entries, no orders, and nothing in production consumes this module (same
  as IG-STR-03 by design).

## Tests

`Stratex/rigorous_backtest/ig/tests/test_levels.py` — 7 new tests, suite
**12/12 passed** locally (pytest, this VM):

- PDO/PDC carried alongside S/R, with correct prices, origin `prev_day`,
  touches 1, null indices; output sorted by price, JSON-shaped.
- `at_price` flag: prev-day close equal to the last close → True.
- 5-minute levels tagged `timeframe: "5m"`, indices relative to the 5m
  series; base records carry no timeframe tag.
- No extras → output identical to `find_levels()`.
- Strength normalised across the combined set (max 1.0; PDO = 1/top).
- `prev_day` missing keys → `ValueError`; empty series → `[]`.
- CI: `test_levels.py` added to the Stratex tier-1 pytest invocation in
  `.github/workflows/friday-universe-ci.yml` (after the `--deselect` line,
  so it cannot conflict with PR #1720's pending insertion above it).
  The file was collected by NO CI job on main before this change.

## Live evidence (real market data, 2026-11-25 ~03:57 IST)

`annotate_levels()` run on live Deribit public candles (BTC-PERPETUAL,
`get_tradingview_chart_data`, no auth — this VM is geo-blocked from
Binance; the module is stdlib-only and runs offline on any OHLC feed,
so no server leg is needed for this annotation):

- Base series: 101 x 1h bars, last close **59,934.5**.
- Previous day (2026-11-24) daily candle: open **61,386.0**, close **60,345.0**,
  high 64,524.5, low 59,368.0.
- Today (2026-11-25) 5-minute bars: **270**.
- Output: **22 records** — 13 base S/R + PDO (61,386.0) + PDC (60,345.0) +
  7 from today's 5m candles (support 59,513.1 / 60,065.7; resistance
  59,993.3 / 60,466.5 / 60,484.7 / 61,046.5 / 61,437.4). Kind counts:
  support 8, resistance 12, pdo 1, pdc 1. Strength max 1.0, sorted by
  price, JSON-serialisable. PDO/PDC `at_price` false (both above the last
  close 59,934.5) — correct.
- Full output saved in the run log (this VM, `/tmp/live_str066_out.txt`).

## Five states

- Implemented: YES (this PR) / Tested: YES (12/12 local; CI — see PR) /
  Merged: NO / Deployed: NO (no production consumer by design — annotation
  aid only) / Production-verified: YES for the acceptance as written
  (live-data run above proves the output carries PDO/PDC + 5m levels
  alongside S/R on real market candles).

— Muse 15
