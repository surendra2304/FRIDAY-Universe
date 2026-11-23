# TASK-MEM-019 — Memora: prove the failed-experiment lesson rule live

**Worker:** Muse 10 · **Date:** 2026-11-23 · **Branch:** `muse10/task-mem-019-failed-experiment-lesson` · **Work commit:** (PR head — see board)
**Board:** TASK-MEM-019 (Memora: prove the failed-experiment lesson rule live — one real failed-experiment lesson lands PRIVATE and UNIVERSAL with correct readability in both)

## Verdict (read this first)

The failed-experiment lesson rule **works for direct reads and fails for
search**. One real lesson, written PRIVATE as sentinel, owner-promoted to
UNIVERSAL: the original stays PRIVATE (owner GET 200, non-owner GET 404)
and a UNIVERSAL copy is created with identical content
(`promoted_dual_copy`, copy `8cfcaeb6cc-…`), readable by non-owners
(friday GET 200, futuris GET 200, scope UNIVERSAL). Re-promotion is
idempotent at the copy level (same copy id, no second copy). But the
UNIVERSAL copy is **invisible in search to the promotion audience**: friday
searching for the lesson's exact distinctive content gets 100 results with
a max keyword score of 0.079 and the copy nowhere among them, while the
owner's identical query finds the original at keyword 1.0 (**G1**). The
acceptance's search leg is therefore not met for the copy; the direct-GET
leg is met in full. A second, minor wart: the idempotent re-promotion
writes a second `MEMORY_SCOPE_PROMOTED` audit row for the same copy
(**G2**).

Acceptance mapping:

1. **One real failed-experiment lesson written live** — yes: sentinel,
   `POST /v1/memories` 201, id `270d1a53-7e3c-4f18-ad00-829ff3c734e1`,
   provenance `failed_experiment: true`, `experiment_outcome: failed`,
   `lesson_type: failed_experiment`, created 2026-11-22T22:47:37Z.
2. **Lands PRIVATE** — yes: read-back scope PRIVATE; owner GET 200,
   friday GET 404 (existence hidden).
3. **Promotes to UNIVERSAL, original stays PRIVATE** — yes: owner promote
   200, `status: promoted_dual_copy`, `universal_copy_id`
   `8cfcaeb6-cc9c-446c-88d1-4797a469fbce`; original still scope PRIVATE
   afterwards (owner GET 200, friday GET 404).
4. **Correct readability in both scopes, direct GET** — yes: PRIVATE
   original owner-only; UNIVERSAL copy friday GET 200 and futuris GET 200,
   scope UNIVERSAL, content byte-identical,
   `provenance.promoted_from_memory_id` = original id.
5. **Correct readability in both scopes, search** — half: owner search
   finds the original at keyword 1.0 (exactly 1 result); friday search
   does **not** find the copy for the same distinctive content (limit 50
   and limit 100 both miss it; max keyword 0.079) — see G1.
6. **Evidence filed** — this doc. Raw service responses: 12 numbered JSON
   files in `/tmp/muse10_mem019/` on Oracle Server 1. No secrets in this
   doc or in any response quoted.

## How the proof ran

- **Live service:** `Memora.service` on Oracle Server 1, active (running)
  since 2026-11-23 01:32:49 IST, `uvicorn app.main:app` on port 8002.
  `GET /health` 200 at 2026-11-22T22:47:36Z: `status: healthy`,
  `storage: oracle`, `database: healthy`, `database_backend: oracle`,
  `database_durable: true`, `vector_store: oracle_23ai_native_vector,
  dim 384, table memora_vector_store`, `version: 2.0.0`.
- **Deployed code:** Server 1 checkout `main` at `3f9cec0c` (merge PR
  #1404). The rule is live in the deployed code:
  `is_failed_experiment_lesson` (`Memora/core/memory/promotion.py:116`),
  dual-copy in `_apply_promotion` (`promotion.py:431-468`, result
  `promoted_dual_copy` at :670), revert refusal for dual copies
  (`promotion.py`, `revert_scope`).
- **Auth:** `X-Agent-Name` + per-agent `X-API-Key`
  (`Memora/apps/api/dependencies.py`). Keys were read from the service's
  own env file (`Memora/.env`) at runtime on the server and never left it;
  only key *names* are recorded here. Owner identity `sentinel`;
  non-owners `friday`, `futuris`; audit read as the `memora` service
  identity.
- **Test data:** one lesson, content-prefixed `MUSE10-TEST-MEM-019` and
  provenance-marked `test_data: true`, `task: TASK-MEM-019`, plus its one
  UNIVERSAL copy. Nothing else was written; no live data was
  overwritten, no live DB or config was touched, no service was
  restarted, no sweep was run (owner path only — no other memory could
  have been promoted by this proof).
- **Probe:** script `probe_mem019.py` (kept with this task's working
  notes), run on Server 1 via heredoc; it wrote the 12 numbered JSON
  responses to `/tmp/muse10_mem019/` and printed the status ladder. Two
  follow-up search diagnostics ran the same way.

## The rule (cited)

`Memora/core/memory/promotion.py`, `is_failed_experiment_lesson`
(:116-130): a record is a failed-experiment lesson when its provenance
carries `failed_experiment: true`, an `experiment_outcome` of
`failed`/`failure`, or a `lesson_type` of `failed_experiment`.
`promote_scope` docstring: "A failed-experiment lesson promoted to
UNIVERSAL keeps its PRIVATE original and gains a UNIVERSAL copy instead
of moving." `_apply_promotion` returns `status: promoted_dual_copy` with
`universal_copy_id`; the copy carries the original's content and
`provenance.promoted_from_memory_id`. A second promotion returns the same
copy id (unit test `test_failed_experiment_lesson_stays_private_and_goes_universal`,
`Memora/tests/test_mem013_memory_promotion.py:171`). The auto-promotion
variant (SHARED + enough needs → sweep dual-copies) is covered by
`test_auto_promotion_of_failed_experiment_uses_dual_copy` (:265); this
proof exercises the owner path, which is the rule's core.

## The ladder

Original `270d1a53-7e3c-4f18-ad00-829ff3c734e1`, namespace
`memora://sentinel/private` (namespace id
`cfa7ef64-6712-4deb-bb6d-f5932da4d478`), owner `sentinel`, created
2026-11-22T22:47:37Z. Copy `8cfcaeb6-cc9c-446c-88d1-4797a469fbce`, same
namespace id, created by the promotion at 22:47:38Z.

| Step | Call | Result |
| --- | --- | --- |
| Write PRIVATE | `POST /v1/memories` (sentinel), provenance `failed_experiment: true`, `experiment_outcome: failed`, `lesson_type: failed_experiment`, idempotency key `muse10-mem019-001` | **201**. `storage_backend: oracle`, `lifecycle_state: active`. Provenance on read-back carries all three markers plus `test_data: true`, `task: TASK-MEM-019`. |
| Read as owner | `GET /v1/memories/{id}` (sentinel) | **200**, `scope: PRIVATE`, `shared_with: null`, content verbatim. |
| Read as other | `GET /v1/memories/{id}` (friday) | **404** `Memory record with ID ... not found.` — existence hidden from non-owners. |
| Promote → UNIVERSAL | `POST /v1/promotion/promote` `{memory_id, target_scope: UNIVERSAL}` (sentinel) | **200** `{status: promoted_dual_copy, scope: PRIVATE, to_scope: UNIVERSAL, path: owner_judgement, universal_copy_id: 8cfcaeb6…}`. |
| Read original as owner | `GET /v1/memories/{id}` (sentinel) | **200**, `scope: PRIVATE` — the original never moved. |
| Read original as other | `GET /v1/memories/{id}` (friday) | **404**, same not-found detail. |
| Read copy as non-owner | `GET /v1/memories/{copy_id}` (friday) | **200**, `scope: UNIVERSAL`, content byte-identical to the original, `provenance.promoted_from_memory_id` = original id, `promoted_by: sentinel`, `promotion_path: owner_judgement`. |
| Read copy as outsider | `GET /v1/memories/{copy_id}` (futuris) | **200**, `scope: UNIVERSAL`. |
| Search as non-owner | `GET /v1/memories/search?q=MUSE10-TEST-MEM-019&limit=50` (friday) | **200**, 50 results; neither the copy nor the original among them (see G1). |
| Search as non-owner, distinctive | `GET /v1/memories/search?q=momentum breakout entry 2x ATR stop volume filter&limit=100` (friday) | **200**, 100 results, max `keyword_score` 0.079, **copy absent** (see G1). |
| Search as owner, distinctive | Same query (sentinel) | **200**, exactly 1 result: the original, `keyword_score: 1.0`. The copy is not in the owner's results either (see G1 note). |
| Re-promote (idempotency) | `POST /v1/promotion/promote` `{memory_id, target_scope: UNIVERSAL}` (sentinel), second time | **200**, same `universal_copy_id` `8cfcaeb6…` — no second copy. But a second `MEMORY_SCOPE_PROMOTED` audit row was written (see G2). |
| Audit | `GET /audit?action=MEMORY_SCOPE_PROMOTED&limit=100` (memora) | **200**. Two rows for the original (22:47:38Z, 22:47:44Z), both `{from_scope: PRIVATE, to_scope: UNIVERSAL, promoted_by: sentinel, path: owner_judgement, failed_experiment_dual: true, universal_copy_id: 8cfcaeb6…}`. |

## Blast radius

- Only the one lesson and its one copy were created, plus the two audit
  rows above. No sweep ran, so no other live memory was evaluated or
  moved. No live memory was created, modified, or deleted besides the
  two marked test records.

## Gaps found

- **G1 (finding — search leg of the acceptance) — The UNIVERSAL dual copy
  is invisible in search to non-owners.** Direct GET honours the copy's
  UNIVERSAL scope (friday/futuris 200 — the MEM-016 fix working), but
  friday's search for the copy's exact distinctive content returns 100
  loosely-related records (max keyword 0.079) with the copy absent, at
  both limit 50 and limit 100, minutes after creation; the owner's
  identical query finds the original at keyword 1.0 within a minute of
  its creation, so this is not a plain indexing delay. The copy is
  `lifecycle_state: active`, same namespace as the original. Note the
  owner's distinctive-content search returns exactly the original and
  not the copy either — consistent with the copy never entering the
  searchable set for any caller, or with search deduping identical
  content to one record. Contrast MEM-018, where friday's search found
  the auto-promoted (moved, not copied) record at keyword 1.0. Fix
  direction: check whether the dual-copy path in `_apply_promotion`
  (`promotion.py:431-468`) skips the search-index write the normal
  write pipeline performs, and whether the search policy gate
  (`core/memory/search_service.py`, the `_record_passes_filters` gate
  cited in MEM-014 G1) honours scope for promotion-created copies.
  Consequence: a fleet agent that learns of a failed-experiment lesson
  only through search will never find it; only agents holding the copy
  id (or the owner) can read it.
- **G2 (minor) — Idempotent re-promotion still writes an audit row.**
  The second promote returned the same `universal_copy_id` and created
  no second copy (correct), but the audit holds two
  `MEMORY_SCOPE_PROMOTED` rows for one promotion (22:47:38Z and
  22:47:44Z, identical details). An audit consumer counting promotion
  rows will double-count this promotion. Fix direction: return the
  existing copy before writing the audit row on the already-promoted
  path.

## Test data left behind (cleanup path)

- Original `270d1a53-7e3c-4f18-ad00-829ff3c734e1` — scope PRIVATE,
  namespace `memora://sentinel/private`, content prefixed
  `MUSE10-TEST-MEM-019`.
- Copy `8cfcaeb6-cc9c-446c-88d1-4797a469fbce` — scope UNIVERSAL, same
  namespace, same content, `provenance.promoted_from_memory_id` =
  original id.
- Cleanup (not done here — out of scope for a proof run): the owner or
  the memora service identity can remove the records via
  `POST /v1/memories/{id}/forget` or `DELETE /v1/memories/{id}`. Note
  `revert_scope` refuses dual-copy promotions ("the copy is a separate
  record and must be dealt with on its own"), so the copy must be
  forgotten on its own; the original never moved, so there is nothing
  to revert on it. Both records carry `provenance.test_data: true` /
  `task: TASK-MEM-019` for identification.

## What was NOT done

- No live database or config was written to directly; no service was
  restarted; no live memory besides the two marked test records was
  created, modified, or deleted; no sweep was run.
- The auto-promotion variant of the dual-copy rule (SHARED + needs →
  sweep) was not exercised live; it is covered by the unit test
  `test_auto_promotion_of_failed_experiment_uses_dual_copy` and the
  sweep mechanics were proven live in MEM-018.
- The master key was not used. No key, token, password, or secret value
  appears in this doc, in any issue comment, or in any probe script (the
  probes ran on Server 1, read keys from the service env file at
  runtime, and left no script file behind — the probe ran via heredoc;
  only the numbered JSON responses remain in `/tmp/muse10_mem019/`).

— Muse 10
