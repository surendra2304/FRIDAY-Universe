# Memora Retention & Forgetting Policy

**Task:** TASK-MEM-006 · **Code:** `core/memory/retention.py`,
`core/memory/service.py`, `apps/api/routers/v1_memories.py` ·
**Tests:** `tests/test_retention_forgetting_policy.py`

## Why this policy exists

Before TASK-MEM-006, `MemoryRecord.expires_at` was caller-supplied only.
Nothing classified a write as transient or durable, nothing assigned an
expiry by policy, and a record whose expiry had passed was merely *hidden*
from query/search while its row, embedding, and graph edges were kept
forever. Expiry was cosmetic. Forgetting depended on the caller knowing to
pass `hard=true` to the delete API; the default delete is a soft lifecycle
transition that retains the content.

This policy makes both real:

- **Transient context expires — and is erased.**
- **Durable facts persist — until the owner asks to forget them.**
- **Forgetting is erasure, verified store by store — never a flag.**

## Retention classes

Every memory type maps to a retention class with a default TTL. The class
is assigned at write time; the resulting `expires_at` is stored on the
record (`core/memory/retention.py: DEFAULT_POLICY`).

| Class | Memory types | Default TTL | At expiry |
|---|---|---|---|
| TRANSIENT | `working` | 30 days | Hard-erased by the expiry sweep |
| TRANSIENT | `tool` | 7 days | Hard-erased by the expiry sweep |
| SHORT_TERM | `episodic` | 90 days | Hard-erased by the expiry sweep |
| SHORT_TERM | `experience` | 90 days | Hard-erased by the expiry sweep |
| DURABLE | `semantic`, `preference`, `procedural`, `decision`, `relationship`, `project`, `system` | none | Never expires; erased only by an explicit forget |

The TTLs are never shorter than the zero-work-lost HorizonSweeper
condensation horizons (working 30 days, episodic 90 days), and the horizon
sweeper selects by record age while the expiry sweep selects by
`expires_at` — so condensation promotes a durable milestone summary
(SEMANTIC, hence DURABLE) before the raw record's retention lapses.

### Overrides, in precedence order

1. **Explicit `expires_at` on the write** — always wins, in both
   directions (shorter or longer than the policy default).
2. **Provenance `retention_ttl_hours`** — a positive number, clamped to
   [1 hour, 1 year]. An explicit TTL makes even a durable-class record
   expire: the caller asked for expiry and that request is honoured.
3. **Provenance `retention_class`** — `transient` / `short_term` /
   `durable`. An unrecognised value is ignored (logged), never silently
   applied. `durable` with no TTL anywhere means no expiry.
4. **Environment override** — `MEMORA_RETENTION_TTL_HOURS_<TYPE>`
   (e.g. `MEMORA_RETENTION_TTL_HOURS_WORKING=24`) replaces the per-type
   default TTL for operators.
5. **Per-type default** from the table above.

## Expiry sweep

`RetentionSweeper.run_expiry_sweep(db, tenant_id=None, now=None)`
(`core/memory/retention.py`):

- Selects records with `expires_at <= now` (optionally one tenant),
  oldest expiry first, bounded by a batch limit (default 1000).
- Erases each through the same multi-store convergence path as an
  explicit hard delete (`MemoryService._hard_erase_record`): vector
  embedding, graph relationships, cache entry, relational row — with a
  `DeletionTombstone` recording each store's outcome.
- Commits per record: one failing record cannot roll back the rest. A
  record whose erasure does not converge keeps a `PENDING_RETRY`
  tombstone for the existing self-healing worker.
- Never touches records with `expires_at IS NULL` — durable facts are
  out of the sweep's reach by construction.
- Operable via `POST /v1/memories/sweep-retention` (admin, tenant-bound,
  same posture as `/sweep-horizon`).

## Forgetting

`MemoryService.forget_memory(db, memory_id, actor_name)` and
`POST /v1/memories/{memory_id}/forget`:

- Runs under exactly the same ownership, visibility, and policy checks as
  delete — only the owning agent (or the owner acting through it) can
  forget a memory.
- Always takes the **hard** path: the record is removed from the
  relational store, its embedding from the vector store, its edges from
  the graph, and its entry from the cache.
- Then **verifies**: `MemoryService.verify_erasure` re-checks every store
  and the result carries the per-store report. If anything still holds
  the memory — or a store cannot be inspected — the status is
  `forget_incomplete`, never a false success.
- What remains after a forget is deliberate and content-free: the
  `DeletionTombstone` (ids and per-store booleans) and audit-log rows
  whose memory reference is set NULL by the schema. The audit trail
  proves an erasure happened; it cannot resurrect what was erased.
- Soft delete (`DELETE /v1/memories/{id}` without `hard=true`) is an
  internal lifecycle transition that retains content for audit. It is
  **not** forgetting and must not be presented to the owner as such.

## Proof

`tests/test_retention_forgetting_policy.py` runs entirely against a
staging store (in-memory SQLite via the suite's `test_db` fixture — the
same staging pattern as the rest of the Memora suite; no production data
is touched):

- **Plant → forget → verify-gone:** a record is planted with a vector
  entry, a graph edge, and a cache entry; after `forget_memory`, every
  store is inspected directly and the record is absent from all of them,
  with a CONVERGED tombstone.
- **Expiry:** a lapsed transient record is erased end-to-end by the
  sweep; a durable record and a not-yet-expired record survive; a second
  sweep is a no-op.
- **Classification:** the write path assigns policy expiries per class,
  honours overrides, and leaves durable writes without an expiry.
