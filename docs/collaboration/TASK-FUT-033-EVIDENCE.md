# TASK-FUT-033 — Futuris: forecast accuracy scoring run 5

- Task: TASK-FUT-033 (P1, owner muse_tp5) — score the next unscored forecast
  cohort against outcomes and file the accuracy evidence. Sequel to FUT-030
  (run 4), per the board entry on main (filed by Muse (coordinator)
  watch143, 2026-11-26).
- Claim: hub #1483 comment 7195226168, 2026-11-26 ~20:06 IST. Branch
  `musetp5/task-fut-033-forecast-scoring-run-5` from main `49cfd862`;
  board flip CLAIMED / muse_tp5 rides in coordinator board PR #2002
  (WATCH175, hub 7199323929 — OPEN, held on CI at filing; re-verify at
  merge time, do not assume).
- **Status of this document: CHECKPOINT 2 — repo-side preparation only.**
  Filed 2026-11-26 ~23:06 IST per WATCH174 (hub 7198392637): "Repo-side
  work (evidence doc prep) proceeds; the live-read leg runs immediately
  on a verified clearance." **No live verification has been run for this
  task yet. No scores are claimed in this document.** The live-read leg
  is held under the WATCH174/175 grant hold (see §3). This document will
  be completed with first-hand live numbers in the same commit chain
  once a verified clearance arrives; the work PR is opened only then.

## 1. Cohort boundary

- Runs 6 and 7 ran before run 5's evidence was filed and are already
  merged: FUT-035 (run 7, PR #1991, merged 2026-11-26T13:34:10Z) and
  FUT-034 (run 6, PR #1992, merged 2026-11-26T14:16:30Z). Both evidence
  docs are on main (`TASK-FUT-035-EVIDENCE.md`,
  `TASK-FUT-034-EVIDENCE.md`) and both record that FUT-033 (run 5) has
  no evidence filed on main — confirmed first-hand 2026-11-26 ~23:06 IST
  (`TASK-FUT-033-EVIDENCE.md` returned 404 on main `708e4041`).
- Both runs found the oldest unscored cohort **empty** (see §2). Run 5's
  deliverable is therefore: (a) a fresh first-hand verification that the
  cohort is still empty (or scoring of any new cohort that has resolved
  since), and (b) this accuracy evidence. It is **not** a re-score of
  runs 6/7's cohort — that cohort is already scored.

## 2. Prior runs' evidence (cited, not this run's live numbers)

For boundary-setting only. These are FUT-035/FUT-034's first-hand live
reads, cited from their merged evidence docs; this run has not yet
re-verified them live.

- FUT-035 (run 7, probes 2026-11-26 ~18:48–18:51 IST):
  `list_unscored_resolved(limit=500)` = 0 rows; store totals forecasts
  1351, outcomes 896, scores 896 (896/896 resolved scored);
  `count_event_only_resolved` = 0; last scoring batch 13:03:17 UTC,
  standing 30-minute `forecast_scoring_job` (FUT-017) on schedule.
  Calibration (13:18:05 UTC): n_scored 896, status measured, MAE 912.45,
  RMSE 1046.53, nominal 0.80, coverage_80 1.0, mean interval width
  8758.19, Winkler_80 9768.92.
- FUT-034 (run 6, probes 2026-11-26 ~19:15–19:16 IST, ~30 min later):
  `list_unscored_resolved(limit=500)` = 0 rows; store totals forecasts
  1362 (+11 new, none resolved), outcomes 896, scores 896;
  `count_event_only_resolved` = 0; last batch still 13:03:17 UTC.
- Scoring sweep (`score_resolved`, idempotent, savepoint-isolated per
  the FUT-025 fix) was armed but did not run in either run: the queue
  was empty. No live writes were made by either run.

## 3. Why the live read is held (grant record, stated plainly)

- Correction 7197725825 (2026-11-26 22:00 IST) states the `run_shell`
  grant stands (owner main-chat tap 18:25:56 IST closing approval
  7113152293) and withdraws WATCH172's denial.
- WATCH174 (7198392637) and WATCH175 (7199323929) hold the live legs:
  `permissions.history` checks #6 and #7 return "No permission request
  found" for approval 7113152293, and no verifiable confirmation has
  arrived from the coordinator's vantage. WATCH174 answered this task
  directly: "I cannot confirm the correction covers your read-only
  server-3 verification... The live read stays held."
- TP5 complies: no live server access for FUT-033 until a verified
  clearance. Bridge health was checked this run (first attempt
  RemoteDisconnected — transport flaky tonight per WATCH174; retry 200
  healthy, Server 2 10.0.0.120). No bridge call beyond health was made.

## 4. Method — ready to execute on verified clearance (FUT-028 method)

Identical to FUT-034/FUT-035, so run 5's numbers are directly comparable:

1. Read-only live reads on the shared Oracle store via FRIDAY-Server
   (bridge server 3, `run_shell`) using Futuris's own session factory
   and tracker code. Verify byte-identity vs current main first
   (sha256 of `Futuris/futuris/storage/{db,score_repository,models}.py`
   and `Futuris/futuris/services/forecast_tracker.py`); record the
   server-3 checkout HEAD and working-tree state for `Futuris/futuris`.
2. `list_unscored_resolved(limit=500)` — the cohort check. Record row
   count verbatim.
3. Store totals (forecasts / outcomes / scores) and
   `count_event_only_resolved`.
4. Newest score rows (last batch time) to confirm the standing
   30-minute `forecast_scoring_job` (FUT-017) is on schedule.
5. Calibration report (n_scored, MAE, RMSE, coverage_80, mean interval
   width, Winkler_80) for the accuracy evidence.
6. Score via `score_resolved` **only if** a new unscored cohort exists
   (idempotent, savepoint-isolated). If the cohort is empty, make no
   live writes — the deliverable is the evidence.
7. No credential read or printed, no service restarted, no deploy, no
   fleet mutation. Complete §§5–6 below with the verbatim numbers,
   then open the work PR (board flip already in #2002; do not duplicate
   it — if #2002 has not merged by then, carry the flip in the work PR
   instead and say so).

## 5. Live verification — PENDING

- [ ] Cohort check (`list_unscored_resolved`) — PENDING verified clearance.
- [ ] Store totals + `count_event_only_resolved` — PENDING.
- [ ] Last-batch / standing-job check — PENDING.
- [ ] Calibration report — PENDING.
- [ ] Scoring pass (only if new cohort) — PENDING; not armed until the
      cohort check runs.

## 6. Five states (at checkpoint 2)

- Implemented: NO (repo-side prep only; live leg not run).
- Tested: NO (no live read yet; prior runs' numbers cited, not re-verified).
- Merged: NO (no work PR yet; branch carries this prep commit only).
- Deployed: N/A (evidence task; no deploy).
- Production-verified: NO.

Not DONE. Next: execute §4 immediately on a verified clearance, complete
§5, open the work PR for peer review (never self-merge).

— Muse TP5
