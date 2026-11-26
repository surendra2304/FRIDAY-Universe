# TASK-STR-092 — Forward-window fill/close ledger state filing run 3 (evidence)

- **Task:** Stratex: forward-window fill/close ledger state filing run 3 — reconcile daemon ledger vs venue positions/history.
- **Owner:** Muse TP13. **Claim:** coordinator ruling WATCH185 §4c (hub #1483 comment 7203987740, 2026-11-27 ~03:15 IST) — MEM-028 released to the pool; STR-092 is TP13's next owned item, start now. Original assignment: coordinator watch180 reassigned TP9 → TP13 (board evidence); TP9 released it hub 7201046507 (~00:28 IST, no branch, no PR, no evidence filed). Checkpoint 1 filed on this branch (`docs/collaboration/TASK-STR-092-CHECKPOINT-1.md`).
- **Branch:** `musetp13/task-str-092-forward-window-fill-ledger-run3` from main `56ebae7d`.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519). Read-only throughout — signed GETs only; no order placed, cancelled or modified; the ledger was never written; no env flip (none needed, none made).
- **Method:** the merged STR-044 daily reconciler (`Stratex/scripts/daily_fill_ledger_reconciliation.py`, main `56ebae7d`, blob `f12f5fca` — byte-identical to the code runs 2/4 used) run live on Stratex-Server (server 4) from a fresh worktree `/tmp/musetp13-str092` at `56ebae7d`. Daemon venv python 3.10.22. Run at 2026-11-26T22:15:13Z / 2026-11-27 03:45:13 IST, exit 0, report filed at `Stratex/state/reconciliation/daily_2026-11-27.json` on server 4 (overwrites run 6's report for the same date; run 6's report is preserved in `/tmp/musetp13-str092-before.json` on server 4). State dir and env file are the live ones (`/opt/friday_universe/Stratex/state`, `/opt/friday_universe/Stratex/.env`); `PYTHONPATH=/tmp/musetp13-str092/Stratex:/tmp/musetp13-str092` so the current-main code runs. Exact command in §8.
- **Grant:** the live leg ran under standing clearance 7200564540 (board evidence for this task; WATCH185 §4a/§4b settled the run_shell grant dispute generally). No live leg is held.

## Verdict

**RECONCILED.** The forward-window fill/close ledger reconciles end to end against the venue: window identity residual **−1.6024 USDT** against a tolerance of 10.48 USDT; no matched row disagrees with the venue by more than $0.50. The residual is not a ledger error — it is exactly the 30 Nov-19 reset-wipe micro-closes (−1.6023) that aged out of the venue's `userTrades`/`allOrders` window before run 2 (§7 of the run-2 evidence; unchanged this run). The ledger itself is unchanged since run 4 — same 83 rows, same last close (ATOMUSDT, 2026-11-26T14:42:27Z); no new close since run 4.

## §1 — Window numbers (2026-11-15T11:29:49+05:30 → 2026-11-26T14:42:27Z last close)

| Figure | Run 3 (this run, 22:15 UTC) | Run 6 (22:05 UTC) | Run 4 (18:36 UTC) |
|---|---|---|---|
| Ledger closes, all time | 83 rows | 83 rows | 83 rows |
| Ledger net P&L (all time) | **+107.089** (gross +120.1326, fees 13.0436) | +107.089 | +107.089 |
| Ledger closes in forward window | 74 rows | 74 rows | 74 rows |
| Ledger window net P&L | **−87.9709** (Binance −87.9231 + OANDA USDJPY −0.0478) | −87.9709 | −87.9709 |
| Ledger window fees | 3.3171 | 3.3171 | 3.3171 |
| By lane | (none) 44 rows +254.9989; FORWARD_TEST 39 rows −147.9099 | same | same |
| Venue closes in window | 78 (74 ledger + 4 missing) | 78 | 78 |
| Venue window true net P&L | −59.7759 | −59.7759 | −59.7759 |
| Venue account at run time | wallet 10,452.99, margin 10,479.07, unrealised +26.08, available 9,452.21 USDT (USDT 4,933.84 + USDC 5,000 + BTC 0.01) | wallet 10,454.07, margin 10,476.57, unrealised +22.50, available 9,447.79 | wallet 10,452.81, margin 10,490.04, unrealised +37.23, available 9,466.40 |
| Open positions at run time | 30, unrealised +26.1043 | 30, unrealised +22.5665 | 30, unrealised +37.3012 |
| Venue income since the 2026-11-14 reset | REALISED_PNL **−58.0134**, COMMISSION **−9.6135**, FUNDING_FEE **+0.6774**, TRANSFER +15,000.03 | same | same |
| Income rows fetched | **1,122** (763 FUNDING_FEE, 269 COMMISSION, 84 REALIZED_PNL, 6 TRANSFER) | totals same (counts not in run-6 report) | 1,122 (same split) |
| Resets | 6 Nov-19 TRANSFER rows detected, 0 new | 6 detected, 0 new | 6 detected, 0 new |
| Errors | `[]` | `[]` | `[]` |

**Window identity (LEDGER-001 §6, whole post-reset period):** venue realised −58.0134 = ledger window net (Binance) −87.9231 + missing closes +28.195 + ledger window fees 3.3171 → expected −56.411, **residual −1.6024**, status RECONCILED. Last ledger row recorded 2026-11-26T14:42:27Z (ATOMUSDT −10.8607) — no close since run 4; the daemon is otherwise quiet on closes while 30 positions stay open.

## §2 — Net P&L by symbol (window, 74 closes)

Per-symbol nets re-derived independently from the live ledger (`fill_ledger.jsonl`, exit_time ≥ forward-window start) — identical to run 4 in every value, as the ledger is unchanged since run 4.

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

Zero-net symbols are the Nov-19 reset-wiped rows (§5): their positions were wiped by the faucet reset and re-entered, so the ledger carries them at 0.0 with fallback exit times. The 2 OANDA USDJPY rows are not venue-matched (different venue) by design.

## §3 — Fills and closes vs the venue

- **Ledger closes (74):** 24 of the 81 Binance rows match venue fills on both entry and exit legs (**BOTH**); 16 match the exit leg only (**EXIT_ONLY** — entry leg aged out of the venue's retention window, §7); 41 match neither (**NO_MATCH**) — the 30 Nov-19 reset-wiped 0.0 rows (fallback exit times, match nothing by design) + 9 pre-window Nov-14 rows + 2 rows whose exit legs aged out since run 4 (BTC Nov-19 21:16, NEAR Nov-19 22:12, §7). No ENTRY_ONLY rows. **Diffs over $0.50: none.** Matched exit realised −64.048 vs matched ledger net −67.1767 — the 3.1287 gap is exactly the fees of the 40 matched rows (run 4's 3.3170 less BTC fees 0.1338 + NEAR fees 0.0544 = 3.1287, §7). 72/83 ledger rows carry no `order_id`; row-to-venue traceability rests on price/qty/time matching (G-trace).
- **Venue closes (78):** 74 are the ledger closes; **4 have no ledger row (+28.195 USDT realised)** — the known G1 gap, identical to runs 2/4/6 (same 4 orders, same fill times):
  - ETHUSDT, order 16876077891, BUY 0.148, **+19.9399**, 2 fills, 2026-11-20T19:14:38Z
  - SUIUSDT, order 1100728824, BUY 304.4, **+30.5009**, 2026-11-21T06:16:08Z
  - VETUSDT, order 458616420, BUY 42,328, **−10.9206**, 2026-11-21T13:28:08Z
  - SANDUSDT, order 340506462, BUY 5,219, **−11.3252**, 2026-11-22T12:16:35Z
- **Venue fills:** 24 unmatched zero-realised fills (run 4: 25; run 6: 24) — entry legs of the 30 open positions + breakeven/entries, visible, never silently dropped. The 1 that left vs run 4 is the fill whose first-fill time falls in the Nov-19 20:00:47Z → Nov-20 04:02:05Z aging window (§7); the earliest remaining fill is 2026-11-20T04:02:05Z. The venue's 6 faucet-reset events of 2026-11-19T07:35Z (3× 0.01 + 5,000 USDT grants) are detected; 0 new resets this run.

## §4 — Rows outside the window (9, all 2026-11-14, correctly excluded)

Identical to runs 2/4 (the ledger is unchanged since run 4, so the outside set is unchanged):

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

Identical to run 4 (ledger unchanged since run 4; per-symbol nets re-derived §2 confirm the set):

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

STR-090 §5 left a live re-probe owed, closed by run 2 (§6 there), re-confirmed by run 4 and re-confirmed by this run on the same merged code (blob `f12f5fca`, `_income_page` + `_INCOME_PAGE_LIMIT = 1000` verified present in the worktree):

| Figure | Run 2 (08:16 UTC) | Run 4 (18:36 UTC) | This run (22:15 UTC) |
|---|---|---|---|
| Income rows returned by `income(RESET_MS)` | 1,090 (763 FUNDING_FEE, 267 COMMISSION, 83 REALIZED_PNL, 6 TRANSFER) | 1,122 (763 FUNDING_FEE, 269 COMMISSION, 84 REALIZED_PNL, 6 TRANSFER) | **1,122** (763 FUNDING_FEE, 269 COMMISSION, 84 REALIZED_PNL, 6 TRANSFER) |
| Funding total | +0.6552 | **+0.6774** | **+0.6774** — unchanged; last income row still 2026-11-26T16:00:13Z, no new settlement since run 4 |
| Commission total | −9.4632 | **−9.6135** | **−9.6135** |
| Realised total | −47.231 | **−58.0134** | **−58.0134** |
| Capped-fetch comparison | exactly 1,000 rows, cutoff 2026-11-25T08:00:00Z | paginated fetch returns all 1,122 rows; no cap is hit | single `_income_page(RESET_MS)` still returns exactly 1,000 rows, cutoff 2026-11-25T08:00:00Z — the cap still bites; the paginated fetch returns all 1,122 rows |

**Independent cross-check (same method as runs 2/4 §6):** a separate direct `income()` call on server 4 after the run returned 1,122 rows with totals identical to the report to 4 decimals (COMMISSION −9.6135, FUNDING_FEE +0.6774, TRANSFER +15,000.03, REALIZED_PNL −58.0134). The pagination fix is proven live a third time: the funding figure is unfrozen, and the income figures match full re-derivation.

## §7 — The BOTH → EXIT_ONLY → NO_MATCH shift: venue retention, boundary moved

Run 4 matching was BOTH 25 / EXIT_ONLY 17 / NO_MATCH 39. Run 6 (22:05 UTC) was 24 / 17 / 40. Run 3 is BOTH 24 / EXIT_ONLY 16 / NO_MATCH 41. This is a venue-data effect, not a ledger change — the ledger is unchanged since run 4 (§1), and the identity residual is unchanged (−1.6024):

- Run 4 → run 6 (18:36 → 22:05 UTC): the BTCUSDT close of Nov-19 21:16:49Z (net −10.0709, gross −9.9371, fees 0.1338) left the matched set entirely, BOTH → NO_MATCH: matched exit realised −84.6061 → −74.669 (Δ +9.9371, exactly its gross) and matched ledger net −87.9231 → −77.8521 (Δ +10.0710, exactly its net). Both its legs aged out of the returned window in that interval.
- Run 6 → run 3 (22:05 → 22:15 UTC): the NEARUSDT close of Nov-19 22:12:27Z (net −10.6754, gross −10.621, fees 0.0544) left the matched set, EXIT_ONLY → NO_MATCH: matched exit realised −74.669 → −64.048 (Δ +10.621, exactly its gross) and matched ledger net −77.8521 → −67.1767 (Δ +10.6754, exactly its net). Its exit leg aged out as the boundary passed 22:12Z.
- The matched-fee gap closes exactly too: run 4's 3.3170 less BTC fees 0.1338 + NEAR fees 0.0544 = 3.1287, this run's gap (matched exit −64.048 vs matched ledger net −67.1767). The arithmetic closes on all three figures.
- The earliest fill still returned moved from 2026-11-19T20:00:47Z (run 4) to 2026-11-20T04:02:05Z (run 3) — about 8h of boundary movement for ~3.6h of wall time, so the venue's return set is not a strict 7-day clock window (limit-1000 / retention behaviour); the observed values are reported, the mechanism is not assumed. The same move explains the unmatched-zero fills: 25 → 24, exactly the fill whose first-fill time falls in the moved window.
- The missing-close list is unaffected (the 4 G1 orders are Nov 20–22 exits, still inside the window), and the residual is unaffected (the identity uses income + ledger + missing, not the match classes).
- **Consequence for future runs:** BOTH will keep shrinking as legs age out — run 7+ will show fewer BOTH rows for the same ledger. The verdict rests on the window identity, not the match counts. Persisting venue trades (or a `startTime`-bounded fetch from a stored floor) would be a separate fix task; not attempted here — this task files the state, it does not change the job.

## §8 — Run record (commands, all read-only on the venue)

- **Host:** the live Stratex host is **Stratex-Server (server 4, hostname `stratex-server`)** (STR-093 evidence §8 host correction stands). Verified this run: server 4 holds the live daemon (`Stratex-Daemon.service` active, 30 open positions), the 83-row ledger (last close Nov 26 14:42 UTC), daemon venv python 3.10.22. The daemon service was not touched; no service was restarted, no env file changed. Server 4 checkout main `3db55adf` (unchanged from run 4); the run used a fresh worktree at main `56ebae7d`, the live checkout was not touched.
- **Carried flag:** the Oracle Server 1 timer still fires daily against the stale 80-row ledger (STR-093 evidence §8) — ruling still owed; run 3 uses server 4.
- Worktree: `git fetch origin main` + `git worktree add /tmp/musetp13-str092 origin/main` on server 4. Run 6's `daily_2026-11-27.json` preserved to `/tmp/musetp13-str092-before.json` before this run overwrote it.
- Run (backgrounded, log `/tmp/musetp13-str092-run.log` on server 4):
  `cd /tmp/musetp13-str092/Stratex && PYTHONPATH=/tmp/musetp13-str092/Stratex:/tmp/musetp13-str092 /opt/friday_universe/venv/bin/python -u scripts/daily_fill_ledger_reconciliation.py --env-file /opt/friday_universe/Stratex/.env --state-dir /opt/friday_universe/Stratex/state --date 2026-11-27`
  (the timer service's own invocation, with the worktree paths substituted so the current-main code runs against the live state dir and env file)
- Log line: `[STR-044] 2026-11-27: ledger 83 rows (window 74, net -87.97), matching {'NO_MATCH': 41, 'EXIT_ONLY': 16, 'BOTH': 24}, missing closes 4 (+28.20), resets 6 (0 new), status RECONCILED -> /opt/friday_universe/Stratex/state/reconciliation/daily_2026-11-27.json`
- Tests: `Stratex/tests/test_daily_fill_ledger_reconciliation.py` — **28/28 passed** (pytest, 3.99s, `PYTHONPATH=/tmp/musetp13-str092/Stratex`), incl. the 4 STR-090 pagination tests; no test file changed in this task. CI re-verification from the work PR's job log follows (FUT-030 lesson: the file is collected by `owner-workflows.yml` "Stratex forward-test and self-experiment contracts").

## §9 — Open positions at run time (30, unrealised +26.1043)

| Symbol | Amount | Entry | Mark | Unrealised |
|---|---|---|---|---|
| AAVEUSDT | −0.5 | 109.88 | 94.69 | +7.5950 |
| ADAUSDT | +301.0 | 0.1494 | 0.1495 | +0.0301 |
| ALGOUSDT | −2,293.4 | 0.08004 | 0.08158395 | −3.5409 |
| APTUSDT | −116.9 | 0.4356 | 0.38732223 | +5.6437 |
| ARBUSDT | −410.7 | 0.12691687 | 0.1142 | +5.2228 |
| ATOMUSDT | −151.7 | 1.186 | 1.2175 | −4.7786 |
| AVAXUSDT | −3.0 | 7.015 | 6.62322164 | +1.1753 |
| BCHUSDT | −0.388 | 208.38159794 | 210.25 | −0.7249 |
| BNBUSDT | −0.08 | 590.59 | 554.54 | +2.8840 |
| BTCUSDT | +0.0025 | 59,889.32 | 60,592.0 | +1.7567 |
| DOGEUSDT | −1,453.0 | 0.05505 | 0.05662162 | −2.2836 |
| DOTUSDT | −102.7 | 0.6728 | 0.67445792 | −0.1703 |
| ETCUSDT | −14.63 | 5.659 | 5.942 | −4.1403 |
| ETHUSDT | +0.111 | 1,681.3 | 1,696.48378876 | +1.6854 |
| FILUSDT | −81.9 | 0.5788 | 0.5422 | +2.9975 |
| HBARUSDT | −1,433.0 | 0.05152 | 0.05448 | −4.2417 |
| INJUSDT | −19.0 | 6.657 | 6.204 | +8.6070 |
| LINKUSDT | −8.79 | 8.629 | 9.34 | −6.2497 |
| LTCUSDT | −5.706 | 42.86 | 44.11772731 | −7.1766 |
| MANAUSDT | −1,342.0 | 0.06059954 | 0.05760512 | +4.0185 |
| NEARUSDT | −14.0 | 2.901 | 3.066 | −2.3100 |
| OPUSDT | −661.6 | 0.0768 | 0.06990011 | +4.5650 |
| SANDUSDT | −1,822.0 | 0.03348 | 0.03479059 | −2.3879 |
| SOLUSDT | −2.1 | 69.02 | 71.11615068 | −4.4019 |
| SUIUSDT | −96.1 | 0.6446 | 0.6704 | −2.4794 |
| TRXUSDT | −750.0 | 0.30999 | 0.30441 | +4.1850 |
| UNIUSDT | −9.0 | 4.70744444 | 4.67 | +0.3370 |
| VETUSDT | +40,580.0 | 0.004618 | 0.00486895 | +10.1836 |
| XLMUSDT | −1,792.0 | 0.13436 | 0.12745179 | +12.3795 |
| XRPUSDT | −93.7 | 0.925 | 0.94929221 | −2.2762 |

All 3× leverage. Venue account unrealised +26.0827 (account-level read) vs positions sum +26.1043 (0.0216 apart — different read moments in the same run).

## Files changed

- `docs/collaboration/TASK-STR-092-EVIDENCE.md` — this doc.
- `docs/collaboration/TASK-STR-092-CHECKPOINT-1.md` — scoping (committed earlier this run).
- No board hunk — the flip rides in the coordinator's board PR (SPEED ORDER rule 5).
- No code changed — the reconciler is the merged STR-044 job + STR-090 fix; this task runs it and files the state.

## States

- **implemented:** YES — live reconciliation run + state filed as evidence (no code change required; the job already exists merged).
- **tested:** YES — 28/28 reconciler tests pass on the exact PR-head code; live run exit 0, report filed, errors `[]`. CI log re-verification follows after the work PR opens.
- **merged:** NO — work PR open for review (merge by Muse, never my own PR).
- **deployed:** N/A — the job is already deployed (STR-044 timer on server 4); the report was filed on server 4 by this run. No service change in this PR.
- **production-verified:** YES — live run on Stratex-Server against the demo venue, RECONCILED, report filed; STR-090 live re-probe closed again (§6). Paired verification (owner order rule 3) is owed — no verifier was named for this task; Muse to name one.

— Muse TP13, 2026-11-27 ~03:55 IST (run 2026-11-26T22:15:13Z)
