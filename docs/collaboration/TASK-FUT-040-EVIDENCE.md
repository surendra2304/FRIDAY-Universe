# TASK-FUT-040 — Futuris: forecast accuracy scoring run 9

- Task: TASK-FUT-040 (P1, owner muse_13) — verify the last 3 scheduler cycles produced real forecasts AND score the oldest unscored forecasts against outcomes; file accuracy evidence. Follow-up to FUT-039 (run 8, IN_REVIEW, PR #2071) and FUT-035 (run 7, MERGED PR #1991).
- Claim: hub #2045 comment 7210858902, 2026-11-27 ~11:15 IST, on coordinator assignment WATCH205 §6 (hub 7210756025). Branch `muse13/task-fut-040-forecast-scoring-run-9` from main `3ce3fdef` (board PR #2079 merged). Board record is a held draft — the board is at the ~4.19 MB bridge ceiling and the record rides the post-shrink PR; per WATCH205 §6 the hub post is the assignment of record. This work PR carries the evidence doc only, no board hunk.
- Queue note: IG2-FRD-01/02-ACTIVATE-01 skipped — both still blocked (WhatsApp gateway unconfigured); FUT-040 is the head task per the blocked-head rule.

## 0. Gates re-probe (this run, ~11:20–11:25 IST)

- G1 Futuris.service: Server 1 — LoadState=not-found, ActiveState=inactive, SubState=dead. Server 2 — LoadState=not-found, ActiveState=inactive. UNCHANGED from FUT-039: the systemd live leg is NOT ARMED on either Oracle server.
- G2 DATABASE_URL: Server 2 has no `Futuris/.env` at all (0 DATABASE_URL lines) — S2 live leg still NOT ARMED.
- Working route (unchanged, per FUT-033/035/039 method): FRIDAY-Server (bridge server 3) run_shell, Futuris's own session factory + tracker code, `Futuris/.env` present (1 DATABASE_URL line). The run_shell grant stands (owner ruling 7192682851, correction 7197725825; clearance 7200564540; reaffirmed settled by WATCH189 §3 and WATCH205 §6).
- Code verification (first-hand): the 4 probe files hash identically on server 3 and on main `3ce3fdef` — `db.py 4d945dcd…`, `score_repository.py 39ed9216…`, `models.py 16794c0f…`, `forecast_tracker.py 2b429615…` (same as the run-5/7/8 verified hashes). Probe script `/tmp/fut036_probe.py` sha256 `d017df1b…` — identical to the run-5/7/8 verified script; read first-hand before running (read-only except the idempotent sweep, which fires only on a non-empty queue). Server-3 checkout HEAD `cb57c8c8`, branch `main`, `futuris` working tree clean. Cycles-listing script `/tmp/fut040_cycles.py` (read-only, this run) — same session factory, 5 newest + 3h count + distinct as_of values.
- Bridge transport healthy this run (4 consecutive run_shell calls + 2 read_text calls, no failures).

## 1. Verdict: the unscored cohort is EMPTY — nothing left to score

- `list_unscored_resolved(limit=500)`: **0 rows**. Every resolved forecast with a numeric outcome already has a score row.
- Store totals (live, probe 2026-11-27T05:51:22Z / 11:21:22 IST): forecasts **1597**, outcomes **1082**, scores **1082**. 1082/1082 resolved forecasts scored.
- `count_event_only_resolved`: **0**.
- Last scoring batch: **05:03:35 UTC** today — the standing 30-minute `forecast_scoring_job` (FUT-017) scored at 05:03; no new score rows since, consistent with an empty unscored queue (the 05:33 forecasts below are unresolved by design, not a scoring gap — nothing was there for the 05:33 cycle to score).
- No scoring pass ran and no live writes were made: there was nothing to score, and the run makes no live change. The deliverable is this accuracy evidence.

## 2. Scheduler cycles: the last 3 cycles produced real forecasts

- Forecasts 1586 → 1597 since run 8 (probe 2026-11-27T04:49:55Z / 10:19:55 IST): **+11 new forecasts in ~62 minutes**.
- 5 newest forecasts (probed 05:53:09 UTC / 11:23:09 IST — the listing run 8 owed), all `as_of` 05:33 UTC today:
  - `04fc5336-8385-461b-8313-c9b7688a034a` — `friday:fleet:forecast_demand_24h` — 05:33:11
  - `b8f6f5aa-f7d3-43fb-9f2c-83114fdb7bdc` — `intelx:research:finding_volume_24h` — 05:33:05
  - `9c3af24b-c571-455b-a735-21f384a3076b` — `service:checkout:capacity_exceedance_24h` — 05:33:01
  - `d65506d6-ee43-4dbe-8dd9-168de17c4f0c` — `macro:SPY:return_exceedance_24h` — 05:33:01
  - `9d9a8b02-fdcf-49b1-8969-021ee3472ec5` — `macro:T10Y2Y:curve_inversion_30d` — 05:33:01
- **36 forecasts with `as_of` in the last 3 hours** — covering the 03:33, 04:33 and 05:33 production cycles. Distinct recent `as_of` values: 05:33 (4 distinct) + 04:33 (2 distinct) at the head of the list. The pipeline is producing real forecasts on schedule.
- Outcomes/scores 1073 → 1082 (+9) in the same window; last_scored_at 05:03:35 UTC.

## 3. Accuracy evidence (calibration report, generated 2026-11-27T05:51:22Z)

- n_scored **1082**, status **measured** (min_samples 30 met).
- MAE **878.89**, RMSE **1012.11**, nominal level 0.80, coverage_80 **1.0** (gap +0.2 vs nominal), mean interval width **8513.01**, Winkler_80 **9676.46**, mean pct error **50.85%**. Verdict: **underconfident**.
- Rolling 30-day hit-rate: **0.890943** (n_in_window 1082, window 2026-10-28 → 2026-11-27).
- By nominal level: 0.80 → n=776, coverage 1.0; 0.90 → n=306, coverage_90 0.614379 (gap −0.286).
- By target (n): `service:checkout:capacity_exceedance_24h` 131, `trading:BTCUSDT:price_variance_24h` 125, `friday:fleet:forecast_demand_24h` 118, `trading:ETHUSDT:price_variance_24h` 118, `trading:SOLUSDT:price_variance_24h` 117, `macro:SPY:return_exceedance_24h` 114, `macro:DGS10:yield_shift_30d` 109, `macro:T10Y2Y:curve_inversion_30d` 109, `macro:UNRATE:unemployment_drift_90d` 109, `BTCUSDT` 9, `NIFTY` 9, `ETHUSDT` 8, `my portfolio` 4, `fleet:api:request_rate` 1, `what should i watch in indian markets` 1. Total 1082.
- Change since run 8 (10:19 IST today): +11 forecasts (1586→1597), +9 outcomes/scores (1073→1082); MAE 877.10→878.89, RMSE 1011.32→1012.11, hit-rate 0.89096→0.890943.

## 4. Headline finding: the only live-scored target is entirely out of interval

- The live class is a single target: `friday:fleet:forecast_demand_24h` (n=118, was 117 in run 8, 103 in run 7, nominal 0.90): coverage_90 **0.0**, MAE **1986.70**, RMSE **2003.24**, mean interval width **93.93**, Winkler_90 **38886.52**, mean pct error **91.36%**. Verdict: **overconfident**.
- Its 90% intervals (~94 wide) are ~21x narrower than its errors (~1987) — all 118 live scores missed. The aggregate 0.891 hit-rate is carried by the synthetic scores; the live leg is miscalibrated on its only target. Follow-up for the coordinator (carried from runs 2–3, 5, 7, 8, still open): widen / recalibrate the `friday:fleet:forecast_demand_24h` intervals, or confirm the target's actuals feed is sane.

## 5. Resolution gap: 253 matured forecasts have no outcome at all (was 251)

- **515** forecasts have no outcome row (was 513); of those **253 are matured** (expires_at already passed) but unresolved — oldest 2026-11-20 18:48 UTC (`service:checkout:capacity_exceedance_24h`, forecast `1140e21f-8bab-4584-afa4-eacd5157f5a8`) — the same oldest row as runs 3, 7 and 8, so the backlog is growing, not resolving.
- By target: `intelx:research:finding_volume_24h` **118**, `vyralx:trends:topic_volume_24h` **116** (the two hourly recurring jobs are 234 of 253), `service:checkout:capacity_exceedance_24h` 2, plus 17 singletons across other targets.
- These can never enter the scoring queue until the outcome-recording sweep records their outcomes. This is a resolution gap, not a scoring gap — the scoring job is healthy; the sweep that records outcomes for these recurring targets is not keeping up. (FUT-025 already filed that the lifecycle sweep is not wired on main; this run quantifies the backlog: 253, +2 since run 8.) Follow-up, not fixed here — no code change in this task.

## 6. Data-quality anomaly: 8 rows carry a future resolved_at (unchanged from run 8)

- `future_resolved_at`: **8**. Run 8 reported 8 (was 0 in run 7); no new future-dated outcome rows appeared since run 8. Flagged for the coordinator; not investigated further in this run (read-only probe; no live change).

## 7. Service state (carried from runs 7/8, not re-checked this run)

- Server-6 Futuris process / `/health` not re-checked this run — the probe scope was the store route (bridge server 3); the Oracle systemd leg is down per §0. Carried: uvicorn `futuris.api.app` on port 8004, PID 35287 since 2026-11-26 06:32 UTC; `/health` degraded, storage ok 13/13.
- FUT-032 note stands: its scoring leg was blocked on S2 `Futuris/.env` missing / no DATABASE_URL. This run's route (FRIDAY-Server, server 3: `Futuris/.env` present, tracker code byte-identical to main) works; the S2 route remains untested.

## 8. States

- implemented YES (evidence filed in this doc) / tested YES (all numbers first-hand live reads, plus the conditional sweep armed and correctly not fired) / merged NO (work PR open, awaiting Muse) / deployed N/A (no code change; no live change made) / production-verified N/A (the scoring job is already running on server 6; verified by fresh rows, not by this task).

— Muse 13
