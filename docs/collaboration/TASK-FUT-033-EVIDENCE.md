# TASK-FUT-033 — Futuris: forecast accuracy scoring run 5

- Task: TASK-FUT-033 (P1) — score the next unscored forecast cohort against outcomes and file the accuracy evidence. Sequel to FUT-030 (run 4), per the board entry on main.
- Claim: Muse TP12, hub #2045 comment 7208501412, 2026-11-27 ~08:15 IST (WATCH197 §2 assignment; queue FUT-033 → STR-078 → EARN-021). Branch `musetp12/task-fut-033-forecast-scoring-run-5` adopted from TP5's retained branch @ `c3d322bc` (checkpoint-2 evidence prep only); branch-verified hub 7208521144.
- Prior prep: Muse TP5, claim hub #1483 comment 7195226168, 2026-11-26 ~20:06 IST; checkpoint-2 prep filed 2026-11-26 ~23:06 IST per WATCH174. No live verification had been run; no scores claimed. TP5's §§1–4 below are retained verbatim as the prep record.
- **Status: COMPLETE — live verification run 2026-11-27 ~08:46 IST (probe 03:16:50 UTC).** Fresh first-hand numbers in §5. Work PR opened after this filing; paired verification requested. Board flip FUT-033 → CLAIMED/muse_tp12 rides in the coordinator's board PR #2054 rebuild (WATCH198 §6); no board hunk in this work PR.

## 1. Cohort boundary

- Runs 6 and 7 ran before run 5's evidence was filed and are already merged: FUT-035 (run 7, PR #1991, merged 2026-11-26T13:34:10Z) and FUT-034 (run 6, PR #1992, merged 2026-11-26T14:16:30Z). Both evidence docs are on main (`TASK-FUT-035-EVIDENCE.md`, `TASK-FUT-034-EVIDENCE.md`) and both record that FUT-033 (run 5) has no evidence filed on main — confirmed first-hand 2026-11-26 ~23:06 IST (`TASK-FUT-033-EVIDENCE.md` returned 404 on main `708e4041`).
- Both runs found the oldest unscored cohort **empty** (see §2). Run 5's deliverable is therefore: (a) a fresh first-hand verification that the cohort is still empty (or scoring of any new cohort that has resolved since), and (b) this accuracy evidence. It is **not** a re-score of runs 6/7's cohort — that cohort is already scored.

## 2. Prior runs' evidence (cited, not this run's live numbers)

For boundary-setting only. These are FUT-035/FUT-034's first-hand live reads, cited from their merged evidence docs; this run has not yet re-verified them live.

- FUT-035 (run 7, probes 2026-11-26 ~18:48–18:51 IST): `list_unscored_resolved(limit=500)` = 0 rows; store totals forecasts 1351, outcomes 896, scores 896 (896/896 resolved scored); `count_event_only_resolved` = 0; last scoring batch 13:03:17 UTC, standing 30-minute `forecast_scoring_job` (FUT-017) on schedule. Calibration (13:18:05 UTC): n_scored 896, status measured, MAE 912.45, RMSE 1046.53, nominal 0.80, coverage_80 1.0, mean interval width 8758.19, Winkler_80 9768.92.
- FUT-034 (run 6, probes 2026-11-26 ~19:15–19:16 IST, ~30 min later): `list_unscored_resolved(limit=500)` = 0 rows; store totals forecasts 1362 (+11 new, none resolved), outcomes 896, scores 896; `count_event_only_resolved` = 0; last batch still 13:03:17 UTC.
- Scoring sweep (`score_resolved`, idempotent, savepoint-isolated per the FUT-025 fix) was armed but did not run in either run: the queue was empty. No live writes were made by either run.

## 3. Why the live read was held (grant record, stated plainly)

- Correction 7197725825 (2026-11-26 22:00 IST) states the `run_shell` grant stands (owner main-chat tap 18:25:56 IST closing approval 7113152293) and withdraws WATCH172's denial.
- WATCH174 (7198392637) and WATCH175 (7199323929) hold the live legs: `permissions.history` checks #6 and #7 return "No permission request found" for approval 7113152293, and no verifiable confirmation has arrived from the coordinator's vantage. WATCH174 answered this task directly: "I cannot confirm the correction covers your read-only server-3 verification... The live read stays held."
- TP5 complies: no live server access for FUT-033 until a verified clearance. Bridge health was checked this run (first attempt RemoteDisconnected — transport flaky tonight per WATCH174; retry 200 healthy, Server 2 10.0.0.120). No bridge call beyond health was made.
- **Superseded 2026-11-27 (TP12 note, not TP5's text):** WATCH183 §2a (hub 7203117194) ruled the grant settled and directed the live leg to run under standing clearance 7200564540. The live leg below ran under that clearance. TP5's hold above is the record of why the leg waited; it no longer blocks this task.

## 4. Method — ready to execute on verified clearance (FUT-028 method)

Identical to FUT-034/FUT-035, so run 5's numbers are directly comparable:

1. Read-only live reads on the shared Oracle store via FRIDAY-Server (bridge server 3, `run_shell`) using Futuris's own session factory and tracker code. Verify byte-identity vs current main first (sha256 of `Futuris/futuris/storage/{db,score_repository,models}.py` and `Futuris/futuris/services/forecast_tracker.py`); record the server-3 checkout HEAD and working-tree state for `Futuris/futuris`.
2. `list_unscored_resolved(limit=500)` — the cohort check. Record row count verbatim.
3. Store totals (forecasts / outcomes / scores) and `count_event_only_resolved`.
4. Newest score rows (last batch time) to confirm the standing 30-minute `forecast_scoring_job` (FUT-017) is on schedule.
5. Calibration report (n_scored, MAE, RMSE, coverage_80, mean interval width, Winkler_80) for the accuracy evidence.
6. Score via `score_resolved` **only if** a new unscored cohort exists (idempotent, savepoint-isolated). If the cohort is empty, make no live writes — the deliverable is the evidence.
7. No credential read or printed, no service restarted, no deploy, no fleet mutation. Complete §§5–6 below with the verbatim numbers, then open the work PR (board flip already in #2002; do not duplicate it — if #2002 has not merged by then, carry the flip in the work PR instead and say so).
- **TP12 update to step 7:** the board flip now rides in the coordinator's board PR #2054 rebuild (WATCH198 §6 lists FUT-033→TP12 among the 18 good flips). This work PR carries the evidence doc only — no board hunk.

## 5. Live verification — COMPLETE (Muse TP12, 2026-11-27 ~08:46 IST)

Probe run on FRIDAY-Server (bridge server 3) 2026-11-27 03:16:50 UTC (08:46:50 IST), script `/tmp/fut036_probe.py` (sha256 `d017df1ba8fd0de8d0af251440e87b2b7b4126685c8d82a862bc56f79bbd4654`, identical to the workspace copy and to the run-7/8 verified script), venv312, `PYTHONPATH=/opt/friday_universe/Futuris`.

**Code verification before probing (all first-hand):**
- Scoring code fetched from main `4af777cc`, sha256-verified byte-identical to the run-7/8 verified code: `forecast_tracker.py 2b429615cbcfcfe0200d89ef476ee23b246e5459cd912bc0c4626a29f59ea3c2`, `db.py 4d945dcd24e5d2befc115756a1f35cd2390e112f44e2cdadac72bed286e75b2a`, `models.py 16794c0f7b2d38aacee6d8bf593c9fb6f0f9818bbefca5f5328a6766d72d57b3`, `score_repository.py 39ed9216a37a3f585729486efa4e9d9389d43c430a3ef7a4d9dc9af9f62e3af5`.
- Server-3 checkout `/opt/friday_universe`: HEAD `5b245ffd`, branch `main` (same as runs 7/8). Working tree: only `FRIDAY/ui/out/*` modifications (another agent's, left untouched); no changes under `Futuris/futuris`. The same 4 files on the checkout hash identically to main.
- Service: Futuris server 6 `/health` HTTP 503 degraded v2.0.0 (observed 03:17:24Z), storage ok 13/13, database ok, forecasting unknown NO_MODEL_PROBE — same posture as runs 7/8. uvicorn PID 35287 since 2026-11-26 06:32 UTC (same process as runs 7/8).

**Cohort check — still empty:**
- `list_unscored_resolved(limit=500)` = **0 rows**. The sweep did **not** run (`score_resolved` not armed, no live writes made by this run).
- Store totals: forecasts **1561**, outcomes **1061**, scores **1061** (1061/1061 resolved scored); `count_event_only_resolved` = **0**; last scoring batch **2026-11-27 03:04:15 UTC** (~12 min before the probe — the standing 30-minute `forecast_scoring_job` (FUT-017) is on schedule).

**Calibration report (generated 2026-11-27T03:16:50Z):**
- n_scored **1061**, status measured, MAE **878.544843**, RMSE **1013.632486**, nominal 0.80, coverage_80 **1.0**, coverage gap vs nominal +0.2, mean interval width 8555.565052, Winkler_80 9743.14823, mean pct error 50.827227. Verdict: **underconfident**.
- Rolling 30-day hit-rate: **0.890669** (n_in_window 1061, window 2026-10-28 → 2026-11-27).
- By nominal level: 0.80 → n 757, coverage_80 1.0; 0.90 → n 304, coverage_90 0.618421.
- Live class (`evidence_class="live"`): n **116**, MAE 1995.381456, RMSE 2011.02774, nominal 0.90, coverage_90 **0.0**, verdict **overconfident**.
- By target (n / MAE / RMSE / coverage_80): BTCUSDT 8 / 635.33 / 655.33 / 1.0; ETHUSDT 7 / 686.06 / 705.95 / 1.0; NIFTY 8 / 650.22 / 675.31 / 1.0; fleet:api:request_rate 1 / 299.31 / 299.31 / 1.0; friday:fleet:forecast_demand_24h 116 / 1995.38 / 2011.03 / — (coverage_90 0.0); macro:DGS10:yield_shift_30d 107 / 763.62 / 826.25 / 1.0; macro:SPY:return_exceedance_24h 112 / 750.53 / 815.11 / 1.0; macro:T10Y2Y:curve_inversion_30d 107 / 763.62 / 826.25 / 1.0; macro:UNRATE:unemployment_drift_90d 107 / 763.62 / 826.25 / 1.0; my portfolio 4 / 1692.04 / 1693.91 / 1.0; service:checkout:capacity_exceedance_24h 129 / 699.68 / 775.08 / 1.0; trading:BTCUSDT:price_variance_24h 123 / 713.94 / 787.12 / 1.0; trading:ETHUSDT:price_variance_24h 116 / 734.25 / 803.26 / 1.0; trading:SOLUSDT:price_variance_24h 115 / 735.63 / 804.96 / 1.0; what should i watch in indian markets 1 / 1493.77 / 1493.77 / 1.0.

**Resolution gap:**
- Forecasts with no outcome row: **500**; of those, matured (as_of + horizon ≤ now): **249**. Oldest matured row **1140e21f-8bab-4584-afa4-eacd5157f5a8** (`service:checkout:capacity_exceedance_24h`, 2026-11-20T18:48:01Z) — unchanged since runs 7/8. Largest matured groups: `intelx:research:finding_volume_24h` 116, `vyralx:trends:topic_volume_24h` 114.
- Data-quality observation (not a doc error): `future_resolved_at` = **8** outcomes stamped with resolved_at in the future relative to probe time (was 0 at run 7). Flagged for the coordinator; no conclusion drawn from it here.

**Comparison vs run 7 (FUT-037, probe 2026-11-26 21:16 UTC, first-hand):** forecasts 1439 → 1561 (+122 ingested), outcomes/scores 952 → 1061 (+109 scored by the standing job), n_scored 952 → 1061, MAE 912.62 → 878.54, RMSE 1041.75 → 1013.63, coverage_80 1.0 → 1.0, hit-rate 0.883403 → 0.890669, gap 487/239 → 500/249, oldest row unchanged, last batch 21:03:32 UTC → 03:04:15 UTC. Direction consistent: the standing job keeps scoring newly resolved forecasts; accuracy improved slightly.

## 6. Five states (live leg complete)

- Implemented: COMPLETE (live verification run; evidence filed).
- Tested: COMPLETE (live probe on the shared store; no test doubles).
- Merged: NO (work PR opened after this filing; paired verification requested).
- Deployed: N/A (evidence task; no deploy).
- Production-verified: YES (first-hand live numbers above, same method as runs 6/7/8).

— Muse TP5 (prep §§1–4) / Muse TP12 (live leg §5)
