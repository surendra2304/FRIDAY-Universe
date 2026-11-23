# TASK-STR-AUDIT-001 — Stratex open-position audit follow-up (evidence)

- **Assignment:** Muse (coordinator) audit post 7101508605 + watch 7101875764 — queue position 2 (STR-HLT-002 blocked head → STR-AUDIT-001 → STR-044 → STR-043).
- **Claim:** hub #1483 comment 7102558094, 2026-11-23 ~18:56 IST (STR-044 PR #1503 merged 18:47:57 IST, merge ecc401a1, verified first-hand via the pulls API).
- **Branch:** `muse4/task-str-audit-001-open-position-audit`, base main `ecc401a1`.
- **Venue:** Binance Futures demo only (`demo-fapi.binance.com`, `BINANCE_ENV=demo`, Ed25519, `LIVE_TRADING_ENABLED` unset). No position was closed or modified. One protective order was PLACED (see §2) — the only venue write in this task, explicitly directed by the assignment ("protect the position per the strategy's rules").
- **Board:** the record was filed by the coordinator's consolidated board PR #1504 (MERGED 19:11:57 IST, merge 3e8a4a14) as CLAIMED, owner muse_4; this PR updates it to IN_REVIEW with the branch and the work results. No duplicate record.

## Verdict

30 open positions verified live from the venue at the final read (2026-11-23 13:42:51Z / 19:12:51 IST): **29/30 carried a full live SL+TP bracket at first read; 1 (AVAXUSDT) carried only its take-profit — no resting stop-loss (P0, posted, then protected — §2).** After protection, 30/30 carry a full bracket (60 live conditional algo orders, re-verified). The BNBUSDT sleeve stop is at its intended per-strategy distance (≈2× weekly ATR, +21.34%), NOT the 15% cap (§1). The exit branch is evaluated every cycle for held positions even when the entry branch reports NO_SIGNAL (§3). The heartbeat/move-verified P&L figures reconcile exactly through the single most recent close (§4).

## §1 — Resting-stop verification (all positions)

**Method.** Signed GETs to demo-fapi via the deployed STR-044 reader (`DemoFuturesReader`, `Stratex/scripts/daily_fill_ledger_reconciliation.py`). Regular `openOrders` returns 0 account-wide — that does NOT mean "no stops": since 2025-12-09, USDⓈ-M Futures rejects STOP_MARKET / TAKE_PROFIT_MARKET on `/fapi/v1/order` (-4120); the daemon's protective orders are conditional algo orders (`/fapi/v1/algoOrder`, `algoType=CONDITIONAL`, `closePosition=true`, `workingType=MARK_PRICE`), visible only via `/fapi/v1/openAlgoOrders` per symbol. This was verified against `Stratex/exchanges/binance_futures_adapter.py` (`_place_sl_tp`, `place_protective_orders`) BEFORE concluding anything about the zero. First read (13:30Z): 30 positions, 59 live algo orders = 29× a full SL+TP pair + AVAX with the TP leg only. Final read (13:42:51Z, after §2 protection): 30 positions, 60 live algo orders. Tag match for every position is EXACT (symbol + side + entry price, from `position_tags.jsonl`, 168 rows). All 30 owners are in the live 73-strategy allowlist (`STRATEX_STRATEGY_ALLOWLIST`, S1 .env); 0 orphaned; 0 past a time-based hold limit (all exits are signal- or broker-stop-driven, per the audit).

**Count change 29 → 30.** The coordinator audit (18:09 IST / 12:39Z) and the STR-044 recon report (12:46Z) both saw 29. The 30th is a new ALGOUSDT LONG (entry 0.08367, `strategy_donchian_turtle_n20_b26_4h`) opened after the recon run; the old ALGOUSDT SHORT closed 11:59:12Z (see §4). The audit's 29 was correct at its time; the table below covers the current 30.

**Per-position evidence table** (final read 13:42:51Z; SL/TP = live conditional algo-order triggers; distances vs entry; last exit-evaluation = latest daemon per-cycle evaluation line for the symbol in `Stratex/bot.log`, all within the last 15 s cycle; heartbeat `last_strategy_evaluation` 13:42:06Z):

| Symbol | Side | Qty | Entry | Mark | Unreal | Owning strategy | SL trigger | SL dist | TP trigger | TP dist | Last exit-eval (UTC) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AAVEUSDT | SHORT | -0.5 | 109.88 | 98.0932 | +5.89 | strategy_keltner_breakout_ema50_m2 | 130.27 | 18.56% | 69.1 | 37.11% | 13:43:02 |
| ADAUSDT | SHORT | -1329 | 0.1397 | 0.1455 | -7.71 | strategy_bollinger_trend_4h | 0.1477 | 5.73% | 0.1236 | 11.52% | 13:42:21 |
| ALGOUSDT | LONG | 2569.2 | 0.08367 | 0.0846558 | +2.53 | strategy_donchian_turtle_n20_b26_4h | 0.07953 | 4.95% | 0.09601 | 14.75% | 13:42:52 |
| APTUSDT | SHORT | -116.9 | 0.4356 | 0.38016 | +6.48 | strategy_donchian_turtle | 0.5258 | 20.71% | 0.1651 | 62.10% | 13:42:40 |
| ARBUSDT | SHORT | -410.7 | 0.126917 | 0.112051 | +6.11 | strategy_bollinger_trend | 0.1529 | 20.47% | 0.0758 | 40.28% | 13:42:42 |
| ATOMUSDT | SHORT | -190.48 | 1.208 | 1.19854 | +1.80 | strategy_donchian_turtle_n20_b26_4h | 1.264 | 4.64% | 1.039 | 13.99% | 13:42:32 |
| AVAXUSDT | SHORT | -29 | 6.453 | 6.72 | -7.74 | strategy_donchian_turtle_n20_b26_4h | 6.824 | 5.75% | 5.341 | 17.23% | 13:42:29 |
| BCHUSDT | SHORT | -0.388 | 208.382 | 199.312 | +3.52 | strategy_keltner_breakout | 235.57 | 13.05% | 154.13 | 26.03% | 13:42:37 |
| BNBUSDT | SHORT | -0.08 | 590.59 | 556.365 | +2.74 | strategy_sleeve_shock_breakout | 716.65 | 21.34% | 338.47 | 42.69% | 13:42:17 |
| BTCUSDT | LONG | 0.0025 | 59889.3 | 61275.6 | +3.47 | strategy_bar_patterns_inside_bar_4h | 55581.2 | 7.19% | 68501.7 | 14.38% | 13:43:06 |
| DOGEUSDT | SHORT | -1453 | 0.05505 | 0.05561 | -0.81 | strategy_donchian_turtle | 0.06237 | 13.30% | 0.0331 | 39.87% | 13:42:19 |
| DOTUSDT | SHORT | -312.4 | 0.6583 | 0.671915 | -4.25 | strategy_donchian_turtle_n20_b26_4h | 0.6926 | 5.21% | 0.5555 | 15.62% | 13:42:26 |
| ETCUSDT | SHORT | -14.63 | 5.659 | 5.787 | -1.87 | strategy_keltner_breakout | 6.38 | 12.74% | 4.223 | 25.38% | 13:42:35 |
| ETHUSDT | LONG | 0.111 | 1681.3 | 1723.85 | +4.72 | strategy_ha_trend_one_candle_4h | 1585.37 | 5.71% | 1873.06 | 11.41% | 13:43:07 |
| FILUSDT | SHORT | -81.9 | 0.5788 | 0.5393 | +3.24 | strategy_bollinger_trend | 0.7079 | 22.30% | 0.3214 | 44.47% | 13:42:39 |
| HBARUSDT | SHORT | -1433 | 0.05152 | 0.05227 | -1.07 | strategy_donchian_turtle | 0.05894 | 14.40% | 0.02927 | 43.19% | 13:42:51 |
| INJUSDT | SHORT | -19 | 6.657 | 6.37914 | +5.28 | strategy_ha_trend_one_candle_4h | 7.209 | 8.29% | 5.557 | 16.52% | 13:42:45 |
| LINKUSDT | SHORT | -8.79 | 8.629 | 8.92262 | -2.58 | strategy_donchian_turtle | 9.838 | 14.01% | 5.001 | 42.04% | 13:42:25 |
| LTCUSDT | SHORT | -5.706 | 42.86 | 40.8307 | +11.58 | strategy_donchian_turtle_n20_b26_4h | 44.7 | 4.29% | 37.34 | 12.88% | 13:42:23 |
| MANAUSDT | SHORT | -1342 | 0.0605995 | 0.0564779 | +5.53 | strategy_keltner_breakout | 0.06856 | 13.14% | 0.045 | 25.74% | 13:42:59 |
| NEARUSDT | SHORT | -14 | 2.901 | 2.99709 | -1.35 | strategy_donchian_turtle | 3.65 | 25.82% | 0.662 | 77.18% | 13:42:30 |
| OPUSDT | SHORT | -661.6 | 0.0768 | 0.0709093 | +3.90 | strategy_ha_trend | 0.0927 | 20.70% | 0.0449 | 41.54% | 13:42:44 |
| SANDUSDT | SHORT | -1822 | 0.03348 | 0.0334255 | +0.10 | strategy_ha_trend | 0.03933 | 17.47% | 0.02184 | 34.77% | 13:42:56 |
| SOLUSDT | LONG | 2.96 | 72.51 | 72.4928 | -0.05 | strategy_ha_trend_one_candle_4h | 68.92 | 4.95% | 79.66 | 9.86% | 13:42:16 |
| SUIUSDT | SHORT | -96.1 | 0.6446 | 0.669585 | -2.40 | strategy_donchian_turtle | 0.7556 | 17.22% | 0.3121 | 51.58% | 13:42:47 |
| TRXUSDT | SHORT | -750 | 0.30999 | 0.30743 | +1.92 | strategy_ichimoku_trend_raw | 0.32401 | 4.52% | 0.28195 | 9.05% | 13:42:28 |
| UNIUSDT | SHORT | -9 | 4.70744 | 4.737 | -0.27 | strategy_keltner_breakout | 5.863 | 24.55% | 2.389 | 49.25% | 13:42:33 |
| VETUSDT | LONG | 40580 | 0.004618 | 0.00475786 | +5.68 | strategy_ha_trend_two_candle_4h | 0.004351 | 5.78% | 0.005137 | 11.24% | 13:42:54 |
| XLMUSDT | SHORT | -1792 | 0.13436 | 0.128479 | +10.54 | strategy_donchian_turtle_n20_b26_4h | 0.14029 | 4.41% | 0.11681 | 13.06% | 13:42:49 |
| XRPUSDT | SHORT | -93.7 | 0.925 | 0.940641 | -1.47 | strategy_bollinger_trend | 1.0385 | 12.27% | 0.698 | 24.54% | 13:42:18 |

**BNBUSDT sleeve stop — intended distance, NOT capped.** SL 716.65 is +21.34% above entry 590.59; TP 338.47 is 42.69% below — exactly the judged 1:2 ratio (`sl_method` 2.0× ATR(14), `tp_method` 4.0× ATR(14) at the signal bar, `strategy_sleeve_shock_breakout`, `config_strategy.py`). Implied ATR = 126.06 / 2 = 63.03; independently, BNB 1w ATR(14) from public demo-fapi klines = 63.97 (11.51% of last close 555.52; 2× = 23.03%) — the live bracket matches the judged geometry within 1.5%. The 15% engine-global cap (`STRATEX_MAX_STOP_PCT=0.15`, S1 .env) does NOT apply: the sleeve's registry entry declares `max_stop_pct: 0.90` (TASK-STR-FWD-012 — "judged stop is 2.0 x weekly ATR — genuine stops ~16-36% of price, structurally above the 15% engine-global cap"; 0.90 is a sanity bound only), and the cap is an entry gate (`run_daemon.py:3238-3251`, judged against `_max_stop_pct_for_strategy`), not a placement clamp. The sleeve's bracket (created 2026-11-19T09:49:23Z, algoIds 1000000293151049/52) is the judged bracket, placed at entry. (Correction to my own first read: the tag match initially picked `strategy_overlay_ema10_50_vt15_none_1d` — entry 589.17, 0.24% away; the exact-match rule gives `strategy_sleeve_shock_breakout`, entry 590.59, qty 0.08, tag ts 2026-11-19T09:49:24Z, matching the audit.)

## §2 — AVAXUSDT: the one position with NO resting stop (P0, protected)

**Finding (P0, hub #1483 comment 7102712231, 2026-11-23 ~19:03 IST; Surendra told 19:13 IST).** AVAXUSDT SHORT, qty −29, entry 6.453, owner `strategy_donchian_turtle_n20_b26_4h` (tag 2026-11-20T16:03:23Z), mark 6.72738, unrealized −7.96 at first read. Live conditional orders: ONE — TAKE_PROFIT_MARKET at 5.341 (algoId 1000000295218307, `closePosition`, `MARK_PRICE`, `NEW`). NO stop-loss above entry. Upside uncapped by any resting order; the only exit while unprotected was the daemon's per-cycle evaluation (§3).

**History (venue's own record).** The stop WAS placed at entry: `/fapi/v1/allAlgoOrders` for AVAXUSDT shows a STOP_MARKET at trigger **6.8240** (algoId 1000000295218294, adjacent to the TP's algoId — same placement batch), last status change **12:16:21Z today (17:46:21 IST)**. The level is exactly the strategy's judged stop: TP-implied ATR = (6.453 − 5.341) / 6 = 0.18533, so 2× ATR above entry = 6.8237 ≈ 6.8240 (and TP:SL distance ratio 1.112 : 0.371 = 3.00, the judged RR 3.0 for `donchian_turtle_n20_b26_4h`: SL 2.0× ATR, TP 6.0× ATR, `max_stop_pct` 0.20).

**Cause of the loss: UNDETERMINED (gap G1).** No daemon log line in any `bot.log*` (current + rotated) records cancelling it: zero `UNPROTECTED` lines, zero `leftover protective` / `Cancelled … protective` lines. No daemon cancel path applies to a still-open trend position — `cancel_protective_orders` runs only after a close (trend exit, forward time exit, trailing exit, overlay close) or after a detected broker SL/TP close in the reconciler (the position never closed). `donchian_turtle_n20_b26_4h` has no `exit_mode: trailing`, so the trailing manager never touched it. The FWD-031 re-arm (`_overlay_ensure_bracket`) covers overlay positions only — there is NO bracket-integrity watch for trend positions, so a lost bracket is never re-armed and never alarmed. That missing watch is the gap, filed as G1 below; the cancellation itself needs the venue's audit trail (not reachable from here) to attribute.

**Protection (done, verified live).** Re-placed the missing leg at the judged level via the production adapter's own path (`BinanceFuturesAdapter.place_protective_orders`, stop leg only, `take_profit=None`), demo only, ~19:08 IST. Pre-checks in the same probe: position still SHORT −29 @ 6.453, mark 6.723 < 6.824 (no instant trigger), exactly one live algo order (TP 5.341), no SL. New STOP_MARKET @ **6.824, algoId 1000000299247691**. Post-check (fresh venue read): 2 live algo orders — STOP_MARKET 6.824 `NEW` + TAKE_PROFIT_MARKET 5.341 `NEW`, both `closePosition`; position unchanged SHORT −29. Final read (§1): AVAX SL 6.824 (5.75%), TP 5.341 (17.23%). No position was closed or modified.

## §3 — Exit-path proof (Nov-19 cohort as test set)

**Code.** The exit branch is separate from the entry branch and runs on its own cadence in `Stratex/autonomy/run_daemon.py`: `_manage_forward_time_exits` (line 2470, ≥60 s, iterates `engine.positions`, closes at market when `forward_guard.time_exit_due` for the strategy's judged `max_bars`); `_manage_trend_positions` (line 1589, EMA20-cross exit, `strategy_trend_daily` only); `_manage_trailing_exits` (line 2622, trailing-mode strategies only). Each cycle also re-evaluates every strategy on every symbol (15 s cadence; heartbeat `last_strategy_evaluation` 13:42:06Z, `scan_count` 3, last cycle scanned 2310 / signals 1). Entry evaluation returning NO_SIGNAL therefore never suppresses the exit passes — they iterate the held positions directly.

**Logs.** The owning strategies of the cohort are re-evaluated every cycle while their positions are held — e.g. `strategy_donchian_turtle_n20_b26_4h` on `binance_futures:AVAXUSDT 4h: NO_SIGNAL` at 13:04:41Z, 13:05:56Z, 13:07:02Z, 13:07:35Z, 13:08:45Z (`bot.log.1`); cohort-symbol evaluation lines at 13:37Z (`bot.log`); `strategy_sleeve_shock_breakout` on AVAXUSDT 1w: `SIGNAL - SELL` 13:31:34Z (re-evaluation while SHORT held — consistent with holding, not a new entry). The manage passes log only on action, so "evaluated, nothing due" is silent by design — the per-cycle evaluation lines above are the evaluation evidence.

**Cohort (all 1d SHORTs opened 2026-11-19T09:58Z, tag ts):**

| Symbol | Owning strategy | Entry | SL | TP | Unreal @ final read | Last exit-eval (UTC) |
|---|---|---|---|---|---|---|
| AAVEUSDT | strategy_keltner_breakout_ema50_m2 | 109.88 | 130.27 | 69.1 | +5.89 | 13:43:02 |
| APTUSDT | strategy_donchian_turtle | 0.4356 | 0.5258 | 0.1651 | +6.48 | 13:42:40 |
| ARBUSDT | strategy_bollinger_trend | 0.126917 | 0.1529 | 0.0758 | +6.11 | 13:42:42 |
| BCHUSDT | strategy_keltner_breakout | 208.382 | 235.57 | 154.13 | +3.52 | 13:42:37 |
| FILUSDT | strategy_bollinger_trend | 0.5788 | 0.7079 | 0.3214 | +3.24 | 13:42:39 |
| MANAUSDT | strategy_keltner_breakout | 0.0605995 | 0.06856 | 0.045 | +5.53 | 13:42:59 |
| OPUSDT | strategy_ha_trend | 0.0768 | 0.0927 | 0.0449 | +3.90 | 13:42:44 |

All 7 in profit at the final read (the audit's "6 of 7" was at 18:09 IST; marks moved). All 7 carry live SL+TP brackets (table §1).

**The exit path fires in practice.** Two positions closed TODAY by broker SL/TP, booked in the fill ledger: SOLUSDT SHORT 09:05:57Z, net −10.72378920; ALGOUSDT SHORT 11:59:12Z, net −10.62294596 (both `exit_reason: SL_TP_BROKER`). The ledger holds 64 `SL_TP_BROKER` closes in total. Those closes are the resting brackets doing exactly what the exit branch is for — on positions whose entry signals were NO_SIGNAL all day.

## §4 — One-line reconciliation (heartbeat realized P&L vs move-verified)

**Heartbeat realized P&L +130.27280441 already includes the 11:59Z ALGO close (net −10.62294596); the move-verified +140.89575037 = heartbeat − (ALGO net), i.e. the pre-ALGO-close total — the two figures reconcile exactly through that single close.**

- Difference: 140.89575037 − 130.27280441 = **10.62294596** = |ALGOUSDT close net| (ledger row 75: ALGOUSDT SHORT, qty 962.8, entry 0.07247, exit 0.08347, gross −10.5908, fees 0.03214596, net **−10.62294596**, `SL_TP_BROKER`, exit 2026-11-23T11:59:12Z).
- The heartbeat's daily counter proves it absorbed the close: `daily_realized_pnl` −21.34673516 = SOL −10.72378920 + ALGO −10.62294596 exactly.
- So the heartbeat figure (+130.27280441, `daemon_heartbeat.json` + `realized_pnl.json`, 13:42:51Z) is the current one; the coordinator's move-verified figure is the total before that close landed. No unexplained residual: the reconciliation is exact to 8 decimals.
- Supporting scope notes (not part of the one-liner): fill-ledger net sum over all 75 rows = +190.49068657 (3 `LEGACY-UNATTRIBUTED` rows +195.7066, 72 attributed rows −5.2159); venue income `REALIZED_PNL` since the 2026-11-14 reset = +24.7149 (75 rows). Ledger, heartbeat counter, and venue income cover different scopes; the one-liner above is exact on the two figures the assignment named. The heartbeat counter's scope vs the ledger total is not documented anywhere I could read — noted as observation O1, not a discrepancy in this reconciliation.

## Gaps / follow-ups

- **G1 (from §2): no bracket-integrity watch for trend positions.** `_overlay_ensure_bracket` (FWD-031) re-arms brackets for overlay positions only. A trend position whose stop is cancelled (AVAX, 12:16:21Z, cause undetermined) sits unprotected until a human notices — the daemon never re-checks the venue for it. Fix owed (not in this task's scope): a periodic bracket-integrity pass over all held positions, re-arming a missing leg from the strategy's judged stop and alarming when it does.
- **O1 (from §4):** the heartbeat cumulative realized-P&L counter's scope vs the fill-ledger total (+130.27 vs +190.49) is undocumented; worth one line in the daemon's accounting docs. No action taken here — the assigned one-liner is exact.

## States

- **implemented:** YES — audit complete (30/30 positions verified, evidence table filed), P0 found, posted, and protected.
- **tested:** YES — all findings re-verified live from the venue (final read 13:42:51Z: 30 positions, 60 live algo orders; AVAX bracket re-read after placement).
- **merged:** NO — work PR open for review (merge by Muse).
- **deployed:** N/A — no code change; the protection was a venue-side order placement (demo), verified live.
- **production-verified:** YES — the 30/30 bracket state was read back from the live venue after the protection, not assumed from the placement call.
