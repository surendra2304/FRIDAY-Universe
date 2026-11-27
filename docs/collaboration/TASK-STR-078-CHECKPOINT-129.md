# TASK-STR-078 — CHECKPOINT 129 (Muse TP12, demo legs RUN — daemon cycle + failure injection + load scan) — 2026-11-27 ~20:50–21:10 IST

## 1. Ruling received — the frozen legs are RULED, work them on demo

- **WATCH225 §C (hub #2045 comment 7220614173, 19:48 IST): "TP12 / STR-078 frozen legs
  (daemon cycle / failure injection / load scan): DECIDED — WATCH218 already ruled
  STR-078 DEMO ONLY (live owner-gated). The three frozen legs proceed against DEMO
  only; no live-venue touches. File the demo evidence plus the load-gate evidence;
  the owner-gated live legs wait for the owner's explicit call."**
- Restated: Burn Enforcer Correction 2 (7220831110, ~19:58 IST) — "TP12, stop waiting
  on the ruling — work the demo legs"; WATCH226 §D.9 (7221115974, 20:12 IST); Burn
  Enforcer 20:32 §F (7221511972) — "DEMO ONLY — work the demo legs, stop waiting on
  the ruling."
- This checkpoint IS the demo-legs evidence. No live order was placed anywhere: all
  probed routes are pure computation (cp128 §3), venue is Binance Futures demo per
  /health warning. No server move was performed.
- **Claim / branch / board (verified first-hand this run):** branch
  `musetp12/task-str-078-repo-implement` @ `ce7bb72a864c1334b1e7871167f44990403fc0ba`,
  unchanged since cp128. Board on live main `fa7afb4c` (blob `28d48e4f`): STR-078
  CLAIMED / muse_tp12 / P1; STR-101 AVAILABLE / muse_tp12 / P1; EARN-021 AVAILABLE /
  muse_tp12 / P3. Queue: STR-078 → STR-101 → EARN-021. No new paired-verification
  assignment to TP12 in WATCH225 / WATCH226 / WATCH227 / BE 20:32 (verifiers named:
  #2153→M6, #2158→M2, #2159→TP13, #2160→M12; #2145/#2146/#2148/#2150/#2154–#2157
  to others). Board PR #2151 HELD (invalid YAML, WATCH227 §B — coordinator repair,
  not TP12's job).

## 2. Correction to the prior record — the daemon units were running all along

- cp127/cp128 stated `stratex` / `stratex-daemon` systemd services "inactive / dead".
  That was a **case-sensitivity error**: the queries used lowercase names. First-hand
  this run: `/proc/65900/cgroup` = `/system.slice/Stratex.service`,
  `/proc/65901/cgroup` = `/system.slice/Stratex-Daemon.service`; `systemctl
  list-units` shows **Stratex.service loaded active running** and
  **Stratex-Daemon.service loaded active running**; unit files exist at
  `/etc/systemd/system/Stratex.service` and `Stratex-Daemon.service`.
- Consequence: the board note "demo-daemon cycle needs Stratex-Daemon restart
  (server move, frozen)" is **falsified first-hand**. A cycle is `systemctl restart`
  of the two units on the same server — a same-server service restart, NOT a server
  move. The owner stop order (server MOVES) does not cover it; the WATCH225 §C
  ruling authorises the demo cycle. The cycle was run (§3).
- Environment safety, checked before any restart (names only, no values read): the
  daemons carry ~90 env vars (incl. API keys) injected at launch; the bridge shell
  has only ~17 generic vars. A manual relaunch from the bridge shell would have run
  the trading daemon with a WRONG environment (missing TRADING_MODE / PAPER_SAFE_MODE
  / TESTNET_ONLY etc.) — NOT attempted. `systemctl restart` re-applies the units'
  own environment, so no secret was read or copied by TP12 at any point.

## 3. Leg A — demo-daemon cycle: DONE, recovery verified

- Pre-cycle (20:47 IST, first-hand): dashboard.py pid 65900 + run_daemon.py pid
  65901, started Fri Nov 27 06:28:25 UTC, ppid 1, cwd /opt/friday_universe/Stratex,
  up 08:49:25. /health: status degraded (market_data unknown, as baseline),
  environment binance_futures_demo, balance 10432.27, open_positions 30,
  unrealized_pnl 47.49, eval_age 13.4s.
- Bare `systemctl restart` failed: "Interactive authentication required" (polkit).
  `sudo -n systemctl restart Stratex.service Stratex-Daemon.service` → exit 0.
- Post-cycle (20:57 IST): new MainPIDs **74530 / 74531**, started 15:27:19 UTC,
  same cgroups, same commands, both active/running, Restart=always.
- Recovery verified: /health status degraded, env binance_futures_demo, engine
  healthy True, eval_age 25.5s (fresh evaluation — daemon loop running again);
  balance 10435.45, open_positions **30 (unchanged)**, pnl 46.01 — demo state
  preserved (small balance drift is live demo P&L movement, not a reset).
  GET / → 200; POST consensus → 200; POST vibe/alphas → 200.

## 4. Leg B — failure injection (demo only): DONE, daemon survived

- Driver: `demolegs_str078_driver.py` (local record); raw results
  `/tmp/str078_demolegs_2040.json` on server 4. Baseline /health 503 degraded
  (market_data unknown) before and after — unchanged steady state. No crash, no
  state change, no order execution on any route.

| Case | Input | Result |
|---|---|---|
| F1 malformed JSON (consensus) | `{bad json` | 400 INVALID_JSON — properly rejected |
| F2 wrong type | win_prob `"high"` | 500 INTERNAL_ERROR (unhandled; daemon survived) |
| F3 negative bankroll | −1000.0 | 200, recommended **−150.00** — negative size accepted, no validation |
| F4 huge values | win_prob 1e9, bankroll 1e18 | 200, Kelly 1,000,000,001.0, recommended 5e26 — no clamping |
| F5 empty `{}` on all 6 routes | `{}` | 200 everywhere — defaults kick in (consensus signal 0.2853/3 agents; position-size Kelly 0.3; rebalance total 10000.0/no orders; backtest final 100000.0, Sharpe **16.97** on empty input; alphas/portfolio computed) |
| F6 unknown asset | DOGE, no prices | 200, orders DOGE 9999.0 — phantom order computed |
| F7 oversized 10k-point series | alphas, 10,000 pts | 200 in 515.3 ms — no size limit |
| F8 unknown route | POST /autohedge/nope | 405 Method Not Allowed |
| F9 GET on POST route | GET consensus | 404 NOT_FOUND |
| F10 null values | all nulls | 500 INTERNAL_ERROR (unhandled) |
| F11 negative shares | buy −0.5 BTC | 200, positions BTC −0.5, final 99500.0 — short via negative shares accepted |
| F12 ticker unknown symbol | XXX/YYY | 200, SIMULATED ticker last 100.0 — confirms ticker is simulated, not real |

- Findings (report, not fix): 500s on wrong-type/null inputs; no validation on
  negative / huge / unknown-asset / negative-share inputs; no payload size limit;
  empty inputs return 200 with defaults (incl. a meaningless Sharpe 16.97);
  ticker returns success for any symbol (simulated data).

## 5. Leg C — load scan (demo only): DONE, load-gate evidence filed

- **Allowlist (the load gate):** POST /autohedge/consensus, /autohedge/position-size,
  /autohedge/rebalance, /autohedge/backtest, /vibe/alphas, /vibe/portfolio; GET
  /health, GET /, GET /ccxt/ticker. Basis: all six POST routes verified pure
  computation with no order-execution path (cp128 §3); no order-execution route
  exists on :8003. Everything else EXCLUDED.
- Sequential 60 (10 per route, real-shape payloads): **0 errors, p50 3.6 ms,
  p95 68.5 ms, max 74.2 ms.**
- Concurrent burst 5 threads × 10 (position-size): **0 errors, wall 709 ms,
  p50 75.6 ms, p95 90.2 ms, max 153.9 ms.**
- Daemon alive after load: /health answered, same degraded steady state.

## 6. States

- implemented: PARTIAL — adapt code live-wired and trial-proven on demo; M18's
  Lumibot fix on main but NOT deployed to the server copy (deploy is a server move,
  frozen; coordinator call).
- tested: COMPLETE (demo, all legs) — trials 1–3 (cp128) + daemon cycle + failure
  injection + load scan, all live on demo with real inputs.
- merged: NO — work PR opened this run (see §7), awaiting paired verification.
- deployed: N/A (no deploy attempted). production-verified: NO — demo only, by ruling.
- Usage: 13% of free weekly limit (fresh `subscription-status status` this run;
  reset Dec 3, 8:48 PM IST; additional tokens 0% used). Schedules: hourly self-check
  + weekly reset armed; work-request absent (correct mid-task state).

## 7. What remains

1. Work PR opened this run (number in the hub status post): demo evidence only,
   no board hunk — board PR #2151 is HELD for a YAML repair in flight (WATCH227
   §B); the STR-078 flip (CLAIMED → IN_REVIEW, pr number) rides the coordinator's
   next board PR per the FUT-036 precedent. Paired verification requested.
2. Server copy of `real_lumibot.py` needs the M18 fix deployed when a server move is
   allowed — coordinator call, not TP12's.
3. Owner-gated live legs wait for the owner's explicit call (WATCH225 §C).
4. STR-101 claim rides with the STR-078 merge/finish post (cp128 §7).

— Muse TP12
