# TASK-MEM-027: Memora three-section live proof run 4 — checkpoint 2 (live cycle)

**Worker:** Muse TP13 · **Date:** 2026-11-28 · **Branch:** `musetp13/task-mem-027-three-section-live-proof-run-4`
**Board:** TASK-MEM-027 (Memora: three-section live proof run 4 — one real write/read/promotion cycle across private / inter-agent / universal)
**Claim:** issue #2045 comment 7228251671 (~02:43 IST, 2026-11-28), per Burn Enforcer 02:38 §B (hub #2045 comment 7228172325).
**Checkpoint 1:** TP11, commit `48e4dd6a` (grounding + probe package; never merged — adopted as this branch's base).

> STATUS: CHECKPOINT 2 — live cycle RUN on the live service. 52/54 checks PASS. The three-section proof is fully evidenced (M1 ladder, M2 auto-promotion + dual copy + MEM-021, M3, M4). Two checks FAIL on the sweep blast-radius assertion (got 3, expected 1) — root-caused below as a live-service backlog, not a proof failure: the sweep also promoted two pre-existing test lessons that had already qualified. No re-run: a re-run would promote the same two again. The finding is disclosed, not hidden.

## Acceptance (board)

One real cycle evidenced across all three sections against the live service. — MET: see M1/M2/M3/M4 below.

## Run facts (verified first-hand this run)

- **Script:** `docs/collaboration/TASK-MEM-027-PROBE.py` (TP11, adopted unmodified from `48e4dd6a`; sha256 `1ffe6110edbdf598026f0d4713a3ace4e2a466a7ecd10733e39662739bf7c1c1`, 457 lines, py_compile OK). Ran ON Oracle Server 1 (localhost Memora `http://127.0.0.1:8002`), outdir `/tmp/musetp13_mem027/out`, 50 numbered call JSONs + `SUMMARY.json`. Keys read from the service's own env file at runtime on the server and NEVER printed or copied (only key names + presence logged: 8 keys present). Content prefix `MUSETP11-TEST-MEM-027` (adopted script, unchanged); provenance `test_data: true`, `task: TASK-MEM-027`.
- **Launch:** detached `setsid nohup` (bridge 120s cap — the fetch call was killed by the cap after the file had already landed; hash match verified before launch). PID 2202288, launched ~02:48 IST, finished ~02:49:40 IST. Exit code 1 (`SUMMARY: FAILURES PRESENT`, `all_pass: false`).
- **Memora health at run:** `status ok`, v2.0.0, memory_store / event_store / vector_search all ok, database healthy (oracle backend, vector `oracle_23ai_native_vector` dim 384), observed `2026-11-27T21:18:49Z`. `systemctl is-active memora` reports `inactive` — the service runs outside systemd (watcher `/tmp/memora_watch.sh`); the `:8002` endpoint answering 200 is what matters.
- **Route:** live leg run under standing clearance `7200564540` (own-task live verification; WATCH241 §C precedent). No key material left the server.

## Results

### M1 — owner-promotion ladder (plain memory) — ALL PASS

Memory `4bce5ced-6198-4bef-ae5e-7c9f74d6fd3e` (`cobalt summit ninefold opal`).

- Write PRIVATE 201 (2,413.5 ms); owner read 200 PRIVATE; non-owner (friday) 404.
- Promote → SHARED 200 (7,757.6 ms, `owner_judgement`, PRIVATE→SHARED); recipients friday + intelx read 200 SHARED; outsider futuris 404; search finds it for friday, rank 1, keyword_score 1.0.
- Promote → UNIVERSAL 200 (97.9 ms, SHARED→UNIVERSAL); futuris + friday read 200 UNIVERSAL; search finds it for futuris.
- Audit `MEMORY_SCOPE_PROMOTED`: 2 rows (both promotions).

### M2 — auto-promotion lesson (dual copy + MEM-021) — ALL PASS except blast radius

Memory `7138f4b4-43d7-4d55-841f-740ee1d502ad`, universal copy `6460d1d9-88c7-475f-b1e4-a6333691c1e0` (`crimson tide fourfold jasper`).

- Write PRIVATE 201 (803.8 ms); owner read 200 PRIVATE; non-owner 404; 0 need rows before round 1.
- Round 1 needs: friday ×2, intelx ×2, futuris ×2, cortex ×2 (8 needs, 4 distinct non-owner agents); owner need → `owner_need_ignored`.
- Sweep 1 (4,781.5 ms): promotes m2 PRIVATE→SHARED, path `auto_repeated_need` — PASS. Owner read 200 SHARED (visible 4,812.9 ms after sweep start); needer friday 200 SHARED; outsider inference 404; search rank 1, keyword_score 1.0.
- Round 2 needs: inference ×2, stratex ×2 (2 more distinct agents, both outside the SHARED allow-list).
- Sweep 2 (12,285.3 ms): promotes m2 SHARED→UNIVERSAL, `promoted_dual_copy`, copy `6460d1d9` — PASS. Original stays SHARED (owner 200 SHARED; outsider inference still 404 on the original). Copy reads 200 UNIVERSAL for inference, stratex, friday, futuris.
- **MEM-021 decisive check PASS:** copy HMAC differs, content SHA identical (orig hmac `b23227424ccc`, copy hmac `4216e1c7f8f0`, sha `556102ff00e8`); copy `promoted_from_memory_id` == original. Search finds the copy for inference at UNIVERSAL, rank 1, keyword_score 1.0.
- Audit `MEMORY_SCOPE_PROMOTED`: 2 rows (PRIVATE→SHARED; SHARED→UNIVERSAL dual=True, copy `6460d1d9`).

### M3 — write-time SHARED control — PASS

Memory `f395734e-502e-45e5-b392-8330d516c878` (`amber ridge sixfold pearl`). Write-time SHARED 201 (1,227.3 ms); recipient friday 200 SHARED; non-recipient intelx 404.

### M4 — direct UNIVERSAL write control — PASS

Direct UNIVERSAL write → 403 (118.1 ms), as expected.

## The two FAILs — blast radius (root-caused, disclosed)

- `FAIL M2 sweep 1 blast radius exactly 1 (got 3)` and `FAIL M2 sweep 2 blast radius exactly 1 (got 3)`.
- Each sweep also promoted two pre-existing, sentinel-owned test lessons that had already qualified for UNIVERSAL (needs in the 30-day window):
  - `694a6843-f203-4e99-8ffd-9a2543766a94` — `MUSE1-TEST-MEM-034`, TASK-MEM-034 failed-experiment lesson, created 2026-11-26T11:40:52Z, `test_data: true`. Universal copy `b2ca708e-56c6-4415-88ab-2020e41bfd9e`.
  - `b5bfbf85-f5ca-4c14-9ba7-22531d0d71da` — `MUSE8-TEST-MEM-025`, MEM-025 run-2 auto-promotion lesson, created 2026-11-24T07:28:17Z, `test_data: true`. Universal copy `32c9ed6e-31c2-4318-8946-e2d40d6ae1c2`.
- Both were already SHARED with qualifying needs; the sweep did what it is designed to do and promoted them. Sweep 2 re-reported the SAME copy ids for both — the sweep is idempotent for already-promoted memories (no duplicate copies created).
- Root cause: the probe's blast-radius-1 assertion assumes a quiescent service. The live service carries a promotion backlog of earlier test lessons, so a live sweep legitimately promotes more than the probe's target. The target memory's own promotion path is fully evidenced in both sweeps. A re-run would hit the same two extras (they still qualify), so no re-run was done.
- State change disclosed: this run's sweeps created the universal copies above for two pre-existing test lessons (by design — they qualified). Their originals stay SHARED.

## Non-blocking finding (for the verifier / coordinator)

- The blast-radius assertion should be relaxed for future live runs (assert the target is promoted + report extras), or the sweep should accept a target filter. The MEM-025 run-2 precedent passed with blast radius 1 only because the service was quiet then.

## Five states

Implemented YES (live service v2.0.0) / tested YES (live, this run) / merged NO (this PR) / deployed N/A / production-verified YES (live cycle evidenced).

No board hunk — flip rides the coordinator board PR. Paired verification owed (coordinator names).

— Muse TP13
