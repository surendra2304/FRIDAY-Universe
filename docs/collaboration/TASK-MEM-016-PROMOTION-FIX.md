# TASK-MEM-016: Promotion readability (G1) + auto-promotion sweep window (G2)

**Worker:** Muse 9 · **Date:** 2026-11-22 · **Branch:** `muse9/task-mem-016`
**Board:** TASK-MEM-016 (Memora: fix promotion readability (G1) + auto-promotion
sweep window (G2), re-run the MEM-014 live probe as proof)
**Claim:** issue #35 comment 7080757041, on coordinator assignment in watch
7080540102 (~19:55 IST). Base: main dd8a0c9 (rebased 2026-11-22 ~20:40 IST
after PR #1385 (MEM-015) merged; originally 1cb07418).

## Verdict (read this first)

Both MEM-014 gaps are fixed in code and pinned by regression tests.

- **G1 — promoted scope now confers readability.** The policy engine
  (`Memora/core/policy/engine.py`, AGENT_PRIVATE branch) consults record
  scope for `read`/`query` via the single visibility authority
  (`storage.relational.access_scope.record_is_visible`) before denying.
  A SHARED record is readable by its allow-list, a UNIVERSAL record by any
  agent in the tenant, a PRIVATE record still only by its owner. The
  direct-GET path and the search policy gate both flow through the engine,
  so both are fixed by the one change — verified at engine, search-gate
  and HTTP API level in the new tests.
- **G2 — the sweep evaluates need-bearing memories first.** The sweep is
  now two-phase within the same `limit` budget: memories with
  `MEMORY_NEED_RECORDED` rows inside the window first (most-recent-need
  first), then the oldest-first scan filling the remaining budget. A
  need-bearing recent memory behind 201 older records is now promoted;
  the limit is still a hard budget and below-threshold needs still
  promote nothing.

## What changed

| File | Change |
| --- | --- |
| `Memora/core/policy/engine.py` | AGENT_PRIVATE branch: after the owner and explicit-grant checks, for `read`/`query` with a `memory_id`, allow when `record_is_visible(record, actor)` — new rule `RULE_1_PROMOTED_SCOPE_READ`. Mutations (`write`/`share`/`delete`/`promote`/`update`) are untouched: promotion confers read only. Bounded-scope and temporal-validity checks above it are untouched. |
| `Memora/core/memory/promotion.py` | `run_auto_promotion_sweep`: two-phase candidate selection (need-bearing first, most-recent-need first; oldest-first fills the rest of the `limit`). Window filtering of need rows in Python, mirroring `need_evidence`, so no DB timezone arithmetic. Module docstring corrected: the "every read path honours a promotion immediately" claim now notes the engine consults record scope since MEM-016 (MEM-014 proved it false before). |
| `Memora/tests/test_mem016_promotion_readability_sweep.py` | 11 new regression tests (see below). |
| `.github/workflows/friday-universe-ci.yml` | New test file added to the collected list alongside `test_mem013_memory_promotion.py`. |
| `docs/collaboration/WORK_BOARD.yaml` | TASK-MEM-016 record (CLAIMED → IN_REVIEW, owner muse_9). |

## G1 — design notes and what was deliberately NOT changed

- The fix lives in the engine, not in each caller, because every read path
  already funnels through `PolicyEngine.evaluate_access` with `memory_id`:
  direct GET (`_require_memory_read_access`, `apps/api/routers/v1_memories.py`),
  search (`_passes_retrieval_filters`, `core/memory/search_service.py`),
  graph traversal and context builder. One change, all paths agree.
- `record_is_visible` is the authority, not a re-derivation: SHARED admits
  owner + allow-list (+ `*` sentinel), UNIVERSAL admits everyone in the
  tenant, PRIVATE admits only the owner. A legacy row with `scope None`
  falls back to the namespace-derived tier inside that helper.
- Namespace-level reads (`memory_id` None, e.g. listing a private
  namespace) are unchanged — no record to consult, still denied. The
  promotion allowance cannot be used to enumerate a namespace.
- Dimension 4 (shared/project namespaces) is unchanged: promoted records
  live in the owner's private namespace (MEM-014 M1/M2), and shared
  namespaces already gate by membership/grants.
- G3 (owner cannot share its own UNIVERSAL record) and G4 (write-time
  SHARED mints a namespace-wide grant) are NOT touched: they are separate
  gaps with their own fix directions, and this task's acceptance is G1+G2
  plus the MEM-014 probe re-run. The G1 fix does not depend on them.
- The old deny rule `RULE_1_PRIVATE_BY_DEFAULT_PROMOTION_REQUIRED` still
  fires for every case that should stay denied (non-recipient SHARED read,
  PRIVATE read, all mutations) — pinned by tests.

## G2 — design notes

- Phase 1 candidates come from `AuditLog` rows with
  `action == MEMORY_NEED_RECORDED` in the tenant; the window cut is applied
  in Python (`_as_utc`, mirroring `need_evidence`), so the change is safe
  on Oracle (no `TIMESTAMP WITH TIME ZONE` arithmetic) and on SQLite.
- Phase 1 is capped at `limit`, so the sweep's total candidate budget never
  grows; phase 2 fills only the remainder and excludes phase-1 ids, so no
  record is evaluated twice in one run.
- A no-need sweep behaves exactly as before (oldest-first, same limit).
- The `DEFAULT_WINDOW_DAYS = 30` window is unchanged; needs older than the
  window still earn nothing.

## Tests (local, file-backed SQLite via Memora/tests/conftest.py)

New file `Memora/tests/test_mem016_promotion_readability_sweep.py` — 11 tests:

G1 (6): promoted SHARED readable by recipient via engine
(`RULE_1_PROMOTED_SCOPE_READ`); promoted UNIVERSAL readable by an outsider;
SHARED still denies a non-recipient; PRIVATE still denies a non-owner;
promotion confers read only (write/share/delete/promote/update denied);
search gate admits the promoted record to its recipient only.
API (1): `GET /v1/memories/{id}` 200 for the recipient after SHARED
promotion, 404 before promotion and 404 for a non-recipient — the MEM-014
M1 sequence verbatim.
G2 (4): sweep promotes a need-bearing recent memory behind 201 older
records; `limit=1` promotes only the most-recent-need candidate; below
threshold still promotes nothing; a no-need sweep stays oldest-first and
promotes nothing.

**Results:** local venv (`.venv-mem016`, `requirements-ci.txt` + ruff),
2026-11-22 ~20:40 IST — **11 passed** in 2.49 s:
`tests/test_mem016_promotion_readability_sweep.py` (11/11, incl. the API
GET test and the 201-older-records sweep test). `ruff check` clean on all
changed files (CI runs `ruff check`, not format).

Neighbouring suites run (same venv, same run): **30 passed, 2 failed** —
`test_mem013_memory_promotion.py`, `test_policy_engine.py`,
`test_policy.py`, `test_memory_access_controller_auth.py`,
`test_memory_write_share_authorization.py` all green. The 2 failures are
both in `test_scope_access_and_fallback_removal.py`
(`test_sqlite_fallback_removed`, `test_bootstrap_uses_unqualified_names`,
`FileNotFoundError: 'D:\\FRIDAY Universe\\Memora\\migrations\\...'` — a
Windows path baked into the test) and are **pre-existing: identical 2
failures on pristine main via `git stash` A/B** (same run, same venv),
untouched by this change.

Rebase check, 2026-11-22 ~20:40 IST: PR #1385 (MEM-015, `revert_scope`)
merged while this PR was open, touching `promotion.py` + the board. The
branch was rebased onto main dd8a0c9 with a real 3-way merge (no conflicts;
both docstring edits preserved). Re-run on the rebased tree: **33 passed**
(MEM-016 11 + MEM-013 + MEM-015 revert suites), `ruff check` clean.

CI guard fix, 2026-11-22 ~20:50 IST: the first push missed the trailing
backslash on the `test_mem013` line, so the new file was a stray shell line
and the test-collection guard failed the PR (`UNCOLLECTED:
test_mem016_promotion_readability_sweep.py`). Fixed the continuation;
guard passes locally (exit 0, 272 files covered by a PR-triggered
workflow).

## Live probe (MEM-014 re-run) — status

_NOT RUN YET._ The MEM-014 live probe re-run is the task's acceptance proof
and needs the fixed code deployed to the live Memora service on Server 1:
the running service still carries the pre-fix engine/sweep, so probing it
now would only re-prove the old behaviour. Deployment needs Muse's
clearance (live-fleet change through a reviewed PR). After merge + deploy
clearance, the re-run repeats the MEM-014 M1/M2 sequences against the live
service (test data only, `MUSE9-TEST-MEM-016` prefix): M1 — owner promotes
PRIVATE → SHARED → UNIVERSAL and a recipient/outside read returns 200;
M2 — a recent memory with above-threshold needs is promoted by a sweep.
This doc will be updated with the live results then; nothing here claims
live proof before that run.

## What was NOT done

- No live database or config was written to directly; no service was
  restarted; no live memory was created, modified or deleted in this run.
- No secret, key, token or password appears in this doc, in any issue
  comment, or in the test data. The live probe (when run) will read keys
  from the service env file at runtime on the server, as MEM-014 did.
- G3/G4/G5/G6/G7 from MEM-014 are untouched (see design notes above).

— Muse 9
