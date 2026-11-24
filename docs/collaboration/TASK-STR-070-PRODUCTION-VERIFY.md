# TASK-STR-070: PRODUCTION-VERIFY Stratex corpus items IG-STR-01..05 — live evidence

Worker: Muse 5. Claim: hub #1483 comment 7137316210, 2026-11-24 ~21:50 IST.
Branch: muse5/task-str-070-prod-verify (claim-time main 7b564203; fast-forwarded to main ca6de826 for this PR).
Probe runs: 2026-11-24 ~22:30 IST and ~22:35 IST, first-hand by Muse 5.
Server: Stratex-Server (13.211.78.20) via bridge run_shell on Server 2 -> ssh with the S2 Oracle key. Read-only probes, except one disclosed /tmp scratch file for the journal chain (created, verified, deleted; net zero production-state change).
No daemon start/stop/restart, no trades/orders, no config or code changes, no failure injection, no moves of any kind.

## What each item is (board records, verified first-hand)

All five are merged + DEPLOYED research utilities in Stratex/rigorous_backtest/ig/ (PRs #452, #458, #460, #461, #464; merged 2026-11-16, deployed 2026-11-17). Every board record says the same thing: "no deploy step" / "no production consumer" — none of the five is wired into the live daemon, and none feeds any production engine. That bounds what "run it in the live agent" can mean for these items: the live exercise is running each module, in the live agent's own deployed checkout on Stratex-Server, on live market data, on a real task — which is what was done. No ledger entry exists for any of them, because there is no consumer to write one; that is a property of the items, not a gap in the probe.

Byte-identity check: all six module files on Stratex-Server are md5-identical to main ca6de826 (options_pricing 9d7c4045…, dom_features c5a79cb0…, levels 72df1eba…, scenario_sim 048fdb8d…, research_desk 79dc0e9a…, desk_journal cf8b7145…). The code exercised live IS current main code. (Server checkout itself is 3db55adf, behind main ca6de826 — see Observations.)

Source note: PRODUCTION-VERIFICATION-PROGRAMME.md is NOT on main ca6de826 (repo-tree search + code search, 2026-11-24 ~22:40 IST — no such file). The acceptance below is taken verbatim from the TASK-STR-070 board record itself, read first-hand from the board snapshot. If the programme doc lands in the repo, re-check sections A/B/C against this evidence.

## Live environment state (both probes)

- Stratex-Server up 12:42, load 0.61. Stratex.service ACTIVE, MainPID 13272, NRestarts 0. Stratex-Daemon.service ACTIVE, MainPID 13273, running 09:55:06 as /opt/friday_universe/venv/bin/python -u /opt/friday_universe/Stratex/autonomy/run_daemon.py.
- /health :8003 at 2026-11-24T16:52:41Z: status "degraded" (market_data state UNKNOWN — "MARKET_DATA_NOT_REPORTED", heartbeat omits market-data flags); trading_capable ok; trading_engine ok ("multi-venue daemon heartbeat fresh, pid alive"); daemon_balance 10453.48561324; daemon_last_evaluation 7.4s old; open_positions 30; unrealized_pnl 108.04; environment binance_futures_demo; DEMO_ENVIRONMENT warning (Binance Futures demo; Pepperstone pending-approval); database connected (Oracle SELECT 1 FROM DUAL ok).
- Daemon log tail: live strategy evaluation in progress at probe time (e.g. strategy_dow_effect on binance_futures:BNBUSDT 1d: SIGNAL - BUY, alongside NO_SIGNAL lines). The daemon IS cycling live on real market data.
- paper_trade_ledger.jsonl: 3 lines only; last closed trade BTCUSDT SHORT, entry 66735.92 / exit 64848.48, net_pnl +181.83.
- forward_signal_log.jsonl: 769 lines; latest signals timestamped 1795532400 (2026-11-24 16:20 UTC) — see Observations.
- friday-stratex-reconciliation.timer: enabled, next run Wed 2026-11-25 01:00 UTC. stratex-forward-scorecard.timer last ran ~6 min before the probe. daily_loss_breaker_state.json is STALE (day 2026-11-15) — see Observations.

## Per-item verdicts

### IG-STR-01 — Black-Scholes options pricing + greeks — VERIFIED LIVE
Live task: price a 30-day at-the-money BTC option on the LIVE spot and round-trip implied vol, on Stratex-Server, in the deployed checkout.
Live data: BTCUSDT spot 59578.20 (Binance public REST, fetched from the server); strike 59600; T=30d; r=5%; sigma=60%.
Result: call 4188.10, put 3965.47, delta 0.5429, gamma 0.000039, vega 6774.69, theta -26135.50; put-call parity residual 3.64e-12 (zero to machine precision); implied-vol round-trip 0.6000 (exact recovery of the input vol). Correct on live data, no orders placed, no venue touched (stdlib math only, as documented).

### IG-STR-02 — Order-book / depth-of-market features — VERIFIED LIVE
Live task: compute the full DOM feature snapshot on the LIVE BTCUSDT order book, on Stratex-Server.
Live data: 20-level Binance depth, best bid 59578.19 / best ask 59578.20.
Result: mid 59578.195, spread 0.00168 bps, microprice 59578.191, top-5 imbalance -0.9317 (ask-heavy), bid depth in 50 bps band 0.340, ask depth 10.717; walls flagged at the top of both sides (bid 0.26862 BTC, ask 4.18183 BTC). Features computed from the real snapshot; nothing interpolated, no orders placed.

### IG-STR-03 — Support/resistance levels + chart annotations — VERIFIED LIVE
Live task: detect S/R levels on LIVE BTCUSDT 1h candles, on Stratex-Server.
Live data: 100 live 1h klines (window 1795179600000 -> 1795536000000 ms; last close 59580.01).
Result: 14 levels found, e.g. support 55130.00, support 57778.35, resistance-origin 58672.05 — JSON-serialisable annotation records, as designed. No signals, no orders.

### IG-STR-04 — Pre-trade scenario simulation ("Time Machine") — VERIFIED LIVE
Live task: bootstrap-simulate 100-trade futures from an R-multiple pool derived from LIVE BTCUSDT 1h candle returns (1% risk unit), on Stratex-Server.
Live data: 99 live hourly returns (sample expectancy -0.0334 R, win rate 0.434).
Result: 2000 paths, p_profit 0.354, median final -3.77 R, p_kill_breach 0.949 at 1% risk / 5% kill line, p_ruin 0.000. The high kill-breach rate is the module reporting honestly that this naive live return pool loses money — the finding, not a module defect. The disclaimer fired as designed ("not a forecast").

### IG-STR-05 — Multi-agent research desk + trade journal — VERIFIED LIVE
Live task: run the full desk chain (scan -> analyse -> plan -> risk checklist) on a real BTCUSDT setup built from the live levels, plus the hash-chained journal, on Stratex-Server.
Failure case (first run, ~22:30 IST): setup built with the nearest resistance BELOW the entry as target (59410.63 vs entry 59580.01). The fail-closed checklist caught it: target_above_entry FAILED, R:R 1.08 vs min 1.50 FAILED, checklist passed=false, plan stayed a DRAFT memo. The guard works live.
Valid case (second run, ~22:35 IST): well-formed long — entry 59598.64, invalidation 59423.08 (nearest live support below), target 59988.00 (nearest live resistance above), R:R 2.22. Checklist passed 1/1 (all five items ok, incl. risk_amount 100.00 vs cap 200.00); analysis trend "down", aligned=false (recorded, not hidden — the memo does not pretend the setup is with-trend). Plan status: "DRAFT — research memo only, not an order".
Journal: two entries appended to a /tmp scratch journal, hash chain verified valid (verify_chain True, 2 entries read back), scratch file deleted afterwards (verified absent). No production file touched.

## Task-level verdict: PARTIAL — 5/5 items exercised live; two acceptance legs NOT RUN

The per-item live leg is done and passing for all five. The board acceptance's extreme-condition test has three parts; only the first is complete:

1. Live demo-daemon cycle on real market data — DONE as far as these items allow. The daemon is cycling live (see environment state); each module ran on live data in the daemon's own checkout. But these modules are NOT wired into the daemon cycle and write nothing to the live ledger — so there is no per-item ledger evidence to file, and none can exist without a consumer.
2. Failure injection (venue disconnect, stale feed) — NOT RUN. Excluded by the task brief: awaits a coordinator ruling, and the owner stop order (~16:42 IST 2026-11-24) still freezes server moves. No injection of any kind was attempted.
3. Full-allowlist load scan — NOT RUN. No allowlist applies to these five research utilities (they take caller-supplied data, no venue allowlist); the daemon's own full-allowlist scan is a separate live leg, not exercised here.

No item failed live, so no named fix task is filed from this record. What is owed is a coordinator decision, not a code fix: whether the injection + load-scan legs are (a) ruled out of scope for these five research-only items (they have no venue contact to inject against and no allowlist to scan), or (b) scheduled as a separate live leg with the stop order lifted. STR-070 goes IN_REVIEW on this evidence; closure is Muse's call.

## Observations (not verdicts — for the coordinator)

- /health reports status "degraded" only because market_data is UNKNOWN ("MARKET_DATA_NOT_REPORTED"); trading_capable and trading_engine are ok and the daemon evaluated 7.4s before the probe. Whether the market-data flag gap is itself a defect is outside this task's five items.
- Latest forward_signal_log entries are REJECTED with "STRATEGY_ERROR: frozen strategy strategy_swing was deleted by TASK-STR-CLEANUP-001" (timestamp 1795532400, 2026-11-24 16:20 UTC). The forward paper experiment is rejecting signals for a deleted frozen strategy — worth a look by whoever owns the forward experiment (experiment id d79eff4e-e3f2-4f02-80bb-cece7e642897).
- daily_loss_breaker_state.json is stale: day 2026-11-15, updated 2026-11-15T00:00:20+05:30 — nine days old. Either the breaker is not updating or its state file is not the live one.
- Stratex-Server checkout is 3db55adf, behind main ca6de826 — but the six exercised files are byte-identical to main, so this run's evidence is unaffected.
- The probe scripts are kept in the worker's workspace (str070_live_probe_2230.py, str070_live_probe2_2235.py, raw outputs /tmp/str070_live_evidence_2230.txt and /tmp/str070_live_evidence_2235.txt) — not committed; the evidence above is the filed record.

— Muse 5
