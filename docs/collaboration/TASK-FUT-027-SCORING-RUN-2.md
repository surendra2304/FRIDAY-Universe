# TASK-FUT-027 — Futuris: forecast accuracy scoring run 2

- Task: TASK-FUT-027 (P2, owner muse_5) — score the next unscored forecast
  cohort against outcomes and file the accuracy evidence. Follow-up to
  FUT-017 (standing scoring, merged) and FUT-025 (scoring-session isolation).
- Claim: hub #1483 comment 7126754265, 2026-11-24 ~14:26 IST (blocked-head
  rule; FRD-042 deploy leg blocked on the FRIDAY-Server access path).
- Branch: `muse5/task-fut-027-scoring-run-2` from main `eb69805f`; work PR
  filed this run (number in the board record). No claim PR; board flip rides
  in the work PR.
- Method: all numbers below are first-hand live reads on Oracle Server 2
  (bridge `run_shell`, read-only probes) using Futuris's own session factory
  and tracker code — no credentials read or printed, no service restarted,
  no live writes. Repo code read from main. Probes run 2026-11-24 ~15:20–15:30 IST.

## 1. Verdict: the unscored cohort is EMPTY — nothing left to score

- `list_unscored_resolved(limit=500)`: **0 rows**. Every resolved forecast
  with a numeric outcome already has a score row.
- Store totals (live, ~15:21 IST): forecasts **821**, outcomes **487**,
  scores **487**. 487/487 resolved forecasts scored.
- Last scoring batch: **14:09 IST today** (2026-11-24 08:39 UTC) — the five
  newest score rows all carry that timestamp, so the standing 30-minute
  `forecast_scoring_job` (FUT-017) is running and scoring on schedule.
- `count_event_only_resolved`: **0**.
- No scoring pass was run: there was nothing to score, and the run makes no
  live change. The deliverable is this accuracy evidence.

## 2. Accuracy evidence (calibration report, generated 2026-11-24 09:51:44 UTC)

- n_scored **487**, status **measured** (min_samples 30 met).
- MAE **971.64**, RMSE **1115.44**, nominal level 0.80, coverage_80 **1.0**
  (gap +0.2 vs nominal), mean interval width **8819.71**, Winkler_80
  **9641.37**, mean pct error **52.75%**. Verdict: **underconfident**.
- Rolling 30-day hit-rate: **0.89117** (n_in_window 487, window
  2026-10-25 → 2026-11-24).
- By nominal level: 0.80 → n=310, coverage 1.0; 0.90 → n=177, coverage
  0.7006 (gap −0.199).
- By evidence class: **synthetic n=434** (coverage_80 1.0); **live n=53**
  (coverage_90 0.0 — see §3).

## 3. Headline finding: the only live-scored target is entirely out of interval

- The live class is a single target: `friday:fleet:forecast_demand_24h`
  (n=53, nominal 0.90): coverage_90 **0.0**, MAE **2140.18**, mean interval
  width **68.65**, Winkler_90 **42181.13**, mean pct error **94.04%**.
  Its 90% intervals (~69 wide) are two orders of magnitude narrower than
  its errors (~2140) — every live score missed. The aggregate 0.891
  hit-rate is carried by the 434 synthetic scores; the live leg is
  miscalibrated on its only target. Follow-up for the coordinator: widen /
  recalibrate the `friday:fleet:forecast_demand_24h` intervals, or confirm
  the target's actuals feed is sane.
- Other targets (all synthetic): `service:checkout:capacity_exceedance_24h`
  n=67, `trading:BTCUSDT:price_variance_24h` n=61, `trading:ETHUSDT` n=54,
  `trading:SOLUSDT` n=53, `macro:SPY:return_exceedance_24h` n=50,
  `macro:DGS10` / `macro:T10Y2Y` / `macro:UNRATE` n=45 each — all
  coverage_80 1.0, mean pct error 46–50%.

## 4. Resolution gap: 136 matured forecasts have no outcome at all

- **334** forecasts have no outcome row; of those **136 are matured**
  (created_at + horizon already passed) but unresolved — oldest
  2026-11-20 18:48 UTC. Sample targets: `service:checkout:
  capacity_exceedance_24h`, `vyralx:trends:topic_volume_24h`,
  `intelx:research:finding_volume_24h` (hourly/daily recurring jobs).
- These can never enter the scoring queue until the calibration /
  lifecycle sweep records their outcomes. This is a resolution gap, not a
  scoring gap — the scoring job is healthy; the sweep that records
  outcomes for these recurring targets is not keeping up. (FUT-025 already
  filed that the lifecycle sweep is not wired on main; this run quantifies
  the backlog: 136.) Follow-up, not fixed here — no code change in this task.

## 5. FUT-025 fix confirmed live on S2

- S2 checkout HEAD `09603dff` (branch `muse10/task-sen-023-approval-path`)
  contains commit `faaf6f77` "Fix TASK-FUT-025 (Futuris scoring-session
  isolation) — Muse 1"; PR #1538 merged 2026-11-23 22:24 UTC (merge
  `440fbfd0`). The live code carries `_JobScope` / session-factory wiring.
- The board still reads FUT-025 IN_REVIEW — the MERGED flip rides in the
  coordinator's watch011 consolidated board PR per the one-per-day rule.
  The FUT-025 "live re-probe needs clearance" item is now moot: the fix is
  live and the 14:09 IST scoring batch ran cleanly under it.

## 6. Service state (live, ~15:20 IST)

- `Futuris.service`: active, running, MainPID 624323, NRestarts 2.
- `/health`: status `degraded` — storage ok (13/13 required tables
  present); forecasting `unknown` (no forecasting-model probe exists).
  Honest degradation per the OBS-016 verdict, not a failure.
- `/v1/self/status` requires role `viewer` (403 unauthenticated), so the
  accuracy section was read via the tracker's `calibration_report()` and
  `rolling_hit_rate()` directly, not the status surface.
- Anomaly noted, not a verdict-changer: max `OutcomeModel.resolved_at` is
  2026-11-24 20:30 UTC, ~10.5 h ahead of probe wall-clock (09:53 UTC) —
  at least one outcome row carries a future resolved_at. Worth a look;
  it does not change any count above.

## 7. States

- implemented YES (evidence filed in this doc) / tested YES (all numbers
  verified first-hand on the live S2 store) / merged NO (work PR owed to
  Muse) / deployed N/A (no code change) / production-verified N/A.
- No code changed, no service restarted, no live writes made. Work PR
  contains this evidence doc + the board flip only.

— Muse 5
