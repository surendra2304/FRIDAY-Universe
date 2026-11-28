# TASK-FRD-064 — Checkpoint 20: Bridge BACK — kill #41 confirmed; live PID 80+ min, longest survival under 300M cap

Filed: 2026-11-28 ~11:25 IST (2026-11-28 ~05:55 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 19 (53d82b79); this file is the checkpoint-20 commit.

## 1. Headline — bridge back, tally verified again, cap extends life but kills continue

- **Bridge BACK.** MCP initialize 200 (FRIDAY-Cloud-Engineering-Bridge
  v1.30.0, 31 tools) on all three calls this run, after the ~10:22–~10:35
  IST outage (WATCH257 §A). Gateway routes 200 again (see §2).
- **Kill #41 CONFIRMED: 04:31:16 UTC, PID 134977** (the PID checkpoint 19
  saw alive at 04:04 UTC, ~83% of the 300M cap at 5 min old), total-vm
  584,408 kB, anon-rss 101,700 kB, file-rss 39,156 kB. Its life was ~32.6
  min (boot ~03:58:40 UTC after kill #40) — about 2x the old ~15.6-min
  cadence, consistent with the 300M cap buying time, not fixing the cause.
- **Tally now 41 FRIDAY-main kills since Nov 27 00:00 UTC** (46 kernel
  kill lines including 5 other-python processes — see §2 recount).
- **Live PID 135781 (boot 04:31:21 UTC): alive 80+ min at probe
  (05:52 UTC) — the longest survival yet under the 300M cap; kill #42
  has NOT yet occurred.** Cycle 3 under MemoryMax=300: cycle 1 killed at
  32 min, cycle 2 at 16 min, cycle 3 alive 80+ min. The cap extends life
  but kills continue — checkpoint 18's "fix FAILED on cadence" verdict
  stands; the 300M cap is a reprieve, not a fix.
- **Memory:** 247.7M current / 300M max, swap 95.9M / 192M max, peak
  300.0M, **swap peak 192.0M — the swap ceiling has been hit** while the
  process stays alive. Tracemalloc ticks 05:46–05:50 UTC: rss 272.4 MB
  → 186.1 MB, traced ~11.1–11.5 MB (~4% of RSS) — Python heap
  exonerated on a seventh PID.
- FRIDAY self-logged `memory_critical` at 05:50:34 (100.0% of the 300 MB
  limit) then `memory_recovered` (<60%) at 05:51:04 — RSS oscillation,
  mechanism unattributed.
- **Health:** loopback `/health` 200 (1.46 s), `/api/health` 200
  (0.78 s); public `/friday/health` 200 (1.62 s),
  `/friday/api/health` 200 (1.12 s); bridge `/health` 200 (2.11 s).

## 2. Probes this run (first-hand)

- **Bridge MCP initialize:** 200 x3 (tools list + three run_shell
  calls, Server 3 x2, Server 2 x1). All succeeded; no outage this run.
- **Server 3 journalctl -k since 04:00 UTC:** exactly one kill line —
  04:31:16 PID 134977 (above).
- **Recount (case-insensitive grep):** Nov 28 kill lines **15** = 14 main
  (#28 00:09:41 through #41 04:31:16) + 1 other-python (02:41:21,
  PID 132365, vm 368,928 kB, anon 113,972 kB — the 5th other-python line;
  smaller vm than main's ~580 kB, likely a FRIDAY child — identity
  unresolved, flagged not claimed). Since Nov 27 00:00 UTC: **46 lines
  = 41 main + 5 other.** Reconciles with checkpoint 14's 32 lines
  (28 main + 4 other) + 14 lines since.
- **Method note:** the first count attempt this run returned 0 — a grep
  case bug (`killed process` vs the kernel's `Killed process`). Re-run
  with `grep -i` gave the verified counts above. Future runs: always
  case-insensitive on kernel OOM lines.
- **Server 3 status (05:52 UTC):** FRIDAY.service active since
  04:31:21 UTC, MainPID 135781, NRestarts=3, MemoryCurrent 259,751,936
  (~247.7 MiB), MemoryMax 314,572,800 (300M). Drop-ins unchanged:
  dispatch-env, malloc-arena-max, memory-max-300, swapmax, tracemalloc.
- **No cap change, no restart, no deploy this run** — none authorized
  (WATCH254 §C.1: no further cap raise without TP10's root-cause
  evidence; TP1 does not raise the cap unilaterally).

## 3. What this means for the held items

- **VOI-045 run 28** (TP10 head): stays HELD. **WATCH258 §F DECIDED:**
  TP10 reclaims VOI-045 and files the root-cause probe report — "the
  outcome-bearing deliverable that unblocks voice work"; the EARN-022
  displacement ask was declined. TP10 has NOT yet posted the reclaim
  (hub read through comment 7234893342). TP1 keeps observing and
  checkpointing; the root-cause probe is TP10's to file.
- **FRD-064 fix direction:** still pending TP10's report. No further cap
  raise, no footprint-reduction work taken unilaterally.
- **Board PR #2273 CLOSED as superseded** (WATCH258 §B); union board
  **#2279 MERGED → main 300ab00c**. Board PR #2281 open (merge rides
  WATCH259 on green).

## 4. Hub + board state this run

- Hub #2045 read through comment 7234893342 (M7 idle post, 05:48:06Z).
  **WATCH257 (7234517672), WATCH258 (7234793701), BE 10:45 (7234528840),
  BE 11:15 (7234754534) read in full.** No P0, no verifier duty for TP1,
  no new TP1 assignment.
- Main HEAD 300ab00c (merges #2266, #2279). Board on main (verified
  first-hand): TASK-FRD-064 CLAIMED / muse_tp1 / pr null (branch field
  still stale: `musetp1/task-frd-064-oom-kill-root-cause` vs actual
  `musetp1/task-frd-064-oom-kills-chat-turns` — correction rides the
  coordinator's board PR); TASK-EARN-017 AVAILABLE / muse_tp1
  (pre-staged next); TASK-VOI-045 AVAILABLE / owner null, branch
  `musetp10/task-voi-045` (TP10 reclaim pending); TASK-WEB-007 MERGED
  pr 2075; TASK-FRD-062 MERGED pr 2108.
- Open PRs: 41 total, none headed musetp1 (checkpoint docs only, no
  code PR).
- Weekly usage 15% (resets Dec 2, 17:43 IST).

## 5. Five states (unchanged from checkpoint 19)

- Implemented: YES (MemoryMax 300M drop-in live on Server 3)
- Tested: YES (three observation cycles under 300M: 32-min kill, 16-min kill, 80+ min alive)
- Merged: NO (checkpoint docs only, no code PR)
- Deployed: YES (cap change live on the production service)
- Production-verified: NO (kills continue; acceptance is no OOM kills)

## 6. Next

Next driver run: re-probe (kill #42 status, live PID 135781 fate — if it
survives past ~06:30 UTC it clears 2 hours, a new record under the cap),
file checkpoint 21; watch for TP10's VOI-045 reclaim + root-cause probe
report. Queue unchanged: FRD-064 → EARN-017. FRD-064 stays head.
