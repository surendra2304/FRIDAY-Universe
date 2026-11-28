# TASK-FUT-045 — Futuris forecast quality: next unscored batch + fit-cost cap check

**Owner:** Muse 7 · **Date:** 2026-11-28 · **Service:** Futuris on IntelX-Server (bridge server 6, PID 60746, port 8004) · **Claim:** hub 7232952679 (BE 08:50 §B assignment)

## Verdict

The unscored queue is empty: the scheduler's own 30-minute scoring job keeps it drained, so the "next batch" is the newest resolved batch, scored by the service itself and re-verified here. That batch (last 24h, n=213) repeats the FUT-016 pattern exactly: 190 synthetic scores with interval hit rate 1.0 (vacuously wide intervals) and 23 live fleet-demand scores with hit rate 0.0 (prediction ~269 vs actuals ~1750, mean pct error 85.7%). The fit-cost cap is live at 256 MB (`FUTURIS_FIT_MEMORY_BUDGET_MB`, half the 512M MemoryMax backstop) and did not bind in the checked window — zero `fit_cost_cap` events — but the 02:35 UTC OOM kill (512.2M peak) shows fit-storm memory still reaches the backstop, so the cap is not yet proven to bind before it.

## 1. Scoring sweep (this run)

Method: `scripts/run_forecast_tracker.py --score` on IntelX-Server (venv312, service storage layer, Oracle store), 2026-11-28 ~08:50 IST.

- Census before sweep (`list_unscored_resolved`, oldest-first): **0 unscored**.
- Sweep result: `considered 0, scored 0, skipped_no_numeric_actual 0, skipped_duplicate 0, event_only_resolved 0`.
- Tracker report before sweep: n_scored 1266, verdict "underconfident", coverage_80 1.0, MAE 875.95 — the synthetic bulk dominates the headline, as in FUT-016.
- Scheduler state: `forecast_scoring_job` executed successfully 03:06:11 UTC (journal, PID 59466 pre-restart); service restarted 03:07:44 UTC (PID 60746, FUT-043 redeploy), refresh/ingest/risk jobs executing successfully after restart.

Coordination note: TASK-FUT-044 (Muse TP11) owns the oldest batch; with the queue at 0 there is no unscored oldest batch to contest — both tasks report on scheduler-scored batches, FUT-045 on the newest 24h batch below.

## 2. Next batch accuracy (resolved in last 24h, n=213)

| Scope | n | MAE | Mean pct err | Interval hit rate |
|---|---|---|---|---|
| All | 213 | 835.50 | 49.27% | 0.892 |
| Live (`friday:fleet:forecast_demand_24h`) | 23 | 1475.22 | 85.66% | **0.0** |
| Synthetic (7 subscription targets + checkout) | 190 | 758.06 | 44.87% | **1.0** |

Newest rows (resolved 2026-11-28 02:33–03:06 UTC): all seven synthetic targets share prediction 875.05 / abs error 895.90 / interval hit — one synthetic series under seven labels, unchanged from FUT-016 (`FUTURIS_TELEMETRY_SOURCE=synthetic` confirmed live). Newest live rows: prediction 268.59, abs error 1484.78 / 1502.36, pct error ~84.7–84.8%, interval miss. 72h window (n=500) is the same shape: live hit rate 0.0 (n=55), synthetic 1.0 (n=445).

## 3. Fit-cost cap check

- Cap: `FUTURIS_FIT_MEMORY_BUDGET_MB=256` (live settings read this run; `futuris/infra/config.py:150-162`, TASK-FUT-017). `resolve_fit_memory_budget` returns the configured 256 MB; selection shortlists candidates against it and stamps `fit_cost_cap` when candidates drop (`futuris/models/selection.py:129-147`).
- Binding evidence: **zero** `fit_cost_cap` journal events since 2026-11-27 03:00 UTC — the cap has not bound in the checked window.
- Counter-evidence: the service was OOM-killed 02:35 UTC today at 512.2M peak vs the 512M MemoryMax (TP14, hub 7232898215) — fit memory reached the backstop without a recorded cap event, so "cap checked" ≠ "cap proven to bind first". Named follow-up for the coordinator: instrument or reproduce a cap-binding fit before claiming the cap controls fit-storm memory.

## 4. States

implemented N/A (evidence task) / tested YES (sweep + census + batch aggregates run first-hand) / merged NO / deployed N/A / production-verified YES for the scoring-state and batch-accuracy claims above (live store read through the service's own storage layer; no service change, no restart by this task).

— Muse 7, 2026-11-28
