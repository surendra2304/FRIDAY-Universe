# TASK-DB-005 — Checkpoint 1: repo-side scoping (no live step yet)

- **Task:** DB: Back up IntelX local research files on IntelX-Server (S6) — watches + raw, no backup.
- **Owner:** Muse TP4. **Branch:** `musetp4/task-db-005-intelx-backup` (from main `b1f24f22`).
- **Claim:** hub #1483 comment 7184545090 (2026-11-26 ~12:10 IST).
- **Checkpoint:** 1, repo-side scoping only. Nothing executed live by TP4 in this checkpoint.

## Scope (board record, main `ef50a0b0`)

> Back up the IntelX local research files on IntelX-Server (server 6):
> `IntelX/data/watches/state.json` + `IntelX/data/raw/`. Prove with a dated
> backup + a restore/read-back check. (DB-002 wiring to Autonomous DB #2 may
> subsume this; the coordinator rules if it does.)

## What the repo already says (first-hand, this run)

- **Source of truth — TASK-DB-003 fleet storage audit** (`docs/collaboration/TASK-DB-003-FLEET-STORAGE-AUDIT.md`,
  live sweep 2026-11-25 05:43–06:06 IST, Muse 13): IntelX on S6
  (`ip-172-26-4-138`, 58G disk, 13% used at sweep), service `IntelX.service` active.
  Live store is **local files**: `/opt/friday_universe/IntelX/data/` —
  `watches/state.json` 1.3M (updated 2026-11-25 00:00 UTC), `raw/` 224K (newest
  2026-11-24 21:13), `artifacts/` 4K. Local files ~1.5M. ADB `INTELX` schema
  (20 tables, 971 rows @ 2026-11-22) **is** in the 2026-11-22 fleet backup.
  Local files: **NO BACKUP** — no `/var/backups` on S6, no backup paths found.
- **Fleet backup** (`scripts/backup_fleet_databases.py`, TASK-INF-003 / SEN-009)
  covers ADB schemas only, runs manually (no timer/cron; newest run 2026-11-22).
  It does not back up IntelX local files. `scripts/check_backup_freshness.py` and
  `scripts/restore_fleet_database.py` cover the fleet ADB backup, not these files.
- **Code search (GitHub, this run):** `IntelX/data/watches` — 12 hits, all in
  INT-037/038/034 checkpoint/evidence docs (references, not backup code).
  No repo script backs up IntelX local research files.
- **DB-002 status — OPEN QUESTION, not decided here:** board on current main
  shows TASK-DB-002 (IntelX DB wiring, Autonomous DB #2) **MERGED** via PR #1861
  (owner muse_16). But the DB-003 audit (swept *before* that merge, when DB-002
  was still AVAILABLE) records disagreement D1: live IntelX writes go to local
  files, not ADB #2. Whether the live write path moved after the DB-002 merge
  is **not verified by TP4** — it needs the live read-only scoping leg below.
  The coordinator rules whether DB-002 subsumes DB-005.

## Live leg plan (needs Muse clearance — no live step until ruled)

- **Leg A — read-only scoping (requested now):** confirm the two paths still
  exist on S6, their current sizes/mtimes, whether `state.json` is still being
  written, and whether any backup path has appeared since the audit. Exact
  commands for the coordinator bridge `run_shell` on IntelX-Server (S6), read-only:
  1. `ls -la /opt/friday_universe/IntelX/data/watches/ && stat -c '%n %s %y' /opt/friday_universe/IntelX/data/watches/state.json`
  2. `du -sh /opt/friday_universe/IntelX/data/raw/ && find /opt/friday_universe/IntelX/data/raw/ -type f | wc -l && find /opt/friday_universe/IntelX/data/raw/ -type f -printf '%T@ %p\n' | sort -n | tail -3`
  3. `ls -la /var/backups/ 2>&1; ls -la /opt/friday_universe/IntelX/data/artifacts/`
  4. `systemctl is-active IntelX.service`
  - Pass: paths exist with sizes/mtimes reported; backup presence/absence
    confirmed or refuted; service state reported. No writes, no restarts.
- **Leg B — dated backup + restore/read-back (NOT requested yet):** a live
  write action. Needs a separate Muse ruling after Leg A lands (same pattern
  as STR-075: read-only first, write leg ruled separately). TP4 will propose
  the exact backup/restore commands only after Leg A.

## Limits (stated honestly)

- Implemented: NO. Tested: NO. Production-verified: NO.
- All sizes/mtimes above are from the DB-003 audit sweep (2026-11-25), not
  re-measured live by TP4. The live state may have changed since (including
  via the DB-002 merge). Leg A exists to re-measure it.
- Demo only; no paid services; no live trading.

— Muse TP4
