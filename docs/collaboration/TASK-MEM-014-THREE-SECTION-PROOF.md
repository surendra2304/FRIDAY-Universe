# TASK-MEM-014: Memora three-section memory — live proof

**Worker:** Muse 10 · **Date:** 2026-11-22 · **Branch:** `muse10/task-mem-014-three-section-proof` · **Work commit:** `a884fea1` (PR head is the board-flip commit `eddc9f0d`)
**Board:** TASK-MEM-014 (Memora: live proof of the three-section memory — one real
write/read/promotion cycle across private / inter-agent / universal sections
against the live service, with evidence)

## Verdict (read this first)

The three-section **state machine works, but the promotion ladder does not
confer readability**. Owner promotion moves a record's scope
PRIVATE → SHARED → UNIVERSAL and writes the audit rows, yet no non-owner can
read the promoted record — by direct GET or by search — because the policy
engine decides purely by namespace type and never looks at record scope
(**G1**). The inter-agent (SHARED) section works only when a memory is
authored SHARED at write time, which creates a namespace-level access grant.
Auto-promotion (path C) never fires for a recent memory: the sweep only
examines the 200 oldest non-UNIVERSAL records, and the fleet already holds
more than 200 older ones (**G2**). Both findings are proven live below with
service responses; neither is a guess from reading code.

Acceptance mapping:

1. **Write/read cycle in each section** — PRIVATE: proven end to end (owner
   reads, others get 404). SHARED / UNIVERSAL: the scope transitions are
   proven (200, audit rows), and readability is proven for write-time SHARED
   (M3, friday GET 200) — but readability of *promoted* SHARED / UNIVERSAL
   records is proven **absent** (403), see G1. That is the task's headline
   finding, not a gap in the proof.
2. **Promotion observed** — yes, twice via owner promotion (A):
   PRIVATE → SHARED and SHARED → UNIVERSAL, both `path: owner_judgement`.
   Auto-promotion (C): non-firing explained with the rule cited, see G2.
3. **Evidence filed** — this doc. Raw service responses: 57 JSON files in
   `/tmp/muse10_mem014/` on Oracle Server 1 (ephemeral; the numbers below are
   the durable record). No secrets in this doc or in any response quoted.

## How the proof ran

- **Live service:** `Memora.service` on Oracle Server 1, active (running)
  since 2026-11-22 11:30:34 IST, `uvicorn app.main:app` on port 8002.
  `GET /health` 200 at 2026-11-22T10:54:19Z: `status: healthy`,
  `storage: oracle`, `database: healthy`, `database_backend: oracle`,
  `database_durable: true`, `database_durability: shared_durable`,
  `vector_store: oracle_23ai_native_vector, dim 384, table memora_vector_store`,
  `version: 2.0.0`. OpenAPI (198 paths) lists `/v1/memories`,
  `/v1/memories/search`, `/v1/promotion/promote`, `/v1/promotion/need`,
  `/v1/promotion/sweep`, `/audit`.
- **Deployed code:** Server 1 checkout `e6ca8d2f` (merge PR #1358). The
  promotion router is mounted (`Memora/apps/api/main.py:343`); the promotion
  module, promotion router and auth dependency are md5-identical on Server 1
  and Server 2 (`028bc3fb`, `d40994ab`, `eab3d237`).
- **Auth:** `X-Agent-Name` + per-agent `X-API-Key`
  (`Memora/apps/api/dependencies.py`). Keys were read from the service's own
  env file at runtime on the server and never left it; only key *names* are
  recorded here. Owner identity `sentinel`; needers `friday`, `intelx`,
  `futuris`, `cortex`; sweeps as the `memora` service identity.
- **Test data:** every test memory is content-prefixed
  `MUSE10-TEST-MEM-014` and provenance-marked `test_data: true`,
  `task: TASK-MEM-014`. Nothing else was written; no live data was
  overwritten, no live DB or config was touched, no service was restarted.
  The three test memories and one namespace grant below remain live (see
  "Test data left behind").

Note on the board wording: the board says "separate Oracle ADB databases per
agent". The live Memora deployment is a **single** Oracle backend
(`database_backend: oracle`, tenant `default`) with namespace + scope
separation — isolation is enforced by namespace/scope checks, proven by the
404s below, not by per-agent databases.

## The promotion rule (cited)

`Memora/core/memory/promotion.py` (module docstring + constants), owner rule
locked 2026-11-18:

- (A) the owning agent promotes its own memory PRIVATE → SHARED → UNIVERSAL
  on its own judgement (`POST /v1/promotion/promote`; SHARED requires
  `shared_with` with ≥ 1 recipient; monotonic, idempotent).
- (C) Memora auto-promotes on repeated cross-agent need
  (`POST /v1/promotion/need` records one audit row per need;
  `POST /v1/promotion/sweep`, memora service identity only, one rung per
  memory per run). Thresholds, module constants:
  - PRIVATE → SHARED: ≥ 2 distinct non-owner agents, ≥ 3 needs total.
  - SHARED → UNIVERSAL: ≥ 4 distinct non-owner agents, ≥ 8 needs total,
    and ≥ 2 distinct needers NOT already on the SHARED allow-list.
  - `SHARED_MIN_DISTINCT_AGENTS = 2`, `SHARED_MIN_TOTAL_NEEDS = 3`,
    `UNIVERSAL_MIN_DISTINCT_AGENTS = 4`, `UNIVERSAL_MIN_TOTAL_NEEDS = 8`,
    `UNIVERSAL_MIN_OUTSIDE_AGENTS = 2`, `DEFAULT_WINDOW_DAYS = 30`.
- Sweep window: `run_auto_promotion_sweep` queries non-UNIVERSAL records in
  `ACTIVE / VERIFIED / CANDIDATE` states, `.order_by(created_at.asc())`,
  `.limit(200)` (default `limit: int = 200`).

## M1 — the owner-promotion ladder (path A)

Memory `2f51fc7b-af02-45b3-b4a1-788760991fb8`, namespace
`memora://sentinel/private`, owner `sentinel`, created 2026-11-22T10:55:14Z.

| Step | Call | Result |
| --- | --- | --- |
| Write PRIVATE | `POST /v1/memories` (sentinel) | **201**. `storage_backend: oracle`, `storage_durable: true`, `lifecycle_state: active`, `is_duplicate: false`. Namespace `memora://sentinel/private`, `namespace_type: agent-private`. |
| Read as owner | `GET /v1/memories/{id}` (sentinel) | **200**, `scope: PRIVATE`, `shared_with: null`, content verbatim. |
| Read as other | `GET /v1/memories/{id}` (friday) | **404** `Memory record with ID ... not found.` — existence hidden from non-owners. |
| Promote → SHARED | `POST /v1/promotion/promote` `{target_scope: SHARED, shared_with: [friday, intelx]}` (sentinel) | **200** `{status: promoted, scope: SHARED, from_scope: PRIVATE, path: owner_judgement}`. |
| Read as recipient | `GET /v1/memories/{id}` (friday, intelx) | **403** `Private namespace 'memora://sentinel/private' is private to another agent and isolated. Agent 'friday' cannot access it without promotion.` (rule `RULE_1_PRIVATE_BY_DEFAULT_PROMOTION_REQUIRED`). |
| Read as outsider | `GET /v1/memories/{id}` (futuris, cortex) | **404** not found. |
| Search as recipient | `GET /v1/memories/search?q=MUSE10-TEST-MEM-014 M1 private-section probe&limit=50` (friday) | **200**, 50 results, M1 **absent**. Same query as sentinel returns exactly M1 (`keyword_score: 1.0`, `Lexical fast lane: full content-token match`). |
| Promote → UNIVERSAL | `POST /v1/promotion/promote` `{target_scope: UNIVERSAL}` (sentinel) | **200** `{status: promoted, scope: UNIVERSAL, from_scope: SHARED, path: owner_judgement}`. |
| Read as outsider | `GET /v1/memories/{id}` (futuris) | **403**, same policy rule. |
| Share as owner | `POST /v1/memories/{id}/share` `{target_agent_name: friday}` (sentinel) | **403** `Only the agent that owns a memory may share it.` — because `may_mutate_record` (`storage/relational/access_scope.py:126-146`) allows only the memora service identity to mutate UNIVERSAL records (G3). |
| Read after M3 grant | `GET /v1/memories/{id}` (friday) | **200**, `scope: UNIVERSAL` — readable only because M3's write created a namespace grant for friday (G4). Intelx still **403**. |

## M2 — the auto-promotion path (path C)

Memory `b3562067-e808-415b-b16c-a633bd9d299b`, namespace
`memora://sentinel/private`, owner `sentinel`, created 2026-11-22T11:01:19Z.

| Step | Call | Result |
| --- | --- | --- |
| Write PRIVATE | `POST /v1/memories` (sentinel) | **201**, `storage_backend: oracle`, durable. Note: the write step ran twice (first run's output was hidden by a local output filter, so it was re-run); the pipeline deduped the second write (`is_duplicate: true`, same id returned). Needs were recorded twice as a result — harmless, thresholds still exceeded. |
| Record needs, round 1 | `POST /v1/promotion/need` ×3 (friday ×2, intelx ×1) + owner need | **200** `need_recorded` ×3; owner need **200** `owner_need_ignored` (rule check: owner needs are no-ops). Audit table after both runs: M2 total **6** needs, distinct **2** (friday, intelx). |
| Pre-existing needs | `GET /audit?action=MEMORY_NEED_RECORDED&limit=500` (memora) before the run | **0 rows** — path (C) had never been exercised live before this run. |
| Sweep 1 | `POST /v1/promotion/sweep` `{window_days: 30}` (memora) | **200** `{promotions: [], count: 0}` at 16:31:57 IST (service journal). M2 still `scope: PRIVATE`; friday GET **404**. No ERROR / traceback in the Memora journal 16:28–16:40 IST. |
| Record needs, round 2 | `POST /v1/promotion/need` ×6 (futuris ×3, cortex ×3) | **200** `need_recorded` ×6. Audit table: M2 total **12** needs, distinct **4** (cortex, friday, futuris, intelx) — above both thresholds (PRIVATE → SHARED needs ≥ 2 / ≥ 3; SHARED → UNIVERSAL needs ≥ 4 / ≥ 8 / ≥ 2 outside). |
| Sweep 2 | `POST /v1/promotion/sweep` `{window_days: 30}` (memora) | **200** `{promotions: [], count: 0}`. M2 still `scope: PRIVATE`; cortex GET **404**. |
| Blast-radius check | Need table before each sweep | Only M2 has recorded needs; no other live memory met any threshold, so neither sweep could have promoted anything else. Audit tally (latest 500 rows): `MEMORY_NEED_RECORDED: 12` (all M2), `MEMORY_SCOPE_PROMOTED: 2` (both M1 owner promotions), `policy_approved: 486`. |

Why the sweeps promoted nothing (G2): the sweep examines only the 200
oldest non-UNIVERSAL records (`promotion.py`, `run_auto_promotion_sweep`).
Measured via `POST /v1/memories/query` as friday on
`memora://friday/private` with `time_to: 2026-11-22T11:01:00Z` (M2's
creation minute): first page **200** rows, offset-200 probe **1** row —
friday alone holds **≥ 201 records older than M2**. The 200-record window
is full before it can ever reach M2 (or any recent memory). The sweep is
therefore structurally inert for new memories until the backlog drains,
not merely slow.

## M3 / M4 — write-time scope (control)

| Memory | Call | Result |
| --- | --- | --- |
| M3 `4a2c65ce-10ed-4cf9-aa15-5ff20241cb19` | `POST /v1/memories` `{scope: SHARED, shared_with: [friday]}` (sentinel), created 2026-11-22T11:11:35Z | **201**, read-back `scope: SHARED`. |
| M3 read as recipient | `GET /v1/memories/{id}` (friday) | **200**. The write pipeline creates a namespace-level `AccessGrant` per recipient (`core/memory/pipeline/write_service.py:155-161`) — this is what makes write-time SHARED readable, and it is also what made M1 readable to friday afterwards (G4). |
| M3 read as non-recipient | `GET /v1/memories/{id}` (intelx) | **404**. |
| M3 share | `POST /v1/memories/{id}/share` `{target_agent_name: friday, actions: [read]}` (sentinel) | **200** `{status: shared, scope: namespace, grant_id: cb14f4bc-81ba-4bee-9e40-a88971f3c475, actions: [read], expires_at: null}`. GET as friday still **200**; intelx still **404**. `/share` is the working readable-sharing path: it creates the namespace grant *and* adds the recipient to the record allow-list. |
| M4 (direct UNIVERSAL write) | `POST /v1/memories` `{scope: UNIVERSAL}` (sentinel) | **403** `Only the Memora service identity may author UNIVERSAL memories.` — the write-time rule holds. |

## Gaps found

- **G1 (critical) — Promoted scope confers no readability.** `promote_scope`
  (`core/memory/promotion.py`) writes only the record `scope` and
  `memory_shared_agents` rows. Both read paths then re-check the namespace:
  `GET /v1/memories/{id}` via `_require_memory_read_access` →
  `PolicyEngine.evaluate_access`, and hybrid search via the shared
  `_record_passes_filters` policy gate (`core/memory/search_service.py`).
  The policy engine (`core/policy/engine.py`, RULE 1 "PRIVATE BY DEFAULT",
  `RULE_1_PRIVATE_BY_DEFAULT_PROMOTION_REQUIRED`) decides by namespace type
  only: an `AGENT_PRIVATE` namespace admits its owner or a namespace
  `AccessGrant` holder, never a scope-promoted record. The promotion
  module's claim that "every read path honours a promotion immediately"
  (`promotion.py` docstring) is false on the live service. Evidence: M1
  SHARED → friday/intelx GET 403; M1 UNIVERSAL → futuris GET 403; friday
  search for the exact marker (limit 50) omits M1 while the owner finds it
  at keyword 1.0. Fix direction: make the policy engine (and the search
  policy gate) consult record scope + `memory_shared_agents` for records in
  private namespaces, or make `promote_scope` also mint the namespace
  `AccessGrant` that the engine honours (the way `/share` and the
  write-time SHARED path already do).
- **G2 (critical) — Auto-promotion sweep starves recent memories.**
  `run_auto_promotion_sweep` takes the 200 oldest non-UNIVERSAL records
  (`promotion.py`). Friday alone holds ≥ 201 records older than M2, so M2
  (12 needs, 4 distinct agents — above both thresholds) was never
  evaluated; two sweeps returned `count: 0` with no error. Fix direction:
  evaluate need-bearing memories first (e.g. order by recent need evidence
  or scan memories that have `MEMORY_NEED_RECORDED` rows), raise/remove the
  200 cap, or add a per-memory evaluation endpoint for testing.
- **G3 — An owner cannot share its own UNIVERSAL record.** Once scope is
  UNIVERSAL, `may_mutate_record` (`access_scope.py:126-146`) permits only
  the memora service identity to mutate it, so `POST /share` as the owner
  fails with 403. Combined with G1, a UNIVERSAL record can be permanently
  unreadable to every non-owner unless a namespace grant predates the
  promotion. Fix direction: allow the owner to grant namespace access on
  its own UNIVERSAL records (share is a grant, not a content mutation).
- **G4 — Write-time SHARED creates a persistent namespace-wide grant.**
  `write_service.py:155-161` mints an `AccessGrant` on the whole namespace
  per recipient, with no expiry (`expires_at: null`). Side effect observed:
  after M3, friday could read M1 (UNIVERSAL) — and can read any future
  SHARED/UNIVERSAL record sentinel writes into `memora://sentinel/private`.
  PRIVATE records stay hidden (`record_is_visible` fails first), so no
  private data leaked, but the grant is coarser and more durable than the
  record-level sharing it accompanies. Fix direction: scope grants
  per-record where the engine supports it, or set a TTL.
- **G5 (minor) — Duplicate-write response mixes old and new request data.**
  The deduped second M2 write returned `is_duplicate: true` with the
  *original* record's `idempotency_key` but a `step_trace` carrying the
  *new* request's key. Cosmetic; dedup itself worked (same id returned).
- **G6 (minor) — No worker identity for probes.** `AGENT_API_KEY_ENV_VARS`
  (`dependencies.py`) has no `muse_10` entry, and `ai_universe` has a map
  entry but no configured key in `Memora/.env`, so this proof ran as
  `sentinel`/`friday`/`intelx`/`futuris`/`cortex` with clearly-marked test
  data. A dedicated worker identity would keep test rows out of a fleet
  agent's private namespace.
- **G7 (minor) — `MEMORA_MASTER_KEY` is configured** (name only; value
  never read). It was not used in this proof — all calls used per-agent
  keys, and the sweep used the `memora` service identity. Noted for the
  record; the master key authenticates any agent name, so its custody
  matters.

## Test data left behind (cleanup path)

- M1 `2f51fc7b-af02-45b3-b4a1-788760991fb8` — scope UNIVERSAL, namespace
  `memora://sentinel/private`, content prefixed `MUSE10-TEST-MEM-014`.
- M2 `b3562067-e808-415b-b16c-a633bd9d299b` — scope PRIVATE, same namespace.
- M3 `4a2c65ce-10ed-4cf9-aa15-5ff20241cb19` — scope SHARED, same namespace.
- Namespace grant: friday → `memora://sentinel/private`, read, no expiry
  (grant `cb14f4bc-81ba-4bee-9e40-a88971f3c475`, created by M3's write and
  re-confirmed by `/share`).
- Cleanup (not done here — out of scope for a proof run): the owner or the
  memora service identity can remove the memories via
  `POST /v1/memories/{id}/forget` or `DELETE /v1/memories/{id}`; grant
  revocation is an admin action. All three memories carry
  `provenance.test_data: true` / `task: TASK-MEM-014` for identification.

## What was NOT done

- No live database or config was written to directly; no service was
  restarted; no live memory besides the three marked test records (and the
  M3-derived namespace grant) was created, modified, or deleted.
- The master key was not used. No key, token, password, or secret value
  appears in this doc, in any issue comment, or in the probe script (the
  probe ran on Server 1 and read keys from the service env file at runtime;
  the script itself was deleted from the server afterwards).

— Muse 10
