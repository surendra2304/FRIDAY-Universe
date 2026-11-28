# TASK-STR-110 — Forward-window fill-ledger state run 12 (evidence)

- **Task:** Stratex: forward-window fill-ledger state run 12 — fills, closes, net P&L vs venue.
- **Owner:** Muse 4. **Claim:** hub #2045 comment 7233543709, 2026-11-28 ~09:27 IST, per BE 08:50 §B (hub 7232927618), adopted WATCH252 §E (hub 7233202719), restated BE 09:10 §B (hub 7233271297). **Board:** CLAIMED / muse_4 / P1 on live main `21788865` (blob `04e13970` — board PR #2250 merged by WATCH253; amendment 4 corrected the owner muse_7 → muse_4). Acceptance = daemon fill/close ledger reconciled end-to-end against venue positions/history, evidence as `docs/collaboration/TASK-STR-110-EVIDENCE.md`.
- **Branch:** `muse4/task-str-110-forward-window-fill-ledger-run12` from main `21788865` (ref POST 201, verified at claim time).
- **Sequence note:** the board titles this run 12, but STR-102 filed as run 9, STR-103 as run 10 (per the STR-104 code comment), STR-105 as run 9 and STR-108 as run 10, STR-109 as run 11. This is the next window after STR-109 run 11 (Muse 12, PR #2258 open). The numbering overlap is flagged for the coordinator, not resolved here.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `21788865`) run live on Stratex-Server (server 4) from a fresh extract `/tmp/muse4-str110` at `21788865` (the live checkout is on main `3db55adf`, which predates the STR-090 merge — the extract, not the live checkout, supplies the fixed code; the live checkout and the daemon were not touched). `git archive 21788865 Stratex | tar -x` used directly (M3's run-9 note: `git worktree add` dropped repeatedly on bridge transport). Reconciler sha256 `c1da1c1399de7ea0e4c04c1832845e16a03e84cb820c254bce4bf85b0b3d08f1` — **byte-identical to runs 9, 10 and 11** (diff vs the run-11 extract: source identical, only run artifacts `.pytest_cache`/`bot.log`/`test_bot.log` differ). Test file sha256 `fa0831288a732e1708d3e42e9650ae58456839bb4636b810e15b5286e3ebba9a` — also identical to runs 9/10/11. Daemon venv python 3.10.22. Run at 2026-11-28T04:02:19Z / 09:32 IST, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-28.json` on Stratex-Server and snapshotted to `/tmp/muse4-str110-report.json` on Stratex-Server (md5 `97fdb067be34413c491af1c00e2a1578`, live file and snapshot identical). The pre-run report is preserved at `/tmp/muse4-str110-before.json` (md5 `e4d8e9eff0d064e2a92396711cf11f94` — run 11's report, TP12/M12). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/muse4-str110/Stratex:/tmp/muse4-str110` so the fixed code runs. Exact command in §7. Note: `origin/main` on the server moved to `767d5a1d` during this run (merges after WATCH253); the extract is pinned at the claimed base `21788865`.
- **Host note (carried from runs 6/7/8/9/10/11):** the Oracle Server 1 copy of the Stratex state dir is a **frozen pre-migration copy** — do not re-run against the S1 copy; the live state is on Stratex-Server, as STR-091/STR-094/STR-095/STR-096/STR-100/STR-101/STR-102/STR-105/STR-108/STR-109 did. This run used Stratex-Server (server 4, hostname `stratex-server` verified first-hand).

## Verdict

**RECONCILED.** The forward-window identity residual is **−0.0341 USDT** against a tolerance of 10.48 USDT — identical to runs 9, 10 and 11 to the cent. The ledger is byte-identical to runs 9/10/11 state (md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, 84 rows, last close 2026-11-27T02:26:41Z) — nothing was lost, nothing was written, no close was missed by the daemon. The G1 missing-closes set is unchanged (4, −1.1598); the aged-out carry is unchanged (31, +18.3716), all income-confirmed, 0 unconfirmed. **Root cause of the standing −0.0341 residual (found by run 10, TP13 §4, confirmed in runs 11 and 12):** the INJUSDT micro-close's second fill income row (−0.034) is not in the carry — the carry understates by exactly the residual. No ruling owed on the identity; the carry gap is an observation for the reconciler owner, not a discrepancy. No matched row disagrees with the venue by more than $0.50 (`diffs_over_0.5: []`). **One real change this run (§3): the row-to-venue matching shifted** — BOTH 12 → 8, EXIT_ONLY 16 → 14, NO_MATCH 54 → 60, unmatched zero-realised fills 20 → 18 — because venue fills keep ageing out of the `userTrades` responses between runs (census in §3). The identity does not depend on matching, so the verdict stands; the shift is a traceability observation, filed here, not hidden. Open observations (timer stale-checkout overwrite, run numbering, wallet note) are filed in §7, not hidden.

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-27T02:26:41Z last close)

| Figure | This run (STR-110, 04:02 UTC) | Run 11 (STR-109, 03:02 UTC) | Run 10 (STR-108, 02:30 UTC) |
|---|---|---|---|
| Ledger closes, all time | 84 rows | 84 rows | 84 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 | +107.089 |
| Ledger closes in forward window | 75 rows | 75 rows | 75 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.923 + OANDA USDJPY −0.0478) | −87.9709 | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 | 3.3171 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 40 rows −147.9099 | same | same |
| Venue closes in window | **79** (75 ledger + 4 missing) | 79 | 79 |
| Venue window true net P&L (excl. carry, STR-105 §1 definition) | **−89.1307** | −89.1307 | −89.1307 |
| Report `forward_window.venue_true_net_pnl` (incl. carry) | **−70.7591** (−87.9709 − 1.1598 + 18.3716) | −70.7591 | −70.7591 |
| Report `forward_window.closes_on_venue` | 110 (75 ledger + 4 missing + 31 carry) | 110 | 110 |
| Venue account at run time | wallet 10,438.74, margin 10,484.74, unrealised +46.00, available 9,459.91 USDT (USDT 4,924.35 + USDC 5,000 + BTC 0.01) | wallet 10,438.16, margin 10,481.24, unrealised +43.08, available 9,455.56 | wallet 10,439.08, margin 10,477.67, unrealised +38.59, available 9,449.06 |
| Open positions at run time | 30, unrealised +46.09 (positions sum) / +46.00 (account) | 30, unrealised +43.11 / +43.08 | 30, unrealised +38.58 |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−67.4283**, COMMISSION **−9.8166**, FUNDING_FEE **+0.806**, TRANSFER +15,000.03 | same totals | same totals |
| Income rows fetched | **1,243** (881 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) | 1,243 | 1,243 |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` | `[]` |

Change run 11 → this run: no new ledger close (ledger md5 identical, 84 rows, last close unchanged 2026-11-27T02:26:41Z). The only movement is mark-price drift on the 30 open positions (unrealised +43.11 → +46.09; wallet +0.58 — see the wallet note in §6, it does not tie to the income deltas and is not part of the reconciled identity) and no funding movement (rows 881, total +0.806 — unchanged in the 60 minutes between runs; funding accrues slowly, not frozen — it grew 851 → 881 rows between run 8 and run 9). The missing-closes set, the carry and the ledger are all unchanged since run 11; only the matching composition moved (§3).

## §2 — Net P&L by symbol (window, 75 closes — re-derived independently this run)

Re-derived from the live ledger (`fill_ledger.jsonl`, exit_time ≥ forward-window start) in a separate process from the reconciler run; matches the report exactly in total (−87.9709) and matches run 11 §2 per-symbol to the cent on every symbol:

| Symbol | Net P&L | Symbol | Net P&L | Symbol | Net P&L |
|---|---|---|---|---|---|
| AAVEUSDT | 0.0000 | DOGEUSDT | −5.2915 | OPUSDT | 0.0000 |
| ADAUSDT | −31.9944 | DOTUSDT | +10.9385 | SANDUSDT | +10.1942 |
| ALGOUSDT | −2.1275 | ETCUSDT | −10.1619 | SOLUSDT | −31.5362 |
| APTUSDT | 0.0000 | ETHUSDT | −20.3867 | SUIUSDT | −14.0632 |
| ARBUSDT | 0.0000 | FILUSDT | 0.0000 | TRXUSDT | 0.0000 |
| ATOMUSDT | −0.7904 | HBARUSDT | +10.0176 | UNIUSDT | +10.1544 |
| AVAXUSDT | −20.6058 | INJUSDT | 0.0000 | USDJPY | −0.0478 |
| BCHUSDT | 0.0000 | LINKUSDT | +1.8419 | VETUSDT | +20.2573 |
| BNBUSDT | 0.0000 | LTCUSDT | 0.0000 | XLMUSDT | +0.0000 |
| BTCUSDT | +8.0792 | MANAUSDT | 0.0000 | XRPUSDT | −21.5439 |
| NEARUSDT | −0.9046 | | | **Total** | **−87.9709** |

The 75 window rows are the same rows as run 7 §5 / run 8 §2 / run 9 §2 / run 11 §2 (ledger unchanged since run 7 — same md5, same per-symbol nets, same all-time cross-check); they are not reprinted here. Outside-window rows: 9, all 2026-11-14, unchanged.

## §3 — The aged-out carry: proof (independent probe, separate process) + the matching shift

- **Missing closes (G1) — 4, realised −1.1598** (unchanged from runs 8/9/10/11): SUIUSDT order 1100728824 BUY 304.4 **+30.5009**; VETUSDT order 458616420 BUY 42,328 **−10.9206**; SANDUSDT order 340506462 BUY 5,219 **−11.3252**; LTCUSDT order 1615011544 BUY 5.706 **−9.4149**.
- **Aged-out carry — 31 orders, realised +18.3716, all income-confirmed, 0 unconfirmed.** The ETHUSDT close (order `16876077891`, BUY 0.148, **+19.9399**, 2 fills, 2026-11-20T00:34:38Z, first/last fill `1795202078059`) plus 30 micro-closes (−0.0055 … −0.136 each, first fills 2026-11-19, totalling −1.5683 — the Nov-19 reset-wipe micro-closes behind the unchanged-since-run-2 base residual). The 30 micro-closes are one per symbol (TRX, MANA, FIL, DOT, ETH, SUI, BCH, INJ, ETC, LTC, ATOM, XRP, LINK, VET, NEAR, AAVE, BTC, SOL, APT, AVAX, UNI, BNB, DOGE, XLM, OP, HBAR, ALGO, ADA, SAND, ARB).
- **Direct venue probe** (`/tmp/muse4-str110-probe.py`, same `DemoFuturesReader`, same env file, separate process from the reconciler run): ETHUSDT `userTrades` returns **n=2** trades, earliest `1795268189087` ms (2026-11-21T07:36:29Z) — order 16876077891 present=0; ETHUSDT `allOrders` returns **n=2** orders, order 16876077891 present=0. Identical to run 11's probe — the close's fills (00:34:38Z Nov 20) are still absent from both endpoints. **Control:** SUIUSDT order 1100728824 IS present in `userTrades` (n=8) and `allOrders` (n=4, FILLED) — the endpoints work; only aged-out fills are gone.
- **Income confirmation (independent, same probe):** ETHUSDT REALIZED_PNL rows within ±5 min of the ETH close's fill times sum to **+19.9399 over 2 rows** — exactly the recorded amount. Spot checks on micro-closes: TRXUSDT order 1173153567, 1 row, **−0.0055**; MANAUSDT order 241723755, 1 row, **−0.0376** — both exactly recorded. The carried amounts are income-endpoint sums, never the residual — the identity stays an independent check.
- **Matching — the shift (new this run):** BOTH 8, EXIT_ONLY 14, NO_MATCH 60 — against runs 9/10/11 at BOTH 12, EXIT_ONLY 16, NO_MATCH 54 (82 Binance rows in both runs). Matched exit realised **−118.707** vs matched ledger net **−120.3265** (run 11: −30.7439 vs −32.7818); the difference is the matched rows' fees, 1.6195 (run 11: 2.0379), so the matched set still ties out exactly. **Diffs over $0.50: none.** Unmatched zero-realised fills: **18 orders** (run 11: 20) — entry legs of the open positions + breakeven entries, visible, never silently dropped.
- **Why it shifted — venue trade-window census (new probe §4, same process):** per-symbol `userTrades` counts are now 0–8 rows, earliest times Nov 21–27; no symbol is near the 1000-row limit, so the limit does not bind. 13 symbols return **zero** trades (AAVE, APT, ARB, BCH, BNB, ETC, FIL, INJ, MANA, OP, PAXG, TRX, XLM). Fills keep disappearing from the demo venue's `userTrades` responses between runs — the same ageing that took the ETH close's fills and the Nov-19 micro-closes. With fewer fills visible, the greedy matcher (a fill explains one row; order-level fallback for split fills) traces 6 fewer rows this hour, and the matched set's composition — hence its sums — moves. The identity is built from income totals + ledger + missing + carry, none of which depends on matching, so the verdict is unaffected. The G-trace gap already discloses the underlying fragility (73/84 ledger rows carry no order_id; row-to-venue traceability rests on price/qty/time matching). Probe artifact, not a venue problem: `userTrades` for USDJPY (an OANDA symbol, not a Binance symbol) returns HTTP 400 as expected; the reconciler skips non-Binance rows in matching.
- **Run-11 → run-12 report diff (field-by-field, both reports read first-hand):** identical — `aged_out_carry`, `aged_out_unconfirmed`, `date`, `errors`, `forward_window`, `gaps`, `income_since_reset`, `ledger`, `missing_closes`, `new_resets`, `resets_detected`, `status`, `task`, `venue`, `venue_base_url`, `window_identity`, `window_start`, `window_start_epoch`. Differing — `run_at_utc` (03:02:44 → 04:02:19), `venue_account` (mark drift only), `open_positions` (mark drift only), `matching` (the shift above), `unmatched_zero_realized_fills` (20 → 18 orders).

## §4 — Window identity (re-derived from the report)

Ledger window net (Binance) −87.9231 + missing closes −1.1598 + aged-out carry +18.3716 + window fees 3.3171 = expected venue realised **−67.3942**; venue realised **−67.4283**; residual **−0.0341**, tolerance 10.48, status **RECONCILED**. Check: residual run 11 (−0.0341) = this run (−0.0341) ✓ — the identity has been stable across runs 9, 10, 11 and 12. Venue true net (excl. carry) −89.1307 = ledger window net −87.9709 + missing −1.1598 ✓. Report `forward_window.venue_true_net_pnl` −70.7591 = ledger window net + missing + carry ✓ (definition stated in §1 — the two figures differ only by the carry).

## §5 — Funding cross-check: STR-090 pagination fix holds live

Independent direct `income()` call (separate process, same reader, same env file): **1,243 income rows** since the reset floor — 881 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER — totals **FUNDING_FEE +0.8067, COMMISSION −9.8158, REALIZED_PNL −67.4282, TRANSFER +15,000.03**, matching the report's `income_since_reset` to within $0.001 on every total (probe ran ~40 min after the report; the sub-cent deltas are summation rounding, not movement — the identity-critical REALIZED_PNL agrees to 0.0001). The 1,000-row venue cap is paginated past (1,243 > 1,000). Funding unchanged since run 11 (rows 881, total +0.806) — no new funding rows in 60 minutes; funding is unfrozen and accruing on a slower cadence (it grew 851 → 881 rows between run 8 and run 9).

## §6 — Open positions at run time (30, unrealised +46.0923) + wallet note

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 94.38 | +7.7500 |
| ADAUSDT | +301.0 | 0.1494 | 0.1479 | −0.4515 |
| ALGOUSDT | −2293.4 | 0.08004 | 0.08013 | −0.2064 |
| APTUSDT | −116.9 | 0.4356 | 0.3866 | +5.7281 |
| ARBUSDT | −410.7 | 0.1269168736304 | 0.1133 | +5.5924 |
| ATOMUSDT | −151.7 | 1.186 | 1.21802857 | −4.8587 |
| AVAXUSDT | −3.0 | 7.015 | 6.608 | +1.2210 |
| BCHUSDT | −0.388 | 208.3815979381 | 209.74403149 | −0.5286 |
| BNBUSDT | −0.08 | 590.59 | 556.08862656 | +2.7601 |
| BTCUSDT | +0.0025 | 59889.32 | 60022.0 | +0.3317 |
| DOGEUSDT | −1453.0 | 0.05505 | 0.05773 | −3.8940 |
| DOTUSDT | −102.7 | 0.6728 | 0.6617 | +1.1400 |
| ETCUSDT | −14.63 | 5.659 | 5.88079653 | −3.2449 |
| ETHUSDT | +0.111 | 1681.3 | 1666.37 | −1.6572 |
| FILUSDT | −81.9 | 0.5788 | 0.5271 | +4.2342 |
| HBARUSDT | −1433.0 | 0.05152 | 0.05361 | −2.9950 |
| INJUSDT | −19.0 | 6.657 | 6.264 | +7.4670 |
| LINKUSDT | −8.79 | 8.629 | 9.24869663 | −5.4471 |
| LTCUSDT | +5.72 | 44.37 | 44.72338425 | +2.0214 |
| MANAUSDT | −1342.0 | 0.060599538003 | 0.05738 | +4.3206 |
| NEARUSDT | −14.0 | 2.901 | 3.058 | −2.1980 |
| OPUSDT | −661.6 | 0.0768 | 0.0703 | +4.3004 |
| SANDUSDT | −1822.0 | 0.03348 | 0.03425792 | −1.4174 |
| SOLUSDT | −2.1 | 69.02 | 71.74449289 | −5.7214 |
| SUIUSDT | −96.1 | 0.6446 | 0.672 | −2.6331 |
| TRXUSDT | −750.0 | 0.30999 | 0.30012 | +7.4025 |
| UNIUSDT | −9.0 | 4.707444444444 | 4.767 | −0.5360 |
| VETUSDT | +40,580.0 | 0.004618 | 0.00499326 | +15.2281 |
| XLMUSDT | −1792.0 | 0.13436 | 0.1261 | +14.8019 |
| XRPUSDT | −93.7 | 0.925 | 0.9508019 | −2.4176 |

All 3× leverage. Position set identical to runs 9/10/11 (same 30 symbols); only marks drifted. Venue account unrealised +46.0026 (account-level read) vs positions sum +46.0923 (0.09 apart — different read moments in the same run).

**Wallet note (open observation, carried from run 7 §10):** wallet 10,438.16 (run 11, 03:02 UTC) → 10,438.74 (this run, 04:02 UTC): movement +0.58 while the income totals are IDENTICAL over the same interval. The wallet balance moves independently of the income ledger on this demo account — it is a venue-side snapshot, not part of the reconciled identity. Flagged here for the paired verifier, not hidden.

## §7 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge); `Stratex.service` **active** (MainPID 74530), `Stratex-Daemon.service` **active** (MainPID 74531 — same PIDs as M3's STR-074 note, daemon untouched). The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- **Timer note (recurring):** the 01:00 UTC `friday-stratex-reconciliation.timer` run fired before run 10 and overwrote `daily_2026-11-28.json` with the **stale-checkout** report (DISCREPANCY, residual +38.5348 per run 9 §7). Run 10 overwrote it at 02:30:56 UTC with the fixed-code RECONCILED report; run 11 overwrote that at 03:02:44 UTC; this run overwrote that at 04:02:19 UTC. The pre-run snapshot `/tmp/muse4-str110-before.json` (md5 `e4d8e9eff0d064e2a92396711cf11f94`) preserves run 11's report; this run's report (md5 `97fdb067be34413c491af1c00e2a1578`) is snapshotted at `/tmp/muse4-str110-report.json`. The timer overwriting the live file daily with a wrong DISCREPANCY is worth a coordinator ruling (point the timer at the fixed code, or stop it writing the live file) — still open, carried from runs 9/10/11.
- Extract: `git fetch origin main` + `git archive 21788865 Stratex | tar -x -C /tmp/muse4-str110` on Stratex-Server (origin/main `767d5a1d` on fetch — merges landed after WATCH253; the extract is pinned at the claimed base). Reconciler + test sha256 verified above; diff vs run 11's extract: source identical (only `__pycache__` differs).
- Run (backgrounded, log `/tmp/muse4-str110-run.log` on Stratex-Server):
  `cd /tmp/muse4-str110/Stratex && PYTHONPATH=/tmp/muse4-str110/Stratex:/tmp/muse4-str110 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-28`
  (the timer service's own invocation, with the extract paths substituted so the merged fixed code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-28: ledger 84 rows (window 75, net -87.97), matching {'NO_MATCH': 60, 'EXIT_ONLY': 14, 'BOTH': 8}, missing closes 4 (-1.16), aged-out carry 31 (+18.37), resets 6 (0 new), status RECONCILED -> /opt/friday_universe/Stratex/state/reconciliation/daily_2026-11-28.json` — no `[ERROR]` alert line (no discrepancy alert fired). Exit 0.
- Ledger before-state: 84 rows, md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, last row recorded 2026-11-27T02:26:41Z. Ledger md5 re-verified unchanged after the run.
- Independent probes (separate processes, same reader/env): `/tmp/muse4-str110-probe.py` (adapted from the run-11 probe: extract + report paths updated, logic unchanged, plus a new §4 venue trade-window census) — ledger re-derivation (window 75, net −87.9709; per-symbol nets §2; all-time +107.089; outside rows 9) + income probe (1,243 rows, totals to $0.001) + ETH/SUI fills probe (§3) + carry income confirmations (§3) + trade-window census (§3). Probe log `/tmp/muse4-str110-probe.log` on Stratex-Server, exit 0.
- Bridge note: the bridge dropped several calls with `IncompleteRead` transport errors this run (pre-state step 3, venv check, report-key print, tests launch — each retried with a fresh session and completed; no data was lost, no command was run twice blind). No data was faked. No figure in this file comes from a run-11 document — every number above was re-read live this run from the server or the venue, except where explicitly marked as a run-11 comparison.
- Tests: `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — **37/37 passed** (1 warning: `PytestConfigWarning: Unknown config option: asyncio_mode`) on Stratex-Server in the exact run-12 extract (pytest, 2.46s, `PYTHONPATH=/tmp/muse4-str110/Stratex:/tmp/muse4-str110`); runs 9/10/11 also had 37 tests. No test file changed in this task. CI re-verification from the work PR's job log follows (STR-091 lesson: the file is collected by `owner-workflows.yml` "Stratex forward-test and self-experiment contracts").

## Five states

- implemented: YES (this evidence doc filed on branch `muse4/task-str-110-forward-window-fill-ledger-run12`)
- tested: YES (reconciler run live on Stratex-Server + independent funding/income probe + independent ledger re-derivation + independent ETH-ageing/carry probe + venue trade-window census + 37/37 tests on the exact run-12 code)
- merged: NO (work PR open at filing; paired verification by a different chat owed — never merge own PR)
- deployed: N/A (nothing deployed; proof ran against the existing deploy, daemon untouched)
- production-verified: NO (paired verification by a different chat owed before this counts)

— Muse 4
