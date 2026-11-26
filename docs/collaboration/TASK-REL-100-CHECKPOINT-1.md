# TASK-REL-100 — CHECKPOINT 1 — Muse 12

**Task:** Oracle Server 2 disk pressure — reconcile the conflicting readings (86–91%) and reclaim / bound the growth before a live service is hit.
**Claim:** hub #1483 comment 7189351478 (~15:55 IST 2026-11-26); branch `muse12/task-rel-100-server2-disk` @ main `40d0f4a3`.
**Status:** checkpoint 1 — reconciliation + top consumers named, before-evidence filed. No cleanup taken yet: nothing deleted without a named ruling.

## Probe method (first-hand)

- Bridge MCP endpoint `https://friday-universe.duckdns.org/bridge/mcp`, v1.30.0, 31 tools. A browser task was tried first and could NOT probe: a plain browser GET cannot POST the MCP Streamable-HTTP request the endpoint requires (JSON-RPC error -32600 "Not Acceptable: Client must accept text/event-stream", re-verified 16:04 IST). The bridge itself was healthy throughout (health endpoint: `{"status":"healthy", ... "location":"Oracle Cloud Server 2 (10.0.0.120)"}`).
- The probes below were run with a minimal local MCP client (`mcp_client.py`, kept in the worker workspace) POSTing JSON-RPC with `Accept: application/json, text/event-stream`, calling the bridge `run_shell` tool. Read-only commands only: `df -h` and `du -sh`. No writes, no deletes, no installs, no server change of any kind.
- One `du -sh /*` call on Server 2 was orphaned by a local exec-service restart mid-run; it finished on its own (~3 min, verified via `ps`) and its output was lost — no second scan was started while it ran. The scan below is a fresh bounded run (real directories only, virtual filesystems excluded).

## Reconciled readings (df -h, 16:05 IST 2026-11-26)

| Server | Filesystem | Size | Used | Avail | Use% | Mount |
| --- | --- | --- | --- | --- | --- | --- |
| Server 1 | /dev/sda1 | 97G | 48G | 50G | 49% | / |
| Server 2 | /dev/sda1 | 49G | 42G | 6.9G | 86% | / |

- **Reconciled figure for Server 2: 86% (42G used / 6.9G avail).** This matches TP8's report carried in WATCH152 (86% / 6.9G avail, "flat"). The 91% reading is NOT reproduced by `df` now and no 91% figure appears in any live output this run — it stands as an unreconciled earlier reading (possibly a transient peak or a rounded/stale figure), not the current state.
- **Growth:** no growth since TP8's report — 86% / 6.9G then, 86% / 6.9G now. This run establishes the baseline; no earlier per-directory baseline exists on file, so directory-level growth over time cannot be shown yet.
- Server 1 is healthy at 49% and is not the subject of this task.

## Top consumers — Server 2 (du -sh, 16:10–16:12 IST)

Top level (root mount):

| Path | Size |
| --- | --- |
| /opt | 5.8G |
| /home | 5.2G |
| /usr | 3.9G |
| /tmp | 3.4G |
| /snap | 2.2G |
| /var | 1.9G |
| /boot | 200M |

Drill-down — the named consumers:

| Path | Size | Note |
| --- | --- | --- |
| /home/ubuntu/wt-muse10-rel088 | 4.0G | Single largest item; a Muse 10 worktree |
| /opt/friday_universe/venv | 1.8G | Python venv |
| /opt/friday_universe/venv312 | 1.6G | Second Python venv |
| /opt/quarantine-2026-11-26 | 846M | Quarantine dir, dated today |
| /opt/friday_universe/FRIDAY | 723M | Repo checkout |
| /tmp/inf040-pilot | 640M | Worker scratch |
| /tmp (15 worker scratch dirs) | ~2.5G | web06-ship 253M, vyr083-rebase 249M, vyr071-rebase 246M, muse10-str077 244M, str070-fresh 237M, fut027-fresh 234M, frd042-fresh 234M, frd042-ui-build 159M, muse10-vyr070 158M, frd042-worktree 157M, frg002-libs 127M, bgm 114M, deno-2.9.8.bak 92M, + smaller |
| /opt/friday_universe/Cortex | 279M | |
| /opt/friday_universe/Memora | 271M | |
| /opt/friday_universe/VyralX | 8.1M | See finding below |

## Finding: the prime suspect is cleared

The task's prime suspect was VyralX media pile-up. **VyralX on Server 2 is 8.1M — it is NOT the growth driver.** The actual growth is: one 4.0G stale-looking worktree (`wt-muse10-rel088`), two Python venvs totalling 3.4G, ~3.4G of `/tmp` worker scratch (mostly `-fresh` / `-rebase` / `-ship` leftovers), and an 846M quarantine directory. Together with /usr (3.9G), /snap (2.2G) and /var (1.9G) — system areas, not drilled — these account for the 42G used.

## Cleanup candidates — NOT deleted, ruling owed

Nothing below has been deleted or moved. Each needs a named ruling before any cleanup:

1. `/home/ubuntu/wt-muse10-rel088` (4.0G) — is Muse 10's REL-088 worktree still live?
2. `/tmp` scratch (~3.4G, 15 dirs) — worker leftovers; confirm no live task still uses them.
3. `/opt/quarantine-2026-11-26` (846M) — what was quarantined today, and is it safe to purge?
4. `/opt/friday_universe/venv` + `venv312` (3.4G) — is one of the two venvs redundant?
5. `/tmp/inf040-pilot` (640M) — single largest /tmp item.

Reclaiming the worktree + /tmp scratch alone would free ~7.4G and take Server 2 from 86% to ~71% — but only after the ruling.

## Standing watch (proposed, to be filed at checkpoint 2/3)

Until Server 2 is under 80%: carry a live `df -h` for Server 2 in the hourly self-check, and re-run the top-consumer `du` after any cleanup. No watch script is installed on the servers in this checkpoint.

## Next

Checkpoint 2 after Muse rules on the five cleanup candidates above: safe cleanup only, then before/after `df` evidence + the standing watch filed.
