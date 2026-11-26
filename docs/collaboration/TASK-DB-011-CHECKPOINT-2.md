# TASK-DB-011 — checkpoint 2: regenerability verdict + implementation plan (Muse TP10, 2026-11-26)

Continues scoping checkpoint `docs/collaboration/TASK-DB-011-SCOPING-CHECKPOINT.md`
(branch `musetp10/task-db-011` @ `d5d241e0`). All anchors below re-verified
first-hand at current main `1d790bb5` (2026-11-26 ~15:30 IST) via the GitHub
contents API. Five states still all NO: implemented NO / tested NO /
merged NO / deployed NO / production-verified NO. Repo-side only; no server
touched. Live Server 1 leg stays gated (owner stop order WATCH141 +
coordinator clearance).

## Regenerability verdict: backup required — do NOT close as not-needed on repo evidence

Per-subdir of `workspaces/task_<id>/` (`Forge/app/core/workspace.py`
`WorkspaceManager.create_workspace` line 67; subdirs lines 98–102:
`project/`, `artifacts/`, `logs/`, `state/`, `cache/`):

| Subdir | Contents | Regenerable? |
|---|---|---|
| `project/` cloned (`git clone --depth 1`, line 117) or copied from `local_path` | Input code | Input yes; generated modifications + local `.git` history/tags on top **no** |
| `project/` generated from empty (LLM-built; `Forge/app/execution/delivery.py` `package_delivery` line 53 commits + tags `v1.0-forge-delivery`, line 34) | Produced code | **No** — re-run from DB-stored goal is possible but non-deterministic; exact output + verification history lost |
| `artifacts/` (`save_artifact`, workspace.py line 220) | Delivery/verification evidence | Only by re-running verification on preserved `project/`; if `project/` lost, artifacts are the sole proof → **back up** |
| `state/` incl. `state/snapshots` (`create_snapshot` line 318, `rollback_snapshot` line 334) | Resume/rollback state | In-flight **no**; snapshots are the rollback source → **back up** |
| `logs/`, `cache/` | Runtime logs/cache | Yes (ephemeral); 27M total is trivial — include in v1, named-exclude only with live size evidence |
| Top-level `Forge/artifacts/` (`Forge/app/core/multi_project.py` `prune_workspaces` line 100 archives completed >7d to `artifacts/archived_<task>`, line 135; cleans failed >24h) | Archived workspaces | Same as workspaces → **must include**; live size unverified (DB-003 audit sized only `workspaces/` + `app/`) — inventory owed in live leg |
| `Forge/data/backups` (`Forge/app/backup/recovery.py` BackupManager, line 5: metadata/config JSON only, never workspace files; `backup_workspace_metadata` line 56) | Metadata snapshots | Already collected via fleet bundle `Forge/data`; **not** a substitute for file content |

Supporting facts (verified at main `1d790bb5`):

- `.gitignore` lines 41–46 ignore `**/workspaces/` ("Ephemeral runtime data") — the repo is not a backup.
- BackupManager never copies workspace files (metadata JSON only) — confirms the DB-003 gap in code.
- Fleet backup `scripts/backup_fleet_databases.py` `FLEET_STATE_SOURCES` (line 322): the server1 entry (lines 324–329, required=False) already collects `/opt/friday_universe/Forge/data` + `/opt/friday_universe/Forge/state` but **omits `Forge/workspaces` and `Forge/artifacts`** — that omission is DB-011. `collect_fleet_state` (line 468) marks the bundle incomplete only on `failed_required` (line 526).
- Coordinator may still close as not-needed ONLY if the live inventory shows every workspace is cloned-input or completed-and-delivered-elsewhere. Repo-side must not pre-claim that; the live inventory decides.

## Implementation (repo-side, one task = one PR)

1. **Code** — `scripts/backup_fleet_databases.py`: add a **separate** server1
   entry so omission becomes loud:
   `("server1", "140.245.208.100", ("/opt/friday_universe/Forge/workspaces", "/opt/friday_universe/Forge/artifacts"), True)`
   `required=True` makes a future miss mark the bundle INCOMPLETE
   (`failed_required`) instead of silently passing — DB-011 exists because
   the omission was silent. Existing server1 `Forge/data` + `Forge/state`
   entry untouched (its required flag not flipped). No
   `FLEET_STATE_EXCLUDED` entry in v1. No change to ADB/MySQL legs, rsync
   argv builder, or manifest format. No Forge runtime change — no service
   deploy needed repo-side. Alternative (optional + manifest assertion)
   noted in the PR body for coordinator ruling; not blocking.
2. **Tests** — extend `tests/test_rel096_backup_fleet_state.py` (already
   collected: `.github/workflows/validate-monorepo.yml` line 58):
   `test_source_table_covers_all_six_servers_and_required_state` (line 42)
   asserts both Forge paths present and workspaces in the required set;
   collect happy-path (manifest SHA-256 entries) and required-missing
   (bundle incomplete, `failed_required` names the path) cases reusing the
   existing `tmp_path`/`monkeypatch` runner pattern. Tests never touch real
   fleet paths.
3. **Docs/evidence** — `docs/collaboration/TASK-DB-011-EVIDENCE.md` with the
   table above at PR-head anchors + the gated live procedure: (a) read-only
   S1 inventory via bridge server 1 (`du -sh`, per-task listing, classify
   cloned/copied vs generated via `.forge_workspace` fields; paths/sizes/
   hashes only, never secrets); (b) fleet-state collect on the Server 2
   bundle builder, dated bundle under `/var/backups/friday-universe`,
   `bundle_manifest.json` `complete: true` with Forge entries present;
   (c) read-back: verify SHA-256 of every Forge workspace file, extract one
   sample task workspace, diff `project/.git` HEAD +
   `artifacts/completion_report.json` (if present) against S1 originals;
   (d) restore note referencing `docs/observability/RESTORE_DRILL_RUNBOOK.md`
   (SEN-009), no second runbook; (e) retention: backup captures workspaces
   before `prune_workspaces` archives/cleans; archived copies under
   `Forge/artifacts` stay in scope. Five states stated separately; live leg
   explicitly gated.
4. **Board/PR discipline** — rebase onto current main immediately before PR;
   board hunk built from current main blob of `WORK_BOARD.yaml`; exactly one
   `evidence:` key citing pushed head sha; flip DB-011 in the work PR only.
   Never merge own PR; peer full-diff review + fully green CI; paired
   verifier tests live behaviour (bundle collect on fixtures / manifest
   assertions), not just the diff.

## Status at this checkpoint

- Branch `musetp10/task-db-011`: checkpoint 1 `d5d241e0` + this checkpoint 2.
  No implementation commits yet — code + tests owed next, then one work PR.
- Queue: DB-011 → INF-043 → VOI-045 (board on main `1d790bb5`, blob
  `0b0b20ae`: DB-011 AVAILABLE / muse_tp10 / branch null / pr null — CLAIMED
  flip rides the work PR per WATCH148 correction).
- Hub: claim 7185987581; WATCH148 correction (7186158821) noted the claim;
  WATCH149–153 carry no TP10 demand, no P0 preemption.
- Usage 8% free weekly (verified this run), reset Wed Dec 2 6:34 PM IST.

— Muse TP10
