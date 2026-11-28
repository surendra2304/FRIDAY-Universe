# TASK-FRG-024 — PRODUCTION-VERIFY Forge corpus items IG-FRG-01..06 — Evidence

**Checkpoint 1 — corpus grounded, live legs HELD on the wedged Forge service — 2026-11-28 ~05:50 IST**

- Task: TASK-FRG-024, PRODUCTION-VERIFY Forge corpus items IG-FRG-01..06 — live build-task verification, wave 3 (P2).
- Claim: hub #2045 comment 7230116668, 2026-11-28 04:55 IST (combined with the #2219 paired-verification post).
- Board: CLAIMED / owner muse_2 on live main (verified first-hand this run; branch/pr fields still null — the flip rides the work PR per owner rule 4).
- Branch: `muse2/task-frg-024-forge-production-verify` @ `81af5b8f` (verified first-hand via API this run; head is main at claim time, no work commits before this checkpoint).
- Usage: 71% of free weekly limit (verified fresh this run; resets Nov 28 21:47 IST).

## Corpus items — grounded on live main this run

Each item is an implemented Forge capability (earlier IG wave) with its repo test. Production-verify means one real build task per item through the deployed Forge, output actually used in production, including the failure case.

| Item | Capability | Implementation (main) | Repo test (main) |
|---|---|---|---|
| IG-FRG-01 | Review passes | `Forge/app/verification/review_passes.py` | `Forge/tests/test_ig_frg01_review_passes.py` |
| IG-FRG-02 | Skill registry | `Forge/app/agents/skill_registry.py` | `Forge/tests/test_ig_frg02_skill_registry.py` |
| IG-FRG-03 | Design import | `Forge/app/integrations/design_import.py` | `Forge/tests/test_ig_frg03_design_import.py` |
| IG-FRG-04 | Sketch-to-prompt | `Forge/app/planning/sketch_prompt.py` | `Forge/tests/test_ig_frg04_sketch_prompt.py` |
| IG-FRG-05 | Checkpoints | `Forge/app/execution/checkpoints.py` (+ `Forge/forge_upgrade/checkpoint.py`) | `Forge/tests/test_ig_frg05_checkpoints.py` |
| IG-FRG-06 | Plan-to-ship | `Forge/app/planning/plan_to_ship.py` | `Forge/tests/test_ig_frg06_plan_to_ship.py` |

Item definitions trace to `Forge/docs/IG_EVALUATION_NOTES.md` (TASK-IG-FRG-08): companion PRs in the same wave implement IG-FRG-01 (review passes), -02 (skill registry), -03 (design import), -04 (sketch-to-prompt), -05 (checkpoints), -06 (plan-to-ship).

## Live route — FRIDAY bus → Forge `/v1/task/execute`

Per the TP4 FRG-036 Leg B precedent (WATCH246 §C, decided): the FRIDAY bus → Forge `/v1/task/execute` route IS the "through FRIDAY" route for this task; Leg B counts as executed (04:11 IST).

## Live-leg gate — HELD, not stalled

- The Forge service is wedged since ~04:20 IST: Leg B FAILED as a **build failure, not a route failure** — sandbox missing `aiosqlite`; security FAIL; no manifest (WATCH246 §C; BE 05:35 §D).
- TP4 owns the fix: (1) fix the Forge sandbox deps (`aiosqlite`), (2) restart the Forge service under standing clearance 7200564540 and re-probe `/health`, (3) re-run Leg B and file the result. Deadline next run.
- Public FRIDAY route DOWN, 7th hour (M11 probe 05:13: duckdns https 000; direct EC2 13.211.78.20:8003 `/health` 503 — BE 05:35 §E). No restart/move (owner-frozen).
- Consequence for FRG-024: **no live build task can run until TP4's Forge fix + restart lands.** The live legs are HELD on that fix — this is a gate, not a Muse 2 stall. The repo leg (this checkpoint) proceeds; live legs start with a `/health` re-probe after TP4's fix.

## Five states (checkpoint 1)

- Implemented: YES (items merged in the earlier IG wave; this task verifies, it does not build).
- Tested: YES repo / NO live (repo tests listed above; live build-task proof owed per item).
- Merged: N/A (verify task; no code PR — the work PR opens when the live evidence is filed, per owner rule 1).
- Deployed: NO.
- Production-verified: NO — owed after TP4's Forge fix: one real build task per item through the deployed Forge with output actually used in production, including the failure case.

## Next

1. Re-probe Forge `/health` after TP4's sandbox-deps fix + service restart.
2. Run one live build task per item IG-FRG-01..06 through the FRIDAY bus → Forge `/v1/task/execute` route; record each output and whether it was actually used in production.
3. Include the failure case (a build that fails, and what Forge does with it).
4. File the live evidence here and open the work PR (with the board flip CLAIMED → IN_REVIEW) when the live legs are done or genuinely blocked.

— Muse 2
