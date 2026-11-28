# TASK-STR-108 — Forward-window fill-ledger state run 10 (evidence)

- **Task:** Stratex: forward-window fill-ledger state run 10 — fills, closes, net P&L vs venue.
- **Owner:** Muse TP13. **Claim:** hub #2045 comment 7232386031, 2026-11-28 ~07:58 IST, pool pull via the work-request task (top AVAILABLE per pool priority, Stratex first). **Board:** AVAILABLE / owner null / P1 on live main `b9e3cf77` (board blob `b1657b5d`, 12,518 lines, read first-hand via git blob API). Acceptance = daemon fill/close ledger reconciled end-to-end against venue positions/history, evidence as `docs/collaboration/TASK-STR-108-EVIDENCE.md`.
- **Branch:** `musetp13/task-str-108-forward-window-fill-ledger-run10` from main `b9e3cf77` (ref POST verified, HTTP 201, at claim time).
- **Sequence note:** the board titles this run 10, but STR-103 already filed as run 10 (per the STR-104 code comment) and STR-102 as run 9. This is the next window after STR-105 run 9 (Muse 12, PR #2238 MERGED). The numbering overlap is flagged for the coordinator, not resolved here.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `b9e3cf77`) run live on Stratex-Server (server 4) from a fresh extract `/tmp/musetp13-str108` at `b9e3cf77` (the live checkout is on main `3db55adf`, which predates the STR-090 merge — the extract, not the live checkout, supplies the fixed code; the live checkout and the daemon were not touched). `git archive b9e3cf77 Stratex | tar -x` used directly (M3's run-9 note: `git worktree add` dropped repeatedly on bridge transport). Reconciler sha256 `c1da1c1399de7ea0e4c04c1832845e16a03e84cb820c254bce4bf85b0b3d08f1` — **byte-identical to run 9** (diff vs the run-9 extract: no output — zero changes). Test file sha256 `fa0831288a732e1708d3e42e9650ae58456839bb4636b810e15b5286e3ebba9a` — also identical to run 9. Daemon venv python. Run at 2026-11-28T02:30:56Z / 08:00 IST, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-28.json` on Stratex-Server and snapshotted to `/tmp/musetp13-str108-report.json` on Stratex-Server (md5 `b38a331848147cecc1e0e6b458c9700a`, live file and snapshot identical). The pre-run report is preserved at `/tmp/musetp13-str108-before.json` (md5 `eb04625eedbe426f8bc73acff9b7c66e` — run 9's report). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/musetp13-str108/Stratex:/tmp/musetp13-str108` so the fixed code runs. Exact command in §7.
- **Host note (carried from runs 6/7/8/9):** the Oracle Server 1 copy of the Stratex state dir is a **frozen pre-migration copy** — do not re-run against the S1 copy; the live state is on Stratex-Server, as STR-091/STR-094/STR-095/STR-096/STR-100/STR-101/STR-102/STR-105 did. This run used Stratex-Server (server 4).

## Verdict

**RECONCILED.** The forward-window identity residual is **−0.0341 USDT** against a tolerance of 10.48 USDT — identical to run 9's residual to the cent. The ledger is byte-identical to run 9's state (md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, 84 rows, last close 2026-11-27T02:26:41Z) — nothing was lost, nothing was written, no close was missed by the daemon. The G1 missing-closes set is unchanged (4, −1.1598); the aged-out carry is unchanged (31, +18.3716), all income-confirmed. **Root cause of the standing −0.0341 residual found this run (§4):** the INJUSDT micro-close's second fill income row (−0.034) is not in the carry — the carry understates by exactly the residual. No ruling owed on the identity; the carry gap is filed as an observation for the reconciler owner, not a discrepancy. No matched row disagrees with the venue by more than $0.50 (`diffs_over_0.5: []`). Open observations (timer stale-checkout overwrite, run numbering, wallet note) are filed in §7, not hidden.

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-27T02:26:41Z last close)

| Figure | This run (STR-108, 02:30 UTC) | Run 9 (STR-105, 01:02 UTC) |
|---|---|---|
| Ledger closes, all time | 84 rows | 84 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 |
| Ledger closes in forward window | 75 rows | 75 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.9231 + OANDA USDJPY −0.0478) | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 40 rows −147.9099 | same |
| Venue closes in window | **79** (75 ledger + 4 missing) | 79 (75 ledger + 4 missing) |
| Venue closes incl. aged-out carry | 110 (75 + 4 + 31) | 110 |
| Venue window true net P&L (incl. carry) | **−70.7591** | −70.7591 |
| Venue window true net P&L (ex-carry) | −89.1307 | −89.1307 |
| Venue account at run time | wallet 10,439.08, margin 10,477.67, unrealised +38.59, available 9,449.06 USDT (USDT 4,924.35 + USDC 5,000 + BTC 0.01) | wallet 10,438.35, margin 10,470.98, unrealised +32.62, available 9,442.10 |
| Open positions at run time | 30, unrealised +38.58 (positions sum) / +38.59 (account) | 30, unrealised +32.47 (positions sum) / +32.62 (account) |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−67.4283**, COMMISSION **−9.8166**, FUNDING_FEE **+0.806**, TRANSFER +15,000.03 | REALISED_PNL −67.4283, COMMISSION −9.8166, FUNDING_FEE +0.806, TRANSFER +15,000.03 |
| Income rows fetched | **1,243** (881 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) | 1,243 (881 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` |

Change run 9 → this run: no new ledger close (ledger md5 identical, 84 rows, last close unchanged 2026-11-27T02:26:41Z). The only movement is mark-price drift on the 30 open positions (unrealised +32.47 → +38.58; wallet +0.73 — see the wallet note in §6, it does not tie to the income deltas and is not part of the reconciled identity) and no funding movement (rows 881, total +0.806 — unchanged since run 9; funding accrues every 8h and none landed in the ~1.5h between runs). The missing-closes set, the carry set, the matched sums and the ledger are all unchanged since run 9.

## §2 — Net P&L by symbol (window, 75 closes — re-derived independently this run)

Re-derived from the live ledger (`fill_ledger.jsonl`, exit_time ≥ forward-window start) in a separate process from the reconciler run; matches the report exactly in total (−87.9709). Two per-symbol values differ from run 9 §2 by 0.0001 (ALGOUSDT −2.1276 vs −2.1275; LINKUSDT +1.8418 vs +1.8419) — float summation order in my manual re-derivation; the ledger is byte-identical, so these are rounding, not movement; the column total is unchanged to the cent:

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

The 75 window rows are the same rows as run 7 §5 / run 8 §2 / run 9 §2 (ledger unchanged since run 7 — same md5 as runs 8/9 pre-run, same per-symbol nets to rounding, same all-time cross-check); they are not reprinted here. Outside-window rows: 9, all 2026-11-14, unchanged.

## §3 — The aged-out carry: proof (independent probe, separate process)

- **Missing closes (G1) — 4, realised −1.1598** (unchanged from run 9): SUIUSDT order 1100728824 BUY 304.4 **+30.5009**; VETUSDT order 458616420 BUY 42,328 **−10.9206**; SANDUSDT order 340506462 BUY 5,219 **−11.3252**; LTCUSDT order 1615011544 BUY 5.706 **−9.4149**.
- **Aged-out carry — 31 orders, realised +18.3716, all income-confirmed, 0 unconfirmed.** The ETHUSDT close (order `16876077891`, BUY 0.148, **+19.9399**, 2 fills, 2026-11-20T00:34:38Z, first/last fill `1795202078059`) plus 30 micro-closes (−0.0055 … −0.136 each, first fills 2026-11-19, totalling −1.5683 — the Nov-19 reset-wipe micro-closes behind the unchanged-since-run-2 base residual). The 30 micro-closes are one per symbol (TRX, MANA, FIL, DOT, ETH, SUI, BCH, INJ, ETC, LTC, ATOM, XRP, LINK, VET, NEAR, AAVE, BTC, SOL, APT, AVAX, UNI, BNB, DOGE, XLM, OP, HBAR, ALGO, ADA, SAND, ARB).
- **Direct venue probe** (`/tmp/musetp13-str108-probe.py`, same `DemoFuturesReader`, same env file, separate process from the reconciler run): ETHUSDT `userTrades` returns **n=2** trades, earliest `1795268189087` ms (2026-11-21T07:36:29Z) — order 16876077891 present=0; ETHUSDT `allOrders` returns **n=2** orders, order 16876077891 present=0. Identical to run 9 (n=2, same earliest) — the close has aged no further since run 9. **Control:** SUIUSDT order 1100728824 IS present in `userTrades` (n=8) and `allOrders` (n=4, FILLED) — the endpoints work; only aged-out fills are gone.
- **Income confirmation (independent, same probe):** ETHUSDT REALIZED_PNL rows within ±5 min of the ETH close's fill times sum to **+19.9399 over 2 rows** — exactly the recorded amount. Spot checks on micro-closes: TRXUSDT order 1173153567, 1 row, **−0.0055**; MANAUSDT order 241723755, 1 row, **−0.0376** — both exactly recorded. The carried amounts are income-endpoint sums, never the residual — the identity stays an independent check.
- **Matching (82 Binance rows):** BOTH 12, EXIT_ONLY 16, NO_MATCH 54 — identical to run 9. No ledger row moved between classes since run 9. The matched-exit set is unchanged at 28 rows (BOTH + EXIT_ONLY) with identical sums (matched exit realised −30.7439 vs matched ledger net −32.7818; the difference is the matched rows' fees, 2.0379, so the matched set ties out exactly). **Diffs over $0.50: none.** Unmatched zero-realised fills: 20 orders (entry legs of the open positions + breakeven entries — visible, never silently dropped; run 9: 20).

## §4 — Window identity (re-derived from the report)

Ledger window net (Binance) −87.9231 + missing closes −1.1598 + aged-out carry +18.3716 + window fees 3.3171 = expected venue realised **−67.3942**; venue realised **−67.4283**; residual **−0.0341**, tolerance 10.48, status **RECONCILED**. Check: residual run 9 (−0.0341) = residual this run (−0.0341) ✓ — the ledger, the missing set and the carry are all unchanged, so the identity reproduces exactly. Venue true net −70.7591 = ledger window net −87.9709 + missing −1.1598 + carry +18.3716 ✓.

**Root cause of the standing −0.0341 residual (new this run):** the INJUSDT micro-close, order `331708071`, has **2 fills** at the same millisecond (`1795075002903`), recorded realised **−0.17**, but the carry holds realised **−0.136** from **1 income row**. My independent probe finds **2 INJUSDT REALIZED_PNL rows** within ±5 min of the fill time summing to **−0.17** — exactly the recorded amount. The second fill's income row (−0.034) is not in the carry, so the carry understates by −0.034 and the residual is −0.0341 (0.0001 is rounding). The only other multi-fill carry order is the ETHUSDT close (2 fills, 2 income rows matched, +19.9399 exact), so the reconciler does match both rows when it finds them — the INJ second row is a matching miss, not a design limit. The run-9 report's INJ entry is byte-identical (recorded −0.17, realised −0.136, 1 income row), so this is standing, not new. Caveat: Binance income rows carry no order id, so the second INJ row is attributed by symbol + time window, not by order id — the attribution is strong (both rows fall in the same ±5 min window as the order's fills, and the sum is exact) but not order-id-proven. Filed as an observation for the reconciler owner: widen the carry's income match so a multi-fill order's rows are all counted. No ruling owed — the residual is 0.3% of tolerance and now explained to the cent.

## §5 — Funding cross-check: STR-090 pagination fix holds live

Independent direct `income()` call (separate process, same reader, same env file): **1,243 income rows** since the reset floor — 881 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER — totals **FUNDING_FEE +0.8067, COMMISSION −9.8158, REALIZED_PNL −67.4282, TRANSFER +15,000.03**, matching the report's `income_since_reset` to within $0.001 on every total (probe ran ~3 min after the report; the sub-cent deltas are summation rounding, not movement — the identity-critical REALIZED_PNL agrees to 0.0001). The 1,000-row venue cap is paginated past (1,243 > 1,000). Funding is unchanged since run 9 (881 rows, +0.806) — no accrual landed between the two runs.

## §6 — Open positions at run time (30, unrealised +38.5838) + wallet note

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 94.77 | +7.5550 |
| ADAUSDT | +301.0 | 0.1494 | 0.1483 | −0.3311 |
| ALGOUSDT | −2,293.4 | 0.08004 | 0.08030993 | −0.6191 |
| APTUSDT | −116.9 | 0.4356 | 0.38850328 | +5.5056 |
| ARBUSDT | −410.7 | 0.1269168736304 | 0.1141 | +5.2639 |
| ATOMUSDT | −151.7 | 1.186 | 1.23721429 | −7.7692 |
| AVAXUSDT | −3.0 | 7.015 | 6.62009206 | +1.1847 |
| BCHUSDT | −0.388 | 208.3815979381 | 209.26981059 | −0.3446 |
| BNBUSDT | −0.08 | 590.59 | 556.11358948 | +2.7581 |
| BTCUSDT | +0.0025 | 59,889.32 | 60,107.0 | +0.5442 |
| DOGEUSDT | −1,453.0 | 0.05505 | 0.05785132 | −4.0703 |
| DOTUSDT | −102.7 | 0.6728 | 0.6644 | +0.8627 |
| ETCUSDT | −14.63 | 5.659 | 5.911 | −3.6868 |
| ETHUSDT | +0.111 | 1,681.3 | 1,667.29511628 | −1.5545 |
| FILUSDT | −81.9 | 0.5788 | 0.53011135 | +3.9876 |
| HBARUSDT | −1,433.0 | 0.05152 | 0.05354 | −2.8947 |
| INJUSDT | −19.0 | 6.657 | 6.281 | +7.1440 |
| LINKUSDT | −8.79 | 8.629 | 9.32161418 | −6.0881 |
| LTCUSDT | +5.72 | 44.37 | 44.89319809 | +2.9927 |
| MANAUSDT | −1,342.0 | 0.060599538003 | 0.05743119 | +4.2519 |
| NEARUSDT | −14.0 | 2.901 | 3.04893941 | −2.0712 |
| OPUSDT | −661.6 | 0.0768 | 0.07049024 | +4.1745 |
| SANDUSDT | −1,822.0 | 0.03348 | 0.03479419 | −2.3945 |
| SOLUSDT | −2.1 | 69.02 | 71.91088967 | −6.0709 |
| SUIUSDT | −96.1 | 0.6446 | 0.6746 | −2.8830 |
| TRXUSDT | −750.0 | 0.30999 | 0.30053103 | +7.0942 |
| UNIUSDT | −9.0 | 4.707444444444 | 4.809 | −0.9140 |
| VETUSDT | +40,580.0 | 0.004618 | 0.00500381 | +15.6562 |
| XLMUSDT | −1,792.0 | 0.13436 | 0.12666809 | +13.7839 |
| XRPUSDT | −93.7 | 0.925 | 0.95150634 | −2.4836 |

All 3× leverage. Position set identical to run 9 (same 30 symbols); only marks drifted. Venue account unrealised +38.5882 (account-level read) vs positions sum +38.5838 (0.0044 apart — different read moments in the same run).

**Wallet note (open observation, carried from run 7 §10):** wallet 10,438.35 (run 9, 01:02 UTC) → 10,439.08 (this run, 02:30 UTC): movement +0.73 while the income totals are IDENTICAL over the same interval. The wallet balance moves independently of the income ledger on this demo account — it is a venue-side snapshot, not part of the reconciled identity. Flagged here for the paired verifier, not hidden.

## §7 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge); `Stratex.service` **active**, `Stratex-Daemon.service` **active** (verified first-hand this run). The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- **Timer note (recurring):** the 01:00 UTC `friday-stratex-reconciliation.timer` run fired at 01:00:15 UTC — before this run — and run 9's filing at 01:02:32 UTC overwrote its stale-checkout report. The live file at this run's start was still run 9's report (md5 `eb04625e`), preserved as the before-snapshot; this run's report (md5 `b38a3318…`) overwrote it at 02:30:56 UTC and is snapshotted at `/tmp/musetp13-str108-report.json`. The timer overwriting the live file daily with a wrong DISCREPANCY (stale checkout, unpaginated income) is worth a coordinator ruling (point the timer at the fixed code, or stop it writing the live file) — carried from run 9, not re-litigated here.
- **Main moved during this run:** `git fetch origin main` on Stratex-Server showed `98215372..9321b0d1` — a merge landed after this run's branch base `b9e3cf77`. The extract is pinned to `b9e3cf77` (the branch base); the reconciler at that sha is byte-identical to run 9's, so the movement has no effect on this run's figures. The work PR's base will be main at filing time; mergeability is checked then.
- Extract: `git fetch origin main` + `git archive b9e3cf77 Stratex | tar -x -C /tmp/musetp13-str108` on Stratex-Server. Reconciler + test sha256 verified above; diff vs run 9's reconciler reviewed first-hand (zero changes).
- Test suite (daemon venv python, extract paths): `pytest tests/test_daily_fill_ledger_reconciliation.py -q` → **37 passed, 1 warning in 1.37s**.
- Run (backgrounded with setsid detachment, log `/tmp/musetp13-str108-run.log` on Stratex-Server, PID 89045):
  `cd /tmp/musetp13-str108/Stratex && PYTHONPATH=/tmp/musetp13-str108/Stratex:/tmp/musetp13-str108 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-28`
  (the timer service's own invocation, with the extract paths substituted so the merged fixed code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-28: ledger 84 rows (window 75, net -87.97), matching {'NO_MATCH': 54, 'EXIT_ONLY': 16, 'BOTH': 12}, missing closes 4 (-1.16), aged-out carry 31 (+18.37), resets 6 (0 new), status RECONCILED -> /opt/friday_universe/Stratex/state/reconciliation/daily_2026-11-28.json` — no `[ERROR]` alert line (no discrepancy alert fired).
- Ledger before-state: 84 rows, md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, last row recorded 2026-11-27T02:26:41Z. Ledger md5 re-verified unchanged after the run.
- Independent probe: `/tmp/musetp13-str108-probe.py` on Stratex-Server (income cross-check, ETH/SUI presence re-probe, carry income confirmations incl. INJ) — output quoted in §3/§4/§5.

## §8 — Observations for the coordinator / verifier (no ruling owed on the identity)

1. **Run numbering:** board titles this run 10; STR-103 already filed as run 10 (STR-104 code comment). Coordinator to reconcile the numbering; not resolved here.
2. **INJ carry second-fill row (§4):** the −0.0341 residual is fully explained by the INJUSDT order 331708071 second fill's income row not being in the carry. Suggested follow-up: widen the carry's income match so all fills of a multi-fill order are counted. Standing since run 9; 0.3% of tolerance; not a discrepancy.
3. **Timer stale-checkout overwrite (§7):** carried from run 9 — coordinator ruling owed (point the timer at the fixed code, or stop it writing the live file).
4. **Wallet drift (§6):** wallet +0.73 with identical income totals — venue-side snapshot behaviour, not part of the identity; carried.
5. **G-trace:** 73/84 ledger rows carry no order_id; row-to-venue traceability rests on price/qty/time matching — carried from run 9.
