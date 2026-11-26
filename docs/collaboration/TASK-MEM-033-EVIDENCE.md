# TASK-MEM-033: Memora three-section proof run-4

**Worker:** Muse 15 · **Date:** 2026-11-26 · **Branch:** `muse15/task-mem-033-three-section-proof-run-4`
**Board:** TASK-MEM-033 (Memora three-section proof run-4 — one real write/read/promotion cycle, live service)
**Assignment:** coordinator WATCH141 follow-up (issue #1483, hub 7183443194, ~10:53 IST) — queue position 2, after FRD-043 (HELD head). Board owner → muse_15 landed on main via board PR #1957 (merged 11:04:26 IST, merge `4127456c`).
**Claim:** issue #1483, this run (completion + claim post for FRD-057 / FUT-032 merges).

> STATUS: CHECKPOINT 2 — live probe run 2026-11-26 ~12:04 IST, 47 calls.
> All acceptance legs green (M1 / M1b / M1b2 / M2 / M3 / M4 + audit +
> journal). One probe self-check failed and is diagnosed first-hand below:
> the M2 sweep promoted 2 memories, not 1 — the second is the MEM-025
> run-2 lesson, re-promoted because the sweep is not idempotent across
> runs (stale in-window needs). The M2 auto-promotion itself is proven.
> Work PR next.

## Acceptance (board)

Live proof of the three-section memory, run-4 (MEM-023/024/025 pattern): one real write/read/promotion cycle across private / inter-agent / universal sections against the live service, with evidence (ids, timestamps, section of each read). Done = one full cycle evidenced end to end on the live service.

## Board verified first-hand (main `b1f24f22`, 2026-11-26 ~11:57 IST)

- MEM-033 CLAIMED / owner muse_15 / branch `muse15/task-mem-033-three-section-proof-run-4` / pr null / P1. Next action: "Claimed by muse_15 (hub 7183575578); live write/read/promotion probe next, then work PR with finished live evidence." — probe now run, work PR next.
- FRD-057 MERGED (pr 1927), FUT-032 MERGED (pr 1956) — flips landed via board PR #1957.
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

## Live probe results — run 4, 2026-11-26 ~12:04 IST

Script `docs/collaboration/TASK-MEM-033-PROBE.py` (filed in this PR), run on
Server 1 as `/tmp/muse15_mem033/probe_mem033.py` (sha256 `86dbed40…d83e3`,
`py_compile` clean, background PID 955449, 12:04:05–12:04:16 IST, 47 calls,
raw responses `/tmp/muse15_mem033/01.json`–`47.json` + `SUMMARY.json`).
Memora `/health` 200 at 12:04:05 IST (v2.0.0, Oracle healthy/durable, vector
dim 384, no circuit breaker open). All 8 agent keys present from the
service's own env file at runtime; no key printed or copied. Test data
content-prefixed `MUSE15-TEST-MEM-033`, provenance `test_data: true`,
`task: TASK-MEM-033`. 46/47 script checks PASS; the one FAIL is diagnosed
in "Finding F1" below — it is a service behavior, not a probe error.

### M1 — owner-promotion ladder, 12:04 IST

Memory `0efe49ae-3f8a-4bea-af6d-a194eb330ad7`, namespace
`memora://sentinel/private`, owner `sentinel`. Phrase: `velvet comet
fivefold sapphire`.

| Step | Result |
| --- | --- |
| Write PRIVATE | **201** (992.9 ms) |
| Read as owner (sentinel) | **200**, `scope: PRIVATE` |
| Read as other (friday) | **404** |
| Promote → SHARED (`shared_with: [friday, intelx]`) | **200** (123.6 ms) `{status: promoted, scope: SHARED, from_scope: PRIVATE, path: owner_judgement}` |
| Read as friday / intelx | **200**, `scope: SHARED` |
| Read as outsider (futuris) | **404** |
| Search as friday | **200**, exactly 1 result, **rank 1, keyword_score 1.0** |
| Promote → UNIVERSAL | **200** (26.1 ms) `{status: promoted, scope: UNIVERSAL, from_scope: SHARED, path: owner_judgement}`, no copy |
| Read as futuris / friday | **200**, `scope: UNIVERSAL` |

### M1b — direct PRIVATE → UNIVERSAL (in-place), 12:04 IST

Memory `38e51b71-6919-49fd-b30d-e70cb49c514a`, plain content. Promote →
UNIVERSAL **200** (15.2 ms) `{status: promoted, scope: UNIVERSAL,
from_scope: PRIVATE}`, no `universal_copy_id`. Reads as friday and futuris:
**200**, `scope: UNIVERSAL`. Phrase: `copper falcon sevenfold topaz`
(shared with M1b2 by design, as in run 2/3).

### M1b2 — failed-experiment lesson (dual copy), 12:04 IST

Original `c7edf621-eeb2-4c94-a387-304d44154d4a`, copy
`97616310-470a-44a6-a5bd-f9943ce09cd4`. Provenance: `failed_experiment:
true`, `experiment_outcome: failed`, `lesson_type: failed_experiment`.

| Step | Result |
| --- | --- |
| Write PRIVATE | **201** (641.6 ms) |
| Promote → UNIVERSAL | **200** (621.2 ms) `{status: promoted_dual_copy, scope: PRIVATE, to_scope: UNIVERSAL, path: owner_judgement, universal_copy_id: 97616310-…}` |
| Original as other (friday) | **404** — original stays PRIVATE |
| Original as owner (sentinel) | **200**, `scope: PRIVATE` |
| Copy as friday / futuris | **200**, `scope: UNIVERSAL` |
| Copy provenance | `hmac_prefix: ce7944d22e5c2734`, `content_sha256` prefix `350e8c686de13376`, `promoted_from: c7edf621-…` |
| Original provenance | `hmac_prefix: a38a2fae9097226a`, `content_sha256` prefix `350e8c686de13376` |

**MEM-021 decisive check — PASS.** Copy HMAC prefix differs (re-signed
under its own id) while the content SHA prefix is identical. Search
(`copper falcon sevenfold topaz`, limit 50) finds the copy for all three
audiences — friday rank 2 (0.7575), sentinel rank 2 (0.7689), futuris rank
2 (0.7575). Rank 2, not rank 1, is expected: the M1b record shares the
same phrase and scores higher in every audience's results.

### M2 — auto-promotion (needs + sweep), 12:04 IST

Memory `4df56e2c-3476-4236-aaae-f85465cd3061`, owner `sentinel`. Phrase:
`silver willow fourfold garnet`.

| Step | Result |
| --- | --- |
| Write PRIVATE | **201** (658.1 ms) |
| Needs before | 0 rows |
| 9 needs (friday×2, intelx×1, futuris×3, cortex×3) | **200** each |
| Owner need (sentinel) | **200** `{status: owner_need_ignored}` |
| Sweep `{window_days: 30}` | **200** (4,548.1 ms) — M2 `PRIVATE → SHARED`, `path: auto_repeated_need` |
| Owner read after sweep | **200**, `scope: SHARED` (sweep→visible 4,563.7 ms) |
| Needer read (friday) | **200**, `scope: SHARED` |
| Audit | M2 row present: `promoted_by: memora`, `path: auto_repeated_need` |

**M2 leg itself: PASS.** The promotion happened via `auto_repeated_need`
with the correct from/to scope and needers. See Finding F1 for the blast
radius check.

### M3 / M4 — write-time controls, 12:04 IST

| Step | Result |
| --- | --- |
| M3 write-time SHARED (`shared_with: [friday]`) | **201** (960.4 ms), id `eb06703a-7360-4fc8-baef-9888994c48a9` |
| M3 as recipient (friday) | **200**, `scope: SHARED` |
| M3 as non-recipient (intelx) | **404** |
| M4 direct UNIVERSAL write | **403** `{detail: Only the Memora service identity may author UNIVERSAL memories.}` |

### Audit + journal

- `GET /audit?action=MEMORY_SCOPE_PROMOTED&limit=20`: **200**, 5 rows for
  this run's memories (M1 ×2, M1b ×1, M1b2 ×1, M2 ×1).
- Memora journal 12:00–12:10 IST (679 lines, PID 3747325 throughout, no
  restart): **zero ERROR, zero traceback, zero 401s**.

### Latency (run 4)

| Call | Latency |
| --- | --- |
| M1 promote → SHARED | 123.6 ms |
| M1 promote → UNIVERSAL | 26.1 ms |
| M1b promote → UNIVERSAL (direct) | 15.2 ms |
| M1b2 promote → UNIVERSAL (dual copy) | 621.2 ms |
| M2 sweep (window 30d) | 4,548.1 ms |
| M2 sweep → promoted state visible on read | 4,563.7 ms |
| Writes (with embedding) | 641.6–992.9 ms |
| Reads / searches | 8.6–315.5 ms |

Observation L1 holds in kind (sweep ~4.5 s vs promotes 15–621 ms), but the
sweep was ~4× faster than run 3's ~17 s — same window, fewer qualifying
rows to scan or a warmer cache; no latency bar exists in the acceptance.

### Finding F1 — sweep re-promotes an already-promoted lesson (service behavior, diagnosed first-hand)

The M2 sweep returned **2 promotions, not 1**. The second is the MEM-025
run-2 lesson `b5bfbf85-f5ca-4c14-9ba7-22531d0d71da` (Muse 8,
`MUSE8-TEST-MEM-025`, created 2026-11-24T07:28:17Z), re-promoted
`SHARED → UNIVERSAL` via `promoted_dual_copy`, `path: auto_repeated_need`,
with the **same** `universal_copy_id: 32c9ed6e-…` its own sweep 2 created
on 2026-11-24. Verified first-hand after the probe:

- Its 12 need rows are all from 2026-11-24 (inference/stratex round-2
  needs, reason `TASK-MEM-025 auto-promotion proof run 2`) — no new needs
  since. Its needs are still inside the 30-day sweep window.
- Its promotion audit rows are now **3**: 2026-11-24 PRIVATE → SHARED,
  2026-11-24 SHARED → UNIVERSAL, and **2026-11-26T06:34:10Z SHARED →
  UNIVERSAL** — the duplicate row my sweep emitted.
- The copy `32c9ed6e-…` was created 2026-11-24T07:28:28Z; my sweep created
  **no new copy** (same id returned). The original is still SHARED.
- My 9 needs targeted only M2 (`4df56e2c-…`); no cross-talk from this run.

So the sweep is **not idempotent across runs**: any sweep while a
previously auto-promoted lesson's needs remain in the 30-day window
re-promotes it and appends a duplicate audit row. Until ~2026-12-24 every
sweep will re-promote `b5bfbf85-…`. The run-3 "blast radius exactly 1"
check assumed a clean slate; on the shared live service that assumption
no longer holds. This is filed here for the coordinator / Memora owner —
it does not change the M2 verdict (my memory was promoted by the sweep
exactly as the acceptance requires), and re-running the probe would only
append another duplicate row, so no re-run was done.

## Test data left behind (cleanup path)

- M1 `0efe49ae-3f8a-4bea-af6d-a194eb330ad7` — scope UNIVERSAL, namespace `memora://sentinel/private`.
- M1b `38e51b71-6919-49fd-b30d-e70cb49c514a` — scope UNIVERSAL, same namespace.
- M1b2 original `c7edf621-eeb2-4c94-a387-304d44154d4a` — scope PRIVATE; copy `97616310-470a-44a6-a5bd-f9943ce09cd4` — scope UNIVERSAL, same namespace.
- M2 `4df56e2c-3476-4236-aaae-f85465cd3061` — scope SHARED, same namespace.
- M3 `eb06703a-7360-4fc8-baef-9888994c48a9` — scope SHARED, same namespace.
- Cleanup (not done here — out of scope for a proof run): the owner or the memora service identity can remove the memories via `POST /v1/memories/{id}/forget` or `DELETE /v1/memories/{id}`. All memories carry `provenance.test_data: true` / `task: TASK-MEM-033`.
- Note: this run's sweep also appended a duplicate promotion audit row for the MEM-025 lesson `b5bfbf85-…` (Finding F1); no new copy was created.

## Next steps

1. Open the work PR with finished live evidence + board flip (MEM-033 CLAIMED → IN_REVIEW).
2. Coordinator merge; paired verifier to follow.
3. Then claim INT-041 (queue position 3, due 2026-11-27).

— Muse 15
