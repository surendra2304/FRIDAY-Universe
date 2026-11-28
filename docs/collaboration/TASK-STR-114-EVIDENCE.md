# TASK-STR-114 — Forward-window fill-ledger state run 15 (evidence)

- **Task:** Stratex: forward-window fill-ledger state run 15 — fills, closes, net P&L vs venue.
- **Owner:** Muse 20. **Claim:** hub #2045 comment 7234818307, 2026-11-28 11:07 IST, per Burn Enforcer §C (hub 7234754534). **Board:** CLAIMED / muse_20 on main (flip rides the coordinator board PR; no board hunk in this PR, ruling 7200564540 §3). Acceptance = daemon fill/close ledger reconciled end-to-end against venue positions/history, evidence as `docs/collaboration/TASK-STR-114-EVIDENCE.md`.
- **Branch:** `muse20/task-str-114` from main `527b073d` (rebased at work-PR time; checkpoint 1 filed from main `300ab00c`).
- **Sequence note:** the board titles this run 15, the next window after STR-112 run 14 (Muse 12, PR #2277 MERGED 2026-11-28T06:32:54Z / 12:02:54 IST, merge `5a20c712`, VERIFIED by Muse 5 review 6096156443). Run 14's report is this run's pre-run snapshot (see §7).
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `527b073d`) run live on Stratex-Server (server 4) from a fresh extract `/tmp/muse20-str114` at `527b073d` (the live checkout is on main `3db55adf`, which predates the STR-090 merge — the extract, not the live checkout, supplies the fixed code; the live checkout and the daemon were not touched). `git archive 527b073d Stratex | tar -x` used directly (M3's run-9 note: `git worktree add` dropped repeatedly on bridge transport). Reconciler sha256 `c1da1c1399de7ea0e4c04c1832845e16a03e84cb820c254bce4bf85b0b3d08f1` — **byte-identical to runs 9, 10, 11, 13 and 14**. Test file sha256 `fa0831288a732e1708d3e42e9650ae58456839bb4636b810e15b5286e3ebba9a` — also identical to runs 9/10/11/13/14. Daemon venv python. Run at 2026-11-28T08:03:09Z / 13:33:09 IST; the backgrounded process's exit code was not captured directly (completion is evidenced by the log line and the written report — stated plainly, not assumed). Report filed at `Stratex/state/reconciliation/daily_2026-11-28.json` on Stratex-Server and snapshotted to `/tmp/muse20-str114-report.json` on Stratex-Server (md5 `6a64f891821aa48042d35d5da5ce60bc`, live file and snapshot identical — re-verified first-hand after the run). The pre-run report is preserved at `/tmp/muse20-str114-before.json` (md5 `c2b573e64ece3a462be8b60b64b2de23` — run 14's report, Muse 12; re-snapshotted first-hand before this run, live file md5 matched before the run started). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/muse20-str114/Stratex:/tmp/muse20-str114` so the fixed code runs. Exact command in §7.
- **Host note (carried from runs 6/7/8/9/10/11/13/14):** the Oracle Server 1 copy of the Stratex state dir is a **frozen pre-migration copy** — do not re-run against the S1 copy; the live state is on Stratex-Server, as STR-091/STR-094/STR-095/STR-096/STR-100/STR-101/STR-102/STR-105/STR-108/STR-109/STR-111/STR-112 did. This run used Stratex-Server (server 4).

## Verdict

**RECONCILED.** The forward-window identity residual is **−0.0341 USDT** against a tolerance of 10.5 USDT — identical residual to runs 9, 10, 11, 13 and 14 to the cent. The ledger is byte-identical to runs 9/10/11/13/14 state (md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, 84 rows, last close 2026-11-27T02:26:41Z) — nothing was lost, nothing was written, no close was missed by the daemon. **One material delta vs run 14, flagged plainly (§8): the SUIUSDT missing close (+30.5009) aged out of venue `userTrades`/`allOrders` history between run 14 (04:47 UTC) and this run (08:03 UTC) and moved from missing-closes into the aged-out carry** — missing closes 4 → 3 (−1.1598 → −31.6607), carry 31 → 32 (+18.3716 → +48.8725). The move is exactly offsetting (−31.6607 + 48.8725 = +17.2118 = −1.1598 + 18.3716), the carry entry is income-confirmed, and the identity is unchanged. No matched row disagrees with the venue by more than $0.50 (`diffs_over_0.5: []`). **Root cause of the standing −0.0341 residual (found by run 10, TP13 §4, confirmed here):** the INJUSDT micro-close's second fill income row (−0.034) is not in the carry — the carry understates by exactly the residual. No ruling owed on the identity; the carry gap is an observation for the reconciler owner, not a discrepancy. Open observations (timer stale-checkout overwrite, funding probe-vs-report delta, wallet note) are filed in §5/§7, not hidden.

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-27T02:26:41Z last close)

| Figure | This run (STR-114, 08:03 UTC) | Run 14 (STR-112, 04:47 UTC) | Run 11 (STR-109, 03:02 UTC) |
|---|---|---|---|
| Ledger closes, all time | 84 rows | 84 rows | 84 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 | +107.089 |
| Ledger closes in forward window | 75 rows | 75 rows | 75 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.923 + OANDA USDJPY −0.0478) | −87.9709 | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 | 3.3171 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 40 rows −147.9099 | same | same |
| Venue closes in window | **78** (75 ledger + 3 missing) | 79 (75 + 4) | 79 |
| Venue window true net P&L (excl. carry) | **−119.6316** (−87.9709 − 31.6607) | −89.1307 | −89.1307 |
| Report `forward_window.venue_true_net_pnl` (incl. carry) | **−70.7591** (−87.9709 − 31.6607 + 48.8725) | −70.7591 | −70.7591 |
| Report `forward_window.closes_on_venue` | 110 (75 ledger + 3 missing + 32 carry) | 110 (75 + 4 + 31) | 110 |
| Venue account at run time | wallet 10,436.79, margin 10,495.20, unrealised +58.41, available 9,481.59 USDT (USDT 4,924.29 + USDC 5,000 + BTC 0.01) | wallet 10,438.87, margin 10,487.16, unrealised +48.29, available 9,465.55 USDT (USDT 4,924.35 + USDC 5,000 + BTC 0.01) | wallet 10,438.16, margin 10,481.24, unrealised +43.08, available 9,455.56 |
| Open positions at run time | 30, unrealised +58.27 (positions sum) / +58.41 (account) | 30, +48.28 / +48.29 | 30, unrealised +43.11 (positions sum) / +43.08 (account) |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−67.4283**, COMMISSION **−9.8166**, FUNDING_FEE **+0.7356**, TRANSFER +15,000.03 | REALISED_PNL −67.4283, COMMISSION −9.8166, FUNDING_FEE +0.806, TRANSFER +15,000.03 | same totals |
| Income rows fetched | **1,272** (910 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) | 1,243 (881 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) | 1,243 |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` | `[]` |

Change run 14 → this run: no new ledger close (ledger md5 identical, 84 rows, last close unchanged 2026-11-27T02:26:41Z). The SUIUSDT close (order 1100728824, +30.5009) aged out of venue history into the carry (§3, §8); the missing-closes and carry totals move by exactly offsetting amounts. The only other movement is mark-price drift on the 30 open positions (unrealised +48.28 → +58.27; wallet −2.08 — see the wallet note in §6, it does not tie to the income deltas and is not part of the reconciled identity) and funding rows 881 → 910 at the 08:00 UTC settlement (see §5).

## §2 — Net P&L by symbol (window, 75 closes — re-derived independently this run)

Re-derived from the live ledger (`fill_ledger.jsonl`, exit_time ≥ forward-window start) in a separate process from the reconciler run; matches the report exactly in total (−87.9709) and matches run 14 §2 per-symbol to the cent on every symbol:

| Symbol | Net P&L | Symbol | Net P&L |
|---|---|---|---|
| AAVEUSDT | 0.0000 | LINKUSDT | +1.8419 |
| ADAUSDT | −31.9944 | LTCUSDT | 0.0000 |
| ALGOUSDT | −2.1275 | MANAUSDT | 0.0000 |
| APTUSDT | 0.0000 | NEARUSDT | −0.9046 |
| ARBUSDT | 0.0000 | OPUSDT | 0.0000 |
| ATOMUSDT | −0.7904 | SANDUSDT | +10.1942 |
| AVAXUSDT | −20.6058 | SOLUSDT | −31.5362 |
| BCHUSDT | 0.0000 | SUIUSDT | −14.0632 |
| BNBUSDT | 0.0000 | TRXUSDT | 0.0000 |
| BTCUSDT | +8.0792 | UNIUSDT | +10.1544 |
| DOGEUSDT | −5.2915 | USDJPY | −0.0478 |
| DOTUSDT | +10.9385 | VETUSDT | +20.2573 |
| ETCUSDT | −10.1619 | XLMUSDT | 0.0000 |
| ETHUSDT | −20.3867 | XRPUSDT | −21.5439 |
| FILUSDT | 0.0000 | **Total** | **−87.9709** |
| HBARUSDT | +10.0176 | | |
| INJUSDT | 0.0000 | | |

The 75 window rows are the same rows as run 7 §5 / run 8 §2 / run 9 §2 / run 11 §2 / run 14 §2 (ledger unchanged since run 7 — same md5, same per-symbol nets, same all-time cross-check); they are not reprinted here. Outside-window rows: 9, all 2026-11-14, unchanged. (The report's ledger symbols list also carries PAXGUSDT, as run 14's report did — it has no window rows and contributes 0.0000; run 14 §2's table did not print it.)

## §3 — The aged-out carry: proof (independent probe, separate process)

- **Missing closes (G1) — 3, realised −31.6607** (run 14: 4, −1.1598): VETUSDT order 458616420 BUY 42,328 **−10.9206**; SANDUSDT order 340506462 BUY 5,219 **−11.3252**; LTCUSDT order 1615011544 BUY 5.706 **−9.4149**. The SUIUSDT close is gone from this set — see below.
- **Aged-out carry — 32 orders, realised +48.8725, all income-confirmed, 0 unconfirmed.** The SUIUSDT close (order `1100728824`, BUY 304.4, **+30.5009**, 1 fill, 2026-11-21T07:36:08Z) is new to the carry this run; the ETHUSDT close (order `16876077891`, BUY 0.148, **+19.9399**, 2 fills, 2026-11-20T00:34:38Z, first/last fill `1795202078059`) plus 30 micro-closes (−0.0055 … −0.136 each, first fills 2026-11-19, totalling −1.5683 — the Nov-19 reset-wipe micro-closes behind the unchanged-since-run-2 base residual). The 30 micro-closes are one per symbol (TRX, MANA, FIL, DOT, ETH, SUI, BCH, INJ, ETC, LTC, ATOM, XRP, LINK, VET, NEAR, AAVE, BTC, SOL, APT, AVAX, UNI, BNB, DOGE, XLM, OP, HBAR, ALGO, ADA, SAND, ARB).
- **Direct venue probe** (`/tmp/muse20-str114-probe.py`, same `DemoFuturesReader`, same env file, separate process from the reconciler run): SUIUSDT `userTrades` returns **n=6** trades, earliest `1795266451107` ms (2026-11-21T07:47:31Z) — order 1100728824 present=0; SUIUSDT `allOrders` returns **n=2** orders, order 1100728824 present=0. Run 14's control showed this order present in both endpoints (`userTrades` n=8, `allOrders` n=4, FILLED) — **its fills have aged out of both endpoints between run 14 and this run**, which is exactly why it moved from missing-closes to the carry. ETHUSDT `userTrades` returns **n=2** trades, earliest `1795268189087` ms (2026-11-21T07:36:29Z) — order 16876077891 present=0; ETHUSDT `allOrders` returns **n=2** orders, order 16876077891 present=0. Identical to runs 9/11/14 probes — the close's fills (00:34:38Z Nov 20) are still absent from both endpoints.
- **Income confirmation (independent, same probe):** SUIUSDT REALIZED_PNL rows within ±5 min of the SUI close's fill time sum to **+30.5009 over 1 row** — exactly the recorded amount. ETHUSDT REALIZED_PNL rows within ±5 min of the ETH close's fill times sum to **+19.9399 over 2 rows** — exactly the recorded amount. Spot checks on micro-closes: TRXUSDT order 1173153567, 1 row, **−0.0055**; MANAUSDT order 241723755, 1 row, **−0.0376** — both exactly recorded. The carried amounts are income-endpoint sums, never the residual — the identity stays an independent check.
- **Matching (82 Binance rows):** BOTH 4, EXIT_ONLY 15, NO_MATCH 63 — see §8 for the shift vs run 14 (BOTH 5, EXIT_ONLY 14, NO_MATCH 63). Matched-exit set: matched exit realised −188.8111 vs matched ledger net −190.1671; the difference is the matched rows' fees, 1.3560, so the matched set ties out exactly. **Diffs over $0.50: none.** Unmatched zero-realised fills: 18 orders — entry legs of the open positions + breakeven entries — visible, never silently dropped.

## §4 — Window identity (re-derived from the report)

Ledger window net (Binance) −87.9231 + missing closes −31.6607 + aged-out carry +48.8725 + window fees 3.3171 = expected venue realised **−67.3942**; venue realised **−67.4283**; residual **−0.0341**, tolerance 10.5, status **RECONCILED**. Check: residual run 14 (−0.0341) = this run (−0.0341) ✓ — the identity has been stable across runs 9, 10, 11, 13, 14 and 15. Venue true net (incl. carry) −70.7591 = ledger window net −87.9709 + missing −31.6607 + carry +48.8725 ✓ (definition stated in §1 — the excl-carry figure −119.6316 differs only by the carry). Report `forward_window.venue_true_net_pnl` −70.7591 = ledger window net + missing + carry ✓. (Tolerance prints 10.5 this run vs 10.49 in run 14's report — a rounding/display difference in the reconciler's tolerance figure; the residual and the verdict are identical.)

## §5 — Funding cross-check: STR-090 pagination fix holds live

Independent direct `income()` call (separate process, same reader, same env file): **1,272 income rows** since the reset floor — 910 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER — totals **FUNDING_FEE +0.7455, COMMISSION −9.8158, REALIZED_PNL −67.4282, TRANSFER +15,000.03**. The identity-critical REALIZED_PNL agrees with the report (−67.4283) to 0.0001; COMMISSION agrees to 0.0008. **Funding probe-vs-report delta (flagged, not hidden):** the probe's FUNDING_FEE total (+0.7455) sits 0.0099 above the report's (+0.7356). The probe total is stable — a second independent `income()` call minutes later returns the same 1,272 rows and the same +0.7455 — so this is a fixed fetch difference between the reconciler's run and the probe, not drift, and funding is not part of the window identity. The 1,000-row venue cap is paginated past (1,272 > 1,000). Funding grew 881 → 910 rows at the 08:00 UTC settlement (net −0.0612 across the 29 new rows — funding payments can be negative); it is accruing, not frozen.

## §6 — Open positions at run time (30, unrealised +58.2736) + wallet note

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 93.62552119 | +8.1272 |
| ADAUSDT | 301.0 | 0.1494 | 0.1461 | −0.9933 |
| ALGOUSDT | −2293.4 | 0.08004 | 0.07907018 | +2.2242 |
| APTUSDT | −116.9 | 0.4356 | 0.37788503 | +6.7469 |
| ARBUSDT | −410.7 | 0.1269168736304 | 0.11279658 | +5.7992 |
| ATOMUSDT | −151.7 | 1.186 | 1.19836571 | −1.8759 |
| AVAXUSDT | −3.0 | 7.015 | 6.53155252 | +1.4503 |
| BCHUSDT | −0.388 | 208.3815979381 | 206.68383012 | +0.6587 |
| BNBUSDT | −0.08 | 590.59 | 552.07 | +3.0816 |
| BTCUSDT | 0.0025 | 59889.32 | 59796.76804348 | −0.2314 |
| DOGEUSDT | −1453.0 | 0.05505 | 0.05682894 | −2.5848 |
| DOTUSDT | −102.7 | 0.6728 | 0.65409076 | +1.9214 |
| ETCUSDT | −14.63 | 5.659 | 5.816 | −2.2969 |
| ETHUSDT | 0.111 | 1681.3 | 1656.35464147 | −2.7689 |
| FILUSDT | −81.9 | 0.5788 | 0.5151739 | +5.2110 |
| HBARUSDT | −1433.0 | 0.05152 | 0.05337395 | −2.6567 |
| INJUSDT | −19.0 | 6.657 | 6.277 | +7.22 |
| LINKUSDT | −8.79 | 8.629 | 9.164 | −4.7027 |
| LTCUSDT | 5.72 | 44.37 | 44.11144028 | −1.4790 |
| MANAUSDT | −1342.0 | 0.060599538003 | 0.05665 | +5.3003 |
| NEARUSDT | −14.0 | 2.901 | 3.024 | −1.722 |
| OPUSDT | −661.6 | 0.0768 | 0.06924282 | +4.9998 |
| SANDUSDT | −1822.0 | 0.03348 | 0.03353 | −0.0911 |
| SOLUSDT | −2.1 | 69.02 | 71.16792828 | −4.5106 |
| SUIUSDT | −96.1 | 0.6446 | 0.6682 | −2.2680 |
| TRXUSDT | −750.0 | 0.30999 | 0.30041 | +7.185 |
| UNIUSDT | −9.0 | 4.707444444444 | 4.69431852 | +0.1181 |
| VETUSDT | 40580.0 | 0.004618 | 0.00486118 | +9.8682 |
| XLMUSDT | −1792.0 | 0.13436 | 0.12419419 | +18.2171 |
| XRPUSDT | −93.7 | 0.925 | 0.94286928 | −1.6744 |

Wallet note (carried): demo wallet balance moves independently of the income ledger (venue-side snapshot, not part of the reconciled identity) — wallet 10,438.87 → 10,436.79 while realised P&L is unchanged; the movement is mark-price drift on the open positions, not a ledger change.

## §7 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge); `Stratex.service` **active**, `Stratex-Daemon.service` **active** (verified first-hand this run). The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- **Timer note (recurring):** the 01:00 UTC `friday-stratex-reconciliation.timer` run overwrote `daily_2026-11-28.json` with the **stale-checkout** report (DISCREPANCY, residual +38.5348 per run 9 §7) before run 10; runs 10/11/13/14/15 overwrote it in turn with fixed-code RECONCILED reports. The pre-run snapshot `/tmp/muse20-str114-before.json` (md5 `c2b573e64ece3a462be8b60b64b2de23`) preserves run 14's report; this run's report (md5 `6a64f891821aa48042d35d5da5ce60bc`) is snapshotted at `/tmp/muse20-str114-report.json`. The timer overwriting the live file daily with a wrong DISCREPANCY is worth a coordinator ruling (point the timer at the fixed code, or stop it writing the live file) — still open, carried from runs 9/10/11/13/14.
- **Bridge note:** no outage this run. `list-tools` exit 0; `run_shell` probes and the run itself exit 0 on server 4 throughout (bridge `friday-universe.duckdns.org/bridge/mcp`, standing clearance 7200564540).
- Extract: `git fetch origin main` + `git archive 527b073d Stratex | tar -x -C /tmp/muse20-str114` on Stratex-Server (origin/main `527b073d` on fetch). Reconciler + test sha256 verified above; source identical to runs 9/10/11/13/14.
- Run (backgrounded, log `/tmp/muse20-str114-run.log` on Stratex-Server):
  `cd /tmp/muse20-str114/Stratex && PYTHONPATH=/tmp/muse20-str114/Stratex:/tmp/muse20-str114 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-28`
  (the timer service's own invocation, with the extract paths substituted so the merged fixed code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-28: ledger 84 rows (window 75, net -87.97), matching {'NO_MATCH': 63, 'EXIT_ONLY': 15, 'BOTH': 4}, missing closes 3 (-31.66), aged-out carry 32 (+48.87), resets 6 (0 new), status RECONCILED`.
- Tests: `pytest tests/test_daily_fill_ledger_reconciliation.py -q` from the extract with the daemon venv python: **37 passed, 1 warning in 2.98s**. The warning is the pre-existing `PytestConfigWarning: Unknown config option: asyncio_mode`, not a failure.
- Report field note (carried observation): the report's `task` field still reads `TASK-STR-044` (the reconciler's own stamp), not TASK-STR-114 — cosmetic, the reconciler was not modified for this run.
- Window start: 2026-11-15T11:29:49+05:30 (epoch 1794722389.0). Venue: `binance_futures_demo`. Gaps: G1 3 venue closes no ledger row (−31.66); G1-carry 32 aged-out (+48.87); G-trace 73/84 ledger rows carry no order_id.

## §8 — Matching-class shift vs run 14 + the SUI move (material, flagged plainly)

Run 14 (04:47 UTC): BOTH 5, EXIT_ONLY 14, NO_MATCH 63; matched sums −188.8111 / −190.1671; unmatched zero-realised 18. This run (08:03 UTC): BOTH **4**, EXIT_ONLY **15**, NO_MATCH **63**; matched sums **−188.8111 / −190.1671** (identical to the cent); unmatched zero 18. The row that moved BOTH → EXIT_ONLY carries zero realised — the matched sums are identical, so its exit realised must be 0.0000 — consistent with a zero-realised entry-leg fill aging out of `userTrades` while its order remains in `allOrders`. The report does not carry per-row classes, so the individual order is not named here; the inference from the unchanged matched sums is stated as an inference, not a verified identification. **The SUI move is the same mechanism one step further:** the SUIUSDT close's fills aged out of both `userTrades` and `allOrders` entirely, so it left missing-closes for the carry (§3 proves this directly — present in both endpoints at run 14, absent from both at this run, income-confirmed at exactly +30.5009). The identity is unaffected — it rests on income totals, which are unchanged — and `diffs_over_0.5` is still empty. Worth a note to the reconciler owner: row-level traceability degrades as fills age out, even while the identity holds. No ruling owed on this run's verdict.
