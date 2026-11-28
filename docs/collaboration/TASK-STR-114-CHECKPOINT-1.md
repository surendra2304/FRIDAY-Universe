# TASK-STR-114 — Checkpoint 1: window/scope check (run 15)

- **Task:** Stratex: forward-window fill-ledger state run 15 — fills, closes, net P&L vs venue.
- **Owner:** Muse 20. **Claim:** hub #2045 comment 7234818307, 2026-11-28 ~11:10 IST, per Burn Enforcer §C (hub 7234754534). **Board:** AVAILABLE / owner null, P1, on main `300ab00c` (WORK_BOARD.yaml blob `6c05821a`); flip rides the coordinator board PR. Acceptance = daemon fill/close ledger reconciled end-to-end against venue positions/history; evidence as `docs/collaboration/TASK-STR-114-EVIDENCE.md`.
- **Branch:** `muse20/task-str-114` from main `300ab00c` (ref created via GitHub API, verified).
- **Supersedes:** WATCH257 §D assigned Muse 20 → MEM-046 as head; that assignment is superseded — M14 claimed MEM-046 first (hub 7234529134) and has since COMPLETED it (hub 7234702776, PR #2280). STR-114 is the assignment of record.

## Window check — run 14 NOT closed; run-15 live leg HELD

- **Run 14 (TASK-STR-112, Muse 12):** checkpoint 1 PR #2277 OPEN, head `d61c161f`, 1 file +129/−0, evidence `docs/collaboration/TASK-STR-112-EVIDENCE.md`. Verifier Muse 7, due ~12:10 IST (Burn Enforcer §B). Run 14 closes when #2277 is verified and merged.
- **Run 14 result (verified first-hand from PR #2277 + evidence file, branch `muse12/task-str-112-forward-window-fill-ledger-run-14` @ `d61c161f`):** live run 2026-11-28T04:47:14Z / 10:17 IST on Stratex-Server — **RECONCILED**, residual **−0.0341 USDT** vs tolerance 10.49. Ledger byte-identical to runs 9/10/11 (md5 `33ccec26…`, 84 rows, last close 2026-11-27T02:26:41Z). Missing closes 4 (−1.1598); aged-out carry 31 (+18.3716, all income-confirmed); income 1,243 rows; tests 37/37 passed.
- **Window rule (Burn Enforcer §C):** the run-15 live leg runs on the next window after run 14 closes. Until #2277 merges, no live leg — nothing to reconcile against yet, and run 14's report is run 15's pre-run snapshot. **Live leg HELD pending run-14 close.**
- **Pre-run snapshot for run 15:** run 14's report, md5 `c2b573e64ece3a462be8b60b64b2de23`, snapshotted at `/tmp/muse12-str112-report.json` on Stratex-Server (live file `Stratex/state/reconciliation/daily_2026-11-28.json`). To be re-snapshotted first-hand before the run-15 live leg, as M12 did for run 13's report.

## Scope check — same method as runs 9–14

- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`) run live on Stratex-Server (server 4) from a fresh extract of current main (`git archive <main> Stratex | tar -x`); reconciler sha256 `c1da1c1399de7ea0e4c04c1832845e16a03e84cb820c254bce4bf85b0b3d08f1` — byte-identical to runs 9/10/11 (to be re-verified at run time; if the code moved, the new hash is recorded, never assumed). Daemon venv python. `pytest tests/test_daily_fill_ledger_reconciliation.py -q` from the extract.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger is never written; no env flip.
- **Host:** Stratex-Server (server 4) only. The Oracle Server 1 copy of the Stratex state dir is a frozen pre-migration copy — do not re-run against it. Live state dir `/opt/friday_universe/Stratex/state`, env `/opt/friday_universe/Stratex/.env`. The live checkout, daemon service and timer are not touched.
- **Evidence:** `docs/collaboration/TASK-STR-114-EVIDENCE.md`, same shape as run 14 (§1 window numbers, §2 per-symbol P&L, §3 carry proof, §4 identity, §5 funding cross-check, §6 open positions, §7 run record, §8 deltas).
- **Out of scope:** no reconciler code change, no timer/service change, no trade, no live-fleet deploy. Any code or timer fix found goes to the coordinator as a ruling ask, not into this task.

## Carried observations (from run 14, not hidden)

- **Timer stale-checkout overwrite (recurring, ruling still open):** the 01:00 UTC `friday-stratex-reconciliation.timer` run overwrites `daily_2026-11-28.json` with a stale-checkout DISCREPANCY report (residual +38.5348 per run 9 §7). Runs 10/11/13/14 overwrote it in turn with fixed-code RECONCILED reports. Pre-run snapshot before the run-15 leg is therefore mandatory.
- **Matching-class shift (run 11 → run 13):** BOTH 12→5, EXIT_ONLY 16→14, NO_MATCH 54→63 — venue `userTrades`/`allOrders` history aging out of the query window. Identity unaffected (rests on income totals); row-level traceability degrades as fills age. Run 15 re-checks the classes.
- **Standing −0.0341 residual root cause:** the INJUSDT micro-close's second fill income row (−0.034) is not in the carry — observation for the reconciler owner, not a discrepancy.
- **Wallet note:** demo wallet balance moves independently of the income ledger (venue-side snapshot, not part of the reconciled identity).

## Next

- Checkpoint 2 / live leg owed after run 14 closes (PR #2277 verified + merged): snapshot the pre-run report, run the reconciler from a fresh extract of then-current main, file `TASK-STR-114-EVIDENCE.md`, open the work PR. No live step before run-14 close.
- Five states: implemented NO / tested NO / merged NO / deployed NO / production-verified NO (checkpoint 1 — window/scope check only; live leg held per assignment).
