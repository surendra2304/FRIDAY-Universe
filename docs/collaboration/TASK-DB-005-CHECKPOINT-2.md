# TASK-DB-005 — Checkpoint 2: Leg A evidence + Leg B proposal (no live step by TP4)

- **Task:** DB: Back up IntelX local research files on IntelX-Server (S6) — watches + raw, no backup.
- **Owner:** Muse TP4. **Branch:** `musetp4/task-db-005-intelx-backup` (head `b13408e1`, checkpoint 1).
- **Claim:** hub #1483 comment 7184545090 (2026-11-26 ~12:10 IST).
- **Checkpoint:** 2. Leg A executed by the coordinator (not by TP4); Leg B proposed only, not granted, nothing executed.

## Leg A — EXECUTED (coordinator bridge run_shell, IntelX-Server S6)

- **Grant:** WATCH155 follow-up, hub 7190118925 (read-only run_shell on S6, scoped exactly to the 4 commands in checkpoint 1). Command list posted by TP4 on #1483, comment 7190711734.
- **Execution:** WATCH161, hub 7192344914, ~18:05–18:10 IST, 4/4 read-only commands exit 0, via coordinator bridge run_shell on S6.
- **Evidence (WATCH161):**
  1. `watches/state.json`: **1,440,445 B, mtime 2026-11-26 12:33:23 UTC — still being written** (minutes before the run). `outbox.jsonl` also present (3,782 B, Nov 24 21:30).
  2. `raw/`: **312K, 29 files, newest ~2026-11-26 12:20 UTC — still being written.**
  3. `/var/backups/`: system files only (alternatives/apt/dpkg) — **no IntelX backup**. `artifacts/` exists but **empty**.
  4. `IntelX.service`: **active**.
- **What Leg A proves:** both live paths exist and are actively written today; no backup of them exists anywhere on S6; the service is up. The DB-003 audit figures (1.3M / 224K, 2026-11-25) are superseded by these live figures (1,440,445 B / 312K, 29 files).
- **Ruling (WATCH161): DB-002 does NOT subsume DB-005 on this evidence.** The live write path still goes to local files after the DB-002 merge (PR #1861): state.json and raw/ are being written today. DB-005's backup is still needed.
- **Honesty note:** TP4 did not re-run the Leg A commands first-hand — TP4's bridge client has no run_shell tool, so the evidence above is the coordinator's execution, cited by hub comment ID (same pattern as STR-075 checkpoint 2, which cited the WATCH140/WATCH143 executions). If a verified run_shell path for TP4 is established, a first-hand re-check can be added as checkpoint 3.

## Leg B — dated backup + restore/read-back: PROPOSED, NOT granted

- A live write action. Needs a separate Muse ruling. Nothing below has been executed.
- Exact commands proposed for the coordinator bridge run_shell on IntelX-Server (S6). `$TS` is one UTC timestamp per run (e.g. `20261126-183000`), set once in command 0 and reused:
  0. `TS=$(date -u +%Y%m%d-%H%M%S); echo $TS; stat -c '%n %s %y' /opt/friday_universe/IntelX/data/watches/state.json; find /opt/friday_universe/IntelX/data/raw/ -type f | wc -l` (live guard, before)
  1. `mkdir -p /var/backups/intelx-$TS && cp -a /opt/friday_universe/IntelX/data/watches/state.json /var/backups/intelx-$TS/state.json && cp -a /opt/friday_universe/IntelX/data/raw /var/backups/intelx-$TS/raw && ls -l /var/backups/intelx-$TS/ && find /var/backups/intelx-$TS/ -type f | wc -l` (dated backup)
  2. `cd /var/backups/intelx-$TS && sha256sum state.json raw/* > SHA256SUMS && cat SHA256SUMS` (hash the backup)
  3. `mkdir -p /tmp/intelx-restore-$TS && cp -a /var/backups/intelx-$TS/state.json /var/backups/intelx-$TS/raw /tmp/intelx-restore-$TS/ && cd /tmp/intelx-restore-$TS && sha256sum -c /var/backups/intelx-$TS/SHA256SUMS && python3 -c "import json; d=json.load(open('state.json')); print('state.json parses, top-level keys:', len(d))" && find . -type f | wc -l` (restore/read-back to scratch)
  4. `du -sh /var/backups/intelx-$TS/; stat -c '%n %s %y' /opt/friday_universe/IntelX/data/watches/state.json` (size evidence + live guard, after)
- **Pass:** backup dir holds state.json + raw/ (29 files, matching Leg A) + SHA256SUMS — 31 files total; every hash in SHA256SUMS verifies OK in the scratch restore; state.json parses as JSON in the restore; the restore holds 30 files (state.json + 29 raw files), matching the backup minus SHA256SUMS.
- **Safety:** no service stop/restart; no writes to the `/opt/friday_universe` live paths — the only write is the new dated dir under `/var/backups/`; the read-back copies to `/tmp` scratch and never overwrites live files; live state.json mtime/size recorded before (command 0) and after (command 4) so any change during the copy is visible.
- **Caveat (honest):** state.json is actively written, so the copy is a point-in-time snapshot, not a crash-consistent image — if the live mtime/size moves between commands 0 and 4, the backup is still a valid dated restore point, and the move is reported, not hidden.

## Limits (stated honestly)

- Implemented: NO (no backup exists yet). Tested: NO. Production-verified: NO.
- Leg A evidence is coordinator-executed (cited above), not re-run first-hand by TP4.
- Demo only; no paid services; no live trading.

— Muse TP4
