# TASK-FRG-002 — Forge: prove 3 consecutive live code-task runs requested through FRIDAY chat

Owner: Muse 10. Assigned: coordinator watch 7081706110 (~21:27 IST, 2026-11-22), answering work request 7081539638. Branch: `muse10/task-frg-002-forge-live-runs`. Status: IN_REVIEW (route shipped, 0/3 live runs — runs need merge + deploy first).

## Claim

- Claim comment: issue #35 comment 7081948198 (~21:36 IST).
- Board record: created in this work PR from main blob `5261b89a` (coordinator watch 7081812835: do NOT wait for tomorrow's consolidated board PR). Status CLAIMED, owner `muse_10`.
- Work-request cycle stands down while claimed.

## Route verification (done 2026-11-22 ~21:57 IST, STATUS comment 7082084124)

- Forge on main served NO `POST /v1/task/execute`. Only `POST /api/v1/forge/delegate` (+ status/cancel) in `Forge/app/api/delegate.py`; `task_contract_router` did not exist in tracked code (the Nov-8 contract test importing it was untracked/stale).
- Live proof (Server 2 curl to Forge :8006 on Server 1): `/openapi.json` lists no `/v1/task/execute`; POST to it returns 401 `{"error":"unauthorized"}`; a control POST to a nonexistent path returns the same 401 — global auth middleware, not a route. `/health` returns 200. Forge service live on Server 1 since 21:09 IST, uvicorn port 8006, Oracle ADB backend.
- Sentinel's own `/v1/task/execute` (`Sentinel/sentinel/apps/api/main.py:599`) is fail-closed read-only (`status` action only) — not the Forge execution path.
- FRIDAY dispatch bus (`FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py`): posts code tasks to `http://10.0.0.121:8006/v1/task/execute` with payload `{task_id, agent, action, payload, priority (string), timeout_sec, source_agent: "FRIDAY"}` and header `x-api-key: FRIDAY_DISPATCH_FORGE_API_KEY`; a 404 breaks retries with "Action 'build' not found on Forge". Receipt: 202 or body status accepted/queued/pending/running → "accepted"; 200/201/204 otherwise → "completed".
- FRIDAY chat routing: `CapabilityRouter` routes code-task requests to the `forge_code_task` tool; `ForgeCodeTool` (`FRIDAY/src/friday/tools/builtin/forge_code_task.py:149-156`) builds envelope `action="build"`, `payload={goal, requirements, execute_now: true}`. Test doc: `FRIDAY/tests/test_forge_code_dispatch.py` (TASK-FOR-002).

## Implementation (this PR)

- `Forge/app/api/delegate.py`: new `task_contract_router` (`APIRouter(prefix="/v1")`) with `POST /v1/task/execute` — a thin adapter over the existing `/delegate` execution path. The fleet payload maps 1:1 onto `TaskEnvelopeModel` (the bus's extra `agent` / `timeout_sec` fields are ignored by pydantic; `priority` stays a string); `delegate_task` does the work, so ping/status/cancel/test/build all behave exactly as on `/delegate`, including the receipt naming the dispatched action, target forge, and non-empty verification evidence. Auth is the app's global API-key middleware (same as `/delegate`); nothing is exempted here.
- `Forge/app/main.py`: imports `task_contract_router` and mounts it at root (the router carries its own `/v1` prefix).
- `Forge/tests/unit/test_task_execute_contract.py`: the orphaned Nov-8 TASK-API-001 test, now tracked, plus a TASK-FRG-002 test posting the bus's exact wire shape (`agent`, string `priority "100"`, `timeout_sec`, `source_agent "FRIDAY"`). Both assert 200, echoed `task_id`, `target_agent forge`, `status SUCCESS`, `result.engine_status ONLINE` for the `ping` action.

## Test evidence

- Contract test: `2 passed in 9.48s` on Server 2 (venv312 python 3.12.16, pytest 9.2.0), run 2026-11-22 ~23:30 IST.
- Env note (pre-existing gap, not introduced here): neither Server 2 venv (`venv`, `venv312`) has Forge's declared dependencies installed — the first runs failed on `anthropic`, then `openai`, then `bs4`. The test was run with a scratch overlay: `pip install --target /tmp/frg002-libs` of the `Forge/requirements.txt` set (anthropic, openai, beautifulsoup4, oracledb, redis, python-dotenv, rich, psutil, greenlet) + pytest/pytest-asyncio, `PYTHONPATH=/tmp/frg002-libs:Forge`, `--noconftest`. CI installs `requirements-ci.txt`, so the suite should be green there; the Server 2 venvs need the same treatment before the Forge suite can run locally without the overlay.
- No other test files were run in this PR; the change is additive (one router + one mount) and the two contract tests cover the new route.

## CI repair (contracts job)

- First CI run on PR #1401 failed the `contracts` check in 9s: the TASK-REL-068 test-collection guard. Reproduced locally (`python3 scripts/ci_test_collection_audit.py --base <merge-base>`): the new contract test was collected by NO PR-triggered workflow. (The local run also flagged a stale reference in the untracked, Server-2-only `.github/workflows/friday-voice-ci.yml`; see the note below — it is not a CI failure.)
- Fix in this PR: added `Forge/tests/unit/test_task_execute_contract.py` to the contracts job's Forge unit-test list in `.github/workflows/owner-workflows.yml`. Guard re-run locally: PASS.
- Note: the local guard run also flagged a stale reference in `.github/workflows/friday-voice-ci.yml` (`tests/test_orpheus_terms_fallback.py`, a file that exists nowhere in the tree). That file is NOT tracked in git — it is excluded via `.git/info/exclude` on Server 2, so CI never sees it and it did not cause the CI failure. It was left untouched (two exploratory edits to it were reverted).

## Live runs: 0/3 — still owed

- The 3 consecutive live code-task runs requested through FRIDAY chat cannot run until this PR is merged and the route is deployed live (the live Forge on Server 1 still serves the pre-PR code). After merge + deploy: request 3 real code tasks through FRIDAY chat, each recorded with its trace (request, routing, agent evidence, result); a silent failure resets the count.
- Still to pin down: the FRIDAY chat entrypoint for the live runs (`FRIDAY/src/friday/api/server.py` mentions `api/chat`; other workers used the FRIDAY web chat for their live runs).

## Stall repair

- The 23:06 IST hourly self-check found this task stalled: claimed ~21:36 IST, last checkpoint ~21:57 IST, zero commits on the branch and no work PR ~90 minutes later. This PR is the repair: route implemented, contract tests green, work PR opened. The self-check did not wait for a new assignment — it continued the claimed work.

— Muse 10
