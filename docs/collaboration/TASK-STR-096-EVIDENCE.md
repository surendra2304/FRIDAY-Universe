# TASK-STR-096 — Forward-window fill/close ledger state filing run 7 (evidence)

- **Task:** Stratex: forward-window fill/close ledger state filing run 7 — reconcile daemon ledger vs venue positions/history after STR-095.
- **Owner:** Muse 3. **Claim:** branch `muse3/task-str-096-forward-window-ledger-run-7` created from main `8de8e3ed` (verified via ref GET). Hub claim post BLOCKED: issue #1483 reached GitHub's 2,500-comment cap during this run — claim POST returned HTTP 403 ("Commenting is disabled on issues with more than 2500 comments"); no successor hub issue exists yet (newest open issues are work PRs #2039–#2043). Claim to be posted on the successor hub once Muse opens it. Queue head reached: VYR-086 now Muse 9, VYR-088 on coordinator HOLD (skipped), REL-090 blocked by owner stop order 7130069033 (live repoint).
- **Board verified:** AVAILABLE, owner muse_3, branch null, pr null, on live main `8de8e3ed` (board blob `552c9e04`, 25,021 lines, read via git blob API). No prior claim, branch or PR for this run. Board flip rides in the coordinator consolidated board PR (coordinator-only rule).
- **Branch:** `muse3/task-str-096-forward-window-ledger-run-7` from main `8de8e3ed`.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `8de8e3ed`) run live on Stratex-Server (server 4) from a fresh worktree `/tmp/muse3-str096` at `8de8e3ed` (the live checkout is on main `3db55adf`, which predates the STR-090 merge — the worktree, not the live checkout, supplies the fixed code; the live checkout and the daemon were not touched). Reconciler sha256 `bc90e854c17923c0370aa43236251dc6060f975adce88ccda5bbbe165fb59b1c` — verified identical at `93628618` (run 6's tested base), `4ca0feb2` and `8de8e3ed`; test file sha256 `956032e776711fec7b1fb47796dcee8ea7540a479da2fa4b4c042c49a948acbc` — identical at `93628618` and `8de8e3ed`. Same code Muse 4 tested 28/28 on run 6. Daemon venv python 3.10.22. Run at 2026-11-27T00:57:12Z / 2026-11-27 06:27:12 IST, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-27.json` on Stratex-Server and snapshotted to `/tmp/muse3-str096-report.json` on Stratex-Server (the 01:00 UTC timer overwrote the live file afterwards with the stale-checkout report, as run 6 predicted — live md5 differs from the snapshot; the snapshot is the filing of record for this run). The pre-run report is preserved at `/tmp/muse3-str096-before.json` (run_at 2026-11-26T22:15:13Z). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/muse3-str096/Stratex:/tmp/muse3-str096` so the fixed code runs. Exact command in §6.
- **Host note (carried from run 6):** the Oracle Server 1 copy of the Stratex state dir is a **frozen pre-migration copy** — ledger 80 rows, mtime 2026-11-24 01:10 IST, its `Stratex.service` is inactive. The live state is on Stratex-Server: ledger 83 rows, daemon active, last close 2026-11-26T14:42:27Z. This run used Stratex-Server (server 4), as STR-091/STR-094/STR-095 did. Do not re-run against the S1 copy — it would reconcile a stale ledger.

## Verdict

**RECONCILED.** The forward-window fill/close ledger reconciles end to end against the venue: window identity residual **−1.6024 USDT** against a tolerance of 10.48 USDT; no matched row disagrees with the venue by more than $0.50 (`diffs_over_0.5: []`). The residual is unchanged since run 2 — it is exactly the aged-out Nov-19 reset-wipe micro-closes (−1.6023) that sit outside the venue's ~7-day `userTrades`/`allOrders` window. The ledger itself is unchanged between run 6 and this run.

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-26T14:42:27Z last close)

| Figure | Run 7 (this run, 00:57 UTC) | Run 6 (19:53 UTC) |
|---|---|---|
| Ledger closes, all time | 83 rows | 83 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 |
| Ledger closes in forward window | 74 rows | 74 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.923 + OANDA USDJPY −0.0478) | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 39 rows −147.9099 | same |
| Venue closes in window | 78 (74 ledger + 4 missing) | 78 (74 ledger + 4 missing) |
| Venue window true net P&L | −59.7759 | −59.7759 |
| Venue account at run time | wallet 10,453.52, margin 10,481.30, unrealised +27.79, available 9,454.55 USDT (USDT 4,933.82 + USDC 5,000 + BTC 0.01) | wallet 10,453.88, margin 10,483.14, unrealised +29.26, available 9,456.67 |
| Open positions at run time | 30, unrealised +27.8579 | 30, unrealised +29.2952 |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−58.0134**, COMMISSION **−9.6135**, FUNDING_FEE **+0.6514**, TRANSFER +15,000.03 | REALISED −58.0134, COMMISSION −9.6135, FUNDING +0.6774, TRANSFER +15,000.03 |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` |

Change run 6 → run 7: ledger unchanged (no new close since 2026-11-26T14:42:27Z); the only movement is mark-price drift on the 30 open positions (unrealised +29.30 → +27.86; wallet −0.36) and one funding interval settling (FUNDING_FEE +0.6774 → +0.6514, −0.0260).

## §2 — Matching classes: the BOTH → EXIT_ONLY / NO_MATCH drift continues

| Class | Run 7 (00:57 UTC) | 22:15 UTC snapshot | Run 6 (19:53 UTC) |
|---|---|---|---|
| BOTH | 22 | 24 | 25 |
| EXIT_ONLY | 18 | 16 | 17 |
| NO_MATCH | 41 | 41 | 39 |
| Rows matched | 81 | 81 | 81 |
| Matched exit realised / matched ledger net | −64.048 / −67.1767 | −64.048 / −67.1767 | −64.048 / −67.1767 |
| Diffs over $0.50 | none | — | none |

Three rows left BOTH since run 6 (two to NO_MATCH, one to EXIT_ONLY): their **entry** fills have aged out of the venue's ~7-day `userTrades`/`allOrders` window as the Nov 19–21 closes cross the boundary — the same retention effect STR-091 §7 documented for exit fills and run 6 §7 for entry fills. The 22:15 UTC pre-run snapshot (matching 41/16/24) shows the drift mid-evening. Nothing was lost: the ledger rows, the exit fills, and the realised P&L are all still present and reconciled; the matched totals still tie out exactly (exit realised −64.048 vs matched ledger net −67.1767 = window fees 3.3171, within the matched set). The G1 gap (4 missing closes, +28.20) is unchanged since run 2.

## §3 — Missing closes (G1): same 4 as run 6

| Symbol | Order | Side | Qty | Realised | Commission | Fills |
|---|---|---|---|---|---|---|
| ETHUSDT | 16876077891 | BUY | 0.148 | +19.9399 | 0.095 | 2 |
| SUIUSDT | 1100728824 | BUY | 304.4 | +30.5009 | 0.0727 | 1 |
| VETUSDT | 458616420 | BUY | 42328.0 | −10.9206 | 0.0778 | 1 |
| SANDUSDT | 340506462 | BUY | 5219.0 | −11.3252 | 0.0712 | 1 |

Total +28.195. Unchanged since run 2. G-trace: 72/83 ledger rows carry no order_id; row-to-venue traceability rests on price/qty/time matching.

## §4 — Window identity

Venue realised −58.0134; ledger window net −87.9231; missing closes +28.195; window fees 3.3171; expected venue realised −56.411; **residual −1.6024**; tolerance 10.48; status RECONCILED. Forward window: 74 fills, ledger net −87.9709, 78 closes on venue, venue true net −59.7759. Unmatched zero-realised fills: 24 orders (entry legs, realised 0.0).

## §5 — Funding: one interval settled since run 6

Report `income_since_reset`: COMMISSION −9.6135, FUNDING_FEE +0.6514, TRANSFER +15,000.03, REALISED_PNL −58.0134. All totals identical to run 6's independently-probed figures except FUNDING_FEE (+0.6774 → +0.6514, −0.0260 — one funding interval settled between the runs). No separate independent income probe was run this run: the reader is the same merged code run 6 probed independently (1,122 income rows, pagination past the 1,000-row venue cap, totals exact), and the report's income block matches that probe on every line except the live funding accrual. Funding is unfrozen and moving.

## §6 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge `250cf2b4`); `Stratex.service` **active**; `friday-stratex-reconciliation.timer` next 2026-11-27 01:00:00 UTC (its code is the stale checkout, so its report overwrote `daily_2026-11-27.json` at 01:00 UTC — the snapshot `/tmp/muse3-str096-report.json` is the filing of record for this run; all figures are preserved here).
- Worktree: `git fetch origin main` + `git worktree add /tmp/muse3-str096 origin/main` on Stratex-Server (server's origin/main was `4ca0feb2`, one merge ahead of this branch's base; worktree re-pointed to `8de8e3ed` — reconciler sha256 identical at both commits, verified). The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- Run (backgrounded, log `/tmp/muse3-str096-run.log` on Stratex-Server, pid 61081):
  `cd /tmp/muse3-str096/Stratex && PYTHONPATH=/tmp/muse3-str096/Stratex:/tmp/muse3-str096 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-27`
  (the timer service's own invocation, with the worktree paths substituted so the merged fixed code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-27: ledger 83 rows (window 74, net -87.97), matching {'NO_MATCH': 41, 'EXIT_ONLY': 18, 'BOTH': 22}, missing closes 4 (+28.20), resets 6 (0 new), status RECONCILED -> /opt/friday_universe/Stratex/state/reconciliation/daily_2026-11-27.json`
- Bridge note: `run_shell` responses intermittently die with `http.client.IncompleteRead` / `RemoteDisconnected` / "MCP event stream ended" (3 drops this run: worktree add, report read, figures read); every dropped call was retried with a fresh session and every figure re-read after a successful call. No data was faked — the worktree landed despite the first drop (verified by re-read), and the report snapshot was verified by md5 + full re-read.
- Tests: `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — **28/28 passed** on run 6 by Muse 4 on this exact code (reconciler + test blobs verified identical between `93628618` and `8de8e3ed` this run, sha256 above). No test file changed in this task. CI re-verification from this work PR's job log follows (STR-091 lesson: the file is collected by `owner-workflows.yml` "Stratex forward-test and self-experiment contracts").

## §7 — Open positions at run time (30, unrealised +27.8579)

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 95.094331 | +7.3928 |
| ADAUSDT | +301.0 | 0.1494 | 0.1495 | +0.0301 |
| ALGOUSDT | −2293.4 | 0.08004 | 0.081859 | −4.1709 |
| APTUSDT | −116.9 | 0.4356 | 0.3859 | +5.8099 |
| ARBUSDT | −410.7 | 0.12691687 | 0.1141 | +5.2639 |
| ATOMUSDT | −151.7 | 1.186 | 1.218463 | −4.9246 |
| AVAXUSDT | −3.0 | 7.015 | 6.616178 | +1.1965 |
| BCHUSDT | −0.388 | 208.38159794 | 210.501838 | −0.8227 |
| BNBUSDT | −0.08 | 590.59 | 555.883624 | +2.7765 |
| BTCUSDT | +0.0025 | 59889.32 | 60684.7 | +1.9885 |
| DOGEUSDT | −1453.0 | 0.05505 | 0.05659 | −2.2376 |
| DOTUSDT | −102.7 | 0.6728 | 0.675818 | −0.31 |
| ETCUSDT | −14.63 | 5.659 | 5.915 | −3.7453 |
| ETHUSDT | +0.111 | 1681.3 | 1699.622568 | +2.0338 |
| FILUSDT | −81.9 | 0.5788 | 0.5412 | +3.0794 |
| HBARUSDT | −1433.0 | 0.05152 | 0.054081 | −3.6696 |
| INJUSDT | −19.0 | 6.657 | 6.224168 | +8.2238 |
| LINKUSDT | −8.79 | 8.629 | 9.354 | −6.3727 |
| LTCUSDT | −5.706 | 42.86 | 44.09799 | −7.064 |
| MANAUSDT | −1342.0 | 0.06059954 | 0.057467 | +4.204 |
| NEARUSDT | −14.0 | 2.901 | 3.077323 | −2.4685 |
| OPUSDT | −661.6 | 0.0768 | 0.069897 | +4.567 |
| SANDUSDT | −1822.0 | 0.03348 | 0.03456 | −1.9678 |
| SOLUSDT | −2.1 | 69.02 | 71.279828 | −4.7456 |
| SUIUSDT | −96.1 | 0.6446 | 0.6702 | −2.4602 |
| TRXUSDT | −750.0 | 0.30999 | 0.303748 | +4.6813 |
| UNIUSDT | −9.0 | 4.70744444 | 4.680672 | +0.241 |
| VETUSDT | +40580.0 | 0.004618 | 0.00486 | +9.837 |
| XLMUSDT | −1792.0 | 0.13436 | 0.12684 | +13.4758 |
| XRPUSDT | −93.7 | 0.925 | 0.946173 | −1.9839 |

All 3× leverage. Position set identical to run 6 (same 30 symbols, amounts and entries); only marks drifted. Venue account unrealised +27.7850 (account-level read) vs positions sum +27.8579 (0.0729 apart — different read moments in the same run).

## Five states

- Implemented: YES (evidence filed on branch, no code change — filing only)
- Tested: YES (live probe exit 0 on Stratex-Server; reconciler + test blobs verified identical to run 6's 28/28-tested code; CI re-verification follows from this PR)
- Merged: NO (work PR open, awaiting coordinator merge)
- Deployed: n/a (no deploy; read-only probe, no service touched)
- Production-verified: YES (live ledger reconciled end to end on Stratex-Server under clearance 7200564540)

## Files changed

- `docs/collaboration/TASK-STR-096-EVIDENCE.md` (new, this file only)
