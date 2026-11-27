# TASK-REL-099 — Checkpoint 2: first-hand Server 2 disk + store-root facts (WATCH190 §4.2)

- **Task:** TASK-REL-099 — Git-style incremental fleet backup for Oracle Cloud (owner order 2026-11-26)
- **Owner:** Muse 12
- **Date:** 2026-11-27 ~06:00 IST
- **Branch:** muse12/task-rel-099-checkpoint-2
- **Base:** main `99dc0c90`
- **Why:** coordinator ruling WATCH190 §4.2 (hub #1483 comment 7206370654) — HOLD the placement move; "Muse 12 — file first-hand S2 disk usage + store-root facts; placement decision lands next run."

## 1. Method

- Read-only `run_shell` probes via the pre-existing local MCP client (`mcp_client.py`) against the FRIDAY bridge, server 2, no client change, no writes. Two probes ~2 minutes apart (00:28:38 UTC and ~00:30 UTC, 2026-11-27).

## 2. Disk headroom — UNSTABLE, both readings filed

| Probe (UTC 2026-11-27) | Size | Used | Avail | Use% |
|---|---|---|---|---|
| ~00:28:38 | 49G | 46G | **2.5G** | **95%** |
| ~00:30 | 49G | 44G | **5.3G** | **90%** |

- Same filesystem (`/dev/sda1`, `/`): a **2.8G swing within ~2 minutes**. Something on the box is churning disk live (writes/deletes). Neither reading can be quoted as the stable state; headroom is between 2.5G and 5.3G and moving.
- The current ~2.7 GB unified backup set does **not** safely fit in that headroom, and a first restic store run would need the set plus working room. **The HOLD on the placement move stands.**
- Context: earlier first-hand readings were 88% / 6.3G (checkpoint 56, ~02:00 IST) and 86% / 6.9G (REL-100, Nov 26) — the trend is up and now volatile. The 91% / 95% figures from other workers are consistent with this volatility, not a single stable number.

## 3. Store-root facts — NO store exists anywhere

- `/opt/friday_universe/backups` — does not exist.
- `/opt/friday_universe/backup*` — does not exist.
- `/srv/backups`, `/opt/backups` — do not exist.
- `/var/backups` — exists, but holds only system files (`alternatives.tar.*`, `apt.extended_states.*`, `dpkg.*`), 2.4M total. No `friday-universe` directory. The old script default `DEFAULT_OUT_ROOT = "/var/backups/friday-universe"` has no fleet content on S2.
- `/opt/friday_universe` itself is 5.0G (repo tree + agent dirs).
- `/tmp` is 3.9G; largest entries: `inf040-pilot` 640M, `web06-ship` 253M, `vyr083-rebase` 249M, `vyr071-rebase` 246M, `muse10-str077` 244M, `str070-fresh` 237M, `fut027-fresh` 234M, `frd042-fresh` 234M. (The stale-`/tmp` slice delete requested in REL-100 checkpoint 2 remains unanswered.)

## 4. Tool presence

- `restic`: **NOT installed** (`command not found`). The preferred store tool is absent; installability / install step is still owed before any restic store run.
- `rsync`: present, version **3.2.7**, protocol 31 (`/usr/bin/rsync`). The `--link-dest` fallback path is available.

## 5. What this decides / what it does not

- **Decides:** placement move stays HELD (WATCH190 §4.2); no store-root change, no first live store run this checkpoint. The ~2.7 GB set does not fit the measured headroom, and headroom itself is unstable.
- **Does not decide:** the placement itself (lands next run, per the ruling), the restic install route, or the /tmp cleanup (separate REL-100 request, still unanswered).
- **Next:** coordinator ruling on placement with these facts; restic installability check; re-measure headroom immediately before any store run.

## 6. Five states (honest)

- Implemented: YES (repo-side incremental design, checkpoint 1 merged as PR #1916)
- Tested: YES (repo-side; CI green on merge)
- Merged: YES (checkpoint 1, PR #1916, merge `1916` record on board)
- Deployed: NO (no store on any server)
- Production-verified: NO (first live store run held on this ruling)

No secrets, no self-merges. Read-only probes only; no live leg run beyond the probe.
