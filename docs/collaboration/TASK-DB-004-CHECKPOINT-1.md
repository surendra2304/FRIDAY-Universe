# TASK-DB-004 — Checkpoint 1: repo-side scoping (2026-11-25 ~15:15 IST)

- **Task:** DB: Back up Stratex live state files on Stratex-Server (S4) — newest state backup 2026-11-14.
- **Claim:** hub #1483 comment 7157386858 (2026-11-25 ~14:15 IST). Branch `muse6/task-db-004-stratex-state-backup` from main `a8beedde` (verified by read-back; this commit is the first on the branch). Board flip AVAILABLE → CLAIMED rides in the work PR per rule 4. No PR yet — one work PR when DONE/BLOCKED, rule 1.
- **Board record verified first-hand this run** on main `c554c54f` (via API; script/workflow reads below are from origin/main `ec46d5f`): TASK-DB-004, P2, AVAILABLE / owner null / branch null / pr null. Acceptance: back up the live Stratex state files on Stratex-Server (server 4) — `Stratex/state/*.jsonl` + `*.json` (fill ledger, equity snapshots, forward scorecard, position tags, reconciliation). Newest state backup 2026-11-14; the Nov 22 fleet backup holds only the 4 empty ADB tables. Prove with a dated backup + a restore/read-back check. Do not change the live daemon. Evidence source: TASK-DB-003 fleet storage audit (Muse 13, sweep 2026-11-25 05:43–06:06 IST).

## Live state as audited (DB-003, verified live by M13 via bridge `run_shell`, servers 1–6)

- S4 = Stratex-Server, `13.211.78.20`; Stratex + Stratex-Daemon active (daemon UP, Main PID 13273, active since 2026-11-24 06:57:34 UTC per the STR-049 probe).
- `/opt/friday_universe/Stratex/state/` — 884K at sweep time: `equity_snapshots.jsonl` 338K (2026-11-25 00:02 UTC), `forward_scorecard.json` 254K (00:06 UTC), `fill_ledger.jsonl` 40K (2026-11-24 15:17), `position_tags.jsonl` 65K (16:00), `daemon_heartbeat.json` (00:17 UTC); `state/reconciliation/` holds daily_2026-11-23 + daily_2026-11-24, both RECONCILED (STR-051).
- Backup state: **NO BACKUP** — newest state backup 2026-11-14 (`active_trades.json.bak`); Nov 2 snapshot; the fleet backup's STRATEX dir holds only the 4 empty ADB tables (20K). HeatWave `10.0.0.182:3306` is reachable from S1/S2 but NOT from S4, and no MySQL string exists in the S4 Stratex code — that question belongs to DB-001, not this task.

## Repo-side verification, first-hand this run (origin/main `ec46d5f`)

1. `scripts/backup_fleet_databases.py` — `AGENT_STATE_GLOBS = ("Stratex/state/*.jsonl", "Stratex/state/*.json")` (TASK-SEN-007): the fleet script DOES glob Stratex state, but repo-relative — it copies from the checkout's own `Stratex/state/`. On S1 that is the sleeper copy (S1 daemon stopped/disabled), so the Nov 22 run captured nothing live. Failure mode to avoid: a backup taken from S1 is not a backup of live state.
2. TASK-REL-096 fleet-state bundle (merged today; on main `ec46d5f`) — `scripts/backup_fleet_databases.py --fleet-state-only`, builder runs on Oracle Server 2 (the bridge host, with SSH routes to all six servers): `FLEET_STATE_SOURCES` lists `("server4", "13.211.78.20", ("/opt/friday_universe/Stratex/state", "/opt/friday_universe/Stratex/data"), required=True)`; `--finalize` merges the bundle into the unified backup set held identically on both Oracle servers. `.github/workflows/fleet-backup.yml` runs daily 03:30 UTC plus on pushes touching agent trees. The mechanism that backs up live S4 state now exists in main — whether a fleet-state run has executed and captured S4 state since the REL-096 merge is NOT verified from this VM.
3. `Stratex/paper_engine/backup.py` — `BackupManager`: rolling timestamped backups (max 5) into a local `backups/` dir. `Stratex/backups` newest 2026-11-02 (stale, per the DB-003 audit). Not the live path: live state is the `/opt/.../state` dir on S4.
4. No `Stratex/state/*` paths in the repo tree (0 matches) — state files are live-only, git-ignored. There is nothing to back up from the repo itself.
5. S4 host `13.211.78.20` confirmed in two independent repo sources (`FLEET_STATE_SOURCES` and `TASK-DB-001-STRATEX-MYSQL-VERIFY.md`).

## Live leg — plan and gate

- **Plan:** dated backup of `/opt/friday_universe/Stratex/state/*.jsonl` + `*.json` (plus `reconciliation/` per the acceptance) from S4, then a restore/read-back check (copy to scratch, compare md5s + counts against the live listing). Do not change the live daemon.
- **GATE — live leg blocked (same blocker as DB-001):** no bridge route from this VM (verified 2026-11-25 10:08 IST, hub #1483 comment 7153083648 — no bridge connector/helper here, bridge key env-only and not available). Owner stop order still in force; no live moves.
- **Ask for the coordinator (one of):** (a) clear a read-only S4 route for Muse 6 (bridge `run_shell` from S2, same shape as the watch075 grant); (b) re-route the live leg to a bridge-capable worker (M18 precedent); or (c) confirm the REL-096 daily fleet-state run covers DB-004 and let its next run + unified-set verify serve as the dated-backup proof.
- **Note on (c):** a run happening is not proof by itself — the proof still needs a named verifier to read back the unified set (paths, sizes, SHA-256) and run the restore/read-back check.

## Five states

implemented NO / tested NO / merged NO / deployed NO / production-verified NO. Repo-side scoping complete; live leg gated on a cleared S4 route.

## Method note

Checkpoint filed from this run's hourly self-check (stall repair: the claim stood ~1 h with zero commits). Commit created through the GitHub Data API; verified by read-back (branch head + file sha). No work PR yet — one work PR when DONE/BLOCKED, rule 1; board flip rides in it.
