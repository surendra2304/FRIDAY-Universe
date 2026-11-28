# TASK-DB-006 — Back up Futuris local forecast files on IntelX-Server (S6)

- **Task:** TASK-DB-006 (DB: Back up Futuris local forecast files on IntelX-Server (S6) - data/storage parquet, no backup)
- **Assignment:** BE 03:42 §B (hub #2045 comment 7229120299), confirmed WATCH244 §B/§C (hub 7229329225)
- **Claim:** hub #2045 comment 7229429474 (2026-11-28 ~04:0x IST)
- **Branch:** `muse17/task-db-006` from main `901a1114`
- **Acceptance:** "Back up the Futuris local forecast files on IntelX-Server (server 6): Futuris/data/storage/ (parquet snapshots, 54M, 805 snapshot dirs). Prove with a dated backup + a restore/read-back check. (DB-002 wiring may subsume this; the coordinator rules if it does.)"

## Board verified first-hand

Live main `901a1114` (board blob `35b6b1ef`, 12,154 lines), 2026-11-28 ~04:0x IST:
TASK-DB-006 reads CLAIMED/muse_14 — the known WATCH244 error (board PR #2213 flipped it to M14 before the BE 03:42 post was read); the owner correction (muse_14 → muse_17) rides WATCH245's board PR. No competing claim on the hub through comment 7229381548.

## Source state (live probe, IntelX-Server S6, 2026-11-28 ~04:0x IST)

- Host `ip-172-26-4-138`, workspace `/opt/friday_universe`, disk 58G / 7.0G used / 51G avail (13%).
- Source `/opt/friday_universe/Futuris/data/storage/`: **94M**, **1,410 UUID snapshot dirs**, 0 top-level files, **1,410 parquet files** (one per dir). Sample: `snapshot_checkout_requests_per_minute_20261126T103301Z.parquet`.
- Live writes confirmed: count grew 1,406 → 1,407 → 1,410 across three probes minutes apart; newest dir mtime Nov 27 22:34 UTC; oldest Nov 20 18:48.
- Growth vs the DB-003 audit (Nov 25): 54M / 805 dirs → 94M / 1,410 dirs. The board record's figures are stale; the live counts above govern.
- No backup existed: `/var/backups/friday-universe`, `/opt/friday_universe/backups`, `Futuris/backups`, `Futuris/data/backups` all absent (matches DB-003: NO BACKUP).

## Dated backup (2026-11-27T22:36Z)

Created with `sudo` (bridge shell runs as `ubuntu`; `/var/backups` is root-owned). All under `/var/backups/friday-universe/` on IntelX-Server (S6), following the fleet-backup root convention from DB-003:

| Artifact | Size | Note |
|---|---|---|
| `futuris-storage-20261127T2236Z.tar.gz` | 64M | `tar --warning=no-file-changed -czf`, exit 0 |
| `futuris-storage-20261127T2236Z.tar.gz.sha256` | 133 B | `a09e8c60ab3132d4c1dc543089c59b64426331ed3993e3327b6180d37c3a3ea2` |
| `futuris-storage-20261127T2236Z.manifest.sha256` | 232K, 1,410 lines | per-file sha256 of the source snapshot (manifest A, pre-tar) |
| `futuris-storage-20261127T2236Z.files.txt` | 141K | sorted relative file list |

## Restore / read-back check (same run, live)

- Extracted the tarball to a temp dir on S6: extract exit 0, **1,410 parquet files restored**.
- `tar -tzf` listing: **1,410 parquet files** — matches the source snapshot exactly.
- `sha256sum -c` against manifest A: exit 0, **1,410/1,410 OK, 0 non-OK lines** — the restored tree is byte-identical to the source snapshot.
- Parquet magic on 3 restored samples: `head=PAR1 tail=PAR1` on all three.
- Restore temp dir removed after the check; S6 disk unchanged at 51G avail.

## Limits, stated plainly

- The backup is a **point-in-time snapshot** (2026-11-27T22:36Z). Futuris keeps writing (count grew during this run); the tarball does not track later snapshots.
- **No row-level parquet read was done:** `pyarrow` is not installed on S6. The read-back proof is byte-identical sha256 comparison of all 1,410 files plus PAR1 magic on 3 samples — not a row-count read.
- **No schedule was set:** this is a one-time dated backup. Whether it becomes a recurring timer (like the fleet backup, which itself has no schedule) is a coordinator decision, not part of this task.
- DB-002 wiring note: no coordinator ruling has been filed on whether DB-002 subsumes DB-006; the backup stands on its own until ruled otherwise.

## Verdict

TASK-DB-006 acceptance met: dated backup exists on S6 with a recorded sha256, and the restore/read-back check proves it byte-identical (1,410/1,410 files OK). No failing item. Paired verification requested — a different chat verifies the backup independently.

— Muse 17
