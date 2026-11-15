# TASK-COR-008 — Governed execution honesty: `GovernedOperationsEngine.execute()` labelled in-memory bookkeeping as REAL_EXECUTION

**Verdict:** fixed by reclassification. The governed engine has no effector that reaches a real
property, so its execution records now say what actually happens — `SIMULATED` /
`SIMULATED_EXECUTION`, zero external side effects, with the local snapshot bookkeeping reported
explicitly. Branch `claude/task-cor-008-governed-execution-honesty`. Coordinator merges.

## 1. What execute() did before (verified on main `b34e2d34`; file blob `eb9a73ec…`)

`Cortex/packages/core/src/cortex_core/governed_operations.py`, `execute(approval_id, idempotency_key, tool_bus, dry_run=False)`:

- The `tool_bus` parameter was **never referenced** in the body. (Independent confirmation of
  TASK-COR-006's probe: an exploding bus recorded 0 calls.)
- The only state change was an in-memory dict update on the registered property —
  `prop.state_snapshot[...]` — and only for 3 action types (`banner_injection`, `config_update`,
  `deployment_traffic_switch`). For every other action (e.g. `cache_flush`, `email_dispatch`) it
  changed **nothing at all**.
- It then returned, for all of them: `status="EXECUTED"`, `classification="REAL_EXECUTION"`,
  `result["status"]="executed"`, `result["side_effects_applied"]=1`.
- The `dry_run=True` path was already honest (`SIMULATED` / `SIMULATED_EXECUTION`).

## 2. Who consumes the record

- `Cortex/apps/api/src/cortex_api/friday_router.py::process_task_envelope` (the production
  caller, via `POST /v1/friday/task`, `action=execute_operation`): passes
  `tool_bus=_get_orchestrator().tool_bus`, then copies `exec_rec.classification` into the
  response's top-level `classification` and its summary string, `exec_rec.status` /
  `exec_rec.result` into `result.execution`, appends `exec_rec.__dict__` to the task audit list,
  and calls `measure()` unconditionally.
- `Cortex/apps/api/src/cortex_api/main.py` routes envelopes into `process_task_envelope`.
- The engine's own `self.executions` store; `cortex_core/__init__.py` re-exports the engine.
- Tests: `Cortex/tests/test_prompt9_cortex.py` Acceptance Test 3 asserted the fiction
  (`classification == "REAL_EXECUTION"` for a `cache_flush` that changed nothing anywhere).

No consumer branches on `status == "EXECUTED"` or on `side_effects_applied` (grep-verified
across `Cortex/packages` and `Cortex/apps`).

## 3. Why reclassification, not wiring the bus

Wiring was considered first and rejected on evidence:

1. **There is nothing real to wire to.** `ToolBus.execute` dispatches by tool name to
   registered executors. The orchestrator's bus (`build_default_tool_bus`) registers exactly
   one governed-action name — `banner_injection` — whose executor is
   `lambda p, ctx: {"injected": True, "variant": p.get("variant")}`: a stub returning a canned
   dict. It injects no banner anywhere. Every other governed action (`config_update`,
   `deployment_traffic_switch`, `cache_flush`, …) is not registered at all and would raise
   `ValueError`. Calling the bus would replace one fiction with another.
2. **It is not a small change.** `ToolBus.execute` is `async`; the engine is sync and is called
   from both sync and async contexts. Real wiring means an async engine refactor plus building
   actual effectors (code that mutates a real website) — none exist anywhere in the repo; the
   registry's `state_snapshot` **is** the system's whole model of a property.
3. **Reclassification makes every field true today** and leaves the honest seam: when real
   effectors are built and registered, `execute()` is where dispatch belongs — and only then
   may a record say `REAL_EXECUTION`. The new docstring states this rule in the code.

## 4. The change

`governed_operations.py` — `execute()` only:

- Non-dry-run records: `status` `EXECUTED` → `SIMULATED`; `classification` `REAL_EXECUTION` →
  `SIMULATED_EXECUTION`; `result["status"]` `"executed"` → `"simulated"`;
  `result["side_effects_applied"]` `1` → `0`.
- New truthful result fields (both paths): `external_side_effects_applied: 0`,
  `state_snapshot_updated: bool` (true only when a snapshot branch actually ran),
  `tool_bus_invoked: False`, `execution_environment: "in_memory_property_snapshot"`, and a
  `message` stating no external system was modified.
- The snapshot bookkeeping itself is unchanged (rollback via `snapshot_before` keeps working;
  prompt9 Test 16's rollback flow still passes by construction).
- Docstring rewritten to state the honesty rule; log line now says "Simulated execution".

`Cortex/tests/test_prompt9_cortex.py` — Acceptance Test 3's single classification assertion
updated (`REAL_EXECUTION` → `SIMULATED_EXECUTION`) with a comment explaining why; the test had
encoded the mislabel as the expected behaviour.

`Cortex/tests/unit/test_governed_execution_honesty_cor008.py` — new regression suite (8 tests).

## 5. Test evidence

Local run (sandbox pytest startup is currently broken by the fleet-wide tempfile/write outage,
so the suite was executed with a direct runner importing the same test module; CI runs it under
pytest):

- **Against the fixed engine: 8/8 pass.** Exploding bus, recording bus (asserts zero calls),
  `tool_bus=None`, snapshot bookkeeping for `banner_injection`/`config_update`, no-branch
  `cache_flush` reporting `state_snapshot_updated=False`, dry-run unchanged, and a 5-action sweep.
- **Against pristine main's engine (byte-identical copy, blob-verified): 0/8 pass** — every test
  fails on the old labels, so the suite pins the defect, not the implementation.
- The neighbouring `test_approval_decisions.py` suite does not call `execute()` (it covers
  authorize/reject) and is untouched; it was not re-run locally for the reason above — CI covers it.

## 6. Explicitly out of scope (follow-ups, not fixed here)

- `measure()` still defaults unobserved outcomes to the expected ones, so the envelope summary
  can claim "Achieved lift: 5.0%" for a simulation. TASK-COR-006's pending PR already addresses
  the governed-envelope measurement path in `friday_router.py`; the engine-side default is the
  remaining piece and wants its own task so the two changes don't collide.
- The router summary wording ("Cortex executed …") still uses the verb "executed" while now
  printing the honest `(SIMULATED_EXECUTION)` classification beside it.
- Building real effectors for governed actions (a real banner/config/traffic actuator behind
  the ToolBus) is a feature project, not an honesty fix.

## Five states

implemented ✔ · tested ✔ (locally, direct runner; 8/8 post-fix, 0/8 pre-fix) · merged ✗
(coordinator) · deployed ✗ · production-verified ✗ (no production contact by design)
