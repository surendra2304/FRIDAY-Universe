# TASK-MEM-021 — Memora: fix the UNIVERSAL dual-copy search invisibility (MEM-019 G1)

**Worker:** Muse 10 · **Date:** 2026-11-23 · **Branch:** `muse10/task-mem-021-universal-search` · **Work PR:** #1457
**Board:** TASK-MEM-021 (Memora: fix the UNIVERSAL dual-copy search invisibility — a promoted UNIVERSAL copy must be findable by search for the promotion audience)
**Assignment:** Muse coordinator watch 7091867264 (10:17 IST), answering work request 7091846124 (10:15 IST). Queue: FRD-037 (blocked head, public-chat 401 gate) → MEM-021; skipping the blocked head per coordinator order.

## Claim (done 2026-11-23 ~10:30 IST)
- Hub claim comment 7092042291 (issue #35).
- Board verified AVAILABLE, owner muse_ai, on main 27b7d4e2 (board blob b6a5af37, via PAT helper git blobs API). Note: main moved fde0591b → 27b7d4e2 (merge PR #1452, Muse 9 REL-070) between the coordinator watch and the claim; board re-fetched and re-verified at the new HEAD before claiming.
- Branch `muse10/task-mem-021-universal-search` created via PAT helper at main 27b7d4e2.
- Board flip committed on the branch via PAT helper contents API: commit c324120e, board blob aef1dcfc (MEM-021 CLAIMED, owner muse_10, branch set, claim evidence; YAML parses, 687 tasks, 0 duplicate ids).
- Work PR #1457 opened via PAT helper (head c324120e, open; board flip rides in the work PR per coordinator order — no separate claim PR).
- Work-request job `muse10-work-request` removed (cron.remove, scheduler reconciled). Hourly self-check stays armed.

## Acceptance
- A non-owner searching the distinctive content of a promoted UNIVERSAL copy finds the copy (or the search limitation is root-caused and the acceptance is re-scoped with evidence).

## Starting point (MEM-019 G1)
- Lesson original `270d1a53-7e3c-4f18-ad00-829ff3c734e1`, UNIVERSAL copy `8cfcaeb6-cc9c-446c-88d1-4797a469fbce`, content prefix `MUSE10-TEST-MEM-019`, distinctive query `momentum breakout entry 2x ATR stop volume filter`.
- friday search (limit 100): 100 results, max keyword 0.079, copy absent. Owner identical query: exactly 1 result, the original, keyword 1.0. The copy is absent from the owner's results too — invisible to search for everyone, not just non-owners. Direct-GET legs pass.

## Investigation log
- **Re-probe 2026-11-23 ~10:35 IST (probe_mem021.py, raw JSON in /tmp/muse10_mem021/ on Server 1): defect reproduces exactly.** Memora.service active since 09:05:28 IST, /health 200. Copy direct GET 200 as friday and futuris. friday search (distinctive query, limit 100): 100 results, copy absent, max keyword 0.0787. sentinel search (same query): exactly 1 result — the original at keyword 1.0, copy absent. friday prefix search (limit 50): 50 results, all keyword 0.0, copy absent.
- **ROOT CAUSE (found 2026-11-23 ~10:40 IST, verified live in-process on Server 1): the UNIVERSAL dual copy carries a STALE HMAC signature.** `promotion._make_universal_copy` copies the original's provenance dict verbatim (including its `hmac_signature`) and gives the copy a new id. The signature payload is `v1:{memory_id}:{tenant_id}:{owner_id}:{content_hash}:{memory_type}` — computed over the ORIGINAL's id, so `verify_memory_signature(copy)` is False while the original verifies True. Search's `_passes_retrieval_filters` (Safety Invariant 2) discards any record failing verification, for EVERY actor: friday COPY False, sentinel COPY False, futuris COPY False (ORIG True for friday/sentinel). Live log confirms: "MemoryRecord 8cfcaeb6... failed cryptographic provenance verification; discarding tampered record." (×3). Copy row itself is otherwise search-eligible: tenant default, scope UNIVERSAL, lifecycle ACTIVE, same namespace/owner — so the HMAC leg is the sole discriminator. Direct GET bypasses this check, which is why GET 200s while search misses.
- **Second, latent gap: the copy has NO vector row.** `memora_vector_store` holds a row for the original only (columns ID/TENANT_ID/EMBEDDING/PAYLOAD/UPDATED_AT). `_make_universal_copy` never upserts an embedding (write path does, service.py:1336, best-effort after commit). So the semantic leg also misses the copy; only the keyword fast lane can surface it — and only after the HMAC fix.
- **Fix plan:** (1) `_make_universal_copy`: re-sign the copy's provenance with `sign_memory_provenance` under the copy's own id (after adding the promotion keys), and best-effort upsert its embedding with the write path's payload/adapter pattern (fail-soft, relational row stays authoritative). One fix covers owner + auto-promotion paths (both go through `_apply_promotion` → `_make_universal_copy`). (2) Repair for already-created dual copies: re-sign + embed existing UNIVERSAL records with `promoted_from_memory_id` whose signature fails; run live for the MEM-019 copy (test data, deterministic re-sign), then re-probe. (3) Unit tests in `Memora/tests/test_mem013_memory_promotion.py`: dual copy verifies; dual copy passes retrieval filters; repair re-signs a stale copy. (4) PR #1457 carries the fix; merge + deploy by Muse; re-probe live after deploy.
- **Open question (noted, not blocking):** `_passes_retrieval_filters` for futuris on the ORIG returns False while friday/sentinel return True — the policy-engine leg distinguishes futuris on the sentinel/private namespace (MEM-014 G1 namespace rule). Pre-existing, separate from MEM-021; the copy fails earlier (HMAC) for all three.

## Implementation (done 2026-11-23 ~11:2x IST, hourly self-check repair of the post-claim stall)

Note: PR #1457 was the claim vehicle only (board flip AVAILABLE → CLAIMED); it merged 10:49 IST (merge 136533e5). The implementation rides in a new work PR (number below); the branch was fast-forwarded to main 136533e5 first so the board edit applies cleanly.

`Memora/core/memory/promotion.py`:
- `_make_universal_copy` now re-signs the copy's provenance under the copy's own id (`_sign_copy_provenance`, the write path's `compute_memory_signature` pattern — not `sign_memory_provenance`, so the content-hash fallback and enum handling match the write path exactly) and best-effort upserts the copy's embedding (`_upsert_copy_embedding`, mirroring the write path's Oracle/Qdrant branch). One fix covers owner + auto-promotion paths (both go through `_apply_promotion` → `_make_universal_copy`). The vector leg is fail-soft: the relational row is authoritative and a vector-store outage must not fail the promotion.
- New `MemoryPromotionService.repair_universal_copies(db, dry_run=True)`: scans UNIVERSAL records carrying `promoted_from_memory_id`, re-signs the stale ones under their own id + upserts their embedding, and reports counts. Safety mirroring `scripts/resign_provenance.py` (MEM-010): content-tampered records (hash mismatch) and unsigned records are NEVER force-signed — reported by id and left untouched. Dry-run is the default. Caller commits.
- New `Memora/scripts/repair_universal_copies.py` CLI: dry-run default; `--apply` requires `MEMORA_REPAIR_UNIVERSAL_APPLY=1`; refuses to run unless `MEMORA_MASTER_KEY` is set and is the key settings resolve. Exit 0 clean, 2 if unverifiable/unsigned records were left untouched, 1 refused.

`Memora/tests/test_mem013_memory_promotion.py` (new tests):
- `test_universal_copy_signature_verifies_and_passes_search_gate` — a signed failed-experiment lesson is promoted; the copy verifies under its own id, its signature differs from the original's, and `_passes_retrieval_filters` admits it to futuris and sentinel.
- `test_repair_universal_copies_resigns_stale_copy` — a copy manually reverted to the pre-fix stale signature fails verification; dry-run reports `would_repair: 1` and writes nothing; apply repairs it and it verifies again.

## Verification

- Targeted tests run live on Server 1 against this branch: [run output in the STATUS comment on issue #35].
- CI on the work PR: [pending/ green — see STATUS comment].

## Still owed (needs Muse)

1. **Merge** the work PR; **deploy** to the Oracle Memora service.
2. **Live repair:** run `scripts/repair_universal_copies.py` dry-run, then `--apply` with `MEMORA_REPAIR_UNIVERSAL_APPLY=1`, for the MEM-019 copy `8cfcaeb6-cc9c-446c-88d1-4797a469fbce` (test data, deterministic re-sign).
3. **Re-probe live:** friday + sentinel search on `momentum breakout entry 2x ATR stop volume filter` — the copy must appear; then report production-verified.

## Related

- FRD-037 stays CLAIMED and blocked: production chat POST still returns HTTP 401 "A valid FRIDAY control API key is required" (re-probed 11:06 IST). Live runs 0/3.
