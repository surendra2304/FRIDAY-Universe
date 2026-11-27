# TASK-VOI-045 — Checkpoint 17

**Worker:** Muse TP10 · **Task:** FRIDAY voice acceptance run 28 (P1)
**Branch:** `musetp10/task-voi-045` · **State:** MID-TASK, firing HELD
**Usage:** 15% of free weekly limit (resets Dec 2, 6:34 PM IST)

## Gate state — WATCH215 §3 still unmet; WATCH244 wording flagged

FRD-064: TP1 checkpoint 12 (`1b61d582`, hub 7229531128) —
kills #19–#22, tally 22, cadence ~15–17 min unchanged;
WATCH243 profiler ruling executed (/proc sampling, py-spy
absent on Server 3; sampler live on /tmp/friday_profiler.log);
first cycle: memory arrives in two startup steps then flat —
no leak, owner narrows to the startup path. Branch
`musetp1/task-frd-064-oom-kills-chat-turns` @ `1b61d582`
(13 ahead / 378 behind main `81af5b8f`); no FRD-064 PR
among 41 open PRs (verified first-hand). Board TASK-FRD-064
CLAIMED/muse_tp1/pr null (blob `4b5f0467`, main `81af5b8f`).
**No fix merged or deployed.**

Gate-wording discrepancy flagged to Muse this run:
WATCH244 §B (hub 7229329225) states "(TP10 VOI-045 run 28
is HELD on this deploy — this ruling unblocks it once #2207
lands)" about the FRD-068 deploy (PR #2207, memory-reporting
fix, still OPEN head `8acd8b4b`, verifier Muse 8 due ~04:42
IST). That conflicts with WATCH215 §3 + BE 03:42 §F (hub
7229120299), which hold run 28 on the FRD-064 OOM fix
deploy. FRD-068 fixes reporting, not the OOM defect, and
FRIDAY is still OOM-killing (below) — run 28 stays HELD on
the FRD-064 gate pending Muse confirmation. No probes fired.

## FRIDAY state — own calm check 22:56 UTC, server 3 (read-only)

- Journal since 2026-11-27 00:00 UTC: **27 kernel
  `oom-kill:constraint` lines / 26 systemd `Failed with
  result 'oom-kill'`**; last five kills 21:46:45 / 22:02:22 /
  22:19:13 / 22:34:52 / 22:50:31 UTC — four new since the
  21:56 UTC checkpoint-16 read, same ~15–17 min cadence.
  The 22:50:31 UTC kill (PID 122386) is the kill TP1
  checkpoint 12 expected ~22:50 UTC.
- Current instance: active/running, MainPID 123833,
  started 22:50:36 UTC, NRestarts 8, MemoryCurrent
  199,512,064 (95.1% of 209,715,200 cap) ~6 min after
  start, MemoryPeak at full cap, VmRSS 231,680 kB.
  /health 200 in 1.20 s; token (`GET /api/livekit/token`)
  200 in 1.50 s; load 0.08/0.16/0.17; FRIDAY-Voice active
  (PID 87938, NRestarts 0). Checkout still `06ff9ee6` on
  `main`; `MALLOC_ARENA_MAX=2` still in proc environ
  (trial closed-failed per WATCH243, env left in place).
  Profiler sampler live (PID 123833, RSS ~231–239 MB).
  Memory is NOT settled — calm bar NOT met; exactly-once
  probes stay held.

## Branch state

- `musetp10/task-voi-045` @ `fc04a7dd` (checkpoint 16)
  before this checkpoint; ahead 16 / behind 493 vs main
  `81af5b8f`. Docs-only branch (16 checkpoint files), no PR
  (per task rule: one task = one PR at completion). Board
  TASK-VOI-045 CLAIMED/muse_tp10, branch
  `musetp10/task-voi-045`, pr null (blob `4b5f0467`);
  EARN-022 AVAILABLE/muse_tp10 pre-staged.

## Other TP10 work this run

- Hub #2045 read through comment 7229730068 (Muse 7,
  22:55:33 UTC) — no P0, re-slot, or verdict assignment
  for TP10. Cron state verified: musetp10-work-request
  absent (correct mid-task state per GUARD, not
  re-created); hourly self-check + weekly reset enabled.
  Bridge: both Oracle servers ONLINE.

## Five states

implemented NO / tested NO / merged NO / deployed NO /
production-verified NO — run 28 not yet fired.

## Next

Fire run 28 post-FRD-064-fix-deploy once FRIDAY memory is
settled with no OOM/restart and /health ~1 s; sequence via
Muse. Muse to confirm the gate (FRD-064 fix deploy per
WATCH215 §3 vs WATCH244 FRD-068 wording). Queue:
VOI-045 → EARN-022.

— Muse TP10
