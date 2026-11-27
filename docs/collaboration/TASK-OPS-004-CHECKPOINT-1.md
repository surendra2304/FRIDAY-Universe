# TASK-OPS-004 — Checkpoint 1: Oracle Server 2 disk audit (read-only)

- Task: TASK-OPS-004 — Oracle Server 2 disk hygiene: audit largest growth paths, propose cleanup; delete nothing without hub clearance.
- Worker: Muse TP4. Branch: `musetp4/task-ops-004-disk-audit`, from main `bf3c76c9`.
- Audit window: 2026-11-27 ~06:00–06:13 IST. Method: read-only only (`df`, `du`, `ls`, `find -size`). No writes, no deletions, no service changes.

## Headline

- Root `/dev/sda1` (49G) is **90% full at steady state, 5.2G avail** — worse than 86% / 6.9G avail at 2026-11-26 15:53 IST.
- **Transient bulge observed this run:** disk read 95–96% full (46G used, 2.5G avail) during the audit, then returned to 90% (44G used, 5.2G avail) ~2 minutes later. About 2.8G appeared and vanished inside ~15 minutes. `/tmp`, `/var/log` and `/opt/friday_universe` were steady across the same window, so the writer is elsewhere and unidentified — likely another worker's live build/rebase activity (rel096 files were being written in `/tmp` at 06:08–06:11 IST). Flagged for the coordinator: the disk oscillates 90–96% and can sit 2.5G from full without warning.
- `df` readings this run: 90% (44G used, 5.3G avail) ~06:00 IST; 95% (46G, 2.5G) ~06:10 IST; 96% (46G, 2.5G) 06:11 IST; 90% (44G, 5.2G) 06:13 IST.

## Top growth paths (sizes first-hand)

| Path | Size | Note |
|---|---|---|
| `/swapfile` | 8.1G | Fixed system swap — not a candidate |
| `/opt` | 5.8G | incl. `/opt/friday_universe` 5.0G + `/opt/quarantine-2026-11-26` 846M |
| `/home/ubuntu` | 5.2G | incl. worktree `wt-muse10-rel088` 4.0G (Nov 24) |
| `/usr` | 3.9G | System |
| `/tmp` | 3.9G | Stale rebase/worktree/pilot dirs, ~3.1G in top 14 |
| `/snap` | 2.2G | incl. `/var/lib/snapd` 929M |
| `/var` | 1.9G | `/var/lib` 1.3G, `/var/log` 418M, `/var/cache` 175M |

- `/opt/friday_universe` 5.0G: `venv` 1.8G + `venv312` 1.6G (duplicate venvs), `FRIDAY` 723M, `Cortex` 279M, `Memora` 271M, `Stratex` 87M.
- `/tmp` top entries: `inf040-pilot` 640M, `web06-ship` 253M, `vyr083-rebase` 249M, `vyr071-rebase` 246M, `muse10-str077` 244M, `str070-fresh` 237M, `fut027-fresh` 234M, `frd042-fresh` 234M, `tp13-str093-rebase` 164M, `tp13-str092` 164M, `frd042-ui-build` 159M, `muse10-vyr070` 158M, `frd042-worktree` 157M, `frg002-libs` 127M.
- `/home/ubuntu` dot-dirs: `.cache` 551M, `.npm` 170M, `.local` 110M, `.deno` 92M. Visible top: `deno-2.2.0` 123M, `rel019-board` 84M, `wt-claude` 83M, `wt-claude-forge` 65M.
- `/var/lib`: `snapd` 929M, `apt` 325M, `dpkg` 42M. `/var/log` 418M (syslog 90M, active).
- Only file over 500M on the root filesystem: `/swapfile`.
- `/opt/quarantine-2026-11-26` (846M) holds a single entry, `tmp-old`.

## Proposed cleanup (NOT executed — hub clearance required)

| Candidate | Size | Clearance / owner check needed |
|---|---|---|
| `/tmp` stale dirs listed above | ~3.1G | Confirm none is a live worktree (several are dated Nov 26–27 and other workers are active in `/tmp` now) |
| `/home/ubuntu/wt-muse10-rel088` | 4.0G | Stale worktree, Nov 24 — confirm with Muse 10 before removal |
| `/opt/quarantine-2026-11-26/tmp-old` | 846M | Confirm what it holds and that quarantine is releasable |
| `venv` vs `venv312` (one duplicate) | ~1.6G | Confirm which venv is live before removing the other |
| `/var/lib/apt` cache | 325M | `apt-get clean` — low risk, still needs clearance |
| `/home/ubuntu/.cache` | 551M | Confirm no live build cache |

- Estimated reclaim if all approved: ~8.3G, taking the disk from ~90% to ~74% at steady state.
- Not candidates: `/swapfile` (system swap), `/usr`, `/var/log` (active syslog).

## Gaps / follow-ups

- Transient ~2.8G writer unidentified; recommend the coordinator watch for repeat bulges and name the writing process before any cleanup executes.
- Per-entry ages inside `/tmp` were not captured (names + sizes only); the cleanup run must re-check liveness per directory at execution time.
- One audit call timed out at 180s on the bridge during a full `/home/ubuntu` sweep; the follow-up call with per-directory timeouts completed.

## Next

- Await hub clearance on the proposed list (or an amended list from Muse). On clearance: execute only the approved paths, capture before/after `df`, file checkpoint 2.
- TASK-STR-074 stays parked (no live-leg clearance). TASK-DB-005 work PR #2029 MERGED this run; its board flip rides in the next consolidated board PR.
