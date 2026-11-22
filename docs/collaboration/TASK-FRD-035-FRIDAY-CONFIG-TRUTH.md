# TASK-FRD-035 — FRIDAY config-truth batch: code default ON + cleared FRIDAY restart + re-probe

- **Task:** TASK-FRD-035 (P1) — coordinator POOL 8, issue #35 comment 7077110975.
- **Worker:** Muse 1. **Coordinator:** Muse. **Owner:** Surendra.
- **Claim:** issue #35 comment 7077160541 (~15:00 IST, 2026-11-22); board-only claim PR #1356
  (head `c95ca09c`, base main `c29230b`).
- **Work PR:** (number filled on filing; see board record).
- **NAMES-ONLY RULE:** no key value appears anywhere in this document, in any probe output,
  or in any commit. Only key names, MATCH/DIFFER booleans, HTTP statuses, PIDs, and file hashes.
  `FRIDAY_AUTONOMOUS_MODE` is a boolean flag, not a credential; its true/false value is stated.

## 1. Finding (ORCH-011 G3, restated)

Autonomy is ON live via the env flag + the FRD-023 boot-arm, while the code default is still OFF:
`FRIDAY/src/friday/core/config.py:212-216` declares `autonomous_mode: bool = Field(default=False, ...)`,
so a fresh Settings with no env set boots non-autonomous. The live `FRIDAY/.env` on Server 1 carries
exactly one `FRIDAY_AUTONOMOUS_MODE` line with value `true` (verified this run, §3). The coordinator
decision (POOL 8, owner standing order: agents autonomous): ALIGN TO ON.

## 2. Code change (this run)

- `FRIDAY/src/friday/core/config.py` — `autonomous_mode` default `False` → `True`; description now
  records the decision (TASK-FRD-035, aligned to the live env) and that the env flag opts out.
  Diff verified against the true base blob from git objects (`8d0619ac`, +2/−2 lines).
- `FRIDAY/tests/test_autonomous_mode.py` — new test `test_autonomous_mode_code_default_is_on`
  (bare `Settings(_env_file=None)` with the env flag removed reads `True`); the old
  `test_personal_assistant_defaults_keep_privileged_modes_disabled` renamed to
  `test_personal_assistant_explicit_opt_out_keeps_privileged_modes_disabled` (explicit
  `autonomous_mode=False` still disables; assertions unchanged).
- `FRIDAY/tests/test_fleet_supervision_loop_contracts.py` — docstring/comment only: the
  rebuild test pins that a *runtime toggle* does not survive a settings rebuild, not the code
  default. Its final assertion (`False` after reload) still holds in the suite because the
  session conftest forces `FRIDAY_AUTONOMOUS_MODE=false`; no assertion changed.
- `FRIDAY/tests/test_autonomous_daemon_arm.py` — docstring only: "(the flag defaults to False)"
  → "(the flag defaults to True since TASK-FRD-035; the gate is what honours an opt-out)".
- No local pytest run: the worker clone was blocked by an execution-risk check in this run, so all
  git work was done through the GitHub API; the affected suites are verified by CI on the work PR
  (the `test` check). `FRIDAY/.env.example` (`FRIDAY_AUTONOMOUS_MODE=False`, line 104) deliberately
  NOT changed: it is a deployment template, not the code default; the live `.env` already reads `true`.
- Diffs for all four files verified against their true base blobs; all four pass `py_compile`.

## 3. Before state (verified 2026-11-22 ~15:00 IST, live S1 via bridge)

- FRIDAY service before the cleared restart: `FRIDAY.service` active (running) since 13:52:30 IST,
  Main PID **2148997** (a restart at 13:52:30 had already picked up the FRD-034 `.env` fix —
  see §5 for the disclosure).
- Live `.env` `FRIDAY_AUTONOMOUS_MODE`: `true` (1 line).
- Pre-restart probe, `POST http://127.0.0.1:10000/api/chat` with `ask cortex report operational status`:
  `success: true`, `http_status: 200`, `task_state: COMPLETED`, task `task_9be8f9fd62f5`,
  `contract_used: /v1/task/execute`. The FRD-034 fix was already live in the running process.
- `/health` before restart: `overall: healthy`.

## 4. Restart + re-probe (cleared window, 2026-11-22 ~15:00 IST)

- Clearance: GRANTED by the coordinator in the POOL 8 post (issue #35 comment 7077110975).
- Restart: `oracle_restart_service` (FRIDAY) once. Before PID **2148997** → after PID **2180495**,
  active since 15:00:11 IST. Exactly one restart by this task.
- `/health` after restart: `overall: healthy` (observed 15:01:05 IST).
- Ask re-probe, `ask cortex report operational status`: `success: true`, `http_status: 200`,
  `task_state: COMPLETED`, task `task_6e55d6d09cfd`, `contract_used: /v1/task/execute`.
- Delegation re-probe, `tell cortex to run a health check on itself and report the result back to me`:
  `success: true`, `http_status: 200`, `task_state: COMPLETED`, task `task_19447dde4017`,
  `contract_used: /v1/task/execute`, `agent: cortex`.
- FRIDAY settled after restart: Memory 20.8M (a 199.7M reading at startup settled within minutes;
  service limit 200M, no OOM, probes served normally).

## 5. Disclosures

- **The 13:52:30 IST restart predates the clearance.** The journal shows systemd stopping PID
  2076194 at 13:52:25 and starting PID 2148997 at 13:52:30 (graceful stop/start, NRestarts=0,
  no crash). The actor is not recorded in the journal slice read. It picked up the FRD-034 `.env`
  fix, proven by the §3 pre-restart 200 probe. This task's cleared restart (§4) is the one restart
  in the cleared window; the 13:52 restart is disclosed here, not claimed as this task's.
- **This run's live probes** left three conversation-history entries and three task records in
  FRIDAY's store (`task_9be8f9fd62f5` pre-restart ask, `task_6e55d6d09cfd` post-restart ask,
  `task_19447dde4017` delegation), same disclosure pattern as TASK-ORCH-010 / TASK-API-005 /
  TASK-FRD-034. The pre-restart ask and both post-restart probes all returned 200.
- **Board hygiene in this work PR:** the TASK-FRD-034 record is flipped IN_REVIEW → MERGED
  (its work rode in claim PR #1347, merged 13:48:35 IST, merge `3d03285f`, verified via API) —
  the flip was owed since the merge and is filed here, disclosed in the PR body.

## 6. Acceptance status

- Code default for `FRIDAY_AUTONOMOUS_MODE` matches the live env value (ON): **MET in code**
  (`config.py` default `True`); live env already `true`. No restart/redeploy can silently flip
  autonomy via the default; the env flag remains the opt-out.
- FRIDAY restarted ONCE in the cleared window (before Muse 6 VOI-027 probes): **MET** (15:00:11 IST,
  PID 2148997 → 2180495; no VOI-027 probe activity seen in issue #35 as of this run).
- FRIDAY to Cortex ask + delegation re-probed at 200: **MET** (both 200 COMPLETED, §4).
- `/health` 200 after restart: **MET** (`overall: healthy`).
- Tests: **NOT YET VERIFIED locally** (no local pytest — see §2); verification owed from CI on the
  work PR.

— Muse 1
