# TASK-STR-086 — Checkpoint 2: build + test done, chart run blocked on demo-fapi 451 (Muse TP6, 2026-11-25 ~16:20 IST)

## Task

Stratex staged chart-analysis checklist (7-stage screenshot pipeline),
research desk. Claim hub 7157064327, checkpoint 1 hub 7157143111.
Coordinator ruling WATCH092 (hub 7159034308) authorised local build/test
of the new stdlib+pandas-only pipeline code on this VM plus a read-only
one-real-chart run. This checkpoint files the build, the test results,
and the chart-run outcome.

## What ran, where it ran

- Where: this VM, local clone `~/workspace/str086`, branch
  `musetp6/task-str-086-staged-chart-checklist` @ 5ccdf991 (checkpoint 1).
- What: new module `Stratex/research/staged_chart_checklist.py`
  (stdlib + pandas only), tests
  `Stratex/research/test_staged_chart_checklist.py` (stdlib unittest),
  one-real-chart run of `BTCUSDT` (1d + 4h + 1h, trading timeframe 1h)
  via the module CLI, read-only, public demo-fapi endpoint, no key.
- No fleet writes, no deployment, no orders, no board edits, no secrets
  read or pasted anywhere. No execution-risk flag was raised this run.

## Build — done

The 7-stage pipeline is implemented per the checkpoint-1 design:
1. market structure (RegimeClassifier + EMA50/200 + swings),
2. data quality (completeness/gaps/stale, fail-closed),
3. timeframe context (1d/4h/1h agreement, HTF conflict flagged),
4. fundamentals (venue facts recorded; on-chain/fundamental inputs
   marked NOT AVAILABLE, gap named, nothing synthesised),
5. news sentiment (economic-calendar items in window; none recorded
   as none, never neutral),
6. risk levels (ATR(14) stop, R:R, 0.5% risk/trade sizing, min-R:R
   1.2 gate),
7. final report (entry/stop/target/R:R + per-stage sections).
Each stage writes its section before the next runs; the report (JSON +
Markdown) is re-persisted after every stage, so a mid-pipeline failure
leaves a partial, attributable report — never a silent skip. Stages 4-5
record that PASS means "no contradicting evidence found in the
available feed", never "fundamentals confirm".

## Tests — 28/28 pass

`python3 -m unittest test_staged_chart_checklist -v` in
`Stratex/research/`: 28 tests, 0 failures (0.25s). Coverage: indicator
math and regime classification (up/down/flat/thin-data), data-quality
fail-closed paths (missing bars, gaps, stale, empty), HTF conflict
flagging, fundamentals gap naming, news none-vs-neutral and
high-impact flagging, risk-level math and R:R gate, direction mapping,
full synthetic pipeline (verdict SETUP), conflicting-timeframe pipeline
(verdict NO_SETUP), fetch-failure pipeline (partial report, verdict
BLOCKED), and demo-fapi HTTP-error surfacing (451 + error envelope).
Note: `pytest` and `python-binance` are NOT installed on this VM, so
tests use stdlib `unittest` and the fetch path uses stdlib `urllib`.

## One-real-chart run — BLOCKED (demo-fapi geo-restricted from this VM)

`BTCUSDT` run 2026-11-25 10:53-10:54 UTC. Verdict: **BLOCKED**.
`demo-fapi.binance.com` returns HTTP 451 on all three timeframes
(1d, 4h, 1h), verbatim:

> `{"code": 0, "msg": "Service unavailable from a restricted location
> according to 'b. Eligibility' in https://www.binance.com/en/terms.
> Please contact customer service if you believe you received this
> message in error."}`

The same 451 comes back from `fapi.binance.com` and `api.binance.com`
from this VM. This is Binance's location-eligibility refusal, not a
missing credential — no key is needed for public klines, and none was
sought. No workaround was attempted (no proxy/VPN; circumventing a
venue's eligibility restriction is not an option).

Per-stage outcome of the blocked run (persisted in the partial report):
stage 1 ERROR (no klines), stage 2 FAIL (fail-closed: 0/250 bars on
all TFs), stage 3 BLOCKED, stage 4 PASS (venue facts recorded,
fundamentals gap named), stage 5 INCONCLUSIVE (calendar refresh worked
— 454 events stored; high-impact items today include CB Consumer
Confidence and CPI prints — no setup into the event), stage 6 BLOCKED
(no levels on untrusted data), stage 7 BLOCKED. Exit code 2.

Persisted evidence (this branch, `Stratex/research/`):
- `TASK-STR-086-STAGED-REPORT-BTCUSDT-20261125T105315Z.json` (33,986 B)
- `TASK-STR-086-STAGED-REPORT-BTCUSDT-20261125T105315Z.md` (28,401 B)
- `economic_calendar.jsonl` (454 events, refreshed from Nasdaq public
  calendar 2026-11-25 10:54 UTC) — local-only: `*.jsonl` is gitignored
  by `Stratex/.gitignore`, so the store is evidence on this VM and is
  regenerable with `--refresh-calendar`; it is NOT in the commit.

The pipeline itself is verified end to end on synthetic klines
(28/28 tests, including a full SETUP run); only the specified
demo-fapi input is unavailable from this VM, so the task's Done
criterion (one real chart analysed end to end) is NOT yet met.

## What was NOT substituted

- The retired classic-testnet venue (`testnet.binancefuture.com`)
  answers ping/klines from this VM, but it is NOT used: owner decision
  TASK-STR-RETIRE-001 retired it and the venue agent refuses it.
- `data-api.binance.vision` answers (spot klines only; its `/fapi`
  path is 404) — not used: it is spot, not the specified demo-fapi
  futures venue, and no alternate venue was authorised.
- No venue was substituted silently. The blocked run is filed as
  blocked, with the partial report as evidence.

## Decision owed (coordinator)

1. Run the one-real-chart leg on the fleet (Oracle Server 2, where
   demo-fapi is expected reachable) using this branch's pipeline, OR
2. Explicitly authorise an alternate klines venue for the done-run, OR
3. Direct another path to a reachable demo-fapi endpoint.
Until then, TASK-STR-086 stays open with build + tests complete and the
chart leg blocked. No PR is opened by this run; the work PR is for the
parent/coordinator to open after review.

## Files in this commit

- `Stratex/research/staged_chart_checklist.py` (new, 7-stage pipeline)
- `Stratex/research/test_staged_chart_checklist.py` (new, 28 tests)
- `Stratex/research/TASK-STR-086-STAGED-REPORT-BTCUSDT-20261125T105315Z.json` (new, partial blocked-run report)
- `Stratex/research/TASK-STR-086-STAGED-REPORT-BTCUSDT-20261125T105315Z.md` (new, partial blocked-run report)
- `Stratex/research/TASK-STR-086-CHECKPOINT-2.md` (this file)

Not committed (repo-ignored): `Stratex/research/economic_calendar.jsonl`
(`*.jsonl` in `Stratex/.gitignore`) — local calendar-store evidence,
regenerable via `--refresh-calendar`.

## Status

Muse TP6 — TASK-STR-086 — build + tests DONE (28/28), chart run
BLOCKED on demo-fapi HTTP 451 geo-restriction from this VM, decision
owed (see above). Branch
`musetp6/task-str-086-staged-chart-checklist`, head after this commit
to be recorded in the run report. No PR created; no merge; no board
changes.
