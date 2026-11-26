# TASK-API-001 — Evidence: Forge `/v1/task/execute` verified on main

- **Task:** TASK-API-001 — Forge `/v1/task/execute` endpoint (WATCH122 assignment,
  hub #1483 comment 7176443876; claim hub #1483 comment 7176665283).
- **Worker:** Muse 15. **Branch:** `muse15/task-api-001-forge-task-execute`
  (base main `bf5a08b7`). **Work PR:** (filed with this doc; see hub post).
- **Date:** 2026-11-26 ~04:10–04:35 IST.

## 1. Headline finding: the route already exists on main

WATCH122 assigned API-001 on the premise "Forge still exposes no route"
(MASTER_PLAN §3 code check, 2026-11-14, main `573da9c`). That check is
**stale**. First-hand verification on current main `bf5a08b7`:

- `Forge/app/api/delegate.py:915` — `task_contract_router = APIRouter(prefix="/v1")`
  with `POST /task/execute` (adapter over `delegate_task`), shipped by
  **TASK-FRG-002**, commit `b8dc480d` ("TASK-FRG-002: ship POST /v1/task/execute
  fleet contract on Forge"), PR #1401, merged `fd4fb046`. Verified
  `b8dc480d` is an ancestor of `origin/main` (`git merge-base --is-ancestor`).
- `Forge/app/main.py:444` — `app.include_router(task_contract_router)` inside
  `create_app()`; the route is mounted in the assembled app, not just defined.
- TASK-FRG-002 board record: status MERGED, owner muse_10; its acceptance
  (3 consecutive live runs via FRIDAY chat) stands at **0/3, owed after
  deploy**.

So API-001's repo leg was already built by FRG-002. What API-001 adds in
this PR is the verification FRG-002 never did: the route proved reachable
**through the assembled app** (not a bare-router test rig), plus a
bus-contract conformance check. Nothing was rebuilt; the stale premise is
reported plainly rather than papered over.

## 2. Board ID collision — ruling owed from Muse

A TASK-API-001 record **already exists** on the board (main `bf5a08b7`,
lines 654–672): old "Sentinel fail-closed status task API", status
DEPLOYED, owner `claude`, PR #29 (2026-11-10 mass merge). No AVAILABLE
record for this Forge task exists. The coordinator's "no board record
existed" (WATCH122) is wrong for the ID, right for the task: the ID is
taken, the Forge task has no record.

**This PR changes no board record.** Muse to rule: fresh ID for the Forge
task (next free API id) or reuse/supersede the old DEPLOYED record. The
flip rides in a follow-up once ruled. Flagged in the claim post
(7176665283).

## 3. Verification performed (all first-hand, this run)

### 3.1 Code reads

- `Forge/app/api/delegate.py` (`TaskEnvelopeModel`, `TaskResultModel`,
  `delegate_task`, `_forge_receipt`): `ping`/`status`/`health` return
  SUCCESS + receipt; `cancel` routes through the canonical lifecycle;
  `test`/`verify` return the verification manifest + derived verdict;
  `build`/`fix`/`refactor`/`review` go through
  `orchestrator.intake_and_plan` (+ `run_task` when `execute_now`, else
  supervised background execution via `_schedule_execution` with honest
  RUNNING status — TASK-REL-011); `plan_only` returns PLANNED with no
  receipt, by design.
- `FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py`
  (`_request_payload`, `_receipt_for_response`): the bus posts
  `{task_id, agent, action, payload, priority (string), timeout_sec,
  source_agent: "FRIDAY"}` to `/v1/task/execute`; a 200 with status
  SUCCESS (or any status outside accepted/queued/pending/running) is a
  **completed** receipt, while RUNNING is an **accepted** receipt.
  Forge's responses match both shapes.
- `Forge/app/main.py` (`require_production_api_key`): auth is enforced
  only when `API_KEY_REQUIRED` is set; the bus sends
  `X-API-Key: <FRIDAY_DISPATCH_FORGE_API_KEY>` when configured, so the
  fleet path carries a key and the local test path (unset) is open.

### 3.2 Live local runs (this VM, isolated venv)

Venv `/tmp/forge-venv` (ephemeral), `pip install -e ".[dev]"` from
`Forge/pyproject.toml`, `PYTHONPATH=<repo root>` per the CI job
(`friday-universe-ci.yml`, Forge tier-1):

```
$ python -m pytest tests/unit/test_task_execute_mounted_app.py \
    tests/unit/test_task_execute_contract.py -q
....  [100%]  4 passed
```

New tests (`Forge/tests/unit/test_task_execute_mounted_app.py`):

1. `test_mounted_app_serves_task_execute_on_bus_wire_shape` — boots the
   **real** `create_app()`, asserts `/v1/task/execute` POST is in the
   assembled OpenAPI, posts the bus's exact wire shape (`ping`), asserts
   200 / SUCCESS / `engine_status ONLINE` / receipt naming action `ping`
   and target `forge`.
2. `test_mounted_app_build_plan_only_through_delegate` — posts a `build`
   with `mode: plan_only` through the mounted route, asserts 200 /
   PLANNED / `plan_stages == 2` / no receipt. Proves the build path is
   wired route → `delegate_task` → `intake_and_plan` while executing no
   code.

Pre-existing contract tests (FRG-002) still pass: 2/2. `ruff check` +
`ruff format --check` clean on the new file.

### 3.3 Pre-existing break found (out of scope, reported)

The Forge suite's SQLite-backed fixtures are broken on current main:
`tests/conftest.py:46` constructs `DatabaseManager(db_path=...)`, but
`DatabaseManager` is now Oracle-only (`__init__(self, database_url=None)`,
`app/memory/db.py:422`); the fixture errors with
`TypeError: DatabaseManager.__init__() got an unexpected keyword argument
'db_path'`. CI already deselects the tests that hit it
(`friday-universe-ci.yml`, TASK-REL-088 comment). Consequence for this
task: a test through the **real** `OrchestratorCore` cannot run here
(it needs a live Oracle DB); the plan_only test therefore stubs the
orchestrator at the same seam FRG-002 used, and says so in the test.
Fixing the test DB layer is a separate task, not API-001.

## 4. Bus-contract conformance (verified)

| Bus action | Forge response (verified) | Bus receipt |
|---|---|---|
| `ping` / `status` / `health` | 200, SUCCESS, receipt (action + target + evidence) | completed |
| `build` + `mode: plan_only` | 200, PLANNED, plan, no receipt | completed (status PLANNED is not in the accepted set; callers must not read it as done work) |
| `build` (default, no `execute_now`) | RUNNING, background execution scheduled (code-read; not executed live here) | accepted |
| `build` + `execute_now` | SUCCESS only when state COMPLETED **and** final battery passed, else FAILED/PARTIAL_FAILURE/DEGRADED (code-read) | completed / not completed per status |

## 5. What is still owed (live leg — gated)

- **Deployed Forge currency unverified.** The live Forge on Server 1
  (port 8006) may predate `b8dc480d`; fleet CD is broken and this
  environment has no bridge access, so no deployed-route check was
  possible here. A read-only `GET /openapi.json` (or `/health`) against
  the deployed Forge is owed once access/clearance exists.
- **Live proof via FRIDAY chat: 0/3.** FRG-002's acceptance (three
  consecutive real code tasks requested through FRIDAY chat, each with a
  trace) is still owed after merge + deploy. Needs hub clearance (owner
  stop order in force) and a deploy of current main to Server 1.
- **Board record:** blocked on Muse's ID-collision ruling (§2).

## 6. Five states

- implemented: **YES** — route on main since FRG-002 (PR #1401, merge
  `fd4fb046`); this PR adds the mounted-app proof, not a rebuild.
- tested: **PARTIAL** — 4/4 local tests pass (2 new mounted-app tests +
  2 FRG-002 contract tests); live proof gated (§5).
- merged: **NO** — work PR open.
- deployed: **UNKNOWN** — deployed build currency unverified; CD broken.
- production-verified: **NO** — live FRIDAY-chat runs 0/3, gated on
  clearance + deploy.

## 7. Files in this PR

- `Forge/tests/unit/test_task_execute_mounted_app.py` (new, 2 tests)
- `docs/collaboration/TASK-API-001-EVIDENCE.md` (new, this file)

No board change in this PR (ID ruling owed, §2). No secrets. Free only.

— Muse 15
