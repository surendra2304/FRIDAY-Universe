# TASK-FRG-036 — Evidence: Leg B end-to-end live run (route works; verification FAILED)

- Task: TASK-FRG-036 — Forge: implement /v1/task/execute route (MASTER_PLAN §6 TASK-API-001).
- Worker: Muse TP4. Branch: `musetp4/task-frg-036-task-execute-route`.
- Filed: 2026-11-28 ~04:50 IST. Leg B executed 04:11 IST; evidence gathered first-hand from the S1 Forge journal + task workspace and the S3 FRIDAY API. No key was obtained, copied, or recorded by TP4 at any step.

## §1 — Dispatch (FRIDAY bus → Forge /v1/task/execute)

- 04:11:11 IST (22:41:11Z), from Oracle Server 3 (FRIDAY-Server) loopback:
  `POST http://127.0.0.1:10000/api/v1/dispatch/send?agent=Forge&action=build&priority=100&timeout_sec=600`
  with the payload as the JSON body:
  `{"goal":"Create a new file docs/collaboration/FRG-036-LEG-B-PROBE.md in the FRIDAY-Universe repository containing exactly one line of text: FRG-036 Leg B end-to-end probe.","requirements":["Create only that one file; change nothing else","No network calls, no secrets, no live services, no destructive action"],"mode":"autonomous","repo_url":"https://github.com/surendra2304/FRIDAY-Universe","execute_now":true}`
- The bus (`UniverseDispatchBus`, FRIDAY/apps/core) maps agent Forge → `http://10.0.0.121:8006`, action_path `/v1/task/execute`, and posts the envelope `{task_id: disp_…, agent: Forge, action: build, payload, priority: "100", timeout_sec: 600, source_agent: "FRIDAY"}`. Forge accepted the POST (intake logged 04:11:14, §2), so the bus presented a valid key loaded server-side from the FRIDAY service env.
- Authorization: WATCH241 §C ruling (TP4 runs Leg B itself under standing clearance 7200564540), re-fetched first-hand this run with no safety notice; adopted by BE 02:38.
- Chat-path note: the FRIDAY chat fast-path "ask forge" is status-only (`fleet_client.ask_forge` GETs `/api/v1/analytics/summary` + `/api/v1/tasks`; no execution), and `dispatch_directive` routes code keywords to that same status path — the chat surface has no execution route to Forge's new endpoint. The end-to-end proof therefore ran through the FRIDAY dispatch bus (the same bus the chat layer feeds, `source_agent=FRIDAY`), not a chat message. Whether that satisfies the "through FRIDAY chat" wording is a coordinator ruling (see §9).

## §2 — Forge intake + execution (journal, S1)

- 04:11:14 IST: `[FORGE_DELEGATE] Received action 'build' from 'FRIDAY'`. Task `task28827112026224114` intaked; goal = the Leg B goal verbatim; cloned `https://github.com/surendra2304/FRIDAY-Universe` into `/opt/friday_universe/Forge/workspaces/task28827112026224114/project`; 8-stage DAG planned; PENDING → READY → RUNNING.
- Stages (journal): Requirements 45.21s (04:11:37–04:12:22); Integration 8.82s (completed 04:13:30); Verification 169.76s (started 04:13:30, completed 04:16:20).
- 04:16:23 IST: task RUNNING → FAILED (no reason in the journal line); `node.failed` audit event; verification battery initiated with 12 checkers.
- 04:19:10 / 04:20:00: AST parsing failed for dependency extraction (U+FEFF BOM).
- 04:20:19: Check [security] 'Security & Vulnerability Analysis': FAIL (exit=1). Journal silent after 04:20:19 (nothing further to 04:36 IST).

## §3 — Build output (sandbox)

- The requested file EXISTS in the sandbox with the exact content: `/opt/friday_universe/Forge/workspaces/task28827112026224114/project/docs/collaboration/FRG-036-LEG-B-PROBE.md`, 30 B, created 04:13 IST, content `FRG-036 Leg B end-to-end probe` (no trailing newline).
- Sandbox git status (untracked): `docs/ARCHITECTURE_SPEC.md`, `docs/FILE_MANIFEST.json`, `docs/PROJECT_CONTEXT_SUMMARY.md`, `docs/collaboration/FRG-036-LEG-B-PROBE.md`, `forge_probe/` — Forge also generated 3 analysis docs + `forge_probe/`; the "only that one file" requirement was not honored (normal Forge working artifacts, recorded honestly).

## §4 — Verdict: FAILED (cause: sandbox missing dependency)

- Verification battery failure cause (workspace `logs/terminal.log`): `ImportError while loading conftest '.../Cortex/tests/conftest.py'. ModuleNotFoundError: No module named 'aiosqlite'` — the battery collects the repo's test suite inside the sandbox, and the sandbox lacks the `aiosqlite` module. The task failed for an ENVIRONMENT reason, not because the one-line file was wrong.
- No `verification_manifest.json` was written (workspace `artifacts/` empty; `state/` empty). No `execute_now` response was ever returned. Per Forge's own rules (TASK-REL-019), SUCCESS requires the task completed AND the final battery passed — neither holds. Leg B verdict: FAILED. The route works; the build's verification does not pass in Forge's sandbox.

## §5 — Transport failure (response never reached TP4)

- The bus call never returned: curl to the FRIDAY API got HTTP 000 at 04:20:31 IST after ~9m20s. Cause: the FRIDAY API server (S3 :10000) restarted mid-call — old uvicorn pid 121959 (started 22:19) died ~04:20:31 IST; new pid 123833 started 04:20:36 IST and answers `/health` + `/dispatch/agents`. Restarting actor unknown; dmesg shows no OOM-kill lines. S3 uptime 3d 18h, load 0.13.
- No duplicate dispatch was fired. The bus's in-memory receipts died with the old process, so no bus receipt survives; the evidence here comes from Forge's journal + workspace, read first-hand.

## §6 — Forge HTTP layer wedged

- `/health` on S1 Forge (:8006) returns HTTP 000 (10 s timeouts) at 04:22, 04:23 and ~04:36 IST, via both `10.0.0.121` and `127.0.0.1`, while the port is LISTENING (`ss`) and the process is alive (pid 2184784, started 02:18 IST, NRestarts=0, 6.7% CPU, 7 threads, journal silent since 04:20:19). The single worker (`--workers 1`) appears blocked by the long sync `execute_now` call / wedged in the battery — new HTTP requests hang while the task is in flight and after it fails. Forge also restarted 02:18 IST (clean stop/start, NRestarts=0, actor unknown) — second restart in ~4h (previous 22:30 IST Nov 27, cp3 §3).
- Consequence: live health/status reads of Forge are unavailable until the service is restarted or unwedges. Restart is a service change — TP4 does not restart it; coordinator/owner call.

## §7 — Other findings

- Forge→Memora writebacks 401: `POST http://127.0.0.1:8002/v1/memories/record-interaction` and `/v1/capture/events` returned 401 Unauthorized at 04:13:30 IST (Memora key missing/wrong on the Forge side). Non-fatal per code; the verified-build Memora writeback is broken.
- S2 FRIDAY :10000 still down per BE 03:42 §E (TP6 flag); the live FRIDAY API is the S3 copy (:10000, healthy after its 04:20 restart).

## §8 — Five states (honest, this checkpoint)

- Implemented: YES — route code on main since FRG-002 (b8dc480d).
- Tested: NO — no dedicated test; live evidence is this file.
- Merged: YES — b8dc480d on main.
- Deployed: YES — live S1 Forge v2.0.0 carries /v1/task/execute; Leg A 5/5 + Leg B executed through it.
- Production-verified: NO — Leg B ran end-to-end through the route but Forge's verdict is FAILED (sandbox missing aiosqlite; security check FAIL; no manifest). The route is proven; the build is not verified.

## §9 — Next (coordinator rulings owed)

1. Rule whether the bus-path proof satisfies acceptance criterion 2 ("requested through FRIDAY chat") or a chat execution route to Forge is owed as follow-up work (the chat fast-path is status-only by code).
2. Forge sandbox dependencies (`aiosqlite` missing) + Forge HTTP wedging + Forge→Memora 401s are service-side defects for the coordinator/owner to route (not TP4's task to fix unasked).
3. FRG-036 stays open (Leg B FAILED, not production-verified). A re-run after the sandbox-deps fix is the next Leg B step; no re-run fired this run (Forge wedged; no duplicate dispatch).
