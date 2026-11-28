# TASK-FRG-036 — Evidence: Leg B re-run (route works; FAILED earlier than run 1)

- Task: TASK-FRG-036 — Forge: implement /v1/task/execute route (MASTER_PLAN §6 TASK-API-001).
- Worker: Muse TP4. Branch: `musetp4/task-frg-036-rerun-evidence`.
- Filed: 2026-11-28 ~08:15 IST. Leg B re-run executed 08:03 IST per BE 07:35 §D (restart + re-run covered under standing clearance 7200564540). Evidence gathered first-hand from the S3 FRIDAY API, the S1 Forge journal + task workspace. No key was obtained, copied, or recorded by TP4 at any step.

## §1 — Dispatch (FRIDAY bus → Forge /v1/task/execute)

- 08:03:19 IST (02:33:19Z), from Oracle Server 3 (FRIDAY-Server) loopback:
  `POST http://127.0.0.1:10000/api/v1/dispatch/send?agent=Forge&action=build&priority=100&timeout_sec=600`
  with the payload as the JSON body:
  `{"goal":"Create a new file docs/collaboration/FRG-036-LEG-B-RERUN.md in the FRIDAY-Universe repository containing exactly one line of text: FRG-036 Leg B re-run probe.","requirements":["Create only that one file; change nothing else","No network calls, no secrets, no live services, no destructive action"],"mode":"autonomous","repo_url":"https://github.com/surendra2304/FRIDAY-Universe","execute_now":true}`
- The bus call never returned: curl HTTP 000 after 482.3 s; no response file written. Same transport failure as run 1 (04:20) — see §4.

## §2 — Forge intake + execution (journal, S1)

- 08:03:19 IST: `[FORGE_DELEGATE] Received action 'build' from 'FRIDAY'`. Task `task28928112026023320` intaked; goal = the re-run goal verbatim; cloned `https://github.com/surendra2304/FRIDAY-Universe` into `/opt/friday_universe/Forge/workspaces/task28928112026023320/project` (clone complete 08:03:41); 8-stage DAG planned; PENDING → READY → RUNNING; Requirements stage started 08:03:41.
- 08:04:55 IST: an upstream call returned HTTP 503 Service Unavailable (server uvicorn; `x-ratelimit-limit: 600`, `x-ratelimit-remaining: 599`) → `[node.failed]` → task RUNNING → FAILED ("no reason provided"), 96 s after intake.
- 08:04:56 IST: verification battery initiated with 12 checkers. AST parsing failed for dependency extraction (U+FEFF BOM) at 08:09:17, 08:09:49, 08:10:06. 08:10:22 IST: Check [security] 'Security & Vulnerability Analysis': FAIL (exit=1). Journal silent after 08:10:22.

## §3 — Build output (sandbox): probe file NEVER created

- `docs/collaboration/FRG-036-LEG-B-RERUN.md` does NOT exist in the sandbox project — the task died in Requirements, before any implementation stage ran. (Run 1 at least created its probe file.)
- Workspace `artifacts/`, `logs/`, `state/` all empty: no `verification_manifest.json`, no `terminal.log`. The run-1 failure cause (sandbox missing `aiosqlite`) was NOT reached this run and remains untested — the sandbox-deps question is still open, not resolved by this re-run.
- Per Forge's own rules (TASK-REL-019), SUCCESS requires the task completed AND the final battery passed — neither holds. Leg B re-run verdict: FAILED.

## §4 — Transport failure (response never reached TP4; S3 API restarted mid-call AGAIN)

- The S3 FRIDAY API restarted during the dispatch: old uvicorn process died ~02:41 UTC; new pid 132376 started 02:41 UTC and answers `/health` 200. The curl ended 02:41:21 UTC with HTTP 000. Second consecutive Leg B dispatch lost the same way (run 1: restart ~04:20:31 IST, old pid 121959 → new pid 123833). Restarting actor unknown both times; no OOM-kill lines seen.
- No duplicate dispatch was fired. The bus's in-memory receipts died with the old process, so no bus receipt survives; the evidence here comes from Forge's journal + workspace, read first-hand.

## §5 — Forge HTTP wedged a second time; restarted by TP4

- After the run, Forge `/health` (:8006) returned HTTP 000 while the process stayed alive (pid 2360779, started 07:54:39 IST) with memory 177.4M of the 180M cgroup max (2.5M available) — the single worker (`--workers 1`) wedged again after a long sync `execute_now` call, same as run 1.
- TP4 restarted Forge 08:13:15 IST (`systemctl restart Forge.service`, covered by WATCH248 §D / BE 07:35 §D): new pid 2370661, application startup complete 08:13:32, `/health` 200, Forge v2.0.0, memory 156.4M. Service healthy at filing.
- Note: Forge had ALREADY been restarted once this morning at 07:54:39 IST (stop timed out, SIGKILL of wedged pid 2184784, clean start pid 2360779, NRestarts=0); the actor is unestablished from the journal (no login recorded). That restart is what made the re-run possible.

## §6 — Inference gateway healthy now

- Inference gateway (S1 :8001) `/health` 200 at ~08:13 IST (providers include groq, cer…), so the 08:04:55 503 was transient / upstream-side, not a dead gateway. The 503's rate-limit headers point at the LLM-provider path behind the gateway.

## §7 — Five states (honest, this checkpoint)

- Implemented: YES — route code on main since FRG-002 (b8dc480d).
- Tested: NO — no dedicated test; live evidence is this file + the run-1 evidence doc.
- Merged: YES — b8dc480d on main.
- Deployed: YES — live S1 Forge v2.0.0 carries /v1/task/execute; Leg A 5/5 + two Leg B executions through it.
- Production-verified: NO — Leg B re-run FAILED in Requirements (upstream 503), before the sandbox battery; the route is proven end-to-end (intake → execution start); the build is not verified.

## §8 — Next (coordinator rulings owed)

1. Sandbox-deps fix (`aiosqlite` in the Forge sandbox) ruling STILL owed — this re-run did not reach the battery, so it neither confirms nor clears the run-1 cause. No third dispatch fired this run.
2. S3 FRIDAY API restarts mid-call on BOTH Leg B dispatches (04:20, 08:11): a synchronous 600 s `execute_now` dispatch cannot return a receipt while the API restarts underneath it. Needs owner/coordinator routing — async dispatch + polling, or a stable API process — before another re-run, or the same transport loss repeats.
3. Forge single-worker wedge after every long build (twice now) + memory near the 180M cap: restart restores it within a minute, but the wedge recurs per build. Service-side defect for the coordinator/owner to route.
4. The bus-path vs "through FRIDAY chat" acceptance question (evidence doc §1/§9) is still unruled.
