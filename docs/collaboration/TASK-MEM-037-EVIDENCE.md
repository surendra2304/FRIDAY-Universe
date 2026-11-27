# TASK-MEM-037 — Memora: universal search live proof run 2 — cross-agent recall against the live service

**Worker:** Muse 15 · **Claim:** hub #2045 comment 7211582420 (2026-11-27 12:00 IST) · **Board:** CLAIMED, owner muse_15, via board PR #2084 (watch209, main 888d6461; board updated 2026-11-27T12:11 IST) · **Branch:** `muse15/task-mem-037-universal-search-run-2` · **Base:** main `25ce04a3`

**Assignment (coordinator watch181, hub #1483):** one real universal-search cycle against the live Memora service: query across agents, verify recall correctness, file the receipts. Follow-up to MEM-021 (universal search run 1) and MEM-035 (three-section run 6). Live-proof route: live Memora service on Oracle Server 1.

## Checkpoint 1 — repo prep (2026-11-27 ~13:10 IST)

Branch pushed; prior-run groundwork read first-hand; run plan set. **Live cycle: NOT RUN in this checkpoint** — the live leg is owed next, against the live Memora service on Server 1.

### Prior runs (read first-hand from main)

- **MEM-021 (run 1, PR #1462 MERGED):** fixed the UNIVERSAL dual-copy search invisibility — `_make_universal_copy` carried a stale HMAC signature (computed over the original's id) and never upserted a vector row, so `_passes_retrieval_filters` discarded every dual copy for every actor. Fix: re-sign under the copy's own id + best-effort embedding upsert; repair CLI `Memora/scripts/repair_universal_copies.py`. Tests live on S1: 14 passed (MEM-021 suite) + 34 passed (related suites). Still owed from MEM-021: live repair + live re-probe of the MEM-019 copy.
- **MEM-019 copy (test data):** id `8cfcaeb6-cc9c-446c-88d1-4797a469fbce`, content prefix `MUSE10-TEST-MEM-019`, distinctive query `momentum breakout entry 2x ATR stop volume filter`.
- **MEM-035 (run 6, three-section):** NOT landed — AVAILABLE, owner muse_tp2, evidence doc absent on main `25ce04a3`. Run 2 proceeds on MEM-021's fix and does not wait for run 6.

### Run plan (live cycle, next)

Live Memora: Server 1, port 8002 (`/api/v1/memora/*`, `/v1/context/*`); production is systemd + Caddy (repo AGENTS.md ground truth 2026-10-26).

1. Health: Memora.service active, `/health` 200 on S1.
2. Baseline: direct GET of the MEM-019 copy as friday + futuris (must 200); record signature verification state.
3. Recall probe: search the distinctive query as friday, sentinel, and futuris (limit 100) — the copy must appear in each actor's results with keyword 1.0 (or the miss is root-caused with log evidence).
4. Cross-agent recall: a second distinctive UNIVERSAL memory written by one agent must be recallable by a different agent's search; record both receipts.
5. File every receipt (query, actor, result count, copy rank/keyword, timestamps) in this doc; no receipts are invented — only live output counts.

### Live-leg route note

The live cycle runs against the live service via the bridge. This checkpoint did no live calls; the bridge route for this run is established by the next work run before the probes (schema review first, read-only probes only, no server moves).

## Five states (MEM-037)

- implemented: NO (repo prep only; live cycle owed)
- tested: NO
- merged: NO
- deployed: N/A
- production-verified: NO

— Muse 15
