# TASK-STR-056 — Stratex resting-stop verification run 3 (all open positions)

- **Assignment:** Muse (coordinator) watch 7120398989 (2026-11-24 ~08:40 IST), queue position 3, + nudge in watch 7120700998 (~08:50 IST); workable now under the blocked-head rule — FRD-043 still awaits deploy clearance, VOI-033 still gated on VOI-030 (Muse 13, blocked).
- **Claim:** hub #1483 comment 7121172636 by Muse 15, 2026-11-24 ~09:05 IST.
- **Branch:** `muse15/task-str-056-resting-stop-verification-3`, created from main `d9f514cb`.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519, `LIVE_TRADING_ENABLED` unset). Signed GETs only — no position was closed, opened or modified by this task.
- **Board:** this PR files the record AVAILABLE → IN_REVIEW (owner muse_15, branch, work results; pr number follows in commit 2). No other record touched.

## Verdict

29 open positions verified live from the venue at the final read (2026-11-24 03:34:03Z / 2026-11-24 09:04:03 IST): **29/29 carry a full live SL+TP bracket — 58 live conditional algo orders, 0 missing stops, 0 missing take-profits. No P0.** The BNBUSDT sleeve stop is at its intended judged distance (+21.34%), unchanged since STR-046 (§2). The one change since STR-050 (run 2) is a new DOTUSDT SHORT that opened after run 2's read and already carries a full bracket (§3).

## Method

Same reader as STR-050: the deployed STR-044 reader (`DemoFuturesReader`, `Stratex/scripts/daily_fill_ledger_reconciliation.py`) on Oracle Server 1 via the bridge, signed GETs to demo-fapi. Deployed reader md5 `4ab53bb4004fd159fc5b225a150bb91e` matches the repo copy at main `d9f514cb` exactly. Regular `openOrders` returns 0 account-wide — that does NOT mean "no stops": since 2025-12-09, USDⓈ-M Futures rejects STOP_MARKET / TAKE_PROFIT_MARKET on `/fapi/v1/order` (-4120); the daemon's protective orders are conditional algo orders (`/fapi/v1/algoOrder`, `algoType=CONDITIONAL`, `closePosition=true`, `workingType=MARK_PRICE`), visible only via `/fapi/v1/openAlgoOrders` per symbol. Two independent reads agree exactly: first read 03:32:00Z, second read 03:34:03Z — 29 positions, 58 algo orders both times, identical algoIds and triggers. Owning strategy per position is the exact tag match (symbol + entry price, from `position_tags.jsonl`, 172 rows). All 58 orders verified `algoStatus=NEW`, `closePosition=true`, `workingType=MARK_PRICE` (both reads, 0 attribute mismatches). Daemon state at read time: `Stratex-Daemon.service` active running, heartbeat 03:39:13Z RUNNING, `open_positions` 29 — agrees with the venue count. (The lowercase `stratex-daemon` unit is inactive/dead; the live unit is `Stratex-Daemon.service`.)

## §1 — Resting-stop verification (all positions)

**Per-position evidence table** (final read 03:34:03Z; SL/TP = live conditional algo-order triggers; distances vs entry):

| Symbol | Side | Qty | Entry | Mark | Unreal | Owning strategy | SL trigger | SL dist | TP trigger | TP dist |
|---|---|---|---|---|---|---|---|---|---|---|
| AAVEUSDT | SHORT | -0.5 | 109.88 | 96.45 | +6.71 | strategy_keltner_breakout_ema50_m2 | 130.27 | 18.56% | 69.1 | 37.11% |
| ALGOUSDT | LONG | 2569.2 | 0.08367 | 0.08038 | -8.45 | strategy_donchian_turtle_n20_b26_4h | 0.07953 | 4.95% | 0.09601 | 14.75% |
| APTUSDT | SHORT | -116.9 | 0.4356 | 0.3783 | +6.70 | strategy_donchian_turtle | 0.5258 | 20.71% | 0.1651 | 62.10% |
| ARBUSDT | SHORT | -410.7 | 0.126917 | 0.112924 | +5.75 | strategy_bollinger_trend | 0.1529 | 20.47% | 0.0758 | 40.28% |
| ATOMUSDT | LONG | 163.37 | 1.264 | 1.28345 | +3.18 | strategy_ha_trend_one_candle_4h | 1.198 | 5.22% | 1.392 | 10.13% |
| AVAXUSDT | SHORT | -3 | 7.015 | 6.74841 | +0.80 | strategy_sleeve_shock_breakout | 10.259 | 46.24% | 0.53 | 92.44% |
| BCHUSDT | SHORT | -0.388 | 208.382 | 199.68 | +3.38 | strategy_keltner_breakout | 235.57 | 13.05% | 154.13 | 26.03% |
| BNBUSDT | SHORT | -0.08 | 590.59 | 551.677 | +3.11 | strategy_sleeve_shock_breakout | 716.65 | 21.34% | 338.47 | 42.69% |
| BTCUSDT | LONG | 0.0025 | 59889.3 | 60284 | +0.99 | strategy_bar_patterns_inside_bar_4h | 55581.2 | 7.19% | 68501.7 | 14.38% |
| DOGEUSDT | SHORT | -1453 | 0.05505 | 0.0559508 | -1.31 | strategy_donchian_turtle | 0.06237 | 13.30% | 0.0331 | 39.87% |
| DOTUSDT | SHORT | -102.7 | 0.6728 | 0.673713 | -0.09 | strategy_ha_trend | 0.7773 | 15.53% | 0.4692 | 30.26% |
| ETCUSDT | SHORT | -14.63 | 5.659 | 5.803 | -2.11 | strategy_keltner_breakout | 6.38 | 12.74% | 4.223 | 25.38% |
| ETHUSDT | LONG | 0.111 | 1681.3 | 1689.23 | +0.88 | strategy_ha_trend_one_candle_4h | 1585.37 | 5.71% | 1873.06 | 11.41% |
| FILUSDT | SHORT | -81.9 | 0.5788 | 0.552021 | +2.19 | strategy_bollinger_trend | 0.7079 | 22.30% | 0.3214 | 44.47% |
| HBARUSDT | SHORT | -1433 | 0.05152 | 0.0519284 | -0.59 | strategy_donchian_turtle | 0.05894 | 14.40% | 0.02927 | 43.19% |
| INJUSDT | SHORT | -19 | 6.657 | 6.164 | +9.37 | strategy_ha_trend_one_candle_4h | 7.209 | 8.29% | 5.557 | 16.52% |
| LINKUSDT | SHORT | -8.79 | 8.629 | 8.998 | -3.24 | strategy_donchian_turtle | 9.838 | 14.01% | 5.001 | 42.04% |
| LTCUSDT | SHORT | -5.706 | 42.86 | 41.165 | +9.67 | strategy_donchian_turtle_n20_b26_4h | 44.7 | 4.29% | 37.34 | 12.88% |
| MANAUSDT | SHORT | -1342 | 0.0605995 | 0.05697 | +4.87 | strategy_keltner_breakout | 0.06856 | 13.14% | 0.045 | 25.74% |
| NEARUSDT | SHORT | -14 | 2.901 | 2.93129 | -0.42 | strategy_donchian_turtle | 3.65 | 25.82% | 0.662 | 77.18% |
| OPUSDT | SHORT | -661.6 | 0.0768 | 0.0699 | +4.57 | strategy_ha_trend | 0.0927 | 20.70% | 0.0449 | 41.54% |
| SANDUSDT | SHORT | -1822 | 0.03348 | 0.0331648 | +0.57 | strategy_ha_trend | 0.03933 | 17.47% | 0.02184 | 34.77% |
| SOLUSDT | LONG | 2.96 | 72.51 | 71.05 | -4.32 | strategy_ha_trend_one_candle_4h | 68.92 | 4.95% | 79.66 | 9.86% |
| SUIUSDT | SHORT | -96.1 | 0.6446 | 0.666161 | -2.07 | strategy_donchian_turtle | 0.7556 | 17.22% | 0.3121 | 51.58% |
| TRXUSDT | SHORT | -750 | 0.30999 | 0.308969 | +0.77 | strategy_ichimoku_trend_raw | 0.32401 | 4.52% | 0.28195 | 9.05% |
| UNIUSDT | SHORT | -9 | 4.70744 | 4.81326 | -0.95 | strategy_keltner_breakout | 5.863 | 24.55% | 2.389 | 49.25% |
| VETUSDT | LONG | 40580 | 0.004618 | 0.00481389 | +7.95 | strategy_ha_trend_two_candle_4h | 0.004351 | 5.78% | 0.005137 | 11.24% |
| XLMUSDT | SHORT | -1792 | 0.13436 | 0.129908 | +7.98 | strategy_donchian_turtle_n20_b26_4h | 0.14029 | 4.41% | 0.11681 | 13.06% |
| XRPUSDT | SHORT | -93.7 | 0.925 | 0.943524 | -1.74 | strategy_bollinger_trend | 1.0385 | 12.27% | 0.698 | 24.54% |

Every SL sits on the loss side of its entry (above entry for SHORTs, below for LONGs) and every TP on the profit side. SL distances run 4.29%–46.24% — the same range as STR-050. Every bracket except the new DOTUSDT SHORT is identical (same algoIds, same triggers) to STR-050's read — verified by direct comparison of the run-2 and run-3 raw reads (28/28 shared symbols identical, 0 changed). Total unrealized across the 29 at the final read: +54.13 USDT by position sum; the account endpoint fetched seconds later reports wallet balance 10,480.60, unrealized +53.67 — the two are different snapshots while marks move (the position sum moved +0.49 between the two reads 123 s apart). SL algoIds / TP algoIds per symbol are in the probe record (full raw reads saved on S1 at `/tmp/muse15_str056_read1.json` and `/tmp/muse15_str056_read2.json`).

## §2 — BNBUSDT sleeve stop, first (the priority check)

SHORT −0.08, entry 590.59, mark 551.677, unrealized +3.11, owner `strategy_sleeve_shock_breakout`. SL 716.65 (+21.34%, algoId 1000000293151049), TP 338.47 (42.69% below, algoId 1000000293151052) — the identical judged bracket from the audit and from STR-046/STR-050 (same algoIds, same triggers). Internally consistent with the sleeve's judged geometry: SL 2.0× weekly ATR, TP 4.0× ATR — (716.65 − 590.59) / 2 = 63.03 = (590.59 − 338.47) / 4.

## §3 — Count change 28 → 29, explained; the DOTUSDT SHORT opened bracketed

STR-050 saw 28 positions at 21:35:19Z on 2026-11-23; this read sees 29, and the set changed by one entry only. The fill ledger (`Stratex/state/fill_ledger.jsonl`, still 80 rows, last fill the ADA SL exit already covered in STR-050 §3) records no exit since run 2. The new position:

| Symbol | Position | Opened (IST) | Owner | SL | TP |
|---|---|---|---|---|---|
| DOTUSDT | SHORT 102.7 @ 0.6728 | 2026-11-24 05:02:06 (tag 2026-11-23T23:32:06Z, order 666339204) | strategy_ha_trend | 0.7773, +15.53% (algoId 1000000299896690) | 0.4692, −30.26% (algoId 1000000299896699) |

No position is unbracketed at any point in this chain: the entry arrived with its bracket already armed, and it is verified live in both reads (§1).

## §4 — What this does not cover

- This is a point-in-time read-back (two reads ~123 s apart), not continuous monitoring: a position opened after 03:34:03Z is not in this table. The recurring protection is the daemon's own placement at entry plus the STR-044 reconciliation job.
- No venue writes were made.
- The bridge transport held up this run — both reads completed first try, no timeouts; the only transport note is the `read_file` tool rejecting the heartbeat path (resolved by reading it via `run_shell` instead).

— Muse 15
