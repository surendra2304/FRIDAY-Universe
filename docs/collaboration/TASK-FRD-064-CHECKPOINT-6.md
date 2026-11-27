# TASK-FRD-064 — Checkpoint 6: no seventh kill; the goal_loop lead is closed; the fix PR is BLOCKED on an attribution ruling

**Task:** FRIDAY: investigate + fix FRIDAY.service OOM-kills under chat turns.
**Owner:** Muse TP1. **Branch:** `musetp1/task-frd-064-oom-kills-chat-turns`.
**Probed:** 2026-11-27 ~21:37 IST (16:07 UTC), bridge Server 3 = FRIDAY-Server,
first-hand, read-only throughout (standing clearance 7200564540).
**Board on live main `5806c273`:** CLAIMED / owner `muse_tp1` / pr null / P1.
Board note (unchanged, correction still owed in the coordinator's board PR):
the record's `branch` field reads `musetp1/task-frd-064-oom-kill-root-cause`;
the real branch is `musetp1/task-frd-064-oom-kills-chat-turns`.

## 1. No seventh kill — FRIDAY stable 1 h 24 m since the 14:42 UTC kill

`FRIDAY.service` at 16:07 UTC, first-hand:

- MainPID **110165**, NRestarts **3**, active since 14:43:00 UTC — unchanged
  since cp5. Journal since 14:42 UTC shows only the two 14:42 OOM lines;
  no new kill.
- `MemoryCurrent=40,886,272` (~39.0 MB, 19.5% of the 200M cap) /
  `MemorySwapCurrent=132,657,152` (~126.5 MB, 65.9% of the 192M cap).
  Total footprint ~165.5 MB.
- `/health` 200 in 1.95 s.

**Swap keeps growing while RAM falls:** cp5 (~15:12 UTC) measured swap
96,592 kB and RAM ~60.4 MB (total ~153.6 MB). Now swap is ~126.5 MB
(+~30 MB in ~55 min) while RAM is ~39 MB (−~21 MB). The anonymous floor
is not shrinking — it is migrating RAM → swap. At this rate the 192M swap
cap is the binding constraint, not RAM. Recorded, not yet a trend (two
points); the next checkpoint re-measures.

## 2. The goal_loop lead is CLOSED — the bug is already fixed on main

Cp5 §6 carried `goal_loop.py:273` as a live lead (JSONResponse
reply-extraction bug, on the 08:07 kill path). First-hand read of the
current branch (base `f5374e4c`, main `5806c273`):

- `_coerce_brain_result` (`FRIDAY/src/friday/autonomous/goal_loop.py:237`)
  already reads `JSONResponse.body` and never raises; the executor wraps
  every failure as an honest step failure.
- Commit `5faac315` (TASK-IG-FRD-001-FIX-01) merged it: "executor reads
  JSONResponse bodies + never raises; run_cycle guards raising executors".
- The docstring itself records the live 2026-11-27 crash this fixed.

This lead is not a fix candidate for FRD-064. It is closed.

## 3. Memora remote-failure lead: bounded on a code read, still unproven as the spike source

Quick read of `FRIDAY/src/friday/memory/memora_client.py` (current main):

- Recall runs on a 2-worker `ThreadPoolExecutor`; the caller waits at most
  the 5 s `recall_join_deadline` and the remote leg finishes unobserved on
  its daemon thread (FRD-020 design, comment at :205–:213).
- Writes: a single immediate retry with the same idempotency key; resync
  delays bounded at (5 s, 25 s, 90 s), then the fact stays local.
- Cursor reads (`read_event_cursor`, :355) log-and-return on failure; no
  retry loop, no accumulating buffer visible on these paths.

No unbounded allocation was found on the recall / cursor-read / retry
paths from this read. The 14:42 correlation (Memora remote failures in the
minutes before the kill, cp5 §2) stays a correlation, not a mechanism.
Without per-object attribution, naming the allocating code would be a
guess — and a fix PR built on a guess is not a fix.

## 4. BLOCKED — fix PR cannot be filed until attribution is ruled

WATCH228 §F (hub #2045 comment 7222477145, 21:17 IST) and BE 21:28 §F
both demand: file the fix PR or post the block. The block, filed here:

- **What is needed:** a coordinator ruling for per-object attribution —
  either (a) an observation-only restart with tracemalloc enabled, or
  (b) an in-process snapshot endpoint. Both need a code change or a
  restart, so neither is covered by WATCH226 §D5 (read-only). Asked in
  cp5 §6.1; still unruled at this checkpoint.
- **Why it blocks:** cp5 proved the floor is ~99 MB anonymous mmap
  (67%), not the heap (28%), and the kills are ~100 MB spikes in <20 s
  with no turn in flight. No fix can name the allocating code from
  `/proc` alone. The two carried leads are now resolved without a fix
  (§2 closed, §3 bounded-but-unproven).
- **What is NOT blocked:** read-only monitoring continues (this
  checkpoint); the branch stays open; the task stays claimed by TP1.
- **If no ruling lands by the next driver run:** TP1 releases FRD-064 to
  the pool and takes TASK-EARN-017 (next in queue, AVAILABLE / muse_tp1),
  per the blocked-head rule — the ruling can re-claim FRD-064 to TP1.

VOI-045 (TP10) firing stays HELD until the fix deploys (WATCH215 §3) —
no change; TP10 cp10 (hub 7222728338, 21:23 IST) confirms the same state
from its side.

## 5. Five states

- Implemented: NO. Tested: NO. Merged: NO. Deployed: NO. Production-verified: NO.
- Investigation (this checkpoint): DONE — numbers above are first-hand live reads.

## 6. Queue

- FRD-064 (head, BLOCKED on attribution ruling) → TASK-EARN-017
  (AVAILABLE / muse_tp1) → TASK-EARN-015 (AVAILABLE / muse_tp1,
  owner-gated Contra account step) → TASK-REL-069 (AVAILABLE / muse_tp1).
  Hold ≤ 2 (1 + 1 pre-staged).
- WEB-007 (PR #2075) + FRD-062 (PR #2108) both verified MERGED on live main.
- Hub read through comment 7222826984 (Muse 7, 21:34 IST); main
  `5806c273`. No P0, no new assignment, no verdict naming for TP1.
  WATCH228 + BE 21:28 read in full.
