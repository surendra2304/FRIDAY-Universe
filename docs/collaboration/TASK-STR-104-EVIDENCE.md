# TASK-STR-104 — Reconciler run 11: aged-out missing closes carried via income endpoint (evidence)

- **Task:** Stratex: reconciler run 11 — carry aged-out missing closes in the identity (follow-up STR-103 ruling).
- **Owner:** Muse 7. **Claim:** hub #2045 comment 7228769872 (2026-11-28 ~03:18 IST), claiming STR-104 in the same post that reported STR-103 complete (PR #2203 merged `f15516b0`). Branch `muse7/task-str-104-reconciler-run-11-carry-fix` from main `72490c60` (board blob `fcbd6b56` verified via git trees → blob API before claiming; STR-104 AVAILABLE / owner null with next_action naming M7 per the WATCH242 ruling, WATCH243 hub 7228739726; no competing claim on hub re-read immediately before posting).
- **Ruling implemented:** WATCH242 §B — carry aged-out missing closes (income-endpoint realised P&L); bound-to-window rejected (it would drop real P&L).
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip; no service restarted.

## Verdict

**RECONCILED — residual −0.0341 USDT against tolerance 10.47** (run 10: DISCREPANCY +18.3375). The carry totals **+18.3716 across 31 aged-out missing closes**, every one confirmed against the income endpoint (0 unconfirmed): the ETHUSDT close (+19.9399, order 16876077891) whose aging broke run 10, plus the 30 tiny Nov-19 reset-wipe closes (sum −1.5683) whose aging between the 11-25 and 11-26 reports had moved the residual from −0.0002 to run 9's −1.6024. The remaining −0.0341 is one close's income-vs-fills rounding (INJUSDT order 331708071: fills recorded −0.1700, income rows sum −0.1360 — carried at the income amount, difference exactly the residual). No matched row disagrees with the venue by more than $0.50 (`diffs_over_0.5: []`); the ledger is byte-identical to run 10 (84 rows, md5 `33ccec264a95c1e3f0e418bd1e6e3d95`).

## §1 — The fix (`Stratex/scripts/daily_fill_ledger_reconciliation.py`)

The identity's two venue inputs age at different rates: `userTrades`/`allOrders` fills expire after ~7 days, the income endpoint keeps reporting the close's realised P&L. Run 10 proved the break (+18.3375 = −1.6024 + 19.9399, exact). The fix:

- `load_prior_missing_closes(out_dir)` — the dated reports are the persistent registry: missing closes unioned by order id across `daily_*.json` (later reports win), so a close stays on record after its fills age out.
- `find_aged_out_carry(income_rows, prior_missing, current_missing, trades_by_symbol)` — a prior missing close is carried only when (a) it is not a current missing close, (b) its fills predate the symbol's current fills window (aged out; if the window still covers its fill times the fills side governs), and (c) the income endpoint still reports its realised P&L: a subset of the REALIZED_PNL rows for its symbol within ±5 min of its fill times sums to the recorded amount within $0.05 (subset match, because the Nov-19 wipe put ledger-close income rows in the same symbol windows; matched rows are consumed so no income row carries two closes). The carried amount is that income sum — never the residual, so the identity stays an independent check. Aged-out closes income no longer confirms are listed as unconfirmed, never silently carried or dropped (if income dropped the close too, both sides dropped it and no carry is owed).
- `reconcile_window(..., aged_out_carry_realized)` — expected = ledger net + visible missing + aged-out carry + fees; the carry is filed in the identity block.
- Report: new `aged_out_carry` / `aged_out_unconfirmed` sections, `G1-carry` gap lines, and the forward-window venue closes / true net now include carried closes (110 closes, −70.7591).

Tests (`Stratex/tests/test_daily_fill_ledger_reconciliation.py`, +8): run-10 live numbers reconcile only with the carry (+18.3375 DISCREPANCY without, −1.6024 RECONCILED with the ETH carry alone); carry confirmed / unconfirmed / still-visible / fills-still-cover cases; subset match ignoring ledger-close income rows; prior-report union; offline run lists unconfirmed and carries nothing. **36/36 passed** locally on the exact blobs shipped (reconciler sha256 `c1da1c1399de7ea0e4c04c1832845e16a03e84cb820c254bce4bf85b0b3d08f1`, test sha256 `d9dbfd8ae192077cd81aff26a10da409ba98dc8a6a8ac88176e74c556ee435c7`; baseline 28/28 before the change).

## §2 — Run 11 numbers (2026-11-27T21:55:24Z / 2026-11-28 03:25 IST)

| Figure | Run 11 (this run) | Run 10 |
|---|---|---|
| Status | **RECONCILED** | DISCREPANCY |
| Residual / tolerance | **−0.0341 / 10.47** | +18.3375 / 10.46 |
| Venue realised (income) | −67.4283 | −67.4283 |
| Ledger window net (Binance) | −87.9231 | −87.9231 |
| Missing closes visible | 4 (−1.1598) | 4 (−1.1598) |
| Aged-out carry | **31 (+18.3716)** | — (fix absent) |
| Expected venue realised | −67.3942 | −85.7658 |
| Ledger closes | 84 rows, md5 identical | 84 rows |
| Ledger net P&L (all time) | +107.089 (gross +120.1326, fees 13.0436) | same |
| Ledger window net (all venues) | −87.9709 | −87.9709 |
| Venue closes in window | 110 (75 ledger + 4 visible + 31 carried) | 79 |
| Venue window true net P&L | −70.7591 | −89.1307 |
| Venue account | wallet 10,436.48, margin 10,466.64, unrealised +30.1588, available 9,438.96 | wallet 10,434.84, margin 10,459.03 |
| Open positions | 30, unrealised +30.1898 | 30, +24.2208 |
| Income since reset | REALIZED_PNL −67.4283, COMMISSION −9.8166, FUNDING_FEE +0.7282, TRANSFER +15,000.03 | identical |
| Resets | 6 detected, 0 new | same |
| Errors | `[]` | `[]` |

Change run 10 → run 11: **no new ledger close, no income movement** — the only changes are the carry (identity expected −85.7658 → −67.3942) and mark-price drift on the 30 open positions (unrealised +24.22 → +30.19). Matching classes unchanged: BOTH 12, EXIT_ONLY 16, NO_MATCH 54; matched exit realised −30.7439 vs matched ledger net −32.7818 (2.0379 = matched set's fees); unmatched zero-realised fills 20. G-trace unchanged: 73/84 ledger rows carry no order_id.

## §3 — Carry table (31 closes, all income-confirmed)

ETHUSDT order 16876077891 **+19.9399** (2 income rows; filled 2026-11-20T19:14:38Z, aged out 2026-11-27 ~19:19Z — run 10 §3), plus the 30 Nov-19 reset-wipe closes (all filled 2026-11-19T07:56:38–56Z, aged out between the 11-25 and 11-26 reports; each 1 income row, income amount = recorded amount except INJUSDT):

TRXUSDT 1173153567 −0.0055 · MANAUSDT 241723755 −0.0376 · FILUSDT 357157011 −0.0993 · DOTUSDT 664485237 −0.0675 · ETHUSDT 16874886479 −0.0389 · SUIUSDT 1099990253 −0.0414 · BCHUSDT 2612293141 −0.0440 · INJUSDT 331708071 −0.1360 (recorded −0.1700) · ETCUSDT 682043496 −0.0286 · LTCUSDT 1612113572 −0.0203 · ATOMUSDT 642763075 −0.0428 · XRPUSDT 3546043750 −0.0528 · LINKUSDT 1073129051 −0.0277 · VETUSDT 457619917 −0.0361 · NEARUSDT 662684725 −0.0840 · AAVEUSDT 444082337 −0.1000 · BTCUSDT 28686637814 −0.0820 · SOLUSDT 4247827494 −0.0342 · APTUSDT 500703285 −0.0528 · AVAXUSDT 559212681 −0.0930 · UNIUSDT 497754303 −0.0870 · BNBUSDT 2682338050 −0.0306 · DOGEUSDT 2392235543 −0.0540 · XLMUSDT 743599548 −0.0233 · OPUSDT 367842932 −0.0497 · HBARUSDT 336905538 −0.0391 · ALGOUSDT 430047109 −0.0424 · ADAUSDT 1340462696 −0.0280 · SANDUSDT 339382246 −0.0385 · ARBUSDT 365776235 −0.0512.

Sum: +19.9399 − 1.5683 = **+18.3716**. Registry proof: all 31 appear in `daily_2026-11-23..25.json` missing orders (ETH also in 11-26/27); none appears in run 10's report. Visible missing closes unchanged (SUIUSDT +30.5009, VETUSDT −10.9206, SANDUSDT −11.3252, LTCUSDT −9.4149). Next aging candidate: SUIUSDT +30.5009 (filled 2026-11-21T06:16:08Z) — the carry now handles it when it ages out.

## §4 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf`; `Stratex.service` **active** throughout; no service restarted, no env file changed, live checkout untouched.
- Extract: `git fetch origin muse7/task-str-104-reconciler-run-11-carry-fix` + `git archive 4be6abba Stratex | tar -x -C /tmp/muse7-str104` on Stratex-Server; reconciler + test sha256 on the server identical to the branch blobs above (verified before running).
- Run (backgrounded, log `/tmp/muse7-str104-run.log` on Stratex-Server):
  `cd /tmp/muse7-str104/Stratex && PYTHONPATH=/tmp/muse7-str104/Stratex:/tmp/muse7-str104 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-28`
- Log line: `[STR-044] 2026-11-28: ledger 84 rows (window 75, net -87.97), matching {'NO_MATCH': 54, 'EXIT_ONLY': 16, 'BOTH': 12}, missing closes 4 (-1.16), aged-out carry 31 (+18.37), resets 6 (0 new), status RECONCILED`. No measurement alert fired (status RECONCILED).
- Report: `Stratex/state/reconciliation/daily_2026-11-28.json` on Stratex-Server, md5 `edb09452d3882d9ed8149453e658738f`, snapshotted to `/tmp/muse7-str104-report.json` (identical md5 — the snapshot is the filing of record). Pre-run report (run 10, DISCREPANCY) preserved at `/tmp/muse7-str104-before.json`, md5 `7809540b97ecdee351438a704cd641b2`. Ledger before/after: 84 rows, md5 `33ccec264a95c1e3f0e418bd1e6e3d95` (unchanged).

## Five states

- Implemented: YES (carry fix + 8 tests on branch; evidence filed)
- Tested: YES (36/36 unit tests on the exact shipped blobs; live run 11 completed end to end)
- Merged: NO (work PR open, awaiting coordinator merge)
- Deployed: NO (the live timer checkout on Stratex-Server is still `3db55adf`; run 11 executed the fixed code from a `/tmp` extract — deploying the fix to the timer checkout is the coordinator/CD leg)
- Production-verified: YES for the audit leg (live run 11 on Stratex-Server against live state + venue: RECONCILED, residual −0.0341, carry 31/+18.3716 all income-confirmed, ledger untouched) — the deployed-timer leg remains NO until the checkout updates

## Files changed

- `Stratex/scripts/daily_fill_ledger_reconciliation.py` (carry fix)
- `Stratex/tests/test_daily_fill_ledger_reconciliation.py` (+8 tests)
- `docs/collaboration/TASK-STR-104-EVIDENCE.md` (new, this file)
- `docs/collaboration/WORK_BOARD.yaml` (STR-104 flip)

— Muse 7
