# TASK-STR-105 — Forward-window fill-ledger state run 9 (evidence)

- **Task:** Stratex: forward-window fill-ledger state run 9 — fills, closes, net P&L vs venue.
- **Owner:** Muse 12. **Claim:** hub #2045 comment 7231341022, 2026-11-28 ~06:32 IST, per WATCH248 §B (hub 7231232057). **Board:** AVAILABLE / owner muse_12 / P1 on live main `98215372` (board blob `cbc16f50`, 12,421 lines, read first-hand via git blob API). Acceptance = daemon fill/close ledger reconciled end-to-end against venue positions/history, evidence as `docs/collaboration/TASK-STR-105-EVIDENCE.md`.
- **Branch:** `muse12/task-str-105-forward-window-fill-ledger-run-9` from main `98215372` (ref POST verified, HTTP 201, at claim time).
- **Sequence note:** the board titles this run 9, but STR-102 already filed as run 9 (Muse 3, PR #2188) and STR-103 as run 10 (per the STR-104 code comment). This is the next window after STR-101 run 8 and the first run of the STR-104 fixed reconciler; the numbering overlap is flagged for the coordinator, not resolved here.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `98215372`) run live on Stratex-Server (server 4) from a fresh extract `/tmp/muse12-str105` at `98215372` (the live checkout is on main `3db55adf`, which predates the STR-090 merge — the extract, not the live checkout, supplies the fixed code; the live checkout and the daemon were not touched). `git archive 98215372 Stratex | tar -x` used directly (M3's run-9 note: `git worktree add` dropped repeatedly on bridge transport). Reconciler sha256 `c1da1c1399de7ea0e4c04c1832845e16a03e84cb820c254bce4bf85b0b3d08f1` — **changed since run 8** (`bc90e854...`): this is the STR-104 aged-out-carry fix (see §3), the only behaviour change in the diff (verified first-hand: diff vs run 8's version is confined to the carry feature + docstring, no tolerance change). Test file sha256 `fa0831288a732e1708d3e42e9650ae58456839bb4636b810e15b5286e3ebba9a` — also changed (9 new STR-104 tests). Daemon venv python. Run at 2026-11-28T01:02:32Z / 06:32 IST, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-28.json` on Stratex-Server and snapshotted to `/tmp/muse12-str105-report.json` on Stratex-Server (md5 `eb04625eedbe426f8bc73acff9b7c66e`, live file and snapshot identical). The pre-run report is preserved at `/tmp/muse12-str105-before.json` (md5 `ae85aa4278542ee8132ec2ecb2001601`) — see the timer note in §7. State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/muse12-str105/Stratex:/tmp/muse12-str105` so the fixed code runs. Exact command in §7.
- **Host note (carried from runs 6/7/8/9):** the Oracle Server 1 copy of the Stratex state dir is a **frozen pre-migration copy** — do not re-run against the S1 copy; the live state is on Stratex-Server, as STR-091/STR-094/STR-095/STR-096/STR-100/STR-101/STR-102 did. This run used Stratex-Server (server 4).

## Verdict

**RECONCILED.** The forward-window identity residual is **−0.0341 USDT** against a tolerance of 10.47 USDT. The STR-104 fix works as ruled (WATCH242): the 31 aged-out missing closes are carried at their income-endpoint amounts (**+18.3716** — the ETHUSDT close **+19.9399** plus 30 Nov-19 reset-wipe micro-closes totalling **−1.5683**), each income-confirmed, none unconfirmed. Run 8's DISCREPANCY (+18.3375) minus the carry (+18.3716) = −0.0341 ✓ — the residual is now rounding-level. No matched row disagrees with the venue by more than $0.50 (`diffs_over_0.5: []`). The ledger is byte-identical to run 8's state (md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, 84 rows, last close 2026-11-27T02:26:41Z) — nothing was lost, nothing was written, no close was missed by the daemon. The G1 missing-closes set is unchanged (4, −1.1598); the G1-carry set is new by design. **No ruling owed on the identity this run** — the WATCH242 ruling is implemented and verified live. Open observations (timer stale-checkout overwrite, BOTH→EXIT_ONLY shift, run numbering) are filed in §7, not hidden.

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-27T02:26:41Z last close)

| Figure | This run (STR-105, 01:02 UTC) | Run 8 (STR-101, 19:19 UTC) | Run 9 (STR-102, 18:59 UTC) |
|---|---|---|---|
| Ledger closes, all time | 84 rows | 84 rows | 84 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 | +107.089 |
| Ledger closes in forward window | 75 rows | 75 rows | 75 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.923 + OANDA USDJPY −0.0478) | −87.9709 | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 | 3.3171 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 40 rows −147.9099 | same | same |
| Venue closes in window | **79** (75 ledger + 4 missing) | 79 (75 ledger + 4 missing) | 80 (75 ledger + 5 missing) |
| Venue window true net P&L | **−89.1307** | −89.1307 | −69.1908 |
| Venue account at run time | wallet 10,438.35, margin 10,470.98, unrealised +32.62, available 9,442.10 USDT (USDT 4,924.35 + USDC 5,000 + BTC 0.01) | wallet 10,438.26, margin 10,462.27, unrealised +24.02, available 9,433.18 | wallet 10,437.29, margin 10,466.23, unrealised +28.93, available 9,439.78 |
| Open positions at run time | 30, unrealised +32.47 (positions sum) / +32.62 (account) | 30, unrealised +24.02 | 30, unrealised +28.92 |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−67.4283**, COMMISSION **−9.8166**, FUNDING_FEE **+0.806**, TRANSFER +15,000.03 | REALISED_PNL −67.4283, COMMISSION −9.8166, FUNDING_FEE +0.7282, TRANSFER +15,000.03 | same totals as run 8 except FUNDING +0.7282 |
| Income rows fetched | **1,243** (881 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) | 1,213 (851 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) | not probed independently |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` | `[]` |

Change run 8 → this run: no new ledger close (ledger md5 identical, 84 rows, last close unchanged 2026-11-27T02:26:41Z). The only movement is mark-price drift on the 30 open positions (unrealised +24.02 → +32.47; wallet +0.09 — see the wallet note in §6, it does not tie to the income deltas and is not part of the reconciled identity) and funding accrual (rows 851 → 881, total +0.7282 → +0.806). The missing-closes set, the matched sums and the ledger are all unchanged since run 8.

## §2 — Net P&L by symbol (window, 75 closes — re-derived independently this run)

Re-derived from the live ledger (`fill_ledger.jsonl`, exit_time ≥ forward-window start) in a separate process from the reconciler run; matches the report exactly in total (−87.9709). Two per-symbol values differ from run 8 §2 by 0.0001 (ALGOUSDT −2.1275 vs −2.1276; LINKUSDT +1.8419 vs +1.8418) — float summation order in my manual re-derivation; the ledger is byte-identical, so these are rounding, not movement; the column total is unchanged to the cent:

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

The 75 window rows are the same rows as run 7 §5 / run 8 §2 (ledger unchanged since run 7 — same md5 as runs 8/9 pre-run, same per-symbol nets to rounding, same all-time cross-check); they are not reprinted here. Outside-window rows: 9, all 2026-11-14, unchanged.

## §3 — The aged-out carry: proof (independent probe, separate process)

- **Missing closes (G1) — 4, realised −1.1598** (unchanged from run 8): SUIUSDT order 1100728824 BUY 304.4 **+30.5009**; VETUSDT order 458616420 BUY 42,328 **−10.9206**; SANDUSDT order 340506462 BUY 5,219 **−11.3252**; LTCUSDT order 1615011544 BUY 5.706 **−9.4149**.
- **Aged-out carry — 31 orders, realised +18.3716, all income-confirmed, 0 unconfirmed.** The ETHUSDT close (order `16876077891`, BUY 0.148, **+19.9399**, 2 fills, 2026-11-20T00:34:38Z, first/last fill `1795202078059`) plus 30 micro-closes (−0.0055 … −0.136 each, first fills 2026-11-19, totalling −1.5683 — the Nov-19 reset-wipe micro-closes behind the unchanged-since-run-2 base residual). The 30 micro-closes are one per symbol (TRX, MANA, FIL, DOT, ETH, SUI, BCH, INJ, ETC, LTC, ATOM, XRP, LINK, VET, NEAR, AAVE, BTC, SOL, APT, AVAX, UNI, BNB, DOGE, XLM, OP, HBAR, ALGO, ADA, SAND, ARB).
- **Direct venue probe** (`/tmp/muse12-str105-probe.py`, same `DemoFuturesReader`, same env file, separate process from the reconciler run): ETHUSDT `userTrades` now returns **n=2** trades, earliest `1795268189087` ms (2026-11-21T07:36:29Z) — order 16876077891 present=0; ETHUSDT `allOrders` returns **n=2** orders, order 16876077891 present=0. The close's fills (00:34:38Z Nov 20) are no longer returned by either endpoint — it has aged further out since run 8 (then n=3). **Control:** SUIUSDT order 1100728824 IS present in `userTrades` (n=8) and `allOrders` (n=4, FILLED) — the endpoints work; only aged-out fills are gone.
- **Income confirmation (independent, same probe):** ETHUSDT REALIZED_PNL rows within ±5 min of the ETH close's fill times sum to **+19.9399 over 2 rows** — exactly the recorded amount. Spot checks on micro-closes: TRXUSDT order 1173153567, 1 row, **−0.0055**; MANAUSDT order 241723755, 1 row, **−0.0376** — both exactly recorded. The carried amounts are income-endpoint sums, never the residual — the identity stays an independent check.
- **Matching (82 Binance rows):** BOTH 12, EXIT_ONLY 16, NO_MATCH 54 — run 8 was BOTH 13, EXIT_ONLY 15, NO_MATCH 54. One ledger row moved BOTH → EXIT_ONLY: its *entry* fill aged out of the venue fills window between run 8 (19:19 UTC) and this run (01:02 UTC) while its exit still matches — the matched-exit set is unchanged at 28 rows (BOTH + EXIT_ONLY) with identical sums (matched exit realised −30.7439 vs matched ledger net −32.7818; the difference is the matched rows' fees, 2.0379, so the matched set ties out exactly). **Diffs over $0.50: none.** Unmatched zero-realised fills: 20 orders (entry legs of the open positions + breakeven entries — visible, never silently dropped; run 8: 20).

## §4 — Window identity (re-derived from the report)

Ledger window net (Binance) −87.9231 + missing closes −1.1598 + aged-out carry +18.3716 + window fees 3.3171 = expected venue realised **−67.3942**; venue realised **−67.4283**; residual **−0.0341**, tolerance 10.47, status **RECONCILED**. Check: residual run 8 (+18.3375) − carry (+18.3716) = −0.0341 ✓. Venue true net −89.1307 = ledger window net −87.9709 + missing −1.1598 ✓. The STR-104 carry closes run 8's DISCREPANCY exactly as ruled.

## §5 — Funding cross-check: STR-090 pagination fix holds live

Independent direct `income()` call (separate process, same reader, same env file): **1,243 income rows** since the reset floor — 881 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER — totals **FUNDING_FEE +0.8067, COMMISSION −9.8158, REALIZED_PNL −67.4282, TRANSFER +15,000.03**, matching the report's `income_since_reset` to within $0.001 on every total (probe ran ~3 min after the report; the sub-cent deltas are summation rounding, not movement — the identity-critical REALIZED_PNL agrees to 0.0001). The 1,000-row venue cap is paginated past (1,243 > 1,000). Funding moved +0.7282 → +0.806 since run 8 (Δ +0.0778) and rows grew 851 → 881. Funding is unfrozen and accruing.

## §6 — Open positions at run time (30, unrealised +32.4717) + wallet note

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 95.39 | +7.2450 |
| ADAUSDT | +301.0 | 0.1494 | 0.1482 | −0.3612 |
| ALGOUSDT | −2,293.4 | 0.08004 | 0.08088392 | −1.9354 |
| APTUSDT | −116.9 | 0.4356 | 0.3922 | +5.0735 |
| ARBUSDT | −410.7 | 0.1269168736304 | 0.1146 | +5.0585 |
| ATOMUSDT | −151.7 | 1.186 | 1.239 | −8.0401 |
| AVAXUSDT | −3.0 | 7.015 | 6.611 | +1.2120 |
| BCHUSDT | −0.388 | 208.3815979381 | 208.1775992 | +0.0792 |
| BNBUSDT | −0.08 | 590.59 | 555.19100927 | +2.8319 |
| BTCUSDT | +0.0025 | 59,889.32 | 59,913.1 | +0.0595 |
| DOGEUSDT | −1,453.0 | 0.05505 | 0.05779 | −3.9812 |
| DOTUSDT | −102.7 | 0.6728 | 0.6651 | +0.7908 |
| ETCUSDT | −14.63 | 5.659 | 5.903 | −3.5697 |
| ETHUSDT | +0.111 | 1,681.3 | 1,663.29 | −1.9991 |
| FILUSDT | −81.9 | 0.5788 | 0.53082889 | +3.9288 |
| HBARUSDT | −1,433.0 | 0.05152 | 0.05363762 | −3.0345 |
| INJUSDT | −19.0 | 6.657 | 6.333 | +6.1560 |
| LINKUSDT | −8.79 | 8.629 | 9.382 | −6.6189 |
| LTCUSDT | +5.72 | 44.37 | 44.825051 | +2.6029 |
| MANAUSDT | −1,342.0 | 0.060599538003 | 0.05761 | +4.0119 |
| NEARUSDT | −14.0 | 2.901 | 3.014 | −1.5820 |
| OPUSDT | −661.6 | 0.0768 | 0.07096534 | +3.8602 |
| SANDUSDT | −1,822.0 | 0.03348 | 0.03466789 | −2.1643 |
| SOLUSDT | −2.1 | 69.02 | 71.73 | −5.6910 |
| SUIUSDT | −96.1 | 0.6446 | 0.6723 | −2.6620 |
| TRXUSDT | −750.0 | 0.30999 | 0.30032 | +7.2525 |
| UNIUSDT | −9.0 | 4.707444444444 | 4.857 | −1.3460 |
| VETUSDT | +40,580.0 | 0.004618 | 0.004971 | +14.3247 |
| XLMUSDT | −1,792.0 | 0.13436 | 0.12694171 | +13.2936 |
| XRPUSDT | −93.7 | 0.925 | 0.9498 | −2.3238 |

All 3× leverage. Position set identical to run 8 (same 30 symbols); only marks drifted. Venue account unrealised +32.6210 (account-level read) vs positions sum +32.4717 (0.15 apart — different read moments in the same run).

**Wallet note (open observation, carried from run 7 §10):** wallet 10,438.26 (run 8, 19:19 UTC) → 10,438.35 (this run, 01:02 UTC): movement +0.09 while the income totals are IDENTICAL over the same interval. The wallet balance moves independently of the income ledger on this demo account — it is a venue-side snapshot, not part of the reconciled identity. Flagged here for the paired verifier, not hidden.

## §7 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge); `Stratex.service` **active**, `Stratex-Daemon.service` **active** (verified first-hand this run). The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- **Timer note (recurring):** the 01:00 UTC `friday-stratex-reconciliation.timer` run fired at 01:00:15 UTC — two minutes before this run — and overwrote `daily_2026-11-28.json` with the **stale-checkout** report: status DISCREPANCY, residual **+38.5348**, venue realised **−47.231**. That figure is consistent with the stale checkout's unpaginated income (1,000-row cap vs 1,243 rows live — the oldest ~20.20 of REALIZED_PNL dropped). The pre-run snapshot `/tmp/muse12-str105-before.json` (md5 `ae85aa4278542ee8132ec2ecb2001601`) preserves the timer's report; this run's report (md5 `eb04625eedbe426f8bc73acff9b7c66e`) overwrote it at 01:02:32 UTC and is snapshotted at `/tmp/muse12-str105-report.json`. The timer's stale report is not the filing of record — but the timer overwriting the live file daily with a wrong DISCREPANCY is worth a coordinator ruling (point the timer at the fixed code, or stop it writing the live file).
- Extract: `git fetch origin main` + `git archive 98215372 Stratex | tar -x -C /tmp/muse12-str105` on Stratex-Server (origin/main `9c943aea..98215372` on fetch). Reconciler + test sha256 verified above; diff vs run 8's reconciler reviewed first-hand (STR-104 carry only).
- Run (backgrounded, log `/tmp/muse12-str105-run.log` on Stratex-Server, PID 86387):
  `cd /tmp/muse12-str105/Stratex && PYTHONPATH=/tmp/muse12-str105/Stratex:/tmp/muse12-str105 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-28`
  (the timer service's own invocation, with the extract paths substituted so the merged fixed code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-28: ledger 84 rows (window 75, net -87.97), matching {'NO_MATCH': 54, 'EXIT_ONLY': 16, 'BOTH': 12}, missing closes 4 (-1.16), aged-out carry 31 (+18.37), resets 6 (0 new), status RECONCILED -> /opt/friday_universe/Stratex/state/reconciliation/daily_2026-11-28.json` — no `[ERROR]` alert line (no discrepancy alert fired).
- Ledger before-state: 84 rows, md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, last row recorded 2026-11-27T02:26:41Z. Ledger md5 re-verified unchanged after the run.
- Independent probes (separate processes, same reader/env): `/tmp/muse12-str105-probe.py` — ledger re-derivation (window 75, net −87.9709; per-symbol nets §2; all-time +107.089; outside rows 9) + income probe (1,243 rows, totals to $0.001) + ETH/SUI fills probe (§3) + carry income confirmations (§3).
- Bridge note: all bridge calls this run completed first-try; every figure was re-read after a successful call. No data was faked.
- Tests: `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — **37/37 passed** (1 warning) on Stratex-Server in the exact run-9 extract (pytest, 6.32s, `PYTHONPATH=/tmp/muse12-str105/Stratex:/tmp/muse12-str105`); run 8 had 28 tests — the 9 new tests cover the STR-104 carry. No test file changed in this task. CI re-verification from the work PR's job log follows (STR-091 lesson: the file is collected by `owner-workflows.yml` "Stratex forward-test and self-experiment contracts").

## Five states

- implemented: YES (this evidence doc filed on branch `muse12/task-str-105-forward-window-fill-ledger-run-9`)
- tested: YES (reconciler run live on Stratex-Server + independent funding/income probe + independent ledger re-derivation + independent ETH-ageing/carry probe + 37/37 tests on the exact run-9 code)
- merged: NO (work PR open at filing; paired verification by a different chat owed — never merge own PR)
- deployed: N/A (nothing deployed; proof ran against the existing deploy, daemon untouched)
- production-verified: NO (paired verification by a different chat owed before this counts)

— Muse 12
