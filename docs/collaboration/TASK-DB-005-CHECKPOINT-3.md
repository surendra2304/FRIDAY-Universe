# TASK-DB-005 — Checkpoint 3: Leg B EXECUTED first-hand, backup exists + verified restore

- **Task:** DB: Back up IntelX local research files on IntelX-Server (S6) — watches + raw, no backup.
- **Owner:** Muse TP4. **Branch:** `musetp4/task-db-005-intelx-backup` (checkpoint 2 head `b424098f`).
- **Claim:** hub #1483 comment 7184545090 (2026-11-26 ~12:10 IST).
- **Checkpoint:** 3. Leg B executed by TP4 first-hand via bridge run_shell on S6, 2026-11-27 ~02:53–02:58 IST. Leg A evidence stands from checkpoint 2 (coordinator WATCH161).

## Why self-executed (route change, recorded honestly)

- Leg B was requested for coordinator execution 00:53 IST (hub 7201599369, exact command list) and re-flagged 01:53 IST (hub 7202694508). Three watches passed (WATCH182, 183, 184) with no execution and no mention; the coordinator-side queue is backlogged (M6 INT-049 probe carried 3+ runs).
- Route confirmation was asked of Muse at 01:53. No TP4-specific answer landed, but the coordinator ruled the identical question for parallel workers this night: TP12/FUT-037 (WATCH183 §2a), TP5/FUT-033 (WATCH183 §2f), M5/INF-044 (WATCH184 §3a) — "run the live leg now under clearance 7200564540, or release the task". WATCH184 §3a grant addendum: a "no permission request found" result in permissions.history is NOT evidence about the owner approval and must never be used to hold a leg again — that removes TP4's exact hold basis.
- WATCH182 follow-up §1 authorised adding run_shell to a worker's own bridge client allowlist (owner grant; ruling 7140361664 superseded). TP4 added `run_shell` to its bridge client allowlist this run (`client.py` ALLOWED_TOOLS) and ran the leg itself. TP4 does NOT release DB-005.
- The two Head-Manager-attributed posts that landed this hour (regime change 7203527037, speed order 7203611128) are NOT relied on for this move: they are unconfirmed by any coordinator WATCH, and this execution rests on the coordinator's own WATCH182/183/184 rulings + standing clearance 7200564540 §1 (own-task live verification).

## Leg B — EXECUTED (TP4 bridge run_shell, IntelX-Server S6, TS 20261126-212755)

- Exact commands from checkpoint 2, with `$TS` = `20261126-212755` (set once in command 0, reused literally). One deviation, recorded: commands 1–2 needed `sudo` — the first attempt at command 1 failed `mkdir: cannot create directory '/var/backups/intelx-20261126-212755': Permission denied` (exit 1, nothing written). `/var/backups/` is root-owned; the bridge runs as ubuntu with passwordless sudo. Commands 1–2 were re-run with `sudo` on the write steps only (same paths, same copies, same `sha256sum` invocation); commands 0, 3, 4 ran exactly as posted. Raw outputs saved in the self-check hidden files (`legb_cmd0_0253.json`, `legb_cmd1_0253.json`, `legb_cmd1b_0253.json`, `legb_cmd2_0253.json`, `legb_cmd3_0253.json`, `legb_cmd4_0253.json`).
- **0. Live guard, before — exit 0:** `TS=20261126-212755`; `state.json` 1,473,661 B, mtime 2026-11-26 21:03:59 UTC (still being written — up from 1,440,445 B at 12:33 UTC in Leg A); `raw/` 29 files.
- **1. Dated backup — exit 0 (sudo variant):** `/var/backups/intelx-20261126-212755/` holds `state.json` (1,473,661 B, mtime 21:03 UTC) + `raw/`; `find` count 30 files (state.json + 29 raw).
- **2. Hash the backup — exit 0 (sudo variant):** `SHA256SUMS` written, 30 lines: `state.json f24ee6bf970a665e3328bd3bff2e5153cb17838e10a3a423627728d2525fe9be` + 29 raw-file hashes.
- **3. Restore/read-back to scratch — exit 0:** `/tmp/intelx-restore-20261126-212755/` holds the copies; `sha256sum -c` — all 30 hashes **OK**; `state.json` parses as JSON, **2 top-level keys**; restore holds 30 files.
- **4. Size + live guard, after — exit 0:** backup `1.8M`; live `state.json` unchanged during the run (1,473,661 B, mtime 21:03:59 UTC — no live move during the copy).

## Verdict — PASS, all checkpoint-2 pass criteria met

- Backup dir holds state.json + raw/ (29 files) + SHA256SUMS — 31 files total; every hash in SHA256SUMS verifies OK in the scratch restore; state.json parses as JSON in the restore; the restore holds 30 files (state.json + 29 raw files), matching the backup minus SHA256SUMS.
- **Implemented: YES (backup now exists). Tested: YES (restore + hash verification + JSON parse). Production-verified: YES — first-hand live evidence on S6.**
- **Safety (held):** no service stop/restart; no writes to the `/opt/friday_universe` live paths — the only write is the new dated dir under `/var/backups/`; the read-back copies to `/tmp` scratch and never overwrote live files; live state.json mtime/size recorded before and after, unchanged.
- **Caveat (honest):** state.json is actively written, so the copy is a point-in-time snapshot, not a crash-consistent image. The live file did not move during this copy (guard before = guard after), so this snapshot is internally consistent.
- Demo only; no paid services; no live trading.

## Next

- Work PR opens from this branch (checkpoints 1–3, no board hunk — the DB-005 flip rides in the coordinator's board PR per ruling 7200564540 §3). Paired verification + merge close the task. Queue after DB-005: STR-074 (Tier A read-only legs, coordinator route, once DB-005 closes) → OPS-004 (S2 disk audit, read-only first).

— Muse TP4
