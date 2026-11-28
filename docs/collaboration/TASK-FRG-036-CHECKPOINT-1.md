# TASK-FRG-036 — Checkpoint 1: Forge POST /v1/task/execute — route already on main; the live leg is the work

- Task: TASK-FRG-036 — Forge: implement /v1/task/execute route (MASTER_PLAN §6 TASK-API-001).
- Worker: Muse TP4. Branch: `musetp4/task-frg-036-task-execute-route` @ `fae3ee05` (claimed 2026-11-27 18:53 IST, hub #2045 comment 7219637401).
- Main verified first-hand this run: `cf49af6bcb04d22933db46c3ff612594c6a7ce16` (merge PR #2141).
- Board record on main: TASK-FRG-036 AVAILABLE / owner muse_tp4 (flip to CLAIMED rides coordinator board PR #2151, WATCH225 §A). Queue settled by WATCH224 §D: FRG-036 (head, CLAIMED) → CTX-014 (pos 2, QUEUED) → REL-111 (pos 3).
- Filed: 2026-11-27 19:53 IST. Read-only repo exploration; no live command run this run except read-only GitHub reads and bridge get_system_info.

## §1 — Headline finding: the route already exists on main

The board premise is stale. The board evidence (filed by the coordinator, watch210, 2026-11-27) says "Sentinel merged the route in PR #29, Forge still absent". That was already wrong when filed:

- **TASK-FRG-002 shipped POST /v1/task/execute on Forge**, commit `b8dc480d`, 2026-11-22T18:05:47Z: "TASK-FRG-002: ship POST /v1/task/execute fleet contract on Forge". Verified first-hand via the commits API on `Forge/app/api/delegate.py` (latest commit touching that file).
- The route, `Forge/app/api/delegate.py` lines 907–925: `task_contract_router = APIRouter(prefix="/v1", ...)` with `@task_contract_router.post("/task/execute", response_model=TaskResultModel, status_code=200)`, handler `task_execute(envelope)` returning `await delegate_task(envelope, orchestrator, store)`. The file comment states the reason: "The fleet dispatch bus posts every specialist task to POST /v1/task/execute ..., but Forge only served /api/v1/forge/delegate, so a FRIDAY-chat code task died at the bus with \"Action 'build' not found on Forge\"."
- Mounted in `Forge/app/main.py` line 444: `app.include_router(task_contract_router, tags=["FRIDAY Universe Forge Task Contract"])` — "router carries its own /v1 prefix". Auth is the app's global API-key middleware, same as /delegate; nothing is exempted.
- **Board file path is also stale**: `Forge/forge/apps/api/main.py` does not exist on main (contents API 404; `Forge/forge/` has no `apps/`). The real files are `Forge/app/api/delegate.py` (route, 41,105 B) and `Forge/app/main.py` (mount, 26,581 B).

## §2 — The execution path behind the route is real, not a stub

`delegate_task` (`Forge/app/api/delegate.py` lines 245+) dispatches on `envelope.action`:

- `status` / `health` / `ping` — queue snapshot, engine ONLINE.
- `cancel` — canonical lifecycle cancellation (TASK-REL-019).
- `test` / `verify` — verification-engine battery + manifest, verdict derived by `app/verification/verdict.py` (TASK-FRG-011).
- Engineering synthesis (`build` / `fix` / `refactor` / `review` and any other action): `orchestrator.intake_and_plan(goal, requirements, mode, repo_url, local_path)`; `plan_only` returns PLANNED with nothing executed (TASK-REL-019); with `execute_now` it runs `orchestrator.run_task(task.id)`, re-verifies, settles the final verdict via `apply_final_verdict`, and returns the settled verdict — SUCCESS means the task completed AND the final battery passed.

## §3 — Caller side verified: the FRIDAY dispatch bus already posts here

`FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py` (29,658 B, lines 150–190, 234):

- Deployed layout (TASK-VAL-006, 2026-11-22): S1 = 10.0.0.121 (Inference, Memora, Forge) + loopback Sentinel; S2 = 10.0.0.120. Forge base URL `http://10.0.0.121:8006`, health `{base}/health`.
- "Every agent serves POST /v1/task/execute (see fleet_client); VyralX has its own API." Default action path `/v1/task/execute` for Forge; payload maps `task_id / agent / action / payload / priority / timeout_sec / source_agent="FRIDAY"`; auth via `x-api-key` header when configured; overridable with `FRIDAY_DISPATCH_FORGE_URL` / `_API_KEY` / `_ACTION_PATH`.
- **Port note for the live probe, not a conclusion**: the repo `Forge/docker-compose.yml` maps `8002:8000` and `Forge/.env.example` sets `FORGE_PORT=8000`, while the bus expects Forge at `10.0.0.121:8006`. Which port the live S1 Forge actually listens on is a live fact to confirm in the probe; do not assume either.

## §4 — Tested state: NOT established for this route

- No `test_frg002*` file exists in `Forge/tests/` (top level or `integration/`).
- `Forge/tests/integration/test_api.py` (6,163 B) contains zero hits for `task/execute`, `task_contract`, `/delegate`, or `TaskEnvelope`.
- No `docs/collaboration/TASK-FRG-002-EVIDENCE.md` exists on main (contents API 404); TASK-FRG-002 has no board record (pruned as MERGED, same as STR-075 / OPS-004).
- The route therefore has no dedicated test and no filed live evidence. "Tested" is NO until a test or a live probe says otherwise.

## §5 — What FRG-036 still has to prove (acceptance criteria, re-scoped)

FRG-036 is now a **live-verification task, not an implementation task**. No code change is expected unless the probe finds the route broken or unreachable on the live service. The two acceptance criteria map to live legs:

1. "Forge exposes POST /v1/task/execute accepting a real code task and returning execution output; route live on the Forge service and probed through the gateway." — LIVE LEG A (probe).
2. "One real code task requested through FRIDAY chat executes via the new route end-to-end, with the trace filed as docs/collaboration/TASK-FRG-036-EVIDENCE.md." — LIVE LEG B (end-to-end).

## §6 — Live-leg plan: exact read-only probe list (Leg A)

Run on Oracle Server 1 (Forge host, 10.0.0.121) via bridge run_shell; read-only first, in order. Standing clearance 7200564540 covers a worker's own-task live verification; the grant is settled (owner approval 2026-11-26 18:25 IST, rulings 7192682851 / 7197725825) and is never re-checked.

- 0. `curl -s -m 10 http://10.0.0.121:8006/health` — expect HTTP 200 with Forge health. If 8006 refuses, also try `http://10.0.0.121:8002/health` and `http://127.0.0.1:8000/health` (compose port) and record which one answers; do not guess.
- 1. `systemctl status forge --no-pager | head -20; ss -ltnp | grep -E '8006|8002|8000'` — service state + which port is actually listening, and which process owns it.
- 2. `curl -s -m 10 http://10.0.0.121:8006/openapi.json | python3 -c "import json,sys; d=json.load(sys.stdin); print([p for p in d['paths'] if 'task/execute' in p])"` — route present in the live service's OpenAPI (proves the deployed build carries FRG-002, not just main).
- 3. `curl -s -m 15 -X POST http://10.0.0.121:8006/v1/task/execute -H 'Content-Type: application/json' -H 'x-api-key: <key from the service env, never posted to the hub>' -d '{"task_id":"frg-036-probe-1","agent":"forge","action":"ping","payload":{},"priority":"low","timeout_sec":15,"source_agent":"FRIDAY"}'` — read-only action, no execution. Expect HTTP 200, `status: SUCCESS`, engine ONLINE.
- 4. `curl -s -m 10 https://friday-universe.duckdns.org/forge/health` (gateway path if Caddy routes /forge; if it 404s, record the actual gateway route from the Caddy config on S1 and re-probe through it) — proves the gateway leg, per criterion 1.

Pass criteria for Leg A: 0–2 confirm a live Forge answering on a known port with /v1/task/execute in its OpenAPI; 3 returns SUCCESS for the ping action; 4 confirms the gateway route (or the corrected route is recorded). Any failure is filed as the finding, not worked around silently.

## §7 — Live-leg plan: end-to-end task (Leg B)

- One real, small, demo-safe code task requested through FRIDAY chat (e.g. a trivial repo task with `execute_now`), dispatched by the bus to `POST /v1/task/execute` on S1 Forge; capture the bus envelope, the Forge response (task id, status, summary, execution output, verification manifest), and the resulting repo change if any. File the full trace as `docs/collaboration/TASK-FRG-036-EVIDENCE.md`.
- Safety: small task only; no live money, no destructive action, no secret in any posted payload. The API key is read from the service env on S1 and never posted to the hub.
- Route question for the coordinator: Leg B's FRIDAY-chat step is a live move through the chat/dispatch path. TP4 will run Leg A first (read-only probe + ping action) under standing clearance 7200564540; Leg B runs the same way unless the coordinator rules otherwise next run. If the probe finds the live service does NOT carry the route (stale deploy), FRG-036 reverts to an implementation + redeploy task and this checkpoint is amended.

## §8 — Five states (honest, this checkpoint)

- Implemented: YES — route code on main since FRG-002, commit b8dc480d, 2026-11-22.
- Tested: NO — no dedicated test found; no FRG-002 evidence filed.
- Merged: YES — b8dc480d is on main cf49af6b.
- Deployed: UNKNOWN — live S1 Forge build unconfirmed; Leg A probe owed.
- Production-verified: NO — Leg A + Leg B owed.

## §9 — Queue and board

- Queue: FRG-036 (head, CLAIMED, this checkpoint) → CTX-014 (pos 2, QUEUED, WATCH224 §D) → REL-111 (pos 3).
- Board flip FRG-036 AVAILABLE → CLAIMED rides coordinator board PR #2151 (WATCH225 §A, open, CI pending, merge owed next run by the coordinator).
- Fleet this run (bridge get_system_info): Oracle Server 1 + Server 2 ONLINE; forge listed among agents; public ingress https://friday-universe.duckdns.org. S2 checkout musetp13/task-frd-046 @ 094dedb2 (another worker's checkout, not a TP4 action).

## §10 — Next

- Next run: run Leg A probe list (§6) from this checkpoint; file results as checkpoint 2 / TASK-FRG-036-EVIDENCE.md (or amend this checkpoint if the probe re-scopes the task). Then Leg B end-to-end + work PR. No PR opened this run (checkpoint 1 is the plan + repo verification, STR-099 precedent).
- Usage 25% of free weekly limit (checked this run; was 24% at 18:53 IST), reset Nov 30, 2:18 PM IST. Not exhausted.
- Schedules verified: musetp4-hourly-self-check enabled (1h); musetp4-weekly-reset enabled (Mon 14:28); musetp4-work-request absent — correct mid-task state per GUARD, not re-created.
