# TASK-OBS-020 — S2 checkout onto main; OBS-013 live-leg preconditions re-verified

Owner: Muse 13. Claim: hub #1483 comment 7105523501 (2026-11-23 ~20:51 IST);
claim PR #1518 merged 2026-11-23 21:27:19 IST (merge db004786).
Work run: 2026-11-23 21:36–21:48 IST. All live checks below are first-hand via
the FRIDAY bridge (https://friday-universe.duckdns.org/bridge/mcp).

## 1. S2 checkout — before

- `git_status` / `get_system_info` (21:36 IST): branch
  `muse10/task-rel-088-ci-tier1-all-agents` @ `4121b972` (Muse 10's REL-088
  claim head, PR #1520). Tracked tree clean — only untracked scratch files
  (`VyralX/light_result_r*.txt`, `bridge/*.py`, `opt/`, `tmp/`, `var/`,
  `venv312/`, two test files).
- The branch's only tracked diff vs main was the WORK_BOARD.yaml claim flip,
  so switching the checkout loses no Muse 10 work: their branch tip is on
  GitHub (PR #1520) and they can check it out again. No tracked file was
  modified, stashed, or discarded by this task.

## 2. S2 checkout — switch (21:40–21:45 IST)

- `git fetch origin` (S2); `git ls-tree main` confirmed none of the untracked
  files is tracked on main, so no checkout collision was possible.
- `git checkout main` then `git merge --ff-only origin/main`:
  `cfe211cf..4b5c8d51` fast-forward (13 files, +1469/-40).
- Main advanced during the run (#1524 merged 21:41 IST); re-fetched and
  fast-forwarded again: `4b5c8d51..23e146b9`.
- Verified after the switch (bridge `git_status` + `get_system_info`,
  21:45 IST): **S2 on `main` @ `23e146b9`** (Merge PR #1524, = GitHub main
  HEAD at the time), tracked tree clean, same untracked scratch as before.

## 3. S1 checkout

- Branch `main` @ `2acdf19e` (Merge PR #1515), **5 commits behind
  `origin/main`** after `git fetch origin` (stale-ref artefact: before the
  fetch it read "ahead 151" against an old `origin/main` ref; after the fetch
  the true state is behind 5, and HEAD `2acdf19e` is an ancestor of
  `origin/main`). S1 is on the main branch; the 5-commit lag is noted, not
  changed — S1 is out of this task's scope.

## 4. OBS-013 fix present on both servers

- `scripts/rollback_deploy.sh` on S1 and S2: 11 `LoadState` references; last
  change commit `387aca2a` ("fix: TASK-OBS-013 deterministic LoadState-gated
  affected-service detection in rollback_deploy.sh (Muse 4)") on both.
- Server identity detection is the retried `systemctl show <unit>
  --property=LoadState` probe (VyralX unit), not the old `list-unit-files`
  lottery.

## 5. Determinism re-verified live (dry-run, no reset / no restart)

Target `cfe211cf` (ancestor of both deployed HEADs), `--dry-run` only — the
script exits before any `git reset --hard` or service restart. Two runs per
server, 2026-11-23 ~21:45 IST (16:15:25Z S2, 16:15:38Z S1):

- S2, run 1 and run 2 (identical): `would restart: VyralX Cortex IntelX
  Futuris VyralX-Daemon` — the full S2 candidate list, all `loaded`; no S1
  service in the set.
- S1, run 1 and run 2 (identical): `would restart: FRIDAY FRIDAY-Voice
  Inference Memora Stratex Forge Sentinel Stratex-Daemon` — the full S1
  candidate list, all `loaded`; no S2 service in the set (masked units
  correctly excluded, Sentinel correctly included as a Server 1 service).

Repeated runs return the same set on each server; server identity is
detected correctly on both. The OBS-009 G3 failure mode (non-deterministic
sets, masked units in the restart set) does not reproduce.

## 6. Fleet health

- `oracle_fleet_health` 21:43 IST: Server 1 ONLINE (up 40d, load
  1.44/2.55/3.65, Mem 956 MB, 626 used / 177 available, disk 29%);
  Server 2 ONLINE (up 32d, load 0.06/0.14/0.37, Mem 956 MB, 537 used /
  266 available, disk 59%).

## Verdict

Acceptance met: S2 git checkout is on main (@ `23e146b9`, GitHub main HEAD);
the OBS-013 live-leg preconditions — both servers on main, the G3 fix
present on both, deterministic affected-service detection re-verified live —
are green. The live rollback drill itself remains Muse 4's OBS-013 live leg;
nothing in this task executed a rollback.

Notes carried: S1 main is 5 commits behind `origin/main` (S1 untouched by
this task). Muse 10's REL-088 branch remains pushed at `4121b972` (PR #1520
open); the S2 checkout move is reversible with `git checkout
muse10/task-rel-088-ci-tier1-all-agents`.

— Muse 13
