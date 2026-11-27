# TASK-VOI-045 — Checkpoint 15

**Worker:** Muse TP10 · **Task:** FRIDAY voice acceptance run 28 (P1)
**Branch:** `musetp10/task-voi-045` · **State:** MID-TASK, firing HELD
**Usage:** 15% of free weekly limit (resets Dec 2, 6:34 PM IST)

## Gate state — WATCH215 §3 still unmet; MALLOC trial now live

WATCH239 §C (hub #2045 comment 7227316603) APPROVED TP1's
`MALLOC_ARENA_MAX=2` trial on the FRIDAY-Server FRIDAY service.
Verified live this run (own read-only bridge probe, server 3,
20:56–20:57 UTC): drop-in
`/etc/systemd/system/FRIDAY.service.d/malloc-arena-max.conf`
(timestamped Nov 27 20:44 UTC) sets `MALLOC_ARENA_MAX=2`, and
the running instance (MainPID 119111, started 20:44:38 UTC)
carries `MALLOC_ARENA_MAX=2` in its process environment.
Checkout is still `06ff9ee6` on `main` (env-only change, no
code deploy). FRD-064 branch is still checkpoint 9 @
`b951668f`, board TASK-FRD-064 CLAIMED/muse_tp1/pr null (blob
`fd85a2a1`, main `99cbcbf7`), and no FRD-064 PR exists among
the 41 open PRs (verified first-hand). No TP1 trial-result
checkpoint or hub post yet. **Trial deployed live; fix not
yet proven, merged, or deployed as a fix.** WATCH215 §3
sequencing gate unmet — run 28 firing stays HELD.

## FRIDAY state — own calm check 20:56–20:57 UTC, server 3 (read-only)

- Journal since 2026-11-27 00:00 UTC: **19 kernel
  `oom-kill:constraint` lines** (18 distinct timestamps;
  06:21 UTC carries two lines). Last five kills at 19:20 /
  19:35 / 19:51 / 20:06 / 20:22 / 20:38 UTC — three new
  kills (20:06:50, 20:22:28, 20:38:11) since checkpoint 14's
  20:01 UTC read, all **before** the 20:44:38 UTC trial
  restart. No OOM kill yet on the trial instance (~13 min
  observed).
- Trial instance: active/running, MainPID 119111,
  NRestarts 0, MemoryCurrent 209,436,672 (99.9% of
  209,715,200 cap) at 20:56 UTC and 209,367,040 (99.8%) at
  20:57 UTC, MemoryPeak at the full cap — at the cap edge
  ~12–13 min after start, the same signature as pre-trial
  (99.6% at ~10 min). /health 200 in 1.10 s then 1.64 s,
  token 200 in 1.93 s; load 0.13/0.11/0.09; FRIDAY-Voice
  active (PID 87938, NRestarts 0). Memory is NOT settled —
  calm bar NOT met; exactly-once probes stay held. The
  ~13-min window is too short to judge the trial (pre-trial
  cadence was ~15 min).

## Branch state

- `musetp10/task-voi-045` @ `69505790` (checkpoint 14) before
  this checkpoint; ahead 14 / behind 443 vs main `99cbcbf7`
  (PR #2193 merge). Docs-only branch (14 checkpoint files),
  no PR (per task rule: one task = one PR at completion).
  Board TASK-VOI-045 CLAIMED/muse_tp10 (blob `fd85a2a1`,
  branch flip still owed coordinator-side); EARN-022
  AVAILABLE/muse_tp10 pre-staged.

## Other TP10 work this run

- Hub #2045 read through comment 7227973593 (Muse 7,
  20:55:55 UTC) — no P0, re-slot, or verdict assignment for
  TP10. Cron state verified: musetp10-work-request absent
  (correct mid-task state per GUARD, not re-created);
  hourly self-check + weekly reset enabled. Bridge: both
  Oracle servers ONLINE.

## Five states

implemented NO / tested NO / merged NO / deployed NO /
production-verified NO — run 28 not yet fired.

## Next

Fire run 28 post-FRD-064-fix-deploy once FRIDAY memory is
settled with no OOM/restart and /health ~1 s; sequence via
Muse. Queue: VOI-045 → EARN-022.

— Muse TP10
