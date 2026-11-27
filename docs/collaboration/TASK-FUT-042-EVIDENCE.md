# TASK-FUT-042 — Futuris: forecast accuracy scoring run 10

- Task: TASK-FUT-042 (P1, owner muse_tp14) — verify the last 3 scheduler cycles produced real forecasts AND score the oldest unscored forecasts against outcomes; file accuracy evidence. Follow-up to FUT-038 (run 9 per board title) and FUT-041 (run 9 evidence, PR #2071-era; note: the FUT-041 evidence doc is also titled "run 10" — a numbering collision on the board; this run files as run 10 per the TASK-FUT-042 board title and flags the collision for the coordinator).
- Claim: hub #2045 comment 7227047739, 2026-11-28 ~01:25 IST, on coordinator assignment WATCH237 §C / WATCH236 §G. Branch `musetp14/task-fut-042-forecast-accuracy-scoring-run-10` from main `c516895c`, fast-forwarded to main `99cbcbf7` before filing (zero prior commits). Board flip rides in the next coordinator board PR (coordinator-only flip rule) — this evidence PR carries the evidence doc only, no board hunk.

## 0. Gates re-probe (this run, ~02:30–02:32 IST)

- G1 Futuris.service: Oracle Server 1 and Server 2 — not re-checked this run (unchanged from FUT-039/040/041: the systemd live leg is NOT ARMED on either Oracle server; Futuris.service LoadState=not-found). The Oracle systemd leg is not the working route.
- G2 DATABASE_URL: <redacted>
- Working route (unchanged, per FUT-033/035/039/040/041 method): FRIDAY-Server (bridge server 3) run_shell, Futuris's own session factory + tracker code, `Futuris/.env` present. The run_shell grant stands (owner ruling 7192682851, correction 7197725825; clearance 7200564540; reaffirmed settled by WATCH189 §3 and WATCH205 §6).
- Live scheduler route (board record): the Futuris scheduler is live on IntelX-Server (32.236.185.237:8004) — verified first-hand this run (§7 below): `/ready` returns ready with database connected (Oracle); `/health` returns degraded with storage ok 13/13. The store probe (server 3) reads the same Oracle DB the IntelX-Server scheduler writes to.
- Code verification (first-hand): the 4 probe files hash identically on server 3 and on main — `db.py 4d945dcd…`, `score_repository.py 39ed9216…`, `models.py 16794c0f…`, `forecast_tracker.py 2b429615…` (same as the run-5/7/8/9 verified hashes). Probe script `/tmp/fut036_probe.py` sha256 `d017df1b…` — identical to the run-5/7/8/9 verified script; read first-hand before running (read-only except the idempotent sweep, which fires only on a non-empty queue). Cycles-listing script `/tmp/fut040_cycles.py` sha256 `48bee79c…` — read first-hand before running (read-only). Cycle-1833 verification script `/tmp/fut042_cycle1833.py` sha256 `0a06bfd8…` (after a one-character `=` → `==` fix, re-read before running) — written this run, read-only. Server-3 checkout HEAD `06ff9ee6`, branch `main`.
- Bridge transport healthy this run (consecutive run_shell calls, one transient JSON-escaping failure on the client side only — no server-side effect; re-sent and completed).

## 1. Verdict: PASS — the unscored cohort is EMPTY (nothing left to score) and the last 3 scheduler cycles produced real forecasts

- `list_unscored_resolved(limit=500)`: **0 rows**. Every resolved forecast with a numeric outcome already has a score row.
- Store totals (live, probe 2026-11-27T21:01:13Z / 02:31:13 IST): forecasts **1761**, outcomes **1211**, scores **1211**. 1211/1211 resolved forecasts scored.
- `count_event_only_resolved`: **0**.
- Last scoring batch: **20:03:10 UTC** today — the standing 30-minute `forecast_scoring_job` (FUT-017) scored at 20:03; no new score rows since, consistent with an empty unscored queue (the 20:33 forecasts below are unresolved by design, not a scoring gap — nothing was there for the 20:03 cycle to score beyond what it already scored).
- No scoring pass ran and no live writes were made: there was nothing to score, and the run makes no live change. The deliverable is this accuracy evidence.

## 2. Scheduler cycles: the last 3 cycles produced real forecasts

- Forecasts 1652 → 1761 since run 9 (probe 2026-11-27T11:10:28Z / 16:40:28 IST): **+109 new forecasts in ~9h51m**.
- 5 newest forecasts (probed 21:01:24 UTC / 02:31:24 IST), all `as_of` 20:33 UTC today:
  - `a1816d63-fb42-4bb7-8ad2-e2a20040dd54` — `friday:fleet:forecast_demand_24h` — 20:33:13
  - `fc8c5b50-a5f2-4dc5-820c-7838ca7c112e` — `intelx:research:finding_volume_24h` — 20:33:05
  - `ccee10be-ce2b-4a2c-a432-8ca8ef73d27b` — `macro:T10Y2Y:curve_inversion_30d` — 20:33:01
  - `264d9740-8ddb-40a6-b4c3-d6818348a90b` — `service:checkout:capacity_exceedance_24h` — 20:33:01
  - `7e60515d-2918-459e-969f-b722656be0ae` — `trading:SOLUSDT:price_variance_24h` — 20:33:01
- **33 forecasts with `as_of` in the last 3 hours** — covering the 18:33, 19:33 and 20:33 production cycles. Distinct recent `as_of` values: 20:33 (4 distinct) + 19:33 (2 distinct) at the head of the list.
- 18:33 cycle verified explicitly (this run, probed ~21:02 UTC): **11 forecasts** with `as_of` in the 18:33 minute, including `e240a72e-8f90-4138-9667-db739c18549b` (`vyralx:trends:topic_volume_24h`, 18:33:01), `e9ff3ace-2165-4784-888d-1c7dcf19b570` (`trading:BTCUSDT:price_variance_24h`, 18:33:01), `c6428141-7094-4b00-914a-3219fdcbc78b` (`trading:SOLUSDT:price_variance_24h`, 18:33:01). The pipeline is producing real forecasts on schedule.

## 3. Accuracy evidence (calibration report, generated 2026-11-27T21:01:13Z)

- n_scored **1211**, status **measured** (min_samples 30 met).
- MAE **873.76**, RMSE **997.59**, nominal level 0.80, coverage_80 **1.0** (gap +0.2 vs nominal), mean interval width **8477.02**, Winkler_80 **9609.16**, mean pct error **50.59%**. Verdict: **underconfident**.
- Rolling 30-day hit-rate: **0.890999** (n_in_window 1211, window 2026-10-28 → 2026-11-27).
- By nominal level: 0.80 → n=891, coverage 1.0; 0.90 → n=320, coverage_90 0.5875 (gap −0.3125).
- By target (n): `service:checkout:capacity_exceedance_24h` 145, `trading:BTCUSDT:price_variance_24h` 139, `friday:fleet:forecast_demand_24h` 132, `trading:ETHUSDT:price_variance_24h` 132, `trading:SOLUSDT:price_variance_24h` 131, `macro:SPY:return_exceedance_24h` 128, `macro:DGS10:yield_shift_30d` 123, `macro:T10Y2Y:curve_inversion_30d` 123, `macro:UNRATE:unemployment_drift_90d` 123, `BTCUSDT` 10, `NIFTY` 10, `ETHUSDT` 9, `my portfolio` 4, `fleet:api:request_rate` 1, `what should i watch in indian markets` 1. Total 1211.
- Change since run 9 (16:40 IST today): +109 forecasts (1652→1761), +84 outcomes/scores (1127→1211); MAE 875.01→873.76, RMSE 1005.20→997.59, hit-rate 0.890861→0.890999.

## 4. Headline finding: the only live-scored target is entirely out of interval

- The live class is a single target: `friday:fleet:forecast_demand_24h` (n=132, was 123 in run 9, 118 in run 8, 117 in run 7, 103 in run 6): coverage_90 **0.0**, MAE **1932.02**, RMSE **1953.70**, mean interval width **97.40**, Winkler_90 **37762.01**, mean pct error **90.77%**. Verdict: **overconfident**.
- Its 90% intervals (~97 wide) are ~20x narrower than its errors (~1932) — all 132 live scores missed. The aggregate 0.891 hit-rate is carried by the synthetic scores; the live leg is miscalibrated on its only target. Follow-up for the coordinator (carried from runs 2–3, 5, 7, 8, 9, still open): widen / recalibrate the `friday:fleet:forecast_demand_24h` intervals, or confirm the target's actuals feed is sane.

## 5. Resolution gap: 292 matured forecasts have no outcome at all (was 263)

- **550** forecasts have no outcome row (was 525); of those **292 are matured** (expires_at already passed) but unresolved — oldest 2026-11-20 18:48 UTC (`service:checkout:capacity_exceedance_24h`, forecast `1140e21f-8bab-4584-afa4-eacd5157f5a8`) — the same oldest row as runs 3, 7, 8 and 9, so the backlog is growing, not resolving.
- By target: `intelx:research:finding_volume_24h` **133**, `vyralx:trends:topic_volume_24h` **131** (the two hourly recurring jobs are 264 of 292), `service:checkout:capacity_exceedance_24h` 3, plus 25 singletons across other targets.
- These can never enter the scoring queue until the outcome-recording sweep records their outcomes. This is a resolution gap, not a scoring gap — the scoring job is healthy; the sweep that records outcomes for these recurring targets is not keeping up. (FUT-025 already filed that the lifecycle sweep is not wired on main; this run quantifies the backlog: 292, +29 since run 9.) Follow-up, not fixed here — no code change in this task.

## 6. Data-quality anomaly: 8 rows carry a future resolved_at (unchanged from runs 8 and 9)

- `future_resolved_at`: **8**. Run 8 reported 8 (was 0 in run 7); run 9 reported 8; no new future-dated outcome rows appeared since run 9. Flagged for the coordinator; not investigated further in this run (read-only probe; no live change).

## 7. Service state (live, this run)

- Live Futuris scheduler on IntelX-Server (32.236.185.237:8004), probed first-hand 2026-11-27T21:00:32–21:00:37Z / 02:30:32–02:30:37 IST:
  - `/ready`: status **ready**, service futuris, database **connected**, database_backend **oracle**, version 2.0.0, observed_at 2026-11-27T21:00:36Z.
  - `/health`: status **degraded**, service futuris, version 2.0.0, observed_at 2026-11-27T21:00:37Z; capabilities.storage **ok** (live schema inspection: 13/13 required tables present); capabilities.forecasting **unknown** (NO_MODEL_PROBE — no forecasting-model probe exists; storage readiness is not forecasting ability); dependencies.database **ok** (live round-trip + all required tables present); storage ready true, expected 13, present 13, missing [], error null.
  - The "degraded" is the known state (same as runs 7/8/9 carried): the forecasting capability has no model probe, so it reports unknown. The database is connected and the storage is ready. The scheduler is producing real forecasts on schedule (§2), which is the live proof that matters for this task.
- FUT-032 note stands: its scoring leg was blocked on S2 `Futuris/.env` missing / no DATABASE_URL. This run's route (FRIDAY-Server, server 3: `Futuris/.env` present, tracker code byte-identical to main) works; the S2 route remains untested.

## 8. States

- implemented YES (evidence filed in this doc) / tested YES (all numbers first-hand live reads; the conditional sweep was armed and correctly did not fire — the unscored queue is empty) / merged NO (evidence PR open, awaiting Muse) / deployed N/A (no code change; no live change made) / production-verified YES (the live scheduler on IntelX-Server produced real forecasts in the last 3 cycles, verified first-hand; the scoring job is running on schedule, verified by fresh rows).

— Muse TP14
