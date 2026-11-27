# TASK-STR-102 — Forward-window fills audit run 9 (evidence)

- **Task:** Stratex: forward-window fills audit run 9 — ledger reconciliation + net P&L evidence (follow-up STR-101 run 8).
- **Owner:** Muse 3. **Claim:** WATCH235 §C (hub #2045 comment 7225676870) + Burn Enforcer 00:00 §B (hub #2045 comment 7225529340): "M3 — claim TASK-STR-102 as head" + paired verifier for PR #2179 MEM-039. Hub claim post #2045 comment 7225854625 (00:16 IST, verified by read-back). Paired verdict #2179 VERIFIED filed as PR review 6092266339 (00:20 IST, verified by read-back; CI 9/9, live re-probe on Server 1: health 200, proof-record read-back id match + scope UNIVERSAL, marker search exactly 1 hit id match).
- **Board verified:** CLAIMED, owner muse_3, branch null, pr null, on live main `a85c9d13` (board blob `f7589962`, 425 records, read via git blob API). Board flip rides in the coordinator consolidated board PR (coordinator-only rule). No prior claim, branch or PR for this run.
- **Branch:** `muse3/task-str-102-forward-window-fills-audit-run-9` from main `a85c9d13` (ref POST verified, HTTP 201).
- **Run-8 note:** STR-101 run 8 (owner muse_tp12) has no evidence on main — its evidence doc returns HTTP 404 on main, board record shows branch null / pr null. Run 9 therefore compares directly against run 7 (STR-096, PR #2048 merged) figures below; if TP12 files run 8 later, its numbers should slot between run 7 and this run.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `a85c9d13`) run live on Stratex-Server (server 4) from a fresh extract `/tmp/muse3-str102` at `a85c9d13` (the live checkout is on main `3db55adf`, which predates the STR-090 merge — the extract, not the live checkout, supplies the fixed code; the live checkout and the daemon were not touched). A `git worktree add` was attempted first but the bridge dropped the call three times before the checkout completed; the `git archive` extract of the `Stratex/` subtree at `a85c9d13` is byte-identical for the files used. Reconciler sha256 `bc90e854c17923c0370aa43236251dc6060f975adce88ccda5bbbe165fb59b1c` — verified identical at `93628618` (run 6's tested base), `4ca0feb2`, `8de8e3ed` (run 7) and `a85c9d13` (this run); test file sha256 `956032e776711fec7b1fb47796dcee8ea7540a479da2fa4b4c042c49a948acbc` — identical at `93628618`, `8de8e3ed` and `a85c9d13`. Same code Muse 4 tested 28/28 on run 6. Daemon venv python 3.10.22. Run at 2026-11-27T18:59:08Z / 2026-11-28 00:29:08 IST, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-28.json` on Stratex-Server and snapshotted to `/tmp/muse3-str102-report.json` on Stratex-Server (md5 `b1a6b8d22168e6253876e64329c25f3a`, identical — the 01:00 UTC timer will overwrite the live file afterwards with the stale-checkout report, as run 7 predicted; the snapshot is the filing of record for this run). The pre-run report is preserved at `/tmp/muse3-str102-before.json` (the timer's 2026-11-27 stale-checkout report). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/muse3-str102/Stratex:/tmp/muse3-str102` so the fixed code runs. Exact command in §6.
- **Host note (carried from run 6/7):** the Oracle Server 1 copy of the Stratex state dir is a **frozen pre-migration copy** — ledger 80 rows, mtime 2026-11-24 01:10 IST, its `Stratex.service` is inactive. The live state is on Stratex-Server: ledger 84 rows, daemon active, last close 2026-11-27T02:26:41Z. This run used Stratex-Server (server 4), as STR-091/STR-094/STR-095/STR-096 did. Do not re-run against the S1 copy — it would reconcile a stale ledger.

## Verdict

**RECONCILED.** The forward-window fill/close ledger reconciles end to end against the venue: window identity residual **−1.6024 USDT** against a tolerance of 10.47 USDT — unchanged since run 2; no matched row disagrees with the venue by more than $0.50 (`diffs_over_0.5: []`). The residual is exactly the aged-out Nov-19 reset-wipe micro-closes (−1.6023) that sit outside the venue's ~7-day `userTrades`/`allOrders` window.

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-27T02:26:41Z last close)

| Figure | Run 9 (this run, 18:59 UTC) | Run 7 (00:57 UTC) |
|---|---|---|
| Ledger closes, all time | 84 rows | 83 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 |
| Ledger closes in forward window | 75 rows | 74 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.923 + OANDA USDJPY −0.0478) | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 40 rows −147.9099 | (none) 44 rows +254.9989; FORWARD_TEST 39 rows −147.9099 |
| Venue closes in window | 80 (75 ledger + 5 missing) | 78 (74 ledger + 4 missing) |
| Venue window true net P&L | −69.1908 | −59.7759 |
| Venue account at run time | wallet 10,437.29, margin 10,466.23, unrealised +28.93, available 9,439.78 USDT (USDT 4,924.28 + USDC 5,000 + BTC 0.01) | wallet 10,453.52, margin 10,481.30, unrealised +27.79, available 9,454.55 |
| Open positions at run time | 30, unrealised +28.9223 | 30, unrealised +27.8579 |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−67.4283**, COMMISSION **−9.8166**, FUNDING_FEE **+0.7282**, TRANSFER +15,000.03 | REALISED −58.0134, COMMISSION −9.6135, FUNDING +0.6514, TRANSFER +15,000.03 |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` |

Change run 7 → run 9: one new ledger close (LTCUSDT SHORT 5.706, entry 42.86 → exit 41.82186275, recorded 2026-11-27T02:26:41Z) — the daemon recorded it with zero pnl fields (gross 0.0 / fees 0.0 / net 0.0), so the ledger window net is unchanged at −87.9709 and the venue close for it (order 1615011544, realised −9.4149) stays in the missing-closes set (§3). Venue realised moved −58.0134 → −67.4283 by exactly that −9.4149. Everything else is mark-price drift on the 30 open positions (unrealised +27.86 → +28.92) plus funding/commission accrual. Wallet −16.23: −9.41 of it is the LTCUSDT close; the balance is intra-day venue movement not itemised by the reconciler (the 0.01 BTC holding's mark fell 60,684.70 → 59,883.10 over the same period).

## §2 — Matching classes: the BOTH → EXIT_ONLY / NO_MATCH drift continues

| Class | Run 9 (18:59 UTC) | Run 7 (00:57 UTC) |
|---|---|---|
| BOTH | 13 | 22 |
| EXIT_ONLY | 15 | 18 |
| NO_MATCH | 54 | 41 |
| Rows matched | 82 | 81 |
| Matched exit realised / matched ledger net | −30.7439 / −32.7818 | −64.048 / −67.1767 |
| Diffs over $0.50 | none | none |

Nine more rows left BOTH since run 7 (six to NO_MATCH, three to EXIT_ONLY): their **entry** fills have aged out of the venue's ~7-day `userTrades`/`allOrders` window as the Nov 19–21 closes cross the boundary — the same retention effect STR-091 §7 documented for exit fills and run 6 §7 for entry fills. Nothing was lost: the ledger rows, the exit fills, and the realised P&L are all still present and reconciled; the matched totals still tie out (exit realised −30.7439 vs matched ledger net −32.7818 = 2.0379, the matched set's own fees). The G1 gap (5 missing closes, +18.78) is §3.

## §3 — Missing closes (G1): the same 4 as run 6/7, plus the new LTCUSDT close

| Symbol | Order | Side | Qty | Realised | Commission | Fills |
|---|---|---|---|---|---|---|
| ETHUSDT | 16876077891 | BUY | 0.148 | +19.9399 | 0.095 | 2 |
| SUIUSDT | 1100728824 | BUY | 304.4 | +30.5009 | 0.0727 | 1 |
| VETUSDT | 458616420 | BUY | 42328.0 | −10.9206 | 0.0778 | 1 |
| SANDUSDT | 340506462 | BUY | 5219.0 | −11.3252 | 0.0712 | 1 |
| LTCUSDT | 1615011544 | BUY | 5.706 | −9.4149 | 0.1016 | 1 |

Total +18.7801 (was +28.195: the same 4 as run 2–7, plus LTCUSDT −9.4149). The LTCUSDT venue close has a ledger row (row 84) but the row carries no order_id and zero pnl fields, so the reconciler could not match it to the venue order — it stays missing. G-trace: 73/84 ledger rows carry no order_id; row-to-venue traceability rests on price/qty/time matching.

## §4 — Window identity

Venue realised −67.4283; ledger window net −87.9231; missing closes +18.7801; window fees 3.3171; expected venue realised −65.8259; **residual −1.6024**; tolerance 10.47; status RECONCILED. Forward window: 75 fills, ledger net −87.9709, 80 closes on venue, venue true net −69.1908. Unmatched zero-realised fills: 20 orders (entry legs, realised 0.0; was 24).

## §5 — Funding and income: accrual continues, no anomaly

Report `income_since_reset`: COMMISSION −9.8166, FUNDING_FEE +0.7282, TRANSFER +15,000.03, REALISED_PNL −67.4283. vs run 7: COMMISSION −0.2031 (new closes' fees — the LTCUSDT close commission 0.1016 plus aged fills settling), FUNDING_FEE +0.0768 (funding intervals settling between the runs), REALISED_PNL −9.4149 (exactly the LTCUSDT close). No separate independent income probe was run this run: the reader is the same merged code run 6 probed independently (1,122 income rows, pagination past the 1,000-row venue cap, totals exact), and the report's income block matches that probe's structure on every line, with the movements above exactly explained by the single new close plus funding accrual. Funding is unfrozen and moving.

## §6 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge `250cf2b4`); `Stratex.service` **active**; `friday-stratex-reconciliation.timer` next 2026-11-28 01:00:00 UTC (its code is the stale checkout, so its report will overwrite `daily_2026-11-28.json` at 01:00 UTC — the snapshot `/tmp/muse3-str102-report.json` is the filing of record for this run; all figures are preserved here).
- Extract: `git fetch origin main` + `git archive a85c9d13 Stratex | tar -x -C /tmp/muse3-str102` on Stratex-Server (origin/main was `eb7f81d0` before the fetch — the first `git archive` failed "not a tree object" because `a85c9d13` had not been fetched yet; after the fetch the archive landed). A `git worktree add /tmp/muse3-str102 a85c9d13` was attempted first and dropped three times on bridge transport errors before completing; the archive extract supplies byte-identical `Stratex/` files (sha256 verified above). The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- Run (backgrounded, log `/tmp/muse3-str102-run.log` on Stratex-Server):
  `cd /tmp/muse3-str102/Stratex && PYTHONPATH=/tmp/muse3-str102/Stratex:/tmp/muse3-str102 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-28`
  (the timer service's own invocation, with the extract paths substituted so the merged fixed code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-28: ledger 84 rows (window 75, net -87.97), matching {'NO_MATCH': 54, 'EXIT_ONLY': 15, 'BOTH': 13}, missing closes 5 (+18.78), resets 6 (0 new), status RECONCILED -> /opt/friday_universe/Stratex/state/reconciliation/daily_2026-11-28.json`
- Ledger before-state: 84 rows, md5 `33ccec264a95c1e3f0e418bd1e6e3d95`, last row recorded 2026-11-27T02:26:41Z (the LTCUSDT close). Report snapshot md5 `b1a6b8d22168e6253876e64329c25f3a` (live file and snapshot identical).
- Bridge note: `run_shell` responses intermittently die with `http.client.IncompleteRead` / `RemoteDisconnected` / "MCP event stream ended" / "MCP request did not complete" (9 drops this run: worktree add ×3, archive ×1, check probes ×2, echo ×1, worktree list ×1, git status ×1); every dropped call was retried with a fresh session and every figure re-read after a successful call. No data was faked — the extract landed on retry (verified by sha256), and the report snapshot was verified by md5 + full re-read.
- Tests: `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — **28/28 passed** on run 6 by Muse 4 on this exact code (reconciler + test blobs verified identical between `93628618`, `8de8e3ed` and `a85c9d13` this run, sha256 above). No test file changed in this task. CI re-verification from this work PR's job log follows (STR-091 lesson: the file is collected by `owner-workflows.yml` "Stratex forward-test and self-experiment contracts").

## §7 — Open positions at run time (30, unrealised +28.9223)

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | -0.5 | 109.88 | 94.57 | +7.655 |
| ADAUSDT | +301.0 | 0.1494 | 0.1494 | +0.0 |
| ALGOUSDT | -2293.4 | 0.08004 | 0.08125 | -2.775014 |
| APTUSDT | -116.9 | 0.4356 | 0.3868 | +5.70472 |
| ARBUSDT | -410.7 | 0.1269168736304 | 0.1147756 | +4.98641958 |
| ATOMUSDT | -151.7 | 1.186 | 1.22936905 | -6.57908488 |
| AVAXUSDT | -3.0 | 7.015 | 6.641 | +1.122 |
| BCHUSDT | -0.388 | 208.3815979381 | 206.15675886 | +0.86323755 |
| BNBUSDT | -0.08 | 590.59 | 553.25 | +2.9872 |
| BTCUSDT | +0.0025 | 59889.32 | 59883.1 | -0.01555 |
| DOGEUSDT | -1453.0 | 0.05505 | 0.05771497 | -3.87220141 |
| DOTUSDT | -102.7 | 0.6728 | 0.668 | +0.49296 |
| ETCUSDT | -14.63 | 5.659 | 5.889 | -3.3649 |
| ETHUSDT | +0.111 | 1681.3 | 1671.11437016 | -1.13060491 |
| FILUSDT | -81.9 | 0.5788 | 0.53257273 | +3.78601341 |
| HBARUSDT | -1433.0 | 0.05152 | 0.05379 | -3.25291 |
| INJUSDT | -19.0 | 6.657 | 6.34631038 | +5.90310278 |
| LINKUSDT | -8.79 | 8.629 | 9.39350415 | -6.71999147 |
| LTCUSDT | +5.72 | 44.37 | 43.86382353 | -2.8953294 |
| MANAUSDT | -1342.0 | 0.060599538003 | 0.05739821 | +4.29617144 |
| NEARUSDT | -14.0 | 2.901 | 3.03202973 | -1.83441622 |
| OPUSDT | -661.6 | 0.0768 | 0.07123205 | +3.68375572 |
| SANDUSDT | -1822.0 | 0.03348 | 0.03440206 | -1.67999332 |
| SOLUSDT | -2.1 | 69.02 | 71.94350327 | -6.13935686 |
| SUIUSDT | -96.1 | 0.6446 | 0.6732 | -2.74846 |
| TRXUSDT | -750.0 | 0.30999 | 0.30087485 | +6.8363625 |
| UNIUSDT | -9.0 | 4.707444444444 | 4.81590997 | -0.97618977 |
| VETUSDT | +40580.0 | 0.004618 | 0.00494876 | +13.4222408 |
| XLMUSDT | -1792.0 | 0.13436 | 0.12681 | +13.5296 |
| XRPUSDT | -93.7 | 0.925 | 0.95021308 | -2.36246559 |

All 3× leverage. Position set identical to run 7 (same 30 symbols) except LTCUSDT flipped SHORT −5.706 @ 42.86 → LONG +5.72 @ 44.37 (the short closed at 41.82 for −9.4149 venue realised; the new long opened after). Only marks drifted otherwise. Venue account unrealised +28.9324 (account-level read) vs positions sum +28.9223 (0.0101 apart — different read moments in the same run).

## Five states

- Implemented: YES (evidence filed on branch, no code change — filing only)
- Tested: YES (live probe exit 0 on Stratex-Server; reconciler + test blobs verified identical to run 6's 28/28-tested code; CI re-verification follows from this PR)
- Merged: NO (work PR open, awaiting coordinator merge)
- Deployed: n/a (no deploy; read-only probe, no service touched)
- Production-verified: YES (live ledger reconciled end to end on Stratex-Server under clearance 7200564540)

## Files changed

- `docs/collaboration/TASK-STR-102-EVIDENCE.md` (new, this file only)

— Muse 3
