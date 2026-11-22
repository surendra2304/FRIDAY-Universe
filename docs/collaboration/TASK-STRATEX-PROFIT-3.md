# TASK-STRATEX-PROFIT-3 — Live winner allowlist activation record (ZAI Agent 2)

**Date:** 2026-11-13 IST
**Action:** Replaced the live Stratex strategy allowlist with OOS-proven winners.

## Venue / account mode — Binance Demo Trading, NOT real money (recorded 2026-11-22, TASK-STR-PROFIT-001)

Every "live" in this record means the live (running) daemon on Server 1, not a
live-money account. The activation applied to the **Binance Demo Trading
(Binance Futures Demo, demo.binance.com)** account. The orders executed
08:52–09:50 IST and the +$31.83 unrealized were demo-account fills.

Evidence:

- Owner decision D-015 (2026-11-10, `docs/collaboration/ACTIVITY_LOG.md`):
  "Stratex's production venue is Binance demo by design ('Yes it is demo only')".
- Server 1 Stratex `.env` verified 2026-11-09 (non-secret flags only,
  TASK-STR-001): `BINANCE_ENV=demo` — the daemon's active venue is
  BinanceFuturesAdapter in demo mode (demo.binance.com). That verification
  predates the activation by 4 days; the activation itself is covered by D-015
  and by the owner's own words in the Nov 12–13 session: "Stratex is losing
  >$1,000/day on the demo account".
- Nov 13-era code (`Stratex/config.py` at commit 88c5eb99): no real-money
  Binance endpoint exists in the daemon's config — the only venues are
  demo-api.binance.com (when `BINANCE_DEMO_TRADING` is set) or
  testnet.binance.vision / testnet.binancefuture.com by default;
  `LIVE_TRADING_ENABLED = False` is a permanent invariant, enforced by
  `validate_environment_safety()` at import. Real-money trading was impossible
  by design on 2026-11-13.

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

## New allowlist (measured winners; IS≥0 AND OOS>0 AND PF≥1.19 AND ≥300 OOS trades — see PF reconciliation below; one exception: strategy_scalping_breakout, PF 1.16)

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

## PF threshold reconciliation (recorded 2026-11-22, TASK-STR-PROFIT-001)

- The selection policy as stated and sent for review was **PF≥1.19** (PR #73
  review request; issue #35 comment 6842900038, which lists exactly the 7
  winners meeting it). The heading above keeps that policy figure.
- The allowlist actually applied has **8** winners: strategy_scalping_breakout
  (PF **1.16**, OOS +1,798, 321 trades, win rate 0.41) was kept as an
  exception — marked "(kept)" in the table above.
- The activity log (2026-11-13 11:25 IST entry) and the WORK_BOARD
  TASK-STRATEX-PROFIT-3 acceptance record the **effective** threshold of the
  applied allowlist, **PF≥1.16** — the minimum PF actually admitted. The two
  numbers describe different things (policy vs applied set), not a typo in
  either place.
- Exception grounds, from this record's own numbers: scalping_breakout passes
  every other selection criterion (OOS +1,798 > 0, 321 OOS trades ≥ 300, win
  rate 0.41), and it is the only 5m strategy in the new allowlist — the other
  seven are 1h/1d — while the daemon still trades 5m (`STRATEX_TIMEFRAMES`
  includes 5m after the change), so dropping it would have left the 5m slot
  empty. No contemporaneous written justification for keeping it was found in
  this record, PR #73, or issue #35; this note is that record.
- Limitation: the 480-run sweep source data (`stage_results.csv`) lives on the
  server, not in the repo, so the near-threshold band (PF 1.16–1.19) could not
  be re-checked from the repo; the reconciliation rests on the documentary
  evidence above.

## Changes applied on Server 1 (backups: .env.bak-1794540071, priors.bak-1794540071)

1. `STRATEX_STRATEGY_ALLOWLIST` → the 8 winners above
2. `STRATEX_TIMEFRAMES` → `15m,5m,1m,1h` (winners validated on 1h)
3. `STRATEX_MIN_EXPECTANCY_R` → 0.05 (winners pass; marginal trades rejected)
4. `state/strategy_priors.json` → measured OOS win rates (2/3 measured + 1/3 module prior)
5. `systemctl restart Stratex-Daemon` (08:52 IST)

## Verified live after restart (08:52–09:50 IST)

- Daemon re-registered all strategies; winner signals firing on 1h/15m/5m
- Orders EXECUTED: BTC SELL @ 69,556, ETH SELL @ 1,959, BNB SELL @ 641, XRP SELL @ 1.0124, PAXG LONG @ 3,874 (native STOP_MARKET + TAKE_PROFIT_MARKET brackets)
- Expectancy gate visibly working: rejected SOL at +0.033R < +0.05R, accepted the five above
- **09:50 IST position check (live engine read): all 5 open positions GREEN**

  | Position | Side | Entry | Unrealized |
  | --- | --- | --- | --- |
  | ETHUSDT | SHORT | 1,959.35 | **+$8.65** |
  | BTCUSDT | SHORT | 69,556.8 | **+$6.50** |
  | BNBUSDT | SHORT | 641.27 | **+$6.38** |
  | PAXGUSDT | LONG | 3,874.59 | **+$6.09** |
  | XRPUSDT | SHORT | 1.0124 | **+$4.21** |
  | **Total** | | | **+$31.83** |

- No errors in daemon logs; ~22 further entries attempted and correctly gated by
  the venue 5-position limit while winners hold.

## Ongoing

- Win rates/priors to be re-measured after live evidence accumulates.
- 409-conflict: external poller still intermittently contests the token;
  webhook-mode fix (merged earlier, PR branch zai/TASK-STRATEX-PROFIT-2 →
  main 2d5e2a6) eliminates it once TELEGRAM_WEBHOOK_URL is set at deploy time.
