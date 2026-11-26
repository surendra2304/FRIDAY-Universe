# TASK-DB-011 — evidence: Forge workspaces backup (Muse TP10, 2026-11-26)

Task: TASK-DB-011 (DB: back up Forge workspaces on Oracle Server 1 — 27M
working output, no file backup), claimed on hub #1483 comment 7185987581
(2026-11-26 13:25 IST). Board record on main `54636a72` (blob `cedb989f`):
AVAILABLE / owner muse_tp10 / P2 / blockers []. Acceptance: "Back up the
Forge workspaces on Oracle Server 1 (server 1): Forge/workspaces/ (27M).
Prove with a dated backup + a read-back check. (Coordinator may close as
not-needed if workspaces are regenerable output; the audit flags the gap,
this task settles it.)" Source: TASK-DB-003 fleet storage audit
(`docs/collaboration/TASK-DB-003-FLEET-STORAGE-AUDIT.md`, sweep 2026-11-25).

Five states at this evidence doc: implemented YES (repo-side) / tested YES
(repo-side, see below) / merged NO / deployed NO / production-verified NO.
The live Server 1 leg is GATED (owner stop order WATCH141 + coordinator
clearance); nothing in this PR touches a server.

## Regenerability verdict: backup required — do NOT close as not-needed on repo evidence

Per-subdir of `workspaces/task_<id>/` (`Forge/app/core/workspace.py`
`create_workspace` line 67; subdirs lines 98–102: `project/`, `artifacts/`,
`logs/`, `state/`, `cache/`; anchors re-verified at main `54636a72`,
2026-11-26):

| Subdir | Contents | Regenerable? |
|---|---|---|
| `project/` cloned (`git clone --depth 1`, line 117) or copied from `local_path` | Input code | Input yes; generated modifications + local `.git` history/tags on top **no** |
| `project/` generated from empty (LLM-built; `Forge/app/execution/delivery.py` `package_delivery` line 53 commits + tags `v1.0-forge-delivery`, line 34) | Produced code | **No** — re-run from DB-stored goal is possible but non-deterministic; exact output + verification history lost |
| `artifacts/` (`save_artifact`, workspace.py) | Delivery/verification evidence | Only by re-running verification on preserved `project/`; if `project/` lost, artifacts are the sole proof → **back up** |
| `state/` incl. snapshots (`create_snapshot` / `rollback_snapshot`, workspace.py) | Resume/rollback state | In-flight **no**; snapshots are the rollback source → **back up** |
| `logs/`, `cache/` | Runtime logs/cache | Yes (ephemeral); 27M total is trivial — included in v1, named-exclude only with live size evidence |
| Top-level `Forge/artifacts/` (`Forge/app/core/multi_project.py` `prune_workspaces` line 100 archives completed >7d to `artifacts/archived_<task>`, line 135; cleans failed >24h) | Archived workspaces | Same as workspaces → **included**; live size unverified (DB-003 audit sized only `workspaces/` + `app/`) — inventory owed in the live leg |
| `Forge/data/backups` (`Forge/app/backup/recovery.py` `BackupManager` line 31; `backup_workspace_metadata` line 56 — metadata/config JSON only, never workspace files) | Metadata snapshots | Already collected via fleet bundle `Forge/data`; **not** a substitute for file content |

Supporting facts (verified at main `54636a72`):

- `.gitignore` ignores `**/workspaces/` ("Ephemeral runtime data") — the
  repo is not a backup.
- BackupManager never copies workspace files (metadata JSON only) —
  confirms the DB-003 gap in code.
- Fleet backup `scripts/backup_fleet_databases.py` `FLEET_STATE_SOURCES`
  (line 322): the server1 entry (lines 324–329, required=False) already
  collects `/opt/friday_universe/Forge/data` + `/opt/friday_universe/Forge/state`
  but **omitted `Forge/workspaces` and `Forge/artifacts`** — that omission
  is DB-011. `collect_fleet_state` (line 468) marks the bundle incomplete
  only on `failed_required` (line 526).
- Coordinator may still close as not-needed ONLY if the live inventory
  shows every workspace is cloned-input or completed-and-delivered-elsewhere.
  Repo-side does not pre-claim that; the live inventory decides.

## Repo-side change (this PR)

1. **Code** — `scripts/backup_fleet_databases.py`: added a **separate**
   server1 entry immediately after the existing server1 data/state entry:

   ```python
   ("server1", "140.245.208.100", (
       "/opt/friday_universe/Forge/workspaces",
       "/opt/friday_universe/Forge/artifacts",
   ), True),
   ```

   `required=True` makes a future miss mark the bundle INCOMPLETE
   (`failed_required`) instead of silently passing — DB-011 exists because
   the omission was silent. Existing server1 `Forge/data` + `Forge/state`
   entry untouched (its required flag not flipped). No
   `FLEET_STATE_EXCLUDED` entry in v1. No change to ADB/MySQL legs, rsync
   argv builder, or manifest format. No Forge runtime change — no service
   deploy needed repo-side. Alternative (optional + manifest assertion)
   noted for coordinator ruling in the PR body; not blocking.
2. **Tests** — `tests/test_rel096_backup_fleet_state.py` (collected by
   `.github/workflows/validate-monorepo.yml`): source-table test now
   asserts both Forge paths present and in the required set; two new tests
   reuse the existing `tmp_path`/`monkeypatch` runner pattern —
   `test_collect_fleet_state_covers_forge_workspaces` (manifest SHA-256
   entries verify on disk; both sources report `ok`) and
   `test_collect_fleet_state_forge_workspaces_missing_fails` (bundle
   incomplete, `failed_required` names the path). Tests never touch real
   fleet paths. Local run before PR: 16/16 passed (pytest, scratch venv,
   module loaded from the edited files; CI re-runs on the PR head).
3. **Docs** — this file. Restore stays single-sourced:
   `docs/observability/RESTORE_DRILL_RUNBOOK.md` (SEN-009); no second
   runbook.

## Gated live procedure (owed on coordinator clearance — NOT run by this PR)

Live leg gated: owner stop order (WATCH141) + coordinator clearance.
Bridge discipline: server number explicit, `sudo -n systemctl`,
`--no-block` for oneshots, capitalized unit names; read-only inventory
first; paths/sizes/hashes only, never secrets.

(a) **Read-only S1 inventory** via bridge server 1: `du -sh` on
    `/opt/friday_universe/Forge/workspaces` and
    `/opt/friday_universe/Forge/artifacts`; per-task listing; classify
    each workspace cloned/copied vs generated via its `.forge_workspace`
    fields. If every workspace proves cloned-input or
    completed-and-delivered-elsewhere, the coordinator may close DB-011
    as not-needed with this inventory as evidence; otherwise proceed.
(b) **Dated backup**: run the fleet-state collect on the Server 2 bundle
    builder; dated bundle under `/var/backups/friday-universe`;
    `bundle_manifest.json` must read `complete: true` with Forge
    workspaces + artifacts entries present and `failed_required` empty.
(c) **Read-back check**: verify SHA-256 of every Forge workspace file
    against the manifest; extract one sample task workspace; diff
    `project/.git` HEAD + `artifacts/completion_report.json` (if present)
    against the S1 originals. Record bundle path, date, file count,
    total bytes, and the sample diff result as live evidence.
(d) **Restore note**: restore follows
    `docs/observability/RESTORE_DRILL_RUNBOOK.md` (SEN-009) — no second
    runbook.
(e) **Retention**: the backup captures workspaces before
    `prune_workspaces` archives (>7d) or cleans (failed >24h); archived
    copies under `Forge/artifacts` stay in scope.

Only after (a)–(c) pass with live evidence may the states move to
deployed / production-verified. Until then: implemented YES (repo-side) /
tested YES (repo-side) / merged NO / deployed NO / production-verified NO.

— Muse TP10
