# TASK-REL-098 — Fleet CD failed-deploy safety: recovery guard

Worker: Muse 9. Branch: `muse9/task-rel-098`, base main `ce5c1bd4`.
Assignment: coordinator watch 7131396444 (17:37 run, hub #1483). Claim: hub
#1483 comment 7131425206, 2026-11-24 ~17:56 IST. Queue: REL-098 -> INT-023
(final compilation due 2026-11-27) -> INT-041.

Task: verify the merged CD map (PR #1642) + add/verify a guard so a failed
deploy step never leaves an agent stopped. Staged proof only — no production
touch without coordinator clearance. No live deploy, restart, or server
touch was performed in this task.

## 1. CD map verification (PR #1642, merged `a3a0f212`)

Verified first-hand on main `ce5c1bd4`
(`.github/workflows/deploy-monorepo.yml`, 485 lines before this task):

- Paths filter (`detect-changes` job): `FRIDAY/**`, `Inference/**`,
  `Stratex/**` no longer trigger the Server 1 deploy; `Memora/**`,
  `Forge/**`, `Sentinel/**` (plus `mesh/**`, `deploy/**`, `scripts/**`,
  `tests/**`, `.github/workflows/**`) do. Server 2 filter unchanged
  (`VyralX`, `Cortex`, `IntelX`, `Futuris`).
- `SERVER1_AGENTS=("Memora" "Forge" "Sentinel")`; the health gate iterates
  the same list. `SERVER2_AGENTS=("VyralX" "Cortex" "IntelX" "Futuris")`.
- No `sudo systemctl restart FRIDAY-Voice.service`,
  `Stratex-Daemon.service`, `FRIDAY.service`, `Inference.service`, or
  `Stratex.service` anywhere in the Server 1 job. No `git reset --hard`.
- The map holds on main. PR #1642's fix is verified present, not just merged.

Finding (PR #1642 follow-up 2, closed by this task): `scripts/rollback_deploy.sh`
still carried the stale Server 1 map —
`SERVER1_SERVICES=(FRIDAY FRIDAY-Voice Inference Memora Stratex Forge
Sentinel Stratex-Daemon)`. Its LoadState gate cannot protect the moved
agents: a disabled unit still reports LoadState=`loaded`, so a rollback
affecting `FRIDAY/` would have restarted (revived) the sleeping S1 backup —
the exact defect #1642 fixed in the workflow. Fixed here:
`SERVER1_SERVICES=(Memora Forge Sentinel)`. `SERVER2_SERVICES` unchanged
(`VyralX Cortex IntelX Futuris VyralX-Daemon`).

## 2. The failure mode

Both deploy jobs run one inline script under `set -euo pipefail`. A failing
`systemctl restart` — or any later step (timer install, health gate, smoke
probe) — aborts the script before the health gate runs, and nothing ever
starts the agent again. PR #1642's body records the incident: "A failed S1
deploy run the same morning also left Memora stopped" (2026-11-24).

Live corroboration that the mode is current, not historical: Fleet CD run
45389036905 (2026-11-24 17:28 IST, head `8034ab1f`) concluded `failure`
with the Server 2 job failing at step "Update Changed Agents on Server 2"
(verified via the jobs API this run; Server 1 job `success`). A failure in
that step is exactly the shape that strands an agent.

## 3. The guard

One EXIT trap per deploy job, installed right after the job's agent map and
before the restart loop; the same pattern in `scripts/rollback_deploy.sh`
(installed after the affected set is computed, before the reset):

- The restart loops record every attempted restart in `RESTART_ATTEMPTED`
  (S1 loop, S2 loop, S2 `VyralX-Daemon` block) *before* the restart call.
- On failure (`$? != 0`) with a non-empty attempted set, the trap makes ONE
  bounded recovery attempt per attempted agent found inactive
  (`systemctl reset-failed` + `systemctl start`; `reset-failed` first
  because a crash-looped unit sits at its start limit and a bare `start`
  would fail). Then the script exits with the ORIGINAL failure code —
  recovery never masks the failure, and a failed recovery only logs a
  `::warning::` with the manual command.
- Scope is the attempted set only. Moved/sleeping units are never in
  `RESTART_ATTEMPTED`, so the guard can never revive them — even though
  their LoadState is `loaded`. The two workflow guard blocks are
  byte-identical (pinned by test).
- In the rollback script the guard iterates the run's affected set and is a
  no-op when the run fails before the reset (affected set empty) or
  succeeds (rc 0).

Files changed (5): `.github/workflows/deploy-monorepo.yml` (+50),
`scripts/rollback_deploy.sh` (+30/-1: map fix + guard),
`tests/test_fleet_cd_rel098_recovery_guard.py` (new, 12 tests),
`tests/test_rollback_deploy.py` (3 expectations updated to the post-move
map), `.github/workflows/owner-workflows.yml` (new test file added to the
contracts pytest list, standing order 5).

## 4. Staged proof (no production touch)

New tests execute the REAL job scripts and the REAL rollback script under
bash with fake `sudo` / `systemctl` / `curl` / `sleep` on PATH and disposable
git fixtures (the only line redirected is the deploy-host
`cd /opt/friday_universe`; this VM has no such checkout). Results, local
run 2026-11-24 ~18:10 IST:

- 12/12 new tests pass
  (`tests/test_fleet_cd_rel098_recovery_guard.py`): S1 restart failure ->
  `reset-failed` + `start Forge`, exit non-zero, no start attempted for
  FRIDAY/Inference/Stratex/FRIDAY-Voice/Stratex-Daemon; later-step failure
  (health gate) -> trap runs, finds Forge active, starts nothing; failure
  before any restart (dirty checkout) -> no recovery; success -> no
  recovery; recovery start itself failing -> warning logged, exit code
  still 1; S2 restart failure -> IntelX recovered, VyralX untouched; S2
  daemon restart failure -> VyralX-Daemon recovered; rollback restart
  failure -> Memora recovered, no `ROLLBACK DONE`; rollback success -> no
  recovery; rollback dry-run -> `would restart: Memora Forge Sentinel`
  with FRIDAY loaded on Server 1.
- Neighbours: `test_safe_fleet_deploy.py`,
  `test_fleet_cd_branch_guard.py`, `test_fleet_cd_s2_health_gate.py`,
  `test_fleet_cd_str044_timer_install.py`, `test_rollback_deploy.py` —
  59/59 pass together with the new file.
- `scripts/ci_test_collection_audit.py --base ce5c1bd4` (REL-068): PASS
  (new file collected via the contracts list and the `pytest -q tests`
  directory run).
- Workflow YAML parses; `bash -n` clean on the rollback script.

NOT proven (stated, not hidden): the guard has never run on a live host.
Staged proof shows the trap fires and recovers under fakes; a live failed
deploy is the only full proof, and staging one needs coordinator clearance
(owner stop order: all server moves frozen except key architecture, bridge,
and Inference work).

## 5. Follow-ups for the coordinator pool (not fixed here)

- Live proof of the guard on a real CD failure (or a controlled failure
  injection on a non-production host) — needs a Muse ruling on whether
  that is acceptable under the freeze.
- `rollback_deploy.sh`: a restart that succeeds but stays
  `UNHEALTHY(http-failed)` still prints `ROLLBACK DONE` with exit 0 —
  observed while working here, out of scope.
- PR #1642 follow-ups still open: (1) the STR-044 reconciliation timer
  still installs on Server 1, where it reads the sleeping Stratex copy —
  it should move to Stratex-Server with its owner; (3) FRIDAY/Inference/
  Stratex merges deploy nowhere automatically until an AWS deploy job
  exists.
- INT-023 final 7-day compilation still due 2026-11-27 (queue position 2).

## Status

- Implemented: yes (guard + map fix, 5 files).
- Tested: yes, locally, staged (12 new + 47 neighbour tests green,
  REL-068 audit PASS). Live legs not run.
- Merged: no — work PR open, awaiting Muse.
- Deployed: no — workflow/rollback changes take effect on merge; no live
  deploy performed.
- Production-verified: no — needs a live CD run; see §4.

— Muse 9
