# Backup Freshness Audit — TASK-SEN-007

**Date:** 2026-11-15 · **Auditor:** Muse crew `muse_ai` (Sentinel wave 5) · **Method:** read-only probes only — bridge `run_shell`/`list` reads on both servers, GitHub REST API (repo + Actions metadata), and the on-server backup manifests. No server state was modified; no secret values were read (file metadata, manifests and workflow metadata only). All dates below are evidence timestamps taken from those sources on 2026-11-15.

## Verdict in one paragraph

The fleet *designed* a real backup system (TASK-INF-003, 2026-11-10: logical dumps of all ten Oracle Autonomous DB schemas + config snapshots, weekly schedule, restore tool, checksums) — and it has **never once completed a backup**. Both runs in its history failed on 2026-11-10; the weekly schedule has never fired; the newest artifact is a 5-day-old partial dump covering 3 of 10 schemas, stored only on Server 1's own boot volume. Separately, the single most important evidence trail in the project — Stratex's forward-test ledger — lives in git-ignored local files that **no** backup mechanism covers, and the master credentials dossier exists as exactly one file on one server. Code and plan docs are the only assets in good shape (GitHub, current today).

## Per-asset backup table

| # | Asset | Backup mechanism | Last backup (evidence) | Where the copy lives | Restorable in principle? |
|---|-------|------------------|------------------------|----------------------|--------------------------|
| 1 | Monorepo code (all 10 agents) | GitHub remote (public repo) | Push 2026-11-15T08:05:45Z, main `1eebae08` | GitHub + server checkouts (S1 at main HEAD; S2 at `1e25237a`, 2026-11-15 12:56 IST, 9 dirty files incl. live bridge code not in git) | **Yes** — clone. Exception: S2's uncommitted bridge changes exist only on S2 |
| 2 | Board + plan docs (`docs/collaboration/WORK_BOARD.yaml`, `docs/MASTER_PLAN.md`, ACTIVITY_LOG) | In-repo (same as #1) | WORK_BOARD last commit 2026-11-15T07:26:49Z; MASTER_PLAN 2026-11-14T07:12:03Z | GitHub | **Yes** |
| 3 | Agent databases — Oracle ADB schemas FRIDAY, INFERENCE, MEMORA (the Memora store), FUTURIS, INTELX, FORGE, SENTINEL, CORTEX, VYRALX, STRATEX | `scripts/backup_fleet_databases.py` via `.github/workflows/fleet-backup.yml` (weekly Sun 03:30 UTC, `--keep 4`) | **Never complete.** Run 2026-11-10T14:36:01Z: 0 schemas (configs only). Run 2026-11-10T14:43:36Z: FORGE, INTELX, STRATEX only, STRATEX tables all 0 rows. No run since; **no scheduled run has ever fired** (workflow on main since 2026-11-10T14:27Z; the Sun 2026-11-15 03:30 UTC slot produced no run) | `/var/backups/friday-universe/<ts>/` on **Server 1 only** (100K + 240K) | Partially — the dumped tables could be reloaded with `scripts/restore_fleet_database.py`, but 7 of 10 schemas (incl. MEMORA) have **no dump at all**; restore has never been drilled in production (ledger-persistence drill workflow: **0 runs ever**) |
| 4 | VyralX media schema (VYRALX_MEDIA, separate ADB) | Same script, only with `--media` | **Never** — the scheduled/manual workflow does not pass `--media`; media DB credentials exist only on Server 2 (`/etc/friday-universe/db-credentials-media.env`, 2026-10-27) while the backup runs on Server 1 | — | **No backup exists** |
| 5 | Stratex measurement state — `Stratex/state/fill_ledger.jsonl`, `equity_snapshots.jsonl`, `position_tags.jsonl` + daemon state JSON | **None.** Files are git-ignored (`Stratex/.gitignore:143 state/`), are not in the Oracle schema, and are outside the fleet backup's scope | **Never.** Live files on S1: equity_snapshots mtime 2026-11-15 13:38 IST (178,693 B, appended today), fill_ledger 2026-11-15 02:33 IST, position_tags 2026-11-14 23:31 IST | Server 1 only, single copy | **No** — if Server 1's disk is lost, the phase-3 forward-test evidence (the demo-profit proof trail) is lost with it. **Fixed prospectively by this PR** (state files join the backup's config snapshot) — but the backup itself must also be made to run (G1) |
| 6 | Master credentials dossier `CREDENTIALS.md` | **None** | Single copy: Server 2 `/opt/friday_universe/CREDENTIALS.md`, 16,951 B, mtime **2026-11-09** 01:51 IST. No copy on S1, none in the sandbox workspace, none (by design) in the public repo | Server 2 only | **No** — loss of Server 2 = loss of the only consolidated key inventory |
| 7 | `credentials.md` (lowercase, Telegram subset) | `.github/workflows/sync-credentials.yml` writes it from GitHub Secrets to both servers | Workflow run 2026-11-11T14:34:28Z **success** (only run ever). On-server files are newer than the run (S1 2026-11-13 12:26 IST; S2 2026-11-13 20:58 IST) → hand-edited since; no `.bak-*` rotations present | GitHub Secrets (source) + both servers | **Yes, for the Telegram subset only** — the API-key pools and everything else in the dossier are not in GitHub Secrets and are not reconstructable this way |
| 8 | Per-agent `.env` files (13 across both servers) | Partially: the fleet backup's config snapshot covers `/etc/friday-universe/db-credentials*.env` + systemd units — **not** the per-agent `.env` files | Config snapshot last captured 2026-11-10 (inside the two partial backups). `.env` mtimes range 2026-10-30 → 2026-11-15 (Stratex edited today) | Servers only | **No** — a rebuilt server cannot reconstruct agent env from any backup; values would have to be re-derived from the dossier (#6, itself unbacked-up) |
| 9 | `/etc/friday-universe/` DB credential files | Fleet-backup config snapshot (Server 1 copies) | 2026-11-10 snapshot: `db-credentials.env` captured. S2's own files (`db-credentials.env` 2026-10-31, `db-credentials-media.env` 2026-10-27, DSN JSONs) are **not** covered — the backup runs on S1 only | S1 backup dirs | Partial (S1 files only, 5 days stale) |
| 10 | Server OS / boot volumes (OCI snapshots or boot-volume backups) | None found | **No evidence of any snapshot mechanism**: no backup cron jobs, timers or units on either server (only the OS `dpkg-db-backup` timer); no `oci` CLI in the ubuntu PATH on either server (`~/.oci` config exists on S2 for the capacity allocator) | — | **Unknown / unverifiable from the servers** — OCI console check required (proposal P4) |
| 11 | Ad-hoc home-directory backups (Server 2) | Manual, by past agents | `env-backups/`: one file (a VyralX env copy, 2026-11-10). `systemd-backups/`: one unit file (2026-11-10). `friday-deploy-backups/`: deploy preflight artifacts (2026-11-12/13). `uncommitted-backup-20261108…`: its `UNCOMMITTED.diff` is **0 bytes** — an empty backup; `uncommitted-backup-20261109…`: a real 55 KB working-tree diff (2026-11-09/10) | Server 2 home — same disk as the data | Ad-hoc only; same-disk, unrotated, partly empty — not a backup system |
| 12 | FRIDAY legacy local DB `FRIDAY/data/friday.db` | None | File mtime 2026-10-27 (344,064 B) — stale; FRIDAY's durable history moved to the Oracle FRIDAY schema (TASK-REL-029) | Server 1 only | Believed superseded — confirm and retire (P5) |

*Memora note:* Memora keeps **no** local store files on Server 1 (verified by file scan) — its store is entirely the Oracle MEMORA schema, so row 3 *is* Memora's backup row: designed, never completed. The Wave-5 Memora backup-drill crew (MEM-003..007 range) covers restore testing; this audit covers inventory/freshness.

## Gap list and remediation

**G1 — CRITICAL — The database backup has never succeeded and its schedule has never fired.**
Evidence: Actions shows exactly 2 runs ever (2026-11-10, both `failure`); manifests show run 1 dumped 0 schemas and run 2 stopped after 3 of 10. The workflow file has been on main since 2026-11-10T14:27Z, yet the Sun 2026-11-15 03:30 UTC slot produced no run.
Remediation (server-side, for the coordinator — this audit changes nothing on servers): (a) read the two failed runs' logs and fix the root cause; (b) dispatch one supervised full run and verify the manifest lists all 10 schemas with non-trivial row counts; (c) investigate why the schedule does not fire (workflow state/permissions) and re-arm it; (d) add failure alerting so a failed backup is loud, not silent for 5 days.

**G2 — CRITICAL — Stratex forward-test evidence has zero backup coverage.**
Evidence: row 5. The phase-3 protocol's proof (fill ledger, equity snapshots, position tags) is append-only local files on one 956MB VM.
Remediation: **implemented repo-side in this PR** — `scripts/backup_fleet_databases.py` now includes `Stratex/state/*.jsonl|*.json` (minus `.lock` files) in every backup's config snapshot (`configs/agent-state/…`, mode 600, covered by the existing `--verify` existence pass), with unit tests. This takes effect the next time a backup actually runs — G1 is still required. Interim (coordinator): one manual copy of `Stratex/state/` to Server 2 today, so the evidence exists twice while G1 is fixed.

**G3 — HIGH — No offsite copy of anything.**
Every backup artifact lives on Server 1's boot volume; the drill doc (`docs/observability/BACKUP_RESTORE_AND_LEDGER_DRILL.md` §5) already recommended "at least one copy outside Server 1's boot volume" on 2026-11-10 as an owner decision — still open. Disk space is not a constraint (97G volume, 23% used; backups are ~340K total).
Proposal (coordinator/owner): sync `/var/backups/friday-universe` to OCI Object Storage (or, minimally, mirror it to Server 2 after each run — survives single-VM loss, though not account loss). Not implemented here: it needs an infra destination decision and server-side scheduling.

**G4 — HIGH — Master credentials dossier is a single point of failure.**
Evidence: row 6 — one file, one server, mtime 2026-11-09, and it is the reconstruction source for every `.env` (row 8). It must never enter the public repo.
Proposal (owner/coordinator only): keep an encrypted copy off-fleet (owner's password manager or an encrypted archive on the owner's machine), refreshed whenever the dossier changes. Server-side handling only; nothing repo-side is appropriate here.

**G5 — MEDIUM — VyralX media schema is silently excluded from backups.**
The workflow never passes `--media`, and the media DB credentials live on Server 2 while the backup runs on Server 1, so simply adding the flag on S1 would fail.
Proposal (coordinator): either run a second, S2-based backup invocation for the media schema, or make the media credential file available to the S1 run; then add `--media` to the workflow.

**G6 — MEDIUM — Restore has never been proven in production.**
The restore script and CI contract tests exist, but the ledger-persistence drill workflow has 0 runs and `--verify` has never been run against a complete backup (none exists).
Proposal (coordinator): after G1 produces one complete backup, run `backup_fleet_databases.py --verify` on it and then the ledger-persistence drill (owner confirmation per the drill doc) — in that order.

**G7 — MEDIUM — Per-agent `.env` files are outside every backup.**
Evidence: row 8. The config snapshot covers `/etc/friday-universe` DB files and systemd units only.
Proposal: extend the config snapshot to the per-agent `.env` files as well (same protected directory, mode 600). Repo-side and small — deliberately **not** bundled into this PR so the coordinator can decide explicitly, because it widens the secret surface of the backup directory; the Stratex-state change in this PR carries no secrets.

**G8 — LOW — Server snapshots unverifiable; ad-hoc backups are not a system.**
Evidence: rows 10–12.
Proposals: (P4) coordinator checks the OCI console for boot-volume backup policies on both VMs and enables one if absent; (P5) confirm `FRIDAY/data/friday.db` is superseded and retire it; fold the S2 home-directory ad-hoc backups into G3's offsite sync or delete them as stale.

## What this PR does

1. This audit (`docs/observability/BACKUP_FRESHNESS_AUDIT_2026-11-15.md`).
2. `scripts/backup_fleet_databases.py`: agent-state snapshot (G2) + tests in `tests/test_backup_fleet_databases.py`.
3. Board entry for TASK-SEN-007.

It does **not** touch the servers, the backup schedule, or any credential material. G1/G3/G4/G5/G6 are written as coordinator/owner actions above, in priority order.

## Probe inventory (for re-verification)

- GitHub API: repo metadata, `branches/main`, per-path commit lists (WORK_BOARD, MASTER_PLAN, fleet-backup.yml), Actions workflow/run lists for Fleet Backup (2 runs), Sync Credentials (1 run), Ledger Persistence Drill (0 runs), Subtree Mirror (dry-run policy), Reconcile Server 1 (1 run).
- Bridge `run_shell` reads, 2026-11-15 08:09–08:20Z and later: S1/S2 `/opt/friday_universe` listings, checkout HEADs, `.env`/credential-file `stat`s, `/var/backups/friday-universe` listings + both `manifest.json` heads, `Stratex/state/` stats + `git check-ignore`, Memora/FRIDAY local-file scans, `/etc/friday-universe` listings, cron/timer/unit greps, home-directory listings.
- Repo reads: `scripts/backup_fleet_databases.py`, `scripts/oracle_db.py` (AGENT_SCHEMAS), `scripts/restore_fleet_database.py`, both workflow files, the drill doc, `Stratex/measurement/fill_ledger.py`, `Stratex/.gitignore`.
- Not retrieved: the two failed Fleet Backup runs' job logs (bridge congestion during the audit window — repeated MCP timeouts). The manifests inside the backup directories provide the completeness evidence instead; reading the logs is step (a) of G1. Server 1's home directory could not be probed for the same reason; Server 2's was (row 11).
