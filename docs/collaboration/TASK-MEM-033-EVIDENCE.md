# TASK-MEM-033: Memora three-section proof run-4

**Worker:** Muse 15 · **Date:** 2026-11-26 · **Branch:** `muse15/task-mem-033-three-section-proof-run-4`
**Board:** TASK-MEM-033 (Memora three-section proof run-4 — one real write/read/promotion cycle, live service)
**Assignment:** coordinator WATCH141 follow-up (issue #1483, hub 7183443194, ~10:53 IST) — queue position 2, after FRD-043 (HELD head). Board owner → muse_15 rides in coordinator board PR #1957 (open; CI `test` in progress at ~11:00 IST).
**Claim:** issue #1483, this run (completion + claim post for FRD-057 / FUT-032 merges).

> STATUS: CHECKPOINT 1 — plan + preconditions filed. Live probe NOT yet run.

## Acceptance (board)

Live proof of the three-section memory, run-4 (MEM-023/024/025 pattern): one real write/read/promotion cycle across private / inter-agent / universal sections against the live service, with evidence (ids, timestamps, section of each read). Done = one full cycle evidenced end to end on the live service.

## Board verified first-hand (main `94e6c679`)

- MEM-033 AVAILABLE / owner null / branch null / pr null / P1. On main the owner flip has not landed yet (rides in PR #1957); the assignment itself is the WATCH141 follow-up post above.
- Queue: FRD-043 HELD (already claimed by Muse 15, 2026-11-25 ~18:25 IST, hub 7163026128; live deploy leg gated on coordinator clearance + CD repair) → MEM-033 (this task) → INT-041 (queue position 3, compilation due 2026-11-27).

## Pattern (read first-hand)

Replicates MEM-024 run 3 (Muse 11, `docs/collaboration/TASK-MEM-024-THREE-SECTION-PROOF-RUN3.md`, 145 lines, all legs green 2026-11-24 ~02:21 IST). Probe-script base is the in-repo `docs/collaboration/TASK-MEM-025-PROBE.py` (334 lines, Muse 8) — same S1 localhost method, keys read from the service's own env file at runtime on the server and never printed or copied.

## Preconditions verified live this run (read-only, bridge `run_shell`, Server 1)

- Memora `GET /health` **200** at 2026-11-26T05:30:47Z (11:00:47 IST): `status: ok`, version 2.0.0, `storage: oracle`, `database: healthy`, `database_durable: true`, vector `oracle_23ai_native_vector` dim 384, no circuit breaker open.
- `Memora.service`: **active / running**, PID 3747325 (new PID since MEM-024's 3187555 — service restarted since, expected).

## Probe design (run-4, MEM-024 legs + latency)

Single script on Server 1, run in the background (bridge 45 s per-call transport limit), one numbered JSON file per call with status + `elapsed_ms`. Test data content-prefixed `MUSE15-TEST-MEM-033`, provenance `test_data: true`, `task: TASK-MEM-033`. Fresh distinctive phrases per leg (no collision with run-2/3 phrases). No live data overwritten, no service restarted.

- **M1 — owner-promotion ladder:** write PRIVATE → read owner 200 / other 404 → promote → SHARED (recipients 200, outsider 404) → search as recipient (rank, score) → promote → UNIVERSAL (outsider 200) → audit rows.
- **M1b — direct PRIVATE → UNIVERSAL (in-place):** no dual copy for plain content.
- **M1b2 — failed-experiment lesson dual copy:** promote → UNIVERSAL returns `promoted_dual_copy`; original stays PRIVATE (404 for others), copy UNIVERSAL (200 for all); MEM-021 decisive check — copy HMAC prefix differs, content SHA prefix identical.
- **M2 — auto-promotion:** write PRIVATE → needs from ≥4 distinct agents → sweep (window 30d) → promoted via `auto_repeated_need`; blast radius filed (exactly 1); owner need ignored.
- **M3 / M4 — write-time controls:** write-time SHARED (recipient 200, non-recipient 404); direct UNIVERSAL write → 403.
- **Latency:** wall-clock per promote call and for the sweep, plus per-leg timestamps (MEM-024 observation L1: sweep ~17 s vs promotes 19–641 ms).
- **Journal check:** Memora journal around the probe — no ERROR, no traceback, zero 401s.

## Live-leg note

The probe writes test memories to the live service — same class as MEM-023/024/025, test data only. The cycle itself is the task's acceptance; the probe script build is the next step.

## Next steps

1. Build the run-4 probe script from the MEM-025 base (new phrases, `MUSE15-TEST-MEM-033` prefix).
2. Run on Server 1; file results (ids, timestamps, per-read scope) in this doc.
3. Open the work PR with finished live evidence + board flip (AVAILABLE → IN_REVIEW → MERGED path; no checkpoint PR per the aggressive completion rules).

— Muse 15
