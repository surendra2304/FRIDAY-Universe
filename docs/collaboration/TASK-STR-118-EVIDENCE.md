# TASK-STR-118 — Forward-window fill-ledger state run 18 (evidence)

- **Task:** Stratex: forward-window fill-ledger state run 18 — fills, closes, net P&L vs venue.
- **Owner:** Muse TP7. **Claim:** hub #2045 comment 7237748645, 2026-11-28 15:42:52 IST, per WATCH268 §C (Burn Enforcer 15:30 §B adopted, WATCH268 comment 7237659936). **Board:** CLAIMED / muse_tp7 — record live on main via board PR #2331 (merged 3b5091de); branch/pr fields still null, flip rides the coordinator board PR; no board hunk in this PR (ruling 7200564540 §3). Acceptance = daemon fill/close ledger reconciled end-to-end against venue positions/history, evidence as `docs/collaboration/TASK-STR-118-EVIDENCE.md`.
- **Branch:** `musetp7/task-str-118-fill-ledger-run18` from main `ed0bd3eb`.
- **Sequence note:** the board titles this run 18, the next window after STR-116 run 16 (TP7, PR #2321 merged WATCH266) and STR-117 run 17 (Muse 9 head). Run 17 had NO evidence on main when run 18 ran (10:16 UTC) — run 18's pre-run snapshot is therefore the 09:06 UTC re-run report (see §7), itself identical in identity to run 16. The sequence is now closed: Muse 9 ran run 17 at 10:27:32 UTC and filed PR #2335 (hub #2045 comment 7237983556, 16:04 IST) — run 17 RECONCILED, residual −0.0341, evidence notes run 18 ran first. Runs 16, 17 and 18 all agree to the cent. Run 18 ran before run 17 — filed plainly here, as run 17's evidence does.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `ed0bd3eb`) run live on Stratex-Server (server 4) from a fresh extract `/tmp/musetp7-str118` at `ed0bd3eb` (the live checkout is on main `3db55adf`, which predates the STR-090 merge — the extract, not the live checkout, supplies the fixed code; the live checkout and the daemon were not touched). `git archive ed0bd3eb Stratex | tar -x` used directly (M3's run-9 note: `git worktree add` dropped repeatedly on bridge transport). Reconciler sha256 `c1da1c1399de7ea0e4c04c1832845e16a03e84cb820c254bce4bf85b0b3d08f1` — **byte-identical to runs 9–16**. Test file sha256 `fa0831288a732e1708d3e42e9650ae58456839bb4636b810e15b5286e3ebba9a` — also identical to runs 9/10/11/13/14/15/16. Daemon venv python. Run at 2026-11-28T10:16:06Z / 15:46:06 IST, pid 106826. Report filed at `Stratex/state/reconciliation/daily_2026-11-28.json` on Stratex-Server and snapshotted to `/tmp/musetp7-str118-report.json` on Stratex-Server (md5 `5a25d8759c7dd8f0e4ba27789f934cf3`, live file and snapshot identical at the run — re-verified first-hand after the run; see §7 for the later run-17 overwrite). The pre-run report is preserved at `/tmp/musetp7-str118-before.json` (md5 `09809e610170b5df3c20964eb4521c02` — the 09:06 UTC report, Muse 3; live file md5 matched before this run started). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/musetp7-str118/Stratex:/tmp/musetp7-str118` so the fixed code runs. Exact command in §7.
- **Host note (carried from runs 6/7/8/9/10/11/13/14/15/16):** the Oracle Server 1 copy of the Stratex state dir is a **frozen pre-migration copy** — do not re-run against the S1 copy; the live state is on Stratex-Server, as STR-091/STR-094/STR-095/STR-096/STR-100/STR-101/STR-102/STR-105/STR-108/STR-109/STR-111/STR-112/STR-114/STR-116 did. This run used Stratex-Server (server 4).

## Verdict

**RECONCILED.** The forward-window identity residual is **−0.0341 USDT** against a tolerance of 10.49 USDT — identical residual to runs 9, 10, 11, 13, 14, 15, 16 and 17 to the cent. The ledger is byte-identical to runs 9–16 state (md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, 84 rows, last close 2026-11-27T02:26:41Z) — nothing was lost, nothing was written, no close was missed by the daemon. **No material delta vs run 16:** matching classes, matched sums, missing closes, carry, unmatched-zero count and income totals are all identical (§8). The only movements are mark-price drift on the 30 open positions (unrealised +58.74 → +61.29; wallet −1.07 — see the wallet note in §6, it does not tie to the income deltas and is not part of the reconciled identity) and the report's funding total unchanged at +0.7449 (independent probe total unchanged at +0.7455 — see §5; funding is not part of the window identity). No matched row disagrees with the venue by more than $0.50 (`diffs_over_0.5: []`). **Root cause of the standing −0.0341 residual (found by run 10, TP13 §4, confirmed here):** the INJUSDT micro-close's second fill income row (−0.034) is not in the carry — the carry understates by exactly the residual. No ruling owed on the identity; the carry gap is an observation for the reconciler owner, not a discrepancy. Open observations (timer stale-checkout overwrite, 09:06 re-run, funding probe-vs-report delta, wallet note) are filed in §5/§7, not hidden.

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-27T02:26:41Z last close)

| Figure | This run (STR-118, 10:16 UTC) | Run 16 (STR-116, 08:41 UTC) |
|---|---|---|
| Ledger closes, all time | 84 rows | 84 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 |
| Ledger closes in forward window | 75 rows | 75 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.9231 + OANDA USDJPY −0.0478) | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 40 rows −147.9099 | same |
| Venue closes in window | **78** (75 ledger + 3 missing) | 78 (75 + 3) |
| Venue window true net P&L (excl. carry) | **−119.6316** (−87.9709 − 31.6607) | −119.6316 |
| Report `forward_window.venue_true_net_pnl` (incl. carry) | **−70.7591** (−87.9709 − 31.6607 + 48.8725) | −70.7591 |
| Report `forward_window.closes_on_venue` | 110 (75 ledger + 3 missing + 32 carry) | 110 |
| Venue account at run time | wallet 10,433.58, margin 10,494.73, unrealised +61.15, available 9,484.68 USDT (USDT 4,924.29 + USDC 5,000 + BTC 0.01) | wallet 10,434.66, margin 10,493.35, unrealised +58.69, available 9,481.55 USDT (USDT 4,924.29 + USDC 5,000 + BTC 0.01) |
| Open positions at run time | 30, unrealised +61.29 (positions sum) / +61.15 (account) | 30, +58.74 / +58.69 |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−67.4283**, COMMISSION **−9.8166**, FUNDING_FEE **+0.7449**, TRANSFER +15,000.03 | REALISED_PNL −67.4283, COMMISSION −9.8166, FUNDING_FEE +0.7449, TRANSFER +15,000.03 |
| Income rows fetched (independent probe) | **1,272** (910 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) | 1,272 (910 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` |

Change run 16 → this run: no new ledger close (ledger md5 identical, 84 rows, last close unchanged 2026-11-27T02:26:41Z). No matching-class shift, no missing/carry movement. The only other movement is mark-price drift on the 30 open positions (unrealised +58.74 → +61.29; wallet −1.07 — see the wallet note in §6). The pre-run (09:06 UTC) snapshot agrees on every identity figure; its wallet was 10,435.15 / unrealised +57.32 — same drift, no ledger change.

## §2 — Net P&L by symbol (window, 75 closes — re-derived independently this run)

Re-derived from the live ledger (`fill_ledger.jsonl`, exit_time ≥ forward-window start) in a separate process from the reconciler run; matches the report exactly in total (−87.9709) and matches run 16 §2 per-symbol to the cent on every symbol:

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

The 75 window rows are the same rows as run 7 §5 / run 8 §2 / run 9 §2 / run 11 §2 / run 14 §2 / run 15 §2 / run 16 §2 (ledger unchanged since run 7 — same md5, same per-symbol nets, same all-time cross-check); they are not reprinted here. Outside-window rows: 9, all 2026-11-14, unchanged. (The report's ledger symbols list also carries PAXGUSDT, as run 16's report did — it has no window rows and contributes 0.0000; run 16 §2's table did not print it.)

## §3 — The aged-out carry: proof (independent probe, separate process)

- **Missing closes (G1) — 3, realised −31.6607** (run 16: 3, −31.6607 — unchanged): VETUSDT order 458616420 BUY 42,328 **−10.9206**; SANDUSDT order 340506462 BUY 5,219 **−11.3252**; LTCUSDT order 1615011544 BUY 5.706 **−9.4149**.
- **Aged-out carry — 32 orders, realised +48.8725, all income-confirmed, 0 unconfirmed** (run 16: 32, +48.8725 — unchanged). The SUIUSDT close (order `1100728824`, BUY 304.4, **+30.5009**, 1 fill, 2026-11-21T07:36:08Z); the ETHUSDT close (order `16876077891`, BUY 0.148, **+19.9399**, 2 fills, 2026-11-20T00:34:38Z, first/last fill `1795202078059`) plus 30 micro-closes (−0.0055 … −0.136 each, first fills 2026-11-19, totalling −1.5683 — the Nov-19 reset-wipe micro-closes behind the unchanged-since-run-2 base residual). The 30 micro-closes are one per symbol (TRX, MANA, FIL, DOT, ETH, SUI, BCH, INJ, ETC, LTC, ATOM, XRP, LINK, VET, NEAR, AAVE, BTC, SOL, APT, AVAX, UNI, BNB, DOGE, XLM, OP, HBAR, ALGO, ADA, SAND, ARB).
- **Direct venue probe** (run 16's `/tmp/musetp7-str116-probe.py` lineage, adapted as `/tmp/musetp7-str118-probe.py`, same `DemoFuturesReader`, same env file, separate process from the reconciler run — re-run this run): SUIUSDT `userTrades` returns **n=6** trades, earliest `1795266451107` ms (2026-11-21T07:47:31Z) — order 1100728824 present=0; SUIUSDT `allOrders` returns **n=2** orders, order 1100728824 present=0. ETHUSDT `userTrades` returns **n=2** trades, earliest `1795268189087` ms (2026-11-21T07:36:29Z) — order 16876077891 present=0; ETHUSDT `allOrders` returns **n=2** orders, order 16876077891 present=0. Identical to run 16's probe — the SUI close's fills remain aged out of both endpoints, and the ETH close's fills (00:34:38Z Nov 20) are still absent from both endpoints.
- **Income confirmation (independent, same probe):** SUIUSDT REALIZED_PNL rows within ±5 min of the SUI close's fill time sum to **+30.5009 over 1 row** — exactly the recorded amount. ETHUSDT REALIZED_PNL rows within ±5 min of the ETH close's fill times sum to **+19.9399 over 2 rows** — exactly the recorded amount. Spot checks on micro-closes: TRXUSDT order 1173153567, 1 row, **−0.0055**; MANAUSDT order 241723755, 1 row, **−0.0376** — both exactly recorded. The carried amounts are income-endpoint sums, never the residual — the identity stays an independent check.
- **Matching (82 Binance rows):** BOTH 4, EXIT_ONLY 15, NO_MATCH 63 — unchanged from run 16 (see §8). Matched-exit set: matched exit realised −188.8111 vs matched ledger net −190.1671; the difference is the matched rows' fees, 1.3560, so the matched set ties out exactly. **Diffs over $0.50: none.** Unmatched zero-realised fills: 18 orders — entry legs of the open positions + breakeven entries — visible, never silently dropped.

## §4 — Window identity (re-derived from the report)

Ledger window net (Binance) −87.9231 + missing closes −31.6607 + aged-out carry +48.8725 + window fees 3.3171 = expected venue realised **−67.3942**; venue realised **−67.4283**; residual **−0.0341**, tolerance 10.49, status **RECONCILED**. Check: residual run 16 (−0.0341) = this run (−0.0341) ✓ — the identity has been stable across runs 9, 10, 11, 13, 14, 15, 16, 17 and 18. Venue true net (incl. carry) −70.7591 = ledger window net −87.9709 + missing −31.6607 + carry +48.8725 ✓ (definition stated in §1 — the excl-carry figure −119.6316 differs only by the carry). Report `forward_window.venue_true_net_pnl` −70.7591 = ledger window net + missing + carry ✓.

## §5 — Funding cross-check: STR-090 pagination fix holds live

Independent direct `income()` call (separate process, same reader, same env file): **1,272 income rows** since the reset floor — 910 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER — totals **FUNDING_FEE +0.7455, COMMISSION −9.8158, REALIZED_PNL −67.4282, TRANSFER +15,000.03**. The identity-critical REALIZED_PNL agrees with the report (−67.4283) to 0.0001; COMMISSION agrees to 0.0008. **Funding probe-vs-report delta (flagged, not hidden):** the probe's FUNDING_FEE total (+0.7455) sits 0.0006 above the report's (+0.7449) — the same 0.0006 gap as run 16, and the probe total is unchanged from run 16's probe (+0.7455, same 1,272 rows), so this is a fixed fetch difference between the reconciler's run and the probe, not drift, and funding is not part of the window identity. The 1,000-row venue cap is paginated past (1,272 > 1,000). Funding rows unchanged at 910 since the 08:00 UTC settlement (next settlement 16:00 UTC); it is accruing, not frozen.

## §6 — Open positions at run time (30, unrealised +61.2873) + wallet note

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 93.07 | +8.4050 |
| ADAUSDT | 301.0 | 0.1494 | 0.1457 | −1.1137 |
| ALGOUSDT | −2293.4 | 0.08004 | 0.07864625 | +3.1964 |
| APTUSDT | −116.9 | 0.4356 | 0.3774 | +6.8036 |
| ARBUSDT | −410.7 | 0.1269168736304 | 0.11214781 | +6.0657 |
| ATOMUSDT | −151.7 | 1.186 | 1.201 | −2.2755 |
| AVAXUSDT | −3.0 | 7.015 | 6.5214576 | +1.4806 |
| BCHUSDT | −0.388 | 208.3815979381 | 206.74 | +0.6369 |
| BNBUSDT | −0.08 | 590.59 | 551.75545989 | +3.1068 |
| BTCUSDT | 0.0025 | 59889.32 | 59424.0 | −1.1633 |
| DOGEUSDT | −1453.0 | 0.05505 | 0.05668007 | −2.3685 |
| DOTUSDT | −102.7 | 0.6728 | 0.6494 | +2.4032 |
| ETCUSDT | −14.63 | 5.659 | 5.7831629 | −1.8165 |
| ETHUSDT | 0.111 | 1681.3 | 1652.16524225 | −3.2340 |
| FILUSDT | −81.9 | 0.5788 | 0.51260768 | +5.4212 |
| HBARUSDT | −1433.0 | 0.05152 | 0.05328882 | −2.5347 |
| INJUSDT | −19.0 | 6.657 | 6.23607168 | +7.9976 |
| LINKUSDT | −8.79 | 8.629 | 9.172 | −4.7730 |
| LTCUSDT | 5.72 | 44.37 | 44.04715686 | −1.8467 |
| MANAUSDT | −1342.0 | 0.060599538003 | 0.05628 | +5.7968 |
| NEARUSDT | −14.0 | 2.901 | 3.001 | −1.4000 |
| OPUSDT | −661.6 | 0.0768 | 0.0689086 | +5.2210 |
| SANDUSDT | −1822.0 | 0.03348 | 0.03353787 | −0.1054 |
| SOLUSDT | −2.1 | 69.02 | 71.01 | −4.1790 |
| SUIUSDT | −96.1 | 0.6446 | 0.6654 | −1.9989 |
| TRXUSDT | −750.0 | 0.30999 | 0.30050701 | +7.1122 |
| UNIUSDT | −9.0 | 4.707444444444 | 4.693 | +0.1300 |
| VETUSDT | 40580.0 | 0.004618 | 0.004824 | +8.3595 |
| XLMUSDT | −1792.0 | 0.13436 | 0.12352549 | +19.4154 |
| XRPUSDT | −93.7 | 0.925 | 0.94053288 | −1.4554 |

Wallet note (carried): demo wallet balance moves independently of the income ledger (venue-side snapshot, not part of the reconciled identity) — wallet 10,435.15 → 10,433.58 while realised P&L is unchanged; the movement is mark-price drift on the open positions, not a ledger change.

## §7 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge); `Stratex.service` **active**, `Stratex-Daemon.service` **active** (verified first-hand before and after this run). The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- **Timer note (recurring):** the 01:00 UTC `friday-stratex-reconciliation.timer` run overwrote `daily_2026-11-28.json` with the **stale-checkout** report (DISCREPANCY, residual +38.5348 per run 9 §7) before run 10; runs 10/11/13/14/15/16/18 overwrote it in turn with fixed-code RECONCILED reports. The pre-run snapshot `/tmp/musetp7-str118-before.json` (md5 `09809e610170b5df3c20964eb4521c02`) preserves the 09:06 UTC report; this run's report (md5 `5a25d8759c7dd8f0e4ba27789f934cf3`) is snapshotted at `/tmp/musetp7-str118-report.json`. The timer overwriting the live file daily with a wrong DISCREPANCY is worth a coordinator ruling (point the timer at the fixed code, or stop it writing the live file) — still open, carried from runs 9/10/11/13/14/15/16.
- **09:06 UTC re-run — identified (correction of the 15:39 run note):** the live `daily_2026-11-28.json` was rewritten at 09:06:07 UTC by **Muse 3** — `/tmp/muse3-str116-run.log` (283 bytes, same format) records the fixed-code RECONCILED run; the report is identity byte-identical to run 16. The 15:39 run note said "no /tmp artifact" — the artifact existed and was found in the 16:01 self-check. Not a discrepancy (RECONCILED, same residual).
- **10:27 UTC re-run — identified:** after this run, **Muse 9 ran run 17 (STR-117)** at 10:27:32 UTC (`/tmp/muse9-str117-report.json`, PR #2335, hub 7237983556) — the live file now holds run 17's report. It is identity-identical to run 18's report (only `run_at_utc` and venue-account / open-positions mark drift differ). Run 17's evidence notes run 18 ran first; this evidence notes run 17 ran second. Both stand.
- **Bridge note:** no outage this run. `run_shell` probes and the run itself exit 0 on server 4 throughout (bridge `friday-universe.duckdns.org/bridge/mcp`, standing clearance 7200564540).
- Extract: `git fetch origin main` + `git archive ed0bd3eb Stratex | tar -x -C /tmp/musetp7-str118` on Stratex-Server (origin/main `ed0bd3eb` on fetch). Reconciler + test sha256 verified above; source identical to runs 9/10/11/13/14/15/16.
- Run (backgrounded, log `/tmp/musetp7-str118-run.log` on Stratex-Server, pid 106826):
  `cd /tmp/musetp7-str118/Stratex && PYTHONPATH=/tmp/musetp7-str118/Stratex:/tmp/musetp7-str118 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-28`
  (the timer service's own invocation, with the extract paths substituted so the merged fixed code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-28: ledger 84 rows (window 75, net -87.97), matching {'NO_MATCH': 63, 'EXIT_ONLY': 15, 'BOTH': 4}, missing closes 3 (-31.66), aged-out carry 32 (+48.87), resets 6 (0 new), status RECONCILED`.
- Tests: `pytest tests/test_daily_fill_ledger_reconciliation.py -q` from the extract with the daemon venv python: **37 passed, 1 warning in 2.65s** (re-run in the 16:01 self-check on the run-18 extract; the 15:39 run recorded 37 passed, 1 warning in 2.32s — same result). The warning is the pre-existing `PytestConfigWarning: Unknown config option: asyncio_mode`, not a failure.
- Report field note (carried observation): the report's `task` field still reads `TASK-STR-044` (the reconciler's own stamp), not TASK-STR-118 — cosmetic, the reconciler was not modified for this run.
- Window start: 2026-11-15T11:29:49+05:30 (epoch 1794722389.0). Venue: `binance_futures_demo`. Gaps: G1 3 venue closes no ledger row (−31.66); G1-carry 32 aged-out (+48.87); G-trace 73/84 ledger rows carry no order_id.
- **Main advance / rebase decision:** main has advanced past the branch base since the claim — `2a5de318` (PR #2325, Muse 14 FRG-037) and `3b5091de` (PR #2331, WATCH267 board — STR-118 record now live on main). No rebase: this PR adds one new file, no conflicts with either merge; the PR merges cleanly from the `ed0bd3eb` base. Rebase/merge call rides the coordinator at merge time.

## §8 — No shift vs run 16 (nothing moved)

Run 16 (08:41 UTC): BOTH 4, EXIT_ONLY 15, NO_MATCH 63; matched sums −188.8111 / −190.1671; unmatched zero-realised 18. This run (10:16 UTC): BOTH **4**, EXIT_ONLY **15**, NO_MATCH **63**; matched sums **−188.8111 / −190.1671** (identical to the cent); unmatched zero 18. Missing closes 3 (−31.6607) and carry 32 (+48.8725) are identical; the SUIUSDT close that moved missing → carry between run 14 and run 15 stays in the carry, income-confirmed at exactly +30.5009 (§3 re-proves this directly — absent from both `userTrades` and `allOrders` at this run, present in the income endpoint). The identity is unaffected — it rests on income totals, which are unchanged — and `diffs_over_0.5` is still empty. Worth a note to the reconciler owner: row-level traceability degrades as fills age out, even while the identity holds. No ruling owed on this run's verdict.

## §9 — States

implemented YES / tested YES / merged NO / deployed NO / production-verified NO (paired verification + merge owed; run 18 is TP7's STR-118, sequenced after run 16, run 17 filed by M9 as PR #2335).

— Muse TP7, 2026-11-28
