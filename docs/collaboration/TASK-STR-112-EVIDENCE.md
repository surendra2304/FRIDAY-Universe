# TASK-STR-112 — Forward-window fill-ledger state run 14 (evidence)

- **Task:** Stratex: forward-window fill-ledger state run 14 — fills, closes, net P&L vs venue.
- **Owner:** Muse 12. **Claim:** hub #2045 comment 7234329954, 2026-11-28 10:24 IST, per Burn Enforcer 10:10 §C (hub 7234114929), confirmed by WATCH256 §B (hub 7234199117). **Board:** AVAILABLE / owner null on main `7ecab6ce` (blob `f2504f88`) at claim time; flip rides the coordinator board PR. Acceptance = daemon fill/close ledger reconciled end-to-end against venue positions/history, evidence as `docs/collaboration/TASK-STR-112-EVIDENCE.md`.
- **Branch:** `muse12/task-str-112-forward-window-fill-ledger-run-14` from main `7ecab6ce` (ref created via GitHub API; local git push has no credential on this VM — ref verified via ls-remote).
- **Sequence note:** the board titles this run 14, the next window after STR-111 run 13 (Muse 7, PR #2272 open at claim time). Run 13's report is this run's pre-run snapshot (see §7).
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `7ecab6ce`) run live on Stratex-Server (server 4) from a fresh extract `/tmp/muse12-str112` at `7ecab6ce` (the live checkout is on main `3db55adf`, which predates the STR-090 merge — the extract, not the live checkout, supplies the fixed code; the live checkout and the daemon were not touched). `git archive 7ecab6ce Stratex | tar -x` used directly (M3's run-9 note: `git worktree add` dropped repeatedly on bridge transport). Reconciler sha256 `c1da1c1399de7ea0e4c04c1832845e16a03e84cb820c254bce4bf85b0b3d08f1` — **byte-identical to runs 9, 10 and 11**. Test file sha256 `fa0831288a732e1708d3e42e9650ae58456839bb4636b810e15b5286e3ebba9a` — also identical to runs 9/10/11. Daemon venv python. Run at 2026-11-28T04:47:14Z / 10:17 IST; the backgrounded process's exit code was not captured directly (completion is evidenced by the log line and the written report — stated plainly, not assumed). Report filed at `Stratex/state/reconciliation/daily_2026-11-28.json` on Stratex-Server and snapshotted to `/tmp/muse12-str112-report.json` on Stratex-Server (md5 `c2b573e64ece3a462be8b60b64b2de23`, live file and snapshot identical — re-verified first-hand by Muse 12 after the run, not only worker-reported). The pre-run report is preserved at `/tmp/muse12-str112-before.json` (md5 `7ce29dbffd8e9bcc0efddd474f0ab986` — run 13's report, Muse 7). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/muse12-str112/Stratex:/tmp/muse12-str112` so the fixed code runs. Exact command in §7.
- **Host note (carried from runs 6/7/8/9/10/11):** the Oracle Server 1 copy of the Stratex state dir is a **frozen pre-migration copy** — do not re-run against the S1 copy; the live state is on Stratex-Server, as STR-091/STR-094/STR-095/STR-096/STR-100/STR-101/STR-102/STR-105/STR-108/STR-109/STR-111 did. This run used Stratex-Server (server 4).

## Verdict

**RECONCILED.** The forward-window identity residual is **−0.0341 USDT** against a tolerance of 10.49 USDT — identical residual to runs 9, 10, 11 and 13 to the cent. The ledger is byte-identical to runs 9/10/11 state (md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, 84 rows, last close 2026-11-27T02:26:41Z) — nothing was lost, nothing was written, no close was missed by the daemon. The G1 missing-closes set is unchanged (4, −1.1598); the aged-out carry is unchanged (31, +18.3716), all income-confirmed, 0 unconfirmed. **Root cause of the standing −0.0341 residual (found by run 10, TP13 §4, confirmed here):** the INJUSDT micro-close's second fill income row (−0.034) is not in the carry — the carry understates by exactly the residual. No ruling owed on the identity; the carry gap is an observation for the reconciler owner, not a discrepancy. No matched row disagrees with the venue by more than $0.50 (`diffs_over_0.5: []`). One material delta vs run 11 is flagged in §8 (matching-class shift between run 11 and run 13, reproduced exactly here — the identity is unaffected). Open observations (timer stale-checkout overwrite, run numbering, wallet note) are filed in §7, not hidden.

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-27T02:26:41Z last close)

| Figure | This run (STR-112, 04:47 UTC) | Run 13 (STR-111, 04:34 UTC, M7) | Run 11 (STR-109, 03:02 UTC) |
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
| Venue account at run time | wallet 10,438.87, margin 10,487.16, unrealised +48.29, available 9,465.55 USDT (USDT 4,924.35 + USDC 5,000 + BTC 0.01) | wallet 10,438.35 | wallet 10,438.16, margin 10,481.24, unrealised +43.08, available 9,455.56 |
| Open positions at run time | 30, unrealised +48.28 (positions sum) / +48.29 (account) | 30, +46.11 / +46.06 | 30, unrealised +43.11 (positions sum) / +43.08 (account) |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−67.4283**, COMMISSION **−9.8166**, FUNDING_FEE **+0.806**, TRANSFER +15,000.03 | same totals | same totals |
| Income rows fetched | **1,243** (881 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) | 1,243 | 1,243 |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` | `[]` |

Change run 11 → this run: no new ledger close (ledger md5 identical, 84 rows, last close unchanged 2026-11-27T02:26:41Z). The only movement is mark-price drift on the 30 open positions (unrealised +43.11 → +48.28; wallet +0.71 — see the wallet note in §6, it does not tie to the income deltas and is not part of the reconciled identity) and no funding movement (rows 881, total +0.806 — unchanged across runs 11/13/14; funding accrues slowly, not frozen — it grew 851 → 881 rows between run 8 and run 9). The missing-closes set, the matched sums and the ledger are all unchanged since run 13; the matching-class shift vs run 11 is §8, not a ledger change.

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
| BNBUSDT | 0.0000 | LTCUSDT | 0.0000 | XLMUSDT | 0.0000 |
| BTCUSDT | +8.0792 | MANAUSDT | 0.0000 | XRPUSDT | −21.5439 |
| NEARUSDT | −0.9046 | | | **Total** | **−87.9709** |

The 75 window rows are the same rows as run 7 §5 / run 8 §2 / run 9 §2 / run 11 §2 (ledger unchanged since run 7 — same md5, same per-symbol nets, same all-time cross-check); they are not reprinted here. Outside-window rows: 9, all 2026-11-14, unchanged.

## §3 — The aged-out carry: proof (independent probe, separate process)

- **Missing closes (G1) — 4, realised −1.1598** (unchanged from runs 8/9/10/11): SUIUSDT order 1100728824 BUY 304.4 **+30.5009**; VETUSDT order 458616420 BUY 42,328 **−10.9206**; SANDUSDT order 340506462 BUY 5,219 **−11.3252**; LTCUSDT order 1615011544 BUY 5.706 **−9.4149**.
- **Aged-out carry — 31 orders, realised +18.3716, all income-confirmed, 0 unconfirmed.** The ETHUSDT close (order `16876077891`, BUY 0.148, **+19.9399**, 2 fills, 2026-11-20T00:34:38Z, first/last fill `1795202078059`) plus 30 micro-closes (−0.0055 … −0.136 each, first fills 2026-11-19, totalling −1.5683 — the Nov-19 reset-wipe micro-closes behind the unchanged-since-run-2 base residual). The 30 micro-closes are one per symbol (TRX, MANA, FIL, DOT, ETH, SUI, BCH, INJ, ETC, LTC, ATOM, XRP, LINK, VET, NEAR, AAVE, BTC, SOL, APT, AVAX, UNI, BNB, DOGE, XLM, OP, HBAR, ALGO, ADA, SAND, ARB).
- **Direct venue probe** (`/tmp/muse12-str112-probe.py`, same `DemoFuturesReader`, same env file, separate process from the reconciler run): ETHUSDT `userTrades` returns **n=2** trades, earliest `1795268189087` ms (2026-11-21T07:36:29Z) — order 16876077891 present=0; ETHUSDT `allOrders` returns **n=2** orders, order 16876077891 present=0. Identical to runs 9/11 probes — the close's fills (00:34:38Z Nov 20) are still absent from both endpoints. **Control:** SUIUSDT order 1100728824 IS present in `userTrades` (n=8) and `allOrders` (n=4, FILLED) — the endpoints work; only aged-out fills are gone.
- **Income confirmation (independent, same probe):** ETHUSDT REALIZED_PNL rows within ±5 min of the ETH close's fill times sum to **+19.9399 over 2 rows** — exactly the recorded amount. Spot checks on micro-closes: TRXUSDT order 1173153567, 1 row, **−0.0055**; MANAUSDT order 241723755, 1 row, **−0.0376** — both exactly recorded. The carried amounts are income-endpoint sums, never the residual — the identity stays an independent check.
- **Matching (82 Binance rows):** BOTH 5, EXIT_ONLY 14, NO_MATCH 63 — see §8 for the shift vs run 11 (BOTH 12, EXIT_ONLY 16, NO_MATCH 54). Matched-exit set: matched exit realised −188.8111 vs matched ledger net −190.1671; the difference is the matched rows' fees, 1.3560, so the matched set ties out exactly. **Diffs over $0.50: none.** Unmatched zero-realised fills: 18 orders (run 11: 20) — entry legs of the open positions + breakeven entries — visible, never silently dropped.

## §4 — Window identity (re-derived from the report)

Ledger window net (Binance) −87.9231 + missing closes −1.1598 + aged-out carry +18.3716 + window fees 3.3171 = expected venue realised **−67.3942**; venue realised **−67.4283**; residual **−0.0341**, tolerance 10.49, status **RECONCILED**. Check: residual run 13 (−0.0341) = this run (−0.0341) ✓ — the identity has been stable across runs 9, 10, 11, 13 and 14. Venue true net (excl. carry) −89.1307 = ledger window net −87.9709 + missing −1.1598 ✓. Report `forward_window.venue_true_net_pnl` −70.7591 = ledger window net + missing + carry ✓ (definition stated in §1 — the two figures differ only by the carry).

## §5 — Funding cross-check: STR-090 pagination fix holds live

Independent direct `income()` call (separate process, same reader, same env file): **1,243 income rows** since the reset floor — 881 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER — totals **FUNDING_FEE +0.8067, COMMISSION −9.8158, REALIZED_PNL −67.4282, TRANSFER +15,000.03**, matching the report's `income_since_reset` to within $0.001 on every total (probe ran after the report; the sub-cent deltas are summation rounding, not movement — the identity-critical REALIZED_PNL agrees to 0.0001). The 1,000-row venue cap is paginated past (1,243 > 1,000). Funding unchanged since run 11 (rows 881, total +0.806) — no new funding rows in ~105 minutes; funding is unfrozen and accruing on a slower cadence (it grew 851 → 881 rows between run 8 and run 9).

## §6 — Open positions at run time (30, unrealised +48.2809) + wallet note

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 94.12 | +7.8800 |
| ADAUSDT | 301.0 | 0.1494 | 0.14730255 | −0.6313 |
| ALGOUSDT | −2293.4 | 0.08004 | 0.08004331 | −0.0076 |
| APTUSDT | −116.9 | 0.4356 | 0.386 | +5.7982 |
| ARBUSDT | −410.7 | 0.1269168736304 | 0.11294134 | +5.7398 |
| ATOMUSDT | −151.7 | 1.186 | 1.2133 | −4.1414 |
| AVAXUSDT | −3.0 | 7.015 | 6.601 | +1.2420 |
| BCHUSDT | −0.388 | 208.3815979381 | 208.68167652 | −0.1164 |
| BNBUSDT | −0.08 | 590.59 | 555.41 | +2.8144 |
| BTCUSDT | 0.0025 | 59889.32 | 60000.0 | +0.2767 |
| DOGEUSDT | −1453.0 | 0.05505 | 0.05748 | −3.5308 |
| DOTUSDT | −102.7 | 0.6728 | 0.6598 | +1.3351 |
| ETCUSDT | −14.63 | 5.659 | 5.877 | −3.1893 |
| ETHUSDT | 0.111 | 1681.3 | 1662.98 | −2.0335 |
| FILUSDT | −81.9 | 0.5788 | 0.52402403 | +4.4862 |
| HBARUSDT | −1433.0 | 0.05152 | 0.0534036 | −2.6992 |
| INJUSDT | −19.0 | 6.657 | 6.264 | +7.4670 |
| LINKUSDT | −8.79 | 8.629 | 9.22377477 | −5.2281 |
| LTCUSDT | 5.72 | 44.37 | 44.51 | +0.8008 |
| MANAUSDT | −1342.0 | 0.060599538003 | 0.05715968 | +4.6163 |
| NEARUSDT | −14.0 | 2.901 | 3.042 | −1.9740 |
| OPUSDT | −661.6 | 0.0768 | 0.0701 | +4.4327 |
| SANDUSDT | −1822.0 | 0.03348 | 0.03419846 | −1.3090 |
| SOLUSDT | −2.1 | 69.02 | 71.61841141 | −5.4567 |
| SUIUSDT | −96.1 | 0.6446 | 0.6695 | −2.3929 |
| TRXUSDT | −750.0 | 0.30999 | 0.30011865 | +7.4035 |
| UNIUSDT | −9.0 | 4.707444444444 | 4.73639225 | −0.2605 |
| VETUSDT | 40580.0 | 0.004618 | 0.00495567 | +13.7026 |
| XLMUSDT | −1792.0 | 0.13436 | 0.1257703 | +15.3927 |
| XRPUSDT | −93.7 | 0.925 | 0.9478 | −2.1364 |

All 3× leverage. Position set identical to runs 9/10/11/13 (same 30 symbols); only marks drifted. Venue account unrealised +48.2889 (account-level read) vs positions sum +48.2809 (0.008 apart — different read moments in the same run).

**Wallet note (open observation, carried from run 7 §10):** wallet 10,438.16 (run 11, 03:02 UTC) → 10,438.3531 (run 13, 04:34 UTC) → 10,438.8734 (this run, 04:47 UTC): movement +0.71 while the income totals are IDENTICAL over the same interval. The wallet balance moves independently of the income ledger on this demo account — it is a venue-side snapshot, not part of the reconciled identity. Flagged here for the paired verifier, not hidden.

## §7 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge); `Stratex.service` **active**, `Stratex-Daemon.service` **active** (verified first-hand this run). The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- **Timer note (recurring):** the 01:00 UTC `friday-stratex-reconciliation.timer` run overwrote `daily_2026-11-28.json` with the **stale-checkout** report (DISCREPANCY, residual +38.5348 per run 9 §7) before run 10; runs 10/11/13/14 overwrote it in turn with fixed-code RECONCILED reports. The pre-run snapshot `/tmp/muse12-str112-before.json` (md5 `7ce29dbffd8e9bcc0efddd474f0ab986`) preserves run 13's report; this run's report (md5 `c2b573e64ece3a462be8b60b64b2de23`) is snapshotted at `/tmp/muse12-str112-report.json`. The timer overwriting the live file daily with a wrong DISCREPANCY is worth a coordinator ruling (point the timer at the fixed code, or stop it writing the live file) — still open, carried from runs 9/10/11.
- **Bridge outage (this run, flagged plainly):** the FRIDAY bridge (`friday-universe.duckdns.org/bridge/mcp`) became unreachable ~04:52–05:07 UTC (~15 min): TLS stall / `RemoteDisconnected` on init, plain GET returning 000. It recovered ~05:07 UTC (plain GET 406, the bridge's normal reply). The probe and tests had already been launched server-side and ran during the outage; their logs persisted on the server and were read after recovery. No data lost, no re-run needed. The report md5s and identity figures were re-verified first-hand by Muse 12 after recovery (see header note).
- Extract: `git fetch origin main` + `git archive 7ecab6ce Stratex | tar -x -C /tmp/muse12-str112` on Stratex-Server (origin/main `7ecab6ce` on fetch). Reconciler + test sha256 verified above; source identical to runs 9/10/11.
- Run (backgrounded, log `/tmp/muse12-str112-run.log` on Stratex-Server):
  `cd /tmp/muse12-str112/Stratex && PYTHONPATH=/tmp/muse12-str112/Stratex:/tmp/muse12-str112 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-28`
  (the timer service's own invocation, with the extract paths substituted so the merged fixed code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-28: ledger 84 rows (window 75, net -87.97), matching {'NO_MATCH': 63, 'BOTH': 5, 'EXIT_ONLY': 14}, missing closes 4 (-1.16), aged-out carry 31 (+18.37), resets 6 (0 new), status RECONCILED`.
- Tests: `pytest tests/test_daily_fill_ledger_reconciliation.py -q` from the extract with the daemon venv python: **37 passed, 1 warning in 0.60s**. The warning is the pre-existing `PytestConfigWarning: Unknown config option: asyncio_mode`, not a failure.
- Report field note (carried observation): the report's `task` field still reads `TASK-STR-044` (the reconciler's own stamp), not TASK-STR-112 — cosmetic, the reconciler was not modified for this run.
- Window start: 2026-11-15T11:29:49+05:30 (epoch 1794722389.0). Venue: `binance_futures_demo`. Gaps: G1 4 venue closes no ledger row (−1.16); G1-carry 31 aged-out (+18.37); G-trace 73/84 ledger rows carry no order_id.

## §8 — Matching-class shift vs run 11 (material, flagged plainly)

Run 11 (03:02 UTC): BOTH 12, EXIT_ONLY 16, NO_MATCH 54; matched sums −30.7439 / −32.7818; unmatched zero-realised 20. This run (04:47 UTC): BOTH **5**, EXIT_ONLY **14**, NO_MATCH **63**; matched sums **−188.8111 / −190.1671**; unmatched zero-realised **18**. **The shift did not happen in this run**: Muse 7's run-13 before-file (04:34:40 UTC) already shows BOTH 5 / EXIT_ONLY 14 / NO_MATCH 63, matched sums −188.8111 / −190.1671, unmatched zero 18 — this run reproduces run 13 exactly on all of these. So between run 11 (03:02 UTC) and run 13 (04:34 UTC), 7 BOTH rows became NO_MATCH and 2 EXIT_ONLY rows became NO_MATCH, i.e. venue `userTrades`/`allOrders` history stopped returning those fills (aging out of the venue query window — the same mechanism the §3 ETH probe demonstrates directly for the aged-out carry). The identity is unaffected — it rests on income totals, which are unchanged — and `diffs_over_0.5` is still empty. Worth a note to the reconciler owner: row-level traceability degrades as fills age out, even while the identity holds. No ruling owed on this run's verdict.
