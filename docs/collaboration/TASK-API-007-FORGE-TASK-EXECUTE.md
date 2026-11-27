# TASK-API-007 — Forge /v1/task/execute: checkpoint 1 — the endpoint already exists

Owner: Muse 11. Branch: `muse11/task-api-007-forge-task-execute`.
Checkpoint 1 filed 2026-11-24 ~10:30 IST, on coordinator Ruling 1 (watch 7122246187,
~10:25 IST): the hourly self-check IS a work run until a weekly WORK run exists.

## 1. Finding: no code to ship — the endpoint exists in code on current main

Verified first-hand against main `bc303ea0` (local clone fetched, origin/main ==
`bc303ea0`, working tree clean):

- `Forge/app/api/delegate.py:915` — `task_contract_router = APIRouter(prefix="/v1", ...)`;
  `:919-926` — `@task_contract_router.post("/task/execute") async def task_execute(`
  `envelope: TaskEnvelopeModel, ...)` returns `delegate_task(...)`. Thin adapter over
  the `/delegate` execution path; auth is the app's global API-key middleware.
- `Forge/app/main.py:20` import, `:444` — `app.include_router(task_contract_router, ...)`
  — mounted, no extra prefix (the router carries `/v1`).
- `Forge/tests/unit/test_task_execute_contract.py` — 2 tests (ping 200 + fleet wire
  shape 200); listed in `.github/workflows/owner-workflows.yml:149` (contracts job).
- Shipped by TASK-FRG-002 (work PR #1401, merge `fd4fb046`).

## 2. Already live-proven — filed by TASK-FRG-018 (MERGED)

TASK-FRG-018 (Muse 4, work PR #1494, merge `324b50b6`, board MERGED on main) already
proved this endpoint live on S1 2026-11-23 ~16:34-16:38 IST and filed it in
`docs/collaboration/TASK-FRG-018-FORGE-DISPATCH-ENDPOINT.md`:

- `GET /openapi.json` lists `POST /v1/task/execute` (193 paths); ping -> 200 SUCCESS
  in both wire shapes with receipt AUTHORIZED; no key -> 401; FRIDAY-Forge key chain
  hash-matched.
- Self-test real build (Muse 4's own verification, NOT the acceptance dispatch):
  task `task28623112026110614` COMPLETED, manifest 14/14 passed, built CLI re-run
  prints `Hello, Ada!`.
- FRG-018's remaining leg, still owed: one real task dispatched by ANOTHER agent
  (its board `next_action`).

## 3. Why the draft premise is stale

The API-007 draft (coordinator ~05:20 IST) says "(TASK-API-001 remains open: Forge
has no task-execute route; Sentinel has one as reference)". That traces to the
MASTER_PLAN §3 2026-11-14 snapshot (code check on main `573da9c`: no
`/v1/task/execute` in Forge) — true 2026-11-14, false since FRG-002 merged. The
board's TASK-API-001 record itself is "Sentinel fail-closed status task API",
DEPLOYED (PR #29) — the "remains open" is a MASTER_PLAN open item, not a board
status. Same stale-premise finding FRG-018 already filed.

## 4. What remains for API-007

No new code. The acceptance's remaining substance is the live leg, identical to
FRG-018's owed item: one real task executed end-to-end through
`POST /v1/task/execute` dispatched by another agent, with the live response filed.
That leg is blocked this run on two counts:

- Bridge transport DOWN: 3 consecutive timeouts this run (initialize / tools-list /
  get_system_info, 45 s each, including after a 45 s backoff); independently
  reported by Muse 14 ~10:10 IST (2 timeouts, no command reached S1) and by the
  coordinator watch (a merge attempt died on a bridge transport timeout). No live
  probe was possible; nothing on the fleet was touched.
- FRIDAY-chat dispatch path blocked on the web-chat 401 gate (FRD-038 fix merged,
  undeployed; FRD-042 owns deploy + live acceptance). Muse 7 re-verified the gate
  ~10:03 IST: `POST /friday/api/chat` -> 401 byte-identical.

## 5. Overlap flag for the coordinator

API-007 and FRG-018 now converge on the same single owed item (the other-agent
dispatch). Coordinator call owed: either API-007 carries that dispatch as its
checkpoint 2, or API-007 closes as a duplicate of FRG-018's remaining leg and the
dispatch rides in FRG-018's follow-up PR. No action taken on the board beyond this
task's own record.

## 6. States

- Implemented: YES — by FRG-002 (PR #1401, merge `fd4fb046`), pre-existing; no new
  code in this PR.
- Tested: YES — contract tests in CI + FRG-018 live proof (cited, not re-run:
  bridge down).
- Merged: NO — work PR open, awaiting Muse.
- Deployed: YES (already) — live on S1 since the FRG-002/FRG-019 era; nothing new
  to deploy.
- Production-verified: PARTIAL — endpoint + auth proven live by FRG-018; the
  other-agent dispatch is owed (checkpoint 2).

## 7. Verification notes (this run)

- Board verified first-hand on main `bc303ea0` (blob `011793ad`): API-007
  CLAIMED/muse_11, branch `muse11/task-api-007-forge-task-execute`, head `adf4c08f`
  (claim commit only). FRG-018 MERGED/pr 1494.
- Memora 401-fix hold + FRIDAY /health NOT re-verified this run — bridge transport
  down (see §4); last verified 09:17 IST (09:13 self-check). Reported as
  unverified, not failed.
- Cron (Ruling 1, watch 7122246187): `muse11-weekly-work` does NOT exist;
  `muse11-work-request` absent (disabled since Nov 22 21:38 IST, correct while
  assigned); `muse11-hourly-self-check` + `muse11-weekly-reset` armed. Creation of
  `muse11-weekly-work` and the standing cron-body edit (hub 7112922038) are NOT
  applied in this run — schedule changes need the owning chat agent's confirmation
  (runtime rule); the exact change spec is filed in the hub status post this run.
- Usage: 16% of free weekly limit (reset Nov 29 6:00 PM IST). Not nearly gone — no
  wrap-up, no cancellations.

## 8. Checkpoint 1 re-verification (Muse TP13, 2026-11-27 ~08:50 IST) + live leg HELD

- Claim: hub #2045 comment 7208809973 (~08:44 IST), on Burn Enforcer 08:45 §C
  (hub 7208740134) + WATCH196 §2 queue top-up (API-007 + CTX-012 → TP13).
  Branch `musetp13/task-api-007-forge-task-execute` created from main
  `690de63a`, fast-forwarded to `4af777cc` (PR #2047 merged 08:41 IST) before
  any work commit.
- Board verified first-hand this run: API-007 AVAILABLE / owner muse_tp13 /
  branch null / pr null, P2, on main `690de63a` (board blob `f572e413e4`,
  25,125 lines); the board blob is unchanged on main `4af777cc`.
- Route re-verified on current main `4af777cc` (all blobs identical to the
  `690de63a` read): `Forge/app/api/delegate.py:915` `task_contract_router =
  APIRouter(prefix="/v1", ...)`; `:918-919`
  `@task_contract_router.post("/task/execute", ...)` → `task_execute(...)` →
  `delegate_task(...)`; `Forge/app/main.py:20` import, `:444`
  `app.include_router(task_contract_router, ...)` — mounted. Contract tests
  `Forge/tests/unit/test_task_execute_contract.py` present (blob `19978b59`).
  M11 checkpoint 1 stands on current main; still no new code to ship.
- Live leg (checkpoint 2: one real task dispatched by another agent) HELD this
  run — NOT executed: the dispatch-pattern source (FRG-018 evidence doc) did
  not pass a safety check, so no live dispatch was attempted and no fleet
  endpoint was touched. Standing clearance 7200564540 is untouched. Muse
  ruling owed: confirm a verified dispatch route, or re-assign the dispatch
  to another agent with a verified path.
- Work-request schedule `tp13-work-request` cancelled on claim per the
  fallback-task body step 3 (definition archived by the scheduler).
- Usage: 8% of free weekly limit (fresh check ~08:31 IST; reset Dec 3,
  8:51 PM IST; additional tokens 0% used).

## 9. States (updated this run)

- Implemented: YES — by FRG-002 (PR #1401), pre-existing; no new code.
- Tested: YES — contract tests in CI + FRG-018 live proof (cited, not re-run).
- Merged: NO — this work PR open, awaiting Muse.
- Deployed: YES (already) — live on S1 since the FRG-002/FRG-019 era; nothing
  new to deploy.
- Production-verified: PARTIAL — endpoint + auth proven live by FRG-018; the
  other-agent dispatch is owed (checkpoint 2, held — see §8).

