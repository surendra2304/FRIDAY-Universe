# TASK-STR-101 — Forward-window fills audit run 8 (evidence)

- **Task:** Stratex: forward-window fills audit run 8 — ledger reconciliation + net P&L.
- **Owner:** Muse TP12. **Claim:** hub #2045 comment 7224263179, 2026-11-27 ~22:40 IST, claim-on-finish with TASK-STR-078 (PR #2162 merged 22:15:51 IST). **Board:** CLAIMED / owner muse_tp12 / P1 on live main `69acab99` (board blob `f7589962`, 478 records, read first-hand via git blob API); claim flip LANDED via coordinator board PR #2182 (WATCH235 §G). Acceptance = daemon fill/close ledger read end-to-end and reconciled against venue positions/history, evidence as `docs/collaboration/TASK-STR-101-EVIDENCE.md`.
- **Branch:** `musetp12/task-str-101-forward-window-fills-audit-run-8` from main `1a58bb15` (ref POST verified, HTTP 201, at claim time).
- **Run-9 note:** STR-102 run 9 (Muse 3, PR #2188 open, not yet merged) was claimed and filed BEFORE this run 8 — WATCH235 §C directed M3 to STR-102 while STR-101 was still in flight. Run 9 compares against run 7; this run 8 slots between run 7 (STR-100, PR #2083 merged, RECONCILED) and run 9 (STR-102, PR #2188, RECONCILED). Run 9's evidence doc is the filing of record for its run; this doc is the filing of record for run 8.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `69acab99`) run live on Stratex-Server (server 4) from a fresh extract `/tmp/musetp12-str101` at `69acab99` (the live checkout is on main `3db55adf`, which predates the STR-090 merge — the extract, not the live checkout, supplies the fixed code; the live checkout and the daemon were not touched). `git archive 69acab99 Stratex | tar -x` used directly (M3's run-9 note: `git worktree add` dropped repeatedly on bridge transport). Reconciler sha256 `bc90e854c17923c0370aa43236251dc6060f975adce88ccda5bbbe165fb59b1c` — verified identical at `93628618` (run 6), `8de8e3ed` (run 7), `a85c9d13` (run 9) and `69acab99` (this run); test file sha256 `956032e776711fec7b1fb47796dcee8ea7540a479da2fa4b4c042c49a948acbc` — identical at the same four mains. Daemon venv python. Run at 2026-11-27T19:19:00Z / 2026-11-28 00:49 IST, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-28.json` on Stratex-Server and snapshotted to `/tmp/musetp12-str101-report.json` on Stratex-Server (md5 `d7c2e98ffa8c7761aeb2b2826363d926`, live file and snapshot identical — the 01:00 UTC timer will overwrite the live file afterwards with the stale-checkout report, as run 9 predicted; the snapshot is the filing of record for this run). The pre-run report is preserved at `/tmp/musetp12-str101-before.json` (md5 `b1a6b8d22168e6253876e64329c25f3a`, identical to run 9's snapshot — this run overwrote run 9's live `daily_2026-11-28.json`; run 9's figures are preserved in its snapshot and in PR #2188). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/musetp12-str101/Stratex:/tmp/musetp12-str101` so the fixed code runs. Exact command in §7.
- **Host note (carried from runs 6/7/9):** the Oracle Server 1 copy of the Stratex state dir is a **frozen pre-migration copy** — do not re-run against the S1 copy; the live state is on Stratex-Server, as STR-091/STR-094/STR-095/STR-096/STR-100/STR-102 did. This run used Stratex-Server (server 4).

## Verdict

**DISCREPANCY — explained, quantified, ledger intact.** The forward-window identity residual is **+18.3375 USDT** against a tolerance of 10.46 USDT, so the reconciler reports `DISCREPANCY` and raises `fill_ledger_reconciliation_discrepancy`. The cause is identified exactly: the ETHUSDT missing close (order `16876077891`, BUY 0.148, realised **+19.9399**, 2026-11-20T00:34:38Z) **aged out of the venue's `userTrades`/`allOrders` window between run 9 (18:59 UTC) and this run (19:19 UTC)** — it is no longer returned by either endpoint, so it left the missing-closes set (5 → 4, +18.7801 → −1.1598), while the venue income history still counts it (REALIZED_PNL −67.4283, unchanged). Residual run 9 → run 8: −1.6024 → +18.3375, Δ = **+19.9399 exactly**. No matched row disagrees with the venue by more than $0.50 (`diffs_over_0.5: []`). The ledger is byte-identical to run 9's pre-run state (md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, 84 rows, last close 2026-11-27T02:26:41Z) — nothing was lost, nothing was written, no close was missed by the daemon. This is a venue-retention artifact in the reconciler's identity check, not a ledger error — but it is a real discrepancy in the reconciler's output and is filed as DISCREPANCY, not RECONCILED. **Ruling owed (coordinator):** how the G-recon identity should treat aged-out missing closes — carry them forward from prior reports, or accept the residual step when a close crosses the retention edge (see §3).

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-27T02:26:41Z last close)

| Figure | Run 8 (this run, 19:19 UTC) | Run 9 (18:59 UTC) | Run 7 (05:49 UTC) |
|---|---|---|---|
| Ledger closes, all time | 84 rows | 84 rows | 84 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 | +107.089 |
| Ledger closes in forward window | 75 rows | 75 rows | 75 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.923 + OANDA USDJPY −0.0478) | −87.9709 | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 | 3.3171 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 40 rows −147.9099 | same | same |
| Venue closes in window | **79** (75 ledger + 4 missing) | 80 (75 ledger + 5 missing) | 80 (75 ledger + 5 missing) |
| Venue window true net P&L | **−89.1307** | −69.1908 | −69.1908 |
| Venue account at run time | wallet 10,438.26, margin 10,462.27, unrealised +24.02, available 9,433.18 USDT (USDT 4,924.28 + USDC 5,000 + BTC 0.01) | wallet 10,437.29, margin 10,466.23, unrealised +28.93, available 9,439.78 | wallet 10,452.14, margin 10,460.95, unrealised +8.81, available 9,415.82 |
| Open positions at run time | 30, unrealised +24.0214 | 30, unrealised +28.9223 | 30, unrealised +8.8236 |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−67.4283**, COMMISSION **−9.8166**, FUNDING_FEE **+0.7282**, TRANSFER +15,000.03 | same totals | REALISED −67.4283, COMMISSION −9.8166, FUNDING +0.6514, TRANSFER +15,000.03 |
| Income rows fetched | **1,213** (851 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) | not probed independently | 1,154 (792 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` | `[]` |

Change run 9 → run 8: no new ledger close (ledger md5 identical, 84 rows, last close unchanged 2026-11-27T02:26:41Z). The only movement is the ETHUSDT close leaving the venue-visible set (§3): venue closes in window 80 → 79, venue true net −69.1908 → −89.1307 (Δ −19.9399). Everything else is mark-price drift on the 30 open positions (unrealised +28.92 → +24.02; wallet +0.97 — see the wallet note in §6, it does not tie to the income deltas and is not part of the reconciled identity). Funding rows grew 792 → 851 since run 7 while the funding total moved only +0.6514 → +0.7282 (run 7 → run 9) and 0.0000 since run 9 — funding is accruing, net ~0 over the 20-minute run 9 → run 8 interval.

## §2 — Net P&L by symbol (window, 75 closes — re-derived independently this run)

Re-derived from the live ledger (`fill_ledger.jsonl`, exit_time ≥ forward-window start) in a separate process from the reconciler run; matches the report exactly, and matches run 7 §2 to the cent — the window rows are unchanged since run 7:

| Symbol | Net P&L | Symbol | Net P&L | Symbol | Net P&L |
|---|---|---|---|---|---|
| AAVEUSDT | 0.0000 | DOGEUSDT | −5.2915 | OPUSDT | 0.0000 |
| ADAUSDT | −31.9944 | DOTUSDT | +10.9385 | SANDUSDT | +10.1942 |
| ALGOUSDT | −2.1276 | ETCUSDT | −10.1619 | SOLUSDT | −31.5362 |
| APTUSDT | 0.0000 | ETHUSDT | −20.3867 | SUIUSDT | −14.0632 |
| ARBUSDT | 0.0000 | FILUSDT | 0.0000 | TRXUSDT | 0.0000 |
| ATOMUSDT | −0.7904 | HBARUSDT | +10.0176 | UNIUSDT | +10.1544 |
| AVAXUSDT | −20.6058 | INJUSDT | 0.0000 | USDJPY | −0.0478 |
| BCHUSDT | 0.0000 | LINKUSDT | +1.8418 | VETUSDT | +20.2573 |
| BNBUSDT | 0.0000 | LTCUSDT | 0.0000 | XLMUSDT | 0.0000 |
| BTCUSDT | +8.0792 | MANAUSDT | 0.0000 | XRPUSDT | −21.5439 |
| NEARUSDT | −0.9046 | | | **Total** | **−87.9709** |

The 75 window rows are the same rows as run 7 §5 (ledger unchanged since run 7 — same md5 as run 9's pre-run, same per-symbol nets, same all-time cross-check §4 of run 7); they are not reprinted here. Outside-window rows: 9, all 2026-11-14, unchanged (run 7 §4).

## §3 — The ETHUSDT close aged out: proof (independent probe, separate process)

- **Missing closes (G1) — 4, realised −1.1598** (run 9: 5, +18.7801). The four remaining are unchanged from run 9:
  - SUIUSDT, order 1100728824, BUY 304.4, **+30.5009**, 1 fill, 2026-11-20T02:56:08Z
  - VETUSDT, order 458616420, BUY 42,328, **−10.9206**, 1 fill, 2026-11-21T13:28:08Z
  - SANDUSDT, order 340506462, BUY 5,219, **−11.3252**, 1 fill, 2026-11-22T12:16:35Z
  - LTCUSDT, order 1615011544, BUY 5.706, **−9.4149**, 1 fill, 2026-11-27T02:26:24Z
  - **GONE — ETHUSDT, order 16876077891, BUY 0.148, +19.9399, 2 fills, 2026-11-20T00:34:38Z** — present in the missing set in runs 6/7/9, absent in run 8.
- **Direct venue probe** (`/tmp/musetp12-str101-probe.py`, same `DemoFuturesReader`, same env file, separate process from the reconciler run): ETHUSDT `userTrades` now returns **n=3** trades, earliest `1795204968339` ms (2026-11-20T07:22:48Z) — order 16876077891 present=0; ETHUSDT `allOrders` returns **n=3** orders, order 16876077891 present=0. The close's fills (00:34:38Z) are no longer returned by either endpoint. **Control:** SUIUSDT order 1100728824 (02:56:08Z, older than the ETH close by 2.4h but still returned) IS present in `userTrades` (n=8) and `allOrders` (n=4, FILLED) — the endpoints work; only the ETH close crossed the retention edge. The edge sits between 00:34 and 02:56 UTC on 2026-11-20.
- **Why the identity breaks:** the reconciler's missing-close set is built from `userTrades`/`allOrders`, while venue realised comes from `income` — and `income` retains longer. Independent income probe this run: **1,213 rows** (851 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER), totals COMMISSION −9.8166, FUNDING_FEE +0.7282, REALIZED_PNL −67.4283, TRANSFER +15,000.03 — exactly matching the report's `income_since_reset`. The ETH realised (+19.9399) is still inside REALIZED_PNL −67.4283, but the ETH close is no longer visible to the missing-close detector, so the identity has nowhere to put it.
- **Matching (82 Binance rows):** BOTH 13, EXIT_ONLY 15, NO_MATCH 54 — identical to run 9. Matched exit realised −30.7439 vs matched ledger net −32.7818 — the difference is the matched rows' fees (2.0379), so the matched set ties out exactly. **Diffs over $0.50: none.** Unmatched zero-realised fills: 20 orders (entry legs of the open positions + breakeven entries — visible, never silently dropped; run 9: 20).

## §4 — Window identity (re-derived from the report)

Ledger window net (Binance) −87.9231 + missing closes −1.1598 + window fees 3.3171 = expected venue realised **−85.7658**; venue realised **−67.4283**; residual **+18.3375**, tolerance 10.46, status **DISCREPANCY**. Check: residual run 9 (−1.6024) + ETH close (+19.9399) = +18.3375 ✓. Venue true net −89.1307 = ledger window net −87.9709 + missing −1.1598 ✓. The aged-out ETH close is the entire residual: add it back and the identity closes at −1.6024, the unchanged-since-run-2 residual (the aged-out Nov-19 reset-wipe micro-closes, −1.6023).

## §5 — Funding cross-check: STR-090 pagination fix holds live

Independent direct `income()` call (separate process, same reader, same env file): **1,213 income rows** since the reset floor — 851 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER — totals **FUNDING_FEE +0.7282, COMMISSION −9.8166, REALIZED_PNL −67.4283, TRANSFER +15,000.03**, exactly matching the report's `income_since_reset`. The 1,000-row venue cap is paginated past (1,213 > 1,000). Funding moved +0.6514 → +0.7282 since run 7 (Δ +0.0768) and 0.0000 since run 9; rows grew 792 → 851 since run 7. Funding is unfrozen and accruing.

## §6 — Open positions at run time (30, unrealised +24.0214) + wallet note

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 94.98609042 | +7.4470 |
| ADAUSDT | +301.0 | 0.1494 | 0.14979264 | +0.1182 |
| ALGOUSDT | −2,293.4 | 0.08004 | 0.08169 | −3.7841 |
| APTUSDT | −116.9 | 0.4356 | 0.38827417 | +5.5324 |
| ARBUSDT | −410.7 | 0.1269168736304 | 0.11513277 | +4.8397 |
| ATOMUSDT | −151.7 | 1.186 | 1.22919143 | −6.5521 |
| AVAXUSDT | −3.0 | 7.015 | 6.653 | +1.0860 |
| BCHUSDT | −0.388 | 208.3815979381 | 206.93561506 | +0.5610 |
| BNBUSDT | −0.08 | 590.59 | 553.76662649 | +2.9459 |
| BTCUSDT | +0.0025 | 59,889.32 | 59,907.50424901 | +0.0455 |
| DOGEUSDT | −1,453.0 | 0.05505 | 0.05798 | −4.2573 |
| DOTUSDT | −102.7 | 0.6728 | 0.6689 | +0.4005 |
| ETCUSDT | −14.63 | 5.659 | 5.908 | −3.6429 |
| ETHUSDT | +0.111 | 1,681.3 | 1,672.39 | −0.9890 |
| FILUSDT | −81.9 | 0.5788 | 0.53667722 | +3.4499 |
| HBARUSDT | −1,433.0 | 0.05152 | 0.05378 | −3.2386 |
| INJUSDT | −19.0 | 6.657 | 6.38 | +5.2630 |
| LINKUSDT | −8.79 | 8.629 | 9.40852359 | −6.8520 |
| LTCUSDT | +5.72 | 44.37 | 43.9190107 | −2.5797 |
| MANAUSDT | −1,342.0 | 0.060599538003 | 0.05759822 | +4.0278 |
| NEARUSDT | −14.0 | 2.901 | 3.052 | −2.1140 |
| OPUSDT | −661.6 | 0.0768 | 0.0712 | +3.7050 |
| SANDUSDT | −1,822.0 | 0.03348 | 0.03454 | −1.9313 |
| SOLUSDT | −2.1 | 69.02 | 72.1 | −6.4680 |
| SUIUSDT | −96.1 | 0.6446 | 0.67519192 | −2.9399 |
| TRXUSDT | −750.0 | 0.30999 | 0.30082 | +6.8775 |
| UNIUSDT | −9.0 | 4.707444444444 | 4.828 | −1.0850 |
| VETUSDT | +40,580.0 | 0.004618 | 0.0049682 | +14.2111 |
| XLMUSDT | −1,792.0 | 0.13436 | 0.12735678 | +12.5498 |
| XRPUSDT | −93.7 | 0.925 | 0.9528 | −2.6049 |

All 3× leverage. Position set identical to run 9 (same 30 symbols); only marks drifted. Venue account unrealised +24.0154 (account-level read) vs positions sum +24.0214 (0.006 apart — different read moments in the same run).

**Wallet note (open observation, carried from run 7 §10):** wallet 10,437.29 (run 9, 18:59 UTC) → 10,438.26 (this run, 19:19 UTC): movement +0.97 while the income totals are IDENTICAL over the same interval. The wallet balance moves independently of the income ledger on this demo account — it is a venue-side snapshot, not part of the reconciled identity. Flagged here for the paired verifier, not hidden.

## §7 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge); `Stratex.service` **active**, `Stratex-Daemon.service` **active** (verified first-hand this run); `friday-stratex-reconciliation.timer` next run 01:00 UTC will overwrite `daily_2026-11-28.json` — all figures are preserved here and in the snapshot. The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- Extract: `git fetch origin main` + `git archive 69acab99 Stratex | tar -x -C /tmp/musetp12-str101` on Stratex-Server (origin/main `a85c9d13..69acab99` on fetch). Reconciler + test sha256 verified above.
- Run (backgrounded, log `/tmp/musetp12-str101-run.log` on Stratex-Server, PID 78926):
  `cd /tmp/musetp12-str101/Stratex && PYTHONPATH=/tmp/musetp12-str101/Stratex:/tmp/musetp12-str101 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-28`
  (the timer service's own invocation, with the extract paths substituted so the merged fixed code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-28: ledger 84 rows (window 75, net -87.97), matching {'NO_MATCH': 54, 'EXIT_ONLY': 15, 'BOTH': 13}, missing closes 4 (-1.16), resets 6 (0 new), status DISCREPANCY -> /opt/friday_universe/Stratex/state/reconciliation/daily_2026-11-28.json` + `[ERROR] [measurement_fill_ledger] [MEASUREMENT] ALERT fill_ledger_reconciliation_discrepancy: STR-044 2026-11-28: window identity residual +18.34 exceeds tolerance 10.46`
- Ledger before-state: 84 rows, md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, last row recorded 2026-11-27T02:26:41Z. Report snapshot md5 `d7c2e98ffa8c7761aeb2b2826363d926` (live file and snapshot identical). Ledger md5 re-verified unchanged after the run (19:26 UTC).
- Independent probes (separate processes, same reader/env): `/tmp/musetp12-str101-probe.py` — ledger re-derivation (window 75, net −87.9709; per-symbol nets §2; all-time +107.089; outside rows 9) + income probe (1,213 rows, totals exact) + ETH/SUI fills probe (§3).
- Bridge note: `run_shell` responses intermittently die with `http.client.IncompleteRead` / `RemoteDisconnected` on this run's sibling calls (none this run — all 7 bridge calls this run completed first-try); every figure was re-read after a successful call. No data was faked.
- Tests: `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — **28/28 passed** (1 warning) on Stratex-Server in the exact run-8 extract (pytest, 0.49s, `PYTHONPATH=/tmp/musetp12-str101/Stratex:/tmp/musetp12-str101`); no test file changed in this task. CI re-verification from the work PR's job log follows (STR-091 lesson: the file is collected by `owner-workflows.yml` "Stratex forward-test and self-experiment contracts").

## Five states

- implemented: YES (this evidence doc filed on branch `musetp12/task-str-101-forward-window-fills-audit-run-8`)
- tested: YES (reconciler run live on Stratex-Server + independent funding/income probe + independent ledger re-derivation + independent ETH-ageing probe + 28/28 tests on the exact run-8 code)
- merged: NO (work PR open at filing; paired verification by a different chat owed — never merge own PR)
- deployed: N/A (nothing deployed; proof ran against the existing deploy, daemon untouched)
- production-verified: NO (paired verification by a different chat owed before this counts; the verdict itself is DISCREPANCY, so the verifier confirms the finding, not a clean balance)

— Muse TP12
