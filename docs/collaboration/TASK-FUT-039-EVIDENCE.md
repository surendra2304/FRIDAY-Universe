# TASK-FUT-039 — Futuris: forecast accuracy scoring run 8

- Task: TASK-FUT-039 (P1, owner muse_10) — verify the last 3 scheduler cycles produced real forecasts AND score the oldest unscored forecasts against outcomes; file accuracy evidence. Follow-up to FUT-035 (run 7, cohort empty) and FUT-033 (run 5).
- Claim: hub #2045 comment 7210162326, 2026-11-27 ~10:22 IST, on coordinator assignment WATCH201 §2 top-up (hub 7209660625), board PR #2063 merged. Branch `muse10/task-fut-039-accuracy-scoring-run-8` from main `c334f212` (board PR #2069 merged 10:19 IST); board flip rides in the next coordinator board PR (coordinator-only flip rule 7200564540) — this work PR carries the evidence doc only, no board hunk.
- Predecessor: TASK-FUT-020 checkpoint 2 complete — work PR #2057 MERGED 09:57 IST (merged by Surendra).

## 0. Gates re-probe (this run, ~10:06–10:20 IST)

- G1 Futuris.service: Server 1 — masked, inactive (dead) via oracle_check_service. Server 2 — LoadState=not-found, ActiveState=inactive via run_shell. UNCHANGED from FUT-020 cp2: the systemd live leg is NOT ARMED on either Oracle server.
- G2 DATABASE_URL: Server 2 `/opt/friday_universe/.env` — 0 lines (unchanged); `FRIDAY/.env` missing. The S2 route remains unusable for Futuris probes.
- G3 scheduler tests: not re-run this run (same RuntimeError as FUT-020 cp2; the store route below is the working leg).
- Working route (unchanged, per FUT-033/035 method): FRIDAY-Server (bridge server 3) run_shell, Futuris's own session factory + tracker code, `Futuris/.env` present (1 DATABASE_URL line). The run_shell grant stands (owner ruling 7192682851, correction 7197725825; clearance 7200564540). Both Oracle servers ONLINE (get_system_info, this run). Server-3 checkout HEAD `cb57c8c8`, branch `main`, `Futuris/futuris` working tree clean.
- Code verification (first-hand): the 4 probe files hash identically on server 3 and on main `99e5fe1` — `db.py 4d945dcd…`, `score_repository.py 39ed9216…`, `models.py 16794c0f…`, `forecast_tracker.py 2b429615…` (same as the run-5 verified hashes). Probe script `/tmp/fut036_probe.py` sha256 `d017df1b…` — identical to the run-5/7/8 verified script. The first probe attempt failed only because it ran from `/opt/friday_universe` (whose `.env` has 0 DATABASE_URL lines); re-ran from `/opt/friday_universe/Futuris` per the script header and succeeded.
- Bridge transport flaky this run: get_system_info failed once then succeeded on retry; the cycles-listing probe failed 3x in a row ("MCP request did not complete") after the main probe — the 5-newest-forecast listing is owed as a follow-up, not blocking this evidence.

## 1. Verdict: the unscored cohort is EMPTY — nothing left to score

- `list_unscored_resolved(limit=500)`: **0 rows**. Every resolved forecast with a numeric outcome already has a score row.
- Store totals (live, probe 2026-11-27T04:49:55Z / 10:19:55 IST): forecasts **1586**, outcomes **1073**, scores **1073**. 1073/1073 resolved forecasts scored.
- `count_event_only_resolved`: **0**.
- Last scoring batch: **04:33:16 UTC** today (~17 min before the probe) — the standing 30-minute `forecast_scoring_job` (FUT-017) is running and scoring on schedule.
- No scoring pass ran and no live writes were made: there was nothing to score, and the run makes no live change. The deliverable is this accuracy evidence.

## 2. Scheduler cycles: recent cycles produced real forecasts

- Forecasts 1561 → 1586 since run 5 (probe 2026-11-27 03:16:50 UTC / 08:46:50 IST): **+25 new forecasts in ~93 minutes**, across the 30-minute scoring cycles and the hourly recurring jobs — the pipeline is producing real forecasts.
- Outcomes/scores 1061 → 1073 (+12) in the same window; last_scored_at 04:33:16 UTC.
- Owed: the 5-newest-forecast listing (bridge transport failed 3x after the main probe; retry next run).

## 3. Accuracy evidence (calibration report, generated 2026-11-27T04:49:55Z)

- n_scored **1073**, status **measured** (min_samples 30 met).
- MAE **877.10**, RMSE **1011.32**, nominal level 0.80, coverage_80 **1.0** (gap +0.2 vs nominal), mean interval width **8553.54**, Winkler_80 **9734.28**, mean pct error **50.75%**. Verdict: **underconfident**.
- Rolling 30-day hit-rate: **0.89096** (n_in_window 1073, window 2026-10-28 → 2026-11-27).
- By nominal level: 0.80 → n=768, coverage 1.0; 0.90 → n=305, coverage_90 0.616393 (gap −0.284).
- By target (n): `friday:fleet:forecast_demand_24h` 117, `service:checkout:capacity_exceedance_24h` 130, `trading:BTCUSDT:price_variance_24h` 124, `trading:ETHUSDT:price_variance_24h` 117, `trading:SOLUSDT:price_variance_24h` 116, `macro:SPY:return_exceedance_24h` 113, `macro:DGS10:yield_shift_30d` 108, `macro:T10Y2Y:curve_inversion_30d` 108, `macro:UNRATE:unemployment_drift_90d` 108, `BTCUSDT` 9, `NIFTY` 9, `ETHUSDT` 8, `my portfolio` 4, `fleet:api:request_rate` 1, `what should i watch in indian markets` 1. Total 1073.
- Change since run 5 (08:46 IST today): +25 forecasts (1561→1586), +12 outcomes/scores (1061→1073); MAE 878.54→877.10, RMSE 1013.63→1011.32, hit-rate 0.890669→0.89096.

## 4. Headline finding: the only live-scored target is entirely out of interval

- The live class is a single target: `friday:fleet:forecast_demand_24h` (n=117, was 103 in run 7, 116 in run 5, nominal 0.90): coverage_90 **0.0**, MAE **1990.93**, RMSE **2007.05**, mean interval width **93.65**, Winkler_90 **38973.59**, mean pct error **91.41%**. Verdict: **overconfident**.
- Its 90% intervals (~94 wide) are ~21x narrower than its errors (~1991) — all 117 live scores missed. The aggregate 0.891 hit-rate is carried by the synthetic scores; the live leg is miscalibrated on its only target. Follow-up for the coordinator (carried from runs 2–3, 5, 7, still open): widen / recalibrate the `friday:fleet:forecast_demand_24h` intervals, or confirm the target's actuals feed is sane.

## 5. Resolution gap: 251 matured forecasts have no outcome at all (was 223)

- **513** forecasts have no outcome row (was 455); of those **251 are matured** (expires_at already passed) but unresolved — oldest 2026-11-20 18:48 UTC (`service:checkout:capacity_exceedance_24h`, forecast `1140e21f-8bab-4584-afa4-eacd5157f5a8`) — the same oldest row as runs 3 and 7, so the backlog is growing, not resolving.
- By target: `intelx:research:finding_volume_24h` **117**, `vyralx:trends:topic_volume_24h` **115** (the two hourly recurring jobs are 232 of 251), `service:checkout:capacity_exceedance_24h` 2, plus singletons across other targets.
- These can never enter the scoring queue until the outcome-recording sweep records their outcomes. This is a resolution gap, not a scoring gap — the scoring job is healthy; the sweep that records outcomes for these recurring targets is not keeping up. (FUT-025 already filed that the lifecycle sweep is not wired on main; this run quantifies the backlog: 251, +28 since run 7.) Follow-up, not fixed here — no code change in this task.

## 6. New anomaly: 8 rows carry a future resolved_at (was 0 in run 7)

- `future_resolved_at`: **8**. Run 7 reported 0 rows in the future at probe time (the run-2 anomaly had stayed gone); 8 future-dated outcome rows have appeared since. Flagged for the coordinator; not investigated further in this run (read-only probe; no live change).

## 7. Service state (live, ~10:20 IST)

- Server-6 Futuris process / `/health` not re-checked this run (bridge transport flaky after the main probe; Oracle systemd leg down per §0). Carried from runs 7/8: uvicorn `futuris.api.app` on port 8004, PID 35287 since 2026-11-26 06:32 UTC; `/health` degraded, storage ok 13/13.
- FUT-032 note stands: its scoring leg was blocked on S2 `Futuris/.env` missing / no DATABASE_URL. This run's route (FRIDAY-Server, server 3: `Futuris/.env` present, tracker code byte-identical to main) works; the S2 route remains untested.

## 8. States

- implemented YES (evidence filed in this doc) / tested YES (all numbers first-hand live reads, plus the conditional sweep armed and correctly not fired) / merged NO (work PR open, awaiting Muse) / deployed N/A (no code change; no live change made) / production-verified N/A (the scoring job is already running on server 6; verified by fresh rows, not by this task).

— Muse 10
