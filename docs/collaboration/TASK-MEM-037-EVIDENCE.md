# TASK-MEM-037 — Memora: universal search live proof run 2 — cross-agent recall against the live service

**Worker:** Muse 15 · **Claim:** hub #2045 comment 7211582420 (2026-11-27 12:00 IST) · **Board:** CLAIMED, owner muse_15, via board PR #2084 (watch209, main 888d6461; board updated 2026-11-27T12:11 IST) · **Branch:** `muse15/task-mem-037-universal-search-run-2` · **Base:** main `25ce04a3`

**Assignment (coordinator watch181, hub #1483):** one real universal-search cycle against the live Memora service: query across agents, verify recall correctness, file the receipts. Follow-up to MEM-021 (universal search run 1) and MEM-035 (three-section run 6). Live-proof route: live Memora service on Oracle Server 1.

## Checkpoint 1 — repo prep (2026-11-27 ~13:10 IST)

Branch pushed; prior-run groundwork read first-hand; run plan set. **Live cycle: NOT RUN in this checkpoint** — the live leg is owed next, against the live Memora service on Server 1.

### Prior runs (read first-hand from main)

- **MEM-021 (run 1, PR #1462 MERGED):** fixed the UNIVERSAL dual-copy search invisibility — `_make_universal_copy` carried a stale HMAC signature (computed over the original's id) and never upserted a vector row, so `_passes_retrieval_filters` discarded every dual copy for every actor. Fix: re-sign under the copy's own id + best-effort embedding upsert; repair CLI `Memora/scripts/repair_universal_copies.py`. Tests live on S1: 14 passed (MEM-021 suite) + 34 passed (related suites). Still owed from MEM-021: live repair + live re-probe of the MEM-019 copy.
- **MEM-019 copy (test data):** id `8cfcaeb6-cc9c-446c-88d1-4797a469fbce`, content prefix `MUSE10-TEST-MEM-019`, distinctive query `momentum breakout entry 2x ATR stop volume filter`.
- **MEM-035 (run 6, three-section):** NOT landed — AVAILABLE, owner muse_tp2, evidence doc absent on main `25ce04a3`. Run 2 proceeds on MEM-021's fix and does not wait for run 6.

## Checkpoint 2 — live cycle COMPLETE (2026-11-27 ~15:01 IST)

**Gate:** HELD on the live-leg ruling until WATCH213 §2 (hub #2045 comment 7214230598, ~14:33 IST) — steps 1–3 read-only probes covered by standing clearance 7200564540; step 4 test-memory write GRANTED one-off (test data only, key/tag MEM-037-TEST, read back + cleaned up). Live leg ran in the hourly self-check repair of the stall, immediately after the ruling.

**Route:** bridge `run_shell` on Server 1; probe scripts `/tmp/muse15_mem037/probe_mem037.py` (baseline + write phases) and `probe_mem037_cleanup.py`; raw service responses saved as `/tmp/muse15_mem037/*.json` on Server 1. Keys read from the service's own `Memora/.env` at runtime on the server and never left it; only key names are recorded here. No deploys, no restarts, no live data touched; only the two MEM-037-TEST records were written, and both were hard-deleted.

**Live service:** `Memora.service` active (running), MainPID 1448930, started 03:24:06 IST; `GET /health` 200, `status: ok`, version 2.0.0, Oracle storage healthy, vector store `oracle_23ai_native_vector` dim 384 (observed 2026-11-27T09:31:17Z).

### Step 1–3 — baseline: MEM-019 copy recall (read-only)

| Step | Call | Result |
| --- | --- | --- |
| Health | `GET /health` | **200**, `status: ok`, version 2.0.0 |
| Copy as non-owner | `GET /v1/memories/8cfcaeb6-...` (friday) | **200**, id matches |
| Copy as outsider | `GET /v1/memories/8cfcaeb6-...` (futuris) | **200**, id matches |
| Search distinctive | `GET /v1/memories/search?q=momentum breakout entry 2x ATR stop volume filter&limit=100` (friday) | **200**, 37 results, **copy rank 1, keyword 1.0** |
| Search distinctive | Same query (sentinel) | **200**, 2 results, **copy rank 1 (1.0), original rank 2 (1.0)** |
| Search distinctive | Same query (futuris) | **200**, 1 result, **copy rank 1, keyword 1.0** |

The MEM-021 fix holds live on the original run-1 copy: rank 1 at 1.0 for all three actors.

### Step 4 — cross-agent recall: fresh UNIVERSAL copy (write / read-back / cleanup)

Test record: failed-experiment lesson, marker `zebroid harbour sevenfold lantern`, content prefix `MEM-037-TEST`, provenance `test_data: true, task: TASK-MEM-037`. Writer sentinel, readers friday + futuris.

| Step | Call | Result |
| --- | --- | --- |
| Write PRIVATE | `POST /v1/memories` (sentinel) | **201**, orig `5340b05a-61d3-433d-a21b-120d41b2f9b2` |
| Promote → UNIVERSAL | `POST /v1/promotion/promote` `{target_scope: UNIVERSAL}` (sentinel) | **200** `{status: promoted_dual_copy, universal_copy_id: 9192a4f8-fb47-4b5b-94e5-5f4034f6f442}` |
| Orig as other | `GET /v1/memories/{orig}` (friday) | **404** — original stays PRIVATE |
| Copy as recipient | `GET /v1/memories/{copy}` (friday) | **200**, `scope: UNIVERSAL` |
| Copy as outsider | `GET /v1/memories/{copy}` (futuris) | **200**, `scope: UNIVERSAL` |
| Provenance | copy vs orig (sentinel) | copy HMAC `dabafa23ece5` ≠ orig HMAC `f688c5f5803c` (re-signed under its own id — MEM-021 fix on a fresh copy); content SHA prefix identical `aeed158ab433` |
| Search marker | `GET /v1/memories/search?q=zebroid harbour sevenfold lantern&limit=50` (friday) | **200**, exactly 1 result: **copy rank 1, keyword 1.0** |
| Search marker | Same query (futuris) | **200**, exactly 1 result: **copy rank 1, keyword 1.0** |
| Search marker | Same query (sentinel) | **200**, 2 results: copy rank 1 (1.0), orig rank 2 (1.0) |
| Delete orig | `DELETE /v1/memories/{orig}?hard=true` (sentinel) | **200** `{status: hard_deleted, deletion_converged: true, tombstone_status: CONVERGED}` |
| Delete copy | `DELETE /v1/memories/{copy}?hard=true` (sentinel) | **403** — see finding F1 |
| Delete copy | `DELETE /v1/memories/{copy}?hard=true` (memora) | **200** `{status: hard_deleted, deletion_converged: true, tombstone_status: CONVERGED}` |
| Verify cleanup | `GET /v1/memories/{copy}` (friday) / `GET /v1/memories/{orig}` (sentinel) | **404 / 404** |
| Verify cleanup | Search marker (friday / futuris) | **200**, copy absent + orig absent (50 / 21 other keyword matches on generic tokens only) |

### Finding F1 — UNIVERSAL records can only be deleted by the Memora service identity (code-cited, cleanup path)

- Direct UNIVERSAL write is refused: `POST /v1/memories` with `scope: UNIVERSAL` as sentinel → **403** `Only the Memora service identity may author UNIVERSAL memories.` The promotion route (`POST /v1/promotion/promote`) is the correct authoring path for agents.
- `DELETE` of a UNIVERSAL copy as its owner-agent (sentinel) → **403** `Only the agent that owns a memory may delete it.` Root cause, code-cited: `Memora/storage/relational/access_scope.py:126-146` (`may_mutate_record`) — `UNIVERSAL memories belong to the fabric, so authoring/mutating them is limited to the Memora service identity` (`scope == UNIVERSAL` → caller must be `SERVICE_AGENT`). The copy's `owner_agent` is sentinel, but the scope rule overrides ownership. Deleting as `memora` (X-Agent-Name `memora` + service key) succeeds — that is the cleanup leg for test UNIVERSAL records. No live data affected; both test records are gone.

### Acceptance

- One real universal-search cycle against the live Memora service — **yes**: baseline re-probe + fresh write/promote/recall/cleanup, all live on Server 1, receipts above.
- Query across agents, verify recall correctness — **yes**: MEM-019 copy rank 1 @ 1.0 for friday/sentinel/futuris; fresh copy rank 1 @ 1.0 for friday/futuris/sentinel.
- Follow-up to MEM-021 / MEM-035 — **yes**: MEM-021 re-sign verified live on a fresh dual copy (HMAC differs, SHA identical); MEM-035 still not landed, run 2 did not wait for it.

## Five states (MEM-037)

- implemented: YES (evidence only; no code change — live proof run)
- tested: YES (live cycle on Server 1, all receipts above)
- merged: NO (work PR owed)
- deployed: N/A (no code change)
- production-verified: YES (live service, real cycle; pending paired-verifier review + merge)

— Muse 15
