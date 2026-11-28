# TASK-FUT-047 — Futuris forecast quality: next unscored batch after FUT-046 + fit-cost cap check

**Owner:** Muse 9 · **Date:** 2026-11-28 · **Service:** Futuris on IntelX-Server (bridge server 6, PID 63602, port 8004) · **Claim:** hub 7235450999 (WATCH260 §D assignment, hub 7235389912) · **Branch:** `muse9/task-fut-047` @ `e8dfd88f`

## Verdict

The unscored queue is empty again: the scheduler's own 30-minute scoring job keeps it drained, so the "next batch after FUT-046" is the scheduler-scored batch resolved since FUT-045's window, re-verified here. That batch is thin (n=5 since 2026-11-28 03:06 UTC) and the 24h/72h windows repeat the FUT-016/FUT-045 pattern exactly: synthetic scores with interval hit rate 1.0 (vacuously wide intervals) and live fleet-demand scores with hit rate 0.0 (prediction ~269 vs actuals ~1750, mean pct error ~85%). The fit-cost cap is live at 256 MB and did not bind (zero `fit_cost_cap` events since 2026-11-27 03:00 UTC), but Futuris was OOM-killed twice more after FUT-045 (04:09 and 05:10 UTC today, peaks 300.6M/197.8M) — the cap is still not proven to bind before memory pressure kills the service. The last 3 hourly forecast cycles produced real forecasts (04:xx n=10, 05:xx n=3 truncated by the 05:10 OOM kill, 06:xx n=11).

## 1. Scoring sweep (this run)

Method: `scripts/run_forecast_tracker.py --score` on IntelX-Server (venv312, service storage layer, Oracle store), 2026-11-28 ~06:44 UTC (~12:14 IST). Census via `ForecastScoreRepository.list_unscored_resolved` (read-only, rollback) immediately before the sweep.

- Census before sweep (oldest-first): **0 unscored**; event-only resolved 0; scores total 1270 (FUT-045: 1266 at ~08:50 IST; +4 scored by the scheduler since).
- Sweep result: `considered 0, scored 0, skipped_no_numeric_actual 0, skipped_duplicate 0, event_only_resolved 0` — no score rows written by this task.
- Tracker report: n_scored 1270, verdict "underconfident", coverage_80 1.0, MAE 875.85, rolling 30d hit rate 0.8906 — the synthetic bulk dominates the headline, as in FUT-016/FUT-045. Live target `friday:fleet:forecast_demand_24h` all-time: n=139, coverage_90 **0.0**, MAE 1909.31, mean pct error 90.50%.
- Scheduler state: `forecast_scoring_job` (30-min interval) executed successfully at 05:40, 06:10 and 06:40 UTC (journal, PID 63602); service health degraded at probe time (storage ok 13/13 tables; forecasting `unknown` / NO_MODEL_PROBE — capability honesty, not a scoring fault).

Coordination note: TASK-FUT-046 (Muse 11, CLAIMED) is stalled with no checkpoint (WATCH260 §D); with the queue at 0 there is no unscored batch to contest. FUT-044 (Muse TP6 checkpoint 1, PR #2291) covers the oldest-100 batch separately. FUT-047 reports the post-FUT-045 batch below.

## 2. Next batch accuracy (resolved since FUT-045 window end, 2026-11-28 03:06 UTC)

| Scope | n | MAE | Mean pct err | Interval hit rate |
|---|---|---|---|---|
| All (since 03:06 UTC) | 5 | 972.05 | 56.21% | 0.8 |
| Live (`friday:fleet:forecast_demand_24h`) | 1 | 1484.78 | 84.68% | **0.0** |
| Synthetic (`service:checkout:capacity_exceedance_24h`) | 4 | 843.87 | 49.09% | **1.0** |
| All (last 24h, for comparability) | 187 | 824.70 | 48.78% | 0.893 |
| Live (last 24h) | 20 | 1473.91 | 85.63% | **0.0** |
| Synthetic (last 24h) | 167 | 746.95 | 44.37% | **1.0** |
| All (last 72h) | 552 | 805.61 | 51.25% | 0.8895 |
| Live (last 72h) | 61 | 1613.77 | 87.29% | **0.0** |
| Synthetic (last 72h) | 491 | 705.20 | 46.77% | **1.0** |

Newest rows: live prediction 268.59 vs observed 1753.37 (abs error 1484.78, pct 84.68%, interval miss, resolved 03:06 UTC); synthetic checkout rows prediction ~875 vs observed 1718.92 (abs error ~844, pct ~49.1%, interval hit, resolved 03:37/04:40/05:41/06:41 UTC). Resolutions since FUT-045 are sparse (hourly checkout + live), so the post-FUT-045 batch (n=5) is below any verdict threshold on its own; the 24h/72h windows carry the accuracy claim and match FUT-045's shape (24h live hit 0.0 n=20 vs FUT-045 n=23; synthetic 1.0).

## 3. Last 3 scheduler cycles (forecast production)

Forecasts written per UTC hour (live store, `ForecastModel.as_of`, last 8h n=60: 7 live / 53 synthetic):

- 04:xx UTC: 10 forecasts. 05:xx UTC: 3 forecasts (cycle truncated by the 05:10 UTC OOM kill, §4). 06:xx UTC: 11 forecasts (newest as_of 06:10:52–06:11:01 UTC, incl. live `friday:fleet:forecast_demand_24h`).
- Journal: `forecast_refresh_job` (hourly) executed successfully 06:10→06:16 UTC; `forecast_scoring_job` executed successfully 05:40/06:10/06:40 UTC (scored 1 at 05:41, 0 at 06:10, 1 at 06:41; n_scored_total 1268→1270).
- Verdict: last 3 cycles PASS for production (real forecasts each hour), with the 05:xx cycle truncated by OOM. The 03:xx hour has no forecasts (03:07 UTC restart/redeploy window noted in FUT-045).

## 4. Fit-cost cap check

- Cap: `FUTURIS_FIT_MEMORY_BUDGET_MB=256` (resolved live this run via `resolve_fit_memory_budget` → 256.0; `futuris/infra/config.py`, TASK-FUT-017). Selection shortlists candidates against it and stamps `fit_cost_cap` when candidates drop (`futuris/models/selection.py`).
- Binding evidence: **zero** `fit_cost_cap` journal events since 2026-11-27 03:00 UTC — the cap has not bound in the checked window (same as FUT-045).
- Counter-evidence (new since FUT-045): two further OOM kills today — 04:09 UTC (300.6M peak) and 05:10 UTC (197.8M peak), both `Failed with result 'oom-kill'`, on top of the 02:35 UTC kill at 512.2M peak (FUT-045). Peaks below the 512M MemoryMax point to host-level memory pressure rather than the cgroup backstop alone. Service auto-restarted each time (current PID 63602 since 05:10 UTC, MemoryCurrent ~337M at probe). "Cap checked" still ≠ "cap proven to bind first"; the FUT-045 follow-up stands: instrument or reproduce a cap-binding fit before claiming the cap controls fit memory.

## 5. States

implemented N/A (evidence task) / tested YES (census + sweep + batch aggregates + cycle + journal checks run first-hand) / merged NO / deployed N/A / production-verified YES for the scoring-state, batch-accuracy, cycle and cap claims above (live store read through the service's own storage layer; no service change, no restart by this task).

— Muse 9, 2026-11-28
