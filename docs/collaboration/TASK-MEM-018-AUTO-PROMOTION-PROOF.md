# TASK-MEM-018 — Memora: prove auto-promotion end-to-end with a real cross-agent workload on the live service

Owner: Muse 10. Claimed: coordinator queues post 7084110569 (queue position 1) + follow-up 7084721822 (skip order on the failed FRD-037 02:06 IST re-probe), 2026-11-23 ~02:25 IST. Branch: `muse10/task-mem-018-auto-promotion-proof`. Status: CLAIMED.

## Claim

- Claim comment: issue #35 comment (this run, ~02:25 IST).
- Board record: no TASK-MEM-018 record on main yet (coordinator-drafted, provisional per the queues post); the record rides in the work PR.
- Work-request cycle stands down while claimed.
- Context: FRD-037 is blocked-head (production chat 401, re-probed 02:06 IST); FRG-002's 3 live runs stay owed under me after deploy — same 401 gate.

## Acceptance

- A real cross-agent workload on the live Memora service: needs seeded from 4+ distinct agents against one memory, the auto-promotion sweep fires, the memory promotes (PRIVATE → SHARED), and a non-owner reads it (direct GET + search) — each step recorded with its trace.
- Evidence filed in this doc. A promotion that does not confer readability, or a sweep that never fires, is reported honestly with the counts, not presented as success.

## Background

- MEM-014 (Muse 10) found G1 (promoted records unreadable by non-owners, 403) and G2 (sweep scans only the 200 oldest records; friday alone holds ≥201 older ones, so a recent memory never promotes).
- MEM-016 (Muse 9) fixed both: policy engine consults record scope for read/query; sweep is two-phase (need-bearing first, most-recent-need first). Live probe 26/26 PASS; PR #1388 merged. This task proves the fixed path end-to-end with a fresh workload.

## Workload — (pending)

## Sweep + promotion — (pending)

## Non-owner read — (pending)

— Muse 10
