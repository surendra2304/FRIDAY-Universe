# TASK-MEM-024: Memora three-section live proof, run 3

**Worker:** Muse 11 · **Date:** 2026-11-24 · **Branch:** `muse11/task-mem-024-three-section-proof-run3`
**Board:** TASK-MEM-024 (Memora three-section live proof run 3 after the FRD-038 401 fix lands — one real write/read/promotion cycle across private / inter-agent / universal sections against the live service, with promotion latency filed)
**Assignment:** coordinator queue top-up 2026-11-23 ~18:30 IST (board next_action) + Muse follow-up 2026-11-24 ~00:41 IST (blocked-head rule: FRD-038 MERGED, MEM-017 blocked). **Claim:** issue #1483 comment 7111300983 (~00:46 IST).

> STATUS: COMPLETE — all legs green. Live probe ran 2026-11-24 ~02:21–02:22 IST (script `/tmp/muse11_mem024/probe_mem024.py` on Server 1, 48 calls, raw responses `/tmp/muse11_mem024/*.json`). Work PR #1555 open, awaiting Muse merge. Board flip CLAIMED → IN_REVIEW rides in this PR.

## Acceptance (board)

One real write/read/promotion cycle across private / inter-agent / universal sections against the live service, with promotion latency filed.

## Verdict

The three-section ladder works end to end on the live service with the FRD-038 401 fix merged (PR #1535, 8c0ef142): owner promotion PRIVATE → SHARED → UNIVERSAL confers readability at every rung, and search finds the promoted records for their audiences. The MEM-021 decisive check passes on a fresh copy (HMAC re-signed under its own id, content SHA identical). Auto-promotion via needs + sweep works with blast radius exactly 1. No new gaps. One latency observation (L1): the sweep takes ~17 s while owner promotes take 19–641 ms.

## Preconditions verified live, 2026-11-24 ~00:44–00:51 IST

- Board record on main 49126a41 (board blob fe731e7d): MEM-024 AVAILABLE, owner muse_11, branch null, pr null. Queue: FRD-038 → MEM-017 → MEM-024.
- FRD-038 fix landed: work PR #1535 merged 2026-11-23 23:40 IST (merge 8c0ef142, CI 9/9 green). The fix is merged, not deployed; the deploy + live acceptance leg is TASK-FRD-042 (Muse 5). This task has no FRIDAY web-chat leg, so the undeployed fix does not block it.
- Memora live and healthy: `oracle_get_logs` (Memora.service, Server 1) 00:50:44–00:51:15 IST — `GET /health` 200 throughout, PID 3187555, `GET /v1/events?after_id=1951` 200 OK. Zero 401s in the window.
- Futuris cursor 401s GONE: `GET /v1/events/cursor?consumer_id=futuris-cloud-v1` 200 OK at 00:51:00 and 00:51:15 IST (was 401 every ~15s through 2026-11-23). Separate consumer, now healthy — noted, not this task.
- Bridge: `get_system_info` OK, both Oracle servers ONLINE (bridge v1.30.0).

## Probe design (replicates MEM-023 run 2, with latency)

Method per `docs/collaboration/TASK-MEM-023-THREE-SECTION-PROOF-RUN2.md` (Muse 10, 2026-11-23): direct Memora API calls from Server 1, `X-Agent-Name` + per-agent `X-API-Key`, keys read from the service's own env file at runtime on the server and never printed or copied. Test data content-prefixed `MUSE11-TEST-MEM-024`, provenance `test_data: true`, `task: TASK-MEM-024`. No live data overwritten, no service restarted. Fresh distinctive phrases per leg (no collision with run-2 records in the same search index). Single script, all legs: M1 ladder, M1b direct UNIVERSAL (in-place), M1b2 failed-experiment lesson (dual copy), M2 needs + sweep, M3/M4 controls. Local copy of the script: `~/workspace/muse11_mem024/probe_mem024.py` (this worker's workspace).

- **M1 — owner-promotion ladder:** write PRIVATE (sentinel) → read as owner 200 / as other 404 → promote → SHARED (read as friday, intelx 200; as futuris 404) → search as recipient (rank, score) → promote → UNIVERSAL (read as futuris 200) → audit rows.
- **M1b2 — failed-experiment lesson dual copy:** write PRIVATE with failed-experiment provenance → promote → UNIVERSAL → `promoted_dual_copy`, original stays PRIVATE (404 for others), copy UNIVERSAL (200 for all), MEM-021 decisive check: copy HMAC prefix differs from original, content SHA prefix identical; distinctive search finds the copy for all three audiences.
- **M2 — auto-promotion:** write PRIVATE → 9 needs (friday×2, intelx×1, futuris×3, cortex×3), owner need ignored → sweep (window 30d) → promoted via `auto_repeated_need`, blast radius filed → reads + audit row.
- **M3 / M4 — write-time controls:** write-time SHARED (recipient 200, non-recipient 404); direct UNIVERSAL write → 403.
- **Latency (new in run 3):** wall-clock latency filed for every promote call and for the sweep (time from sweep request to promoted state visible on read), plus per-leg timestamps.
- **Journal check:** Memora journal around the probe — no ERROR, no traceback.

## M1 — the owner-promotion ladder, 02:21 IST

Memory `c6c45e86-8da5-486d-ab88-0d6126e37b78`, namespace `memora://sentinel/private`, owner `sentinel`, created 2026-11-24 ~02:21 IST. Distinctive phrase: `zephyr atlas threefold emerald`.

| Step | Call | Result |
| --- | --- | --- |
| Write PRIVATE | `POST /v1/memories` (sentinel) | **201** (1485.5 ms). |
| Read as owner | `GET /v1/memories/{id}` (sentinel) | **200**, `scope: PRIVATE`. |
| Read as other | `GET /v1/memories/{id}` (friday) | **404** — existence hidden from non-owners. |
| Promote → SHARED | `POST /v1/promotion/promote` `{target_scope: SHARED, shared_with: [friday, intelx]}` (sentinel) | **200** (235.9 ms) `{status: promoted, scope: SHARED, from_scope: PRIVATE, path: owner_judgement}`. |
| Read as recipient | `GET /v1/memories/{id}` (friday, intelx) | **200**, `scope: SHARED`. |
| Read as outsider | `GET /v1/memories/{id}` (futuris) | **404** not found. |
| Search as recipient | `GET /v1/memories/search?q=zephyr atlas threefold emerald&limit=50` (friday) | **200**, exactly 1 result: M1 at **rank 1, keyword_score 1.0**. |
| Promote → UNIVERSAL | `POST /v1/promotion/promote` `{target_scope: UNIVERSAL}` (sentinel) | **200** (19.1 ms) `{status: promoted, scope: UNIVERSAL, from_scope: SHARED, path: owner_judgement}` — no dual copy (plain content, not a lesson). |
| Read as outsider | `GET /v1/memories/{id}` (futuris) | **200**, `scope: UNIVERSAL`. |
| Read as recipient | `GET /v1/memories/{id}` (friday) | **200**, `scope: UNIVERSAL`. |
| Audit | `GET /audit?action=MEMORY_SCOPE_PROMOTED&limit=20` (memora) | **200**, 17 rows returned (includes M1's two promotion rows). |

## M1b — direct PRIVATE → UNIVERSAL (in-place path), 02:21 IST

Memory `48249b7e-28eb-422c-9898-9b5ee0361ad9`, plain content (no lesson provenance). Promote → UNIVERSAL **200** (59.2 ms) `{status: promoted, scope: UNIVERSAL, from_scope: PRIVATE}` with **no** `universal_copy_id` — scope mutated in place, no copy. Correct per `Memora/core/memory/promotion.py:816-819` (dual copy only for failed-experiment lessons). Reads as friday and futuris: **200**, `scope: UNIVERSAL`. Distinctive phrase: `cobalt lantern eightfold ruby` (shared with M1b2 by design, as in run 2).

## M1b2 — failed-experiment lesson, direct PRIVATE → UNIVERSAL (dual copy), 02:21 IST

Original `5f482533-59dd-49a7-b5c9-968ad191f34d`, copy `f06b9ff7-bece-45c5-bcc9-7af35763eeb9`, created 2026-11-24 ~02:21 IST.
Provenance: `failed_experiment: true`, `experiment_outcome: failed`, `lesson_type: failed_experiment`.

| Step | Call | Result |
| --- | --- | --- |
| Write PRIVATE | `POST /v1/memories` (sentinel) | **201** (752.8 ms). |
| Promote → UNIVERSAL | `POST /v1/promotion/promote` `{target_scope: UNIVERSAL}` (sentinel) | **200** (640.5 ms) `{status: promoted_dual_copy, scope: PRIVATE, to_scope: UNIVERSAL, path: owner_judgement, universal_copy_id: f06b9ff7-...}`. |
| Original as other | `GET /v1/memories/{orig}` (friday) | **404** — original stays PRIVATE. |
| Original as owner | `GET /v1/memories/{orig}` (sentinel) | **200**, `scope: PRIVATE`. |
| Copy as recipient | `GET /v1/memories/{copy}` (friday) | **200**, `scope: UNIVERSAL`. |
| Copy as outsider | `GET /v1/memories/{copy}` (futuris) | **200**, `scope: UNIVERSAL`. |
| Copy provenance | `GET /v1/memories/{copy}` (sentinel) | `signature_version: v1`, `hmac_prefix: 21a0ae220561`, `content_sha256` prefix `b05cc33f9dd6`, `promoted_from: 5f482533-...`. |
| Original provenance | `GET /v1/memories/{orig}` (sentinel) | `hmac_prefix: 9cc069a385b5`, `content_sha256` prefix `b05cc33f9dd6`. |

**MEM-021 decisive check — PASS.** The copy's HMAC prefix differs from the original's (re-signed under its own id, the MEM-021 fix) while the content SHA prefix is identical (content preserved verbatim). Distinctive search (`cobalt lantern eightfold ruby`, limit 50) finds the copy for all three audiences immediately after promotion — friday rank 2 (0.8923), sentinel rank 2 (0.8946), futuris rank 2 (0.8923). Rank 2, not rank 1, is expected: the M1b record `48249b7e-...` shares the same distinctive phrase and scores 1.0 in every audience's results.

## M2 — auto-promotion (needs + sweep), 02:21–02:22 IST

Memory `c0f410fa-d07d-487d-9b17-7ec657041dc2`, owner `sentinel`, created 2026-11-24 ~02:21 IST. Distinctive phrase: `marble tide sixfold amber`.

| Step | Call | Result |
| --- | --- | --- |
| Write PRIVATE | `POST /v1/memories` (sentinel) | **201**. |
| Needs before | `GET /audit?action=MEMORY_NEED_RECORDED&limit=500` (memora) | 0 rows for M2. |
| 9 needs | `POST /v1/promotion/need` (friday×2, intelx×1, futuris×3, cortex×3) | **200** each. |
| Owner need | `POST /v1/promotion/need` (sentinel) | **200** `{status: owner_need_ignored}` — correct. |
| Sweep | `POST /v1/promotion/sweep` `{window_days: 30}` (memora) | **200** (16,896.3 ms) `{count: 1, promotions: [{status: promoted, memory_id: c0f410fa-..., scope: SHARED, to_scope: SHARED, path: auto_repeated_need, from_scope: PRIVATE}]}`. |
| Owner read | `GET /v1/memories/{id}` (sentinel) | **200**, `scope: SHARED` (sweep-to-visible 16,993.1 ms). |
| Needer read | `GET /v1/memories/{id}` (friday) | **200**, `scope: SHARED`. |
| Audit | `GET /audit?action=MEMORY_SCOPE_PROMOTED&limit=20` (memora) | **200**, M2 row present: `promoted_by: memora`, `path: auto_repeated_need`, `reason: repeated cross-agent need`, `shared_with: [cortex, friday, futuris, intelx]`, evidence `distinct_agents: 4, total_needs: 9, window_days: 30`. |

**Blast radius exactly 1** — only M2 was promoted. The sweep promoted the minutes-old M2 on the first pass, confirming the MEM-016 two-phase sweep fix live (run 3 re-proof).

## M3 / M4 — write-time controls, 02:22 IST

| Step | Call | Result |
| --- | --- | --- |
| M3 write-time SHARED | `POST /v1/memories` `{scope: SHARED, shared_with: [friday]}` (sentinel) | **201** (805.0 ms), id `1261eb3e-b21d-4c3e-bc75-6cde2417867b`. |
| M3 as recipient | `GET /v1/memories/{id}` (friday) | **200**, `scope: SHARED`. |
| M3 as non-recipient | `GET /v1/memories/{id}` (intelx) | **404**. |
| M4 direct UNIVERSAL write | `POST /v1/memories` `{scope: UNIVERSAL}` (sentinel) | **403** `{detail: Only the Memora service identity may author UNIVERSAL memories.}` — correct. |

## Latency (new in run 3)

Wall-clock per call, measured in the probe script (Server 1, localhost). All 48 calls logged with `elapsed_ms` in `/tmp/muse11_mem024/<phase>-<nn>.json`.

| Call | Latency |
| --- | --- |
| M1 promote → SHARED | 235.9 ms |
| M1 promote → UNIVERSAL | 19.1 ms |
| M1b promote → UNIVERSAL (direct) | 59.2 ms |
| M1b2 promote → UNIVERSAL (dual copy) | 640.5 ms |
| M2 sweep (window 30d) | 16,896.3 ms |
| M2 sweep → promoted state visible on read | 16,993.1 ms |
| Writes (with embedding) | 742.4–1,485.5 ms |
| Reads / searches | 10.2–318.4 ms |

**Observation L1 (not a gap):** the sweep takes ~17 s — ~25–850× the owner-promote calls. No latency bar exists in the acceptance (latency filed is the requirement); the sweep's cost is filed here for the coordinator. Promotion itself is fast (19–641 ms).

## Journal check

Memora journal, 200 lines covering the probe window 02:21–02:24 IST: **no ERROR, no traceback, zero 401s**. Every probe call logged with its expected status (including the 404s and the M4 403). The sweep logged `POST /v1/promotion/sweep 200 OK` at 02:21:57 IST. Memora PID 3187555 throughout (same PID as 00:50 IST — no restart during the run).

## Memora 401 fix holds (re-verified this run)

- `GET /health` **200** at 02:17:03 IST (`status: ok`, `storage: oracle`, `database: healthy`, `database_durable: true`, vector `oracle_23ai_native_vector` dim 384, version 2.0.0).
- `GET /v1/events/cursor?consumer_id=friday-cloud` **200** at 02:16:36 IST; `consumer_id=futuris-cloud-v1` **200** at 02:16:11 / 02:16:26 / 02:16:42 IST; `/v1/events?after_id=1951` **200** throughout. Zero 401s in the 02:16–02:24 IST windows.

## Blocker — RESOLVED

Bridge `run_shell` stalled 0/5 between ~00:47–00:57 IST and was flaky through ~01:35 IST (bridge down 01:29–01:35 IST, recovered ~01:44 IST per other workers). Recovered this run: `list-tools` OK (×3), `run_shell echo ok` Server 1 OK 02:16:45 IST, Memora `/health` curl 200, `oracle_get_logs` OK. Probe script copied to Server 1 byte-identical (14,104 bytes, `py_compile` clean) and run in the background (PID 3252965, started 02:21:31 IST, finished ~02:22 IST) to stay inside the bridge's 45 s per-call transport limit. No further bridge action needed.

## Gaps

None. All acceptance legs green on the live service with the FRD-038 401 fix merged.

## Test data left behind (cleanup path)

- M1 `c6c45e86-8da5-486d-ab88-0d6126e37b78` — scope UNIVERSAL, namespace `memora://sentinel/private`, content prefixed `MUSE11-TEST-MEM-024`.
- M1b `48249b7e-28eb-422c-9898-9b5ee0361ad9` — scope UNIVERSAL, same namespace.
- M1b2 original `5f482533-59dd-49a7-b5c9-968ad191f34d` — scope PRIVATE; copy `f06b9ff7-bece-45c5-bcc9-7af35763eeb9` — scope UNIVERSAL, same namespace.
- M2 `c0f410fa-d07d-487d-9b17-7ec657041dc2` — scope SHARED, same namespace.
- M3 `1261eb3e-b21d-4c3e-bc75-6cde2417867b` — scope SHARED, same namespace.
- Cleanup (not done here — out of scope for a proof run): the owner or the memora service identity can remove the memories via `POST /v1/memories/{id}/forget` or `DELETE /v1/memories/{id}`. All memories carry `provenance.test_data: true` / `task: TASK-MEM-024`.

— Muse 11
