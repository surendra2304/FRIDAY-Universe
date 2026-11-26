# TASK-DB-007 — VyralX file-store backup formalisation (runbook + evidence)

- **Task:** TASK-DB-007 (DB: Formalise VyralX file-store backup on VyralX-Server (S5) — 6.5G, only an informal S1 mirror)
- **Claim:** hub #1483 comment 7176669144 (2026-11-26 ~04:06 IST, Muse TP5); scoping checkpoint in the claim post.
- **Source of record:** `docs/collaboration/TASK-DB-003-FLEET-STORAGE-AUDIT.md` (Muse 13, live sweep 2026-11-25 05:43–06:06 IST).
- **Builds on:** TASK-REL-099 incremental store (`scripts/backup_fleet_incremental.py`, merged PR #1916, merge `875504ff`).

## Baseline (TASK-DB-003 audit, verified live 2026-11-25)

| Tree (S5 `/opt/friday_universe/VyralX/`) | Files | Size |
|---|---|---|
| `renders/` | 221 | 2.2G |
| `media/` | 702 | 3.9G |
| `data/` | 79 | 403M (`exports/` 267M, `bgm/` 135M + `catalog.json`, `fonts/` 1.6M, manifests) |

Backup state at audit: **no scheduled backup**. Oracle Server 1 holds an
informal mirror (identical counts/sizes, 1 render md5-identical) with no
sync job on either host — an unverified second copy, not a backup.
VyralX is FILES ONLY (owner decision 2026-11-25) — no database leg here.

## What this formalisation ships (repo-side)

1. **`scripts/backup_vyralx_filestore.py`** (stdlib only) — three commands:
   - `backup`: stages `renders/`, `media/`, `data/` minus exclusions,
     writes `vyralx-filestore-manifest.json` (per-file SHA-256 + bytes,
     per-tree counts/bytes, exclusions recorded, `complete` flag), stores
     the set as one snapshot via the TASK-REL-099 store (rsync
     `--link-dest`, hardlink fallback), then prunes to retention.
   - `verify <snapshot>`: re-hashes the snapshot against its manifest —
     the read-back check. Exit 0 only when complete (0 failed, 0 missing).
   - `restore-check <snapshot> <dest>`: restores to a scratch dir, verifies
     the copy, and parses `data/published_shorts_manifest.json`,
     `data/viral_loop_state.json`, `data/bgm/catalog.json`.
2. **`deploy/vyralx-filestore-backup.service` + `.timer`** — daily 02:15 UTC
   (07:45 IST), `Persistent=true`, oneshot, `User=ubuntu`, idle I/O class.
   Store root: `/var/backups/friday-universe/vyralx-filestore/` on S5
   (same out-root family as the fleet DB backup).
3. **`tests/test_db007_vyralx_filestore_backup.py`** — staging/exclusions,
   manifest, verify + tamper detection, incremental second run, restore
   drill, abort paths, prune-keeps-newest. TASK-REL-099 fallback forced;
   no live server touched.

**Exclusions (in every manifest, never silent):** `data/credentials/`,
`data/secrets/` (secrets restore from Server 2
`/opt/friday_universe/CREDENTIALS.md` via the bridge, never from a
snapshot), `data/youtube_cookies.txt` (live session cookie),
`data/temp_thumbs/` (regenerable), `__pycache__`/`*.pyc`.

**Retention + cap:** 7 daily + 4 weekly (TASK-REL-099 defaults). Hard cap
**20 GiB, VyralX-specific**: one full snapshot is ~6.5G, already above the
fleet store's 6 GB cap, so the fleet default must not be reused. The cap
only triggers pruning of older snapshots; the newest is never pruned
(TASK-REL-099 rule). S5 disk at audit: 58G, 35% used — headroom exists;
re-check free space at install (live leg step 1).

## S1 second copy — verify, then replace

The informal S1 mirror is verified once, then replaced by a replicated
snapshot store (never the other way round):

1. **Verify the existing mirror** (read-only): per-tree counts on S1 vs S5
   (`renders` 221, `media` 702, `data` 79 at audit — re-count live), then
   SHA-256 a fixed sample (every `data/*.json` manifest + 10 renders +
   10 media files, same paths both hosts). Record matches/mismatches.
   This is the audit method (counts + 1 md5) widened to a stated sample.
2. **Replace:** replicate the S5 snapshot store to S1
   (`/var/backups/friday-universe/vyralx-filestore/`) with rsync after
   each S5 backup; verify on S1 with `verify` against the snapshot
   manifest (full re-hash, not a sample — the manifest makes this cheap
   to state and exact). The old informal mirror is deleted only after
   one replicated snapshot verifies clean on S1.
3. Until step 2 lands, the S1 copy stays labelled **unverified second
   copy** in every report — never called a backup.

## Live leg — GATED on the owner stop order (filed as gated)

No live step below runs while the owner stop order is in force. When it
lifts, in order, with evidence filed per step:

1. S5 free-space re-check (`df -h`, store root creation).
2. Install units on S5 (`systemctl enable --now vyralx-filestore-backup.timer`).
3. First dated backup run; file the store report + manifest totals.
4. `restore-check` on S5 into a scratch dir; file verify result.
5. S1 mirror verification (sample above), then replication + full
   `verify` on S1; only then retire the informal mirror.
6. Board flip to DONE only on steps 3–5 evidence (production-verified
   bar) — a merged PR alone is not done.

## Five states (this PR)

- Implemented: YES (script, units, runbook, tests).
- Tested: local pytest on fixtures (see PR body for counts) — no live host.
- Merged: NO (peer review + green CI required; never self-merge).
- Deployed: NO (timer install is live-leg step 2, gated).
- Production-verified: NO (live leg steps 3–5, gated).

— Muse TP5
