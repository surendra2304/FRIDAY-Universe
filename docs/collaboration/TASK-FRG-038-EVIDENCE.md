# TASK-FRG-038 — Evidence: checkpoint 1 — blocker sweep + tool identified

- Task: TASK-FRG-038 — Forge: ship the one tool another agent is currently blocked on (or first self-upgrade slice with live proof).
- Worker: Muse 19. Branch: `muse19/task-frg-038`.
- Filed: 2026-11-28 ~09:05 IST. Board verified first-hand on live main `dc1ed6f0` (board blob `b1657b5d`, 12,517 lines).
- Claim: BE 08:50 §B/§D (hub #2045 comment 7232927618, ~08:50 IST) — re-slot from Muse 11, final term expired (WATCH250 §C, BE 08:00 §C, WATCH251 §E). Hub claim post 7233066707 (~08:56 IST). This checkpoint is identification + plan only; no code yet.

## §1 — Blocker sweep (board + hub, first-hand)

Board BLOCKED tasks on live main `dc1ed6f0` (10) — same set Muse 18 swept for FRG-035 (~07:09 IST); each record read in full. None is blocked on a shippable Forge tool:

| Blocked task | Blocker | Why not a Forge tool |
|---|---|---|
| FRD-048 (TP3) | Owner gate: Fish Audio route decision before Nov 30 | Owner decision, not a tool |
| MEM-017 (TP3) | Owner gate: Halo key paste (7200182638) | Owner step, not a tool |
| INT-023 (null) | INT-032 soak timer never installed; IntelX has no running home | Fleet ops install, not a Forge tool |
| VYR-052 (TP5) | Machine-QA gate unachievable (VYR-056 CLOSED: yt-dlp n-challenge) | Closed as unachievable; no tool fixes it |
| VYR-081 (M9) | No permitted GTA 6 footage; no live EARN-024 brief | Footage/brief, not a tool |
| DB-001 (M6) | MySQL HeatWave production-usage verification | Owned by M6; database work, not Forge |
| EARN-005 | Owner answer owed: $19 product identity | Owner answer; inventing a product is not the work |
| WF-007/008/009 | CSV converter acceptance (old lane) | Owner-gated, not a Forge tool |

Hub carried items checked (BE 08:50 hub 7232927618 + WATCH251 hub 7232592508, read in full; hub read through 7233012870):
- TP4 FRG-036 Leg B re-run owed after the sandbox-deps fix + Forge restart — see §2 (the wedge is the blocker).
- VOI-031 gated on FRD-064 deploy — not a Forge tool.
- TP7 (b)/(d)/(e) + live Forge host naming — ruling asks, not a tool-block.
- M15 INF-LLM-002 / TP2 REL-095 — ruling asks, not a tool-block.
- M18 FRG-035 cp1 MERGED (PR #2244, head `324c804b`); no cp2 PR open from Muse 18 at claim time — the sandbox test-dep provisioning slice is taken, mine must differ.

**Sweep verdict: no agent is blocked on an unowned Forge tool — except one, §2: the Forge HTTP wedging blocks TP4's FRG-036 Leg B re-run (and every live Forge caller).**

## §2 — The tool: Forge HTTP wedging — async `execute_now`

**Blocked agent:** Muse TP4 (TASK-FRG-036). Its Leg B re-run "needs routing (async + polling, or a stable API process) before another re-run" (hub 7232591042, ~08:20 IST). Two consecutive Leg B dispatches were lost the same way, and Forge wedged twice.

**The defect, first-hand from code on main `dc1ed6f0`:**
- `POST /v1/task/execute` (`Forge/app/api/delegate.py:918-926`, `task_execute`) delegates straight to `delegate_task` (`delegate.py:245`).
- With `execute_now: true` (`delegate.py:379`), the handler awaits the whole build inline (`delegate.py:421-424`): `completed_task = await orchestrator.run_task(task.id)` (the 8-stage DAG — Requirements 45 s, Integration, Verification 170 s in Leg B run 1) + `verify_task` + `generate_manifest` — 9+ minutes inside one HTTP request.
- The non-`execute_now` path already does it right (`delegate.py:656-672`): `_schedule_execution(task.id, callback_url)` — "the same supervised background execution POST /tasks uses" — and returns the honest RUNNING state; completion is observable via the status endpoint (`GET /tasks/{task_id}/status`, `delegate.py:690`) and the completion webhook.
- `_schedule_execution` (`Forge/app/api/tasks.py:192-203`) is `loop.create_task(_run_task_supervised(...))` under a semaphore (`_execution_slots`, `tasks.py:110-118`) — the background machinery exists; `execute_now` bypasses it.
- Live Forge is a single worker: `Forge/app/deployment/forge.service` — `ExecStart=... uvicorn app.main:app --host 0.0.0.0 --port 8006 --workers 1`, `MemoryMax=180M`.

**Two live reproductions (TP4 evidence, hub #2045):**
- Run 1, 04:11–04:20 IST (TASK-FRG-036-EVIDENCE.md §5–§6): bus call never returned (HTTP 000 after ~9m20s; S3 FRIDAY API restarted mid-call). `/health` on S1 Forge (:8006) HTTP 000 (10 s timeouts) at 04:22, 04:23, ~04:36 IST while the port is LISTENING and the process is alive (pid 2184784, NRestarts=0, 7 threads, journal silent since 04:20:19). "The single worker (--workers 1) appears blocked by the long sync `execute_now` call / wedged in the battery."
- Re-run, 08:03 IST (hub 7232591042): Requirements node failed on an upstream HTTP 503; "Forge wedged a second time (/health 000, memory 177.4M/180M cap); TP4 restarted it 08:13:15 IST, healthy now (pid 2370661, /health 200)." Bus call HTTP 000 after 482 s (S3 FRIDAY API restarted mid-call AGAIN).

**The tool:** route `execute_now` through the existing supervised background execution and return the honest RUNNING receipt with `forge_task_id` immediately — the same shape the non-`execute_now` path already returns. `/health` stays answerable while builds run; the FRIDAY bus no longer holds a 9-minute call that dies when FRIDAY restarts; completion is polled via `GET /tasks/{task_id}/status` or delivered by the `callback_url` webhook. The FRIDAY bus adopting polling (instead of awaiting the response) is a named follow-up — coordinator ruling owed on whether the bus changes, or whether a bounded-wait variant is wanted.

**Open question for checkpoint 2 (stated, not assumed):** whether `run_task`'s sync subprocess work (the battery "spawns subprocesses" per `tasks.py` queue-endpoint docs; `Forge/app/verification/checkers.py`, `security_scanner.py`) blocks the event loop even as a background task. If it does, background runs wedge `/health` too and the slice must also move the blocking steps off the loop (`asyncio.to_thread` / `run_in_executor`). To be settled by reading `step_task` (`Forge/app/core/orchestrator.py:326`) + the checkers in checkpoint 2.

**Not my slice (stated so the two Forge tasks stay distinct):** M18's FRG-035 sandbox test-dep provisioning (PR #2244 MERGED); the Forge→Memora 401s (TP4 evidence §7: Memora key missing/wrong on the Forge side — a server-side key/config action, non-fatal per code, not shippable code; coordinator/owner to route).

## §3 — Plan (checkpoint 2: code + tests; checkpoint 3: live proof)

1. Implement: in `delegate_task`, the `execute_now` branch schedules via `_schedule_execution` and returns RUNNING + `forge_task_id` (same receipt shape as the background path); `plan_only` / `verify_only` / `cancel` / `status` / `test` paths untouched; `callback_url` webhook dispatch kept. Settle the §2 open question first — if the battery blocks the loop, move the blocking steps off it in the same change.
2. Tests: a test proving a delegate call with `execute_now: true` returns RUNNING immediately (handler returns without awaiting the DAG) and the task reaches a terminal state via background execution with status pollable; a test that a status/health action answers while a build runs. CI green (contracts workflow file list updated if a test file is added, per board discipline). Local verification first (stub runner; pytest absent locally — the 2 tests needing real runs go through CI).
3. Live proof (coordinator clearance owed — a Forge restart is a service change; no live-fleet deploy without Muse's clearance on the hub first): after merge, Forge restart on Server 1, then a Leg-B-style dispatch with `execute_now` through the FRIDAY bus; `/health` 200 DURING the build + the bus receives the RUNNING receipt + the task completes and is pollable. TP4's Leg B re-run is the blocked agent's live use. If clearance is refused, the live leg stays owed and is stated as such — no claim without it.

## §4 — Five states (honest, this checkpoint)

- Implemented: NO — identification + plan only; code lands in checkpoint 2.
- Tested: NO.
- Merged: NO — no PR yet (checkpoint PRs abolished; work PR at completion with live evidence).
- Deployed: NO.
- Production-verified: NO — live proof is checkpoint 4, gated on coordinator clearance for the Forge restart.

## §5 — Grant note

- BE 08:50 §D states the grant dispute SETTLED (owner approved full run_shell for all worker chats; main-chat approvals do not appear in permissions.history) and directs: stop checking. Standing record kept: no permissions.history record for approval 7113152293 (16 checks; last 20:17 IST 2026-11-27); Surendra's confirmation of the 18:25:56 IST tap still unanswered. No live leg run in this checkpoint; no server touched.

— Muse 19

## Checkpoint 2 — event-loop question SETTLED + fix design (2026-11-28 ~11:00 IST)

- **Branch:** `muse19/task-frg-038` fast-forwarded to main `7ecab6ce` first (merge `95dad0cbb3de2e891cedc3584c74ad52cae54b01`); this section appended after. All file:line reads below are main `7ecab6ce`, first-hand this run.
- **Question from cp1, answered:** does the battery's sync subprocess work block the event loop even as a background task? **No — there is no sync subprocess work in the battery path.**
  - Checkers (`Forge/app/verification/checkers.py`, 1,413 lines): `TestChecker.run_check` (:389), `RuntimeChecker.run_check` (:538), `LintChecker.run_check` (:214) all run external tools through `engine.terminal.run_command(...)`.
  - `Forge/app/execution/terminal.py:311`: `run_command` uses `await asyncio.create_subprocess_shell(...)` + `await asyncio.wait_for(process.communicate(), ...)` — fully async; the loop yields while a subprocess runs.
  - The only sync `subprocess.run` in terminal.py is inside `kill_process_tree` (:86–94), Windows `taskkill` branch only; on POSIX it uses `os.killpg` — a cancel/timeout cleanup path, not the battery path.
  - `Forge/app/core/orchestrator.py` (1,478 lines): no `subprocess` / `run_in_executor` / `to_thread` anywhere. `step_task` (:326) runs DAG waves via `asyncio.gather`; `run_task` (:791) loops `step_task`, then `_verify_and_repair` + `apply_final_verdict` (:917–927) — the battery + manifest + settle happen INSIDE `run_task`.
  - Verification engine (`Forge/app/verification/engine.py:143–173`): Phase A checkers concurrent via `asyncio.gather`, Phase B (TestChecker, RuntimeChecker) serial — all awaited.
  - **Conclusion:** routing `execute_now` through `_schedule_execution` (`Forge/app/api/tasks.py:192` — `loop.create_task(_run_task_supervised(...))`, semaphore-guarded at :116–120) frees the request AND leaves the loop servable: the background task awaits provider calls and async subprocesses, so `/health` stays responsive during a build. The Leg B wedging mechanism is therefore the inline await itself (request held ~9m20s; bus HTTP 000) compounded by memory pressure (177.4M/180M at wedge time) — not the battery blocking the loop. Memory headroom is a separate, still-open concern (Forge MemoryMax=180M; a background task does not fix memory).
- **The fix (designed, code owed next run):** in `Forge/app/api/delegate.py`, replace the `execute_now` inline block (:422–~652 — `await orchestrator.run_task` + second battery + manifest + re-settle + verdict derivation + three return shapes) with the same schedule-and-return-RUNNING shape the non-`execute_now` path already uses (:653–670, `_schedule_execution(task.id, callback_url)` + RUNNING `TaskResultModel` with `forge_task_id`, no receipt). Polling endpoint already exists: `GET /tasks/{task_id}` (`tasks.py:428`, `get_task` — fine-grained status, DAG stage, ETA). Test: mirror `Forge/tests/unit/test_delegate_schedules_execution.py::test_delegate_without_execute_now_schedules_and_reports_running` with an `execute_now=True` envelope — assert scheduled + RUNNING + `forge_task_id` + no receipt.
- **Why the second battery re-run can go:** `run_task` already runs `_verify_and_repair` + `apply_final_verdict` (orchestrator.py:917–927); the inline path's re-run is redundant defense-in-depth (FRG-011's "re-settle from THIS run"). Dropping it loses the fresher re-settle, not verification itself.
- **Open design points for the code run (not decided here):**
  1. `require_sentinel` pre-delivery gate (delegate.py:559–600 — scan + settle-as-hard-failure) has no home on the background path; the flag lives in the envelope, not on the task. Decide: carry it on task metadata and run the scan in `_run_task_body` at completion, or document that Sentinel-gated callers must poll the settled verdict.
  2. Memora writeback on all-passed (:602–616) likewise has no background home — same decision.
  3. Completion receipt (`_forge_receipt`, :640–650) is issued only on the synchronous SUCCESS return; background completion notifies via webhook with state+error only (`_run_task_body`, tasks.py:120–155) and the settled verdict via `GET /tasks/{id}`. Whether the bus's receipt verification accepts that is part of the coordinator ruling owed on FRIDAY-bus polling adoption (cp1 follow-up, still owed — no ruling in WATCH253–256 / BE 09:10–10:16).
- **Supersedes cp1 §3 step 2:** "code lands in checkpoint 2" is corrected — code is designed here, lands next run. The `execute_now` branch is ~230 lines with three return shapes plus the Sentinel gate, and it is not rushed without a local test runner (pytest/fastapi absent in this VM — same constraint as the 01:17 run; the delegate tests run in CI on the work PR).
- **Not done this checkpoint:** no code written, no tests run. No server touched; no live leg. Live proof (now checkpoint 4) still gated on coordinator clearance for the Forge restart.

## Five states at checkpoint 2

- Implemented: NO — event-loop question settled + fix designed; code lands next run.
- Tested: NO.
- Merged: NO — no PR yet (work PR at completion with live evidence).
- Deployed: NO.
- Production-verified: NO — live proof is checkpoint 4, gated on coordinator clearance for the Forge restart.

— Muse 19

## Checkpoint 3 — async `execute_now` routing: code + tests — 2026-11-28 ~11:34 IST

**What changed (6 files, branch `muse19/task-frg-038`, main `42ba9151` merged first — merge `f5e99f65`):**

- `Forge/app/api/delegate.py` (sha `a3514480ecb818e87de7b7b5827a78db5e4b7220`): the `if execute_now:` inline block (lines 422–650 on main `42ba9151`, ~230 lines, three return shapes + Sentinel gate + Memora writeback) is deleted. `execute_now` now routes through `_schedule_execution` with the caller's post-completion flags and returns RUNNING + `forge_task_id` — the same shape as the default path. Removed with the block: `_task_provider_summary` (FRG-009 provider stamp — see consequence below), `_degraded_suffix`, `_dispatch_webhook_callback`, and the now-unused `asyncio` / `httpx` / `get_memora_client` imports + `TaskState` from the models import. `task_execute` (POST /v1/task/execute) is a thin adapter over `delegate_task`, so both entry points are fixed by this one change.
- `Forge/app/api/tasks.py` (sha `12436db8f920d644a1c411bc0e164a8b485cbfd1`): `_schedule_execution` / `_run_task_supervised` / `_run_task_body` take `require_sentinel: bool = False, memora_goal: str | None = None`. After `run_task`'s own verify+settle, when either flag is set, the body re-runs the battery (`verify_task` + `generate_manifest`), re-settles via `apply_final_verdict` (FRG-011, same derivation the inline path used), runs the Sentinel gate (only on settled COMPLETED; a block settles the named hard failure and the webhook reports `task_failed`), and does the Memora writeback (only when the manifest passed AND the settled state is COMPLETED). The default background path is unchanged — no second battery run when no flag is set. A duplicate submission reuses the live runner and its flags (documented in `_schedule_execution`).
- `Forge/app/core/orchestrator.py` (sha `df124e95856dac258751a6b8d85cfd88e5e7647e`): one-line docstring fix in `apply_final_verdict` — the caller of the second battery run is now the supervised background finalization, not the delegate execute_now path.
- Tests: `Forge/tests/unit/test_delegate_schedules_execution.py` (sha `57953b2d48587fb617de30d80e64ac801614a431`) +1 test (execute_now schedules + RUNNING + flags ride the runner, `run_task` not called on the request path); `Forge/tests/unit/test_delegate_mode_truthfulness.py` (sha `d5b630a98ac834862c8dcf2394f9bb2a81efa328`) — the two execute_now tests rewritten to the new contract (old synchronous SUCCESS/FAILED assertions removed; `_manifest` / `_patch_verification` helpers removed as unused); `Forge/tests/test_frg011_verdict_consistency.py` (sha `774fc453e6f28ff133eaa49af9f553c6edf6fb06`) — the settled-verdict test retargeted from the delegate response to `_run_task_body` with flags (R5 shape: FAILED + gate error + 11/11 green battery → COMPLETED, `build_verdict` SUCCESS, `task_completed` webhook, one Memora writeback).

**Design points settled this checkpoint (cp2 open points):**

- Sentinel gate + Memora writeback have a background home: `_run_task_body`'s flag-gated finalization (above). The flags ride the runner, not the task record.
- Gate/writeback run only on settled COMPLETED — the inline path returned before both on any other verdict, and this preserves that exactly.
- The FRG-011 re-settle is preserved: the background body re-runs the battery and re-settles when flagged, so the response/store/manifest stay one verdict.
- Receipt: no receipt is issued at intake (RUNNING response, no receipt — same as the default path since REL-011). Whether the completion receipt is issued on `GET /tasks/{id}/status` or only via webhook is still the coordinator ruling owed on FRIDAY-bus polling adoption — NOT invented here.

**Known consequence, stated not hidden:** the FRG-009 provider stamp (which provider generated the build, mock/degraded disclosure) no longer appears in any delegate response — it was computed only inside the deleted inline block. The stamps still exist on the task graph record. If a surface needs the disclosure post-completion, that is a follow-up, not part of this slice.

**Verification this run:** `python -m py_compile` passes on all six edited files (no pytest/fastapi in this VM — same constraint as cp2; the delegate tests run in CI on the work PR). Full diff read before commit: delegate.py 925 → 651 lines, tasks.py 949 → 1040 lines. No server touched; no live leg. Live proof (now checkpoint 4) still gated on coordinator clearance for the Forge restart.

## Five states at checkpoint 3

- Implemented: YES (routing + flags + tests).
- Tested: PARTIAL (py_compile only; CI pending on the work PR).
- Merged: NO — no PR yet (work PR at completion with live evidence).
- Deployed: NO.
- Production-verified: NO — live proof is checkpoint 4, gated on coordinator clearance for the Forge restart.

— Muse 19

## Checkpoint 3 repair — PR #2295 CI failures (2026-11-28 ~12:55 IST)

- Work PR #2295 opened this run (head `6c922f6b`, 7 files +348/-359, mergeable True).
- CI on the first head failed 2/12: `test` (ruff F821) + `contracts` (REL-068 guard).
- Root cause 1 (F821): cp3 removed `TaskState` from the `app.memory.models` import in `delegate.py`, but the status endpoint still uses it 6 times (lines 444–568) — a NameError at runtime for every status poll, not just a lint finding. Local undefined-name scan over all six changed files confirmed `TaskState` was the only undefined name. Fix: import restored (`TaskMode, TaskState`).
- Root cause 2 (REL-068): the three test files in this PR are named by NO PR-triggered workflow — the Forge contracts run in `owner-workflows.yml` lists sibling delegate tests but not `test_delegate_schedules_execution.py`, `test_delegate_mode_truthfulness.py`, or `test_frg011_verdict_consistency.py`. Fix: all three added to that Forge pytest invocation (same step, same PYTHONPATH).
- Live proof (checkpoint 4) still after merge: Forge restart clearance GRANTED (WATCH260 §D, standing ruling 7200564540). FRIDAY-bus polling-adoption ruling still owed.

— Muse 19

## Checkpoint 3 repair #2 — M14 NOT VERIFIED on PR #2295 (2026-11-28 ~13:25 IST)

- Paired verifier Muse 14, review 6096460517 (~12:50 IST, due ~13:40): NOT VERIFIED. CI on head `9cee728b` 9 success / 1 failure (`contracts`) / 2 skipped. WATCH262 §B confirms the failure is PR-caused, not the main workflow bug M13 root-caused on #2284 (REL-120 install gate; fixed on #2284, not yet on main).
- Defect 1 (reproduced first-hand by M14, confirmed first-hand this run): cp3 changed the `delegate_task` call to `_schedule_execution(task.id, callback_url, require_sentinel=..., memora_goal=...)` but two pre-existing tests still monkeypatch it with 2-arg lambdas — `test_delegate_verify_only_still_schedules_execution` and `test_delegate_without_execute_now_schedules_and_reports_running`. The TypeError is swallowed by the delegate error handler (`delegate.py:404`), so the task never schedules. Fix: both lambdas now accept `require_sentinel`/`memora_goal` (same shape as the cp3 `_capture` helper); the other three identical 2-arg patches of `_schedule_execution` in the truthfulness file got the same treatment (two latent `plan_only` delegate ones — plan_only never reaches the call — plus the `tasks_api`/`routes_api` ones, whose call sites pass positionally only).
- Defect 2 (latent): `test_frg009_provider_wiring.py::test_delegate_provider_summary_aggregation` imports the deleted `_degraded_suffix`/`_task_provider_summary`. No workflow runs it, but it is broken by this PR. Fix: test removed — the helpers are gone by design (FRG-009 stamp no longer in any delegate response; stamps remain on the task graph record).
- Scope checked: `tasks.py:410` / `routes.py:171,256` call `_schedule_execution` positionally with no kwargs, so those two patched lambdas never receive the new kwargs — they were updated anyway for uniformity with the new signature (harmless: extra defaulted params). No dangling references to the deleted helpers remain in `Forge/app/` (verified first-hand).
- Live proof (checkpoint 4) still after merge: Forge restart clearance GRANTED (WATCH260 §D, standing ruling 7200564540). M14 re-verifies on the fixed head (WATCH262 §B).

— Muse 19

## Checkpoint 3 repair #3 — REL-068 guard failure on the repaired head (2026-11-28 ~13:32 IST)

- CI on repair-#2 head `7c3a1542`: 10 success / 1 failure (`contracts`) / 2 skipped. `test` is now SUCCESS (the lambda fix works) — but `contracts` still fails, at a different step.
- Root cause (first-hand, job 140912665769): step 5 "Guard — every test file shipped in this PR is collected (TASK-REL-068)" fails; steps 6–17 skipped. Repair #2 modified `Forge/tests/test_frg009_provider_wiring.py`, but no PR-triggered workflow collects that file, so the diff-scoped guard (`scripts/ci_test_collection_audit.py`) fails before any test runs. On head `9cee728b` the guard passed — the file was not in the diff then.
- Fix: the file is added to the same Forge pytest list in `owner-workflows.yml` where repair #1 added the other three test files (same step, same PYTHONPATH). Its remaining 25 tests now run in CI; they were previously uncollected (M14 verified by grep that no workflow ran this file).
- Not the M13 workflow bug: the Stratex step (step 14) never ran on either head (skipped after the step-5 / step-8 failure); M13's install-gate fix merged on #2284 and is on main, but this PR's Forge-only diff does not trigger the Stratex step, so no rebase is owed for it.
- M14 re-verifies on the fixed head (WATCH262 §B).

— Muse 19
