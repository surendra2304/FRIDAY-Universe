# TASK-STR-072 — PRODUCTION-VERIFY: Stratex corpus IG-STR-11, IG-STR-12, IG2-STR-01, IG2-STR-02, IG2-STR-03

- **Claim:** hub #1483 comment 7137567513 (2026-11-24 ~21:52 IST), under the central pool pull model (owner order ~21:25 IST, directive 7136890552; pool order announcement 7137277063: Wave 1 Stratex first; aggressive burn order 7137435150).
- **Branch:** `muse13/task-str-072-prod-verify`, created from main `7b56420379eb74b6752e48f227751d4663b7e62d`, verified by read-back. No claim PR — board flip rides in the work PR (M5 precedent, coordinator 21:17 watch 7137288514).
- **Board record (main 7b564203, blob 740bad7a0e, 21,015 lines, verified first-hand):** AVAILABLE / owner null / P1, no blockers. STR-070 claimed by M5; STR-071 pre-staged by M3 — left for M3, took next in order.
- **Pre-staged next:** TASK-VOI-030 (run 17; per the coordinator's VOI-040 ruling for M7 — acceptance-run sequencing is coordinator-held).
- **Released this run:** TASK-VOI-035 → pool (blocked: calm window + owner stop order; flip rides in the consolidated board PR).
- **Standard:** owner implementation standard (directive 7136696000) — merged code is NOT implemented. This task closes ONLY on live extreme-condition evidence per item, never on a merge. A failing item gets a named fix task filed from this record; never mark a failing item verified.

## Items under verification

| Item | Title | Board status | PR | Code on main 7b564203 (verified present) |
|---|---|---|---|---|
| IG-STR-11 | Prediction-market research lane (read-only) | DEPLOYED | #476 | `Stratex/rigorous_backtest/ig/prediction_lane.py`, `ig/__init__.py`, `ig/tests/test_prediction_lane.py` |
| IG-STR-12 | Strategy stacking (research) + stack/MT5 evaluation | DEPLOYED | #477 | `Stratex/rigorous_backtest/ig/strategy_stacking.py`, `ig/__init__.py`, `Stratex/docs/IG_STACK_EVALUATION.md`, `ig/tests/test_strategy_stacking.py` |
| IG2-STR-01 | Vectorized parameter-sweep harness for Stratex RD (vectorbt pattern) | MERGED | #668 (merge 2b08d1158e) | `Stratex/research/sweep_harness/harness.py`, `__init__.py`, `Stratex/tests/test_ig2_sweep_harness.py` |
| IG2-STR-02 | Selective CCXT venue adapter for gap venues (demo/testnet only) | MERGED | #671 (merge 0480df1ae6) | `Stratex/stratex_ccxt_adapter/extra_venues.py`, `Stratex/tests/test_ig2_ccxt_extra_venues.py` |
| IG2-STR-03 | Vibe-Trading research layer for Stratex (pattern only) | MERGED | #677 (merge 302c1f645c) | `Stratex/research/vibe_layer/committee.py`, `factors.py`, `spec_parser.py`, `__init__.py`, `Stratex/tests/test_ig2_vibe_layer.py` |

Existence check 2026-11-24 ~21:55 IST: all 16 files present on main 7b564203 (recursive tree, 7,538 blobs, not truncated). Existence is NOT verification — it is only the starting point.

## Live verification plan (per item)

Acceptance (board record): live demo-daemon cycle on Stratex-Server on real market data + failure injection (venue disconnect, stale feed) + full-allowlist load scan; results filed from the live ledger. For EACH item: run it in the live agent on a real task, file live evidence (what ran, on which server, with what result, incl. the failure case).

- **IG-STR-11 (prediction lane, read-only):** run the lane live against a real prediction market feed; record the lane output vs the underlying market; failure case: feed stale/disconnect — lane must degrade read-only, no order path touched.
- **IG-STR-12 (strategy stacking + MT5 eval):** run a stacked strategy evaluation live; record stack output and the MT5 evaluation leg; failure case: one stack leg failing — evaluation must report, not silently pass.
- **IG2-STR-01 (sweep harness):** run a live vectorized sweep over a real parameter grid; record sweep time, grid size, top results; failure case: degenerate grid / empty result set handled explicitly.
- **IG2-STR-02 (CCXT extra venues, demo/testnet only):** connect a gap venue in demo/testnet; record venue handshake + a read-only market-data pull; failure case: venue disconnect — adapter must fail closed, never fall back to a live venue.
- **IG2-STR-03 (vibe layer):** run a committee evaluation from a real spec; record parsed spec, committee votes, factors; failure case: malformed spec — parser must reject with a named error, not hallucinate defaults.

## Gate (decision owed)

**Stratex-Server read route — RESOLVED for read-only legs** by coordinator ruling, 21:57 watch 7138466832 §3: read-only live legs (ledger read, daemon state, market-data check) are NOT moves — they proceed now under the owner's implement-all order. **Failure injection (venue disconnect, stale feed) on the live demo daemon is a live change — HELD; it needs separate owner clearance.** The STR-072 failure-injection legs wait on that clearance; they are NOT run in this filing.

## Live legs — read-only, run 2026-11-24 ~22:50–23:00 IST

Route: bridge `run_shell`, server 4 (Stratex-Server) direct — proven first-hand this run (M5/M15 used the S2→ssh hop; the direct server-4 route works and is the documented one). Driver: `~/workspace/muse13/str072/str072_live_driver.py` (run under `/opt/friday_universe/venv/bin/python`, the daemon's venv: ccxt 4.5.89, numpy 2.2.6; system python3 has neither). Deployed item files on Stratex-Server are byte-identical to main `37e030c7` (all 7 git blob SHAs match first-hand). Bridge flaked twice with empty replies during this run (known flakiness, retried OK). One driver bug found and fixed in-run: `dataclasses` needs the dynamically-loaded module registered in `sys.modules` (first run failed all dataclass modules with `AttributeError: 'NoneType' object has no attribute '__dict__'`).

**Route probe (first-hand):** host `stratex-server`, up 13:00, load 0.52. `Stratex.service` active; `Stratex-Daemon.service` active, MainPID 13273 (same PID M5/M15 saw), NRestarts 0, running. `/health` :8003: `trading_capable` ok, `trading_engine` ok, engine healthy, env `binance_futures_demo`, balance 10456.81, 30 open positions, unrealized PnL 104.98, last evaluation 4.6 s fresh, Oracle DB connected, status `degraded` only because market_data is `unknown` ("heartbeat omits market-data flags"). Live ledger `Stratex/paper_trade_ledger.jsonl`: 3 trades; last BTCUSDT SHORT +188.30 gross PnL.

**Shared real market data:** Binance public klines, BTCUSDT 1d × 365 (first close 87369.96, last 59732.14) — fetched live on the server, keyless, read-only.

### IG-STR-11 — LIVE-VERIFIED (read-only)
`PredictionLaneCollector` vs the live Polymarket Gamma API: 5 markets fetched, 0 skipped; first market "Xi Jinping out before 2027?" (volume 17,504,109), implied Yes 0.0165 / No 0.9835, prob sum 1.0. Failure cases: malformed record (`{"id": "x"}`, no question/outcomes) parses to None — skipped, never repaired; simulated feed disconnect raises `ConnectionError` and surfaces — no order path exists in the module (no wallet/keys/POSTs). Failure-injection leg (stale feed on the live lane) HELD per the ruling.

### IG-STR-12 — PARTIAL (stacking live-verified; MT5 leg open)
Stack composed live from the real closes: two MA legs (10/50 @ 0.6, 20/100 @ 0.4), 365 periods, total return −3.3%, max drawdown 16.3%, contributions +0.095 / −0.108. Failure case: misaligned series raises `ValueError: series are misaligned: lengths [364, 365]` — reported, not silently passed. **MT5 evaluation leg NOT RUNNABLE on Stratex-Server: no `MetaTrader5` library/terminal on the host (`ModuleNotFoundError`).** Open finding FIX-02 below — the stacking half is live-verified, the MT5 half is not, and the item is NOT marked verified.

### IG2-STR-01 — LIVE-VERIFIED (read-only)
Vectorized sweep on the 365 real closes, grid fast (10,20,30) × slow (50,100,200), fee 5 bps: 9 combos in 0.0 s; best fast=10/slow=50, net return +13.6%, Sharpe 0.63, Sortino 0.77, maxDD −18.7%, profit factor 1.15, 5 trades. Walk-forward (4 folds): folds 1–3 no eligible combo (too few trades in short train windows — reported, not hidden); fold 4 winner holds OOS (train Sharpe 0.54 → test 0.737). Failure cases: oversized grid (88,804 combos) raises `GridTooLargeError: grid has 88804 combos > cap 4096`; degenerate grid (fast=slow=50) yields 0 results, best None — handled explicitly.

### IG2-STR-02 — PARTIAL (bitget live-verified; registry wrong for 3 venues)
Venue matrix, live on Stratex-Server (ccxt 4.5.89):
- **bitget — WORKS:** constructed, sandbox pinned, live ticker BTC/USDT last 59805.65 / bid 59741.13 / ask 59744.88 (agrees with Binance ~59732 — real market data).
- **kraken — FAILS at construction:** `TypeError: 'NoneType' object is not iterable` — ccxt 4.5.89 has no Kraken testnet URL (`urls['test']` is None), so `set_sandbox_mode(True)` crashes. Registry claims `testnet: True` — wrong for this ccxt version.
- **kucoin — FAILS the same way:** no testnet URL in ccxt 4.5.89; registry claim wrong.
- **gateio — FAILS:** `UnsupportedVenue: installed ccxt has no 'gateio'` — not present in ccxt 4.5.89 (renamed to `gate`).
- **hyperliquid — constructs, no data:** BTC/USDC ticker last null, 0 OHLCV candles — testnet reachable but returns no market data.
- **mexc — correctly refused:** `LiveTradingRefused` (no testnet mode) — by design.
- Fail-closed design holds everywhere checked: `sandbox=False` → `LiveTradingRefused`; native `binance` → `UnsupportedVenue`; simulated venue disconnect → `ConnectionError` propagates, no fallback to any live venue. **Item NOT verified — FIX-01 below.**

### IG2-STR-03 — LIVE-VERIFIED (read-only)
Real spec parsed: "backtest ma_crossover on BTC/USDT with fast=10 slow=50 lookback 365 fee 5bps" → plan ma_crossover/BTC/USDT, sweep grid fast (10,) slow (50,). Momentum-20d factor IC on the real closes: **0.1244** (measurable signal). Committee review of the real evidence (IC 0.1244, Sharpe 0.63, maxDD −18.7%, 5 trades, no OOS): verdict **WATCH, score 0.575** — signal adopt, risk watch, evidence reject (5 trades < 30), robustness watch. The committee correctly did NOT adopt on thin evidence. Failure cases: malformed spec → `ValueError: unknown strategy 'nonsense'; supported: ma_crossover, momentum, mean_reversion, bollinger`; inverted windows → `ValueError: fast window must be < slow window`.

## Verdicts (read-only legs only; failure injection still held)

| Item | Read-only live leg | Verdict |
|---|---|---|
| IG-STR-11 | live Gamma fetch + failure cases | LIVE-VERIFIED |
| IG-STR-12 | stack on real closes + failure case | PARTIAL — MT5 leg open (FIX-02) |
| IG2-STR-01 | sweep + walk-forward on real closes + failure cases | LIVE-VERIFIED |
| IG2-STR-02 | CCXT gap venues on testnet | PARTIAL — kraken/kucoin/gateio broken (FIX-01) |
| IG2-STR-03 | real spec + real IC + committee | LIVE-VERIFIED |

## Fix tasks named from this record (coordinator to file/board — new STR numbers are the coordinator's)

- **STR-072-FIX-01 — CCXT EXTRA_VENUES registry wrong for fleet ccxt 4.5.89:** `kraken`/`kucoin` claim `testnet: True` but ccxt has no testnet URLs for them (`set_sandbox_mode(True)` crashes with TypeError); `gateio` is absent from installed ccxt (renamed `gate`). Fix: correct the registry to the installed ccxt version (or pin a ccxt version that has these testnets) + a live construction smoke test per venue. Evidence: this doc, IG2-STR-02 section.
- **STR-072-FIX-02 — MT5 evaluation leg has no host:** no `MetaTrader5` on Stratex-Server, so IG-STR-12's MT5 evaluation leg cannot run there. Fix: scope the leg — either a host with an MT5 terminal/library, or a coordinator ruling that the leg is non-applicable on Linux fleet hosts. Evidence: this doc, IG-STR-12 section.

## Five states

- implemented: PARTIAL (3 of 5 items live-verified read-only; 2 partial)
- tested: PARTIAL (live tests run per above; failure-injection legs held)
- merged: NO (work PR filed this run — see below)
- deployed: YES (item code byte-identical on Stratex-Server; daemon live)
- production-verified: NO (not until failure-injection legs + FIX-01/FIX-02 close)

## Next steps

1. ~~Read each item's code on main + its tests; record what each item actually does (claim vs code).~~ Done — code read, interfaces recorded above.
2. ~~Await / chase the Stratex-Server scoped read-only route grant.~~ Resolved by coordinator ruling 7138466832 §3 (read-only legs proceed now).
3. ~~Run the live legs per item; file live evidence here as it lands.~~ Read-only legs run and filed above; failure-injection legs HELD on owner clearance.
4. File the work PR (evidence doc + board flip STR-072 AVAILABLE → CLAIMED, owner muse_13) — in progress this run.
5. Failure-injection legs (venue disconnect, stale feed on the live demo daemon) when owner clearance lands; FIX-01/FIX-02 tracked via the coordinator.
