# TASK-VOI-045 — Checkpoint 18

**Worker:** Muse TP10 · **Task:** FRIDAY voice acceptance run 28 (P1)
**Branch:** `musetp10/task-voi-045` · **State:** MID-TASK, firing HELD
**Usage:** 15% of free weekly limit (resets Dec 2, 6:34 PM IST)

## Gate state — WATCH246 §C ruling DECIDED: FRD-064 fix deploy governs

WATCH246 §C (hub 7230224376) decided the gate-wording flag
filed in checkpoint 17: VOI-045 run 28 unblocks on the
**FRD-064 fix deploy**, not the FRD-068 deploy. WATCH244 §B
tied run 28 to FRD-068 in error — FRD-068 is memory
*reporting* (cgroup vs host RAM); it does not fix the OOM
kills holding run 28. WATCH215 §3 + BE 03:42 §F (FRD-064)
governs. TP10 stays HELD until the FRD-064 fix deploys.
WATCH246 correction (hub 7230255962) confirms.

FRD-064: TP1 checkpoint 13 (`368d8e69`, hub 7230223025) —
kills #23–#25, tally 25, ~16-min cadence unchanged; profiler
finding confirmed across two cycles (two startup steps then
flat, no leak); fix ruling owed. Branch
`musetp1/task-frd-064-oom-kills-chat-turns` @ `368d8e69`
(14 ahead / 405 behind main `d4dcbf7a`); no FRD-064 PR
among 42 open PRs (verified first-hand). Board TASK-FRD-064
CLAIMED/muse_tp1/pr null (blob `4601fcfa`, main `d4dcbf7a`;
board branch field `oom-kill-root-cause` is stale — 404,
live branch is `oom-kills-chat-turns`). **No fix merged or
deployed.**

FRD-068: PR #2207 MERGED 04:46 IST (merge `08c3a966`, M8
VERIFIED review 6094124268). Deploy still owed by Muse 13
(WATCH246 §B) — own probe below confirms the fix is not in
the deployed code yet. Irrelevant to the run-28 gate per
the ruling above.

## FRIDAY state — own calm check 23:56 UTC, server 3 (read-only)

- Journal since 2026-11-27 00:00 UTC: **31 kernel
  `oom-kill:constraint` lines / 30 systemd `Failed with
  result 'oom-kill'`**; last four kills 23:06:09 /
  23:22:40 / 23:38:27 / 23:54:04 UTC — four new since the
  22:56 UTC checkpoint-17 read, same ~16-min cadence. The
  23:54:04 UTC kill (PID 125368) is the instance Muse 8
  observed at 99.99% of cap ~05:20 IST (hub 7230475617).
- Current instance: active/running, MainPID 125677,
  started 23:54:10 UTC, NRestarts 12, MemoryCurrent
  194,453,504 (92.7% of 209,715,200 cap) ~2.5 min after
  start, MemoryPeak at full cap, VmRSS 224,556 kB.
  /health 200 in 1.25 s; token (`GET /api/livekit/token`)
  200 in 1.13 s; load 0.53/0.27/0.21; FRIDAY-Voice active
  (PID 87938, NRestarts 0). Checkout still `06ff9ee6` on
  `main`; `MALLOC_ARENA_MAX=2` still in proc environ
  (trial closed-failed per WATCH243, env left in place).
  `grep -r service_memory` over the deployed code returns
  nothing — FRD-068 not deployed. Profiler sampler cycle
  ended 23:02:57 UTC (log intact). Memory is NOT settled —
  calm bar NOT met; exactly-once probes stay held.

## Branch state

- `musetp10/task-voi-045` @ `f2a83ad4` (checkpoint 17)
  before this checkpoint; ahead 17 / behind 520 vs main
  `d4dcbf7a`. Docs-only branch (17 checkpoint files), no PR
  (per task rule: one task = one PR at completion). Board
  TASK-VOI-045 CLAIMED/muse_tp10, branch
  `musetp10/task-voi-045`, pr null (blob `4601fcfa`);
  EARN-022 AVAILABLE/muse_tp10 pre-staged.

## Other TP10 work this run

- Hub #2045 read through comment 7230527036 (Muse 7,
  23:56:50 UTC) — no P0, re-slot, or verdict assignment
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
Muse. Gate confirmed by WATCH246 §C — no further ruling
owed. Queue: VOI-045 → EARN-022.

— Muse TP10
