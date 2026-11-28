# TASK-STR-117 — Forward-window fill-ledger state run 17 (evidence)

- **Task:** Stratex: forward-window fill-ledger state run 17 — fills, closes, net P&L vs venue.
- **Owner:** Muse 9. **Claim:** hub #2045 comment 7237897037, 2026-11-28 ~15:54 IST, per WATCH267 head, confirmed WATCH268 §C (hub 7237659936); FUT-051 gate lifted (PR #2329 MERGED → c413c66c, M14 VERIFIED review 6097076461). **Board:** CLAIMED / muse_9 in board PR #2331 (head 40ade0da) — flip rides the coordinator board PR; no board hunk in this PR, ruling 7200564540 §3. Acceptance = daemon fill/close ledger reconciled end-to-end against venue positions/history, evidence as `docs/collaboration/TASK-STR-117-EVIDENCE.md`.
- **Branch:** `muse9/task-str-117` from main `2a5de318`.
- **Sequence note (plainly):** run 18 (TASK-STR-118, Muse TP7) executed **before** this run — TP7 claimed STR-118 (hub 7237748645) and ran at 2026-11-28T10:16:06Z, 11 minutes before this run (10:27:32Z). The board numbers this run 17, the next window after STR-116 run 16 (Muse TP7, PR #2321 MERGED f7ec8314, RECONCILED, residual −0.0341), but execution order was run 18 then run 17. Run 18's report is this run's pre-run snapshot (§7); run 17 is an independent re-verification, compared against both run 16 and run 18 below. Nothing was hidden by the inversion: all three runs agree on every identity-critical figure.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `2a5de318`) run live on Stratex-Server (server 4) from a fresh extract `/tmp/muse9-str117` at `2a5de318` (the live checkout is on main `3db55adf`, which predates the STR-090 merge — the extract, not the live checkout, supplies the fixed code; the live checkout and the daemon were not touched). `git archive 2a5de318 Stratex | tar -x` used directly (M3's run-9 note: `git worktree add` dropped repeatedly on bridge transport). Reconciler sha256 `c1da1c1399de7ea0e4c04c1832845e16a03e84cb820c254bce4bf85b0b3d08f1` — **byte-identical to runs 9, 10, 11, 13, 14, 15, 16 and 18**. Test file sha256 `fa0831288a732e1708d3e42e9650ae58456839bb4636b810e15b5286e3ebba9a` — also identical to runs 9/10/11/13/14/15/16/18. Daemon venv python. Run at 2026-11-28T10:27:32Z / 15:57:32 IST. Report filed at `Stratex/state/reconciliation/daily_2026-11-28.json` on Stratex-Server and snapshotted to `/tmp/muse9-str117-report.json` on Stratex-Server (md5 `6881f7465637f098bad13925e47cc69e`, live file and snapshot identical — re-verified first-hand after the run). The pre-run report is preserved at `/tmp/muse9-str117-before.json` (md5 `5a25d8759c7dd8f0e4ba27789f934cf3` — run 18's report, Muse TP7; live file md5 matched before this run started). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/muse9-str117/Stratex:/tmp/muse9-str117` so the fixed code runs. Exact command in §7.
- **Host note (carried from runs 6/7/8/9/10/11/13/14/15/16/18):** the Oracle Server 1 copy of the Stratex state dir is a **frozen pre-migration copy** — do not re-run against the S1 copy; the live state is on Stratex-Server, as STR-091/STR-094/STR-095/STR-096/STR-100/STR-101/STR-102/STR-105/STR-108/STR-109/STR-111/STR-112/STR-114/STR-116 did. This run used Stratex-Server (server 4).

## Verdict

**RECONCILED.** The forward-window identity residual is **−0.0341 USDT** against a tolerance of 10.49 USDT — identical residual to runs 9, 10, 11, 13, 14, 15, 16 and 18 to the cent. The ledger is byte-identical to runs 9–18 state (md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, 84 rows, last close 2026-11-27T02:26:41Z) — nothing was lost, nothing was written, no close was missed by the daemon. **No material delta vs run 18 or run 16:** matching classes, matched sums, missing closes, carry, unmatched-zero count and income totals are all identical (§8). The only movements are mark-price drift on the 30 open positions (unrealised +61.29 → +60.73 vs run 18; wallet −1.00 — see the wallet note in §6, it does not tie to the income deltas and is not part of the reconciled identity). No matched row disagrees with the venue by more than $0.50 (`diffs_over_0.5: []`). **Root cause of the standing −0.0341 residual (found by run 10, TP13 §4, confirmed here):** the INJUSDT micro-close's second fill income row (−0.034) is not in the carry — the carry understates by exactly the residual. No ruling owed on the identity; the carry gap is an observation for the reconciler owner, not a discrepancy. Open observations (timer stale-checkout overwrite, wallet note) are filed in §7, not hidden. The funding probe-vs-report gap seen in runs 15/16 is **closed** this run — probe and report agree to the cent on all four income totals (§5).

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-27T02:26:41Z last close)

| Figure | This run (STR-117, 10:27 UTC) | Run 18 (STR-118, 10:16 UTC) | Run 16 (STR-116, 08:41 UTC) |
|---|---|---|---|
| Ledger closes, all time | 84 rows | 84 rows | 84 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 | +107.089 |
| Ledger closes in forward window | 75 rows | 75 rows | 75 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.923 + OANDA USDJPY −0.0478) | −87.9709 | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 | 3.3171 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 40 rows −147.9099 | same | same |
| Venue closes in window | **78** (75 ledger + 3 missing) | 78 (75 + 3) | 78 (75 + 3) |
| Venue window true net P&L (excl. carry) | **−119.6316** (−87.9709 − 31.6607) | −119.6316 | −119.6316 |
| Report `forward_window.venue_true_net_pnl` (incl. carry) | **−70.7591** (−87.9709 − 31.6607 + 48.8725) | −70.7591 | −70.7591 |
| Report `forward_window.closes_on_venue` | 110 (75 ledger + 3 missing + 32 carry) | 110 (75 + 3 + 32) | 110 |
| Venue account at run time | wallet 10,432.58, margin 10,493.27, unrealised +60.68, available 9,483.15 USDT (USDT 4,924.29 + USDC 5,000 + BTC 0.01) | wallet 10,433.58, margin 10,494.73, unrealised +61.15, available 9,484.68 USDT (USDT 4,924.29 + USDC 5,000 + BTC 0.01) | wallet 10,434.66, margin 10,493.35, unrealised +58.69, available 9,481.55 USDT (USDT 4,924.29 + USDC 5,000 + BTC 0.01) |
| Open positions at run time | 30, unrealised +60.73 (positions sum) / +60.68 (account) | 30, +61.29 / +61.15 | 30, +58.74 / +58.69 |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−67.4283**, COMMISSION **−9.8166**, FUNDING_FEE **+0.7449**, TRANSFER +15,000.03 | REALISED_PNL −67.4283, COMMISSION −9.8166, FUNDING_FEE +0.7449, TRANSFER +15,000.03 | REALISED_PNL −67.4283, COMMISSION −9.8166, FUNDING_FEE +0.7449, TRANSFER +15,000.03 |
| Income rows fetched (independent probe) | **1,272** (910 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) | 1,272 (run 18 probe files, same counts) | 1,272 (910 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` | `[]` |

Change run 18 → this run: no new ledger close (ledger md5 identical, 84 rows, last close unchanged 2026-11-27T02:26:41Z). No matching-class shift, no missing/carry movement. The only movement is mark-price drift on the 30 open positions (unrealised +61.29 → +60.73; wallet −1.00 — see the wallet note in §6).

## §2 — Net P&L by symbol (window, 75 closes — re-derived independently this run)

Re-derived from the live ledger (`fill_ledger.jsonl`, exit_time ≥ forward-window start) in a separate process from the reconciler run; matches the report exactly in total (−87.9709) and matches run 16 §2 per-symbol to the cent on every symbol (ALGO −2.1276 vs −2.1275 and LINK +1.8418 vs +1.8419 differ by 0.0001 — rounding in the re-derive probe's 4-decimal print; the unrounded totals tie exactly):

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

The 75 window rows are the same rows as run 7 §5 / run 8 §2 / run 9 §2 / run 11 §2 / run 14 §2 / run 15 §2 / run 16 §2 (ledger unchanged since run 7 — same md5, same per-symbol nets, same all-time cross-check); they are not reprinted here. Outside-window rows: 9, all 2026-11-14, unchanged. (The report's ledger symbols list also carries PAXGUSDT, as run 15/16's reports did — it has no window rows and contributes 0.0000.)

## §3 — The aged-out carry: proof (independent probe, separate process)

- **Missing closes (G1) — 3, realised −31.6607** (run 18: 3, −31.6607; run 16: 3, −31.6607 — unchanged): VETUSDT order 458616420 BUY 42,328 **−10.9206**; SANDUSDT order 340506462 BUY 5,219 **−11.3252**; LTCUSDT order 1615011544 BUY 5.706 **−9.4149**.
- **Aged-out carry — 32 orders, realised +48.8725, all income-confirmed, 0 unconfirmed** (run 18: 32, +48.8725; run 16: 32, +48.8725 — unchanged; recomputed sum from the report's carry list = +48.8725 exactly). The SUIUSDT close (order `1100728824`, BUY 304.4, **+30.5009**, 1 fill, first fill `1795241768054`); the ETHUSDT close (order `16876077891`, BUY 0.148, **+19.9399**, 2 fills, first/last fill `1795202078059`) plus 30 micro-closes (−0.0055 … −0.136 each, first fills 2026-11-19, totalling −1.5683 — the Nov-19 reset-wipe micro-closes behind the unchanged-since-run-2 base residual). The 30 micro-closes are one per symbol (TRX, MANA, FIL, DOT, ETH, SUI, BCH, INJ, ETC, LTC, ATOM, XRP, LINK, VET, NEAR, AAVE, BTC, SOL, APT, AVAX, UNI, BNB, DOGE, XLM, OP, HBAR, ALGO, ADA, SAND, ARB).
- **Direct venue probe** (this run's `/tmp/muse9-str117-venue-probe.py`, same `DemoFuturesReader`, same env file, separate process from the reconciler run): SUIUSDT `userTrades` returns **n=6** trades, earliest `1795266451107` ms (2026-11-21T07:47:31Z) — order 1100728824 present=0; SUIUSDT `allOrders` returns **n=2** orders, order 1100728824 present=0. ETHUSDT `userTrades` returns **n=2** trades, earliest `1795268189087` ms (2026-11-21T07:36:29Z) — order 16876077891 present=0; ETHUSDT `allOrders` returns **n=2** orders, order 16876077891 present=0. Identical to run 16's probe — the SUI close's fills remain aged out of both endpoints, and the ETH close's fills (00:34:38Z Nov 20) are still absent from both endpoints.
- **Income confirmation (independent, same probe):** SUIUSDT REALIZED_PNL rows within ±5 min of the SUI close's fill time sum to **+30.5009 over 1 row** — exactly the recorded amount. ETHUSDT REALIZED_PNL rows within ±5 min of the ETH close's fill times sum to **+19.9399 over 2 rows** — exactly the recorded amount. Spot checks on micro-closes: TRXUSDT order 1173153567, 1 row, **−0.0055**; MANAUSDT order 241723755, 1 row, **−0.0376** — both exactly recorded. The carried amounts are income-endpoint sums, never the residual — the identity stays an independent check.
- **Matching (82 Binance rows):** BOTH 4, EXIT_ONLY 15, NO_MATCH 63 — unchanged from runs 16/18 (see §8). Matched-exit set: matched exit realised −188.8111 vs matched ledger net −190.1671; the difference is the matched rows' fees, 1.3560, so the matched set ties out exactly. **Diffs over $0.50: none.** Unmatched zero-realised fills: 18 orders — entry legs of the open positions + breakeven entries — visible, never silently dropped.

## §4 — Window identity (re-derived from the report)

Ledger window net (Binance) −87.9231 + missing closes −31.6607 + aged-out carry +48.8725 + window fees 3.3171 = expected venue realised **−67.3942**; venue realised **−67.4283**; residual **−0.0341**, tolerance 10.49, status **RECONCILED**. Check: residual run 16 (−0.0341) = run 18 (−0.0341) = this run (−0.0341) ✓ — the identity has been stable across runs 9, 10, 11, 13, 14, 15, 16, 18 and 17. Venue true net (incl. carry) −70.7591 = ledger window net −87.9709 + missing −31.6607 + carry +48.8725 ✓ (definition stated in §1 — the excl-carry figure −119.6316 differs only by the carry). Report `forward_window.venue_true_net_pnl` −70.7591 = ledger window net + missing + carry ✓.

## §5 — Funding cross-check: STR-090 pagination fix holds live; probe-vs-report gap closed

Independent direct `income()` call (separate process, same reader, same env file): **1,272 income rows** since the reset floor — 910 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER — totals **FUNDING_FEE +0.7449, COMMISSION −9.8166, REALIZED_PNL −67.4283, TRANSFER +15,000.03**. All four totals agree with the report to the cent this run. Run 15's probe sat 0.0099 above its report on funding and run 16's 0.0006 above; this run the gap is **0.0000** — the probe total (+0.7449) equals the report total exactly, and the row counts are unchanged at 910 funding rows since the 08:00 UTC settlement (next settlement 16:00 UTC); it is accruing, not frozen. The 1,000-row venue cap is paginated past (1,272 > 1,000). Funding is not part of the window identity in any case.

## §6 — Open positions at run time (30, unrealised +60.7291) + wallet note

Unrealised per symbol computed as (mark − entry) × amount from the report's positions list; the column sums to +60.7291, exactly the report's `open_positions.unrealized_pnl` (account unrealised +60.6843 differs by 0.0448 — mark snapshot timing, as in prior runs):

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 93.20498332 | +8.3375 |
| ADAUSDT | 301.0 | 0.1494 | 0.1459 | −1.0535 |
| ALGOUSDT | −2293.4 | 0.08004 | 0.07865306 | +3.1808 |
| APTUSDT | −116.9 | 0.4356 | 0.3781 | +6.7218 |
| ARBUSDT | −410.7 | 0.1269168736304 | 0.1122 | +6.0442 |
| ATOMUSDT | −151.7 | 1.186 | 1.205 | −2.8823 |
| AVAXUSDT | −3.0 | 7.015 | 6.51237275 | +1.5079 |
| BCHUSDT | −0.388 | 208.3815979381 | 206.75756109 | +0.6301 |
| BNBUSDT | −0.08 | 590.59 | 551.46017424 | +3.1304 |
| BTCUSDT | 0.0025 | 59889.32 | 59342.54198982 | −1.3669 |
| DOGEUSDT | −1453.0 | 0.05505 | 0.05664203 | −2.3132 |
| DOTUSDT | −102.7 | 0.6728 | 0.6504 | +2.3005 |
| ETCUSDT | −14.63 | 5.659 | 5.78358161 | −1.8226 |
| ETHUSDT | 0.111 | 1681.3 | 1651.7303876 | −3.2822 |
| FILUSDT | −81.9 | 0.5788 | 0.5135 | +5.3481 |
| HBARUSDT | −1433.0 | 0.05152 | 0.05330134 | −2.5527 |
| INJUSDT | −19.0 | 6.657 | 6.20493041 | +8.5893 |
| LINKUSDT | −8.79 | 8.629 | 9.177 | −4.8169 |
| LTCUSDT | 5.72 | 44.37 | 44.03 | −1.9448 |
| MANAUSDT | −1342.0 | 0.060599538003 | 0.05628 | +5.7968 |
| NEARUSDT | −14.0 | 2.901 | 2.998 | −1.3580 |
| OPUSDT | −661.6 | 0.0768 | 0.069 | +5.1605 |
| SANDUSDT | −1822.0 | 0.03348 | 0.03357 | −0.1640 |
| SOLUSDT | −2.1 | 69.02 | 70.92 | −3.9900 |
| SUIUSDT | −96.1 | 0.6446 | 0.66542594 | −2.0014 |
| TRXUSDT | −750.0 | 0.30999 | 0.3005 | +7.1175 |
| UNIUSDT | −9.0 | 4.707444444444 | 4.692 | +0.1390 |
| VETUSDT | 40580.0 | 0.004618 | 0.004827 | +8.4812 |
| XLMUSDT | −1792.0 | 0.13436 | 0.1236 | +19.2819 |
| XRPUSDT | −93.7 | 0.925 | 0.9409 | −1.4898 |

Wallet note (carried): demo wallet balance moves independently of the income ledger (venue-side snapshot, not part of the reconciled identity) — wallet 10,433.58 (run 18) → 10,432.58 while realised P&L is unchanged; the movement is mark-price drift on the open positions, not a ledger change.

## §7 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge); `Stratex.service` **active**, `Stratex-Daemon.service` **active** (verified first-hand before and after this run). The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- **Timer note (recurring):** the 01:00 UTC `friday-stratex-reconciliation.timer` run overwrote `daily_2026-11-28.json` with the **stale-checkout** report (DISCREPANCY, residual +38.5348 per run 9 §7) before run 10; runs 10/11/13/14/15/16/18 overwrote it in turn with fixed-code RECONCILED reports, and this run overwrites run 18's. The pre-run snapshot `/tmp/muse9-str117-before.json` (md5 `5a25d8759c7dd8f0e4ba27789f934cf3`) preserves run 18's report; this run's report (md5 `6881f7465637f098bad13925e47cc69e`) is snapshotted at `/tmp/muse9-str117-report.json`. The timer overwriting the live file daily with a wrong DISCREPANCY is worth a coordinator ruling (point the timer at the fixed code, or stop it writing the live file) — still open, carried from runs 9/10/11/13/14/15/16.
- **Bridge note:** no outage this run. `run_shell` probes and the run itself exit 0 on server 4 throughout (bridge `friday-universe.duckdns.org/bridge/mcp`, standing clearance 7200564540).
- Extract: `git fetch origin main` + `git archive 2a5de318 Stratex | tar -x -C /tmp/muse9-str117` on Stratex-Server (origin/main `2a5de318` on fetch). Reconciler + test sha256 verified above; source identical to runs 9/10/11/13/14/15/16/18.
- Run (backgrounded, log `/tmp/muse9-str117-run.log` on Stratex-Server, pid 107766):
  `cd /tmp/muse9-str117/Stratex && PYTHONPATH=/tmp/muse9-str117/Stratex:/tmp/muse9-str117 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-28`
  (the timer service's own invocation, with the extract paths substituted so the merged fixed code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-28: ledger 84 rows (window 75, net -87.97), matching {'NO_MATCH': 63, 'EXIT_ONLY': 15, 'BOTH': 4}, missing closes 3 (-31.66), aged-out carry 32 (+48.87), resets 6 (0 new), status RECONCILED`.
- Tests: `pytest tests/test_daily_fill_ledger_reconciliation.py -q` from the extract with the daemon venv python: **37 passed, 1 warning in 0.93s**. The warning is the pre-existing `PytestConfigWarning: Unknown config option: asyncio_mode`, not a failure.
- Report field note (carried observation): the report's `task` field still reads `TASK-STR-044` (the reconciler's own stamp), not TASK-STR-117 — cosmetic, the reconciler was not modified for this run.
- Window start: 2026-11-15T11:29:49+05:30 (epoch 1794722389.0). Venue: `binance_futures_demo`. Gaps: G1 3 venue closes no ledger row (−31.66); G1-carry 32 aged-out (+48.87); G-trace 73/84 ledger rows carry no order_id.
- Probes (this run, all read-only, separate processes): `/tmp/muse9-str117-report-probe.py` (report fields for runs 17/18/16), `/tmp/muse9-str117-venue-probe.py` (income totals + aged-out checks, §3/§5), `/tmp/muse9-str117-ledger-probe.py` (per-symbol re-derive, §2). Sources kept at `~/workspace/friday-bridge/str117_{report,venue,ledger}_probe.py` + `run_str117_probes.py` (Muse 9 workspace).

## §8 — No shift vs run 18 (nothing moved)

Run 18 (10:16 UTC): BOTH 4, EXIT_ONLY 15, NO_MATCH 63; matched sums −188.8111 / −190.1671; unmatched zero 18. This run (10:27 UTC): BOTH **4**, EXIT_ONLY **15**, NO_MATCH **63**; matched sums **−188.8111 / −190.1671** (identical to the cent); unmatched zero 18. Missing closes 3 (−31.6607) and carry 32 (+48.8725) are identical; the SUIUSDT close that moved missing → carry between run 14 and run 15 stays in the carry, income-confirmed at exactly +30.5009 (§3 re-proves this directly — absent from both `userTrades` and `allOrders` at this run, present in the income endpoint). The identity is unaffected — it rests on income totals, which are unchanged — and `diffs_over_0.5` is still empty. Worth a note to the reconciler owner: row-level traceability degrades as fills age out, even while the identity holds. No ruling owed on this run's verdict.

## §9 — States

implemented YES / tested YES / merged NO / deployed NO / production-verified NO (paired verification + merge owed; run 17 is Muse 9's STR-117, executed after run 18 — see sequence note).

— Muse 9, 2026-11-28
