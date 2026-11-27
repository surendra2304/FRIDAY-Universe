# TASK-VOI-045 — Checkpoint 1 (scoping)

Worker: Muse TP10. Claimed 2026-11-27 (hub #2045 claim post accompanies this commit).

## Task

FRIDAY voice acceptance run 28 — the next calm-window run after VOI-044 (run 27).
Acceptance (WORK_BOARD.yaml, TASK-VOI-045):
- Run the probes in the next calm window; file per-probe latency + pass/fail.
- Speed is the headline metric. A correct answer after long silence counts as failing.

## Precedent (run 27, to be re-read first-hand before any live leg)

- VOI-044 (Muse 10) MERGED via PR #1952 (merge e8f50ef6).
- Evidence: `docs/collaboration/TASK-VOI-044-ACCEPTANCE-RUN-27.md`.
- Board summary of run 27: greeting onset 0.54 s vs 8 s bar, latency PASS 7/7;
  scorer overall UNVERIFIED on the followup attribution leg only; one real defect —
  truncated fragment (VOI-043 symptom, pre-VOI-043 build).
- Run 28 must state explicitly whether the truncated-fragment defect still reproduces.

## Plan

1. Read the run-27 evidence doc first-hand; reuse its probe set and latency bars
   unless the doc itself says otherwise. Any probe change is called out in the
   run-28 evidence, not made silently.
2. Calm window = FRIDAY voice stack (FRIDAY-Server: FRIDAY + FRIDAY-Voice,
   LiveKit Cloud + Gemini Live) stable with no deploy/restart in flight.
   Confirm stack state read-only before firing; coordinate on hub #2045 first.
3. Fire each probe exactly once in the calm window; record per-probe latency
   (onset + completion) and pass/fail against the run-27 bars.
4. File `docs/collaboration/TASK-VOI-045-ACCEPTANCE-RUN-28.md`; open one work PR;
   paired verification by a different chat owed before merge.

## This run

Scoping only. No live legs fired, no bridge calls, no server moves.

Five states: implemented NO / tested NO / merged NO / deployed NO / production-verified NO.

— Muse TP10
