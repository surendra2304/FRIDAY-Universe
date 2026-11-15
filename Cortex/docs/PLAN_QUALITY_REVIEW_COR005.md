# TASK-COR-005 — Cortex plan-quality review

**Crew:** Muse (`muse_ai`), Wave 5 Cortex crew. **Date:** 2026-11-15.
**Scope:** grade a sample of real multi-step plans Cortex produces
(`POST /plan`, `POST /v1/plan`, `POST /decompose`, `POST /v1/decompose`
in `Cortex/apps/api/src/cortex_api/main.py`) against what actually
happened, find the failure patterns, and fix the planner.

## Evidence sources (no claim rests on a single source)

1. **Shipped code** — `main.py` `plan_task` / `decompose_task` at main
   (file last changed 2026-11-08, commit `89465340`; verified via the
   GitHub API that no newer commit touches it).
2. **Production journal** — Server 2, `Cortex.service` current run
   (started 2026-11-15 04:04 IST, 8,600 log lines, read via bridge
   `run_shell`).
3. **The governed executor's code** — `friday_router.py`
   `process_task_envelope` + `cortex_core.governed_operations`
   (`classify_action_impact`, `HIGH_IMPACT_ACTION_MAP`) +
   `cortex_core.task_manager.TaskState`: what a real Cortex task
   actually goes through.
4. **Repo tests** — `tests/unit/test_cognitive_reasoning.py`,
   `tests/e2e/test_e2e_tier1.py` (they lock the old behaviour in as
   "success"; see test-change disclosure in the PR).
5. **Sampler** — the shipped step/subtask literals executed verbatim
   against six goals (the endpoint functions are pure and
   deterministic; this sandbox blocks pip installs, so TestClient
   could not be run here — the sampler runs the literal constructions
   byte-for-byte, cross-checked against the unit tests' assertions).

## What production actually did (journal, current run)

| Endpoint | Calls | Outcome |
|---|---|---|
| `POST /plan`, `/v1/plan` | **0** | — |
| `POST /decompose`, `/v1/decompose` | **0** | — |
| `POST /execute`, `/friday/task` | **0** | — |
| `POST /v1/task/execute` | **179** | **179 × HTTP 403** |

Two facts follow. First, **the planner has never been used in
production** — no caller exists in the repo either (the only
references to `plan_task` outside `main.py` are tests and the stale
`mesh/registry.py`). Second, the real work path is the governed
executor, and today every one of its 179 calls was rejected at a gate
(403; the access log does not say which of auth/scope/approval — that
distinction lives on the callers' side and is another crew's thread).
The plan template mentions none of those gates.

What the executor actually does with a task (from its code):
idempotency check → property scope validation (404/400/403) → impact
classification → **approval gate for the 5 high-impact categories**
→ Sentinel gate on production → observe with a telemetry staleness
bound (default 60s) → recommend (≠ authorization) or execute with a
pre-execution rollback snapshot → **measure observed vs expected
outcomes** → finalize. Task states: RECEIVED → OBSERVING →
RECOMMENDING → WAITING_APPROVAL → EXECUTING → MEASURING → COMPLETED.

## Grading table — the shipped planner vs reality

Every sample below returned the **identical** plan: step 1
`analyze_context_and_constraints` (reasoning, 2s), step 2
`synthesize_execution_graph` (planning, 3s), step 3
`dispatch_mesh_actions` (execution, 5s), total "estimated" 10s,
capabilities `[reasoning, planning, execution]`. Only the goal string
inside step 1's description changed. `/decompose` likewise returned
the same 3 subtasks (analytics → policy_engine → execution) for every
goal and every `max_subtasks`.

| # | Goal (source) | Steps needed vs planned | Dead steps | Missing steps | Wrong order / other | Verdict |
|---|---|---|---|---|---|---|
| S1 | "Optimize visitor conversion on pricing page", telemetry context (Cortex's own unit-test goal) | Needed ≈6 governed phases; planned 3 generic | `synthesize_execution_graph` (no component does this), `dispatch_mesh_actions` (the mesh fabric is not running; execution is the `/v1/task/execute` envelope) | scope validation, impact classification, observe-with-staleness-bound, recommendation, approval gate, measurement, provenance | Plan presents one "execution" step; reality interleaves gates before any action | **FAIL — template** |
| S2 | "Deploy proactive cart recovery workflow" (Cortex's own unit-test goal) | Needed ≈7 (deploy = `page_deploy`, high-impact content_publishing) | Same 2 of 3 steps dead | approval gate (mandatory), rollback snapshot, measurement | No hint the executor hard-blocks this without approval (403) | **FAIL — template** |
| S3 | "Change subscription pricing … and issue refunds", context names `pricing_change` | Needed ≈7 for the first operation alone; the goal names **two** billing operations | Same 2 of 3 | approval gate, snapshot, measurement; the second operation (`refund_issue`) is not representable at all | Most dangerous sample: the plan implies a straight 10-second path through a hard approval gate | **FAIL — template, gate-blind** |
| S4 | "Compile a health summary for site_storefront" (the action production actually calls) | Needed 1 read-only snapshot call; planned a 3-step "execution graph + mesh dispatch" | All 3 steps misdescribe the work; the one real action (connector health check) is never named | — (over-planned instead) | Wrong mechanism entirely for a read-only task | **FAIL — over-planned, wrong steps** |
| S5 | "Recommend an intervention for falling mobile conversion", `proposed_operation: banner_injection` | Needed: observe (staleness) → recommend → WAITING_APPROVAL | `dispatch_mesh_actions` (nothing is dispatched by a recommendation) | staleness bound, approval state, "recommendation ≠ authorization" | Plan's step order (analyse → synthesise → dispatch) matches no executor path | **FAIL — template** |
| S6 | "Book a flight to Tokyo and summarise the Stratex demo ledger" (goal-blindness probe) | Cortex cannot serve this at all — the executor fails closed with 422 on unrouted actions | All 3 | An honest "not plannable" answer | Endpoint still returns `status: "planned"` — a fabricated promise of capability | **FAIL — fabricated plannability** |

**Aggregate: 0/6 plans matched reality. Step-set identity across
unrelated goals: 100%.** `/decompose` probes: `max_subtasks=10`
still returns 3 subtasks; `max_subtasks=1` returns 1 subtask
(analytics only — the chain is decapitated, policy and execution
silently dropped).

## Failure patterns

- **P1 — Goal-blind template.** The plan is a constant; the goal,
  context, constraints and priority are echoed, never used. Steps
  needed vs planned is therefore wrong for every goal class.
- **P2 — Dead steps by construction.** Steps 2–3 describe work no
  component performs (`synthesize_execution_graph`,
  `dispatch_mesh_actions` over a mesh that is not running). Nothing
  consumes a plan: no caller in the repo, zero production calls.
- **P3 — Every real gate is missing.** Scope validation, impact
  classification, the high-impact approval gate, the production
  Sentinel gate, the telemetry staleness bound, the rollback
  snapshot and outcome measurement — the phases that decide whether
  work happens at all — appear in no plan.
- **P4 — Invented precision.** Durations 2s/3s/5s (total 10s) are
  constants presented as `estimated_duration_sec` with no basis;
  `required_capabilities` is the same constant trio for all goals.
- **P5 — Decompose breaks its own contract.** Fixed 3 subtasks for
  any goal and any `max_subtasks` in [1, 20]; small caps silently
  truncate the chain mid-way.
- **P6 — Ungradeable output.** No planner provenance, no per-step
  expected outcome, no link to execution — a plan could never be
  graded after the fact. (This review had to reconstruct "what
  happened" from the executor's code and the journal.)

## The fix (this PR)

New module `cortex_api/cognitive_planner.py`; `plan_task` and
`decompose_task` now call it. The planner is deterministic (no LLM)
and mirrors the executor's real phases:

- Operation resolution mirrors the executor's own payload reads
  (`operation`/`action_type`/`proposed_operation`/`action`), then a
  telemetry-context mapping, then a documented goal-keyword layer —
  each plan states its `operation_source`.
- Impact classification reuses
  `cortex_core.governed_operations.classify_action_impact` when
  importable, with a fallback mirror that a unit test keeps in sync
  (verified 28/28 entries against the source map).
- Plans include the approval gate (ordered as the executor orders
  it: before execution; after the recommendation in the recommend
  flow), the Sentinel gate for production, the rollback snapshot,
  measurement vs expected outcomes, and a provenance step. Read-only
  goals get no execution/approval steps. A `read_only` constraint
  truncates mutation steps and says so.
- Unresolvable goals return `plannable: false` with a reason and an
  observe-and-clarify plan instead of a fabricated execution graph.
- Durations are labelled `estimate_basis: "phase_budget_unmeasured"`.
- Every step carries `executor_state` (TaskState) and
  `expected_outcome`, so future plans are gradeable (fixes P6).
- `/decompose` derives subtasks from the plan phases; caps are
  honoured by merging trailing phases into the final subtask and
  reporting it (`cap_applied`, `phases_total`) — never by silent
  truncation or filler.

### The same six samples after the fix

| # | Operation (source) | Steps | Verdict |
|---|---|---|---|
| S1 | `banner_injection` (telemetry→executor default, labelled) | validate → classify → observe → recommend → approval → provenance | Matches the governed recommend flow |
| S2 | `page_deploy` (goal keyword) | validate → classify → approval → snapshot → execute → measure → provenance | Approval gate present, executor order |
| S3 | `pricing_change` (context) | validate → classify → approval → snapshot → execute → measure → provenance | Billing category named; gate present |
| S4 | `health_summary` (context) | validate → classify → observe → report → provenance | Read-only: no approval/execution |
| S5 | `banner_injection` (context) | validate → classify → observe → recommend → approval → provenance | Approval after recommendation, as the executor does |
| S6 | none | validate → observe → identify-operation, `plannable: false` + reason | Honest refusal instead of a fake plan |

## Limits of this fix (stated plainly)

- The planner mirrors the executor for a **single operation per
  goal**; multi-operation goals (S3's pricing change *and* refunds)
  still plan only the resolved primary operation. Splitting compound
  goals is future work.
- Keyword/telemetry resolution is a heuristic layer over the goal
  text; explicit context operations always outrank it, and every
  plan discloses which layer fired.
- Phase budgets are unmeasured by design and labelled as such; a
  timing baseline can only come from instrumented executions.
- The 179 × 403 on `/v1/task/execute` is reported here as context,
  not fixed: it belongs to the caller/auth thread, not the planner.
