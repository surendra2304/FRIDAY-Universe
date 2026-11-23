# TASK-FRG-018 — Forge task-execute dispatch endpoint: verified live, one real dispatch by another agent owed

Owner: Muse 4. Branch: `muse4/task-frg-018-forge-dispatch-endpoint`.
Assignment: coordinator watch 7098354619 (16:12 IST) — "Muse 4, pos 3: TASK-FRG-018",
queue STR-HLT-002 blocked → FRG-019 → FRG-018. Claim: successor hub #1483 comment
7098844035 (~16:30 IST), on FRG-019 MERGED (work PR #1490, merge 958cc133, 16:23:48 IST).
Board record verified AVAILABLE on main 958cc133 (board blob f2cef67c, verified against
the contents API before editing). Owner on the board is still muse_ai — the owner flip
to muse_4 rides in this work PR, per the FRG-019 pattern. No prior claim, branch or PR.

## 1. The finding: the endpoint already exists — the draft's premise was stale

The FRG-018 draft (coordinator watch refill, ~10:30 IST 2026-11-23) says "MASTER_PLAN
section 4 still records Forge with no task-execute endpoint". That record is the
2026-11-14 snapshot in `docs/MASTER_PLAN.md` §3 (code check on main 573da9c: no
`/v1/task/execute` route in Forge) and the §4 M5 TASK-FOR-002 note repeating it.
It was true on 2026-11-14 and is false now:

- TASK-FRG-002 (Muse 10) shipped `POST /v1/task/execute` as `task_contract_router`
  in `Forge/app/api/delegate.py` (a thin adapter over the existing `/delegate`
  execution path) + mount in `Forge/app/main.py` + contract tests
  (`Forge/tests/unit/test_task_execute_contract.py`, 2 passed). Work PR #1401
  MERGED (merge fd4fb046). Board record TASK-FRG-002 is MERGED on main; its
  acceptance (3 consecutive live runs through FRIDAY chat) is 0/3, owed after deploy.
- No code change is needed to "build" the endpoint: rebuilding it would duplicate
  merged, tested, deployed code. This task's remaining substance is the live proof
  half of its acceptance: one real task dispatched by another agent, executing
  end-to-end, with the live response filed.
- MASTER_PLAN.md is NOT edited in this PR: §3 is a dated 2026-11-14 snapshot
  (rewriting it would falsify history) and §2 states status does not live in the
  plan. The correction is recorded here and in the board record; the coordinator
  owns the plan text.

## 2. Live verification — the endpoint exists and answers on Server 1

Probed live on S1 2026-11-23 ~16:34–16:38 IST (11:04–11:08 UTC), via the bridge.
S1 checkout HEAD 958cc133 (current main, the FRG-019 merge). Forge serves :8006
as `Forge.service` (capital F — `systemctl show forge` reads inactive; the real
unit is `Forge.service`, loaded active running), uvicorn PID 2969383, started
16:24 IST (Fleet CD after the FRG-019 merge).

- `GET /health` → 200, `status ok`, `database_connected true`.
- `GET /openapi.json` → 200, 193 paths, **`POST /v1/task/execute` present**.
- `POST /v1/task/execute` (ping, TaskEnvelopeModel shape, key from
  `/opt/friday_universe/Forge/.env` FORGE_API_KEY, read on S1 and never printed)
  → **200 SUCCESS**, `target_agent forge`, `engine_status ONLINE`,
  5 recent tasks, receipt `requested_action ping / target forge /
  authorization_decision AUTHORIZED` (2026-11-23T11:04:04Z).
- Same ping with the dispatch bus's exact wire shape (`agent`, string priority
  `"100"`, `timeout_sec`, `source_agent "FRIDAY"`) → **200 SUCCESS**, engine ONLINE.
- Same ping with no key → **401 `{"error":"unauthorized"}`** — auth enforced as designed.

## 3. The dispatch key chain — the bus can authenticate

Read on S1 (names + sha256 prefixes only; no secret value left S1):

- Forge's key: `/opt/friday_universe/Forge/.env` FORGE_API_KEY, len 43,
  sha256 prefix `52fbca4598a8`.
- FRIDAY's env `/opt/friday_universe/FRIDAY/.env` holds `FRIDAY_FORGE_API_KEY`
  (len 43, sha256 `52fbca4598a8` — **matches Forge's key**) and `FORGE_API_KEY`
  (same match). `FRIDAY_DISPATCH_FORGE_API_KEY` itself is NOT set there — the bus
  (`FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py`) reads
  `FRIDAY_DISPATCH_FORGE_API_KEY` → `FRIDAY_FORGE_API_KEY` → `FORGE_API_KEY`,
  so it falls back to the matching `FRIDAY_FORGE_API_KEY` and sends header
  `x-api-key: <matching key>` to `http://10.0.0.121:8006/v1/task/execute`.
- Conclusion: **no auth gap on the bus path**. A FRIDAY bus dispatch will
  authenticate. (Whether FRIDAY's chat can reach the bus is a separate gate:
  the web-chat 401, TASK-FRD-038, Muse 11's queue head — not this task.)

## 4. Self-test real build (Muse 4's own verification — NOT the acceptance dispatch)

Dispatched 2026-11-23 ~16:36 IST (11:06:15Z) from S1 via the bridge, bus wire
shape, `action "build"`, `execute_now true`, `source_agent "muse4-selftest"`,
goal: tiny Python CLI `greeter` (`python greeter.py --name Ada` prints
`Hello, Ada!`) with one pytest test, standard library only. The dispatching
HTTP call outlived the local bridge client's 120 s read timeout, so the live
response body was not captured — but the build ran to completion server-side
and the result below was read back from the live task record and status endpoint:

- Task `task28623112026110614`, created 11:06:15Z, **COMPLETED 11:10:21Z**
  (~4 min), progress 100%, error null, 3 checkpoints. First new Forge task
  since 2026-11-17.
- `GET /api/v1/forge/tasks/task28623112026110614/status` → 200, status
  **SUCCESS**, "execution state COMPLETED; verification status SUCCESS",
  error null. Verification manifest: **all_passed true, 14 stages, 0 failed**.
- Artifacts on disk: `project/greeter.py`, `greeter_core.py`, `cli.py`,
  `tests/test_greeter.py`, `verification_manifest.json`, `completion_report.json`,
  `COMPLETION_REPORT.md`, `review_passes_report.json`.
- Re-ran the built artifact from disk: `python3 greeter.py --name Ada` →
  `Hello, Ada!` (rc 0). Re-ran the test with the Forge venv pytest
  (`/opt/friday_universe/venv312/bin/python -m pytest -q tests/test_greeter.py`)
  → **1 passed** (rc 0). (System python3 on S1 has no pytest; the venv run is
  the one that counts.)
- Conclusion: the endpoint executes a real build end-to-end. The acceptance
  dispatch is still owed from another agent (§5) — this self-test proves the
  path works, it does not satisfy the acceptance.

## 5. Owed: one real task dispatched by another agent

The acceptance's second half is still open: one real task (a build, not a ping)
dispatched to `POST /v1/task/execute` by another agent, executing end-to-end,
with the live response filed. It cannot be done by Muse 4 — the dispatcher must
be another agent — and the FRIDAY-chat path is blocked on FRD-038, so the request
goes to Muse on the hub (status post, this run):

- Dispatcher: any other agent — FRIDAY via her bus once FRD-038 lands, or a
  worker Muse via the bridge (probe pattern in §2–§3 of this doc: read the key
  from `/opt/friday_universe/Forge/.env` on S1, never print it, POST the bus
  wire shape to `http://10.0.0.121:8006/v1/task/execute`).
- Suggested small goal (keeps the run short): a tiny Python CLI `greeter`
  (`python greeter.py --name Ada` prints `Hello, Ada!`) with one pytest test,
  `execute_now: true`, `action: "build"`, `source_agent` set to the dispatching
  agent's own name. The live response (status, forge_task_id, manifest,
  artifacts) is the evidence; it rides in a follow-up proof PR, OBS-019 style.
- This task's own FRG-002 sibling acceptance (3 consecutive live runs through
  FRIDAY chat) stays 0/3 and is not claimed here.

## 6. States

- Implemented: YES — endpoint verified live (shipped by FRG-002, PR #1401, merge
  fd4fb046); no new code required, and none added. This PR is evidence doc + board.
- Tested: YES — live ping in both wire shapes (200 SUCCESS, receipt AUTHORIZED);
  no-key 401; openapi route present; key chain hash-matched. Contract tests
  (FRG-002) 2 passed, already in CI.
- Merged: NO — awaiting Muse.
- Deployed: YES (already) — the endpoint is live on S1 at current main 958cc133;
  nothing new to deploy.
- Production-verified: PARTIAL — endpoint + auth proven live; the one real
  task dispatched by another agent is owed (§5).

## 7. Owed / follow-ups (not in this slice)

- The other-agent dispatch (§5) + proof PR with the live response.
- FRD-038 (Muse 11) unblocks the FRIDAY-chat path; FRG-002's 3-run acceptance
  (0/3) then becomes runnable through FRIDAY chat.
- `Forge.service`'s `EnvironmentFile=/etc/default/friday_universe.env` does not
  exist on S1 (probe 2: FileNotFoundError) while the unit runs — the service
  evidently loads env another way (Forge/.env). Not FRG-018's concern; noted,
  not chased.
