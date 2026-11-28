# TASK-FRG-036 — Checkpoint 5: Leg B re-run EXECUTED, verdict FAILED (Requirements 503; S3 API restart; Forge re-wedged + restarted)

- Task: TASK-FRG-036 — Forge: implement /v1/task/execute route (MASTER_PLAN §6 TASK-API-001).
- Worker: Muse TP4. Branch: `musetp4/task-frg-036-rerun-evidence` @ main `9321b0d1` + this checkpoint + evidence doc.
- Main verified first-hand this run: `9321b0d1` (board blob `b1657b5d`).
- Board record on main: TASK-FRG-036 IN_REVIEW / owner muse_tp4 / pr 2220, next_action "Merged as evidence filing; FRG-036 re-run owed after TP4 sandbox-deps fix + Forge restart." REL-111 AVAILABLE / owner muse_tp4.
- Filed: 2026-11-28 ~08:15 IST. Full trace: `docs/collaboration/TASK-FRG-036-EVIDENCE-RERUN.md` (this checkpoint's companion file).

## §1 — Leg B re-run EXECUTED (08:03 IST) — the route works end-to-end

- Dispatch: FRIDAY bus `POST /api/v1/dispatch/send` on S3 loopback (no key obtained/copied by TP4), agent Forge, action build, `execute_now: true`, timeout 600 s. Goal: create `docs/collaboration/FRG-036-LEG-B-RERUN.md` with one line of text, in a sandbox clone of the public repo.
- Forge received it 08:03:19 IST (`[FORGE_DELEGATE] Received action 'build' from 'FRIDAY'`), task `task28928112026023320`, cloned the repo, planned an 8-stage DAG, PENDING → READY → RUNNING, Requirements stage started 08:03:41.
- Authorization: BE 07:35 §D (restart + re-run covered under standing clearance 7200564540 — "run them now"). Pre-run hub note posted #2045 comment 7232437971 (owns the re-run, no duplicate dispatch).

## §2 — Verdict: FAILED — upstream 503 in Requirements, before any build work

- 08:04:55 IST: upstream HTTP 503 (rate-limit headers) → node.failed → RUNNING → FAILED, 96 s in. Verification battery ran (12 checkers); security check FAIL (exit=1) 08:10:22; journal silent after.
- The probe file was NEVER created; workspace `artifacts/` / `logs/` / `state/` empty — no manifest, no terminal log. The run-1 `aiosqlite` cause was not reached; the sandbox-deps question is still open.
- Production-verified: NO. The route is proven end-to-end (intake → execution start); the build is not verified. FRG-036 stays open.

## §3 — Transport failure (second consecutive) + Forge wedge #2, restarted

- The bus call never returned (curl HTTP 000, 08:11:21 IST): the S3 FRIDAY API restarted mid-call AGAIN (old process died ~02:41 UTC; new pid 132376 up 02:41 UTC, healthy). No duplicate dispatch fired; bus receipts died with the old process. Same loss as run 1 (04:20).
- Forge `/health` 000 after the run (pid alive, memory 177.4M/180M cap). TP4 restarted Forge 08:13:15 IST (covered, WATCH248 §D / BE 07:35 §D): new pid 2370661, startup complete 08:13:32, `/health` 200. Forge had also been restarted 07:54:39 IST by an unestablished actor (stop timed out, SIGKILL) — that restart enabled this re-run.
- Inference gateway :8001 `/health` 200 after the run — the 503 was transient/upstream, not a dead gateway.

## §4 — Five states (honest, this checkpoint)

- Implemented: YES — route code on main since FRG-002, commit b8dc480d, 2026-11-22.
- Tested: NO — no dedicated test; live evidence is the companion file.
- Merged: YES — b8dc480d is on main 9321b0d1.
- Deployed: YES — live S1 Forge v2.0.0 carries /v1/task/execute (Leg A 5/5 + two Leg B executions through it).
- Production-verified: NO — Leg B re-run verdict FAILED (Requirements 503).

## §5 — Hub, queue, next

- Hub #2045 read this run through comment 7232347389 (1006 comments) + pre-run note 7232437971: BE 07:35 §D (run the restart + re-run now) and WATCH250 (07:40, silent on the sandbox fix) read in full; all other new comments swept for TP4/FRG-036/REL-111/Leg B — no new TP4 direction, no verifier assignment, no re-slot.
- No third dispatch this run. Next Leg B attempt needs (a) the sandbox-deps fix ruling, and (b) a transport that survives the S3 API restart (async + polling, or a stable API process) — otherwise the same transport loss repeats.
- Queue after FRG-036 (in review): REL-111 (AVAILABLE/owner muse_tp4, queue pos 3). No new head task claimed this run; FRG-036 stays open.
