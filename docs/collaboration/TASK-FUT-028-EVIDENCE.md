# TASK-FUT-028 — Futuris forecast accuracy scoring run 3: score the next unscored forecast cohort

**Owner:** Muse 9 · **Date:** 2026-11-28 · **Service:** Futuris on IntelX-Server (bridge server 6, `Futuris.service`, PID 63602, port 8004) · **Claim:** hub #2045 comment 7236579772 (WATCH263 §C + BE 13:45 §B assignment; WATCH263 §D.5 ruling: FUT-028 is M9's) · **Branch:** `muse9/task-fut-028` @ main `38887ed5`

## Verdict

The unscored cohort is empty: the scheduler's 30-minute scoring job keeps the queue drained, so run 3's "next cohort" is the scheduler-scored batch resolved since FUT-047's probe (2026-11-28 06:44 UTC), re-verified here. That batch is a single synthetic score (n=1, interval hit). The 24h/72h windows repeat the FUT-016/FUT-045/FUT-047 pattern exactly: synthetic scores with interval hit rate 1.0 (vacuously wide intervals) and live fleet-demand scores with hit rate 0.0 (mean pct error ~86–87%). The fit-cost cap is live at 256 MB, did not bind (zero `fit_cost_cap` events since 06:30 UTC), and there has been no OOM kill since the 05:10 UTC kill recorded in FUT-047 (NRestarts still 2, PID unchanged since 05:10 UTC). The last 3 hourly forecast cycles produced real forecasts (06:xx n=11, 07:xx n=11, 08:xx n=11, newest as_of 08:11 UTC).

## 1. Scoring sweep (this run)

Method: census via `ForecastScoreRepository.list_unscored_resolved` (read-only, rollback) immediately before the sweep, then `scripts/run_forecast_tracker.py --score` on IntelX-Server (venv312, service storage layer, Oracle store), 2026-11-28 ~08:28 UTC (~13:58 IST). All reads through the service's own repository layer; SELECTs only + rollback, apart from the tracker sweep itself.

- Census before sweep (oldest-first): **0 unscored**.
- Sweep result: `considered 0, scored 0, skipped_no_numeric_actual 0, skipped_duplicate 0, event_only_resolved 0` — no score rows written by this task.
- Tracker report: n_scored **1271** (FUT-047: 1270 at ~12:14 IST; +1 scored by the scheduler at 07:41 UTC), coverage_80 1.0, MAE 875.82. By evidence class: live n=139, coverage_90 **0.0**, MAE 1909.31, mean pct error 90.50%; synthetic n=1132, coverage_80 1.0, MAE 748.92, mean pct error 45.82%.
- Scheduler state (journal, PID 63602): `forecast_scoring_job` executed successfully 06:41 (scored 1, total 1270), 07:10 (0), 07:40 (0), 07:41 (scored 1, total 1271), 08:10 UTC; `forecast_refresh_job` executed successfully 07:10→07:14 and 08:10 UTC. Service health at probe: degraded — storage ok 13/13 tables; forecasting `unknown` / NO_MODEL_PROBE (capability honesty, not a scoring fault; same as FUT-047).

Coordination note: TASK-FUT-046 (PR #2300) and TASK-FUT-047 (PR #2292) are IN_REVIEW with verdicts due ~15:30 / ~15:00 IST (WATCH264 §C); with the queue at 0 there is no unscored batch to contest. FUT-028 reports the post-FUT-047 batch below.

## 2. Cohort accuracy (resolved since FUT-047 probe, 2026-11-28 06:44 UTC)

| Scope | n | MAE | Mean pct err | Interval hit rate |
|---|---|---|---|---|
| All (since 06:44 UTC) | 1 | 843.85 | 49.09% | 1.0 |
| Live (`friday:fleet:forecast_demand_24h`) | 0 | — | — | — |
| Synthetic (`service:checkout:capacity_exceedance_24h`) | 1 | 843.85 | 49.09% | **1.0** |
| All (last 24h, for comparability) | 179 | 829.37 | 49.07% | 0.894 |
| Live (last 24h) | 19 | 1474.63 | 85.62% | **0.0** |
| Synthetic (last 24h) | 160 | 752.74 | 44.73% | **1.0** |
| All (last 72h) | 540 | 802.56 | 51.49% | 0.891 |
| Live (last 72h) | 59 | 1597.03 | 87.10% | **0.0** |
| Synthetic (last 72h) | 481 | 705.11 | 47.12% | **1.0** |

Newest row: synthetic checkout prediction 875.07 vs observed 1718.92 (abs error 843.85, pct 49.09%, interval hit, resolved 07:41 UTC). The post-FUT-047 batch (n=1) is below any verdict threshold on its own; the 24h/72h windows carry the accuracy claim and match FUT-047's shape (24h live hit 0.0 n=19 vs FUT-047 n=20; synthetic 1.0).

## 3. Last 3 scheduler cycles (forecast production)

Forecasts written per UTC hour (`ForecastModel.as_of`, last 6h n=49): 02:xx 3, 04:xx 10, 05:xx 3, 06:xx 11, 07:xx 11, 08:xx 11 (newest as_of 08:11:02 UTC). The 03:xx hour has no forecasts (03:07 UTC restart/redeploy window noted in FUT-045/FUT-047); 05:xx was truncated by the 05:10 UTC OOM kill (FUT-047 §4). Verdict: last 3 cycles (06/07/08) PASS for production — real forecasts each hour, no truncation.

## 4. Fit-cost cap check

- Cap: `FUTURIS_FIT_MEMORY_BUDGET_MB=256` (resolved live this run via `futuris.models.fit_cost.resolve_fit_memory_budget(None)` → 256.0; `futuris/infra/config.py`, TASK-FUT-017).
- Binding evidence: **zero** `fit_cost_cap` journal events since 2026-11-28 06:30 UTC — the cap has not bound in the checked window (same as FUT-045/FUT-047).
- OOM state: no `oom-kill` journal events since 05:15 UTC; `NRestarts=2`, PID 63602 unchanged since 05:10 UTC, MemoryCurrent ~312 MB against MemoryMax 512 MB at probe. The FUT-045/FUT-047 follow-up stands: the cap is still not proven to bind before memory pressure kills the service — instrument or reproduce a cap-binding fit before claiming the cap controls fit memory.

## 5. States

implemented N/A (evidence task) / tested YES (census + sweep + batch aggregates + cycle + journal checks run first-hand) / merged NO / deployed N/A / production-verified YES for the scoring-state, batch-accuracy, cycle and cap claims above (live store read through the service's own storage layer; no service change, no restart by this task).

— Muse 9, 2026-11-28
