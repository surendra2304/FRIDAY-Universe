# TASK-STR-050 — Stratex resting-stop verification run 2 (all open positions)

- **Assignment:** Muse (coordinator) watch 7114406781 (2026-11-24 ~03:15 IST): queue position 4 after FUT-024 / VYR-043 / EARN-002; board PR #1570 (main `384950d9`).
- **Claim:** hub #1483 comment 7114516196 by Muse 15, 2026-11-24 ~03:00 IST.
- **Branch:** `muse15/task-str-050-resting-stop-verification-2`, created from main `384950d9`.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519, `LIVE_TRADING_ENABLED` unset). Signed GETs only — no position was closed, opened or modified by this task.
- **Board:** this PR files the record AVAILABLE → IN_REVIEW (owner muse_15, branch, work results; pr number follows in commit 2). No other record touched.

## Verdict

28 open positions verified live from the venue at the final read (2026-11-23 21:35:19Z / 2026-11-24 03:05:19 IST): **28/28 carry a full live SL+TP bracket — 56 live conditional algo orders, 0 missing stops, 0 missing take-profits. No P0.** The BNBUSDT sleeve stop is at its intended judged distance (+21.34%), unchanged since STR-046 (§2). The ADAUSDT LONG that STR-046 verified has closed — its protective stop fired (§3); the new ATOMUSDT LONG opened after STR-046's read already carries a full bracket.

## Method

Same reader as STR-046: the deployed STR-044 reader (`DemoFuturesReader`, `Stratex/scripts/daily_fill_ledger_reconciliation.py`) on Oracle Server 1 via the bridge, signed GETs to demo-fapi. Deployed reader md5 `4ab53bb4004fd159fc5b225a150bb91e` matches the repo copy at main `384950d9` exactly. Regular `openOrders` returns 0 account-wide — that does NOT mean "no stops": since 2025-12-09, USDⓈ-M Futures rejects STOP_MARKET / TAKE_PROFIT_MARKET on `/fapi/v1/order` (-4120); the daemon's protective orders are conditional algo orders (`/fapi/v1/algoOrder`, `algoType=CONDITIONAL`, `closePosition=true`, `workingType=MARK_PRICE`), visible only via `/fapi/v1/openAlgoOrders` per symbol. Two independent reads agree exactly: first read 21:34:18Z, second read 21:35:19Z — 28 positions, 56 algo orders both times, identical algoIds and triggers. Owning strategy per position is the exact tag match (symbol + entry price, from `position_tags.jsonl`, 171 rows). All 56 orders verified `algoStatus=NEW`, `closePosition=true`, `workingType=MARK_PRICE` (second read, 0 attribute mismatches).

One adaptation from STR-046: the bridge client times out at 45 s, so the two reads ran as two separate invocations (~61 s apart) instead of one process with an 80 s sleep — the first single-process attempt was killed mid-sleep by the client timeout and wrote nothing. The U1 read path is gone (AWS U1/U2 deleted 2026-11-23 ~18:09 IST on the owner order); both reads ran on Oracle S1, where Stratex now lives. Daemon state at read time: `Stratex-Daemon.service` active running, heartbeat 21:29:44Z RUNNING, `open_positions` 28 — agrees with the venue count. (The lowercase `stratex-daemon` unit is inactive/dead; the live unit is `Stratex-Daemon.service`.)

## §1 — Resting-stop verification (all positions)

**Per-position evidence table** (final read 21:35:19Z; SL/TP = live conditional algo-order triggers; distances vs entry):

| Symbol | Side | Qty | Entry | Mark | Unreal | Owning strategy | SL trigger | SL dist | TP trigger | TP dist |
|---|---|---|---|---|---|---|---|---|---|---|
| AAVEUSDT | SHORT | -0.5 | 109.88 | 97.56393505 | +6.16 | strategy_keltner_breakout_ema50_m2 | 130.27 | 18.56% | 69.1 | 37.11% |
| ALGOUSDT | LONG | 2569.2 | 0.08367 | 0.08186079 | -4.65 | strategy_donchian_turtle_n20_b26_4h | 0.07953 | 4.95% | 0.09601 | 14.75% |
| APTUSDT | SHORT | -116.9 | 0.4356 | 0.383 | +6.15 | strategy_donchian_turtle | 0.5258 | 20.71% | 0.1651 | 62.10% |
| ARBUSDT | SHORT | -410.7 | 0.1269168736304 | 0.113 | +5.72 | strategy_bollinger_trend | 0.1529 | 20.47% | 0.0758 | 40.28% |
| ATOMUSDT | LONG | 163.37 | 1.264 | 1.268 | +0.65 | strategy_ha_trend_one_candle_4h | 1.198 | 5.22% | 1.392 | 10.13% |
| AVAXUSDT | SHORT | -3 | 7.015 | 6.82504504 | +0.57 | strategy_sleeve_shock_breakout | 10.259 | 46.24% | 0.53 | 92.44% |
| BCHUSDT | SHORT | -0.388 | 208.3815979381 | 201.32 | +2.74 | strategy_keltner_breakout | 235.57 | 13.05% | 154.13 | 26.03% |
| BNBUSDT | SHORT | -0.08 | 590.59 | 559.26489876 | +2.51 | strategy_sleeve_shock_breakout | 716.65 | 21.34% | 338.47 | 42.69% |
| BTCUSDT | LONG | 0.0025 | 59889.32 | 61408.4 | +3.80 | strategy_bar_patterns_inside_bar_4h | 55581.2 | 7.19% | 68501.7 | 14.38% |
| DOGEUSDT | SHORT | -1453 | 0.05505 | 0.05676485 | -2.49 | strategy_donchian_turtle | 0.06237 | 13.30% | 0.0331 | 39.87% |
| ETCUSDT | SHORT | -14.63 | 5.659 | 5.896 | -3.47 | strategy_keltner_breakout | 6.38 | 12.74% | 4.223 | 25.38% |
| ETHUSDT | LONG | 0.111 | 1681.3 | 1723.0866376 | +4.64 | strategy_ha_trend_one_candle_4h | 1585.37 | 5.71% | 1873.06 | 11.41% |
| FILUSDT | SHORT | -81.9 | 0.5788 | 0.5555 | +1.91 | strategy_bollinger_trend | 0.7079 | 22.30% | 0.3214 | 44.47% |
| HBARUSDT | SHORT | -1433 | 0.05152 | 0.05288 | -1.95 | strategy_donchian_turtle | 0.05894 | 14.40% | 0.02927 | 43.19% |
| INJUSDT | SHORT | -19 | 6.657 | 6.486 | +3.25 | strategy_ha_trend_one_candle_4h | 7.209 | 8.29% | 5.557 | 16.52% |
| LINKUSDT | SHORT | -8.79 | 8.629 | 9.016 | -3.40 | strategy_donchian_turtle | 9.838 | 14.01% | 5.001 | 42.04% |
| LTCUSDT | SHORT | -5.706 | 42.86 | 41.38 | +8.44 | strategy_donchian_turtle_n20_b26_4h | 44.7 | 4.29% | 37.34 | 12.88% |
| MANAUSDT | SHORT | -1342 | 0.060599538003 | 0.05696792 | +4.87 | strategy_keltner_breakout | 0.06856 | 13.14% | 0.045 | 25.74% |
| NEARUSDT | SHORT | -14 | 2.901 | 2.99829369 | -1.36 | strategy_donchian_turtle | 3.65 | 25.82% | 0.662 | 77.18% |
| OPUSDT | SHORT | -661.6 | 0.0768 | 0.0702 | +4.37 | strategy_ha_trend | 0.0927 | 20.70% | 0.0449 | 41.54% |
| SANDUSDT | SHORT | -1822 | 0.03348 | 0.03299 | +0.89 | strategy_ha_trend | 0.03933 | 17.47% | 0.02184 | 34.77% |
| SOLUSDT | LONG | 2.96 | 72.51 | 72.61402481 | +0.31 | strategy_ha_trend_one_candle_4h | 68.92 | 4.95% | 79.66 | 9.86% |
| SUIUSDT | SHORT | -96.1 | 0.6446 | 0.6774 | -3.15 | strategy_donchian_turtle | 0.7556 | 17.22% | 0.3121 | 51.58% |
| TRXUSDT | SHORT | -750 | 0.30999 | 0.30952 | +0.35 | strategy_ichimoku_trend_raw | 0.32401 | 4.52% | 0.28195 | 9.05% |
| UNIUSDT | SHORT | -9 | 4.707444444444 | 4.841 | -1.20 | strategy_keltner_breakout | 5.863 | 24.55% | 2.389 | 49.25% |
| VETUSDT | LONG | 40580 | 0.004618 | 0.004827 | +8.48 | strategy_ha_trend_two_candle_4h | 0.004351 | 5.78% | 0.005137 | 11.24% |
| XLMUSDT | SHORT | -1792 | 0.13436 | 0.13104952 | +5.93 | strategy_donchian_turtle_n20_b26_4h | 0.14029 | 4.41% | 0.11681 | 13.06% |
| XRPUSDT | SHORT | -93.7 | 0.925 | 0.94207471 | -1.60 | strategy_bollinger_trend | 1.0385 | 12.27% | 0.698 | 24.54% |

Every SL sits on the loss side of its entry (above entry for SHORTs, below for LONGs) and every TP on the profit side. SL distances run 4.29%–46.24% — the same range as STR-046; every bracket except the new ATOMUSDT LONG is identical (same triggers, same algoIds) to STR-046's read. Total unrealized across the 28: +48.46 USDT at the final read (account: wallet balance 10,491.79, unrealized +48.47 — agrees). SL algoIds / TP algoIds per symbol are in the probe record (`muse15_str050_probe.py` output; full raw reads saved on S1 at `/tmp/muse15_str050_read1.json` and `/tmp/muse15_str050_read2.json`).

## §2 — BNBUSDT sleeve stop, first (the priority check)

SHORT −0.08, entry 590.59, mark 559.26489876, unrealized +2.51, owner `strategy_sleeve_shock_breakout`. SL 716.65 (+21.34%, algoId 1000000293151049), TP 338.47 (42.69% below, algoId 1000000293151052) — the identical judged bracket from the audit and from STR-046 (same algoIds, same triggers). Internally consistent with the sleeve's judged geometry: SL 2.0× weekly ATR, TP 4.0× ATR — (716.65 − 590.59) / 2 = 63.03 = (590.59 − 338.47) / 4.

## §3 — Count change 28 → 28, explained; the ADA stop fired, ATOM opened bracketed

STR-046 saw 28 positions at 16:53:33Z on 2026-11-23; this read sees 28 again, but the set changed by one exit and one entry. The fill ledger (`Stratex/state/fill_ledger.jsonl`, 80 rows) accounts for the single exit since STR-046's read — recorded `exit_reason: SL_TP_BROKER`, i.e. a resting stop/take-profit fired:

| Symbol | Old position | Exit (IST) | Exit price | vs resting trigger | Net P&L |
|---|---|---|---|---|---|
| ADAUSDT | LONG 1549 @ 0.155875, ha_trend_one_candle_4h | 01:10:06 (Nov 24) | 0.1486 | SL 0.1482 (placed, STR-046 §1) | −11.36 |

The ADAUSDT LONG's stop fired at 19:40:06Z (01:10:06 IST) — exit 0.1486 against the resting SL trigger 0.1482 (fill 0.0004 above the mark-price trigger, normal execution). The loss was bounded at −11.36 net instead of running uncapped. The new ATOMUSDT LONG (163.37 @ 1.264, `strategy_ha_trend_one_candle_4h`, tag 2026-11-23T20:01:52Z, order 645270529) opened after STR-046's read and already carries a full bracket (SL 1.198, −5.22%; TP 1.392, +10.13%) — verified live in both reads (§1). No position is unbracketed at any point in this chain: the exit was a stop firing, the entry arrived with its bracket.

## §4 — What this does not cover

- This is a point-in-time read-back (two reads ~61 s apart), not continuous monitoring: a position opened after 21:35:19Z is not in this table. The recurring protection is the daemon's own placement at entry plus the STR-044 reconciliation job.
- No venue writes were made. The ADA exit in §3 was the broker's, before this task started.
- The bridge transport dropped twice this run (client 45 s timeout on the first single-process probe attempt; one `run_shell` status check also failed with "MCP request did not complete" and succeeded on retry) — reads themselves are complete and agree exactly; the transport lag is noted, not a data gap.
