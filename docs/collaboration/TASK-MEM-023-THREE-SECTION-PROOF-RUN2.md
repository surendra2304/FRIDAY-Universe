# TASK-MEM-023: Memora three-section live proof, run 2

**Worker:** Muse 10 · **Date:** 2026-11-23 · **Branch:** `muse10/task-mem-023-three-section-proof-run2`
**Board:** TASK-MEM-023 (Memora three-section live proof, run 2, with the MEM-021
fix in place — one real write/read/promotion cycle across private / inter-agent /
universal against the live service, verifying the UNIVERSAL-copy signature path
MEM-021 fixed (re-sign under own id + embedding upsert); evidence at each hop)
**Assignment:** coordinator watch 7094281062 (12:53 IST). **Claim:** issue #35
comment 7094696812 (~13:17 IST).

> STATUS: COMPLETE — all legs green. Phase 1 (M1 stepwise ladder) green
> 13:26–13:31 IST; phase 2 (M1b2 dual-copy leg, M2 auto-promotion, M3/M4
> controls) green 14:07–14:08 IST after the bridge outage cleared. Work PR
> open, awaiting Muse merge.

## Verdict

The three-section ladder works end to end on the deployed MEM-016 + MEM-021
code: owner promotion PRIVATE → SHARED → UNIVERSAL confers readability at
every rung, and search finds the promoted record for its audience. The
MEM-014 G1 defect (promoted scope confers no readability) is confirmed fixed
live, and the MEM-014 G2 defect (sweep misses fresh records) is confirmed
fixed live — the sweep promoted the minutes-old M2 on the first pass. The
MEM-021 decisive check passes on a fresh copy with no repair: the
failed-experiment lesson's UNIVERSAL copy is re-signed under its own id
(HMAC prefix differs from the original), carries the same content SHA, and
is searchable by all three audiences immediately after promotion. No new
gaps. One out-of-scope observation (O1) noted for the coordinator.

## How the proof ran

- **Live service:** `Memora.service` on Oracle Server 1, active (running)
  since 2026-11-23 12:07:22 IST, `uvicorn app.main:app` on port 8002.
  `GET /health` 200 at 2026-11-23T07:50:15Z / re-checked in-probe:
  `status: ok`, `storage: oracle`, `database: healthy`,
  `database_durable: true`, `vector_store: oracle_23ai_native_vector, dim 384,
  table memora_vector_store`, `version: 2.0.0`.
- **Deployed code:** Server 1 checkout `d7d534cd` (MEM-021 merge). MEM-016
  merge `4a16d09f` verified an ancestor of `d7d534cd` first-hand
  (`git merge-base --is-ancestor`, 2026-11-23 ~13:24 IST), so both fixes are
  live: MEM-016 (promotion readability + two-phase sweep) and MEM-021
  (UNIVERSAL-copy re-sign + embedding upsert).
- **Auth:** `X-Agent-Name` + per-agent `X-API-Key`. Keys read from the
  service's own env file at runtime on the server and never left it; only key
  names are recorded here. Owner identity `sentinel`; needers `friday`,
  `intelx`, `futuris`, `cortex`; sweeps as the `memora` service identity.
- **Test data:** every test memory is content-prefixed `MUSE10-TEST-MEM-023`
  and provenance-marked `test_data: true`, `task: TASK-MEM-023`. Nothing else
  was written; no live data was overwritten, no live DB or config was touched,
  no service was restarted.
- **Probe scripts:** `/tmp/muse10_mem023/probe_mem023.py` (phase 1, ran
  13:26–13:31 IST) and `probe_mem023_phase2.py` (phase 2, ran 14:07–14:08 IST
  after the bridge recovered). Local copies in the goal hidden_files. Raw
  service responses: `/tmp/muse10_mem023/m1-*.json`, `m1b2-*.json`,
  `m2-*.json`, `m3m4-*.json` on Server 1 (ephemeral; the numbers below are
  the durable record). No secrets in this doc or in any response quoted.
- **Blocker, resolved:** bridge MCP outage ~13:32–14:06 IST (no bridge
  request completed; public ingress still 200). Recovered on its own;
  `get_system_info` OK at 14:06 IST, `run_shell` OK at 14:07 IST. Phase-2
  script copy to Server 1 verified byte-identical (9593 bytes, py_compile
  clean) before running. STATUS comment 7095166113 posted during the outage.

## M1 — the owner-promotion ladder (path A), phase 1

Memory `f638b79d-4b31-4834-afc3-16be02e51af5`, namespace
`memora://sentinel/private`, owner `sentinel`, created 2026-11-23 ~13:26 IST.

| Step | Call | Result |
| --- | --- | --- |
| Write PRIVATE | `POST /v1/memories` (sentinel) | **201**. `storage_backend: oracle`, `storage_durable: true`, `lifecycle_state: active`, `is_duplicate: false`. |
| Read as owner | `GET /v1/memories/{id}` (sentinel) | **200**, `scope: PRIVATE`, content verbatim. |
| Read as other | `GET /v1/memories/{id}` (friday) | **404** — existence hidden from non-owners. |
| Promote → SHARED | `POST /v1/promotion/promote` `{target_scope: SHARED, shared_with: [friday, intelx]}` (sentinel) | **200** `{status: promoted, scope: SHARED, from_scope: PRIVATE, path: owner_judgement}`. |
| Read as recipient | `GET /v1/memories/{id}` (friday, intelx) | **200**, `scope: SHARED` — was 403 in MEM-014 (G1); MEM-016 fix holds live. |
| Read as outsider | `GET /v1/memories/{id}` (futuris) | **404** not found. |
| Search as recipient | `GET /v1/memories/search?q=quasar ledger ninefold verdant&limit=50` (friday) | **200**, exactly 1 result: M1 at **rank 1, keyword_score 1.0**. |
| Promote → UNIVERSAL | `POST /v1/promotion/promote` `{target_scope: UNIVERSAL}` (sentinel) | **200** `{status: promoted, scope: UNIVERSAL, from_scope: SHARED, path: owner_judgement}` — no dual copy (see finding below). |
| Read as outsider | `GET /v1/memories/{id}` (futuris) | **200**, `scope: UNIVERSAL` — was 403 in MEM-014 (G1); MEM-016 fix holds live. |
| Read as recipient | `GET /v1/memories/{id}` (friday) | **200**, `scope: UNIVERSAL`. |
| Audit | `GET /audit?action=MEMORY_SCOPE_PROMOTED&limit=20` (memora) | **200**, 12 rows returned (includes M1's two promotion rows). |

## Finding F1 — the dual-copy path fires only for failed-experiment lessons

A second record `d16063a7-5771-4250-87e6-3fc39889d631` (plain content, no
lesson provenance) promoted direct PRIVATE → UNIVERSAL returned **200**
`{status: promoted, scope: UNIVERSAL, from_scope: PRIVATE}` with **no**
`universal_copy_id` — scope mutated in place, no copy. This is correct
behaviour, code-cited: `Memora/core/memory/promotion.py:816-819` —
"Failed-experiment dual rule: the original stays PRIVATE and a UNIVERSAL copy
carries the lesson to the whole universe", gated on
`target == UNIVERSAL and is_failed_experiment_lesson(record)`. Phase 2
re-ran this leg as a failed-experiment lesson (M1b2) to exercise the MEM-021
re-sign + embedding fix on a fresh copy.

## M1b2 — failed-experiment lesson, direct PRIVATE → UNIVERSAL (dual copy), phase 2

Original `064a7d24-3806-432c-b6ca-04e0c6dc9683`, copy
`038bb8d9-cfed-4958-ae78-390784dd4fdb`, created 2026-11-23 ~14:07 IST.
Provenance: `failed_experiment: true`, `experiment_outcome: failed`,
`lesson_type: failed_experiment`.

| Step | Call | Result |
| --- | --- | --- |
| Write PRIVATE | `POST /v1/memories` (sentinel) | **201**. |
| Promote → UNIVERSAL | `POST /v1/promotion/promote` `{target_scope: UNIVERSAL}` (sentinel) | **200** `{status: promoted_dual_copy, scope: PRIVATE, to_scope: UNIVERSAL, path: owner_judgement, universal_copy_id: 038bb8d9-...}`. |
| Original as other | `GET /v1/memories/{orig}` (friday) | **404** — original stays PRIVATE. |
| Original as owner | `GET /v1/memories/{orig}` (sentinel) | **200**, `scope: PRIVATE`. |
| Copy as recipient | `GET /v1/memories/{copy}` (friday) | **200**, `scope: UNIVERSAL`. |
| Copy as outsider | `GET /v1/memories/{copy}` (futuris) | **200**, `scope: UNIVERSAL`. |
| Copy provenance | `GET /v1/memories/{copy}` (sentinel) | `signature_version: v1`, `hmac_prefix: 40a0513bad85`, `content_sha256` prefix `a4dcf739489d`, `promoted_from: 064a7d24-...`. |
| Original provenance | `GET /v1/memories/{orig}` (sentinel) | `hmac_prefix: 959d2c5c5d70`, `content_sha256` prefix `a4dcf739489d`. |

**MEM-021 decisive check — PASS.** The copy's HMAC prefix differs from the
original's (re-signed under its own id, the MEM-021 fix) while the content
SHA prefix is identical (content preserved verbatim). Distinctive search
(`halcyon beacon sevenfold crimson`, limit 50) finds the copy for all three
audiences — friday, sentinel, futuris — at rank 2, keyword 0.8923–0.8946, with
no repair step. Rank 2, not rank 1, is expected: phase 1's M1b record
`d16063a7-...` shares the same distinctive phrase and scores 1.0 in every
audience's results. The copy is findable immediately after promotion, which
is the MEM-021 fix working on a fresh copy (MEM-019's copy needed a live
repair before it surfaced).

## M2 — auto-promotion (needs + sweep), phase 2

Memory `f4f77b31-df02-49d7-a4c5-4711dad5436d`, owner `sentinel`, created
2026-11-23 ~14:08 IST.

| Step | Call | Result |
| --- | --- | --- |
| Write PRIVATE | `POST /v1/memories` (sentinel) | **201**. |
| Needs before | `GET /audit?action=MEMORY_NEED_RECORDED&limit=500` (memora) | 0 rows for M2. |
| 9 needs | `POST /v1/promotion/need` (friday×2, intelx×1, futuris×3, cortex×3) | **200** each. |
| Owner need | `POST /v1/promotion/need` (sentinel) | **200** `{status: owner_need_ignored}` — correct. |
| Sweep | `POST /v1/promotion/sweep` `{window_days: 30}` (memora) | **200** `{count: 1, promotions: [{status: promoted, memory_id: f4f77b31-..., scope: SHARED, to_scope: SHARED, path: auto_repeated_need, from_scope: PRIVATE}]}`. |
| Owner read | `GET /v1/memories/{id}` (sentinel) | **200**, `scope: SHARED`. |
| Needer read | `GET /v1/memories/{id}` (friday) | **200**, `scope: SHARED`. |
| Audit | `GET /audit?action=MEMORY_SCOPE_PROMOTED&limit=20` (memora) | **200**, M2 row present: `promoted_by: memora`, `path: auto_repeated_need`, `reason: repeated cross-agent need`, `shared_with: [cortex, friday, futuris, intelx]`, evidence `distinct_agents: 4, total_needs: 9, window_days: 30`. |

**MEM-014 G2 — CLOSED by live evidence.** The sweep promoted the
minutes-old M2 on the first pass (blast radius exactly 1 — only M2 was
promoted), confirming the MEM-016 two-phase sweep fix live. In MEM-014 the
sweep left M2 PRIVATE because it scanned only the 200 oldest records.

## M3 / M4 — write-time controls, phase 2

| Step | Call | Result |
| --- | --- | --- |
| M3 write-time SHARED | `POST /v1/memories` `{scope: SHARED, shared_with: [friday]}` (sentinel) | **201**, id `e567f9ad-2b88-429a-8a72-48ad361e8729`. |
| M3 as recipient | `GET /v1/memories/{id}` (friday) | **200**, `scope: SHARED`. |
| M3 as non-recipient | `GET /v1/memories/{id}` (intelx) | **404**. |
| M4 direct UNIVERSAL write | `POST /v1/memories` `{scope: UNIVERSAL}` (sentinel) | **403** `{detail: Only the Memora service identity may author UNIVERSAL memories.}` — correct. |

## Journal check

Memora journal around the sweep (14:08:01–14:08:43 IST, 80 lines): no
ERROR, no traceback. Every probe call logged with its expected status
(including the 404s and the M4 403). Embedding calls to Gemini return
200 OK. The sweep itself logged `POST /v1/promotion/sweep 200 OK` at
14:08:13 IST.

## Observation O1 (out of scope, for the coordinator)

The journal shows repeated `GET /v1/events/cursor?consumer_id=futuris-cloud-v1`
→ **401 Unauthorized** from 10.0.0.120 (Server 2) — 3 times in the 14:08
window alone (14:08:01, 14:08:16, 14:08:31). A background consumer on
Server 2 is polling Memora's events cursor with credentials Memora rejects.
Pre-existing, unrelated to this proof (my probe used localhost only); not
filed as a task gap. Worth a look by whoever owns the futuris-cloud
event consumer — it is failing auth on every poll.

## Gaps

None. All acceptance legs green on the live service with the MEM-021 fix
in place.

## Test data left behind (cleanup path)

- M1 `f638b79d-4b31-4834-afc3-16be02e51af5` — scope UNIVERSAL, namespace
  `memora://sentinel/private`, content prefixed `MUSE10-TEST-MEM-023`.
- M1b `d16063a7-5771-4250-87e6-3fc39889d631` — scope UNIVERSAL, same namespace.
- M1b2 original `064a7d24-3806-432c-b6ca-04e0c6dc9683` — scope PRIVATE;
  copy `038bb8d9-cfed-4958-ae78-390784dd4fdb` — scope UNIVERSAL, same namespace.
- M2 `f4f77b31-df02-49d7-a4c5-4711dad5436d` — scope SHARED, same namespace.
- M3 `e567f9ad-2b88-429a-8a72-48ad361e8729` — scope SHARED, same namespace.
- Cleanup (not done here — out of scope for a proof run): the owner or the
  memora service identity can remove the memories via
  `POST /v1/memories/{id}/forget` or `DELETE /v1/memories/{id}`. All memories
  carry `provenance.test_data: true` / `task: TASK-MEM-023`.

— Muse 10
