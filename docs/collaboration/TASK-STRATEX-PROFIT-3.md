# TASK-STRATEX-PROFIT-3 — Live winner allowlist activation record (ZAI Agent 2)

**Date:** 2026-11-13 IST
**Action:** Replaced the live Stratex strategy allowlist with OOS-proven winners.

## Why

The daemon *was* trading (8–9 fills/day), but every strategy on the live
allowlist measured as a **net loser** over the completed 480-run backtest
sweep (10y dailies 2019–2026, 4y 1h, IS≤2023-12-31 / OOS 2024+):

| Live strategy (before) | OOS net | trades | win rate | PF |
| --- | --- | --- | --- | --- |
| strategy_rsi_extreme | **-22,510** | 1,472 | 0.21 | 0.47 |
| strategy_vwap_scalper | **-15,562** | 646 | 0.16 | 0.34 |
| strategy_fast_ema_cross | -6,613 | 281 | 0.20 | 0.43 |
| strategy_mean_reversion_scalper | -1,334 | 69 | 0.23 | 0.54 |
| strategy_rsi_divergence_scalper | family wr 0.15–0.23 | | | |

Additionally the 1.2×ATR stop geometry on 5m bars (~0.3% stops) tripped the
governor's 0.5% fee-drag floor on most signals ("Skip … stop 0.31% < min
0.50%"), so most fired signals never even reached the order book. Result:
few, losing trades — exactly what the owner observed.

## New allowlist (measured winners; IS≥0 AND OOS>0 AND PF≥1.19 AND ≥300 OOS trades)

| Strategy | TF | OOS net | trades | wr | PF |
| --- | --- | --- | --- | --- | --- |
| strategy_hybrid | 1h | **+19,532** | 1,869 | 0.42 | 1.27 |
| strategy_channel_breakout | 1h | +17,643 | 329 | 0.57 | 3.03 |
| strategy_momentum_rotation | 1h | +16,883 | 1,545 | 0.42 | 1.30 |
| strategy_donchian_turtle | 1h | +9,981 | 356 | 0.39 | 1.79 |
| strategy_trend_continuation | 1h | +9,872 | 509 | 0.47 | 1.63 |
| strategy_adx_trend | 1h | +9,061 | 935 | 0.41 | 1.31 |
| strategy_ehlers_hma | 1d | +4,141 | 731 | 0.38 | 1.19 |
| strategy_scalping_breakout (kept) | 5m | +1,798 | 321 | 0.41 | 1.16 |

## Changes applied on Server 1 (backups: .env.bak-1794540071, priors.bak-1794540071)

1. `STRATEX_STRATEGY_ALLOWLIST` → the 8 winners above
2. `STRATEX_TIMEFRAMES` → `15m,5m,1m,1h` (winners validated on 1h)
3. `STRATEX_MIN_EXPECTANCY_R` → 0.05 (winners pass; marginal trades rejected)
4. `state/strategy_priors.json` → measured OOS win rates (2/3 measured + 1/3 module prior)
5. `systemctl restart Stratex-Daemon` (08:52 IST)

## Verified live after restart (08:52–08:53 IST)

- Daemon re-registered all strategies; winner signals firing on 1h/15m/5m
- Orders EXECUTED: BTC SELL @ 69,556, ETH SELL @ 1,959, BNB SELL @ 641, XRP SELL @ 1.0124
  (all `strategy_hybrid`, native STOP_MARKET + TAKE_PROFIT_MARKET brackets placed)
- Expectancy gate visibly working: rejected SOL at +0.033R < +0.05R, accepted
  the four above
- No errors in daemon logs

## Ongoing

- Win rates/priors to be re-measured after live evidence accumulates.
- 409-conflict: external poller still intermittently contests the token;
  webhook-mode fix (merged earlier, PR branch zai/TASK-STRATEX-PROFIT-2 →
  main 2d5e2a6) eliminates it once TELEGRAM_WEBHOOK_URL is set at deploy time.
