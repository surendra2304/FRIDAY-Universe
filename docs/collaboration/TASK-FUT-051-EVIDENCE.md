# TASK-FUT-051 — Futuris forecast quality: score the next unscored batch after FUT-049 + scheduler-cycle health check

**Owner:** Muse 9 · **Date:** 2026-11-28 · **Service:** Futuris on IntelX-Server (bridge server 6, PID 63602, port 8004) · **Claim:** hub 7237230501 (WATCH266 §C; board PR #2326 CLAIMED/muse_9) · **Branch:** `muse9/task-fut-051` @ `f7ec8314` (base main `f7ec8314f62c0863ac59835096ff1dce2aaa5248`)

## Verdict

The unscored queue is empty again: census 0 unscored, 0 event-only, and my sweep scored 0. The "next batch after FUT-049" is a single scheduler-scored row resolved after FUT-049's newest row (08:41 UTC, synthetic checkout, prediction 875.05 vs observed 1718.92) — n=1, below any verdict threshold on its own. The 24h/72h windows repeat the FUT-016/FUT-045/FUT-047/FUT-049 pattern: synthetic scores with interval hit rate 1.0 and live fleet-demand scores with hit rate 0.0 (prediction ~269 vs actuals ~1750, mean pct error ~86–87%). The last 3 hourly forecast cycles produced real forecasts (07:xx n=11, 08:xx n=11, 09:xx n=11). The fit-cost cap resolves live at 256 MB and did not bind (zero `fit_cost_cap` events since 2026-11-27 03:00 UTC); no new OOM kill since the 05:10 UTC kill (three kills today, all before FUT-047), so the cap is still not proven to bind before memory pressure kills the service.

## 1. Scoring sweep (this run)

Method: `scripts/run_forecast_tracker.py --score` on IntelX-Server (venv312, `PYTHONPATH=/opt/friday_universe/Futuris:/opt/friday_universe`, service storage layer, Oracle store), 2026-11-28 ~09:26 UTC (~14:56 IST). Census via `ForecastScoreRepository.list_unscored_resolved` (read-only, rollback) immediately before the sweep.

- Census before sweep: **0 unscored**; event-only resolved 0; scores total 1272 (FUT-028: 1271 at ~08:28 UTC; the +1 landed at 08:41 UTC, scored by the scheduler's own job — see below); forecasts total 1876; newest forecast 09:11 UTC (live `friday:fleet:forecast_demand_24h`).

- Sweep result (run twice, both no-ops): `considered 0, scored 0, skipped_no_numeric_actual 0, skipped_duplicate 0, event_only_resolved 0` — no score rows written by this task.

- Tracker report: n_scored 1272, verdict "underconfident", coverage_80 1.0, MAE 875.80, rolling 30d hit rate 0.8907 — the synthetic bulk dominates the headline, as in FUT-016/FUT-045/FUT-047/FUT-049. Live target `friday:fleet:forecast_demand_24h` all-time: n=139, coverage_90 **0.0**, MAE 1909.31, mean pct error 90.50%.

- Scheduler state: `forecast_scoring_job` (30-min interval) executed successfully at 08:41 (scored 1, n=1272) and 09:10 (scored 0, n=1272); service health degraded at probe time (storage ok 13/13 tables; forecasting `unknown` / NO_MODEL_PROBE — capability honesty, not a scoring fault). PID 63602 since 05:10 UTC, MemoryCurrent ~300M / MemoryMax 512M.

Window convention (per FUT-049, verified first-hand): all windows below use **resolved_at** for comparability with FUT-047/FUT-049.

## 2. Next batch accuracy (resolved since FUT-049)

FUT-049's newest resolved row was 07:41:01 UTC (synthetic checkout, the +1 to 1271). A strict window `resolved_at > 07:41:00 UTC` returns n=2, but one of those rows (07:41:01) is FUT-049's own row; the genuinely new batch since FUT-049 is n=1 (08:41:01 UTC). Both are shown for auditability; the n=1 row is the FUT-051 batch.

| Scope | n | MAE | Mean pct err | Interval hit rate |
|---|---|---|---|---|
| All (since 07:41:00 UTC; incl. FUT-049 row) | 2 | 843.86 | 49.09% | 1.0 |
| All (since FUT-049 newest 07:41:01 UTC; = since FUT-028 08:28 UTC) | 1 | 843.87 | 49.09% | 1.0 |
| Live (`friday:fleet:forecast_demand_24h`) | 0 | — | — | — |
| Synthetic (`service:checkout:capacity_exceedance_24h`) | 1 | 843.87 | 49.09% | **1.0** |
| All (last 24h, for comparability) | 171 | 835.69 | 49.41% | 0.8947 |
| Live (last 24h) | 18 | 1477.27 | 85.63% | **0.0** |
| Synthetic (last 24h) | 153 | 760.20 | 45.15% | **1.0** |
| All (last 72h) | 541 | 802.64 | 51.48% | 0.8909 |
| Live (last 72h) | 59 | 1597.03 | 87.10% | **0.0** |
| Synthetic (last 72h) | 482 | 705.40 | 47.12% | **1.0** |

Newest rows: live prediction 268.59 vs observed 1753.37 (abs error 1484.78, pct 84.68%, interval miss, resolved 03:06 UTC — still the newest live row); synthetic checkout rows prediction ~875 vs observed 1718.92 (abs error ~844, pct ~49.1%, interval hit, resolved 03:37/04:40/05:41/06:41/07:41/08:41 UTC). The post-FUT-049 batch (n=1) is below any verdict threshold on its own; the 24h/72h windows carry the accuracy claim and match FUT-049's shape (24h live hit 0.0 n=18 vs FUT-049 n=20 as the window slid; synthetic 1.0).

## 3. Last 3 scheduler cycles (forecast production)

Forecasts written per UTC hour (live store, last 8h n=71: 8 live / 63 synthetic):

- 07:xx UTC: 11 forecasts. 08:xx UTC: 11 forecasts. 09:xx UTC: 11 forecasts (newest 09:11 UTC, incl. live `friday:fleet:forecast_demand_24h`).

- Journal: `forecast_refresh_job` (hourly) executed successfully 07:10→07:14, 08:10→08:15 and 09:10→09:14 UTC; `forecast_scoring_job` executed successfully 08:41 (scored 1, n_scored_total 1271→1272) and 09:10 UTC (scored 0).

- Verdict: last 3 cycles PASS for production (real forecasts each hour, 11/11/11). Earlier context: 05:xx n=3 (truncated by the 05:10 UTC OOM kill), 06:xx n=11; 02:xx n=3 (02:35 UTC OOM kill); 03:xx has no forecasts (restart/redeploy window noted in FUT-045).

## 4. Fit-cost cap check

- Cap: `FUTURIS_FIT_MEMORY_BUDGET_MB=256` (resolved live this run via `resolve_fit_memory_budget` → 256.0; `futuris/infra/config.py`, TASK-FUT-017). Selection shortlists candidates against it and stamps `fit_cost_cap` when candidates drop (`futuris/models/selection.py`).

- Binding evidence: **zero** `fit_cost_cap` journal events since 2026-11-27 03:00 UTC — the cap has not bound in the checked window (same as FUT-045/FUT-047/FUT-049).

- Counter-evidence: no NEW OOM kill since FUT-047; three kills today, all before FUT-047's window — 02:35 UTC (512.2M peak, per FUT-045), 04:09 UTC (300.6M) and 05:10 UTC (197.8M), all `Failed with result 'oom-kill'`. Service auto-restarted each time (current PID 63602 since 05:10 UTC, MemoryCurrent ~300M at probe, MemoryMax 512M). "Cap checked" still ≠ "cap proven to bind first"; the FUT-045 follow-up stands: instrument or reproduce a cap-binding fit before claiming the cap controls fit memory.

## 5. States

implemented N/A (evidence task) / tested YES (census + sweep + batch aggregates + cycle + journal + health checks run first-hand) / merged NO / deployed N/A / production-verified YES for the scoring-state, batch-accuracy, cycle and cap claims above (live store read through the service's own storage layer; no service change, no restart by this task).

— Muse 9, 2026-11-28
