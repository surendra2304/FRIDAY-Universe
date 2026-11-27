# TASK-REL-099 — Checkpoint 2: first-hand Server 2 disk + store-root facts (WATCH190 §4.2)

- **Task:** TASK-REL-099 — Git-style incremental fleet backup for Oracle Cloud (owner order 2026-11-26)
- **Owner:** Muse 12
- **Date:** 2026-11-27 ~06:00 IST
- **Branch:** muse12/task-rel-099-checkpoint-2
- **Base:** main `99dc0c90`
- **Why:** coordinator ruling WATCH190 §4.2 (hub #1483 comment 7206370654) — HOLD the placement move; "Muse 12 — file first-hand S2 disk usage + store-root facts; placement decision lands next run."
- **Amendment 2026-11-27 ~09:00 IST:** §3 corrected per paired-verifier Muse 9 NEEDS WORK (PR comment 7207388141, ~07:02 IST) and Muse 12's own re-probe 08:59 IST — `/var/backups/friday-universe` EXISTS (see §3). The original "NO store exists anywhere" claim is withdrawn. Placement HOLD stands, endorsed by the verifier.

## 1. Method

- Read-only `run_shell` probes via the pre-existing local MCP client (`mcp_client.py`) against the FRIDAY bridge, server 2, no client change, no writes. Two probes ~2 minutes apart (00:28:38 UTC and ~00:30 UTC, 2026-11-27), plus a re-probe 03:29 UTC (08:59 IST) for the §3 correction.

## 2. Disk headroom — UNSTABLE, all readings filed

| Probe (UTC 2026-11-27) | Size | Used | Avail | Use% |
|---|---|---|---|---|
| ~00:28:38 | 49G | 46G | **2.5G** | **95%** |
| ~00:30 | 49G | 44G | **5.3G** | **90%** |
| 03:29 (08:59 IST, re-probe) | 49G | 44G | **5.0G** | **90%** |

- Same filesystem (`/dev/sda1`, `/`): a **2.8G swing within ~2 minutes**. Something on the box is churning disk live (writes/deletes). Neither reading can be quoted as the stable state; headroom is between 2.5G and 5.3G and moving. The 03:29 reading (5.0G) confirms the verifier's independent 5.0G / 5.2G readings (~07:02 IST).
- The current ~2.7 GB unified backup set does **not** safely fit in that headroom, and a first restic store run would need the set plus working room. **The HOLD on the placement move stands.**
- Context: earlier first-hand readings were 88% / 6.3G (checkpoint 56, ~02:00 IST) and 86% / 6.9G (REL-100, Nov 26) — the trend is up and now volatile. The 91% / 95% figures from other workers are consistent with this volatility, not a single stable number.

## 3. Store-root facts — CORRECTED: an unreadable store directory exists

- `/opt/friday_universe/backups` — does not exist.
- `/opt/friday_universe/backup*` — does not exist.
- `/srv/backups`, `/opt/backups` — do not exist.
- `/var/backups/friday-universe` — **EXISTS** (root-owned 0755; birth 2026-11-16 05:54 IST per verifier probe; directory mtime 2026-11-27 08:23 IST). It holds root-only (`drwx------`) snapshot directories created today. First-hand re-probe 2026-11-27 03:29 UTC / 08:59 IST listed: `20261127T061510Z`, `20261127T070423Z`, `20261127T070433Z-fleetstate`, `20261127T075219Z`, `20261127T075449Z-fleetstate` (newest 08:19 IST).
- The snapshot set churns: the verifier's 07:02 IST probe listed `20261127T035233Z`, `20261127T054144Z`, `20261127T054842Z-fleetstate`, `20261127T061510Z`, `20261127T061521Z-fleetstate`, `20261127T070208Z` — by 08:59 IST all but `061510Z` were gone and four new ones had appeared. A backup job is actively writing AND pruning there.
- Snapshot contents are **UNREADABLE to the bridge user** (root-only directories), so fleet content and true store size are **UNVERIFIED**.
- The original claim "No `friday-universe` directory" / "NO store exists anywhere" was **WRONG and is withdrawn**. Correct statement: no READABLE store exists at the checked paths; an unreadable, actively-written store may exist at `/var/backups/friday-universe`.
- `/var/backups` `du` total 2.4M **EXCLUDES** the unreadable snapshots — it covers only the system files.
- `/opt/friday_universe` itself is 5.0G (repo tree + agent dirs).
- `/tmp` is 3.9G; largest entries: `inf040-pilot` 640M, `web06-ship` 253M, `vyr083-rebase` 249M, `vyr071-rebase` 246M, `muse10-str077` 244M, `str070-fresh` 237M, `fut027-fresh` 234M, `frd042-fresh` 234M. (The stale-`/tmp` slice delete requested in REL-100 checkpoint 2 remains unanswered.)

## 4. Tool presence

- `restic`: **NOT installed** (`command not found`). The preferred store tool is absent; installability / install step is still owed before any restic store run.
- `rsync`: present, version **3.2.7**, protocol 31 (`/usr/bin/rsync`). The `--link-dest` fallback path is available.

## 5. What this decides / what it does not

- **Decides:** placement move stays HELD (WATCH190 §4.2); no store-root change, no first live store run this checkpoint. The ~2.7 GB set does not fit the measured headroom, and headroom itself is unstable. The HOLD is endorsed by paired verifier Muse 9 (NEEDS WORK 7207388141); the §3 correction strengthens it — an unknown, actively-written store already occupies the same tight disk.
- **Does not decide:** the placement itself (lands next run, per the ruling), the restic install route, or the /tmp cleanup (separate REL-100 request, still unanswered). Also not decided: what the unreadable `/var/backups/friday-universe` snapshots contain, or which job writes them — coordinator/owner call; the contents need a root read, not a bridge-user probe.
- **Next:** coordinator ruling on placement with these facts; restic installability check; re-measure headroom immediately before any store run.

## 6. Five states (honest)

- Implemented: YES (repo-side incremental design, checkpoint 1 merged as PR #1916)
- Tested: YES (repo-side; CI green on merge)
- Merged: YES (checkpoint 1, PR #1916, merge `1916` record on board)
- Deployed: NO (no store on any server)
- Production-verified: NO (first live store run held on this ruling)

No secrets, no self-merges. Read-only probes only; no live leg run beyond the probe.
