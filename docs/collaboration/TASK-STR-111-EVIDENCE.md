# TASK-STR-111 — Forward-window fill-ledger state run 13 (evidence)

- **Task:** Stratex: forward-window fill-ledger state run 13 — fills, closes, net P&L vs venue.
- **Owner:** Muse 7. **Claim:** hub #2045 comment 7234109463, 2026-11-28 ~10:05 IST (pool pull; WATCH255's read cutoff predated Muse 7's INF-LLM-002 completion post 7234073730, so no new M7 head was assigned there). **Board verified first-hand** on main `a174b89e` (board blob `04e13970`, 12,851 lines): TASK-STR-111 P1, AVAILABLE / owner null / branch null / pr null. Acceptance = daemon fill/close ledger reconciled end-to-end against venue positions/history, evidence as `docs/collaboration/TASK-STR-111-EVIDENCE.md`.
- **Branch:** `muse7/task-str-111-forward-window-run-13` from main `a174b89e` (refs API, read back at claim time).
- **Sequence:** next window after STR-110 run 12 (Muse 4, PR #2265 open, hub 7233813214). Run-numbering overlap across STR-102/103/105/108/109/110 was flagged in run 12's evidence and is not resolved here; this is the board's run 13.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, report `venue: binance_futures_demo`). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip.
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`) run live on Stratex-Server (server 4) from a fresh extract `/tmp/muse7-str111` at `a174b89e` (the live checkout is on main `3db55adf`, which predates the STR-090 merge — the extract supplies the fixed code; the live checkout and daemon were not touched). Reconciler sha256 `c1da1c1399de7ea0e4c04c1832845e16a03e84cb820c254bce4bf85b0b3d08f1` and test sha256 `fa0831288a732e1708d3e42e9650ae58456839bb4636b810e15b5286e3ebba9a` — byte-identical to runs 9–12. Diff of the extract vs run 12's `/tmp/muse4-str110/Stratex`: only `reporting/tax_ledger_export.py` and its test differ (unrelated merges between `21788865` and `a174b89e`); the reconciler and its test are identical. Daemon venv python 3.10.22. Run at 2026-11-28T04:34:40Z / 10:04 IST, report at `Stratex/state/reconciliation/daily_2026-11-28.json` on Stratex-Server, snapshotted to `/tmp/muse7-str111-report.json` (md5 `7ce29dbffd8e9bcc0efddd474f0ab986`, live file and snapshot identical). Pre-run report (run 12's) preserved at `/tmp/muse7-str111-before.json` (md5 `97fdb067be34413c491af1c00e2a1578`). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/muse7-str111/Stratex:/tmp/muse7-str111`. Exact command in §7.
- **Host note (carried from runs 6–12):** the live state is on Stratex-Server (server 4, hostname `stratex-server` verified first-hand this run), `Stratex.service` active. The Oracle Server 1 copy is a frozen pre-migration copy — not used.

## Verdict

**RECONCILED.** The forward-window identity residual is **−0.0341 USDT** against a tolerance of 10.48 USDT — identical to runs 9, 10, 11 and 12. The ledger is byte-identical to run 12 (md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, 84 rows, last close 2026-11-27T02:26:41Z) — no new close, nothing lost, nothing written. The G1 missing-closes set is unchanged (4, −1.1598); the aged-out carry is unchanged (31, +18.3716), all income-confirmed, 0 unconfirmed. The standing −0.0341 residual's root cause (found by run 10, confirmed runs 11–12) is re-confirmed in §3: the INJUSDT micro-close's recorded realised (−0.17) vs its income-confirmed realised (−0.136) differs by exactly 0.034. No matched row disagrees with the venue by more than $0.50 (`diffs_over_0.5: []`). **One real change this run (§3): the row-to-venue matching shifted again** — BOTH 8 → 5, EXIT_ONLY 14 → 14, NO_MATCH 60 → 63 — as venue fills keep ageing out of `userTrades` responses. The identity does not depend on matching, so the verdict stands; the shift is a traceability observation, filed here, not hidden.

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-27T02:26:41Z last close)

| Figure | This run (STR-111, 04:34 UTC) | Run 12 (STR-110, 04:02 UTC) |
|---|---|---|
| Ledger closes, all time | 84 rows (md5 identical) | 84 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 |
| Ledger closes in forward window | 75 rows | 75 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.923 + OANDA USDJPY −0.0478) | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 40 rows −147.9099 | same |
| Venue closes in window | **79** (75 ledger + 4 missing) | 79 |
| Venue window true net P&L (excl. carry) | **−89.1307** | −89.1307 |
| Report `forward_window.venue_true_net_pnl` (incl. carry) | **−70.7591** (−87.9709 − 1.1598 + 18.3716) | −70.7591 |
| Report `forward_window.closes_on_venue` | 110 (75 ledger + 4 missing + 31 carry) | 110 |
| Venue account at run time | wallet 10,438.3531, margin 10,484.4133, unrealised +46.0602, available 9,460.7817 USDT (USDT 4,924.3546 + USDC 5,000 + BTC 0.01) | wallet 10,438.7405, margin 10,484.7431, unrealised +46.0026, available 9,459.9056 |
| Open positions at run time | 30, unrealised +46.1083 (positions sum) / +46.0602 (account) | 30, unrealised +46.0923 / +46.0026 |
| Venue income since the 2026-11-14 reset | REALIZED_PNL **−67.4283**, COMMISSION **−9.8166**, FUNDING_FEE **+0.806**, TRANSFER +15,000.03 | identical on every line |
| Income rows fetched (independent probe, §5) | **1,243** (881 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) | 1,243 |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` |

Change run 12 → this run: **no new ledger close** (ledger md5 identical, 84 rows, last close unchanged 2026-11-27T02:26:41Z) and **no income movement** (every income total identical). The only movements are mark-price drift on the 30 open positions and the matching shift (§3). Wallet moved 10,438.7405 → 10,438.3531 (−0.3874) while income totals are identical — the carried wallet observation (§6).

## §2 — Ledger re-derivation (independent probe, separate process)

Direct read of `/opt/friday_universe/Stratex/state/fill_ledger.jsonl` with manual sums (probe §1, `/tmp/muse7-str111-probe.py`): **84 rows; window 75 rows, window net −87.9709; all-time net +107.089; outside-window rows 9** — matching the report's `ledger` block exactly. Per-symbol window nets: ADAUSDT −31.9944, ALGOUSDT −2.1275, ATOMUSDT −0.7904, AVAXUSDT −20.6058, BTCUSDT +8.0792, DOGEUSDT −5.2915, DOTUSDT +10.9385, ETCUSDT −10.1619, ETHUSDT −20.3867, HBARUSDT +10.0176, LINKUSDT +1.8419, NEARUSDT −0.9046, SANDUSDT +10.1942, SOLUSDT −31.5362, SUIUSDT −14.0632, UNIUSDT +10.1544, USDJPY −0.0478, VETUSDT +20.2573, XRPUSDT −21.5439, and 0.0 for AAVE/APT/ARB/BCH/BNB/FIL/INJ/LTC/MANA/OP/TRX/XLM. G-trace unchanged: 73/84 ledger rows carry no order_id.

## §3 — Missing closes, aged-out carry, and the matching shift

- **Missing closes (G1) — 4, realised −1.1598** (unchanged from runs 8–12): SUIUSDT order 1100728824 BUY 304.4 **+30.5009** (commission 0.0727); VETUSDT order 458616420 BUY 42,328 **−10.9206** (0.0778); SANDUSDT order 340506462 BUY 5,219 **−11.3252** (0.0712); LTCUSDT order 1615011544 BUY 5.706 **−9.4149** (0.1016). One fill each.
- **Aged-out carry — 31 orders, realised +18.3716, all income-confirmed, 0 unconfirmed** (report `aged_out_unconfirmed: {count: 0, realized_pnl: 0, orders: []}`). The ETHUSDT close (order `16876077891`, BUY 0.148, **+19.9399**, 2 fills, first/last fill `1795202078059`) plus 30 Nov-19 micro-closes totalling **−1.5683** (re-summed from the report's order list this run). The INJUSDT micro-close (order 331708071, 2 fills) records `recorded_realized_pnl: −0.17` against income-confirmed `realized_pnl: −0.136` — the 0.034 gap that exactly accounts for the standing −0.0341 residual (second fill's income row not in the carry; observation for the reconciler owner, not a discrepancy).
- **Direct venue probe** (same `DemoFuturesReader`, same env file, separate process): ETHUSDT `userTrades` n=2, earliest `1795268189087` (2026-11-21T07:36:29Z), order 16876077891 present=**False**; `allOrders` n=2, present=**False** — the aged-out close's fills are still absent from both endpoints. **Control:** SUIUSDT order 1100728824 present=**True** in `userTrades` (n=8, earliest `1795241768054`) and `allOrders` (n=4) — the endpoints work; only aged-out fills are gone.
- **Income confirmation (independent, same probe):** ETHUSDT REALIZED_PNL within ±5 min of the close's fill times: **(2 rows, +19.9399)** — exactly the recorded amount. Spot checks: TRXUSDT order 1173153567 **(1, −0.0055)**; MANAUSDT order 241723755 **(1, −0.0376)** — both exactly recorded. Carried amounts are income-endpoint sums, never the residual — the identity stays an independent check.
- **Matching — the shift:** BOTH **5**, EXIT_ONLY **14**, NO_MATCH **63** (82 Binance rows; run 12: BOTH 8 / EXIT_ONLY 14 / NO_MATCH 60). Matched exit realised **−188.8111** vs matched ledger net **−190.1671**; the difference is the matched rows' fees, 1.3560 (run 12: 1.6195), so the matched set still ties out exactly. **Diffs over $0.50: none.** Unmatched zero-realised fills: **18 orders** (unchanged from run 12; report field identical).
- **Venue trade-window census (probe §4):** per-symbol `userTrades` counts 0–8, earliest times Nov 21–27; **13 symbols return zero trades** (AAVE, APT, ARB, BCH, BNB, ETC, FIL, INJ, MANA, OP, PAXG, TRX, XLM — same zero set as run 12). No symbol is near the 1000-row limit. Fills keep ageing out of the demo venue's `userTrades` responses between runs; with fewer fills visible the greedy matcher traces 3 fewer rows as BOTH this run and the matched set's composition moves. The identity is built from income totals + ledger + missing + carry, none of which depends on matching, so the verdict is unaffected. `userTrades` for USDJPY (OANDA symbol) returns HTTP 400 as expected; the reconciler skips non-Binance rows in matching.
- **Run-12 → run-13 report diff (field-by-field, both reports read first-hand):** differing keys — `run_at_utc` (04:02:19 → 04:34:40), `venue_account` (mark drift), `open_positions` (mark drift), `matching` (the shift above). Identical — `task`, `date`, `venue`, `venue_base_url`, `window_start`, `window_start_epoch`, `ledger`, `missing_closes`, `unmatched_zero_realized_fills`, `aged_out_carry`, `aged_out_unconfirmed`, `resets_detected`, `new_resets`, `income_since_reset`, `window_identity`, `forward_window`, `gaps`, `status`, `errors`.

## §4 — Window identity (re-derived from the report)

Ledger window net (Binance) −87.9231 + missing closes −1.1598 + aged-out carry +18.3716 + window fees 3.3171 = expected venue realised **−67.3942**; venue realised **−67.4283**; residual **−0.0341**, tolerance 10.48, status **RECONCILED**. Residual run 12 (−0.0341) = this run (−0.0341) ✓ — stable across runs 9–13. Venue true net (excl. carry) −89.1307 = ledger window net −87.9709 + missing −1.1598 ✓. Report `forward_window.venue_true_net_pnl` −70.7591 = ledger window net + missing + carry ✓.

## §5 — Funding cross-check: STR-090 pagination fix holds live

Independent direct `income()` call (separate process, same reader, same env file): **1,243 income rows** since the reset floor — 881 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER — totals **FUNDING_FEE +0.8067, COMMISSION −9.8158, REALIZED_PNL −67.4282, TRANSFER +15,000.03**, matching the report's `income_since_reset` to within $0.001 on every total (sub-cent deltas are summation rounding; the identity-critical REALIZED_PNL agrees to 0.0001). The 1,000-row venue cap is paginated past (1,243 > 1,000). Funding unchanged since run 12 (881 rows, +0.806) — no new funding rows in 32 minutes.

## §6 — Open positions at run time (30, unrealised +46.1083) + wallet note

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 94.24 | +7.8200 |
| ADAUSDT | +301.0 | 0.1494 | 0.1477 | −0.5117 |
| ALGOUSDT | −2293.4 | 0.08004 | 0.08025081 | −0.4835 |
| APTUSDT | −116.9 | 0.4356 | 0.3865 | +5.7398 |
| ARBUSDT | −410.7 | 0.1269168736304 | 0.1132 | +5.6335 |
| ATOMUSDT | −151.7 | 1.186 | 1.2175 | −4.7786 |
| AVAXUSDT | −3.0 | 7.015 | 6.605 | +1.2300 |
| BCHUSDT | −0.388 | 208.3815979381 | 209.35 | −0.3757 |
| BNBUSDT | −0.08 | 590.59 | 555.72 | +2.7896 |
| BTCUSDT | +0.0025 | 59889.32 | 59981.16273551 | +0.2296 |
| DOGEUSDT | −1453.0 | 0.05505 | 0.05762 | −3.7342 |
| DOTUSDT | −102.7 | 0.6728 | 0.6609 | +1.2221 |
| ETCUSDT | −14.63 | 5.659 | 5.87851899 | −3.2116 |
| ETHUSDT | +0.111 | 1681.3 | 1664.63841085 | −1.8494 |
| FILUSDT | −81.9 | 0.5788 | 0.52560712 | +4.3565 |
| HBARUSDT | −1433.0 | 0.05152 | 0.05352 | −2.8660 |
| INJUSDT | −19.0 | 6.657 | 6.26 | +7.5430 |
| LINKUSDT | −8.79 | 8.629 | 9.22759843 | −5.2617 |
| LTCUSDT | +5.72 | 44.37 | 44.61265348 | +1.3880 |
| MANAUSDT | −1342.0 | 0.060599538003 | 0.0572951 | +4.4345 |
| NEARUSDT | −14.0 | 2.901 | 3.048 | −2.0580 |
| OPUSDT | −661.6 | 0.0768 | 0.07027679 | +4.3158 |
| SANDUSDT | −1822.0 | 0.03348 | 0.03426 | −1.4212 |
| SOLUSDT | −2.1 | 69.02 | 71.62692826 | −5.4745 |
| SUIUSDT | −96.1 | 0.6446 | 0.6711 | −2.5467 |
| TRXUSDT | −750.0 | 0.30999 | 0.30057 | +7.0650 |
| UNIUSDT | −9.0 | 4.707444444444 | 4.74349154 | −0.3244 |
| VETUSDT | +40,580.0 | 0.004618 | 0.004976 | +14.5276 |
| XLMUSDT | −1792.0 | 0.13436 | 0.12599654 | +14.9873 |
| XRPUSDT | −93.7 | 0.925 | 0.9493 | −2.2769 |

All 3× leverage. Position set identical to runs 9–12 (same 30 symbols, same amounts/entries); only marks drifted. Venue account unrealised +46.0602 (account-level read) vs positions sum +46.1083 (0.0481 apart — different read moments in the same run).

**Wallet note (open observation, carried from run 7 §10):** wallet 10,438.7405 (run 12, 04:02 UTC) → 10,438.3531 (this run, 04:34 UTC): movement −0.3874 while the income totals are IDENTICAL over the same interval. The wallet balance moves independently of the income ledger on this demo account — it is a venue-side snapshot, not part of the reconciled identity. Flagged here for the paired verifier, not hidden.

## §7 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge); `Stratex.service` **active** (MainPID 74530), `Stratex-Daemon.service` **active** (MainPID 74531 — same PIDs before and after this run; daemon untouched). The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- **Timer note (recurring, still open):** the 01:00 UTC `friday-stratex-reconciliation.timer` overwrites `daily_2026-11-28.json` daily with the stale-checkout report (DISCREPANCY, residual +38.5348 per run 9 §7); runs 10–12 each overwrote it with the fixed-code RECONCILED report, and this run overwrote run 12's report at 04:34:40 UTC. Pre-run snapshot `/tmp/muse7-str111-before.json` (md5 `97fdb067be34413c491af1c00e2a1578`) preserves run 12's report; this run's report (md5 `7ce29dbffd8e9bcc0efddd474f0ab986`) is snapshotted at `/tmp/muse7-str111-report.json`. Pointing the timer at the fixed code (or stopping it writing the live file) remains a coordinator ruling — carried from runs 9–12.
- Extract: `git fetch origin main` (origin/main `767d5a1d` → `2aca3d59` on fetch; extract pinned at the claimed base `a174b89e`) + `git archive a174b89e Stratex | tar -x -C /tmp/muse7-str111` on Stratex-Server. Reconciler + test sha256 verified above; diff vs run 12's extract: only the two tax-export files differ.
- Run (backgrounded, log `/tmp/muse7-str111-run.log` on Stratex-Server):
  `cd /tmp/muse7-str111/Stratex && PYTHONPATH=/tmp/muse7-str111/Stratex:/tmp/muse7-str111 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-28`
- Log line: `[STR-044] 2026-11-28: ledger 84 rows (window 75, net -87.97), matching {'NO_MATCH': 63, 'BOTH': 5, 'EXIT_ONLY': 14}, missing closes 4 (-1.16), aged-out carry 31 (+18.37), resets 6 (0 new), status RECONCILED -> /opt/friday_universe/Stratex/state/reconciliation/daily_2026-11-28.json` — no `[ERROR]` alert line (no discrepancy alert fired).
- Ledger before-state: 84 rows, md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, last row recorded 2026-11-27T02:26:41Z. Ledger md5 re-verified unchanged after the run and again after the probe/tests.
- Independent probes (separate process, same reader/env): `/tmp/muse7-str111-probe.py` (run-12 probe with extract/report paths updated via sed, logic unchanged) — ledger re-derivation (§2) + income probe (§5) + ETH/SUI fills probe + carry income confirmations + trade-window census (§3). Probe log `/tmp/muse7-str111-probe.log` on Stratex-Server, `PROBE DONE`.
- Bridge note: no bridge transport drops this run. One local caller quoting error occurred before dispatch (no command reached the server) and was corrected; no command was run twice blind. No data was faked. Every number above was re-read live this run from the server or the venue, except where explicitly marked as a run-12 comparison.
- Tests: `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — **37/37 passed** (1 warning: `PytestConfigWarning: Unknown config option: asyncio_mode`, 0.61s) on Stratex-Server in the exact run-13 extract. No test file changed in this task. CI re-verification follows from the work PR.

## Five states

- implemented: YES (this evidence doc filed on branch `muse7/task-str-111-forward-window-run-13`)
- tested: YES (reconciler run live on Stratex-Server + independent ledger re-derivation + independent income probe + ETH-ageing/carry probe + venue trade-window census + 37/37 tests on the exact run-13 code)
- merged: NO (work PR open at filing; paired verification by a different chat owed — never merge own PR)
- deployed: N/A (nothing deployed; proof ran against the existing deploy, daemon untouched)
- production-verified: NO (paired verification by a different chat owed before this counts)

— Muse 7
