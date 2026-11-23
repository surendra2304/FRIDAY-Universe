# TASK-OBS-011 — LiveKit voice worker: GET :8081/health

- **Status:** code + tests done, work PR open; **live verification OWED** — needs
  deploy + FRIDAY-Voice restart on S1 with coordinator clearance (see §6).
- **Assigned:** coordinator watch 7094281062 (2026-11-23 ~12:53 IST).
- **Claim:** issue #35 comment 7094568374 (2026-11-23 ~13:09 IST).
- **Branch:** `muse13/task-obs-011-livekit-health-route`, from main `ba2dbea7`.
- **Work PR:** #1475 (head 84c72968).
- **Queue after:** VOI-030 → REL-085\* (coordinator queue maintenance 7094463200).

## 1. Scope

Add a `/health` route to `livekit_worker.py` — GET :8081/health is 404 — and
verify it live. The fleet convention (and the watcher/Cortex probes) is
GET /health; the voice worker was invisible to the standard probe.

## 2. Baseline (first-hand, live, S1, 2026-11-23 ~13:12 IST)

- `ss`: `0.0.0.0:8081` + `[::]:8081`, PID 2823815, `FRIDAY-Voice.service`,
  MainPID 2823815, started 11:44:35 IST, active.
- `GET http://127.0.0.1:8081/` → **200 "OK"**,
  `Server: Python/3.10 aiohttp/3.14.5`.
- `GET http://127.0.0.1:8081/health` → **404 "404: Not Found"** (same server
  header). The 404 is confirmed, not assumed.

## 3. Root cause (first-hand, SDK source on S1)

- Port 8081 is the LiveKit agents SDK's built-in health/status HTTP server
  (livekit-agents **1.8.12**, `/opt/friday_universe/venv312/.../livekit/agents/`).
  The port literal appears nowhere in repo code — it is the framework default
  (`WorkerOptions.port`, `ServerEnvOption(dev_default=0, prod_default=8081)`;
  "The HTTP server is used as a health check endpoint").
- The SDK registers exactly two routes in `AgentServer._start`
  (`worker.py:698-699`): `GET /` (the liveness probe — 503 while the inference
  process is down / not connected to LiveKit, else "OK") and `GET /worker`
  (JSON worker info). There is **no `/health` route and no public hook** to
  add one (`WorkerOptions` has no route/http-server option).
- Two candidate hook points were tested on the production venv and one
  **fails**: a `worker_started` listener is too late — the aiohttp router
  freezes when the runner starts
  (`RuntimeError: Cannot register a resource into frozen router`, reproduced
  2026-11-23). The alias must be registered after the SDK adds its routes
  but before `HttpServer.start()` runs the runner.
- Prior art: TASK-SEN-013 §4.1 already attributed :8081 to "the FRIDAY-Voice
  LiveKit worker's health endpoint (production component)" — the listener is
  legitimate; only the `/health` path was missing.

## 4. Change

`FRIDAY/src/friday/voice/livekit_worker.py` (+64 lines, no other file touched
by the fix):

- `_add_health_alias(app)`: finds the SDK's GET `/` route in the aiohttp
  router and registers `GET /health` with **the same handler object** —
  identical semantics by construction, no duplicated liveness logic.
  Idempotent (a second call, or a future SDK that ships `/health`, is a
  no-op); returns False when there is no GET `/` route.
- `_HealthAliasHttpServer(_lk_http_server.HttpServer)`: overrides `start()`
  to run the alias **before** `super().start()` sets up the runner (i.e.
  before the router freezes), then starts normally. `/` and `/worker` are
  untouched.
- Installed at import time (`_lk_http_server.HttpServer =
  _HealthAliasHttpServer`); the `cli.run_app(_worker_options())` entrypoint
  is unchanged. The worker module IS the worker process, so the patch only
  affects this server; the telemetry/prometheus server is a different class
  (`livekit.agents.telemetry.http_server`) and is untouched.

## 5. Tests

`FRIDAY/tests/test_voice_livekit_health_route.py` — 6 tests:

- `test_add_health_alias_registers_health` — real HTTP round-trip on an
  ephemeral port: GET /health → 200 "OK", GET / → 200 "OK", GET /nope → 404.
- `test_add_health_alias_reuses_the_root_handler` — the /health route serves
  the SAME handler object as /.
- `test_add_health_alias_no_root_route` — no GET / → False, no /health.
- `test_add_health_alias_idempotent` — second call False, one /health resource.
- `test_health_alias_server_start_registers_before_freeze` — the subclass
  path end-to-end: /, /health and /worker all 200 after start().
- `test_sdk_http_server_class_is_patched` — importing the worker installs the
  subclass as the SDK HttpServer.

Results (first-hand):

- **6 passed in 2.18 s**, local venv 2026-11-23 ~13:47 IST, with the exact
  production dependency versions (livekit-agents 1.8.12, aiohttp 3.14.5),
  the branch code, and the real worker module imported. (This VM's
  `NO_PROXY` carries bare IPv6 literals that break httpx at import, so the
  run used `NO_PROXY=localhost,127.0.0.1` — a runner-env quirk, not a code
  issue; S1's env does not have it.)
- **S1 first run (head f65f0c8a, venv312, scratch copy, production checkout
  untouched): 5 passed, 1 failed** — the failure was the test harness, not
  the fix: one app served across separate `asyncio.run` calls (aiohttp
  binds an Application to its first loop). Fixed in 84c72968 by fetching
  all paths from one server + one loop (`_fetch_many`).
- **S1 re-run of 84c72968: 6 passed in 21.31 s** (venv312, scratch copy of
  the branch, production checkout untouched), 2026-11-23 ~13:52 IST. The
  bridge transport was slow during this run (calls taking 200–380 s, one
  JSON parse failure on a wrapper), so the re-run result landed after the
  PR was opened; it is recorded here and in the status post. CI on the
  work PR is the canonical full-suite run.

## 6. Live verification — OWED (deploy + restart clearance requested)

The code cannot go live without the worker process restarting on the new
code. **No restart has been performed by this run** — the production voice
worker (FRIDAY-Voice.service, PID 2823815) still runs the old code and
:8081/health still 404s as of the last probe (~13:12 IST).

Requested from Muse (coordinator) in the status post on issue #35:

- Merge the work PR, then deploy main to the S1 checkout and restart
  `FRIDAY-Voice.service` **once**, in a voice-quiet window.
- Re-probe: `GET http://127.0.0.1:8081/health` → 200 (same body as GET /),
  `GET /` → 200, `GET /worker` → 200; `/api/voice/diagnostics` via Caddy
  green; a test voice session connects.
- Rollback: `git checkout` restore + restart FRIDAY-Voice again; the change
  is additive (the SDK's `/` route and `/worker` endpoint are untouched),
  so a rollback is a plain restart.

## 7. Board

Record `TASK-OBS-011` filed in this PR (no record existed on main `ba2dbea7`:
board blob `5f22622f`, 612 task records, zero occurrences of OBS-011 — new
draft, per coordinator direction; record rides in the work PR). Status
IN_REVIEW, owner muse_13, branch
`muse13/task-obs-011-livekit-health-route`, pr 1475.

## 8. CI — contracts guard failure and fix (2026-11-23 ~15:45 IST)

- **Failure (first-hand, contracts job log):** work PR #1475 head
  `6d5552d6`, run 45138064532, job 137568999784, step "Guard — every test
  file shipped in this PR is collected (TASK-REL-068)", 13:52 IST:
  `FAIL: 1 test file(s) shipped in this PR are collected by NO
  PR-triggered workflow` — `UNCOLLECTED:
  FRIDAY/tests/test_voice_livekit_health_route.py`. No stale references
  (guard: 1,931 test files in repo, 302 covered, 11 PR-triggered
  workflows scanned). The `test` job never runs `FRIDAY/tests/` and
  `voice-regressions` runs only `tests/test_runtime_audit_contract.py`,
  so the new test ran nowhere in PR CI — the exact REL-001 defect class
  the guard exists to catch. Coordinator watch 7096098820 carried it as
  held: "failure detail still owed".
- **Fix (this PR, follow-up commit):** added the file to the `contracts`
  job's explicit pytest list in `.github/workflows/owner-workflows.yml`
  (next to `test_voice_tool_security.py`), so the guard collects it and
  the test actually runs in PR CI. The job already installs
  `livekit-agents` and `pytest-asyncio`; the test needs only `aiohttp` +
  `livekit-agents` and uses sync tests with `asyncio.run` internally.
- **CI re-run owed:** the fix commit re-triggers all checks; a green
  `contracts` run on the new head is the proof. Live verification (§6)
  still owed after merge, per coordinator clearance.
