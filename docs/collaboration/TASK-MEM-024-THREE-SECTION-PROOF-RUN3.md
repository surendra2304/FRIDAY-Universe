# TASK-MEM-024: Memora three-section live proof, run 3

**Worker:** Muse 11 · **Date:** 2026-11-24 · **Branch:** `muse11/task-mem-024-three-section-proof-run3`
**Board:** TASK-MEM-024 (Memora three-section live proof run 3 after the FRD-038 401 fix lands — one real write/read/promotion cycle across private / inter-agent / universal sections against the live service, with promotion latency filed)
**Assignment:** coordinator queue top-up 2026-11-23 ~18:30 IST (board next_action) + Muse follow-up 2026-11-24 ~00:41 IST (blocked-head rule: FRD-038 MERGED, MEM-017 blocked). **Claim:** issue #1483 comment 7111300983 (~00:46 IST).

> STATUS: CHECKPOINT 1 — probe design filed, preconditions verified. Live probe NOT yet run: bridge `run_shell` stalled 0/5 (see Blocker).

## Acceptance (board)

One real write/read/promotion cycle across private / inter-agent / universal sections against the live service, with promotion latency filed.

## Preconditions verified live, 2026-11-24 ~00:44–00:51 IST

- Board record on main 49126a41 (board blob fe731e7d): MEM-024 AVAILABLE, owner muse_11, branch null, pr null. Queue: FRD-038 → MEM-017 → MEM-024.
- FRD-038 fix landed: work PR #1535 merged 2026-11-23 23:40 IST (merge 8c0ef142, CI 9/9 green). The fix is merged, not deployed; the deploy + live acceptance leg is TASK-FRD-042 (Muse 5). This task has no FRIDAY web-chat leg, so the undeployed fix does not block it.
- Memora live and healthy: `oracle_get_logs` (Memora.service, Server 1) 00:50:44–00:51:15 IST — `GET /health` 200 throughout, PID 3187555, `GET /v1/events?after_id=1951` 200 OK. Zero 401s in the window.
- Futuris cursor 401s GONE: `GET /v1/events/cursor?consumer_id=futuris-cloud-v1` 200 OK at 00:51:00 and 00:51:15 IST (was 401 every ~15s through 2026-11-23). Separate consumer, now healthy — noted, not this task.
- Bridge: `get_system_info` OK, both Oracle servers ONLINE (bridge v1.30.0).

## Probe design (replicates MEM-023 run 2, with latency)

Method per `docs/collaboration/TASK-MEM-023-THREE-SECTION-PROOF-RUN2.md` (Muse 10, 2026-11-23): direct Memora API calls from Server 1, `X-Agent-Name` + per-agent `X-API-Key`, keys read from the service's own env file at runtime on the server and never printed or copied. Test data content-prefixed `MUSE11-TEST-MEM-024`, provenance `test_data: true`, `task: TASK-MEM-024`. No live data overwritten, no service restarted.

- **M1 — owner-promotion ladder:** write PRIVATE (sentinel) → read as owner 200 / as other 404 → promote → SHARED (read as friday, intelx 200; as futuris 404) → search as recipient (rank, score) → promote → UNIVERSAL (read as futuris 200) → audit rows.
- **M1b2 — failed-experiment lesson dual copy:** write PRIVATE with failed-experiment provenance → promote → UNIVERSAL → `promoted_dual_copy`, original stays PRIVATE (404 for others), copy UNIVERSAL (200 for all), MEM-021 decisive check: copy HMAC prefix differs from original, content SHA prefix identical; distinctive search finds the copy for all three audiences.
- **M2 — auto-promotion:** write PRIVATE → 9 needs (friday×2, intelx×1, futuris×3, cortex×3), owner need ignored → sweep (window 30d) → promoted via `auto_repeated_need`, blast radius filed → reads + audit row.
- **M3 / M4 — write-time controls:** write-time SHARED (recipient 200, non-recipient 404); direct UNIVERSAL write → 403.
- **Latency (new in run 3):** wall-clock latency filed for every promote call and for the sweep (time from sweep request to promoted state visible on read), plus per-leg timestamps.
- **Journal check:** Memora journal around the probe — no ERROR, no traceback.

## Blocker

Bridge `run_shell` stalled 0/5 between ~00:47–00:57 IST: every call ends in `TimeoutError: The read operation timed out` in the MCP transport (45s client timeout), on Server 1 AND Server 2, even for `echo ok`. `get_system_info` and `oracle_get_logs` succeed in the same window, so the bridge is up and the `run_shell` tool path itself is stalled. The probe script must run on Server 1 via `run_shell`, so the live probe cannot execute until that tool recovers. Next step: retry `run_shell` in the next self-check; if it stays down, escalate to Muse (bridge-outage class — cf. the MEM-023 bridge outage 2026-11-23 13:32–14:06 IST, which recovered on its own).

## Test data left behind

None yet — no probe calls have run.

— Muse 11
