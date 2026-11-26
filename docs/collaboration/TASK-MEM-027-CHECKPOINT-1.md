# TASK-MEM-027: Memora three-section live proof run 4 — checkpoint 1 (grounding + probe package)

**Worker:** Muse TP11 · **Date:** 2026-11-27 · **Branch:** `musetp11/task-mem-027-three-section-live-proof-run-4`
**Board:** TASK-MEM-027 (Memora: three-section live proof run 4 — one real write/read/promotion cycle across private / inter-agent / universal)
**Claim:** issue #1483 comment 7200744574 (~00:10 IST, 2026-11-27).
**Deadline:** WATCH188 §6 — checkpoint 1 lands by ~05:30 IST or the task is re-slotted. This commit + hub post is the landing.

> STATUS: CHECKPOINT 1 — grounding + probe package filed. Live cycle NOT run yet: one decision is owed from the coordinator (see "Decision owed" below). No live calls were made in this checkpoint; nothing was written to the live service. The stall is owned plainly: claimed 00:11 IST, zero commits until this checkpoint (~05:10 IST, ~5h).

## Acceptance (board)

One real cycle evidenced across all three sections against the live service.

## Board record (live main `aebd481f`, verified first-hand this run)

- `id: TASK-MEM-027`, status CLAIMED, owner muse_tp11, priority P2, branch null, pr null (flip rides in the work PR).
- Board blob `0f8b45f1`, 3,090,056 bytes; record `updated_at: 2026-11-26T23:30:00+05:30`.
- Record `next_action` is stale ("In the pool - claim via hub #1483 when assigned") — the claim is recorded in the hub (7200744574) and in status/owner; the text flip rides in the work PR.
- Evidence trail: drafted by the coordinator 2026-11-24; assigned to Muse 11 queue position 3 (watch 2026-11-24 ~06:35 IST); released back to the pool by Muse 11 (hub 7199615571, 2-task limit); claimed by Muse TP11 2026-11-27 ~00:10 IST after a live pool scan (Stratex/VyralX lane exhausted — STR-078 blocked, VYR-081 footage-blocked, EARN items owner-account steps only).

## Preconditions verified live this run (~05:02–05:12 IST)

- **Main head `aebd481f`** (merge PR #2031, TASK-VYR-087, 2026-11-26 23:14:52 UTC). CI: 13 check-runs — 12 completed (success/skipped), 1 in progress (Claim Oracle Ampere A1 Instance), **0 failed**. `Deploy Specialist Fleet (Server 2)` is SKIPPED on this head — the failure WATCH188 §6 noted on `56ebae7d` (run 45901118812) does not reproduce on current main.
- **Fleet:** bridge `get_system_info` — Oracle Server 1 ONLINE, Oracle Server 2 ONLINE; public ingress `https://friday-universe.duckdns.org`. Server 2 `/opt/friday_universe` git is on branch `muse10/task-ig2-web-07-fix-01-glass-start-page` @ `410f0738` (deploy state, not main — noted, not this task).
- **Branch:** `musetp11/task-mem-027-three-section-live-proof-run-4` verified 200 @ `b74efa00ca91454104b74a8e652df55888d157d8` (claim base, merge PR #2004) before this commit; this checkpoint rebases the work onto current main `aebd481f`.
- **Roster PR #1845 MERGED** (2026-11-25 15:09:52 UTC) — no change.
- **Hub #1483** open, **2,445 comments** at check — 55 short of GitHub's 2,500-comment limit; a continuation hub will be needed soon (same as #35).
- **Usage:** 11% of free weekly limit (reset Nov 28, 9:29 PM IST; additional tokens 0% used).

## Predecessor evidence (read in full this run)

### MEM-024 run 3 — Muse 11, 2026-11-24 ~02:21 IST

`docs/collaboration/TASK-MEM-024-THREE-SECTION-PROOF-RUN3.md`, work PR #1555. All legs green on the live service:

- **M1 ladder:** write PRIVATE → owner 200 / other 404 → promote SHARED (friday, intelx) → recipients 200 / outsider 404 → search finds it (rank 1, score 1.0) → promote UNIVERSAL → outsider 200.
- **M1b:** direct PRIVATE → UNIVERSAL, in place, no dual copy (plain content).
- **M1b2:** failed-experiment lesson, direct PRIVATE → UNIVERSAL via dual copy; MEM-021 decisive check PASS (copy HMAC differs, content SHA identical).
- **M2:** auto-promotion, 9 needs → sweep → PRIVATE → SHARED, blast radius exactly 1 (MEM-016 two-phase sweep fix re-proved).
- **M3/M4:** write-time SHARED (recipient 200, non-recipient 404); direct UNIVERSAL write → 403.
- **Latency:** owner promotes 19–641 ms; sweep ~17 s; writes 742–1,485 ms; reads 10–318 ms.

### MEM-025 run 2 — Muse 8, live run 3 2026-11-24 ~12:58–13:05 IST

`docs/collaboration/TASK-MEM-025-AUTO-PROMOTION-PROOF-RUN2.md`, work PR #1627. Live proof verified: one lesson promoted PRIVATE → SHARED → UNIVERSAL by repeated need + sweep, dual copy verified first-hand (MEM-021 check PASS, both audit rows present, blast radius 1 on both sweeps). Script filed as `docs/collaboration/TASK-MEM-025-PROBE.py` — the base for the run-4 script.

### MEM-026 run 4 grounding — Muse 19, 2026-11-24; re-claimed by Muse 2

`docs/collaboration/TASK-MEM-026-GROUNDING.md`, probe `docs/collaboration/TASK-MEM-026-PROBE.py`. Checkpoint 1 was grounding + probe package only — live cycle NOT run, two decisions owed (FRD-042 deploy + live-leg route grant). Current board state (live main `aebd481f`): MEM-026 CLAIMED / muse_2 / branch `muse2/task-mem-026-three-section-proof-run4` / PR #1886 open; next action "checkpoint-2 re-grounding in work PR #1886; live cycle gated on FRIDAY deploy + route grant." The route gate is shared, not unique to MEM-027.

Script defects found and fixed across the MEM-025 runs (all carried into the run-4 script):

1. Memora listens on **port 8002** on Server 1 (not 8000).
2. `memory_type` must be lowercase `"episodic"` (uppercase → 422).
3. MEM-021 check reads provenance `hmac_signature` (not `hmac_prefix`, which does not exist) and `promoted_from_memory_id` (not `promoted_from`).
4. `expect()` must coerce to bool (a trailing string in an `and`-chain raised `TypeError` after logging PASS).
5. Sweep expects must accept `from_scope` or `scope` (dual-copy promotion records omit `from_scope`).

## Thresholds (verified first-hand on main `aebd481f` this run)

From `Memora/core/memory/promotion.py`, lines 101–105 (unchanged from the MEM-026 grounding):

- PRIVATE → SHARED: `SHARED_MIN_DISTINCT_AGENTS = 2`, `SHARED_MIN_TOTAL_NEEDS = 3`.
- SHARED → UNIVERSAL: `UNIVERSAL_MIN_DISTINCT_AGENTS = 4`, `UNIVERSAL_MIN_TOTAL_NEEDS = 8`, `UNIVERSAL_MIN_OUTSIDE_AGENTS = 2` (needers NOT already on the SHARED allow-list).

## Method (probe package filed in this commit)

- `docs/collaboration/TASK-MEM-027-PROBE.py` (455 lines, adapted from `TASK-MEM-026-PROBE.py`, syntax-checked): legs M1 ladder, M2 auto-promotion lesson (dual copy + MEM-021 check), M3 write-time SHARED control, M4 direct UNIVERSAL write control (expect 403). Fresh distinctive phrases per leg (no collision with run-2/run-3 records in the same search index): M1 `cobalt summit ninefold opal`, M2 `crimson tide fourfold jasper`, M3 `amber ridge sixfold pearl`.
- Run ON Server 1 (localhost Memora, default `http://127.0.0.1:8002`). Keys read from the service's own env file at runtime on the server and NEVER printed or copied: only key names and presence are logged. Test data content-prefixed `MUSETP11-TEST-MEM-027`, provenance `test_data: true`, `task: TASK-MEM-027`. No live data overwritten, no service restarted. Launch with nohup in the background (bridge 45 s per-call transport limit); poll for `SUMMARY.json`.
- Outputs: numbered JSON files in the outdir (default `/tmp/musetp11_mem027/`), one per call, each with status + elapsed_ms. Exit 0 only if every leg passes.

## Decision owed — live-leg execution route

- The bridge client in this workspace is read-only by design (`ALLOWED_TOOLS = {get_system_info, read_text}` in `custom.friday-bridge/bin/client.py` — no `run_shell`; the other 29 server tools are untested and blocked until reviewed and added by name). The probe must execute ON Server 1, and its keys must be read at runtime there.
- The owner order of 2026-11-26 18:25:56 IST + clearance `7200564540` settle the `run_shell` grant per Burn Enforcer 04:58 §F ("RUN THE LEG OR RELEASE"), but the MEM-025 grant was scoped to that probe only, and MEM-026 grounding recorded a fresh grant (or a named drill assist) as owed for its own run — MEM-026 is still gated on it (PR #1886).
- **Ask to the coordinator: confirm the MEM-027 execution route** — standing clearance `7200564540` applied to this probe, or a named drill assist — and the run starts immediately. Until then the live cycle is blocked-with-reason, not stalled by inaction.

## Next

1. Run the live cycle once the route is confirmed; file the evidence (checkpoint 2) + work PR. Board flip CLAIMED → IN_REVIEW rides in the work PR.
2. Work-request task stays cancelled — task held (MEM-027 claimed); not re-created.

— Muse TP11
