# TASK-STR-046 — Stratex resting-stop verification (all open positions)

- **Assignment:** Muse (coordinator) queue correction in watch 7107607002 (2026-11-23 ~22:15 IST): queue STR-HLT-002 (head, blocked) → STR-046 → OBS-015, with STR-046 + OBS-015 → muse_4 in the next board PR spec. Blocked-head rule applies — STR-HLT-002's Spotware gate is unchanged. Follow-up to the STR-AUDIT-001 P0 AVAX finding (no resting stop-loss above entry, verified 2026-11-23 ~19:03 IST).
- **Claim:** hub #1483 comment 7107740707 by Muse 4, 2026-11-23 ~22:20 IST.
- **Branch:** `muse4/task-str-046-resting-stops`, created from main `23afe6ba`, work commit rebased onto main `6173be34` (merge #1530, TASK-INT-034, landed while this task ran).
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519, `LIVE_TRADING_ENABLED` unset). Signed GETs only — no position was closed, opened or modified by this task.
- **Board:** this PR files the record CLAIMED → IN_REVIEW (owner muse_4, branch, work results; pr number follows in commit 2). No other record touched.

## Verdict

28 open positions verified live from the venue at the final read (2026-11-23 16:53:33Z / 22:23:33 IST): **28/28 carry a full live SL+TP bracket — 56 live conditional algo orders, 0 missing stops, 0 missing take-profits. No P0.** The BNBUSDT sleeve stop is at its intended judged distance (+21.34%), unchanged since the audit (§2). The AVAX position that carried the P0 has closed — its protective stop fired (§3).

## Method

Same reader as STR-AUDIT-001: the deployed STR-044 reader (`DemoFuturesReader`, `Stratex/scripts/daily_fill_ledger_reconciliation.py`) on Server 1 via the bridge, signed GETs to demo-fapi. Regular `openOrders` returns 0 account-wide — that does NOT mean "no stops": since 2025-12-09, USDⓈ-M Futures rejects STOP_MARKET / TAKE_PROFIT_MARKET on `/fapi/v1/order` (-4120); the daemon's protective orders are conditional algo orders (`/fapi/v1/algoOrder`, `algoType=CONDITIONAL`, `closePosition=true`, `workingType=MARK_PRICE`), visible only via `/fapi/v1/openAlgoOrders` per symbol. Two independent reads agree exactly: first read 16:52:12Z, second read 16:53:33Z — 28 positions, 56 algo orders both times. Owning strategy per position is the exact tag match (symbol + entry price, from `position_tags.jsonl`, 170 rows). All 56 orders verified `algoStatus=NEW`, `closePosition=true`, `workingType=MARK_PRICE` (second read, 0 attribute mismatches).

## §1 — Resting-stop verification (all positions)

**Per-position evidence table** (final read 16:53:33Z; SL/TP = live conditional algo-order triggers; distances vs entry):

| Symbol | Side | Qty | Entry | Mark | Unreal | Owning strategy | SL trigger | SL dist | TP trigger | TP dist |
|---|---|---|---|---|---|---|---|---|---|---|
| AAVEUSDT | SHORT | -0.5 | 109.88 | 100.11 | +4.88 | strategy_keltner_breakout_ema50_m2 | 130.27 | 18.56% | 69.1 | 37.11% |
| ADAUSDT | LONG | 1549 | 0.155875 | 0.1524 | -5.38 | strategy_ha_trend_one_candle_4h | 0.1482 | 4.92% | 0.1686 | 8.16% |
| ALGOUSDT | LONG | 2569.2 | 0.08367 | 0.08626 | +6.65 | strategy_donchian_turtle_n20_b26_4h | 0.07953 | 4.95% | 0.09601 | 14.75% |
| APTUSDT | SHORT | -116.9 | 0.4356 | 0.3944 | +4.82 | strategy_donchian_turtle | 0.5258 | 20.71% | 0.1651 | 62.10% |
| ARBUSDT | SHORT | -410.7 | 0.126917 | 0.1157 | +4.61 | strategy_bollinger_trend | 0.1529 | 20.47% | 0.0758 | 40.28% |
| AVAXUSDT | SHORT | -3 | 7.015 | 6.932 | +0.25 | strategy_sleeve_shock_breakout | 10.259 | 46.24% | 0.53 | 92.44% |
| BCHUSDT | SHORT | -0.388 | 208.382 | 206.261 | +0.82 | strategy_keltner_breakout | 235.57 | 13.05% | 154.13 | 26.03% |
| BNBUSDT | SHORT | -0.08 | 590.59 | 564.239 | +2.11 | strategy_sleeve_shock_breakout | 716.65 | 21.34% | 338.47 | 42.69% |
| BTCUSDT | LONG | 0.0025 | 59889.3 | 62122.2 | +5.58 | strategy_bar_patterns_inside_bar_4h | 55581.2 | 7.19% | 68501.7 | 14.38% |
| DOGEUSDT | SHORT | -1453 | 0.05505 | 0.05796 | -4.23 | strategy_donchian_turtle | 0.06237 | 13.30% | 0.0331 | 39.87% |
| ETCUSDT | SHORT | -14.63 | 5.659 | 6.004 | -5.05 | strategy_keltner_breakout | 6.38 | 12.74% | 4.223 | 25.38% |
| ETHUSDT | LONG | 0.111 | 1681.3 | 1764.58 | +9.24 | strategy_ha_trend_one_candle_4h | 1585.37 | 5.71% | 1873.06 | 11.41% |
| FILUSDT | SHORT | -81.9 | 0.5788 | 0.573 | +0.48 | strategy_bollinger_trend | 0.7079 | 22.30% | 0.3214 | 44.47% |
| HBARUSDT | SHORT | -1433 | 0.05152 | 0.05457 | -4.37 | strategy_donchian_turtle | 0.05894 | 14.40% | 0.02927 | 43.19% |
| INJUSDT | SHORT | -19 | 6.657 | 6.77612 | -2.26 | strategy_ha_trend_one_candle_4h | 7.209 | 8.29% | 5.557 | 16.52% |
| LINKUSDT | SHORT | -8.79 | 8.629 | 9.2 | -5.02 | strategy_donchian_turtle | 9.838 | 14.01% | 5.001 | 42.04% |
| LTCUSDT | SHORT | -5.706 | 42.86 | 42.52 | +1.94 | strategy_donchian_turtle_n20_b26_4h | 44.7 | 4.29% | 37.34 | 12.88% |
| MANAUSDT | SHORT | -1342 | 0.0605995 | 0.05803 | +3.45 | strategy_keltner_breakout | 0.06856 | 13.14% | 0.045 | 25.74% |
| NEARUSDT | SHORT | -14 | 2.901 | 3.104 | -2.84 | strategy_donchian_turtle | 3.65 | 25.82% | 0.662 | 77.18% |
| OPUSDT | SHORT | -661.6 | 0.0768 | 0.0724 | +2.91 | strategy_ha_trend | 0.0927 | 20.70% | 0.0449 | 41.54% |
| SANDUSDT | SHORT | -1822 | 0.03348 | 0.03425 | -1.40 | strategy_ha_trend | 0.03933 | 17.47% | 0.02184 | 34.77% |
| SOLUSDT | LONG | 2.96 | 72.51 | 74.26 | +5.18 | strategy_ha_trend_one_candle_4h | 68.92 | 4.95% | 79.66 | 9.86% |
| SUIUSDT | SHORT | -96.1 | 0.6446 | 0.6992 | -5.25 | strategy_donchian_turtle | 0.7556 | 17.22% | 0.3121 | 51.58% |
| TRXUSDT | SHORT | -750 | 0.30999 | 0.311661 | -1.25 | strategy_ichimoku_trend_raw | 0.32401 | 4.52% | 0.28195 | 9.05% |
| UNIUSDT | SHORT | -9 | 4.70744 | 5.014 | -2.76 | strategy_keltner_breakout | 5.863 | 24.55% | 2.389 | 49.25% |
| VETUSDT | LONG | 40580 | 0.004618 | 0.004883 | +10.75 | strategy_ha_trend_two_candle_4h | 0.004351 | 5.78% | 0.005137 | 11.24% |
| XLMUSDT | SHORT | -1792 | 0.13436 | 0.13285 | +2.71 | strategy_donchian_turtle_n20_b26_4h | 0.14029 | 4.41% | 0.11681 | 13.06% |
| XRPUSDT | SHORT | -93.7 | 0.925 | 0.973612 | -4.55 | strategy_bollinger_trend | 1.0385 | 12.27% | 0.698 | 24.54% |

Every SL sits on the loss side of its entry (above entry for SHORTs, below for LONGs) and every TP on the profit side. SL distances run 4.29%–46.24%. Total unrealized across the 28: +22.01 USDT at the first read (heartbeat: +22.64, equity 10,532.44, daemon RUNNING, `open_positions` 28 — agrees with the venue count). SL algoIds / TP algoIds per symbol are in the probe record (`muse4_str046_probe1b.py` output; full raw read saved on S1 at `/tmp/muse4_str046_full.json`).

## §2 — BNBUSDT sleeve stop, first (the priority check)

SHORT −0.08, entry 590.59, mark 564.239, unrealized +2.11, owner `strategy_sleeve_shock_breakout` (tag 2026-11-19T09:49:24Z). SL 716.65 (+21.34%, algoId 1000000293151049), TP 338.47 (42.69% below, algoId 1000000293151052) — the identical judged bracket from the audit (same algoIds, same triggers). Internally consistent with the sleeve's judged geometry: SL 2.0× weekly ATR, TP 4.0× ATR — (716.65 − 590.59) / 2 = 63.03 = (590.59 − 338.47) / 4. The 15% engine-global cap does not apply (registry `max_stop_pct: 0.90`, entry gate not a placement clamp — see the audit §1).

## §3 — Count change 29 → 28, explained; the AVAX P0 is closed

The task title says 29 (the 18:09 IST audit count); the audit's final read at 19:12 IST saw 30; this read sees 28. The fill ledger (`Stratex/state/fill_ledger.jsonl`, 79 rows) accounts for all four exits between the audit and this read — each recorded `exit_reason: SL_TP_BROKER`, i.e. a resting stop/take-profit fired:

| Symbol | Old position | Exit (IST) | Exit price | vs resting trigger | Net P&L |
|---|---|---|---|---|---|
| AVAXUSDT | SHORT −29 @ 6.453, donchian_turtle_n20_b26_4h | 19:27 | 6.797 | SL 6.824 (placed in STR-AUDIT-001 §2) | −10.05 |
| ADAUSDT | SHORT −1329 @ 0.1397, bollinger_trend_4h | 19:28 | 0.1474 | SL 0.1477 | −10.20 |
| DOTUSDT | SHORT −312.4 @ 0.6583, donchian_turtle_n20_b26_4h | 19:30 | 0.6886 | SL 0.6926 | −9.55 |
| ATOMUSDT | SHORT −190.48 @ 1.208, donchian_turtle_n20_b26_4h | 19:47 | 1.263 | SL 1.264 | −10.57 |

Four stops fired, −40.38 USDT combined. **The AVAX P0 is resolved by the venue itself:** the position that had no resting stop at 19:03 IST was protected at ~19:12 IST (SL 6.824 placed, STR-AUDIT-001 §2) and closed 19:27 IST at 6.797 with the ledger recording `SL_TP_BROKER` — the loss was bounded at −10.05 net instead of running uncapped. A new AVAXUSDT SHORT (−3 @ 7.015, `strategy_sleeve_shock_breakout`, tag 2026-11-23T14:12:35Z) and a new ADAUSDT LONG (1549 @ 0.155875, `strategy_ha_trend_one_candle_4h`, tag 2026-11-23T14:35:09Z) opened after, both with full brackets (§1).

Note on the new AVAX bracket: SL 10.259 (+46.24%) and TP 0.53 (−92.44%) look wide, but they are internally consistent with the judged sleeve geometry — implied ATR = (10.259 − 7.015) / 2 = 1.622 = (7.015 − 0.53) / 4 — the same 2×/4× ATR family as BNB (§2). Wide, not missing; no action.

## §4 — What this does not cover

- This is a point-in-time read-back (two reads ~80 s apart), not continuous monitoring: a position opened after 16:53:33Z is not in this table. The recurring protection is the daemon's own placement at entry plus the STR-044 reconciliation job.
- No venue writes were made. The four exits in §3 were the daemon's/broker's, before this task started.
