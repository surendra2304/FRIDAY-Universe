# TASK-STR-078 — CHECKPOINT 128 (Muse TP12, demo-leg trials 1–3 RUN — live evidence) — 2026-11-27 ~17:45–18:40 IST

## 1. Ruling received — HELD becomes DEMO ONLY

- **WATCH218 §D (hub #2045 comment 7216979610, ~16:51 IST), adopted by Burn Enforcer 17:01 §A
  (7217108843): "TP12 STR-078 live-trial — DECIDED: DEMO ONLY. The trial leg runs against the
  demo account (demo 5376835) and files trial evidence; the live leg stays owner-gated — no
  live execution without Surendra's words. TP12 proceeds on demo now; progress report owed
  next run."** BE 17:47 §A (7217811734) and WATCH219/WATCH220 carry no further TP12 direction.
- This checkpoint IS that progress report, with the trials run. No live order was placed
  anywhere: all six trial routes are pure computation (verified from the route code, §3),
  the Lumibot gate demo is in-process simulation, and the venue is the Binance Futures demo
  per the daemon's own /health warning. Account number 5376835 was not independently
  verified on the server (no account record read); the demo venue was verified instead.
- **Claim / branch / board (verified first-hand this run):** branch
  `musetp12/task-str-078-repo-implement` @ `5f0cf3b2942e2f98d1215ef0a5db5bde040a8a21`,
  unchanged. Board on live main `896ceb7a` (blob `409850b4`): STR-078 CLAIMED / muse_tp12 /
  branch on record / pr null / P1; STR-101 AVAILABLE / muse_tp12 / P1; EARN-021 AVAILABLE /
  muse_tp12 / P3. Queue: STR-078 → STR-101 → EARN-021. No new paired-verification assignment
  to TP12 in WATCH218 §B / WATCH219 / WATCH220 / BE 17:47 §B.

## 2. Live service state (read-only, Friday Bridge, Stratex-Server = server 4)

- `stratex` and `stratex-daemon` systemd services: **inactive / dead** (unchanged since
  2026-11-24 13:42 IST). No restart attempted — server move, frozen under the owner stop order.
- Live processes instead: `dashboard.py` (pid 65900) and
  `Stratex/autonomy/run_daemon.py` (pid 65901), both up 5:45:11, listening on **:8003**.
  `GET /health` → **503**: `trading_capable ok`, `trading_engine ok` ("multi-venue daemon
  heartbeat fresh, pid alive"), `market_data unknown` ("MARKET_DATA_NOT_REPORTED").
  Warning: **"DEMO_ENVIRONMENT: execution venue is Binance Futures demo; Pepperstone
  pending-approval"**. `GET /` → 200 (operations dashboard). `/openapi.json`, `/docs` → 404.
- **Daemon ticker is SIMULATED, not real market data:** `GET
  /api/v1/trading/engines/ccxt/ticker?symbol=BTC/USDT&exchange=binance` returns
  last 100.0 / bid 99.9 / ask 100.1 / high 105.0 / low 95.0 / volume 1000.0. The trials
  below therefore do NOT use the daemon ticker; real market data is Binance public klines
  fetched on the server (§3).
- Blueprint mounting verified: `Stratex/dashboard.py:55` registers `real_trading_bp`
  (`/api/v1/trading/engines` prefix) — the trial routes ARE served by the :8003 app.

## 3. Trial inputs — real market data

- **30 hourly BTCUSDT klines** (Binance public API, fetched on server 4, HTTP 200):
  closes first 60521.78 / last 61667.79, min 60480.01, max 61777.36,
  open times 1795676400000 → 1795780800000. **60 hourly klines** for the Lumibot leg:
  first 59272.01 / last 61650.01.
- Route code read first-hand from live main `896ceb7a` (blob `e4b682ba`, 24,041 B):
  all six trial handlers take JSON inputs and return computed values; **no order execution,
  no broker call inside any endpoint** (AutoHedge consensus / position-size / rebalance /
  backtest; Vibe alphas / portfolio). Trial driver: `trial_str078_driver.py`, full raw
  results `/tmp/str078_trials_1740.json` on server 4 (12 entries).

## 4. Trial results — all HTTP 200

| Trial | Result (live :8003, demo venue) |
|---|---|
| T1 AutoHedge consensus | signal 0.2633, confidence 0.0202, disagreement 0.96, weighted_vote 0.2633, 3 agents; signals = signs of last 5 hourly returns |
| T1F empty signals | 200, all zeros (signal 0.0, confidence 0.0) — no validation error |
| T2 AutoHedge position-size | Kelly 0.3, raw 15000.0, fractional Kelly 0.15, drawdown multiplier 1.0, recommended 15000.0 (win_prob 0.55, ratio 1.8, fraction 0.5, bankroll 100000) |
| T2F win_prob 1.5 | 200, Kelly 1.7778, recommended 88888.89 — **no input validation: win_prob > 1 returns a >1 Kelly fraction** (finding, not a crash) |
| T2F bankroll 0 | 200, all sizes 0.0 |
| T3 AutoHedge rebalance | total 40833.895, drift BTC 0.59999, needs_rebalance True, orders BTC −6333.56 / USDT +16333.56 (0.5 BTC @ 61667.79, cash 10000, target 60/40) |
| T3F empty positions | 200, total 10000.0, orders BTC 6000.0 |
| T4 AutoHedge backtest | final 100114.601, Sharpe 3.287, Sortino 6.094, cash 100114.601 — real trade buy 0.1 BTC @ 60521.78, sell @ 61667.79 (+$114.60) |
| T5 Vibe alphas | 200, `engine VibeTrading`; 5 core factors + GTJA alpha_001/002/003/010/191 computed over the real 30-candle OHLCV series |
| T5F 2-point series | 200, factors computed (no crash on short input) |
| T6 Vibe portfolio | 200; combined[:5] 0.3706, 0.1432, −0.1545, 0.2495, 0.1934; top_n [18, 0], bottom_n [2, 14]; total_risk 0.1421 |
| T7 Lumibot paper-gate | **GATE DEMONSTRATED:** paper broker — order `filled` @ 61667.79, position BTC/USDT open, cash 93833.221; live broker — order `submitted`, NOT filled, no position, cash untouched 100000.0 |

## 5. Lumibot backtest — server copy still carries the pre-fix defect (finding)

- First run on the server copy: **0 trades on 30 AND 60 real closes, all three strategies**
  (sma_crossover / breakout / mean_reversion). Cause verified first-hand on server 4:
  the server's working copy has line 240
  `sig = signals.get(symbol, {}).get(i, 0) if isinstance(signals.get(symbol), dict) else 0`
  — the exact defect M18 fixed (signals is `dict[str, list[int]]`, so `sig` is always 0).
  Server file hash-object `505d8943…`, NOT main's fixed blob. The signal generator itself
  works (rising series → 30 nonzero signals from idx 30).
- **Fixed module re-run (blob verified):** the live-main file (SHA-1 `6270a959d960…`,
  = main blob `6270a959`) run on the same 60 real closes:
  sma_crossover **3 trades** (BUY @ 60521.78 idx 30, SELL @ 61319.44 idx 49 pnl +1.32%,
  BUY @ 61411.00 idx 50 open at end; return +6.165% by the module's own metric,
  win_rate 0.333); breakout **1 trade** (BUY @ 60458.01 idx 22, open); mean_reversion
  **0 trades** (price never deviated ±5% from the 20-SMA on this range — honest zero).
  Note: the module's `total_return` counts an open 0.1-BTC position at last price on top
  of initial cash; reported as returned, not re-derived.
- **Consequence:** M18's fix is on main but NOT on the live server copy. Deploying it is a
  server move — frozen; NOT attempted. Flagged here for the coordinator; the backtest leg
  is proven against the fixed main-branch code, not against the stale server copy.

## 6. States

- implemented: PARTIAL — adapt code live-wired and trial-proven on demo; Lumibot fix on
  main but not deployed to the server copy.
- tested: COMPLETE (demo trials 1–3) — all six routes + paper gate run live on demo with
  real market inputs and failure cases; no live order placed.
- merged: NO — no work PR yet (frozen legs still open, §7).
- deployed: N/A (no deploy attempted). production-verified: NO — demo only, by ruling.
- Usage: 12% of free weekly limit (fresh `subscription-status status` this run; reset
  Dec 3, 8:48 PM IST; additional tokens 0% used). Schedules: hourly self-check + weekly
  reset armed; work-request absent (correct mid-task state).

## 7. What remains

1. Demo-daemon cycle — FROZEN (restart = server move, owner stop order).
2. Failure injection — HELD per STR-070 precedent.
3. Full-allowlist load scan — needs the allowlist definition.
4. Validation gaps found (report, not fix, in this checkpoint): position-size accepts
   win_prob > 1 (Kelly 1.78); empty/degenerate inputs return 200 with zeros everywhere.
5. Server copy of `real_lumibot.py` needs the M18 fix deployed when a server move is
   allowed — coordinator call, not TP12's.
- Work PR owed when the coordinator rules on the frozen legs (trials 1–3 are done with
  live evidence; the task is not fully DONE while 1–3 above stand). No work PR opened
  in this run. Next: hub progress post this run; STR-101 claim rides with the STR-078
  merge/finish post.

— Muse TP12
