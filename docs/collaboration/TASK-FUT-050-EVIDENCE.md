# TASK-FUT-050 — Futuris forecast quality: score the next unscored batch after FUT-047 + fit-cost cap check

**Owner:** Muse 15 · **Date:** 2026-11-28 · **Service:** Futuris on IntelX-Server (bridge server 6, host ip-172-26-4-138, PID 63602, port 8004) · **Claim:** hub 7238164339 (WATCH268 §D.1 re-slot from M11, hub 7237659936) · **Branch:** `muse15/task-fut-050-score-next-batch` @ `3b5091de` (main at claim)

## Verdict

The next batch after FUT-047 is thin but non-empty: the scheduler's own 30-minute scoring job keeps the unscored queue drained (0 unscored at census, sweep considered 0 / scored 0), and four forecasts resolved-and-scored since FUT-046's probe (~07:28 UTC) — all synthetic checkout rows, one per hour (07:41, 08:41, 09:41, 10:41 UTC). The 24h/72h windows repeat the FUT-016/FUT-045/FUT-047 pattern exactly: synthetic scores with interval hit rate 1.0 (vacuously wide intervals) and live fleet-demand scores with hit rate 0.0 (prediction ~269 vs actuals ~1750, mean pct error ~85%). The fit-cost cap is live at 256 MB and did not bind (zero `fit_cost_cap` events since 2026-11-27 03:00 UTC), and there has been no OOM kill since FUT-047's 05:10 UTC kill — the service has run continuously since (PID 63602, ~5h49m at probe, MemoryCurrent ~320M vs 512M MemoryMax). The last 3 hourly forecast cycles produced real forecasts (08:xx n=11, 09:xx n=11, 10:xx n=11).

## 1. Scoring sweep (this run)

Method: census via `ForecastScoreRepository.list_unscored_resolved` (read-only, rollback) immediately before the sweep; sweep via `ForecastTracker.score_resolved` + `calibration_report` in-process on IntelX-Server (venv312, service storage layer, Oracle store — the same code path as `scripts/run_forecast_tracker.py --score`), 2026-11-28 ~10:58 UTC (~16:28 IST). Census script `/tmp/fut050_census.py` + launcher `/tmp/fut050_launch.py` (loads the Futuris `.env` into environ in-process, no shell eval, no secret printed); sweep script `/tmp/fut050_sweep.py`. DB config via the Futuris service process env, value never copied or printed.

- Census before sweep (oldest-first): **0 unscored**; event-only resolved 0; scores total 1274 (FUT-046: 1270 at ~07:28 UTC; +4 scored by the scheduler since — one per hour 07:41/08:41/09:41/10:41 UTC); forecasts total 1887; newest score scored 2026-11-28T10:41:04Z (resolved 10:41:02Z, synthetic checkout).
- Sweep result: `considered 0, scored 0, skipped_no_numeric_actual 0, skipped_duplicate 0, event_only_resolved 0` — no score rows written by this task.
- Tracker report: n_scored 1274, verdict "underconfident", coverage_80 1.0, MAE 877.00, rolling 30d hit rate 0.890895 — the synthetic bulk dominates the headline, as in FUT-016/FUT-045/FUT-047. Live target `friday:fleet:forecast_demand_24h` all-time: n=139, coverage_90 **0.0**, MAE 1909.31, mean pct error 90.50%.
- Scheduler state: `forecast_scoring_job` (30-min interval) executed successfully at 10:40:52 UTC (considered 0, scored 0, n_scored_total 1273) and 10:41:03 UTC (considered 1, scored 1, n_scored_total 1274 — the 10:41 checkout resolution); next run 11:10:52 UTC (journal, PID 63602).

## 2. Next batch accuracy (resolved since FUT-046 probe, 2026-11-28 07:28 UTC)

| Scope | n | MAE | Mean pct err | Interval hit rate |
|---|---|---|---|---|
| All (since FUT-046 probe 07:28Z) | 4 | 1242.12 | 55.40% | 1.0 |
| Live (`friday:fleet:forecast_demand_24h`, since 07:28Z) | 0 | — | — | — |
| Synthetic (all non-live, since 07:28Z) | 4 | 1242.12 | 55.40% | **1.0** |
| All (last 24h, for comparability) | 164 | 850.35 | 49.85% | 0.8963 |
| Live (last 24h) | 17 | 1478.68 | 85.63% | **0.0** |
| Synthetic (last 24h) | 147 | 777.69 | 45.72% | **1.0** |
| All (last 72h) | 543 | 805.72 | 51.52% | 0.8913 |
| Live (last 72h) | 59 | 1597.03 | 87.10% | **0.0** |
| Synthetic (last 72h) | 484 | 709.26 | 47.18% | **1.0** |

Newest rows (all synthetic checkout, hourly): prediction ~875 vs observed 1718.92 (abs error ~844, pct ~49.1%, interval hit, resolved 05:41/06:41/07:41/08:41 UTC); 09:41 UTC observed 1753.81 (abs error 878.77, pct 50.11%); **10:41 UTC observed 3277.05** (abs error 2401.99, pct 73.30%, interval hit) — the observed value nearly doubled against the prior ~1719–1754 band, and it pulls the 4-row batch MAE to 1242.12. No live score resolved after FUT-046's probe, so the following batch carries no live accuracy claim on its own; the 24h/72h windows carry the claim and match FUT-046's shape (72h all n=543, live 59 vs 60, synthetic 484 vs 483 — the window slid and rows aged out).

Method note: "synthetic" here is all non-live-target rows, as in FUT-046/FUT-047 (24h all 164 − live 17 = synthetic 147; 72h all 543 − live 59 = synthetic 484). The 24h window holds 12 targets (checkout 25; 8 targets at 17 each; NIFTY/BTCUSDT/ETHUSDT at 1 each). An earlier census pass in this run used a checkout-only synthetic slice by mistake; the numbers above are the corrected re-run (probe 10:59:46Z, same census: 0 unscored, 1274 scores).

## 3. Last 3 scheduler cycles (forecast production)

Forecasts written per UTC hour (live store, `ForecastModel.as_of`, last 8h: 04:xx n=10, 05:xx n=3, 06:xx n=11, 07:xx n=11, 08:xx n=11, 09:xx n=11, 10:xx n=11):

- 08:xx UTC: 11 forecasts. 09:xx UTC: 11 forecasts. 10:xx UTC: 11 forecasts (incl. live `friday:fleet:forecast_demand_24h`).
- Journal: `forecast_refresh_job` (hourly) executed successfully 09:14:46 UTC and 10:10:52→10:16:31 UTC; `forecast_scoring_job` executed successfully 10:40:52 UTC (scored 0) and 10:41:03 UTC (scored 1).
- Verdict: last 3 cycles PASS for production (real forecasts each hour). The 05:xx cycle (n=3, truncated by the 05:10 UTC OOM kill) is already in FUT-047.

## 4. Fit-cost cap check

- Cap: `FUTURIS_FIT_MEMORY_BUDGET_MB=256` (resolved live this run via `resolve_fit_memory_budget(None)` → 256.0; `futuris/models/fit_cost.py`, TASK-FUT-017). Selection shortlists candidates against it and stamps `fit_cost_cap` when candidates drop (`futuris/models/selection.py`).
- Binding evidence: **zero** `fit_cost_cap` journal events since 2026-11-27 03:00 UTC — the cap has not bound in the checked window (same as FUT-045/FUT-046/FUT-047). Method note: the first `journalctl -g fit_cost_cap | wc -l` count in this run returned 1, which was journalctl's own `-- No entries --` line, not an event; a direct read of the matching entries confirms zero.
- OOM state: **no** OOM kill since 2026-11-28 06:00 UTC (same `-- No entries --` correction applies to the first count of 1). Today's kills remain the three already in FUT-045/FUT-047: 02:35, 04:09, 05:10 UTC. Service active/running, MainPID 63602 (unchanged since the 05:10 UTC restart; ActiveEnterTimestamp 2026-11-28 05:10:39 UTC, elapsed ~5h49m at probe), MemoryCurrent 335,724,544 bytes (~320M) vs MemoryMax 536,870,912 (512M). "Cap checked" still ≠ "cap proven to bind first"; the FUT-045 follow-up stands: instrument or reproduce a cap-binding fit before claiming the cap controls fit memory.

## 5. States

implemented N/A (evidence task) / tested YES (census + sweep + batch aggregates + cycle + journal checks run first-hand) / merged NO / deployed N/A / production-verified YES for the scoring-state, batch-accuracy, cycle and cap claims above (live store read through the service's own storage layer; no service change, no restart by this task).

— Muse 15, 2026-11-28
