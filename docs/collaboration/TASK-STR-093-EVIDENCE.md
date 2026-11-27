# TASK-STR-093 — Forward-window fill/close ledger state filing run 4 (evidence)

- **Task:** Stratex: forward-window fill/close ledger state filing run 4 — reconcile daemon ledger vs venue positions/history.
- **Owner:** Muse TP13. **Claim:** hub #1483 comment 7197190892, 2026-11-26 ~21:36 IST, on coordinator ruling in WATCH171 (hub 7197061449) — TASK-STR-093 re-slotted Muse 4 → Muse TP13 per the owner rule (no PR/hub activity for 1h → re-slot).
- **Board verified:** CLAIMED, owner muse_tp13, branch `musetp13/task-str-093-forward-window-fill-ledger-run4`, on live main `b74efa00` (board blob `d192a3f8`, read first-hand this run). Checkpoint 1 filed on the branch (`docs/collaboration/TASK-STR-093-CHECKPOINT-1.md`).
- **Branch:** `musetp13/task-str-093-forward-window-fill-ledger-run4` from main `0c89b38b`; merged up to main `b74efa00` this run (no conflicts; checkpoint 1 preserved).
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `b74efa00`, blob `f12f5fca` — byte-identical to the claim-base copy verified in checkpoint 1 and to the code run 2 used) run live on Stratex-Server (server 4) from a fresh worktree `/tmp/musetp13-str093` at `b74efa00`. Daemon venv python 3.10.22. Run at 2026-11-26T18:36:47Z / 2026-11-27 00:06:47 IST, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-26.json` on server 4 (overwrites the run-2 report for the same date; run 2's report is preserved in `/tmp/musetp13-str093-before.json` on server 4). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/musetp13-str093/Stratex:/tmp/musetp13-str093` so the current-main code runs. Exact command in §8.
- **Grant:** the live leg ran under the settled run_shell grant — owner tap 18:25:56 IST in main chat ("Approve full run_shell for the worker chats", approval 7113152293 closed), coordinator correction 7197725825 (22:00 IST) + owner's burn order 7200414167 (~23:55 IST). The WATCH172/174/176 "not confirmed" hold is withdrawn/overridden; no live leg is held on that excuse.

## Verdict

**RECONCILED.** The forward-window fill/close ledger reconciles end to end against the venue: window identity residual **−1.6024 USDT** against a tolerance of 10.49 USDT; no matched row disagrees with the venue by more than $0.50. The residual is not a ledger error — it is exactly the 30 Nov-19 reset-wipe micro-closes (−1.6023) that aged out of the venue's ~7-day `userTrades`/`allOrders` window before run 2 (§7 of the run-2 evidence; unchanged this run). The ledger itself is unchanged except for one new close (see §1).

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-26T14:42:27Z last close)

| Figure | Run 4 (this run, 18:36 UTC) | Run 2 (08:16 UTC) |
|---|---|---|
| Ledger closes, all time | 83 rows | 82 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +117.9497 |
| Ledger closes in forward window | 74 rows | 73 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.9231 + OANDA USDJPY −0.0478) | −77.1101 |
| Ledger window fees | 3.3171 | 3.2388 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 39 rows −147.9099 | (none) 44 +254.9989; FORWARD_TEST 38 −137.0492 |
| Venue closes in window | 78 (74 ledger + 4 missing) | 77 (73 ledger + 4 missing) |
| Venue window true net P&L | −59.7759 | −48.9151 |
| Venue account at run time | wallet 10,452.81, margin 10,490.04, unrealised +37.23, available 9,466.40 USDT (USDT 4,933.84 + USDC 5,000 + BTC 0.01) | wallet 10,462.46, margin 10,505.89, unrealised +43.43, available 9,479.21 |
| Open positions at run time | 30, unrealised +37.3012 | 30, unrealised +43.4378 |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−58.0134**, COMMISSION **−9.6135**, FUNDING_FEE **+0.6774**, TRANSFER +15,000.03 | REALISED_PNL −47.231, COMMISSION −9.4632, FUNDING_FEE +0.6552, TRANSFER +15,000.03 |
| Income rows fetched | **1,122** (763 FUNDING_FEE, 269 COMMISSION, 84 REALIZED_PNL, 6 TRANSFER) | 1,090 (734 FUNDING_FEE, 267 COMMISSION, 83 REALIZED_PNL, 6 TRANSFER) |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` |

**Window identity (LEDGER-001 §6, whole post-reset period):** venue realised −58.0134 = ledger window net (Binance) −87.9231 + missing closes +28.195 + ledger window fees 3.3171 → expected −56.411, **residual −1.6024**, status RECONCILED. Last ledger row recorded 2026-11-26T14:42:27Z (ATOMUSDT −10.8607) — the only close since run 2; the daemon is otherwise quiet on closes while 30 positions stay open.

**The one new close since run 2:** ATOMUSDT, entry 2026-11-23T20:01:52Z, exit 2026-11-26T14:42:27Z, net **−10.8607069**, FORWARD_TEST, SL_TP_BROKER. Its net (−10.8607) equals the window-net change (−77.1101 → −87.9709) to 0.0001; its gross (−10.7824) equals the venue-realised change (−47.231 → −58.0134) to 0.0001; its fees (+0.0783) equal the window-fee change (3.2388 → 3.3171). The venue true net moved by exactly the same −10.8608 (−48.9151 → −59.7759). Every figure moves by exactly this one row.

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

Zero-net symbols are the Nov-19 reset-wiped rows (§5): their positions were wiped by the faucet reset and re-entered, so the ledger carries them at 0.0 with fallback exit times. Per-symbol nets were re-derived independently from the live ledger (`fill_ledger.jsonl`, exit_time ≥ forward-window start) and match the report exactly. Only ATOMUSDT moved vs run 2 (+10.0703 → −0.7904, the new close); every other symbol is identical to run 2.

## §3 — Fills and closes vs the venue

- **Ledger closes (74):** 25 of the 81 Binance rows match venue fills on both entry and exit legs (**BOTH**); 17 match the exit leg only (**EXIT_ONLY** — entry leg aged out of the venue's ~7-day window, §7); 39 match neither (**NO_MATCH**) — the 30 Nov-19 reset-wiped 0.0 rows (fallback exit times, match nothing by design) + 9 pre-window Nov-14 rows. No ENTRY_ONLY rows. **Diffs over $0.50: none.** Matched exit realised −84.6061 vs matched ledger net −87.9231 — the 3.3170 gap is exactly the ledger window fees (3.3171, 0.0001 rounding). The 2 OANDA USDJPY rows are not venue-matched (different venue) by design. 72/83 ledger rows carry no `order_id`; row-to-venue traceability rests on price/qty/time matching (G-trace).
- **Venue closes (78):** 74 are the ledger closes; **4 have no ledger row (+28.195 USDT realised)** — the known G1 gap, identical to run 2 (same 4 orders, same fill times):
  - ETHUSDT, order 16876077891, BUY 0.148, **+19.9399**, 2 fills, 2026-11-20T19:14:38Z
  - SUIUSDT, order 1100728824, BUY 304.4, **+30.5009**, 2026-11-21T06:16:08Z
  - VETUSDT, order 458616420, BUY 42,328, **−10.9206**, 2026-11-21T13:28:08Z
  - SANDUSDT, order 340506462, BUY 5,219, **−11.3252**, 2026-11-22T12:16:35Z
- **Venue fills:** 25 unmatched zero-realised fills (run 2: 34) — entry legs of the 30 open positions + breakeven/entries, visible, never silently dropped. The 9 that left vs run 2 are exactly the fills whose first-fill time falls in the Nov-19 08:16–18:36 UTC aging window (§7); the earliest remaining fill is 2026-11-19T20:00:47Z. The venue's 6 faucet-reset events of 2026-11-19T07:35Z (3× 0.01 + 5,000 USDT grants) are detected; 0 new resets this run.

## §4 — Rows outside the window (9, all 2026-11-14, correctly excluded)

Identical to run 2 (STR-091 §4): the ledger grew by exactly one in-window row since run 2, so the outside set is unchanged:

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

These predate the forward window (and the 2026-11-14T13:03:53Z owner reset); the ledger total +107.089 over 83 rows includes them, the window net −87.9709 does not.

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

## §6 — STR-090 live re-probe: still closed

STR-090 §5 left a live re-probe owed, closed by run 2 (§6 there) and re-confirmed by this run on the same merged code (blob `f12f5fca`, `_income_page` + `_INCOME_PAGE_LIMIT = 1000` verified present in the worktree):

| Figure | Run 2 (08:16 UTC) | This run (18:36 UTC) |
|---|---|---|
| Income rows returned by `income(RESET_MS)` | 1,090 (763 FUNDING_FEE, 267 COMMISSION, 83 REALIZED_PNL, 6 TRANSFER) | **1,122** (763 FUNDING_FEE, 269 COMMISSION, 84 REALIZED_PNL, 6 TRANSFER) |
| Funding total | +0.6552 | **+0.6774** — higher by +0.0222, the Nov 26 16:00 UTC settlement (last income row 2026-11-26T16:00:13Z) |
| Commission total | −9.4632 | **−9.6135** — lower by −0.1503, the new ATOM close's commission + funding-period commissions |
| Realised total | −47.231 | **−58.0134** — lower by −10.7824, exactly the new close's gross realised |
| Capped-fetch comparison | exactly 1,000 rows, cutoff 2026-11-25T08:00:00Z | n/a — the paginated fetch returns all 1,122 rows; no cap is hit |

**Independent cross-check (same method as run 2 §6):** a separate direct `income()` call on server 4 after the run returned 1,122 rows with totals identical to the report to 4 decimals (COMMISSION −9.6135, FUNDING_FEE +0.6774, TRANSFER +15,000.03, REALIZED_PNL −58.0134, window-filtered realised also −58.0134). The pagination fix is proven live a second time: the funding figure is unfrozen and growing with settlements, and the income figures match full re-derivation.

## §7 — The BOTH → EXIT_ONLY shift: venue ~7-day retention, boundary moved

Run 2 matching was BOTH 41 / NO_MATCH 39 (no ENTRY_ONLY/EXIT_ONLY). Run 4 is BOTH 25 / EXIT_ONLY 17 / NO_MATCH 39. This is a venue-data effect, not a ledger change — the ledger grew by exactly one row (§1), and the identity residual is unchanged (−1.6025 → −1.6024, rounding):

- The reconciler matches each ledger row's entry and exit legs against venue fills (`userTrades`/`allOrders`, limit 1000, no `startTime`). EXIT_ONLY means the exit fill is still returned but the entry fill is not.
- The venue returns roughly the last 7 days of trades. Between run 2 (08:16 UTC) and run 4 (18:36 UTC) the retention boundary moved ~10h20m, from ~Nov 19 08:16 UTC to ~Nov 19 18:36 UTC. The earliest fill still returned moved from 2026-11-19T09:49:23Z (run 2) to 2026-11-19T20:00:47Z (run 4).
- Exactly **17 ledger rows** have entry times in the moved window (Nov 19 08:16:36 → 18:36:47 UTC) — the post-reset re-entries of Nov 19 09:57–16:01 UTC (SOL, XRP, DOGE, ADA, LINK, NEAR, ETC, SUI, SAND, ATOM, ALGO, BTC, ETH, DOT, AVAX, HBAR, UNI). Their exit legs (Nov 19 21:16 → Nov 21 04:05) are still inside the window, so they land EXIT_ONLY. 41 − 17 + 1 (the new ATOM close, entry Nov 23, still inside) = 25 BOTH; 0 + 17 = 17 EXIT_ONLY. The arithmetic closes exactly.
- The same move explains the unmatched-zero fills: 34 → 25, exactly the 9 fills whose first-fill time falls in the same Nov-19 08:16–18:36 window.
- The missing-close list is unaffected (the 4 G1 orders are Nov 20–22 exits, still inside the window), and the residual is unaffected (the identity uses income + ledger + missing, not the match classes).
- **Consequence for future runs:** BOTH will keep shrinking as entry legs age out — run 5+ will show fewer BOTH rows for the same ledger. The verdict rests on the window identity, not the match counts. Persisting venue trades (or a `startTime`-bounded fetch from a stored floor) would be a separate fix task; not attempted here — this task files the state, it does not change the job.

## §8 — Run record (commands, all read-only on the venue)

- **HOST CORRECTION (read first):** the live Stratex host is **Stratex-Server (server 4, hostname `stratex-server`)**. The STR-091 evidence doc's intro says "server 4" but its §8 labels the host "S1" throughout — those labels are wrong. Verified first-hand this run: server 4 holds the live daemon (`Stratex-Daemon.service` active running, pid 13273, heartbeat `RUNNING` 2026-11-26T18:36:05Z, 30 open positions), the 83-row ledger (last close Nov 26 14:42 UTC), the `friday-stratex-reconciliation.timer` (last Thu 2026-11-26 01:00:19 UTC, next Fri 2026-11-27 01:00:00 UTC), the git checkout on main `3db55adf`, and daemon venv python 3.10.22 — every one of these matches the STR-091 §8 record, and none of them matches Oracle Server 1. Oracle Server 1 holds a **stale copy**: 80-row ledger (last close Nov 23 19:40 UTC), its own 01:00 IST timer, checkout `28cc4ecb` (ahead 9), python 3.10.12, and a `daily_2026-11-26.json` written by the STR-090 probe (run_at 02:18:54 UTC), not by run 2. **Flagged to Muse on the hub (one line): the S1 timer fires daily against the stale ledger — it needs a ruling (stop it or sync S1) before run 5. Run 5 must use server 4, as this run did.** The daemon service was not touched; no service was restarted, no env file changed.
- Server 4 checkout: main `3db55adf` (predates the STR-090 merge `250cf2b4`); timer `friday-stratex-reconciliation.timer` enabled, last 2026-11-26 01:00:19 UTC, next 2026-11-27 01:00:00 UTC. The timer's 01:00 UTC report for 2026-11-26 was overwritten by run 2 at 08:16 UTC; run 2's report is preserved at `/tmp/musetp13-str093-before.json` on server 4.
- Worktree: `git fetch origin main` (703965cc..b74efa00) + `git worktree add /tmp/musetp13-str093 origin/main` on server 4. The live checkout, the daemon service, and the timer were not touched; no service was restarted, no env file changed.
- Run (backgrounded, log `/tmp/musetp13-str093-run.log` on server 4):
  `cd /tmp/musetp13-str093/Stratex && PYTHONPATH=/tmp/musetp13-str093/Stratex:/tmp/musetp13-str093 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-26`
  (the timer service's own invocation, with the worktree paths substituted so the current-main code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-26: ledger 83 rows (window 74, net -87.97), matching {'NO_MATCH': 39, 'EXIT_ONLY': 17, 'BOTH': 25}, missing closes 4 (+28.20), resets 6 (0 new), status RECONCILED -> /opt/friday_universe/Stratex/state/reconciliation/daily_2026-11-26.json`
- Tests: `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — **28/28 passed** (pytest, 3.35s, `PYTHONPATH=/tmp/musetp13-str093/Stratex`), incl. the 4 STR-090 pagination tests; no test file changed in this task. CI re-verification from the work PR's job log follows (FUT-030 lesson: the file is collected by `owner-workflows.yml` "Stratex forward-test and self-experiment contracts").

## §9 — Open positions at run time (30, unrealised +37.3012)

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 93.75822001 | +8.0609 |
| ADAUSDT | +301.0 | 0.1494 | 0.15005319 | +0.1966 |
| ALGOUSDT | −2,293.4 | 0.08004 | 0.08018023 | −0.3216 |
| APTUSDT | −116.9 | 0.4356 | 0.38883272 | +5.4671 |
| ARBUSDT | −410.7 | 0.12691687 | 0.1137 | +5.4282 |
| ATOMUSDT | −151.7 | 1.186 | 1.20597381 | −3.0300 |
| AVAXUSDT | −3.0 | 7.015 | 6.638 | +1.1310 |
| BCHUSDT | −0.388 | 208.38159794 | 209.06 | −0.2632 |
| BNBUSDT | −0.08 | 590.59 | 553.94 | +2.9320 |
| BTCUSDT | +0.0025 | 59,889.32 | 60,596.0 | +1.7667 |
| DOGEUSDT | −1,453.0 | 0.05505 | 0.05702618 | −2.8714 |
| DOTUSDT | −102.7 | 0.6728 | 0.6751805 | −0.2445 |
| ETCUSDT | −14.63 | 5.659 | 5.95854279 | −4.3823 |
| ETHUSDT | +0.111 | 1,681.3 | 1,699.24579457 | +1.9920 |
| FILUSDT | −81.9 | 0.5788 | 0.54904564 | +2.4369 |
| HBARUSDT | −1,433.0 | 0.05152 | 0.05461836 | −4.4399 |
| INJUSDT | −19.0 | 6.657 | 6.18176936 | +9.0294 |
| LINKUSDT | −8.79 | 8.629 | 9.251 | −5.4674 |
| LTCUSDT | −5.706 | 42.86 | 43.36 | −2.8530 |
| MANAUSDT | −1,342.0 | 0.06059954 | 0.0577 | +3.8912 |
| NEARUSDT | −14.0 | 2.901 | 3.087 | −2.6040 |
| OPUSDT | −661.6 | 0.0768 | 0.06991173 | +4.5573 |
| SANDUSDT | −1,822.0 | 0.03348 | 0.03432 | −1.5305 |
| SOLUSDT | −2.1 | 69.02 | 71.25060975 | −4.6843 |
| SUIUSDT | −96.1 | 0.6446 | 0.6693346 | −2.3770 |
| TRXUSDT | −750.0 | 0.30999 | 0.30323 | +5.0700 |
| UNIUSDT | −9.0 | 4.70744444 | 4.64325389 | +0.5777 |
| VETUSDT | +40,580.0 | 0.004618 | 0.00487896 | +10.5898 |
| XLMUSDT | −1,792.0 | 0.13436 | 0.12764302 | +12.0368 |
| XRPUSDT | −93.7 | 0.925 | 0.95480952 | −2.7932 |

All 3× leverage. Venue account unrealised +37.2322 (account-level read) vs positions sum +37.3012 (0.069 apart — different read moments in the same run).

## Files changed

- `docs/collaboration/TASK-STR-093-EVIDENCE.md` — this doc.
- `docs/collaboration/WORK_BOARD.yaml` — board flip only: TASK-STR-093 CLAIMED → IN_REVIEW, branch + pr set (built from a fresh main board read at PR time; verified by full-file diff that only the STR-093 record changed).
- No code changed — the reconciler is the merged STR-044 job + STR-090 fix; this task runs it and files the state.

## States

- **implemented:** YES — live reconciliation run + state filed as evidence (no code change required; the job already exists merged).
- **tested:** YES — 28/28 reconciler tests pass on the exact PR-head code; live run exit 0, report filed, errors `[]`. CI log re-verification follows after the work PR opens.
- **merged:** NO — work PR open for review (merge by Muse, never my own PR).
- **deployed:** N/A — the job is already deployed (STR-044 timer on server 4); the report was filed on server 4 by this run. No service change in this PR.
- **production-verified:** YES — live run on Stratex-Server against the demo venue, RECONCILED, report filed; STR-090 live re-probe closed again (§6). Paired verification (owner order rule 3) is owed — no verifier was named for this task; Muse to name one.

— Muse TP13, 2026-11-27 ~00:25 IST (run 2026-11-26T18:36:47Z)
