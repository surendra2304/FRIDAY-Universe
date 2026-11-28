# TASK-STR-109 — Forward-window fill-ledger state run 11 (evidence)

- **Task:** Stratex: forward-window fill-ledger state run 11 — fills, closes, net P&L vs venue.
- **Owner:** Muse 12. **Claim:** hub #2045 comment 7232726900, 2026-11-28 ~08:30 IST, per WATCH251 §E (hub 7232592508; answers my free post). **Board:** CLAIMED / muse_12 / P1 on coordinator board PR #2250 (blob `b1b8069c5bfa3e13be645a3918ac09ed4ebfc1c0`, head `ca0785f5`; the record is drafted there — not yet on main, flip rides that PR). Acceptance = daemon fill/close ledger reconciled end-to-end against venue positions/history, evidence as `docs/collaboration/TASK-STR-109-EVIDENCE.md`.
- **Branch:** `muse12/task-str-109-forward-window-fill-ledger-run-11` from main `9321b0d1` (ref POST verified at claim time).
- **Sequence note:** the board titles this run 11, but STR-102 filed as run 9, STR-103 as run 10 (per the STR-104 code comment), STR-105 as run 9 and STR-108 as run 10. This is the next window after STR-108 run 10 (Muse TP13, PR #2252 open). The numbering overlap is flagged for the coordinator, not resolved here.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `9321b0d1`) run live on Stratex-Server (server 4) from a fresh extract `/tmp/muse12-str109` at `9321b0d1` (the live checkout is on main `3db55adf`, which predates the STR-090 merge — the extract, not the live checkout, supplies the fixed code; the live checkout and the daemon were not touched). `git archive 9321b0d1 Stratex | tar -x` used directly (M3's run-9 note: `git worktree add` dropped repeatedly on bridge transport). Reconciler sha256 `c1da1c1399de7ea0e4c04c1832845e16a03e84cb820c254bce4bf85b0b3d08f1` — **byte-identical to runs 9 and 10** (diff vs the run-10 extract: source identical, only `__pycache__` differs). Test file sha256 `fa0831288a732e1708d3e42e9650ae58456839bb4636b810e15b5286e3ebba9a` — also identical to runs 9/10. Daemon venv python. Run at 2026-11-28T03:02:44Z / 08:32 IST, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-28.json` on Stratex-Server and snapshotted to `/tmp/muse12-str109-report.json` on Stratex-Server (md5 `e4d8e9eff0d064e2a92396711cf11f94`, live file and snapshot identical). The pre-run report is preserved at `/tmp/muse12-str109-before.json` (md5 `b38a331848147cecc1e0e6b458c9700a` — run 10's report, TP13). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/muse12-str109/Stratex:/tmp/muse12-str109` so the fixed code runs. Exact command in §7.
- **Host note (carried from runs 6/7/8/9/10):** the Oracle Server 1 copy of the Stratex state dir is a **frozen pre-migration copy** — do not re-run against the S1 copy; the live state is on Stratex-Server, as STR-091/STR-094/STR-095/STR-096/STR-100/STR-101/STR-102/STR-105/STR-108 did. This run used Stratex-Server (server 4).

## Verdict

**RECONCILED.** The forward-window identity residual is **−0.0341 USDT** against a tolerance of 10.48 USDT — identical to runs 9 and 10 to the cent. The ledger is byte-identical to runs 9/10 state (md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, 84 rows, last close 2026-11-27T02:26:41Z) — nothing was lost, nothing was written, no close was missed by the daemon. The G1 missing-closes set is unchanged (4, −1.1598); the aged-out carry is unchanged (31, +18.3716), all income-confirmed, 0 unconfirmed. **Root cause of the standing −0.0341 residual (found by run 10, TP13 §4, confirmed here):** the INJUSDT micro-close's second fill income row (−0.034) is not in the carry — the carry understates by exactly the residual. No ruling owed on the identity; the carry gap is an observation for the reconciler owner, not a discrepancy. No matched row disagrees with the venue by more than $0.50 (`diffs_over_0.5: []`). Open observations (timer stale-checkout overwrite, run numbering, wallet note) are filed in §7, not hidden.

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-27T02:26:41Z last close)

| Figure | This run (STR-109, 03:02 UTC) | Run 10 (STR-108, 02:30 UTC) | Run 9 (STR-105, 01:02 UTC) |
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
| Venue account at run time | wallet 10,438.16, margin 10,481.24, unrealised +43.08, available 9,455.56 USDT (USDT 4,924.35 + USDC 5,000 + BTC 0.01) | wallet 10,439.08, margin 10,477.67, unrealised +38.59, available 9,449.06 | wallet 10,438.35, margin 10,470.98, unrealised +32.62, available 9,442.10 |
| Open positions at run time | 30, unrealised +43.11 (positions sum) / +43.08 (account) | 30, unrealised +38.58 | 30, unrealised +32.47 |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−67.4283**, COMMISSION **−9.8166**, FUNDING_FEE **+0.806**, TRANSFER +15,000.03 | same totals | same totals |
| Income rows fetched | **1,243** (881 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER) | 1,243 | 1,243 |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` | `[]` |

Change run 10 → this run: no new ledger close (ledger md5 identical, 84 rows, last close unchanged 2026-11-27T02:26:41Z). The only movement is mark-price drift on the 30 open positions (unrealised +38.58 → +43.11; wallet −0.92 — see the wallet note in §6, it does not tie to the income deltas and is not part of the reconciled identity) and no funding movement (rows 881, total +0.806 — unchanged in the 32 minutes between runs; funding accrues slowly, not frozen — it grew 851 → 881 rows between run 8 and run 9). The missing-closes set, the matched sums and the ledger are all unchanged since run 10.

## §2 — Net P&L by symbol (window, 75 closes — re-derived independently this run)

Re-derived from the live ledger (`fill_ledger.jsonl`, exit_time ≥ forward-window start) in a separate process from the reconciler run; matches the report exactly in total (−87.9709) and matches run 9 §2 per-symbol to the cent on every symbol:

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

The 75 window rows are the same rows as run 7 §5 / run 8 §2 / run 9 §2 (ledger unchanged since run 7 — same md5, same per-symbol nets, same all-time cross-check); they are not reprinted here. Outside-window rows: 9, all 2026-11-14, unchanged.

## §3 — The aged-out carry: proof (independent probe, separate process)

- **Missing closes (G1) — 4, realised −1.1598** (unchanged from runs 8/9/10): SUIUSDT order 1100728824 BUY 304.4 **+30.5009**; VETUSDT order 458616420 BUY 42,328 **−10.9206**; SANDUSDT order 340506462 BUY 5,219 **−11.3252**; LTCUSDT order 1615011544 BUY 5.706 **−9.4149**.
- **Aged-out carry — 31 orders, realised +18.3716, all income-confirmed, 0 unconfirmed.** The ETHUSDT close (order `16876077891`, BUY 0.148, **+19.9399**, 2 fills, 2026-11-20T00:34:38Z, first/last fill `1795202078059`) plus 30 micro-closes (−0.0055 … −0.136 each, first fills 2026-11-19, totalling −1.5683 — the Nov-19 reset-wipe micro-closes behind the unchanged-since-run-2 base residual). The 30 micro-closes are one per symbol (TRX, MANA, FIL, DOT, ETH, SUI, BCH, INJ, ETC, LTC, ATOM, XRP, LINK, VET, NEAR, AAVE, BTC, SOL, APT, AVAX, UNI, BNB, DOGE, XLM, OP, HBAR, ALGO, ADA, SAND, ARB).
- **Direct venue probe** (`/tmp/muse12-str109-probe.py`, same `DemoFuturesReader`, same env file, separate process from the reconciler run): ETHUSDT `userTrades` returns **n=2** trades, earliest `1795268189087` ms (2026-11-21T07:36:29Z) — order 16876077891 present=0; ETHUSDT `allOrders` returns **n=2** orders, order 16876077891 present=0. Identical to run 9's probe — the close's fills (00:34:38Z Nov 20) are still absent from both endpoints. **Control:** SUIUSDT order 1100728824 IS present in `userTrades` (n=8) and `allOrders` (n=4, FILLED) — the endpoints work; only aged-out fills are gone.
- **Income confirmation (independent, same probe):** ETHUSDT REALIZED_PNL rows within ±5 min of the ETH close's fill times sum to **+19.9399 over 2 rows** — exactly the recorded amount. Spot checks on micro-closes: TRXUSDT order 1173153567, 1 row, **−0.0055**; MANAUSDT order 241723755, 1 row, **−0.0376** — both exactly recorded. The carried amounts are income-endpoint sums, never the residual — the identity stays an independent check.
- **Matching (82 Binance rows):** BOTH 12, EXIT_ONLY 16, NO_MATCH 54 — identical to runs 9 and 10 (no further BOTH→EXIT_ONLY shift this run; the matched-exit set is unchanged at 28 rows with identical sums: matched exit realised −30.7439 vs matched ledger net −32.7818; the difference is the matched rows' fees, 2.0379, so the matched set ties out exactly). **Diffs over $0.50: none.** Unmatched zero-realised fills: 20 orders (entry legs of the open positions + breakeven entries — visible, never silently dropped; run 9/10: 20).

## §4 — Window identity (re-derived from the report)

Ledger window net (Binance) −87.9231 + missing closes −1.1598 + aged-out carry +18.3716 + window fees 3.3171 = expected venue realised **−67.3942**; venue realised **−67.4283**; residual **−0.0341**, tolerance 10.48, status **RECONCILED**. Check: residual run 10 (−0.0341) = this run (−0.0341) ✓ — the identity has been stable across runs 9, 10 and 11. Venue true net (excl. carry) −89.1307 = ledger window net −87.9709 + missing −1.1598 ✓. Report `forward_window.venue_true_net_pnl` −70.7591 = ledger window net + missing + carry ✓ (definition stated in §1 — the two figures differ only by the carry).

## §5 — Funding cross-check: STR-090 pagination fix holds live

Independent direct `income()` call (separate process, same reader, same env file): **1,243 income rows** since the reset floor — 881 FUNDING_FEE, 271 COMMISSION, 85 REALIZED_PNL, 6 TRANSFER — totals **FUNDING_FEE +0.8067, COMMISSION −9.8158, REALIZED_PNL −67.4282, TRANSFER +15,000.03**, matching the report's `income_since_reset` to within $0.001 on every total (probe ran ~3 min after the report; the sub-cent deltas are summation rounding, not movement — the identity-critical REALIZED_PNL agrees to 0.0001). The 1,000-row venue cap is paginated past (1,243 > 1,000). Funding unchanged since run 10 (rows 881, total +0.806) — no new funding rows in 32 minutes; funding is unfrozen and accruing on a slower cadence (it grew 851 → 881 rows between run 8 and run 9).

## §6 — Open positions at run time (30, unrealised +43.1081) + wallet note

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 94.58 | +7.6500 |
| ADAUSDT | +301.0 | 0.1494 | 0.14772109 | −0.5054 |
| ALGOUSDT | −2293.4 | 0.08004 | 0.08009 | −0.1147 |
| APTUSDT | −116.9 | 0.4356 | 0.38707221 | +5.6729 |
| ARBUSDT | −410.7 | 0.1269168736304 | 0.11373156 | +5.4152 |
| ATOMUSDT | −151.7 | 1.186 | 1.22784762 | −6.3483 |
| AVAXUSDT | −3.0 | 7.015 | 6.60562833 | +1.2281 |
| BCHUSDT | −0.388 | 208.3815979381 | 208.90887205 | −0.2046 |
| BNBUSDT | −0.08 | 590.59 | 555.32010012 | +2.8216 |
| BTCUSDT | +0.0025 | 59,889.32 | 59,949.0 | +0.1492 |
| DOGEUSDT | −1453.0 | 0.05505 | 0.05760586 | −3.7137 |
| DOTUSDT | −102.7 | 0.6728 | 0.66275513 | +1.0316 |
| ETCUSDT | −14.63 | 5.659 | 5.89503491 | −3.4532 |
| ETHUSDT | +0.111 | 1,681.3 | 1,664.28 | −1.8892 |
| FILUSDT | −81.9 | 0.5788 | 0.52726109 | +4.2210 |
| HBARUSDT | −1433.0 | 0.05152 | 0.05334206 | −2.6110 |
| INJUSDT | −19.0 | 6.657 | 6.284 | +7.0870 |
| LINKUSDT | −8.79 | 8.629 | 9.318 | −6.0563 |
| LTCUSDT | +5.72 | 44.37 | 44.79070366 | +2.4064 |
| MANAUSDT | −1342.0 | 0.060599538003 | 0.05737857 | +4.3225 |
| NEARUSDT | −14.0 | 2.901 | 3.044 | −2.0020 |
| OPUSDT | −661.6 | 0.0768 | 0.07015068 | +4.3992 |
| SANDUSDT | −1822.0 | 0.03348 | 0.03446 | −1.7856 |
| SOLUSDT | −2.1 | 69.02 | 71.7 | −5.6280 |
| SUIUSDT | −96.1 | 0.6446 | 0.6731921 | −2.7477 |
| TRXUSDT | −750.0 | 0.30999 | 0.30035 | +7.2300 |
| UNIUSDT | −9.0 | 4.707444444444 | 4.78169029 | −0.6682 |
| VETUSDT | +40,580.0 | 0.004618 | 0.00499206 | +15.1794 |
| XLMUSDT | −1792.0 | 0.13436 | 0.12633025 | +14.3893 |
| XRPUSDT | −93.7 | 0.925 | 0.95026833 | −2.3676 |

All 3× leverage. Position set identical to runs 9/10 (same 30 symbols); only marks drifted. Venue account unrealised +43.0793 (account-level read) vs positions sum +43.1081 (0.03 apart — different read moments in the same run).

**Wallet note (open observation, carried from run 7 §10):** wallet 10,439.08 (run 10, 02:30 UTC) → 10,438.16 (this run, 03:02 UTC): movement −0.92 while the income totals are IDENTICAL over the same interval. The wallet balance moves independently of the income ledger on this demo account — it is a venue-side snapshot, not part of the reconciled identity. Flagged here for the paired verifier, not hidden.

## §7 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge); `Stratex.service` **active**, `Stratex-Daemon.service` **active** (verified first-hand this run). The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- **Timer note (recurring):** the 01:00 UTC `friday-stratex-reconciliation.timer` run fired before run 10 and overwrote `daily_2026-11-28.json` with the **stale-checkout** report (DISCREPANCY, residual +38.5348 per run 9 §7). Run 10 overwrote it at 02:30:56 UTC with the fixed-code RECONCILED report; this run overwrote that at 03:02:44 UTC. The pre-run snapshot `/tmp/muse12-str109-before.json` (md5 `b38a331848147cecc1e0e6b458c9700a`) preserves run 10's report; this run's report (md5 `e4d8e9eff0d064e2a92396711cf11f94`) is snapshotted at `/tmp/muse12-str109-report.json`. The timer overwriting the live file daily with a wrong DISCREPANCY is worth a coordinator ruling (point the timer at the fixed code, or stop it writing the live file) — still open, carried from runs 9/10.
- Extract: `git fetch origin main` + `git archive 9321b0d1 Stratex | tar -x -C /tmp/muse12-str109` on Stratex-Server (origin/main `9321b0d1` on fetch). Reconciler + test sha256 verified above; diff vs run 10's extract: source identical (only `__pycache__` differs).
- Run (backgrounded, log `/tmp/muse12-str109-run.log` on Stratex-Server):
  `cd /tmp/muse12-str109/Stratex && PYTHONPATH=/tmp/muse12-str109/Stratex:/tmp/muse12-str109 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-28`
  (the timer service's own invocation, with the extract paths substituted so the merged fixed code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-28: ledger 84 rows (window 75, net -87.97), matching {'NO_MATCH': 54, 'EXIT_ONLY': 16, 'BOTH': 12}, missing closes 4 (-1.16), aged-out carry 31 (+18.37), resets 6 (0 new), status RECONCILED -> /opt/friday_universe/Stratex/state/reconciliation/daily_2026-11-28.json` — no `[ERROR]` alert line (no discrepancy alert fired). Exit 0.
- Ledger before-state: 84 rows, md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, last row recorded 2026-11-27T02:26:41Z. Ledger md5 re-verified unchanged after the run.
- Independent probes (separate processes, same reader/env): `/tmp/muse12-str109-probe.py` (adapted from the run-9 probe: extract + report paths updated, logic unchanged) — ledger re-derivation (window 75, net −87.9709; per-symbol nets §2; all-time +107.089; outside rows 9) + income probe (1,243 rows, totals to $0.001) + ETH/SUI fills probe (§3) + carry income confirmations (§3).
- Bridge note: all bridge calls this run completed first-try except two local JSON-arg errors (a malformed probe args file, fixed by rewriting it in Python; and one `run_shell` call that backgrounded and delivered normally). No data was faked. No figure in this file comes from a run-9/10 document — every number above was re-read live this run from the server or the venue.
- Tests: `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — **37/37 passed** (1 warning) on Stratex-Server in the exact run-11 extract (pytest, 4.64s, `PYTHONPATH=/tmp/muse12-str109/Stratex:/tmp/muse12-str109`); runs 9/10 also had 37 tests. No test file changed in this task. CI re-verification from the work PR's job log follows (STR-091 lesson: the file is collected by `owner-workflows.yml` "Stratex forward-test and self-experiment contracts").

## Five states

- implemented: YES (this evidence doc filed on branch `muse12/task-str-109-forward-window-fill-ledger-run-11`)
- tested: YES (reconciler run live on Stratex-Server + independent funding/income probe + independent ledger re-derivation + independent ETH-ageing/carry probe + 37/37 tests on the exact run-11 code)
- merged: NO (work PR open at filing; paired verification by a different chat owed — never merge own PR)
- deployed: N/A (nothing deployed; proof ran against the existing deploy, daemon untouched)
- production-verified: NO (paired verification by a different chat owed before this counts)

— Muse 12
