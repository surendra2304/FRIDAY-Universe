# TASK-DB-013 — S2 headroom + store-root facts re-probe (checkpoint 1)

- **Task:** TASK-DB-013 (P1) — Fleet: S2 headroom + store-root facts re-probe (follow-up REL-099/DB-010/DB-012)
- **Worker:** Muse TP6. **Coordinator:** Muse. **Owner:** Surendra.
- **Date:** 2026-11-28 ~10:05 IST
- **Claim:** hub #2045 comment 7233869168 (2026-11-28 ~09:46 IST); branch `musetp6/task-db-013-headroom-reprobe` @ main `5de10dbf`.
- **Board basis at claim:** AVAILABLE, owner muse_tp6, branch null, pr null — assigned to TP6 as queue position 3 by coordinator watch201; verdict column 9 awaiting per WATCH254 correction (hub 7233848712) — under the 10-cap.
- **Work PR:** opened on this branch (number filled on filing; see board record).

## 0. Method

- Read-only `run_shell` probes via the Friday Bridge against Oracle Server 2, no writes, no restarts, no deploys. Standing run_shell clearance: WATCH180 §2(b) (owner tap 2026-11-26 18:25:56 IST; clarification 7200651240; standing clearance 7200564540), restated fleet-wide in BE 09:30 §C (ruling 7192682851, correction 7197725825, burn order 7200414167). Same method as REL-099 checkpoint 2 (Muse 12, 2026-11-27).
- Two probes: probe A (disk + memory + load, 2026-11-28 04:17:35 UTC / 09:47:35 IST) and probe B (store roots + sizes, ~09:48 IST). Bridge `get_system_info` first-hand this run: both Oracle servers ONLINE, Server 2 git `69ff042b` (branch musetp4/task-frg-036-rerun3-evidence).
- No secrets, no self-merges. All numbers below are first-hand from these probes unless marked otherwise.

## 1. Disk headroom — 6.2G avail, 88% used, ABOVE the 10% line

Probe A, `df -h /`, 2026-11-28 09:47:35 IST:

| Filesystem | Size | Used | Avail | Use% | Mounted on |
|---|---|---|---|---|---|
| /dev/sda1 | 49G | 43G | **6.2G** | **88%** | / |

- Free space is **12.7%** — above the 10% headroom threshold that governs any write. A write is not threshold-blocked at this reading.
- Trend (first-hand readings, same filesystem `/dev/sda1`, `/`):

| When | Used | Avail | Use% | Source |
|---|---|---|---|---|
| 2026-11-26 (REL-100) | — | 6.9G | 86% | REL-099 checkpoint 2 §2 context |
| 2026-11-27 ~02:00 IST (checkpoint 56) | — | 6.3G | 88% | REL-099 checkpoint 2 §2 context |
| 2026-11-27 ~05:58 IST | 46G | 2.5G | 95% | REL-099 checkpoint 2 (probe 1) |
| 2026-11-27 ~06:00 IST | 44G | 5.3G | 90% | REL-099 checkpoint 2 (probe 2) |
| 2026-11-27 08:59 IST | 44G | 5.0G | 90% | REL-099 checkpoint 2 (re-probe) |
| **2026-11-28 09:47 IST** | **43G** | **6.2G** | **88%** | **this probe** |

- Headroom is volatile: REL-099 recorded a 2.8G swing within ~2 minutes on 2026-11-27. Today's 6.2G is the best reading since 2026-11-26, but a single reading is not a stable state — **re-measure immediately before any store run or large write**.
- The M16 DB-010/DB-012 held-leg figure of 6% headroom is now stale: free space today is 12.7%.
- The ~2.7 GB unified backup set (REL-099 §2) fits inside today's 6.2G headroom with working room, but only just, and only at this reading — the placement decision stays the coordinator's; this re-probe supplies fresh numbers, it does not lift the REL-099 placement HOLD by itself.

## 2. Memory headroom

Probe A, `/proc/meminfo` head, 2026-11-28 09:47:35 IST:

| Field | Value |
|---|---|
| MemTotal | 979412 kB (~956 MB) |
| MemFree | 115084 kB (~112 MB) |
| MemAvailable | 298196 kB (~291 MB) |
| Buffers / Cached | 45696 kB / 245076 kB |

- Load average 0.07 / 0.08 / 0.22; uptime 36 days 15:21. Memory headroom is thin (~291 MB available) but stable versus the 2026-11-28 morning readings (~286–313 MB available).

## 3. Store-root facts — one unreadable, actively-written store; no readable store

Probe B, ~09:48 IST:

| Path | Result |
|---|---|
| `/opt/friday_universe/backups` | Does not exist |
| `/srv/backups` | Does not exist |
| `/opt/backups` | Does not exist |
| `/var/backups/friday-universe` | **EXISTS** — root-owned 0755, mtime 2026-11-28 09:26 IST |
| `/var/backups` | Exists (root-owned 0755) |

`/var/backups/friday-universe` listing (first-hand, ~09:48 IST) — 5 snapshot directories, all root-only (`drwx------`), contents **UNREADABLE** to the bridge user:

| Snapshot | mtime (IST) |
|---|---|
| `20261128T065351Z` | 07:24 |
| `20261128T080508Z-fleetstate` | 08:17 |
| `20261128T080709Z` | 08:30 |
| `20261128T085945Z-fleetstate` | 09:11 |
| `20261128T090145Z` | 09:22 |

- The set churns: all five snapshots are from today, and the set differs from REL-099's 2026-11-27 listing — a backup job is actively writing AND pruning there. What the snapshots contain, and their true size, remain **UNVERIFIED** (needs a root read, not a bridge-user probe).
- `/opt/friday_universe` itself: **4.9G** (was 5.0G in REL-099).
- `/tmp`: readable portion **668M** (was 3.9G in REL-099 — the stale-`/tmp` slice is largely gone). Six `systemd-private-*` / `snap-private-tmp` directories were unreadable (Permission denied), so the true `/tmp` total is **>= 668M**; the probe exited 1 on those permission errors only — the sizes above are unaffected.

## 4. What this decides / what it does not

- **Decides:** the fresh numbers. Disk headroom is 6.2G / 12.7% free — above the 10% threshold, so a write is not threshold-blocked at this reading; memory available ~291 MB; exactly one store root exists on S2 (`/var/backups/friday-universe`), unreadable, actively written; no readable store exists at any checked path.
- **Does not decide:** the REL-099 placement HOLD (coordinator's call, on these numbers); what the unreadable snapshots contain or which job writes them; the restic install route (`restic` presence not re-checked this run — REL-099 found it NOT installed); the /tmp cleanup (separate REL-100 request).
- **Carried note:** WATCH249 §D attributed a "TP6 06:48 probe: 7.4G avail" to this account; TP6 holds no record of such a probe and does not claim it. Today's first-hand figure is 6.2G avail at 09:47 IST. The conclusion drawn from it (above the 5G line) is consistent with today's reading.

## 5. Five states (honest)

- Implemented: YES (re-probe executed, numbers filed here)
- Tested: N/A (read-only probes; no code change in this PR)
- Merged: NO (this PR awaiting paired verdict + coordinator merge)
- Deployed: NO (no store run, no placement change)
- Production-verified: NO (verification is the paired verifier's first-hand re-probe, not this filing)

No secrets, no self-merges. Read-only probes only; no live leg run beyond the probe.
