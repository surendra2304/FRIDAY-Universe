# TASK-MEM-018 — Memora: prove auto-promotion end-to-end with a real cross-agent workload on the live service

**Worker:** Muse 10 · **Date:** 2026-11-23 · **Branch:** `muse10/task-mem-018-auto-promotion-proof` · **Work commit:** (PR head — see board)
**Board:** TASK-MEM-018 (Memora: prove auto-promotion end-to-end with a real cross-agent workload on the live service)

## Verdict (read this first)

Auto-promotion works end to end on the live service, **both rungs**, with the
MEM-016 fix deployed. One fresh PRIVATE memory, 8 needs from 4 distinct
agents → sweep promotes PRIVATE → SHARED, non-owners read it (GET 200) and
find it in search (keyword 1.0). Four more needs from 2 outside agents →
next sweep promotes SHARED → UNIVERSAL, non-owners read it and find it.
MEM-014 G1 (promoted scope confers no readability) is closed by the fix;
MEM-014 G2 (sweep starves recent memories) is closed by the two-phase sweep.
One honest non-firing in the middle: sweep 2 returned `count: 0` because the
UNIVERSAL rule requires ≥ 2 needers NOT on the SHARED allow-list and all 4
first-round needers were on it — the rule working as specified, not a defect;
fresh outside demand unlocked it.

Acceptance mapping:

1. **Needs seeded from 4+ agents** — 6 distinct agents total (friday,
   intelx, futuris, cortex + inference, stratex), 12 needs.
2. **Promotion fires** — twice, both rungs, `path: auto_repeated_need`.
3. **Non-owner reads it** — GET 200 for friday / futuris / cortex at SHARED
   and UNIVERSAL; search finds it for friday and futuris at keyword 1.0.
4. **Evidence filed** — this doc. Raw service responses: 34 numbered JSON
   files in `/tmp/muse10_mem018/` on Oracle Server 1. No secrets in this doc
   or in any response quoted.

## How the proof ran

- **Live service:** `Memora.service` on Oracle Server 1, `GET /health` 200
  at 2026-11-22T20:47:20Z: `status: healthy`, `storage: oracle`,
  `database: healthy`, `database_backend: oracle`,
  `database_durable: true`, `vector_store: oracle_23ai_native_vector,
  dim 384, table memora_vector_store`, `version: 2.0.0`.
- **Deployed code:** `Memora/core/memory/promotion.py` carries the MEM-016
  two-phase sweep (lines 539–549: need-bearing candidates are evaluated
  first within the `limit` budget, TASK-MEM-016 / MEM-014 G2). Server 1
  checkout on branch `muse10/task-frd-037-chat-live-runs` at `db933cfc`
  (`get_system_info` this run).
- **Auth:** `X-Agent-Name` + per-agent `X-API-Key`
  (`Memora/apps/api/dependencies.py`). Keys were read from the service's own
  env file (`Memora/.env`) at runtime on the server and never left it; only
  key *names* are recorded here. Owner identity `sentinel`; needers `friday`,
  `intelx`, `futuris`, `cortex`, `inference`, `stratex`; sweeps as the
  `memora` service identity.
- **Test data:** one memory, content-prefixed `MUSE10-TEST-MEM-018` and
  provenance-marked `test_data: true`, `task: TASK-MEM-018`. Twelve need rows
  + two promotion audit rows for it. Nothing else was written; no live data
  was overwritten, no live DB or config was touched, no service was restarted.
  The probe scripts ran on Server 1 and were deleted from the server
  afterwards (MEM-014 pattern); the numbered JSON responses remain.

## The ladder

Memory `e451738c-63f0-4049-90ec-fd9ffb3101e6`, namespace
`memora://sentinel/private`, owner `sentinel`, created 2026-11-22T20:50:04Z.

| Step | Call | Result |
| --- | --- | --- |
| Write PRIVATE | `POST /v1/memories` (sentinel) | **201**. `storage_backend: oracle`, `lifecycle_state: active`. |
| Read as owner | `GET /v1/memories/{id}` (sentinel) | **200**, `scope: PRIVATE`. |
| Read as other | `GET /v1/memories/{id}` (friday) | **404** `Memory record with ID ... not found.` — existence hidden from non-owners. |
| Record needs, round 1 | `POST /v1/promotion/need` ×8 (friday ×2, intelx ×2, futuris ×2, cortex ×2) | **200** `need_recorded` ×8. Audit: 8 rows for this memory. |
| Sweep 1 | `POST /v1/promotion/sweep` `{window_days: 30}` (memora) | **200** `{count: 1, promotions: [{memory_id: e451738c..., from_scope: PRIVATE, to_scope: SHARED, path: auto_repeated_need}]}` — only the target promoted. |
| Read as needers | `GET /v1/memories/{id}` (friday, futuris) | **200**, `scope: SHARED`. |
| Search as needer | `GET /v1/memories/search?q=MUSE10-TEST-MEM-018&limit=50` (friday, futuris) | **200**, exactly the target (`keyword_score: 1.0`, `Lexical fast lane: full content-token match`, rank 1). |
| Sweep 2 | `POST /v1/promotion/sweep` `{window_days: 30}` (memora) | **200** `{count: 0, promotions: []}` — honest non-firing, see G1 below. Memory stays SHARED; futuris GET still **200**, cortex GET **200**. |
| Record needs, round 2 | `POST /v1/promotion/need` ×4 (inference ×2, stratex ×2) — agents NOT on the SHARED allow-list | **200** `need_recorded` ×4. Audit: 12 rows total for this memory, 6 distinct agents, 2 outside. |
| Sweep 3 | `POST /v1/promotion/sweep` `{window_days: 30}` (memora) | **200** `{count: 1, promotions: [{memory_id: e451738c..., from_scope: SHARED, to_scope: UNIVERSAL, path: auto_repeated_need}]}` — only the target promoted. |
| Read as needers | `GET /v1/memories/{id}` (futuris, cortex) | **200**, `scope: UNIVERSAL`. |
| Search as needer | `GET /v1/memories/search?q=MUSE10-TEST-MEM-018&limit=50` (futuris) | **200**, exactly the target (`keyword_score: 1.0`, rank 1). |

## Blast radius

- Pre-sweep audit (`GET /audit?action=MEMORY_NEED_RECORDED&limit=500`,
  memora): 21 need rows on two older memories — MEM-014 M2
  `b3562067-e808-415b-b16c-a633bd9d299b` (12 needs) and MEM-016 M2
  `d271b0ac-4d48-4555-be8e-0879274e7834` (9 needs). Neither was promoted by
  any of my three sweeps: both already sit SHARED with all their needers on
  their SHARED allow-lists, so the outside rule holds them too (see G1).
- Each sweep promoted only the target memory (`count: 1`, `count: 0`,
  `count: 1`). No other live memory was created, modified, or deleted.

## Gaps found

- **G1 (finding, rule as specified) — UNIVERSAL promotion needs fresh
  outside demand.** After a SHARED promotion the sweep puts the needers on
  the SHARED allow-list; a second sweep cannot promote to UNIVERSAL until
  ≥ 2 agents NOT on that list record needs (thresholds:
  `UNIVERSAL_MIN_DISTINCT_AGENTS = 4`, `UNIVERSAL_MIN_TOTAL_NEEDS = 8`,
  `UNIVERSAL_MIN_OUTSIDE_AGENTS = 2`). The rule is explicit in
  `promotion.py` and the behaviour matches it — sweep 2 returned `count: 0`
  with no error. Consequence: a memory whose whole audience already needs
  it stalls at SHARED until new agents ask. Worth a coordinator decision,
  not a fix in this task: whether UNIVERSAL should count total distinct
  needers instead of outside-only.
- **G2 (minor) — `/v1/memories/search` returns a top-level JSON list, not
  an object with a `results` key.** Tooling that assumes an object shape
  will misread it (my first probe summary printed `{}` for the same reason;
  the files prove the target was present in each search).
- **G3 (minor) — MEM-014's M2 and MEM-016's M2 still sit SHARED** with 12
  and 9 needs respectively, above the UNIVERSAL thresholds on every count
  except the outside rule. They will promote the moment 2 outside agents
  need them — expected behaviour under the rule, noted so nobody is
  surprised when a future sweep moves them.

## Test data left behind (cleanup path)

- M1 `e451738c-63f0-4049-90ec-fd9ffb3101e6` — scope UNIVERSAL, namespace
  `memora://sentinel/private`, content prefixed `MUSE10-TEST-MEM-018`.
- Cleanup (not done here — out of scope for a proof run): the owner or the
  memora service identity can remove the memory via
  `POST /v1/memories/{id}/forget` or `DELETE /v1/memories/{id}`. The memory
  carries `provenance.test_data: true` / `task: TASK-MEM-018` for
  identification.

## What was NOT done

- No live database or config was written to directly; no service was
  restarted; no live memory besides the one marked test record was created,
  modified, or deleted.
- The master key was not used. No key, token, password, or secret value
  appears in this doc, in any issue comment, or in any probe script (the
  scripts ran on Server 1, read keys from the service env file at runtime,
  and were deleted from the server afterwards).

— Muse 10
