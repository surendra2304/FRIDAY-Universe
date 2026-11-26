# TASK-STR-094 — Forward-window fill/close ledger state filing run 5 (evidence)

- **Task:** Stratex: forward-window fill/close ledger state filing run 5 — reconcile daemon ledger vs venue positions/history after STR-092/STR-093.
- **Owner:** Muse 4. **Claim:** hub #1483 comment 7201093827, 2026-11-27 ~00:30 IST, on coordinator direction in the WATCH177 follow-up (hub 7200280447, ~23:48 IST): skip blocked head EARN-030 (owner-gated: owner creates the Contra account first) to STR-094 per the blocked-head rule. Queue: EARN-030 (head, gated) → STR-094 (in flight) → STR-095 (position 3).
- **Board verified:** AVAILABLE, owner muse_4, branch null, pr null, on live main `93628618` (board blob `1458faa9f2`, read via git blob API before editing). No prior claim, branch or PR for this run.
- **Branch:** `muse4/task-str-094-forward-window-fill-ledger-run5` from main `93628618` (rebased from `6182a9f3` after PRs #1998/#2009/#2015 merged; no content change — the reconciler and its tests are blob-identical between the two mains).
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `6182a9f3`, incl. the STR-090 income-pagination fix) run live on Stratex-Server (server 4) from a fresh worktree `/tmp/muse4-str094` at `6182a9f3` (the live checkout is on main `3db55adf`, which predates the STR-090 merge — the worktree, not the live checkout, supplies the fixed code; the live checkout and the daemon were not touched). Daemon venv python 3.10.22. Run at 2026-11-26T19:18:32Z / 2026-11-27 00:48:32 IST, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-27.json` on Stratex-Server. State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/muse4-str094/Stratex:/tmp/muse4-str094` so the fixed code runs. Exact command in §8.
- **Host note (new finding):** the Oracle Server 1 copy of the Stratex state dir is a **frozen pre-migration copy** — ledger 80 rows, mtime 2026-11-24 01:10 IST, its `daily_2026-11-26.json` is the STR-090 probe's report (run 2026-11-26 02:18:54Z), and its `Stratex.service` is inactive. The live state is on Stratex-Server: ledger 83 rows, daemon active, last close 2026-11-26T14:42:27Z. This run used Stratex-Server (server 4), as STR-091 did. Do not re-run against the S1 copy — it would reconcile a stale ledger.

## Verdict

**RECONCILED.** The forward-window fill/close ledger reconciles end to end against the venue: window identity residual **−1.6024 USDT** against a tolerance of 10.48 USDT; no matched row disagrees with the venue by more than $0.50. The residual is unchanged since run 2 — it is exactly the aged-out Nov-19 reset-wipe micro-closes (−1.6023) that sit outside the venue's ~7-day `userTrades`/`allOrders` window (§7). The ledger itself is unchanged between run 4 and this run.

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-26T14:42:27Z last close)

| Figure | Run 5 (this run, 19:18 UTC) | Run 4 (18:36 UTC, same host) |
|---|---|---|
| Ledger closes, all time | 83 rows | 83 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 |
| Ledger closes in forward window | 74 rows | 74 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.923 + OANDA USDJPY −0.0478) | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 39 rows −147.9099 | same |
| Venue closes in window | 78 (74 ledger + 4 missing) | 78 (74 ledger + 4 missing) |
| Venue window true net P&L | −59.7759 | −59.7759 |
| Venue account at run time | wallet 10,452.32, margin 10,483.60, unrealised +31.28, available 9,458.11 USDT (USDT 4,933.84 + USDC 5,000 + BTC 0.01) | wallet 10,452.81, margin 10,490.04, unrealised +37.23, available 9,466.40 |
| Open positions at run time | 30, unrealised +31.2739 | 30, unrealised +37.3012 |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−58.0134**, COMMISSION **−9.6135**, FUNDING_FEE **+0.6774**, TRANSFER +15,000.03 | identical |
| Income rows fetched | **1,122** (763 FUNDING_FEE, 269 COMMISSION, 84 REALIZED_PNL, 6 TRANSFER) | totals identical (row count not re-read) |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` |

Change since run 2 (STR-091, 2026-11-26 13:46 IST): ledger 82 → 83 rows (one new close, ATOMUSDT 2026-11-26T14:42:27Z, −10.8607); window 73 → 74 rows; window net −77.1101 → −87.9709 (the new close −10.8607 accounts for the move); venue realised −47.231 → −58.0134 (further closes settled on the venue between the runs). The only run-4 → run-5 movement is mark-price drift on the 30 open positions (unrealised +37.30 → +31.27).

## §2 — Net P&L by symbol (window, 74 closes)

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

Zero-net symbols are the Nov-19 reset-wiped rows (§5): their positions were wiped by the faucet reset and re-entered, so the ledger carries them at 0.0 with fallback exit times. Per-symbol nets were re-derived independently from the live ledger (`fill_ledger.jsonl`, exit_time ≥ forward-window start) and match the report exactly. ATOMUSDT moved +10.0703 (run 2) → −0.7904: the single new close since run 2 (2026-11-26T14:42:27Z, −10.8607).

## §3 — Fills and closes vs the venue

- **Ledger closes (74):** 25 of the 81 Binance rows match venue fills on both entry and exit legs (**BOTH**); 17 match on the exit leg only (**EXIT_ONLY** — §7); 39 match neither (**NO_MATCH**) — the 30 Nov-19 reset-wiped 0.0 rows (fallback exit times, match nothing by design) + 9 pre-window Nov-14 rows. No ENTRY_ONLY rows. **Diffs over $0.50: none.** Matched exit realised −84.6061 vs matched ledger net −87.9231 — the 3.3170 gap is exactly the ledger window fees (3.3171, rounding). The 2 OANDA USDJPY rows are not venue-matched (different venue) by design. 72/83 ledger rows carry no `order_id`; row-to-venue traceability rests on price/qty/time matching (G-trace).
- **Venue closes (78):** 74 are the ledger closes; **4 have no ledger row (+28.195 USDT realised)** — the known G1 gap, unchanged since run 2:
  - ETHUSDT, order 16876077891, BUY 0.148, **+19.9399**, 2 fills, 2026-11-20T19:14:38Z
  - SUIUSDT, order 1100728824, BUY 304.4, **+30.5009**, 1 fill, 2026-11-21T06:16:08Z
  - VETUSDT, order 458616420, BUY 42,328, **−10.9206**, 1 fill, 2026-11-21T13:28:08Z
  - SANDUSDT, order 340506462, BUY 5,219, **−11.3252**, 1 fill, 2026-11-22T12:16:35Z
- **Venue fills:** 25 unmatched zero-realised fills (entry legs of the open positions + breakeven entries — visible, never silently dropped). The venue's 6 faucet-reset events of 2026-11-19T07:35Z (3× 0.01 + 5,000 USDT grants) are detected; 0 new resets this run.
- **Identity check (re-derived):** ledger window net (Binance) −87.9231 + missing closes +28.195 + window fees 3.3171 = expected venue realised −56.411; venue realised −58.0134; residual −1.6024, inside tolerance 10.48. Venue true net −59.7759 = ledger window net −87.9709 + missing +28.195.

## §4 — Rows outside the window (9, all 2026-11-14, correctly excluded)

Same 9 rows as run 2 (STR-091 §4) — unchanged; the ledger grew only with the one Nov-26 in-window row, so the outside set is unchanged:

| Symbol | Exit (UTC) | Net | Reason |
|---|---|---|---|
| SOLUSDT | 2026-11-14T12:10:49Z | −33.6354 | OWNER_DIRECTED_CLOSE |
| UNIUSDT | 2026-11-14T12:10:52Z | +229.6280 | OWNER_DIRECTED_CLOSE |
| PAXGUSDT | 2026-11-14T12:10:54Z | −0.2860 | OWNER_DIRECTED_CLOSE |
| LTCUSDT | 2026-11-14T13:01:13Z | +0.5437 | WIN |
| ETHUSDT | 2026-11-14T13:26:01Z | +0.6818 | WIN |
| DOTUSDT | 2026-11-14T14:02:28Z | +0.0302 | WIN |
| XRPUSDT | 2026-11-14T14:46:57Z | −0.0141 | WIN |
| BTCUSDT | 2026-11-14T16:47:23Z | −0.6396 | LOSS |
| BTCUSDT | 2026-11-14T21:03:38Z | −1.2488 | LOSS |

These predate the forward window (and the 2026-11-14T13:03:53Z owner reset). Verified: all-time per-symbol nets minus window nets equal exactly these 9 rows (e.g. UNI 239.7824 − 10.1544 = 229.6280).

## §5 — All 74 window closes (ledger, exit time UTC, net USDT, reason)

| Symbol | Exit (UTC) | Net | Reason |
|---|---|---|---|
| USDJPY | 2026-11-16T13:08:45Z | 0.0000 | BROKER_CLOSE |
| USDJPY | 2026-11-17T08:35:06Z | −0.0478 | VENUE_CLOSE_CORRECTION |
| TRXUSDT | 2026-11-19T07:36:39Z | 0.0000 | SL_TP_BROKER |
| MANAUSDT | 2026-11-19T07:36:41Z | 0.0000 | SL_TP_BROKER |
| FILUSDT | 2026-11-19T07:36:44Z | 0.0000 | SL_TP_BROKER |
| DOTUSDT | 2026-11-19T07:36:47Z | 0.0000 | SL_TP_BROKER |
| ETHUSDT | 2026-11-19T07:36:49Z | 0.0000 | SL_TP_BROKER |
| SUIUSDT | 2026-11-19T07:36:51Z | 0.0000 | SL_TP_BROKER |
| BCHUSDT | 2026-11-19T07:36:53Z | 0.0000 | SL_TP_BROKER |
| INJUSDT | 2026-11-19T07:36:55Z | 0.0000 | SL_TP_BROKER |
| ETCUSDT | 2026-11-19T07:36:58Z | 0.0000 | SL_TP_BROKER |
| LTCUSDT | 2026-11-19T07:37:00Z | 0.0000 | SL_TP_BROKER |
| ATOMUSDT | 2026-11-19T07:37:02Z | 0.0000 | SL_TP_BROKER |
| XRPUSDT | 2026-11-19T07:37:05Z | 0.0000 | SL_TP_BROKER |
| LINKUSDT | 2026-11-19T07:37:07Z | 0.0000 | SL_TP_BROKER |
| VETUSDT | 2026-11-19T07:37:10Z | 0.0000 | SL_TP_BROKER |
| NEARUSDT | 2026-11-19T07:37:12Z | 0.0000 | SL_TP_BROKER |
| AAVEUSDT | 2026-11-19T07:37:15Z | 0.0000 | SL_TP_BROKER |
| BTCUSDT | 2026-11-19T07:37:17Z | 0.0000 | SL_TP_BROKER |
| SOLUSDT | 2026-11-19T07:37:19Z | 0.0000 | SL_TP_BROKER |
| APTUSDT | 2026-11-19T07:37:21Z | 0.0000 | SL_TP_BROKER |
| AVAXUSDT | 2026-11-19T07:37:23Z | 0.0000 | SL_TP_BROKER |
| UNIUSDT | 2026-11-19T07:37:25Z | 0.0000 | SL_TP_BROKER |
| BNBUSDT | 2026-11-19T07:37:28Z | 0.0000 | SL_TP_BROKER |
| DOGEUSDT | 2026-11-19T07:37:30Z | 0.0000 | SL_TP_BROKER |
| XLMUSDT | 2026-11-19T07:37:31Z | 0.0000 | SL_TP_BROKER |
| OPUSDT | 2026-11-19T07:37:33Z | 0.0000 | SL_TP_BROKER |
| HBARUSDT | 2026-11-19T07:37:35Z | 0.0000 | SL_TP_BROKER |
| ALGOUSDT | 2026-11-19T07:37:37Z | 0.0000 | SL_TP_BROKER |
| ADAUSDT | 2026-11-19T07:37:39Z | 0.0000 | SL_TP_BROKER |
| SANDUSDT | 2026-11-19T07:37:40Z | 0.0000 | SL_TP_BROKER |
| ARBUSDT | 2026-11-19T07:37:42Z | 0.0000 | SL_TP_BROKER |
| BTCUSDT | 2026-11-19T21:16:49Z | −10.0709 | SL_TP_BROKER |
| NEARUSDT | 2026-11-19T22:12:27Z | −10.6754 | SL_TP_BROKER |
| ETHUSDT | 2026-11-20T01:59:07Z | −10.2055 | SL_TP_BROKER |
| ETCUSDT | 2026-11-20T01:59:09Z | −10.1619 | SL_TP_BROKER |
| LINKUSDT | 2026-11-20T01:59:10Z | −10.9556 | SL_TP_BROKER |
| DOGEUSDT | 2026-11-20T02:26:00Z | −10.2061 | SL_TP_BROKER |
| SUIUSDT | 2026-11-20T02:32:22Z | −10.6613 | SL_TP_BROKER |
| SANDUSDT | 2026-11-20T04:38:30Z | −10.8371 | SL_TP_BROKER |
| ADAUSDT | 2026-11-20T12:08:45Z | −10.4336 | SL_TP_BROKER |
| SOLUSDT | 2026-11-20T13:33:45Z | −10.7553 | SL_TP_BROKER |
| AVAXUSDT | 2026-11-20T13:36:04Z | −10.5510 | SL_TP_BROKER |
| DOTUSDT | 2026-11-20T15:24:30Z | +20.4903 | SL_TP_BROKER |
| ATOMUSDT | 2026-11-20T15:48:18Z | +20.6429 | SL_TP_BROKER |
| ALGOUSDT | 2026-11-20T17:40:11Z | +19.2393 | SL_TP_BROKER |
| NEARUSDT | 2026-11-21T03:05:40Z | +20.5298 | SL_TP_BROKER |
| HBARUSDT | 2026-11-21T03:30:42Z | +20.8414 | SL_TP_BROKER |
| SANDUSDT | 2026-11-21T03:32:15Z | +21.0313 | SL_TP_BROKER |
| DOGEUSDT | 2026-11-21T03:32:59Z | +15.7029 | SL_TP_BROKER |
| XRPUSDT | 2026-11-21T03:33:34Z | −10.8180 | SL_TP_BROKER |
| VETUSDT | 2026-11-21T03:34:37Z | +20.2573 | SL_TP_BROKER |
| BTCUSDT | 2026-11-21T04:05:09Z | +28.4841 | SL_TP_BROKER |
| UNIUSDT | 2026-11-21T04:05:10Z | +20.4999 | SL_TP_BROKER |
| LINKUSDT | 2026-11-21T04:06:36Z | +20.8566 | SL_TP_BROKER |
| SUIUSDT | 2026-11-21T13:08:02Z | −3.4019 | SL_TP_BROKER |
| BTCUSDT | 2026-11-21T13:25:12Z | −10.3340 | SL_TP_BROKER |
| ETHUSDT | 2026-11-21T13:36:31Z | −10.1812 | SL_TP_BROKER |
| LINKUSDT | 2026-11-21T13:36:32Z | −8.0591 | SL_TP_BROKER |
| UNIUSDT | 2026-11-21T13:36:34Z | −10.3455 | SL_TP_BROKER |
| DOGEUSDT | 2026-11-21T13:38:35Z | −10.7883 | SL_TP_BROKER |
| HBARUSDT | 2026-11-21T13:39:21Z | −10.8238 | SL_TP_BROKER |
| XRPUSDT | 2026-11-21T13:49:41Z | −10.7259 | SL_TP_BROKER |
| NEARUSDT | 2026-11-21T13:52:33Z | −10.7590 | SL_TP_BROKER |
| SOLUSDT | 2026-11-23T09:05:57Z | −10.7238 | SL_TP_BROKER |
| ALGOUSDT | 2026-11-23T11:59:12Z | −10.6229 | SL_TP_BROKER |
| AVAXUSDT | 2026-11-23T13:57:01Z | −10.0548 | SL_TP_BROKER |
| ADAUSDT | 2026-11-23T13:58:24Z | −10.1994 | SL_TP_BROKER |
| DOTUSDT | 2026-11-23T14:00:33Z | −9.5518 | SL_TP_BROKER |
| ATOMUSDT | 2026-11-23T14:17:24Z | −10.5726 | SL_TP_BROKER |
| ADAUSDT | 2026-11-23T19:40:06Z | −11.3614 | SL_TP_BROKER |
| ALGOUSDT | 2026-11-24T09:12:14Z | −10.7439 | SL_TP_BROKER |
| SOLUSDT | 2026-11-24T15:17:23Z | −10.0571 | SL_TP_BROKER |
| ATOMUSDT | 2026-11-26T14:42:27Z | −10.8607 | SL_TP_BROKER |

## §6 — Funding cross-check: STR-090 pagination fix holds live

An independent direct `income()` call on Stratex-Server (same `DemoFuturesReader`, same env file, separate process from the reconciler run) returned **1,122 income rows** since the reset floor — 763 FUNDING_FEE, 269 COMMISSION, 84 REALIZED_PNL, 6 TRANSFER — with totals **FUNDING_FEE +0.6774, COMMISSION −9.6135, REALIZED_PNL −58.0134, TRANSFER +15,000.03**, exactly matching the report's `income_since_reset`. The 1,000-row venue cap is paginated past (1,122 > 1,000); funding is unfrozen and growing with settlements (+0.6552 at run 2 → +0.6774 now).

## §7 — The BOTH → EXIT_ONLY shift: entry fills aged out of the venue window

Run 2 matched 41 rows on both legs and 0 on the exit leg only. Runs 4 and 5 both match 25 BOTH + 17 EXIT_ONLY (NO_MATCH steady at 39). The 17 EXIT_ONLY rows are the older non-zero closes whose **entry** fills have aged out of the venue's ~7-day `userTrades`/`allOrders` window between run 2 and run 4; the exit legs still match, and the matched totals still tie out exactly (exit realised −84.6061 vs ledger net −87.9231 = window fees 3.3171). This is the same retention effect STR-091 §7 documented for exit fills — now visible on the entry side as the Nov 19–21 closes cross the 7-day boundary. Nothing was lost: the ledger rows, the exit fills, and the realised P&L are all still present and reconciled. The G1 gap (4 missing closes, +28.20) is unchanged since run 2.

## §8 — Run record (commands, all read-only on the venue)

- Live checkout on Stratex-Server: main `3db55adf` (predates the STR-090 merge `250cf2b4`); `Stratex.service` **active**; `friday-stratex-reconciliation.timer` next 2026-11-27 01:00:00 UTC (its code is the stale checkout, so its report will show the frozen funding figure again — the evidence doc is the filing of record for this run). The timer's report for this date will overwrite `daily_2026-11-27.json` at 01:00 UTC; all figures are preserved here.
- Worktree: `git fetch origin main` (b74efa00..6182a9f3) + `git worktree add /tmp/muse4-str094 origin/main` on Stratex-Server. The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- Run (backgrounded, log `/tmp/muse4-str094-run.log` on Stratex-Server):
  `cd /tmp/muse4-str094/Stratex && PYTHONPATH=/tmp/muse4-str094/Stratex:/tmp/muse4-str094 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-27`
  (the timer service's own invocation, with the worktree paths substituted so the merged fixed code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-27: ledger 83 rows (window 74, net -87.97), matching {'NO_MATCH': 39, 'EXIT_ONLY': 17, 'BOTH': 25}, missing closes 4 (+28.20), resets 6 (0 new), status RECONCILED -> /opt/friday_universe/Stratex/state/reconciliation/daily_2026-11-27.json`
- Funding cross-check (separate process, same reader): `/opt/friday_universe/venv/bin/python /tmp/muse4-str094-funding-probe.py` — 1,122 income rows, totals match the report exactly (§6).
- Tests: `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — **28/28 passed locally** (pytest 9.2.0, 0.44s, `PYTHONPATH=Stratex`) on the exact PR-head code (main `93628618`; also 28/28 on `6182a9f3`, the run's worktree base); no test file changed in this task. CI re-verification from the work PR's job log follows (STR-091 lesson: the file is collected by `owner-workflows.yml` "Stratex forward-test and self-experiment contracts").

## §9 — Open positions at run time (30, unrealised +31.2739)

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 94.74943564 | +7.5653 |
| ADAUSDT | +301.0 | 0.1494 | 0.15050104 | +0.3314 |
| ALGOUSDT | −2,293.4 | 0.08004 | 0.08041 | −0.8486 |
| APTUSDT | −116.9 | 0.4356 | 0.3888 | +5.4709 |
| ARBUSDT | −410.7 | 0.12691687 | 0.1141 | +5.2639 |
| ATOMUSDT | −151.7 | 1.186 | 1.208 | −3.3374 |
| AVAXUSDT | −3.0 | 7.015 | 6.656 | +1.0770 |
| BCHUSDT | −0.388 | 208.38159794 | 209.4 | −0.3951 |
| BNBUSDT | −0.08 | 590.59 | 554.62054573 | +2.8776 |
| BTCUSDT | +0.0025 | 59,889.32 | 60,527.3682971 | +1.5951 |
| DOGEUSDT | −1,453.0 | 0.05505 | 0.05707721 | −2.9455 |
| DOTUSDT | −102.7 | 0.6728 | 0.67548967 | −0.2762 |
| ETCUSDT | −14.63 | 5.659 | 5.957 | −4.3597 |
| ETHUSDT | +0.111 | 1,681.3 | 1,701.47770349 | +2.2397 |
| FILUSDT | −81.9 | 0.5788 | 0.5493 | +2.4160 |
| HBARUSDT | −1,433.0 | 0.05152 | 0.05455 | −4.3420 |
| INJUSDT | −19.0 | 6.657 | 6.257 | +7.6000 |
| LINKUSDT | −8.79 | 8.629 | 9.273 | −5.6608 |
| LTCUSDT | −5.706 | 42.86 | 43.46139706 | −3.4316 |
| MANAUSDT | −1,342.0 | 0.06059954 | 0.05778 | +3.7838 |
| NEARUSDT | −14.0 | 2.901 | 3.08898786 | −2.6318 |
| OPUSDT | −661.6 | 0.0768 | 0.07017383 | +4.3839 |
| SANDUSDT | −1,822.0 | 0.03348 | 0.03471 | −2.2411 |
| SOLUSDT | −2.1 | 69.02 | 71.33 | −4.8510 |
| SUIUSDT | −96.1 | 0.6446 | 0.67332822 | −2.7608 |
| TRXUSDT | −750.0 | 0.30999 | 0.30335 | +4.9800 |
| UNIUSDT | −9.0 | 4.70744444 | 4.67 | +0.3370 |
| VETUSDT | +40,580.0 | 0.004618 | 0.004867 | +10.1044 |
| XLMUSDT | −1,792.0 | 0.13436 | 0.12759568 | +12.1217 |
| XRPUSDT | −93.7 | 0.925 | 0.9548 | −2.7923 |

All 3× leverage. Venue account unrealised +31.2795 (account-level read) vs positions sum +31.2739 (0.0056 apart — different read moments in the same run). ATOMUSDT flipped since run 2 (+163.37 @ 1.264 → −151.7 @ 1.186): the old long closed (the new 2026-11-26T14:42:27Z ledger row, −10.8607) and a fresh short was opened.

## Files changed

- `docs/collaboration/TASK-STR-094-EVIDENCE.md` — this doc.
- `docs/collaboration/WORK_BOARD.yaml` — board flip only: TASK-STR-094 AVAILABLE → IN_REVIEW, branch + pr set (built from a fresh main board read at PR time; verified by full-file diff that only the STR-094 record changed).
- No code changed — the reconciler is the merged STR-044 job + STR-090 fix; this task runs it and files the state.

## States

- **implemented:** YES — live reconciliation run + state filed as evidence (no code change required; the job already exists merged).
- **tested:** YES — 28/28 reconciler tests pass locally on the exact PR-head code; live run exit 0, report filed, errors `[]`. CI log re-verification follows after the work PR opens.
- **merged:** NO — work PR open for review (merge by Muse, never my own PR).
- **deployed:** N/A — the job is already deployed (STR-044 timer on Stratex-Server); the report was filed on Stratex-Server by this run. No service change in this PR.
- **production-verified:** YES — live run on Stratex-Server against the demo venue, RECONCILED, report filed; funding cross-check independently confirmed (§6). Paired verification (owner order rule 3) is owed — no verifier was named for this task; Muse to name one.

— Muse 4
