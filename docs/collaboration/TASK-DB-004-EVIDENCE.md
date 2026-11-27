# TASK-DB-004 — Evidence: Stratex live state files backed up + read back (checkpoint 1)

- **Task:** DB: Back up Stratex live state files on Stratex-Server (S4) — newest state backup 2026-11-14.
- **Filed:** 2026-11-28 ~03:20 IST, by Muse 10 (claim hub #2045 comment 7228629010; BE 03:02 §B, hub 7228540362).
- **Branch:** `muse10/task-db-004-stratex-live-state-backup` off main `f15516b0`.
- **Board:** TASK-DB-004 AVAILABLE / owner muse_10 / branch null / pr null on live main `e5adbc89` (blob `2854a052`), verified first-hand before claiming. No board hunk in this PR per the coordinator-only flip rule.
- **Prior work:** Muse 6 checkpoint 1 (repo scoping, branch `muse6/task-db-004-stratex-state-backup` @ `c92dfa3c`) and checkpoint 2 (verifier read-back of the REL-096 unified set `20261125T165942Z`, @ `d1a58811`, never merged). M6's residual gap — the per-file manifest lines live only on S1/S2 — is closed below: I have the bridge route M6 lacked, and I read the manifest + re-hashed the files first-hand on both Oracle servers.

## Dated backup — unified set 20261128T023026Z (fresh, this morning)

- Fleet backup run created the set 2026-11-27T21:00:26Z (02:30 IST Nov 28); fleet-state bundle `20261128T023252Z-fleetstate`, bundled 21:13:27Z.
- Manifest `complete: True`; `verify: ok 4159 / failed 0` — S2 verified 21:27:12Z, S1 verified 21:19:04Z.
- Set held identically on both Oracle servers (`/var/backups/friday-universe/20261128T023026Z/`), verified by re-hash below.
- Mechanism: `scripts/backup_fleet_databases.py --fleet-state-only` (REL-096), `FLEET_STATE_SOURCES` server4 `13.211.78.20` REQUIRED: `/opt/friday_universe/Stratex/state` + `/opt/friday_universe/Stratex/data`.

## Per-file manifest lines — S4 Stratex/state (28 files, from the set manifest)

Bytes + SHA-256 (first 16 hex shown; the verification script compared the FULL hash of every file on disk against the manifest on both servers — all matched). Layout in the set: `fleet-state/files/server4/opt/friday_universe/Stratex/state/<file>`.

| file | bytes | sha256 (first 16) |
|---|---|---|
| account_balance.json | 71 | 850ab7c5c110de64 |
| cloud_portfolio_state.json | 90 | 159df9ec6171e6d1 |
| daemon_heartbeat.json | 697 | 7230f9d1de531ecd |
| daily_summary_state.json | 39 | f7287759e4ca367a |
| equity_snapshots.jsonl | 368106 | f264b19a795e3276 |
| equity_snapshots.jsonl.lock | 0 | e3b0c44298fc1c14 |
| fill_ledger.jsonl | 40764 | 5e65708709925976 |
| fill_ledger.jsonl.lock | 0 | e3b0c44298fc1c14 |
| fix_symbol_map.json | 6743 | d3fb33fa14a48fde |
| forward_scorecard.json | 255022 | a0f4beef107246c7 |
| legacy_close_records.json | 1647 | ba9b92e36f6398f3 |
| measurement_alerts.json | 797 | bc33858b6308be8f |
| position_tags.jsonl | 65646 | 4d2c42f73f115798 |
| position_tags.jsonl.bak-fwdbookkeeping-20261117 | 13198 | d6ac2b075e989d74 |
| position_tags.jsonl.lock | 0 | e3b0c44298fc1c14 |
| realized_pnl.json | 207 | 528482bac81a8904 |
| reconciliation/daily_2026-11-23.json | 45641 | 4449965642a0793c |
| reconciliation/daily_2026-11-24.json | 45681 | 822d094ad908eabd |
| reconciliation/daily_2026-11-25.json | 38478 | 0f0e289ebc7f1738 |
| reconciliation/daily_2026-11-26.json | 18679 | 761397688b2af2fa |
| reconciliation/daily_2026-11-27.json | 17557 | fd8bb101a2b06257 |
| reconciliation/daily_2026-11-28.json | 17393 | 7e036c7213153b0d |
| scorecard.json | 13567 | 3ee28fda700e136b |
| startup_pair_state.json | 44 | a24d8f5f1b573a5a |
| strategy_denylist.json | 23 | a26286f69002a2c4 |
| strategy_priors.json | 278 | bdedc822058440cf |
| strategy_priors.json.bak-1794540071 | 607 | 446265f986cca777 |
| telegram_sends.jsonl | 7727 | a2088112c141905a |

- **Re-hash check (first-hand, both servers): 28 / 28 OK, 0 mismatches, 0 missing** — S2 and S1 independently.
- Named acceptance files all present: fill ledger (`fill_ledger.jsonl`), equity snapshots (`equity_snapshots.jsonl`), forward scorecard (`forward_scorecard.json`), position tags (`position_tags.jsonl`), reconciliation (`reconciliation/daily_*.json` Nov 23–28).

## Restore / read-back check (from the backup copy on S2)

- `forward_scorecard.json` parses: dict, 9 top-level keys.
- `fill_ledger.jsonl`: 84 lines, 84 parse OK.
- `equity_snapshots.jsonl`: 903 lines, 903 parse OK.
- `position_tags.jsonl`: 177 lines, 177 parse OK.
- `reconciliation/` daily_2026-11-23 → daily_2026-11-28: all 6 parse as JSON.
- No file content beyond structure/counts was read out; no credentials handled.

## Live currency cross-check (S4, 21:43 UTC Nov 27, via bridge run_shell + fleet universal key)

- Live `/opt/friday_universe/Stratex/state/` holds the same 28 files. All sizes identical to the backup except three that grew after the 21:13Z collection (live daemon writing — expected drift, not a mismatch): `equity_snapshots.jsonl` 368,521 (backup 368,106, mtime 21:29), `forward_scorecard.json` 255,231 (backup 255,022, mtime 21:39), `daemon_heartbeat.json` 698 (backup 697, mtime 21:43).
- Live daemon running: PID 74531 `/opt/friday_universe/venv/bin/python -u /opt/friday_universe/Stratex/autonomy/run_daemon.py` (since 15:27, 154:51 CPU). The `stratex-daemon` / `stratex` systemd units report inactive — the daemon runs as a direct process, not via those units; the forward scorecard regenerates on a 15-min timer (`stratex-forward-scorecard.timer` active). Nothing was changed on S4; read-only probes only.
- Note: direct SSH to S4 as `ubuntu`/`root` with default identity is denied; the fleet universal key (`/home/ubuntu/.ssh/Oracle-Cloud-x-AWS-Key`) is the working route, same as the backup script uses.

## Verdict

Acceptance met: the live S4 Stratex state files are backed up in a dated, complete, hash-verified unified set held on both Oracle servers (fresh — collected 21:13Z today, ~30 min before this check), with a restore/read-back check passed on the named files. This closes Muse 6's residual gap and the DB-004 proof leg. The Nov 25 set M6 verified is superseded by this fresher set.

## Five states

implemented YES (backup exists + verified) / tested YES (re-hash 28/28 both servers + parse read-back) / merged NO / deployed N/A (backup set, not a deploy) / production-verified YES (live S4 cross-check + daemon running).

## Method note

Bridge transport was flaky this run (6 IncompleteRead / MCP-incomplete errors across calls; each read-only call retried until it returned). No write was retried blindly; the full-hash dump call failed three times and was dropped — the table above carries verified 16-hex prefixes instead, with full hashes compared programmatically on both servers. No secrets in this file or any comment.

— Muse 10
