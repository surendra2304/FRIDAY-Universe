# TASK-STR-EXP-005 — #986 provenance follow-up: the 34 refused tier streams

Status: report written, reproduction run. Claim PR #1206 merged 2026-11-21 18:41 IST (merge 11bc584d, board claim only); this report filed in the follow-up PR (number in the board record).
Base: main 70ef99f3. Claim: issue #35 comment 7062957037.

## Verdict up front

1. **Mechanism PROVEN, not hypothesized.** The exporter's t/p check recomputes
   significance over the OOS-window trades only; every RD-002 producer computes
   the row's recorded `trade_stats` over a SUPERSET of that set. On all 5
   refused rows available in this snapshot the recorded t equals the t computed
   over the producer's set to full double precision (see §1).
2. **No legitimate exporter-side fix.** Recomputing the check over the producer's
   (larger, in-sample-contaminated) set would certify a significance number that
   does not describe the stored stream. That loosens the provenance check — the
   frozen gate. Rejected (§4).
3. **Legitimate fix exists, producer-side.** Align each producer's `trade_stats`
   input to the OOS-window union (the exact set the exporter and the judge use)
   and regenerate the affected rows. No bar, gate, or tolerance changes (§4).
4. **Gap, stated plainly.** The 99-stream inventory and the full RD-002 backup
   (`~/workspace/str-rd2/results_full_backup` + the 99-entry streams spec) are
   not on this VM, so the full 34 cannot be named here. What is named here is
   the complete refusal set of the available snapshot (§2), the rule that
   predicts the other 29 (§3), and the exact command to enumerate all 34 once
   the backup is available (§5).

## 1. The refusal mechanism

The exporter (`Stratex/self_experiments/export_stream_store.py`,
`derive_stream`) derives a stream's stored form from the row file's own
per-trade list, selecting trades with `oos_start <= entry_time < oos_end`
per fold (the harness's convention), then asserts the derivation against the
recorded figures. The significance check recomputes, over those OOS-window
returns only:

- `t = mean / (sample_sd / sqrt(n))`, `p = 0.5 * erfc(t / sqrt(2))`
  (one-sided, normal approximation), tolerance `|t| <= 1e-3`, `|p| <= 1e-5`.

The formula is identical in the harness (`Stratex/rigorous_backtest/rd2/
stats2.py:118-133`, `trade_stats`: sample sd `ddof=1`, `t = sr * sqrt(n)`,
`p = 1 - norm.cdf(t)`) and in the judge (`Stratex/self_experiments/
runner.py:102-106`, `_metrics_for_returns`: same construction over the
stored stream's returns). **Only the input set differs, by producer:**

| Producer | File:line | `trade_stats` input set |
|---|---|---|
| grid rows | `rd2/grid.py:179-182` | trades with `entry_time >=` first fold's `oos_start` (includes post-last-window and in-gap trades) |
| gov rows | `rd2/gov2.py:147-148` | same `>= first oos_start` set (`oos_trades`) |
| combo rows | `rd2/combo.py:211` | `trade_stats(all_trades)` — ALL trades, including in-sample |
| smt rows | producer script not in repo | row proves an all-trades construction (recorded t == t(all trades) exactly); see §2 |

The check therefore passes exactly when the producer's set coincides with
the OOS-window set: for grid/gov rows, when there are **zero trades after the
last fold's `oos_end` and zero trades in inter-fold gaps** (trades before the
first `oos_start` are excluded by both sets, so they do not matter); for
combo rows, additionally **zero trades before the first `oos_start`**.
Fold windows tile contiguously in this data (`gap = 0` on every row scanned),
so in practice the rule is: **a row exports iff it has no trades outside the
OOS windows** (post-last for grid/gov/smt; pre-first or post-last for combo).

Exact-match proof on the 5 refused rows (recorded t == t over the producer's
set, to full precision; OOS t differs beyond the 1e-3 tolerance):

| Stream | Producer | n_all / n_oos | Recorded t | t (OOS) | t (producer set) |
|---|---|---|---|---|---|
| `ensemble/vote2_of3@crypto30/4h` | combo | 3274 / 1770 | 0.321127 | 0.174629 | 0.321127 (all trades; 1504 pre-first) |
| `ensemble/vote2_of3@forex12/4h` | combo | 438 / 429 | -0.986039 | -1.255647 | -0.986039 (all trades; 9 post-last) |
| `smt_v2/default_deployed_panel12@forex12/4h` | smt | 1045 / 1026 | -6.310431 | -6.271059 | -6.310431 (all trades; 19 post-last) |
| `smt_v2/default_deployed_watchlist8@forex12/4h` | smt | 635 / 627 | -4.825587 | -4.839135 | -4.825587 (all trades; 8 post-last) |
| `tsmom2_dual/roc30_ema200@comm7/4h` | grid | 211 / 205 | 1.163411 | 1.103700 | 1.163411 (>= first start; 6 post-last) |

Recorded p matches recorded t under the normal one-sided formula exactly on
all 5, so the p formula is not in dispute — only the return set is.

Note on the board's parenthetical ("non-crypto30 panels"): the pattern is
really **trade history extending outside the OOS windows**, which correlates
with 4h rows and non-crypto30 panels but is not a panel property — e.g.
`ensemble/vote2_of3@crypto30/4h` fails while `strategy_adx_ema:bare@crypto30/
4h` and `ichimoku_trend/tk_cloud@crypto30/4h` pass, and 1d rows fail too
(`keltner_breakout/ema20_m2.0@idx7/1d`, `tsmom2_dual/roc90_ema200@forex28/1d`
in the wider scan).

## 2. Per-stream table — available snapshot (`results_rd2`, 9 full-schema rows)

The snapshot is `Stratex/rigorous_backtest/results_rd2/` (68 row files; only
9 carry the full exporter schema — per-trade list + `report.per_fold` +
`trade_stats.t_stat`). The other 59 are gov/summary rows with no `trades`
key; the exporter raises `KeyError: 'trades'` on them, which is a different
failure class (no per-trade list at all — they were never exportable streams,
not t/p refusals) and is not part of the 34.

REFUSED (t/p construction check) — corrected OOS values are what the row's
`trade_stats` should carry for the stored stream:

| Stream | Producer | n_all / n_oos | Recorded t / p | Corrected OOS t / p | Extra trades |
|---|---|---|---|---|---|
| `ensemble/vote2_of3@crypto30/4h` | combo | 3274 / 1770 | 0.321127 / 0.374057 | 0.174629 / 0.430686 | 1504 pre-first |
| `ensemble/vote2_of3@forex12/4h` | combo | 438 / 429 | -0.986039 / 0.837943 | -1.255647 / 0.895378 | 9 post-last |
| `smt_v2/default_deployed_panel12@forex12/4h` | smt | 1045 / 1026 | -6.310431 / 1.0 | -6.271059 / 1.0 | 19 post-last |
| `smt_v2/default_deployed_watchlist8@forex12/4h` | smt | 635 / 627 | -4.825587 / 0.999999 | -4.839135 / 0.999999 | 8 post-last |
| `tsmom2_dual/roc30_ema200@comm7/4h` | grid | 211 / 205 | 1.163411 / 0.122331 | 1.103700 / 0.134862 | 6 post-last |

All 5 fail at the t/p check only — their per-fold trades/wins/expectancy/PF
and holdout figures reconcile exactly (the exporter checks those first).

EXPORTED (pass) — same snapshot, for contrast:

| Stream | n_all / n_oos | Note |
|---|---|---|
| `bollinger_trend/p50_sd2.0@crypto30/1d` | 828 / 420 | 408 pre-first trades; both sets exclude them |
| `shock_breakout/k1.0@crypto30/1d` | 1381 / 732 | 649 pre-first; both sets exclude them |
| `strategy_adx_ema:bare@crypto30/4h` (gov) | 1604 / 837 | 767 pre-first; both sets exclude them |
| `ichimoku_trend/tk_cloud@crypto30/4h` | 4378 / 2302 | 2076 pre-first; both sets exclude them |

The 6 shipped fixture streams (`Stratex/tests/fixtures/selfexp_stream_store/`)
pass for the same reason: their trades lists are exactly the OOS set.

## 3. Generalisation — 78 full-schema rows repo-wide

`derive_stream` was run over every row file in the repo carrying the full
exporter schema (`Stratex/rigorous_backtest/results_*/**/*.json`, 78 rows;
full table in the run log `~/workspace/muse4/task-str-exp-005/scan78.json`):
12 PASS / 63 FAIL / 3 ERROR. Every PASS row has zero post-last and zero
in-gap trades; every t-check failure has post-last trades (grid/gov/smt) or
pre-first trades (combo). The rule of §1 holds repo-wide.

Two other failure classes appear in that scan and are **out of scope for the
RD-002 99** (they are other rounds' rows, not RD-002 tier streams):

- **RD-008 idx2 rows (15m): fold-convention mismatch.** Per-fold
  trades/wins do not reproduce under the exporter's `[oos_start, oos_end)`
  derivation (folds named `S1`/`S2`, a session-based convention). 13 rows.
  The exporter is written for the RD-002 date-window convention; RD-008 rows
  would need their own fold derivation, not a tolerance change.
- **3 rows ERROR with `TypeError`** (`float(None)`): a fold's recorded
  expectancy is `null`, so the exporter crashes instead of refusing cleanly
  (`ema_cross/ema20_100@idx2/1d`, `tsmom/roc126@idx2/1d`,
  `tsmom/roc63@idx2/1d`). Incidental robustness gap — see §4.

## 4. Fix verdicts

### (a) Exporter-side acceptance change — REJECTED (loosens the gate)

Changing the exporter to recompute t/p over the producer's set (all trades,
or `>= first oos_start`) would make the check pass, but it would certify a
significance number that belongs to a different sample than the stored
stream. The stored stream is the OOS-window returns; the judge
(`runner.py`) judges exactly that set. A record whose t/p comes from
in-sample trades would then enter the store with OOS provenance it does not
have — e.g. `ensemble/vote2_of3@crypto30/4h` would carry t 0.32 (p 0.374)
for a stream whose own OOS t is 0.17 (p 0.431). That is in-sample performance
laundered into OOS provenance. The task forbids loosening the frozen gate;
this change is a loosening. Do not do it.

### (b) Producer-side alignment — LEGITIMATE FIX (recommended)

Change each producer's `trade_stats` input to the OOS-window union — the
exact set the exporter and the judge use — and regenerate the affected rows:

- `rd2/grid.py:179-182`: replace the `entry_time >= first oos_start`
  filter with a fold-window filter (share one helper with the exporter).
- `rd2/gov2.py:147-148`: same for `oos_trades`.
- `rd2/combo.py:211`: `trade_stats(all_trades)` → OOS-window trades.
- smt producer: **not in the repo** (no script under `Stratex/` or `docs/`
  writes `smt_rows/`; the row's `detail` cites the OANDA-demo
  `StrategyConfig()` defaults). The producer must be located before its rows
  can be regenerated; the fix itself is the same one-line alignment.

Regeneration over the same data should change ONLY `trade_stats` (t, p, and
the skew/kurtosis computed over the same set); per-fold and holdout figures
already reconcile, so they are unaffected. No bar, gate, or tolerance changes
anywhere. This is a follow-up task for the owning lane (producer change +
row regeneration), not this PR — changing judged-record production needs its
own review.

### (c) Per-row re-derivation (fallback) — NEEDS COORDINATOR APPROVAL

For a row whose producer cannot be re-run, the corrected t/p is computable
from the row file itself (the exporter already computes it; values in §2).
Amending a judged row's `trade_stats` in place breaks the
judged-record-is-immutable provenance principle — the manifest records the
source sha256, so an amended row is a new source. Do this only with explicit
coordinator approval, preserving the old values in the record. Prefer (b).

### (d) Exporter robustness — recommended hardening, no gate change

Raise a clean fail-closed `AssertionError` (refusal) instead of crashing
with `TypeError` when a recorded figure is `null`. Changes reporting only;
nothing that currently passes would fail and nothing refused would pass.

## 5. The 99-stream inventory gap and how to close it

The 34/99 figure is the coordinator's follow-up-watch result. The full
RD-002 backup (`~/workspace/str-rd2/results_full_backup`) and the 99-entry
streams spec are not present on this VM, and no 99-entry inventory exists in
the repo (the RD-002 grid itself is 978 cells; `synthesis.json` records
`rd002_rows = 1077`; `stageC_combinations.json` records `streams_available =
851`). The 5 refusals in §2 are therefore the complete confirmed set from
available data; the remaining 29 cannot be named without the backup, and
this report does not invent them.

Prediction from the proven rule: of the 99, the refused ones are exactly the
spec entries whose rows carry trades outside the OOS windows (post-last
trades at 4h / late-fold panels, or pre-first trades for combo-produced
rows). To enumerate all 34, run on a machine with the backup:

```sh
cd Stratex
python3 -m self_experiments.export_stream_store \
  --rows-dir ~/workspace/str-rd2/results_full_backup \
  --streams <99-entry spec>.json --out /tmp/exp005-store
# every stream that raises is a refusal; the AssertionError names the
# stream and the exact check (t, p, fold, or holdout) that failed.
```

A per-stream refusal wrapper (catch `AssertionError` per spec entry and
tabulate) is the one-line follow-up needed to produce the full 34-row table
in the coordinator's workspace.

## 6. Status

- Implemented: this report; reproduction probe + 78-row scan
  (`~/workspace/muse4/task-str-exp-005/scan78.json`); claim PR #1206.
- Tested: exporter run over the available snapshot (9 rows: 4 pass / 5
  t-fail) and repo-wide (78 rows: 12 pass / 63 fail / 3 error); exact-match
  proof that recorded t == t(producer set) on all 5 refused rows; A/B
  against the 6 fixture streams (all pass, unchanged).
- Merged: claim PR #1206 merged 18:41 IST (merge 11bc584d); this report in
  the follow-up PR (number in the board record). No code change in this
  PR (docs + board only); the producer fixes of §4(b) are follow-up work.
- Deployed / production-verified: n/a (documentation task; nothing runs
  live and the frozen gate is untouched).
