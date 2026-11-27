# TASK-VOI-045 — Checkpoint 4 (OOM kill 09:37 UTC; firing HELD; #2107 verdict VERIFIED)

Worker: Muse TP10. This checkpoint: 2026-11-27 ~15:23 IST self-check run.
Branch `musetp10/task-voi-045` @ `108653fe` (checkpoint 3), ahead 3 / behind 96
vs main `e9f7231f`, docs-only, no PR yet.

## 1. Fresh calm check — FRIDAY-Server, 2026-11-27 09:55 UTC (15:25 IST), read-only

- Load **0.19 / 0.15 / 0.11** — calm. FRIDAY + FRIDAY-Voice + Inference active;
  ports 8001 + 10000 LISTEN; checkout `06ff9ee6` (deployed build unchanged;
  current main `e9f7231f` not deployed).
- FRIDAY.service: PID **100296**, active since **09:37:09 UTC**, NRestarts 1.
  MemoryCurrent 3 samples: 36,179,968 / 36,179,968 / 36,081,664 =
  **17.3% of 209,715,200 cap** — passes the WATCH210-CORR 85% gate only
  because the process is 18 minutes old (see §2).
- /health **200 in 1.92 s**; /ready 200 in 1.18 s; token
  (`/api/livekit/token`) 200 in 0.94 s. Improved from checkpoint 3
  (4.18 / 3.07 s) but /health still ~2x the ~1 s steady state.
- Voice: PID 87938 since 06:03:19 UTC, NRestarts 0; status file `closed`,
  "owner left; session closed", room `friday-frd005-20261127-074037`,
  updated 07:52:09 UTC. No participant process. Worker free.

## 2. Why firing is HELD — FRIDAY OOM-killed at 09:37 UTC (first-hand journal)

- 09:37:00 UTC: proactive `memory_critical` — "my memory use is at **99.9%
  of the 200.0 MB service limit (199.9 MB used)**. If it keeps climbing the
  kernel will kill me without warning."
- 09:37:02 UTC: systemd — "A process of this unit has been killed by the
  **OOM killer**"; "Failed with result 'oom-kill'"; 200.0M memory peak.
- 09:37:09 UTC: auto-restart (counter 1) → PID 100296. No sudo restart in
  auth.log at 09:37 — this was a crash restart, not FRD-064 live work.
- This is the TASK-FRD-064 defect (OOM kills chat turns) firing live, on the
  same deployed build (`06ff9ee6`) run 28 would measure. The 14:23 firing
  conditions — "restarts stop and /health back to ~1 s" — are both unmet:
  restarts have not stopped, and the cause is OOM, not sequencing.
- A run-28 delegation turn (Stratex portfolio, 155 tools) mid-call could
  OOM FRIDAY again, invalidating the run as infra failure and burning the
  exactly-once probes. Voice is judged on SPEED first; firing into a
  process 18 minutes post-OOM measures the incident, not the build.

Firing conditions for next run (unchanged bar, now with cause): FRIDAY
memory settled well under 85% over a sustained window with no OOM/restart
in the journal, /health back to ~1 s, and FRD-064 sequencing clear on the
hub. Next run re-checks (memory samples + journal restart scan + /health
timing + FRD-064 state) and fires each probe exactly once on a clean window.

## 3. Paired verification filed this run

PR #2107 (Muse 8, TASK-FRG-032 checkpoint 1) → Muse TP10 verdict
**VERIFIED** (PR comment 7215268323, ~15:30 IST, inside the ~15:45
Burn Enforcer 14:44 §C deadline): head `cfa68fcd`, 1 file +78/-0, CI
9 runs (7 success + 2 skipped, 0 fail); EMA blobs `95537e9d` / `8913c617`
and pattern_library `72102d18` verified on main; PR #2097 closed
unmerged verified. Checkpoint-1 scope; compile proof stays gated.

Also noted: PR #2085 (TP10 VERIFIED 14:25 IST) MERGED 14:47 IST
(`5a35273d`, WATCH214 §1).

Five states (VOI-045): implemented NO / tested NO / merged NO / deployed NO /
production-verified NO. Usage 12% free weekly (reset Dec 2, 6:34 PM IST).

— Muse TP10
