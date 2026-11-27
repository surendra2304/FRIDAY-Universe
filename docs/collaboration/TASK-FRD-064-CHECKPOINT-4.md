# TASK-FRD-064 — Checkpoint 4: the fifth kill (13:22 UTC) — the spike outruns the monitor

**Task:** FRIDAY: investigate + fix FRIDAY.service OOM-kills under chat turns.
**Owner:** Muse TP1. **Branch:** `musetp1/task-frd-064-oom-kills-chat-turns` (@ `cf49af6b`).
**Probed:** 2026-11-27 ~19:47–20:00 IST (14:17–14:30 UTC), bridge Server 3 = FRIDAY-Server,
first-hand, read-only throughout.
**Board on live main `cf49af6b`:** CLAIMED / owner `muse_tp1` / pr null / P1.
Board note (unchanged, correction still owed in the coordinator's board PR):
the record's `branch` field reads `musetp1/task-frd-064-oom-kill-root-cause`;
the real branch is `musetp1/task-frd-064-oom-kills-chat-turns` (verified via
ref read-back: head `7fb51991` before this checkpoint).

## 1. TP10's 19:33 IST report VERIFIED first-hand — FIFTH kill today

Journal (`FRIDAY.service`, Server 3), OOM-killer lines today:

- 00:56:12 / 06:21:02 / 08:07:11 / 09:37:02 / **13:22:03 UTC** — five distinct
  kills (06:21 is logged twice at the same second = one event, as in cp2).
- The 13:22 kill record: `13:22:03 "A process of this unit has been killed by
  the OOM killer"` → `13:22:05 "Failed with result 'oom-kill'"` →
  `"Consumed 5min 24.459s CPU time, 200.0M memory peak, 192.0M memory swap
  peak"`. **Both caps were exhausted at the kill: RAM 200M AND swap 192M.**
  The killed activation (PID 100296) lived 09:37 → 13:22 UTC (~3h45m).

## 2. The kill sequence — 23 seconds from warn to dead, no critical line

Monitor lines (cgroup RAM % of 200M), PID 100296, 12:30–13:22 UTC:

- 12:33 warn 76.5% (152.9 MB) → recovered <60%.
- 12:49 warn 78.5% (157.1 MB) → recovered.
- 13:05 warn 77.7% (155.3 MB) → 13:06:09 **critical 99.1%** (198.2 MB) →
  13:06:39 recovered <60% — survived.
- 13:21:40 warn 78.4% (156.7 MB) → **13:22:03 OOM kill — 23 s later, with
  no critical line in between.**

**Spike magnitude (estimate, basis stated):** RAM 156.7 → 200M (+43 MB) and
swap ~125 → 192M (+~67 MB) inside 23 s — on the order of **≥100 MB of new
anonymous memory in under 23 s**. Swap basis: cp3 measured 125–128 MB at
12:26 UTC; the killed activation's swap peak hit the 192M cap. The monitor
samples far slower than that, so the guard (warn 75% / critical 90%) never
saw the spike coming. A guard that reacts on the monitor's cadence cannot
catch this kill shape; the fix must either react in seconds or add headroom.

## 3. The 13:22 kill was NOT during a chat turn

Five minutes before the kill (13:17–13:22:10 UTC, journal, non-memory lines):

- 13:18:09–13:18:16 — a UI page load from one client: Next.js static chunks,
  favicon, `GET /api/v1/conversation/history?limit=20`, WebSocket
  `/api/ws/activity` accepted, `/api/voice/diagnostics`. No voice/chat
  request, no LiveKit session, no agent-turn lines.
- 13:19:11 — agent-watch pass: 0 topics, nothing delivered.
- Then the kill at 13:22:03.

**The "in chat turns" premise is not supported by this kill.** Zero turns
between the 09:37 restart and the 13:22 kill (cp3: newest entry 08:13:16Z;
this run: still no turn before 13:22). The driver is the idle floor plus a
fast spike, not a turn in flight. (Earlier kills may differ — cp2's 08:07
path had the `goal_loop.py:273` JSONResponse bug; that item stays carried,
not proven for this kill.)

## 4. New activation — the floor reproduces exactly

`FRIDAY.service`: active, MainPID **106781**, NRestarts **2**, active since
13:22:10 UTC. `MemoryCurrent=51,150,848` (~48.8 MB) /
`MemorySwapCurrent=117,059,584` (~111.6 MB) / `MemoryPeak=209,719,296`
(the 200M cap already touched in this activation). `/health` 200 in 1.06 s.

`/proc/106781` at ~14:17 UTC: `VmRSS 83,448 kB`, `VmSwap 114,196 kB`,
`VmSize 1,463,508 kB`, `VmPeak 1,485,760 kB`, **21 threads** (was 13 in cp3).
`smaps_rollup`: `Rss 83,448`, `Pss 63,159`, `Pss_Anon 43,620`,
`Pss_File 19,539`, `Swap 114,196` — anonymous total ≈ 43.6 + 114.2 =
**~158 MB**, the same shape as cp3's ~162 MB. The floor survives restarts.
`[heap]`: Size 42,216 kB, Rss 10,244 kB — heap again ~42 MB, not the floor.

Sawtooth continues in the new activation (all recovered, swap absorbing):

- 13:37:55 critical 91.4% (182.9 MB) → recovered <60%.
- 13:54:28 critical **100.0%** (200.0 MB) → recovered — confirms TP10.
- 14:09:59 warn 89.4% → 14:10:30 critical 99.9% (199.8 MB) → recovered.

The process survives 100% hits only because swap absorbs them — until swap
also fills, as it did at 13:22. Swap cap 192M is a second hard limit.

## 5. History — turns resumed AFTER the restart

`GET /api/v1/conversation/history`: `total` = **483** (cp3: 481, +2), newest
entry **13:58:57 UTC**. Two new turns arrived 13:55–13:58 UTC, after the
restart. The kill at 13:22 preceded them. History is still ~1–5 MB
in-process; nothing about the +2 turns changes the cp3 exoneration.

## 6. What the fix needs now

1. **Heap attribution before any fix PR — still needs coordinator
   clearance, still not granted.** No ruling in WATCH223 / WATCH224 / BE
   19:14 / BE 19:45 (BE 19:45 §F lists TP1 "RETURNED / NO ACTION"). Not done
   unilaterally. Until the mmap owner is named, no fix PR can target the
   floor.
2. **New constraint from this kill:** any in-process guard must react in
   seconds (warn → kill was 23 s), or the fix must add headroom (RAM cap
   and/or swap cap) — a monitor-cadence guard cannot catch a ≥100 MB /
   <23 s spike. Both caps exhausted at the kill, so headroom means both.
3. Carried fixable items (ride the eventual fix PR, still valid): the
   `goal_loop.py:273` `JSONResponse` reply-extraction bug (real defect, on
   the 08:07 kill path); a cap on escalation-provenance retention (spike
   suspect, unproven).
4. VOI-045 (TP10) firing stays HELD until the fix deploys (WATCH215 §3) —
   no change; TP10 re-checks each run.

## 7. Five states

- Implemented: NO. Tested: NO. Merged: NO. Deployed: NO. Production-verified: NO.
- Investigation (this checkpoint): DONE — numbers above are first-hand live reads.

## 8. Queue

- FRD-064 (head) → TASK-EARN-015 (pre-staged next, AVAILABLE / muse_tp1)
  → TASK-REL-069 (pos 3, AVAILABLE / muse_tp1) → TASK-EARN-017 (queued,
  AVAILABLE / muse_tp1). Hold ≤ 2 (1 + 1 pre-staged).
- WEB-007 (PR #2075) + FRD-062 (PR #2108) both verified MERGED on live main.
- Hub read through comment 7220540781 (INT-046-FIX-01 COMPLETE, 19:44 IST);
  main `cf49af6b`. No P0, no new assignment, no verdict naming for TP1.
