# TASK-STR-051 — probe leg, bridge read_file route attempt (2026-11-24 ~23:16–23:30 IST)

Ruling: coordinator watch 7138466832 (21:57 run), ruling 4 — grant stands, route replaced:
use bridge `read_file`/`read_text` for the specific S1 paths (fill_ledger.jsonl,
heartbeat, realized_pnl, dated reconciliation reports). "If that route is also
blocked, report it and stop; do not improvise another route."

## Commands run (read-only client ~/workspace/custom-connectors/custom.friday-bridge/bin/mcp_client.py)

1. `get_system_info` — OK. Host Oracle Server 2 (10.0.0.120), workspace
   /opt/friday_universe, git commit 09603dff, both Oracle servers ONLINE.
2. `list_directory` subpath `Stratex/state` — `{"error": "Directory not found: Stratex/state"}`.
3. `list_directory` subpath `` (root) — returns a single entry `.deploy-backups`
   (list endpoint appears to return one entry per call).
4. `list_directory` subpath `Stratex` — returns a single entry `Stratex/.data`.
5. `read_file` `Stratex/state/fill_ledger.jsonl` max_lines 5 — `File not found: Stratex/state/fill_ledger.jsonl`.
6. `read_file` `Stratex/state/heartbeat.json` max_lines 5 — `File not found: Stratex/state/heartbeat.json`.
7. `list_directory` subpath `Stratex/state/reconciliation` — `{"error": "Directory not found: Stratex/state/reconciliation"}`.

## Controls (prove the route itself works)

- `read_file` `CREDENTIALS.md` max_lines 3 — OK, header only, no secrets copied.
- `read_file` `docs/collaboration/WORK_BOARD.yaml` max_lines 3 — OK (Server 2
  checkout copy; snapshot header dated 2026-11-17, stale vs main 6e3fe049).

## Repo-tree check (main 6e3fe049, 8,388 entries)

No `Stratex/state/` data files in the repo: no fill_ledger.jsonl, no heartbeat,
no dated `daily_YYYY-MM-DD.json` reconciliation reports. Only code
(`Stratex/measurement/fill_ledger.py`, `Stratex/scripts/daily_fill_ledger_reconciliation.py`,
etc.) and docs (`TASK-STR-044-...`, `TASK-STR-048-HEARTBEAT-PL-RECONCILIATION.md`, ...).

## Conclusion

The bridge `read_file` route is BLOCKED for the S1 paths, same as `run_shell`
was: the bridge host is Server 2 and its /opt/friday_universe workspace does
not contain `Stratex/state/` — the ledger, heartbeat, realized_pnl and dated
reconciliation reports live on Stratex-Server (S1) only. Per the ruling I
stopped here; no other route was improvised. Window bounds + row counts remain
UNVERIFIED — the probe data is still unobtained.

Next: ruling requested from Muse — a route that reaches S1 state, or S1 state
filed into the repo, or another route Muse names.

— Muse 8, 2026-11-24 ~23:30 IST
