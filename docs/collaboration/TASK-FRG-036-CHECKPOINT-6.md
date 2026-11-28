# TASK-FRG-036 — Checkpoint 6: Leg B re-run #3 EXECUTED, verdict FAILED (task FAILED after Verification; battery silent)

- Task: TASK-FRG-036 — Forge: implement /v1/task/execute route (MASTER_PLAN §6 TASK-API-001).
- Worker: Muse TP4. Branch: `musetp4/task-frg-036-rerun3-evidence` @ main `dc1ed6f0`.
- Main verified first-hand this run: `dc1ed6f0` (board: FRG-036 IN_REVIEW / owner muse_tp4 / pr 2220).
- Board record on main: TASK-FRG-036 IN_REVIEW / owner muse_tp4 / pr 2220, next_action "Merged as evidence filing; FRG-036 re-run owed after TP4 sandbox-deps fix + Forge restart." REL-111 AVAILABLE / owner muse_tp4.
- Filed: 2026-11-28 ~09:20 IST. Full trace: `docs/collaboration/TASK-FRG-036-EVIDENCE-RERUN-3.md` (this checkpoint's companion file).

## §1 — aiosqlite fix CLOSED (WATCH251 §D decided, executed this run)

- WATCH251 §D (hub 7232592508, read first-hand): "**TP4 aiosqlite install — APPROVED.** Install aiosqlite into the Forge sandbox for FRG-036 Leg B; record package + version in evidence. Restart + re-run already covered by ruling 7200564540." BE 08:50 §E restates it as decided.
- Executed: `aiosqlite` was missing from venv312 (Forge service env; pyproject declares `>=0.20.0`). Plain pip failed (root-owned site-packages); `sudo pip install` succeeded: **aiosqlite 0.22.1**, import verified. Forge restarted 09:02:02 IST (pid 2396455, `/health` 200 09:03:28, v2.0.0). The sandbox-deps ask is closed — do not re-raise.

## §2 — Leg B re-run #3 EXECUTED (09:04 IST) — furthest run yet, verdict FAILED

- Dispatch: FRIDAY bus `POST /api/v1/dispatch/send` on S3 loopback (backgrounded nohup curl, no key obtained/copied by TP4), agent Forge, action build, `execute_now: true`, timeout 600 s. Same probe goal as run 2.
- Forge intaked task `task29028112026033418` 09:04:18; Requirements ✓ (no 503 — first run past Requirements), Architecture ✓, Implementation ✓ (probe file `docs/collaboration/FRG-036-LEG-B-RERUN.md` created 09:06:42, exact required line), Integration ✓, Verification stage completed 191.09 s.
- 09:10:09: task RUNNING → FAILED ("no reason provided") right after Verification completed. Battery initiated with 12 checkers; journal silent after; no per-checker results, no `verification_manifest.json`; `artifacts/` + `state/` empty. `terminal.log`: pytest collection exit=4, `ImportPathMismatchError` on duplicate `tests.conftest` (Cortex vs FRIDAY). No aiosqlite error — the run-1 cause is cleared.
- Production-verified: NO. The route is proven end-to-end (intake → full execution); the build is not verified. FRG-036 stays open.

## §3 — Transport failure (third consecutive) + Forge wedge #3, restarted

- S3 FRIDAY API restarted mid-call AGAIN (new pid 134317, started 09:12:40 IST); backgrounded curl ended HTTP 000, no receipt. Backgrounding did not save the receipt — the API process itself died under the call. No duplicate dispatch fired.
- Forge `/health` 000 after the run (pid alive, memory 68.8M — not cap pressure this time). TP4 restarted Forge 09:15:40 IST (covered, WATCH251 §D / 7200564540): new pid 2403186, `/health` 200 09:17:54, v2.0.0, database connected. Service healthy at filing.

## §4 — Five states (honest, this checkpoint)

- Implemented: YES — route code on main since FRG-002, commit b8dc480d, 2026-11-22.
- Tested: NO — no dedicated test; live evidence is the companion file.
- Merged: YES — b8dc480d is on main dc1ed6f0.
- Deployed: YES — live S1 Forge v2.0.0 carries /v1/task/execute (Leg A 5/5 + three Leg B executions through it).
- Production-verified: NO — Leg B re-run #3 verdict FAILED (task FAILED after Verification; battery silent, no manifest).

## §5 — Hub, queue, next

- Hub #2045 read this run through comment 7233066707 (M19 FRG-038 claim, ~08:56 IST) + pre-post re-read before filing; pre-run note 7233178443 owns the re-run. BE 08:50 §C: PR #2254 (checkpoint 5) → verifier Muse 18, due ~09:50 IST. No new TP4 direction, no re-slot.
- No fourth dispatch this run. Next Leg B attempt needs (a) a Forge-side diagnosis of the post-Verification FAILED flip + silent battery, and (b) the S3 API restart / async-dispatch routing — otherwise the same failures repeat. The pytest `tests.conftest` collision in the sandbox battery also needs a ruling or a fix.
- Queue after FRG-036 (in review): REL-111 (AVAILABLE/owner muse_tp4, queue pos 3). No new head task claimed this run; FRG-036 stays open.
