# TASK-FRG-036 — Evidence: Leg B re-run #3 (aiosqlite fixed, furthest run yet; verdict FAILED)

- Task: TASK-FRG-036 — Forge: implement /v1/task/execute route (MASTER_PLAN §6 TASK-API-001).
- Worker: Muse TP4. Branch: `musetp4/task-frg-036-rerun3-evidence` @ main `dc1ed6f0`.
- Filed: 2026-11-28 ~09:20 IST. Leg B re-run #3 executed 09:04 IST per WATCH251 §D (aiosqlite install APPROVED, hub 7232592508) + standing clearance 7200564540 (restart + re-run). Pre-run hub note #2045 comment 7233178443.
- Evidence gathered first-hand from the S1 Forge journal + task workspace, the S3 FRIDAY API process, and venv312. No key was obtained, copied, or recorded by TP4 at any step.

## §1 — aiosqlite install: the run-1 cause is fixed

- Before: `aiosqlite` NOT importable in `/opt/friday_universe/venv312` (the Forge service env): `ModuleNotFoundError`, `pip show aiosqlite` = not found. Forge's own `pyproject.toml:53` declares `"aiosqlite>=0.20.0"` — a declared dependency missing from the live env.
- First install failed: venv312 + site-packages are root-owned (`drwxr-xr-x root root`); the bridge runs as `ubuntu`, so plain `pip install` died with `Permission denied: .../site-packages/aiosqlite`.
- Fix: `sudo /opt/friday_universe/venv312/bin/pip install 'aiosqlite>=0.20.0'` → `Successfully installed aiosqlite-0.22.1`. Import verified in the service env: `aiosqlite OK 0.22.1`, location `/opt/friday_universe/venv312/lib/python3.12/site-packages`.
- Forge restarted 09:02:02 IST (covered, WATCH251 §D / 7200564540): new pid 2396455, startup complete 09:02:51, `/health` 200 at 09:03:28 (Forge v2.0.0, database connected). Slow start (~86 s to first 200) — the two 000 probes before that were startup, not a wedge.

## §2 — Dispatch (FRIDAY bus → Forge /v1/task/execute)

- 09:04:16 IST, from Oracle Server 3 (FRIDAY-Server) loopback, FRIDAY API healthy (200) before dispatch:
  `POST http://127.0.0.1:10000/api/v1/dispatch/send?agent=Forge&action=build&priority=100&timeout_sec=600`
  with the payload as the JSON body:
  `{"goal":"Create a new file docs/collaboration/FRG-036-LEG-B-RERUN.md in the FRIDAY-Universe repository containing exactly one line of text: FRG-036 Leg B re-run probe.","requirements":["Create only that one file; change nothing else","No network calls, no secrets, no live services, no destructive action"],"mode":"autonomous","repo_url":"https://github.com/surendra2304/FRIDAY-Universe","execute_now":true}`
- Transport change vs runs 1–2: the curl ran backgrounded (`nohup`, bg pid 134273, output to `/tmp/frg036_rerun3_curl.log`) so the dispatch survives an S3 API restart. Same probe goal as run 2 (the run-2 file was never created).

## §3 — Execution: furthest run yet — all stages ran, probe file created

- 09:04:18 IST: Forge intaked task `task29028112026033418`; cloned `https://github.com/surendra2304/FRIDAY-Universe` into `/opt/friday_universe/Forge/workspaces/task29028112026033418/project` (complete 09:04:42); 8-stage DAG planned; PENDING → READY → RUNNING.
- Requirements: completed 46.68 s + 10.87 s (two nodes) — **no upstream 503 this time**; run 2 died here at 96 s. Architecture: completed 44.45 s. Implementation: completed 16.18 s — the probe file `docs/collaboration/FRG-036-LEG-B-RERUN.md` was created 09:06:42 with exactly the required line (`FRG-036 Leg B re-run probe`). Integration: completed 13.17 s (file re-applied 09:06:55). Verification stage: completed 191.09 s (09:06:56 → 09:10:07).
- 09:10:09 IST: task transitioned RUNNING → FAILED ("no reason provided") immediately after the Verification stage completed. Verification battery initiated with 12 checkers at 09:10:09; **journal silent after that** — no per-checker PASS/FAIL lines, no battery verdict.
- Build output (sandbox): probe file EXISTS with the exact required content. Workspace `artifacts/` empty, `state/` empty, `logs/` holds only `terminal.log` (16 lines). **No `verification_manifest.json` produced.** The run-1 cause (sandbox missing `aiosqlite`) was NOT the failure here: no `aiosqlite` / `ModuleNotFoundError` line appears in `terminal.log`.
- `terminal.log` shows the Verification-stage pytest run failed at collection: exit=4, `ImportError while loading conftest ... ImportPathMismatchError: ('tests.conftest', '.../project/Cortex/tests/conftest.py', '.../project/FRIDAY/tests/conftest.py')` — duplicate `tests.conftest` module names across subprojects in the monorepo clone. (Also a non-fatal cortex sqlite error: `no such table: agent_budget_state`, falling back to the in-process mirror.)
- Per Forge's own rules (TASK-REL-019), SUCCESS requires the task completed AND the final battery passed — neither holds. Leg B re-run #3 verdict: **FAILED**.

## §4 — Transport failure (third consecutive receipt loss; S3 API restarted mid-call AGAIN)

- The backgrounded curl ended 09:12 with HTTP 000; no response file was written. The S3 FRIDAY API restarted during the dispatch: old uvicorn process died ~09:12, new pid 134317 started 09:12:40 IST (`/opt/friday_universe/venv/bin/python -m uvicorn friday.api.server:app --host 0.0.0.0 --port 10000 --workers 1`), healthy (200) now. Third consecutive Leg B dispatch lost the same way (run 1 ~04:20, run 2 ~08:11, run 3 ~09:12).
- Backgrounding the curl did not save the receipt — the API process itself died under the call. No duplicate dispatch was fired. Evidence here comes from the Forge journal + workspace, read first-hand, as in runs 1–2.

## §5 — Forge HTTP wedged a third time; restarted by TP4

- After the run, Forge `/health` (:8006) returned HTTP 000 while the process stayed alive (pid 2396455) — the single worker (`--workers 1`) wedged again after a long sync `execute_now` call, same as runs 1–2. Memory was NOT at cap this time (68.8M/180M at 09:14), so the wedge is not purely memory pressure.
- TP4 restarted Forge 09:15:40 IST (covered by WATCH251 §D / 7200564540): new pid 2403186, `/health` 200 at 09:17:54, Forge v2.0.0, database connected. Memory 175.3M/180M after restart (4.6M available) — the service runs at its cap at steady state.

## §6 — Five states (honest, this checkpoint)

- Implemented: YES — route code on main since FRG-002 (b8dc480d).
- Tested: NO — no dedicated test; live evidence is this file + the run-1/run-2 evidence docs.
- Merged: YES — b8dc480d is on main dc1ed6f0.
- Deployed: YES — live S1 Forge v2.0.0 carries /v1/task/execute; Leg A 5/5 + three Leg B executions through it.
- Production-verified: NO — Leg B re-run #3 FAILED (task FAILED after Verification; battery produced no manifest).

## §7 — Next (what is owed now)

1. The aiosqlite ask is CLOSED (installed 0.22.1, verified) — WATCH251 §D decided it; do not re-raise.
2. Task FAILED with "no reason provided" right after Verification completed, and the 12-checker battery then went silent with no manifest — needs a Forge-side diagnosis (why the Verification-stage completion flips the task to FAILED; why the battery emits no checker results). This is the new blocker for a Leg B pass.
3. The sandbox battery's pytest collection trips on duplicate `tests.conftest` across monorepo subprojects (exit=4) — the battery cannot pass a whole-repo collection as configured.
4. S3 FRIDAY API restarts on EVERY long dispatch (3/3) — async dispatch + polling, or a stable API process, is still needed before another re-run, or the receipt loss repeats.
5. Forge single-worker wedge after every long build (3rd time) + memory at the 180M cap — service-side defect for the coordinator/owner to route; restart restores it within minutes.
6. The bus-path vs "through FRIDAY chat" acceptance question (evidence doc §1/§9) is still unruled.
