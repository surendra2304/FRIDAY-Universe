# TASK-FUT-041 — Futuris: forecast accuracy scoring run 10

- Task: TASK-FUT-041 (P2, owner muse_14) — verify the last 3 scheduler cycles produced real forecasts AND score the oldest unscored forecasts against outcomes; file accuracy evidence. Follow-up to FUT-040 (run 9, IN_REVIEW, PR #2071) and FUT-039 (run 8) and FUT-035 (run 7, MERGED PR #1991).
- Claim: hub #2045 comment 7216688690, 2026-11-27 ~16:36 IST, on coordinator assignment WATCH217 §3 (hub 7216667333) — queue REL-117 → FUT-041 → INT-046-FIX-01, REL-117 COMPLETE. Branch `muse14/task-fut-041` from main `94e6ee48`. Board flip rides in the next coordinator board PR (coordinator-only flip rule) — this evidence PR carries the evidence doc only, no board hunk.

## 0. Gates re-probe (this run, ~16:37–16:42 IST)

- G1 Futuris.service: Oracle Server 1 and Server 2 — not re-checked this run (unchanged from FUT-039/040: the systemd live leg is NOT ARMED on either Oracle server; Futuris.service LoadState=not-found). The Oracle systemd leg is not the working route.
- G2 DATABASE_URL: FRIDAY-Server (bridge server 3) `Futuris/.env` present (1 DATABASE_URL line) — the store route is ARMED.
- Working route (unchanged, per FUT-033/035/039/040 method): FRIDAY-Server (bridge server 3) run_shell, Futuris's own session factory + tracker code, `Futuris/.env` present. The run_shell grant stands (owner ruling 7192682851, correction 7197725825; clearance 7200564540; reaffirmed settled by WATCH189 §3 and WATCH205 §6).
- Live scheduler route (board record): the Futuris scheduler is live on IntelX-Server (32.236.185.237:8004) — verified first-hand this run (§7 below): `/ready` returns ready with database connected (Oracle); `/health` returns degraded with storage ok 13/13. The store probe (server 3) reads the same Oracle DB the IntelX-Server scheduler writes to.
- Code verification (first-hand): the 4 probe files hash identically on server 3 and on main `94e6ee48` — `db.py 4d945dcd…`, `score_repository.py 39ed9216…`, `models.py 16794c0f…`, `forecast_tracker.py 2b429615…` (same as the run-5/7/8/9 verified hashes). Probe script `/tmp/fut036_probe.py` sha256 `d017df1b…` — identical to the run-5/7/8/9 verified script; read first-hand before running (read-only except the idempotent sweep, which fires only on a non-empty queue). Cycles-listing script `/tmp/fut040_cycles.py` sha256 `48bee79c…` — read first-hand before running (read-only). Cycle-0833 verification script `/tmp/fut041_cycle0833.py` sha256 `efa94e8c…` — written this run, read-only, read back before running. Server-3 checkout HEAD `06ff9ee6`, branch `main`.
- Bridge transport healthy this run (7 consecutive run_shell calls, no failures).

## 1. Verdict: PASS — the unscored cohort is EMPTY (nothing left to score) and the last 3 scheduler cycles produced real forecasts

- `list_unscored_resolved(limit=500)`: **0 rows**. Every resolved forecast with a numeric outcome already has a score row.
- Store totals (live, probe 2026-11-27T11:10:28Z / 16:40:28 IST): forecasts **1652**, outcomes **1127**, scores **1127**. 1127/1127 resolved forecasts scored.
- `count_event_only_resolved`: **0**.
- Last scoring batch: **11:03:35 UTC** today — the standing 30-minute `forecast_scoring_job` (FUT-017) scored at 11:03; no new score rows since, consistent with an empty unscored queue (the 10:33 forecasts below are unresolved by design, not a scoring gap — nothing was there for the 11:03 cycle to score beyond what it already scored).
- No scoring pass ran and no live writes were made: there was nothing to score, and the run makes no live change. The deliverable is this accuracy evidence.

## 2. Scheduler cycles: the last 3 cycles produced real forecasts

- Forecasts 1597 → 1652 since run 9 (probe 2026-11-27T05:51:22Z / 11:21:22 IST): **+55 new forecasts in ~5h19m**.
- 5 newest forecasts (probed 11:10:53 UTC / 16:40:53 IST), all `as_of` 10:33 UTC today:
  - `f98c192e-0e41-4d8b-b2d1-e90fcff7bbab` — `friday:fleet:forecast_demand_24h` — 10:33:11
  - `fb6af1f4-edcb-4220-870e-0a2cc05a0dc4` — `intelx:research:finding_volume_24h` — 10:33:05
  - `3bbba55b-c2a9-4912-9e9d-7ff993772339` — `macro:T10Y2Y:curve_inversion_30d` — 10:33:01
  - `fd145f2e-b9fa-4269-a88c-6e969543f53e` — `macro:DGS10:yield_shift_30d` — 10:33:01
  - `17749fcc-e7ad-4104-96c2-0a8a5c2c9c7c` — `trading:ETHUSDT:price_variance_24h` — 10:33:01
- **33 forecasts with `as_of` in the last 3 hours** — covering the 08:33, 09:33 and 10:33 production cycles. Distinct recent `as_of` values: 10:33 (4 distinct) + 09:33 (2 distinct) at the head of the list.
- 08:33 cycle verified explicitly (this run, probed 11:11:37 UTC): **11 forecasts** with `as_of` in the 08:33 minute, including `d3888b96-1701-45ab-bdb9-889d93dd7ac4` (`friday:fleet:forecast_demand_24h`, 08:33:14), `ec215923-43c5-45c4-a23d-f0e1f901ba3d` (`intelx:research:finding_volume_24h`, 08:33:10), `09bcc3c9-ffbe-414f-ba65-63f2e0e6fc04` (`service:checkout:capacity_exceedance_24h`, 08:33:01). The pipeline is producing real forecasts on schedule.
- Outcomes/scores 1082 → 1127 (+45) in the same window; last_scored_at 11:03:35 UTC.

## 3. Accuracy evidence (calibration report, generated 2026-11-27T11:10:28Z)

- n_scored **1127**, status **measured** (min_samples 30 met).
- MAE **875.01**, RMSE **1005.20**, nominal level 0.80, coverage_80 **1.0** (gap +0.2 vs nominal), mean interval width **8465.98**, Winkler_80 **9605.86**, mean pct error **50.64%**. Verdict: **underconfident**.
- Rolling 30-day hit-rate: **0.890861** (n_in_window 1127, window 2026-10-28 → 2026-11-27).
- By nominal level: 0.80 → n=816, coverage 1.0; 0.90 → n=311, coverage_90 0.604502 (gap −0.295).
- By target (n): `service:checkout:capacity_exceedance_24h` 136, `trading:BTCUSDT:price_variance_24h` 130, `friday:fleet:forecast_demand_24h` 123, `trading:ETHUSDT:price_variance_24h` 123, `trading:SOLUSDT:price_variance_24h` 122, `macro:SPY:return_exceedance_24h` 119, `macro:DGS10:yield_shift_30d` 114, `macro:T10Y2Y:curve_inversion_30d` 114, `macro:UNRATE:unemployment_drift_90d` 114, `BTCUSDT` 9, `NIFTY` 9, `ETHUSDT` 8, `my portfolio` 4, `fleet:api:request_rate` 1, `what should i watch in indian markets` 1. Total 1127.
- Change since run 9 (11:21 IST today): +55 forecasts (1597→1652), +45 outcomes/scores (1082→1127); MAE 878.89→875.01, RMSE 1012.11→1005.20, hit-rate 0.890943→0.890861.

## 4. Headline finding: the only live-scored target is entirely out of interval

- The live class is a single target: `friday:fleet:forecast_demand_24h` (n=123, was 118 in run 9, 117 in run 8, 103 in run 7, nominal 0.90): coverage_90 **0.0**, MAE **1965.43**, RMSE **1984.17**, mean interval width **95.26**, Winkler_90 **38449.33**, mean pct error **91.13%**. Verdict: **overconfident**.
- Its 90% intervals (~95 wide) are ~21x narrower than its errors (~1965) — all 123 live scores missed. The aggregate 0.891 hit-rate is carried by the synthetic scores; the live leg is miscalibrated on its only target. Follow-up for the coordinator (carried from runs 2–3, 5, 7, 8, 9, still open): widen / recalibrate the `friday:fleet:forecast_demand_24h` intervals, or confirm the target's actuals feed is sane.

## 5. Resolution gap: 263 matured forecasts have no outcome at all (was 253)

- **525** forecasts have no outcome row (was 515); of those **263 are matured** (expires_at already passed) but unresolved — oldest 2026-11-20 18:48 UTC (`service:checkout:capacity_exceedance_24h`, forecast `1140e21f-8bab-4584-afa4-eacd5157f5a8`) — the same oldest row as runs 3, 7, 8 and 9, so the backlog is growing, not resolving.
- By target: `intelx:research:finding_volume_24h` **123**, `vyralx:trends:topic_volume_24h` **121** (the two hourly recurring jobs are 244 of 263), `service:checkout:capacity_exceedance_24h` 2, plus 17 singletons across other targets.
- These can never enter the scoring queue until the outcome-recording sweep records their outcomes. This is a resolution gap, not a scoring gap — the scoring job is healthy; the sweep that records outcomes for these recurring targets is not keeping up. (FUT-025 already filed that the lifecycle sweep is not wired on main; this run quantifies the backlog: 263, +10 since run 9.) Follow-up, not fixed here — no code change in this task.

## 6. Data-quality anomaly: 8 rows carry a future resolved_at (unchanged from runs 8 and 9)

- `future_resolved_at`: **8**. Run 8 reported 8 (was 0 in run 7); run 9 reported 8; no new future-dated outcome rows appeared since run 9. Flagged for the coordinator; not investigated further in this run (read-only probe; no live change).

## 7. Service state (live, this run)

- Live Futuris scheduler on IntelX-Server (32.236.185.237:8004), probed first-hand 2026-11-27T11:12:08–11:12:23Z / 16:42:08–16:42:23 IST:
  - `/ready`: status **ready**, service futuris, database **connected**, database_backend **oracle**, version 2.0.0, observed_at 2026-11-27T11:12:13Z.
  - `/health`: status **degraded**, service futuris, version 2.0.0, observed_at 2026-11-27T11:12:23Z; capabilities.storage **ok** (live schema inspection: 13/13 required tables present); capabilities.forecasting **unknown** (NO_MODEL_PROBE — no forecasting-model probe exists; storage readiness is not forecasting ability); dependencies.database **ok** (live round-trip + all required tables present); storage ready true, expected 13, present 13, missing [], error null.
  - The "degraded" is the known state (same as runs 7/8/9 carried): the forecasting capability has no model probe, so it reports unknown. The database is connected and the storage is ready. The scheduler is producing real forecasts on schedule (§2), which is the live proof that matters for this task.
- FUT-032 note stands: its scoring leg was blocked on S2 `Futuris/.env` missing / no DATABASE_URL. This run's route (FRIDAY-Server, server 3: `Futuris/.env` present, tracker code byte-identical to main) works; the S2 route remains untested.

## 8. States

- implemented YES (evidence filed in this doc) / tested YES (all numbers first-hand live reads; the conditional sweep was armed and correctly did not fire — the unscored queue is empty) / merged NO (evidence PR open, awaiting Muse) / deployed N/A (no code change; no live change made) / production-verified YES (the live scheduler on IntelX-Server produced real forecasts in the last 3 cycles, verified first-hand; the scoring job is running on schedule, verified by fresh rows).

— Muse 14
