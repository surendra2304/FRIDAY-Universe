# Fleet Backup Repair — TASK-SEN-009

**Date:** 2026-11-15 · **Crew:** Muse crew `muse_ai` (Sentinel wave) · **Origin:** TASK-SEN-007 backup freshness audit (PR #326) · **Owner mandate (2026-11-15):** "Maintain a backup" — this task's end-state is a *standing, monitored* backup, not a one-off fix.

**Method:** GitHub REST API from the sandbox (repo metadata, Actions runs/jobs, file contents at the exact run head SHAs), code inspection of `scripts/backup_fleet_databases.py` + `scripts/oracle_db.py` at all three relevant revisions, and the on-server manifest evidence recorded by TASK-SEN-007. The Server-2 bridge MCP was hung fleet-wide throughout, so no server-side commands could be run and the Actions job logs (which require an authenticated download) could not be retrieved — §1 states plainly what that leaves unproven. No secret values were read or printed anywhere in this task.

---

## 1. G1 — Root cause of the two failed runs

### Evidence

| | Run 1 — 42835686434 | Run 2 — 42836955350 |
|---|---|---|
| Created | 2026-11-10T14:35:47Z | 2026-11-10T14:43:20Z |
| Event | `workflow_dispatch` | `workflow_dispatch` |
| Job duration | 13 s (14:35:50Z → 14:36:03Z) | 23 s (14:43:25Z → 14:43:48Z) |
| Failing step | Step 3 "Run backup" (SSH step) | Step 3 "Run backup" (SSH step) |
| Workflow file | blob `890fda63` (ssh-action v1.0.3) | blob `890fda63` (identical) |
| Backup script | blob `1e4b6037` — **no per-agent .env loading** | blob `a3a4a020` — **with per-agent .env loading (== current main)** |
| Backup dir produced on Server 1 | yes — manifest lists **0 agents**, configs only (SEN-007) | yes — manifest lists **FORGE, INTELX, STRATEX** only (SEN-007) |

### Reasoning chain

1. **The workflow and SSH layers worked both times.** A backup directory, config snapshot and manifest were produced on Server 1 in both runs, so the failure is inside `scripts/backup_fleet_databases.py`'s run on the server, not in GitHub, the schedule, or the SSH action.
2. **The script finished — and exited 1 by design.** `run()` catches each agent's failure, keeps going, writes the manifest, and returns `1` when `failed_agents` is non-empty. Under the SSH step's `set -e`, exit 1 fails the step and the job. Both "failures" are therefore the script's own partial-failure exit code — run 2 in fact *succeeded* for 3 of 10 schemas.
3. **The per-agent failures were fast.** 10 schema attempts plus a config snapshot completed in 13 s (run 1); 3 small dumps plus 7 failures in 23 s (run 2). A hanging Oracle connection costs the driver's 15 s timeout *each* — the failures were near-instant, which is the signature of `OracleConfigError` raised *before* connecting: **no resolvable credentials for those agents** (`resolve_target` raises immediately when no candidate key or user/password/DSN triplet is found).
4. **Run 1 → run 2 is a controlled experiment.** The only code delta between the two run heads is the addition of `agent_runtime_env()` (load each agent's own `.env`, the production credential source). With only `/etc/friday-universe/db-credentials*.env` to consult (run 1), **zero** agents resolved. With per-agent `.env` files added (run 2), exactly the agents whose `.env` carries a resolvable Oracle URL resolved and dumped: FORGE, INTELX, STRATEX.
5. **Why the other 7 did not resolve in run 2** is only partly determinable from here. SENTINEL, CORTEX and VYRALX are Server-2 agents: their `.env` files do not exist in Server 1's checkout (`.env` is git-ignored), and Server 1's `/etc/friday-universe/db-credentials.env` evidently does not carry their keys — a structural gap, since the backup has only ever run on Server 1. For FRIDAY, INFERENCE, MEMORA and FUTURIS (Server-1 agents), their `.env` files exist on Server 1 but apparently held no key matching `resolve_target`'s candidate list (`<AGENT>_DATABASE_URL|_DB_URL|_ORACLE_URL|_URL`, generic `DATABASE_URL`/`ORACLE_CORE_URL`, or the `<AGENT>_DB_USER/PASSWORD/DSN` triplet) at that time. **The discriminating evidence — the `[AGENT] FAILED: …` lines in the two job logs — could not be retrieved in this session** (log download returns 403 unauthenticated; the authenticated route, the bridge, is hung). The supervised dispatch in §4 prints those lines by name, per agent, and is the designed moment this question gets its final answer.

### Root-cause statement

> The backup never succeeded because **credential resolution, not backup logic, was incomplete**: the shared `/etc` credential file alone resolved zero agents, and per-agent `.env` resolution (added between the two runs) covered only 3 of 10 — the three Server-2 agents are structurally unreachable from a Server-1-only run, and four Server-1 agents' env files matched no candidate key. The script's by-design exit-1-on-any-failure then failed both workflow runs, nobody was alerted, and the partial directories on Server 1 were mistaken for a working system.

### Fixes applied in this PR (repo-side)

* **Loud failure (G1d):** any failed Fleet Backup or media job, and any stale/missing backup detected by the watchdog, opens/updates a `[BACKUP-ALERT]` GitHub issue. Silence is no longer a possible failure mode.
* **Media failures count:** a requested media backup that fails is now recorded in `failed_agents` and fails the run (previously a `SKIP` log line that left the exit code untouched) — and a media exception can no longer crash the run before the manifest is written.
* **Completeness is explicit:** every manifest now records `"complete": true/false`. Retention (§7) and freshness (§7) both key off it.
* **Credential-resolution visibility:** the supervised dispatch checklist (§4) requires the per-agent `FAILED:` lines to be read and each unresolved agent's key gap fixed at the source (the agent's `.env` or the `/etc` file) — the runbook names the candidate key shapes so the fix is mechanical.
* **Server-2 schemas:** SENTINEL/CORTEX/VYRALX `.env` files live on Server 2; the structural answer is the same one applied to the media schema (G5): their schemas resolve when a backup runs where their env files are. Until a Server-2 full run is scheduled, the Server-1 manifest will keep listing them as failed **loudly** — see the open item in §8. (Deliberately not papered over: copying other agents' `.env` files between servers to make the number green is a credential-sprawl decision for the coordinator, not a crew.)

## 2. Why the schedule never fired

The workflow (GitHub API, 2026-11-15): state **`active`**, created 2026-11-10T14:27:24Z, never modified on main since. Exactly **one** scheduled slot has elapsed since creation — Sunday 2026-11-15 03:30 UTC — and it produced no run. GitHub drops or delays scheduled runs under load and the first slot after a workflow lands is the most commonly missed; the API offers no field that proves the cause, and this report does not invent one. Mitigations in this PR: a **second weekly slot** (Wednesdays 03:30 UTC), the **watchdog** on its own schedule (§7), and **failure alerting** — so a missed slot is now detected within ~25 hours instead of never.

## 3. What this PR changes

| File | Change |
|---|---|
| `scripts/backup_fleet_databases.py` | G7 per-agent `.env` snapshot (`snapshot_agent_envs`, §6 of SEN-007's list); manifest `complete` flag; successful-run retention in `prune_old_backups`; media failure = failure; `--media-only` mode; verify also covers `agent_envs` |
| `scripts/check_backup_freshness.py` | **New.** Freshness assessment + JSON report + exit codes (0 fresh / 1 stale / 2 never) for the watchdog and for Sentinel/coordinator polling |
| `.github/workflows/fleet-backup.yml` | Second weekly slot; Server 2 `--media-only` job (G5); `[BACKUP-ALERT]` issue on any failure; encrypted offsite artifact upload (G3, secret-gated) |
| `.github/workflows/backup-watchdog.yml` | **New.** Mon+Thu freshness check on Server 1; opens/updates `[BACKUP-ALERT]` when stale/missing; comments + closes it on recovery |
| `tests/test_backup_sen009.py` | **New.** 16 tests: env snapshot (600 perms, no value leak), completeness (flag + legacy derivation), retention (incl. "one bad run cannot evict the last good copy"), media failure counting, `--media-only`, freshness ok/stale/never |
| `docs/observability/BACKUP_REPAIR_SEN009.md` | This report + the §4/§5 runbooks + G3 spec + end-state |
| `docs/observability/RESTORE_DRILL_RUNBOOK.md` | G6 restore-drill runbook |
| `docs/collaboration/WORK_BOARD.yaml` | TASK-SEN-009 entry (insertion-only) |

## 4. G1 — Supervised manual dispatch + verification checklist

Run **after** this PR merges and Fleet CD has deployed it to both servers (the media job needs the new script on Server 2; note Server 2's checkout has historically lagged main — verify before dispatching):

1. Confirm the deployed script is current on both servers: `grep -c "media-only" /opt/friday_universe/scripts/backup_fleet_databases.py` ≥ 1 on Server 1 **and** Server 2.
2. Dispatch: GitHub → Actions → **Fleet Backup** → Run workflow (or `POST /repos/surendra2304/FRIDAY-Universe/actions/workflows/fleet-backup.yml/dispatches` with `{"ref":"main"}`). No inputs.
3. Watch both jobs. In the Server 1 job log, read every `[AGENT] FAILED:` line. For each unresolved agent, fix the credential source (add the agent's Oracle URL to its own `.env` under one of the candidate key names in §1, or to `/etc/friday-universe/db-credentials.env`) and re-dispatch. **Do not accept a partial manifest as success.**
4. Verify the Server 1 manifest (`sudo cat /var/backups/friday-universe/<newest>/manifest.json`):
   - [ ] `agents` lists **all 10 schemas** (FRIDAY, INFERENCE, MEMORA, STRATEX, FUTURIS, INTELX, FORGE, SENTINEL, CORTEX, VYRALX);
   - [ ] `failed_agents` is `[]` and `complete` is `true`;
   - [ ] every agent's tables have `row_count > 0` where the schema is non-empty (cross-check table counts against `VERIFIED_TABLE_COUNTS` in `scripts/oracle_db.py`: 15/8/15/3/12/18/7/15/16/8 tables respectively — a schema dumping 0 tables or all-zero rows is a wrong-schema resolution, not a backup);
   - [ ] `verify.failed` is `0`;
   - [ ] `configs` is non-empty and `agent_envs` lists the `.env` files of the agents hosted on that server;
   - [ ] the Stratex state files are present under `configs/agent-state/` (once PR #326 has merged).
5. Verify the Server 2 media manifest: `agents` lists **VYRALX_MEDIA** with tables and row counts, `complete` is `true`.
6. Run the freshness check on Server 1: `scripts/check_backup_freshness.py --json` → `status: "ok"`, exit 0.
7. Record the run IDs and manifest summaries on the TASK-SEN-009 board entry. Only then does the G6 restore drill (§docs/observability/RESTORE_DRILL_RUNBOOK.md) become runnable.

## 5. G2 — Interim Stratex state copy (Server 1 → Server 2)

Until PR #326's state snapshot rides a *successful* backup, the phase-3 evidence trail (`Stratex/state/*.jsonl|*.json`) exists once. One-time stopgap, from any shell with SSH access to both servers (the bridge `run_shell` can drive it server-side once the bridge recovers):

```bash
# on Server 1 (or via ssh ubuntu@<server1>):
cd /opt/friday_universe/Stratex/state
sha256sum fill_ledger.jsonl equity_snapshots.jsonl position_tags.jsonl > /tmp/stratex-state.sha256
scp fill_ledger.jsonl equity_snapshots.jsonl position_tags.jsonl /tmp/stratex-state.sha256 \
    ubuntu@<server2>:/home/ubuntu/stratex-state-copy-2026-11-15/
# on Server 2:
cd /home/ubuntu/stratex-state-copy-2026-11-15 && sha256sum -c stratex-state.sha256
```

Checksums must verify on Server 2 before the copy counts as done. This is a stopgap, not a system: it is superseded the moment a complete backup (§4) lands, because PR #326 puts the same files inside every backup.

## 6. G3 — Offsite copy: implemented, one secret short of live

**Implemented in this PR:** after each successful Server 1 backup, the workflow tars the newest backup directory on the server, encrypts it with `openssl enc -aes-256-cbc -salt -pbkdf2`, downloads the ciphertext over SCP, and uploads it as a GitHub Actions artifact (`fleet-backup-offsite`, 90-day retention). That is a genuine off-server, off-account copy using only existing tooling and the already-existing SSH secrets.

**The one missing piece — a new secret, specified exactly:**

> **GitHub repository secret `BACKUP_ARTIFACT_PASSPHRASE`** — a long random passphrase (32+ characters) used to encrypt/decrypt the offsite artifacts. It must be created by the repo owner/coordinator (Settings → Secrets and variables → Actions) **and recorded in the `CREDENTIALS.md` dossier on Server 2**, or every artifact becomes undecryptable the day the secret is rotated/lost. Until the secret exists, the workflow step prints a loud `::warning::` and skips — plaintext is **never** uploaded, because the backup contains credential env files.

Decrypt (restore time): `openssl enc -d -aes-256-cbc -salt -pbkdf2 -pass env:BACKUP_ARTIFACT_PASSPHRASE -in friday-backup-offsite.tar.gz.enc | tar xzf -`.

Residual honesty: GitHub artifacts expire after 90 days and live in the same GitHub account as the repo — this survives loss of either server, not loss of the GitHub account. A second destination (OCI Object Storage) remains a coordinator decision (SEN-007 G3); the encrypted-artifact path is the zero-new-infrastructure floor, not the ceiling.

## 7. The maintained end-state (owner mandate: "Maintain a backup")

| Property | End-state |
|---|---|
| Cadence | Fleet Backup: **Sundays + Wednesdays 03:30 UTC** (Server 1 full + Server 2 media in parallel jobs); manual dispatch anytime |
| Freshness tripwire | Backup Watchdog: **Mondays + Thursdays 04:30 UTC**, threshold **120 h** since the last *complete* backup |
| Alert path | Any job failure **or** watchdog staleness opens/updates the **`[BACKUP-ALERT]`** GitHub issue (auto-closed by the watchdog on recovery); `scripts/check_backup_freshness.py --json` gives Sentinel / the coordinator backup age at a glance (`status`, `age_hours`, `last_success_at`) |
| Retention | `--keep 4` now counts **successful** backups: newest 4 complete are always kept; a failed attempt is kept only as the newest forensic record and can never evict a good copy |
| Coverage | 10 schemas + media schema + `/etc` credential files + systemd units + per-agent `.env` files (this PR) + Stratex state files (PR #326) |
| Offsite | Encrypted artifact per successful run (§6), live once `BACKUP_ARTIFACT_PASSPHRASE` is created |
| Schedule verification | A schedule counts as *verified firing* only when an Actions run with `event: schedule` succeeds — the watchdog's first green run after a scheduled slot is the standing proof mechanism; the coordinator records the first scheduled success on the board entry (next_action) |

## 8. Documented, not actioned (per brief)

* **G4 (owner):** `CREDENTIALS.md` — the master dossier — is still a single copy on Server 2. Recommendation stands (SEN-007): an encrypted copy off-fleet under the owner's control (password manager or encrypted archive on the owner's machine), refreshed whenever the dossier changes. Nothing repo-side is appropriate for this file. *Note the interplay with §6: the dossier is also where `BACKUP_ARTIFACT_PASSPHRASE` must be recorded.*
* **G8 (coordinator):** check the OCI console for boot-volume backup policies on both VMs and enable one if absent; confirm `FRIDAY/data/friday.db` (stale since 2026-10-27) is superseded and retire it.
* **Open item from §1:** SENTINEL/CORTEX/VYRALX credential resolution from a Server-1-only run. Options for the coordinator: (a) schedule a full backup job on Server 2 as well (its checkout hosts those agents' `.env` files), mirroring the media job; (b) accept the loud per-run failure for those three until (a). This PR does not silently pick one.

## 9. Honest limitations of this repair

* The two 2026-11-10 job logs were **not** read (403 unauthenticated; bridge hung). §1's root cause is established from the run metadata, both script revisions, both manifests, and timing — the per-agent `FAILED:` lines that would name each missing key exactly are step 3 of the §4 checklist, by design.
* No dispatch was executed from this session (no working authenticated route while the bridge is hung). §4 is written to be executed verbatim by the coordinator/merge-runner after merge + Fleet CD.
* The G2 copy (§5) likewise awaits a server route; it is specified, not executed.
* The first *scheduled* success cannot be observed before the first post-merge slot (Wed 2026-11-18 03:30 UTC); the watchdog is the mechanism that will catch it if it does not fire.
