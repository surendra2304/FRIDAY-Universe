# TASK-FUT-046 — Futuris forecast quality: score the following unscored batch + fit-cost cap check

**Owner:** Muse 9 · **Date:** 2026-11-28 · **Service:** Futuris on IntelX-Server (bridge server 6, host ip-172-26-4-138, PID 63602, port 8004) · **Claim:** hub 7235943406 (WATCH261 §C assignment, hub 7235730851; after the #2290 verdict, review 6096493808) · **Branch:** `muse9/task-fut-046` @ `d72d7966` (main at claim)

## Verdict

The following batch is empty. The scheduler's own 30-minute scoring job keeps the unscored queue drained (0 unscored at census, sweep considered 0 / scored 0), and no forecast has resolved-and-scored since TASK-FUT-047's probe (~06:44 UTC): scores total is unchanged at 1270, newest score scored 06:41:03 UTC. The post-FUT-045 batch (n=5) that FUT-047 reported is still the latest batch, and the 24h/72h windows repeat the FUT-016/FUT-045/FUT-047 pattern exactly: synthetic scores with interval hit rate 1.0 (vacuously wide intervals) and live fleet-demand scores with hit rate 0.0 (prediction ~269 vs actuals ~1750, mean pct error ~85%). The fit-cost cap is live at 256 MB and did not bind (zero `fit_cost_cap` events since 2026-11-27 03:00 UTC); no new OOM kill since FUT-047's 05:10 UTC kill — the service has run continuously since (PID 63602, ~303M current vs 512M MemoryMax). The last 3 hourly forecast cycles produced real forecasts (05:xx n=3 truncated by the 05:10 OOM kill, 06:xx n=11, 07:xx n=11).

Numbering note (plain): FUT-047 ("next batch after FUT-046") executed before FUT-046 because FUT-046's first owner (Muse 11) stalled with zero commits and the task re-slotted (WATCH261 §D). FUT-047 therefore covered the post-FUT-045 batch. FUT-046, claimed fresh by Muse 9, re-verified first-hand and found no further batch to score — the "following batch" after FUT-047 is n=0. Nothing is double-claimed: this record reports the fresh census/sweep and the unchanged accuracy windows.

## 1. Scoring sweep (this run)

Method: census via `ForecastScoreRepository.list_unscored_resolved` (read-only, rollback) immediately before the sweep; sweep via `scripts/run_forecast_tracker.py --score` on IntelX-Server (venv312, service storage layer, Oracle store), 2026-11-28 ~07:27–07:28 UTC (~12:57 IST). The sweep ran twice (first run's head was truncated in capture; both runs were no-ops — considered 0, no score rows written).

- Census before sweep (oldest-first): **0 unscored**; event-only resolved 0; scores total 1270 (identical to FUT-047 at ~12:14 IST); forecasts total 1854; newest score scored 2026-11-28T06:41:03Z (resolved 06:41:00Z).
- Sweep result: `considered 0, scored 0, skipped_no_numeric_actual 0, skipped_duplicate 0, event_only_resolved 0` — no score rows written by this task.
- Tracker report: n_scored 1270, verdict "underconfident", coverage_80 1.0, MAE 875.85, rolling 30d hit rate 0.8906 — the synthetic bulk dominates the headline, as in FUT-016/FUT-045/FUT-047. Live target `friday:fleet:forecast_demand_24h` all-time: n=139, coverage_90 **0.0**, MAE 1909.31, mean pct error 90.50%.
- Scheduler state: `forecast_scoring_job` (30-min interval) executed successfully at 06:41 UTC (considered 1, scored 1, n_scored_total 1269→1270) and 07:10 UTC (considered 0, scored 0); next run 07:40 UTC (journal, PID 63602).

## 2. Following-batch accuracy (resolved since FUT-047 probe, 2026-11-28 06:44 UTC)

| Scope | n | MAE | Mean pct err | Interval hit rate |
|---|---|---|---|---|
| All (since FUT-047 probe 06:44Z) | 0 | — | — | — |
| All (since FUT-045 window end 03:06Z) | 5 | 972.05 | 56.21% | 0.8 |
| Live (`friday:fleet:forecast_demand_24h`, since 03:06Z) | 1 | 1484.78 | 84.68% | **0.0** |
| Synthetic (`service:checkout:capacity_exceedance_24h`, since 03:06Z) | 4 | 843.87 | 49.09% | **1.0** |
| All (last 24h, for comparability) | 187 | 824.70 | 48.78% | 0.893 |
| Live (last 24h) | 20 | 1473.91 | 85.63% | **0.0** |
| Synthetic (last 24h) | 167 | 746.95 | 44.37% | **1.0** |
| All (last 72h) | 543 | 804.22 | 51.45% | 0.8895 |
| Live (last 72h) | 60 | 1605.12 | 87.20% | **0.0** |
| Synthetic (last 72h) | 483 | 704.73 | 47.01% | **1.0** |

Newest rows: live prediction 268.59 vs observed 1753.37 (abs error 1484.78, pct 84.68%, interval miss, resolved 03:06 UTC); synthetic checkout rows prediction ~875 vs observed 1718.92 (abs error ~844, pct ~49.1%, interval hit, resolved 03:37/04:40/05:41/06:41 UTC). No score resolved after 06:41 UTC, so the following batch is n=0 and carries no accuracy claim on its own; the 24h/72h windows carry the claim and match FUT-047's shape (72h n=543 vs FUT-047's 552 — the window slid and 9 rows aged out; live 60 vs 61).

## 3. Last 3 scheduler cycles (forecast production)

Forecasts written per UTC hour (live store, `ForecastModel.as_of`, last 8h n=71: 8 live / 63 synthetic):

- 05:xx UTC: 3 forecasts (cycle truncated by the 05:10 UTC OOM kill, §4). 06:xx UTC: 11 forecasts. 07:xx UTC: 11 forecasts (newest as_of 07:10:52–07:11:03 UTC, incl. live `friday:fleet:forecast_demand_24h`).
- Journal: `forecast_refresh_job` (hourly) executed successfully 06:10→06:16 UTC and 07:10→07:14 UTC; `forecast_scoring_job` executed successfully 06:41 UTC (scored 1) and 07:10 UTC (scored 0).
- Verdict: last 3 cycles PASS for production (real forecasts each hour), with the 05:xx cycle truncated by OOM. The 03:xx hour has no forecasts (03:07 UTC restart/redeploy window noted in FUT-045).

## 4. Fit-cost cap check

- Cap: `FUTURIS_FIT_MEMORY_BUDGET_MB=256` (resolved live this run via `resolve_fit_memory_budget` → 256.0; `futuris/infra/config.py`, TASK-FUT-017). Selection shortlists candidates against it and stamps `fit_cost_cap` when candidates drop (`futuris/models/selection.py`).
- Binding evidence: **zero** `fit_cost_cap` journal events since 2026-11-27 03:00 UTC (grep count 0 this run) — the cap has not bound in the checked window (same as FUT-045/FUT-047).
- OOM state (new since FUT-047): **no** OOM kill since 2026-11-28 06:00 UTC (journal grep empty). Service active/running, MainPID 63602 (unchanged since the 05:10 UTC restart), MemoryCurrent 317,616,128 bytes (~303M) vs MemoryMax 536,870,912 (512M) at probe. "Cap checked" still ≠ "cap proven to bind first"; the FUT-045 follow-up stands: instrument or reproduce a cap-binding fit before claiming the cap controls fit memory.

## 5. States

implemented N/A (evidence task) / tested YES (census + sweep + batch aggregates + cycle + journal checks run first-hand) / merged NO / deployed N/A / production-verified YES for the scoring-state, batch-accuracy, cycle and cap claims above (live store read through the service's own storage layer; no service change, no restart by this task).

— Muse 9, 2026-11-28
