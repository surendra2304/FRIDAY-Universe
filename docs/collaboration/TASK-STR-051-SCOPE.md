# TASK-STR-051 — Forward-window fills audit run 2: scope (draft, repo-side only)

- **Task:** TASK-STR-051 — reconcile the daemon fill ledger against venue history for the new window. Follow-up to STR-048.
- **Claim:** hub #1483 comment 7131989527 (2026-11-24 ~18:20 IST); branch `muse8/task-str-051` from main `ce5c1bd4`. Board on main `4e2a14be` still AVAILABLE / owner muse_8 — the AVAILABLE→CLAIMED flip rides in tomorrow's consolidated board PR per the 21:37 watch spec.
- **Acceptance (board):** fills, closes and net P&L filed for the new window with venue reconciliation.
- **Grant:** coordinator watch 7137288514 (21:17 run) — scoped read-only S1 probe granted on the STR-054 precedent: read the S1 ledger at `/opt/friday_universe/Stratex/state/fill_ledger.jsonl` via the daemon's repository layer + venue signed GETs, read-only throughout, keys in-memory on S1 only, no writes/moves/deploys. No live leg beyond the probe.
- **Status of this draft:** repo-side scoping only. The live probe leg was NOT executed this run — see §4.

## §1 — Window (proposed; to be confirmed by the probe read)

- **New window opens where STR-048 closed it:** exits after the STR-048 audit read, **2026-11-23T13:42:51Z**.
- **Opening counter:** heartbeat counter at the STR-048 audit read = **+130.27280441 USDT** (baseline 134.79416134 + post-reset ledger nets −4.52135693), verified at three anchors in STR-048 §1.
- **Known first rows of the new window (from STR-048 §1/§2):** AVAX close 2026-11-23 13:57:01Z, ADA close 13:58:24Z (−10.19941296, venue-verified in STR-048 §3), then DOT / ATOM / ADA closes after the audit read. The probe read must enumerate every exit after 13:42:51Z; the window closes at the new audit read time, which the probe records.
- **Construction to re-derive (STR-048 §1):** counter = carried pre-reset baseline 134.79416134 + Σ post-reset ledger nets. The new window's net is the counter step across the window; the baseline must stay consistent at the STR-048 audit anchor and the new audit anchor — if it does not, the gap is a finding, not a rounding.

## §2 — Method (STR-048 + STR-044, both on main)

- **Ledger:** append-only `Stratex/state/fill_ledger.jsonl`, one row per CLOSED trade, strategy-tagged (`Stratex/measurement/fill_ledger.py`; paths follow `STRATEX_STATE_DIR` else `Stratex/state/`). Rows are never edited; corrections are new rows.
- **Recurring reader:** `Stratex/scripts/daily_fill_ledger_reconciliation.py` (TASK-STR-044, merged) — ledger read end-to-end with forward-window slice; venue read with signed GETs only (account, open positions, user trades, income, all orders); row-by-row match (side, qty, VWAP, time) into BOTH / ENTRY_ONLY / EXIT_ONLY / NO_MATCH; venue closes with no ledger row, with realized P&L; equity walk split at detected faucet resets; forward-window state filed as a dated JSON report in `Stratex/state/reconciliation/daily_YYYY-MM-DD.json`. The timer (`friday-stratex-reconciliation.timer`, daily 01:00 UTC, S1) runs it from the deployed checkout — dated reports for the new window may already exist on S1; the probe checks.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519, `LIVE_TRADING_ENABLED` unset). Signed GETs only (`/fapi/v1/userTrades` via the merged STR-044 reader, `DemoFuturesReader`). No order placed, cancelled or modified; the ledger is never written. Keys in-memory on S1 only, never printed or stored.
- **Matching rule (STR-043/STR-044):** ledger rows carry no `order_id`, so match by symbol + side + qty + price + time. Split fills: recompute from the two-fill VWAP, not the stored single exit price (STR-048 §3–§4: ADA $0.1122 / NEAR $0.0300 apparent gaps were VWAP artefacts, not errors).
- **Checks to file:** (1) trade-by-trade table for every exit in the window (exit, symbol, side, qty, net, running sum, implied counter); (2) baseline consistency at both anchors; (3) venue fill-level verification of the key closes (entry + exit legs, quantities, VWAP, commission, order IDs); (4) price-move recomputation of every row's gross/net; (5) venue closes with no ledger row, with realized P&L.

## §3 — Carried gaps to re-check in the new window

- **STR-043 G1 (ledger-vs-venue gap, already filed):** 34 venue closes with no ledger row, +26.5927 USDT — 30 Nov-19 post-reset micro-closes (−1.6023) plus 4 real closes: ETH +19.9399 (2026-11-20), SUI +30.5009 (2026-11-21), VET −10.9206 (2026-11-21), SAND −11.3252 (2026-11-22). The counter is ledger-derived and inherits this blind spot (STR-048 §5). Run 2 must check whether any further venue closes in the new window lack ledger rows, and whether the 4 real closes recur.
- **Reset-wipe rows:** the 30 Nov-19 07:36–07:42Z rows recorded at net 0.0 by design (STR-043 §3) stay outside the new window; they contribute 0.00 and must not be re-counted.

## §4 — Block: live probe leg NOT executed — BOTH routes now blocked

- The grant (watch 7137288514) stands, but the only route used for the MEM-025 precedent — the scope-guarded bridge `run_shell` client — was refused this run by a runtime safety flag on the route's own script pattern. No probe was executed, no live read was taken, nothing was sent to any server. This is a route block, not a grant block.
- **Ruling received (watch 7138466832, 21:57 run, ruling 4):** route replaced — use bridge `read_file`/`read_text` for the specific S1 paths (fill_ledger.jsonl, heartbeat, realized_pnl, dated reconciliation reports). "If that route is also blocked, report it and stop; do not improvise another route."
- **Read_file route attempted 2026-11-24 ~23:16–23:30 IST — BLOCKED:** bridge access proven (Server 2, both Oracle servers ONLINE); read_file controls work (CREDENTIALS.md header, WORK_BOARD.yaml). All S1 paths fail: `Stratex/state/fill_ledger.jsonl` "File not found", `Stratex/state/heartbeat.json` "File not found", `Stratex/state` + `Stratex/state/reconciliation` "Directory not found". The bridge workspace is Server 2's /opt/friday_universe; S1 state is not in it. Repo tree on main 6e3fe049 holds no `Stratex/state/` data files either (code + STR-048 doc only). Evidence: ~/workspace/muse8/str-051/probe_readfile_2026-11-24.md. Per the ruling I stopped; no other route improvised.
- **Ruling requested from Muse:** a route that reaches S1 state, or S1 state filed into the repo, or another route Muse names. Window bounds + row counts remain UNVERIFIED.
- **Ruling received (watch 7140957093, 2026-11-25 ~00:2x IST):** S1-state pull assigned to **Muse 13** — pull `fill_ledger.jsonl`, `heartbeat.json` and the reconciliation dir from Oracle Server 1 Stratex state via bridge run_shell (server 1), file as evidence for STR-051; if the server-1 route fails, report the exact error, do not improvise another route. **M8 holds STR-051 and files what it has.** This scope doc + the read_file probe evidence are filed on branch `muse8/task-str-051` this run (2026-11-25 ~00:16 IST) per that instruction. The probe leg itself awaits M13's pull.
- **Not a stall:** the grant arrived 21:42 IST; both ruled routes were attempted and both are blocked by the runtime/bridge, not by inaction. Repo-side scoping is filed here; the probe follows the next ruling.

## §5 — Queue / states

- **Queue:** STR-051 (head; S1 pull assigned to M13 per watch 7140957093 — M8 filed scope + probe evidence on branch `muse8/task-str-051` 2026-11-25 ~00:16 IST; probe leg awaits M13's pull) → STR-047 (IN_PROGRESS, wiring leg held under the owner stop order ~16:42 IST + coordinator clearance owed).
- **STR-047:** checkpoint 1 merged (PR #1663, merge 8034ab1f, 17:28 IST). S1 `STRATEX_STRATEGY_ALLOWLIST` append still needs coordinator clearance; no live change.
- **VAL-009:** unchanged; no third re-probe until FRD-042 deploy confirmed live. Flag 7112983747 stays open, no action.
- **Five states (STR-051):** implemented NO / tested NO / merged NO / deployed N/A / production-verified NO — scope drafted repo-side only; no live evidence yet.

— Muse 8, 2026-11-24 ~22:30 IST
