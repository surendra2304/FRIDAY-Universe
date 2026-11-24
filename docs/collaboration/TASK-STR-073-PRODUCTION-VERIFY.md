# TASK-STR-073: PRODUCTION-VERIFY Stratex corpus items IG2-STR-04..08 — live evidence

Worker: Muse 15. Claim: hub #1483 comment 7137824560, 2026-11-24 ~21:57 IST.

Branch: muse15/task-str-073-production-verify-ig2-str-04-08 (claim PR #1684 merged 3a2009b8, 22:39:47 IST; work continues on the same branch).

Probe runs: 2026-11-24 ~23:02 IST, ~23:13 IST, ~23:21 IST and ~23:25 IST, first-hand by Muse 15.

Server: Stratex-Server (13.211.78.20) via bridge run_shell on Server 2 -> ssh with the S2 Oracle key. Read-only probes, except /tmp scratch files (probe scripts, session log, whale/defi scratch stores, result JSONs) — all created, verified, deleted; net-zero production-state change. Verified absent afterwards (`ls /tmp/str073_*`: no such file).

No daemon start/stop/restart, no trades/orders, no config or code changes, no failure injection, no moves of any kind.

## What each item is (board records, verified first-hand)

All five are merged research utilities (owner muse_ai, IG Repo Wave 2):

- IG2-STR-04: Walk-forward validation gate for Stratex RD candidates (merged PR #683) — `Stratex/rigorous_backtest/ig/walkforward_gate.py`
- IG2-STR-05: Backtest=live parity harness (merged PR #693) — `Stratex/rigorous_backtest/ig/parity_harness.py`
- IG2-STR-06: Deterministic event-replay log for Stratex demo sessions (merged PR #696) — `Stratex/rigorous_backtest/ig/event_replay.py`
- IG2-STR-07: On-chain/whale-flow tracker for Stratex research, free endpoints only (merged PR #675) — `Stratex/research/whale_flow_tracker.py`
- IG2-STR-08: DeFi LP/yield monitor, DeFiLlama free API (merged PR #680) — `Stratex/research/defi_yield_monitor.py`

Every board record says the same thing: "Post-merge: fleet CD deploy -> production probe" — none of the five is wired into the live daemon, and none feeds any production engine. That bounds what "run it in the live agent" can mean for these items: the live exercise is running each module, in the live agent's own deployed checkout on Stratex-Server, on live market data, on a real task — which is what was done. No ledger entry exists for any of them, because there is no consumer to write one; that is a property of the items, not a gap in the probe.

Byte-identity check: all five module files on Stratex-Server are md5-identical to main 3a2009b8 (walkforward_gate 40a1bab5…, parity_harness 3d3029bc…, event_replay fa20bb17…, whale_flow_tracker 38889199…, defi_yield_monitor 18df41c4…). The code exercised live IS current main code. (Server checkout itself is 3db55adf, behind main 3a2009b8 — see Observations.)

Source note: PRODUCTION-VERIFICATION-PROGRAMME.md is NOT in the repo (coordinator confirmed missing). The acceptance below is taken verbatim from the TASK-STR-073 board record itself, read first-hand from the board snapshot.

## Live environment state (all probes)

- Stratex-Server up 13:21, load 0.62. Stratex.service ACTIVE, Stratex-Daemon.service ACTIVE, MainPID 13272, NRestarts 0. Python 3.10.22, requests 2.34.2 in /opt/friday_universe/venv.
- /health :8003 at 2026-11-24T17:32:29Z: status "degraded" (market_data state UNKNOWN — "MARKET_DATA_NOT_REPORTED", heartbeat omits market-data flags); trading_capable ok; trading_engine ok ("multi-venue daemon heartbeat fresh, pid alive"); daemon_balance 10457.47490603; daemon_last_evaluation 23.5s old; open_positions 30; unrealized_pnl 95.27; environment binance_futures_demo; DEMO_ENVIRONMENT warning (Binance Futures demo; Pepperstone pending-approval); database connected (Oracle SELECT 1 FROM DUAL ok).
- Daemon log tail (17:54:44 UTC): live strategy evaluation in progress at probe time (e.g. strategy_adx_ema_bare on binance_futures:ALGOUSDT 4h: NO_SIGNAL). The daemon IS cycling live on real market data.
- paper_trade_ledger.jsonl: 3 lines only. forward_signal_log.jsonl: 770 lines; latest signals timestamped 1795536000 (2026-11-24 17:20 UTC) — see Observations.
- daily_loss_breaker_state.json is STALE (day 2026-11-15) — see Observations.

## Per-item verdicts

### IG2-STR-04 — Walk-forward validation gate — VERIFIED LIVE

Live task: run the gate over 600 LIVE BTCUSDT 1h candles (Binance public REST, fetched from the server; 2026-10-30 18:00 UTC -> 2026-11-24 17:00 UTC; first close 76661.13, last close 60059.37) with a mean-cross candidate, train 200 / test 100, 4 rolling windows, fit_fn selecting the window (5/10/20) on the TRAIN segment only.

Result: the gate ran end-to-end and CORRECTLY FAILED the candidate — passed=false; pooled 8 test trades, 2 wins, win rate 0.25, expectancy_net -0.00958, profit_factor_net 0.4877, total_return_net -7.70%, max_drawdown_net -9.92%; 0/4 windows positive (window expectancies -0.0194, -0.0151, -0.0204, -0.0044). Failing checks: pooled_test_trades_gte_min, pooled_expectancy_gt_0, pooled_profit_factor_gte_min, positive_window_fraction_gte_min. `require_gate()` raised GateFailed naming exactly those four checks, as designed. The candidate losing money on live data is the finding, not a module defect — the module's job is to refuse such a candidate, and it did, with train-only fitting honoured (params_from_train_only true in every window).

### IG2-STR-05 — Backtest=live parity harness — VERIFIED LIVE

Live task: run the same mean-cross strategy definition unchanged through the batch BacktestRunner and the streaming LiveRunner over the same 600 live BTCUSDT 1h bars, then replay a recorded live session through the backtester.

Result: run_parity_check identical=true — signals 146/146, orders 15/15, fills 15/15, first_divergence null. replay_parity identical=true — 600 bars replayed, recorded orders 15 and fills 15 match the backtester's orders/fills exactly. One strategy definition, two runners, zero divergence on live data.

### IG2-STR-06 — Deterministic event-replay log — VERIFIED LIVE

Live task: record the LiveRunner session over the 600 live bars (with the IG2-STR-05 strategy) into a hash-chained log, then verify determinism by replay.

Result: 778 events recorded (1 session_start, 600 market, 146 signal, 15 order, 15 fill, 1 session_end). verify_deterministic: deterministic=true, replays_identical=true, sealed_digest_matches=true, stream_digest 5f7d38833fef24943c87d07de651400f60be60f64d08e07522ac6b49bc5e1560. The log was a /tmp scratch file, deleted afterwards (verified absent). No production file touched.

### IG2-STR-07 — On-chain/whale-flow tracker — NOT VERIFIED (live defect found)

Live task: poll all three free sources live on Stratex-Server and run the detector over the real payloads (probe 2026-11-24 17:51:50 UTC).

Result — two of three legs verified live, one leg dead:

- DexScreener leg VERIFIED: all three symbol searches returned 30 pairs each. BTC: 30 pairs, 1h volume $61,250 vs 24h $1,195,211 (share 5.12%, below the 25% spike bar), buys 281 / sells 251 (ratio 1.12, below the 2.0 bar). ETH: 30 pairs, 1h $3,202,758 vs 24h $82,544,396 (3.88%), buys 4469 / sells 4276 (1.05). SOL: 30 pairs, 1h $1,369,899 vs 24h $22,394,802 (6.12%), buys 1410 / sells 1526 (1.08). Detector correctly emitted no signals — the market was quiet by the module's own bars, and the numbers prove it looked.
- CoinGecko leg VERIFIED: BTC $59,969 (-2.55% 24h), 24h volume $31.86B; ETH $1,681.24 (-3.20%), $12.02B; SOL $69.51 (-5.43%), $2.81B. All three parsed; baselines written for all three coins (first poll, so no spot-volume-spike signal can fire yet — by design).
- DeFiLlama TVL leg DEAD LIVE: /v2/chains returned 426 rows, but the rows carry NO `change_1d` field — keys are chainId, cmcId, gasTokenGeckoId, gecko_id, name, tokenSymbol, tvl. `parse_defillama_chains` therefore returns {} for every chain, and `detect_tvl_shifts` can never fire a TVL_SHIFT signal. Live TVL is present in the payload (Ethereum $35,875,574,666; Solana $4,543,496,630; Arbitrum $1,220,742,604) but the module cannot see the 24h change. The unit test fixture (`Stratex/tests/test_ig2_str07_whale_flow.py:40-42`) assumes `change_1d` exists — a fixture-only assumption that does not hold against the live endpoint. poll_once() emitted 0 signals overall; the 0 is honest for the DexScreener/CoinGecko legs and vacuous for the TVL leg.

Fix task owed from this record: **TASK-IG2-STR-07-FIX-01 — Whale-flow TVL leg reads a field the live DeFiLlama /v2/chains payload does not carry.** Repair `parse_defillama_chains` to obtain the 24h TVL change from a live source (e.g. per-chain /v2/historicalChainTvl) or drop the TVL leg, and correct the test fixture to the live payload shape (no `change_1d`). Do NOT mark IG2-STR-07 verified until the TVL leg fires or is removed on live evidence.

### IG2-STR-08 — DeFi LP/yield monitor — VERIFIED LIVE

Live task: poll the DeFiLlama yields API live on Stratex-Server for the default watchlist.

Result: /pools returned 14,898 pools. All 4 watched pools snapshotted, all NEW_POOL (first poll, no history to diff against): aave-v3 USDC on Ethereum APY 2.65%, TVL $926,898,282; aave-v3 WETH on Ethereum APY 1.41%, TVL $484,306,360; uniswap-v3 WETH-USDC on Base APY 89.15%, TVL $95,220,364; lido STETH on Ethereum APY 2.39%, TVL $16,277,983,492. research_note generated with all four pools. Snapshots/changes went to /tmp scratch files, deleted afterwards (verified absent). No wallet, no funds — read-only public API.

## Task-level verdict: PARTIAL — 4/5 items verified live; 1 item NOT verified; two acceptance legs NOT RUN

The per-item live leg is done for all five, with 4 passing and 1 failing on a genuine live defect (IG2-STR-07 TVL leg — fix task TASK-IG2-STR-07-FIX-01 named above). The board acceptance's extreme-condition test has three parts; only the first is complete:

1. Live demo-daemon cycle on real market data — DONE as far as these items allow. The daemon is cycling live (see environment state); each module ran on live data in the daemon's own checkout. But these modules are NOT wired into the daemon cycle and write nothing to the live ledger — so there is no per-item ledger evidence to file, and none can exist without a consumer.
2. Failure injection (venue disconnect, stale feed) — NOT RUN. Held fleet-wide pending owner clearance; no injection of any kind was attempted. Coordinator watch 7138911209 ruling 4 ruled injection + full-allowlist load-scan out of scope for STR-070's five research-only items; whether that ruling extends to STR-073 is an open question before the coordinator — this record assumes nothing and records both legs as NOT RUN.
3. Full-allowlist load scan — NOT RUN. No allowlist applies to these five research utilities (grep: no "allowlist" string in any of the five modules; they take caller-supplied data / public free endpoints, no venue allowlist); the daemon's own full-allowlist scan is a separate live leg, not exercised here.

STR-073 goes IN_REVIEW on this evidence; closure is Muse's call. IG2-STR-07 stays unverified until TASK-IG2-STR-07-FIX-01 lands and is re-probed live.

## Observations (not verdicts — for the coordinator)

- /health reports status "degraded" only because market_data is UNKNOWN ("MARKET_DATA_NOT_REPORTED"); trading_capable and trading_engine are ok and the daemon evaluated 23.5s before the probe. Whether the market-data flag gap is itself a defect is outside this task's five items.
- Latest forward_signal_log entries are REJECTED with "STRATEGY_ERROR: frozen strategy strategy_swing was deleted by TASK-STR-CLEANUP-001" (timestamp 1795536000, 2026-11-24 17:20 UTC; logged_at 1795539635). The forward paper experiment is rejecting signals for a deleted frozen strategy — same as STR-070 found; worth a look by whoever owns the forward experiment.
- daily_loss_breaker_state.json is stale: day 2026-11-15, updated 2026-11-15T00:00:20+05:30 — nine days old. Either the breaker is not updating or its state file is not the live one. Same as STR-070 found.
- Stratex-Server checkout is 3db55adf, behind main 3a2009b8 — but the five exercised files are byte-identical to main, so this run's evidence is unaffected.
- Bridge transport was flaky during this run: roughly half of run_shell calls failed with "MCP request did not complete", "MCP event stream ended before the matching result", or an IncompleteRead, including two failed deliveries of the main probe script. Every call was retried until a verified result arrived; no evidence was lost, but the bridge's reliability tonight is itself worth noting.
- Probe-script self-correction (disclosed): the first probe's own source-check for CoinGecko/DeFiLlama assumed a dict payload and errored with "'list' object has no attribute 'get'" — that was my probe code, not the modules (both modules handle list payloads correctly). The follow-up probe used a logging fetcher and showed all three endpoints healthy (DexScreener 30 rows per symbol, CoinGecko 3 rows, DeFiLlama 426 rows).
- The probe scripts are kept in the worker's workspace (str073_live_probe.py, str073_probe2.py, str073_ship.py, str073_deliver.py, str073_deliver2.py, str073_run.py, str073_fetch2.py; raw outputs /tmp/str073_result_clean.json and /tmp/str073p2_result_clean.json) — not committed; the evidence above is the filed record.

— Muse 15
