# TASK-MEM-015: Memora viking persistence + promotion audit trail with undo

**Worker:** Muse 10 · **Date:** 2026-11-22 · **Branch:** `muse10/task-mem-015-viking-persistence-audit`
**Board:** TASK-MEM-015 (Memora: persist the viking context layer to Oracle ADB or mark it explicitly ephemeral in API responses + promotion audit trail with undo)

## Verdict (read this first)

Both halves are implemented, tested, and — for the persistence half — proven
live against Oracle ADB. The viking layer **is** ADB-backed on writes: a
clearly-marked test file written through the live API landed in the
`context_snapshots` row, verified by an independent fresh-process load. What
was missing was not the store but the *signal*: no `/v1/context` response
said whether the layer was durable, and the `stats()` durability receipt
carried stale restore-time file counts (live: 18 vs the real 22). Every
`/v1/context/*` response now carries a `durability` label with live counts,
and a store-less service says `ephemeral` explicitly. The promotion audit
trail already existed; the missing piece was the undo — `POST
/v1/promotion/revert` now demotes exactly one rung from the latest promotion
audit row and writes a `MEMORY_SCOPE_DEMOTED` row pointing at it.

One acceptance item stays open: the **live restart write/read probe** (G1).
Restarting Memora needs Muse's clearance under the standing rule, so it was
not run. The test file is already sitting in the ADB snapshot row, ready to
be re-read after the next authorised restart.

## Acceptance mapping

1. **No agent can mistake the viking layer for durable memory** — met by
   both arms. (a) ADB-backed: proven live for writes (see M1 below); the
   restart half is G1, outstanding. (b) Labelling: every `/v1/context/*`
   response now carries `durability` (`enabled`, `state`, `backend`,
   `node_count`, live `files`, `updated_at`); a store-less service reports
   `enabled: false, state: ephemeral` with an explicit note. The stale
   receipt counts that made `stats()` under-report files are fixed in the
   label (G4).
2. **Every promotion writes an audit record reversible by one call** — the
   audit rows already existed (`MEMORY_SCOPE_PROMOTED` with `from_scope`,
   `to_scope`, `promoted_by`, `path`, `shared_with`, `evidence`, verified
   live for the MEM-014 M1 memory). `POST /v1/promotion/revert` is the one
   call: owner or Memora service identity only, one rung, allow-list rows
   granted by that promotion removed, `MEMORY_SCOPE_DEMOTED` row written
   with `reverts_audit_id`. Proven by 10 new tests including the API flow.
3. **Evidence filed** — this doc.

## What was probed live

- **Live service:** `Memora.service` on Oracle Server 1, active (running)
  since 2026-11-22 11:30:34 IST, `uvicorn app.main:app` on port 8002.
  `GET /health` 200: `status: healthy`, `storage: oracle`,
  `database_durable: true`, `version: 2.0.0`. Server 1 checkout `bbf7bd87`
  (merge PR #1371) — older than this branch's base, but it already carries
  the MEM-010 snapshot code.
- **M1 — viking write reaches ADB (2026-11-22 ~19:36 IST):**

  | Step | Call | Result |
  | --- | --- | --- |
  | Baseline stats | `GET /v1/context/stats` | **200**. `files: 21, memories: 19`, `durability: {enabled: true, state: saved, node_count: 27, backend: relational, updated_at: 2026-11-22T13:42:06Z}` |
  | Write test file | `POST /v1/context/write` `viking://user/memora/memories/fact/muse10-test-mem015.md` | **200**, `tokens: 26`, tags `["test", "mem015"]`. No auth header required from localhost (see G6). |
  | Stats after | `GET /v1/context/stats` | **200**. `files: 22, memories: 20`, `durability.state: saved`, `node_count: 29`, `updated_at: 2026-11-22T14:06:48Z` — a fresh save at the write time. Note the receipt's `files: 18` stayed at its restore-time value while live files are 22 — the stale-count wart fixed by this task (G4). |
  | Read back | `GET /v1/context/read` (L2) | **200**, content verbatim. |
  | Independent ADB load | Fresh process on Server 1, `RelationalContextSnapshotStore(tenant default, scope memora).load()` | Row present: `node_count: 29, files: 22`, **test URI present in the stored payload nodes**. The write is in Oracle ADB, not just in the service's memory. |
- **M2 — promotion audit trail is live and revert-readable:** fresh-process
  read-only query of `audit_logs` for the MEM-014 M1 memory
  (`2f51fc7b-af02-45b3-b4a1-788760991fb8`): 3 rows — `policy_approved` (1),
  `MEMORY_SCOPE_PROMOTED` PRIVATE → SHARED (owner_judgement, sentinel),
  `MEMORY_SCOPE_PROMOTED` SHARED → UNIVERSAL (owner_judgement, sentinel).
  DB totals: 2 promoted rows, **0 demoted rows** (the revert endpoint does
  not exist in production yet — it ships in this PR).
- **Code read (branch base 3dd7cfba, Server 2):** `PersistentContextDatabase`
  (`real_viking_context.py:1221-1566`) persists after every mutation
  (`write`/`mkdir`/`rm`/`move`/`remember`/`open_session`/`commit_session`);
  `RelationalContextSnapshotStore` (`context_durability.py`, table
  `context_snapshots`, sha256-verified load, fail-closed save guard);
  lifespan restore + `stats()` in `apps/api/main.py:162-178`; service
  construction in `context_service.py` (`_build_default_service`,
  `_durability_store`); promotion module `core/memory/promotion.py`
  (monotonic, audit rows, no undo — the gap).

## What changed

- **`Memora/core/memory/promotion.py`** (+152/−~0): `ACTION_DEMOTED =
  "MEMORY_SCOPE_DEMOTED"` (line 79); `MemorySharedAgent` import;
  `MemoryPromotionService.revert_scope` (def line 258) — see design below;
  module docstring notes the audited exception to monotonicity;
  `ACTION_DEMOTED` exported.
- **`Memora/apps/api/routers/v1_promotion.py`** (+29): `RevertRequest`
  (`memory_id`, `reason`) and `POST /v1/promotion/revert` (line ~74),
  actor from the authenticated header, 403/404 mapping like `/promote`.
- **`Memora/core/memory/context_service.py`** (+67/−~16):
  `MemoraContextService.durability()` (line 193) — the label; `stats()`
  now uses it; `write`/`read`/`remember`/`commit_session`/`compile_wiki`
  include it; router `layers`/`ls`/`tree`/`grep`/`find`/`search` include
  it. Every `/v1/context/*` response now carries `durability`.
- **`Memora/tests/test_mem015_promotion_revert.py`** (new, 288 lines, 10
  tests) and **3 labelling tests appended to
  `Memora/tests/test_viking_context_durability.py`** (lines 263-329).
- **Environment note (not in the repo):** `alembic` 1.20.1 installed into
  the test venv `/opt/friday_universe/venv` — it is a declared requirement
  (`requirements.txt`, `pyproject.toml`) but was missing, so the
  `test_mem013` API test errored at collection. The production venv
  (`venv312`, used by `Memora.service`) was not touched.

### Revert design (the part that needed a decision)

`revert_scope(db, actor_name, memory_id, reason)`:

- Only the owning agent or the Memora service identity may revert — the
  same actors allowed to promote. A non-owner gets 403.
- The **latest** `MEMORY_SCOPE_PROMOTED` audit row is the source of truth:
  the record is demoted to that row's `from_scope`, and only the
  `shared_with` agents that row lists have their `memory_shared_agents`
  rows removed. A `MEMORY_SCOPE_DEMOTED` row is written with
  `reverts_audit_id` pointing at the promotion, plus `reverted_by`,
  `path`, `reason`, `shared_with_revoked`.
- Reverting UNIVERSAL → SHARED keeps the earlier SHARED promotion's
  allow-list intact (that promotion was never undone), so visibility returns
  to exactly what it was before the UNIVERSAL step. Reverting SHARED →
  PRIVATE removes the membership rows; `record_is_visible` already treats
  PRIVATE as owner-only regardless of leftover rows, so the demotion is
  airtight even if a row were missed.
- Refusals, all explicit, no silent partial undo: no promotion on record
  (404); already reverted (idempotent `already_reverted` no-op, no second
  demotion row); scope moved since the promotion (403 — a revert never
  skips a rung); dual-copy promotion of a failed-experiment lesson (403 —
  the UNIVERSAL copy is a separate record, see G2).
- `promote_scope` itself is untouched: promotion stays monotonic there; the
  revert is the one audited exception.

### Durability label shape

Snapshot-backed: `{"enabled": true, "state": "saved"|"restored"|"empty",
"backend": "relational", "tenant_id", "scope_key", "node_count",
"files": <live count>, "updated_at"}`. Store-less: `{"enabled": false,
"state": "ephemeral", "backend": null, "note": "in-memory only; content is
lost on restart"}`. `files` comes from the live `stats()` call, not the
restore-time receipt.

## Tests

Targeted suites on Server 2 (`venv/bin/python -m pytest`, 2026-11-22
~19:40 IST): **31 passed in 13.12s** —
`test_mem015_promotion_revert.py` (10), `test_viking_context_durability.py`
(9, incl. 3 new labelling tests), `test_mem013_memory_promotion.py` (12,
unchanged behaviour). Baseline before the change was 18/18 on the latter
two files. Full `Memora/tests/` suite (2026-11-22 ~19:50 IST, excluding
`test_deployment_packaging.py`, which cannot be collected under the test
venv's Python 3.10 — `import tomllib` needs 3.11+): **800 passed, 60
failed, 2 skipped**. A/B on pristine main (3dd7cfba worktree, same 60 node
IDs): **the identical 60 failed** — zero regressions from this change; the
60 are pre-existing environment/contract failures (Oracle/postgres policy,
resilience probes, phase-16 hardening, namespace migration, telemetry).

## Gaps found

- **G1 (open, needs Muse's clearance) — Live restart write/read probe not
  run.** Acceptance arm (a) is proven for writes only. A real Memora
  restart + re-read of `viking://user/memora/memories/fact/muse10-test-mem015.md`
  is still owed; restarting the service needs Muse's clearance under the
  standing rule, and deploying this PR's code to production rides the same
  clearance. The test file is already in the ADB snapshot row, so the probe
  is: restart with clearance, `GET /v1/context/read` the test URI, confirm
  content verbatim and `durability.state: restored`.
- **G2 — Dual-copy promotions cannot be reverted by demotion.** A
  failed-experiment lesson promoted to UNIVERSAL keeps its PRIVATE original
  and gains a separate UNIVERSAL copy; `revert_scope` refuses with a clear
  error rather than deleting the copy. Needs coordinator direction: should
  the revert delete the UNIVERSAL copy (destructive), or is refusal the
  intended semantics?
- **G3 — Namespace-level grants survive a revert.** Revert removes only
  record-level `memory_shared_agents` rows. A record also shared via
  `/share` (or write-time SHARED, MEM-014 G4) keeps its namespace-wide
  `AccessGrant`. For promotion-only reverts this does not leak — promotion
  never mints namespace grants — but a record shared both ways keeps the
  namespace grant after revert. Direction needed on whether revert should
  also revoke `/share` grants.
- **G4 (fixed in the label, noted) — `last_snapshot` receipt counts go
  stale.** The receipt's `files`/`dirs`/`sessions`/`commits` are
  restore-time values; only `state` and `node_count` update on save (live
  proof: receipt `files: 18` vs live `files: 22`). `durability()` now
  reports live counts; any other consumer reading `last_snapshot` directly
  should use `durability()` instead.
- **G5 — MEM-014 G1/G2 still open, untouched by this task.** Promoted scope
  still confers no readability through the policy engine, and the
  auto-promotion sweep still only examines the 200 oldest records. The
  revert is correct bookkeeping on top of those behaviours, not a fix for
  them; the MEM-016 draft covers G1+G2.
- **G6 (observation) — `/v1/context/*` takes no agent auth at the app
  layer.** The live probe wrote and read from Server 1 localhost with no
  `X-Agent-Name`/`X-API-Key` headers and got 200s. Whether the public
  ingress (Caddy) adds auth in front was not probed. Pre-existing, not
  changed here; flagged because this task's probe wrote live data through
  it.

## Test data left behind (cleanup path)

- Live viking file `viking://user/memora/memories/fact/muse10-test-mem015.md`
  (content prefixed `MUSE10-TEST-MEM-015`, tags `test`/`mem015`) — now part
  of the durable snapshot row `(tenant default, scope memora)`, node_count
  29. It is the G1 probe's re-read target; remove it (via a future context
  delete route or a maintenance action) only after the restart probe, or
  leave it as the standing durability canary. No live memory record was
  created, modified, or deleted; no promotion was reverted live (the
  endpoint is not deployed); no service was restarted.
- MEM-014 test memories (M1/M2/M3) and the friday namespace grant remain as
  documented in `TASK-MEM-014-THREE-SECTION-PROOF.md`; this task only read
  their audit rows.

## What was NOT done

- No live restart, no production deploy (both need Muse's clearance — G1).
- No live database or config was written to directly; the only live write
  was the one clearly-marked viking test file through the public API, which
  the snapshot store then persisted to ADB by design.
- No key, token, password, or secret value appears in this doc, in any
  issue comment, or in the probe scripts (keys/env were read on the server
  at runtime and never printed; the probe scripts were deleted from the
  server afterwards). Probe scripts kept locally:
  `~/workspace/goals/friday-universe-muse-10-worker-role/hidden_files/mem015/probe_snapshot.py`,
  `probe_audit.py` (they print counts and scopes only).
- Bridge flakiness noted: `edit_file`/`run_shell` dropped roughly half the
  calls during this run ("MCP request did not complete", "MCP event stream
  ended"); every write was verified by a read before proceeding, and
  retries succeeded. No write was applied twice — all edit scripts are
  idempotent.

— Muse 10
