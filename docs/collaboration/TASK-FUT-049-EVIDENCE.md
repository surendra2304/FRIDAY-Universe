# TASK-FUT-049 — Futuris forecast quality: next unscored batch after FUT-047 + fit-cost cap check

**Owner:** Muse TP11 · **Date:** 2026-11-28 · **Service:** Futuris on IntelX-Server (bridge server 6, PID 63602, port 8004) · **Claim:** hub 7234861652 (WATCH258 §D); REL-123 double-claim released hub 7236055851, FUT-049 confirmed single head · **Branch:** `musetp11/task-fut-049-forecast-quality-next-batch` @ `1368bf07` (checkpoint 1)

## Verdict

The unscored queue is empty again: census 0 unscored, 0 event-only, and my sweep scored 0. The "next batch after FUT-047" is the single scheduler-scored row since FUT-047's window end (resolved 07:41 UTC, synthetic checkout, prediction 875.07 vs observed 1718.92) — n=1, below any verdict threshold on its own. The 24h/72h windows repeat the FUT-016/FUT-045/FUT-047 pattern exactly: synthetic scores with interval hit rate 1.0 and live fleet-demand scores with hit rate 0.0 (prediction ~269 vs actuals ~1750, mean pct error ~85–87%). The fit-cost cap is live at 256 MB and did not bind (zero `fit_cost_cap` events since 2026-11-27 03:00 UTC), but Futuris was OOM-killed three times today already (02:35, 04:09, 05:10 UTC) — no new kill since FUT-047 — so the cap is still not proven to bind before memory pressure kills the service. The last 3 hourly forecast cycles produced real forecasts (05:xx n=3 truncated by the 05:10 OOM kill, 06:xx n=11, 07:xx n=11).

## 1. Scoring sweep (this run)

Method: `scripts/run_forecast_tracker.py --score` on IntelX-Server (venv312, `PYTHONPATH=/opt/friday_universe/Futuris:/opt/friday_universe`, service storage layer, Oracle store), 2026-11-28 ~07:40 UTC (~13:10 IST). Census via `ForecastScoreRepository.list_unscored_resolved` (read-only, rollback) immediately before the sweep.

- Census before sweep (oldest-first): **0 unscored**; event-only resolved 0; scores total 1270 at sweep time (FUT-047: 1270 at ~06:44 UTC; the +1 to 1271 landed after my sweep, scored by the scheduler's own 07:41 job — see below).
- Sweep result: `considered 0, scored 0, skipped_no_numeric_actual 0, skipped_duplicate 0, event_only_resolved 0` — no score rows written by this task.
- Tracker report: n_scored 1270, verdict "underconfident", coverage_80 1.0, MAE 875.85, rolling 30d hit rate 0.8906 — the synthetic bulk dominates the headline, as in FUT-016/FUT-045/FUT-047. Live target `friday:fleet:forecast_demand_24h` all-time: n=139, coverage_90 **0.0**, MAE 1909.31, mean pct error 90.50%.
- Scheduler state: `forecast_scoring_job` (30-min interval) executed successfully at 07:10 (scored 0, n=1270), 07:40 (scored 0, n=1270) and 07:41 (scored 1, n=1271); service health degraded at probe time (storage ok 13/13 tables; forecasting `unknown` / NO_MODEL_PROBE — capability honesty, not a scoring fault). PID 63602 since 05:10 UTC.

Window convention, verified first-hand: FUT-047's windows are by **resolved_at** — at M9's 06:44 UTC anchor, resolved_at windows reproduce their 187/552 exactly, while scored_at windows give 179/592. All windows in this evidence use resolved_at for comparability.

## 2. Next batch accuracy (resolved since FUT-047 window end, 2026-11-28 06:44 UTC)

| Scope | n | MAE | Mean pct err | Interval hit rate |
|---|---|---|---|---|
| All (since 06:44 UTC) | 1 | 843.85 | 49.09% | 1.0 |
| Live (`friday:fleet:forecast_demand_24h`) | 0 | — | — | — |
| Synthetic (`service:checkout:capacity_exceedance_24h`) | 1 | 843.85 | 49.09% | **1.0** |
| All (last 24h, for comparability) | 188 | 824.80 | 48.78% | 0.8936 |
| Live (last 24h) | 20 | 1473.91 | 85.63% | **0.0** |
| Synthetic (last 24h) | 168 | 747.53 | 44.39% | **1.0** |
| All (last 72h) | 544 | 804.29 | 51.45% | 0.8897 |
| Live (last 72h) | 60 | 1605.12 | 87.20% | **0.0** |
| Synthetic (last 72h) | 484 | 705.02 | 47.02% | **1.0** |

Newest rows: live prediction 268.59 vs observed 1753.37 (abs error 1484.78, pct 84.68%, interval miss, resolved 03:06 UTC); synthetic checkout rows prediction ~875 vs observed 1718.92 (abs error ~844, pct ~49.1%, interval hit, resolved 03:37/04:40/05:41/06:41/07:41 UTC). Resolutions since FUT-047 are a single row, so the post-FUT-047 batch (n=1) is below any verdict threshold on its own; the 24h/72h windows carry the accuracy claim and match FUT-047's shape (24h live hit 0.0 n=20 vs FUT-047 n=20; synthetic 1.0).

## 3. Last 3 scheduler cycles (forecast production)

Forecasts written per UTC hour (live store, `ForecastModel.created_at`, last 8h n=60: 7 live / 53 synthetic):

- 05:xx UTC: 3 forecasts (cycle truncated by the 05:10 UTC OOM kill). 06:xx UTC: 11 forecasts. 07:xx UTC: 11 forecasts (newest 07:xx, incl. live `friday:fleet:forecast_demand_24h`).
- Journal: `forecast_refresh_job` (hourly) executed successfully 06:10→06:16 UTC (FUT-047) and 07:14:28 UTC; `forecast_scoring_job` executed successfully 07:10/07:40/07:41 UTC (scored 0, 0, 1; n_scored_total 1270→1271).
- Verdict: last 3 cycles PASS for production (real forecasts each hour), with the 05:xx cycle truncated by OOM. The 02:xx hour has n=3 (truncated by the 02:35 UTC OOM kill); the 03:xx hour has no forecasts (03:07 UTC restart/redeploy window noted in FUT-045).

## 4. Fit-cost cap check

- Cap: `FUTURIS_FIT_MEMORY_BUDGET_MB=256` (resolved live this run via `resolve_fit_memory_budget` → 256.0; `futuris/infra/config.py`, TASK-FUT-017). Selection shortlists candidates against it and stamps `fit_cost_cap` when candidates drop (`futuris/models/selection.py`).
- Binding evidence: **zero** `fit_cost_cap` journal events since 2026-11-27 03:00 UTC — the cap has not bound in the checked window (same as FUT-045/FUT-047).
- Counter-evidence: no NEW OOM kill since FUT-047; three kills today, all before FUT-047's window — 02:35 UTC (512.2M peak, per FUT-045), 04:09 UTC (300.6M) and 05:10 UTC (197.8M), all `Failed with result 'oom-kill'`. Peaks below the 512M MemoryMax point to host-level memory pressure rather than the cgroup backstop alone. Service auto-restarted each time (current PID 63602 since 05:10 UTC, MemoryCurrent ~319M at probe, MemoryMax 512M). "Cap checked" still ≠ "cap proven to bind first"; the FUT-045 follow-up stands: instrument or reproduce a cap-binding fit before claiming the cap controls fit memory.

## 5. States

implemented N/A (evidence task) / tested YES (census + sweep + batch aggregates + cycle + journal checks run first-hand) / merged NO / deployed N/A / production-verified YES for the scoring-state, batch-accuracy, cycle and cap claims above (live store read through the service's own storage layer; no service change, no restart by this task).

— Muse TP11, 2026-11-28
