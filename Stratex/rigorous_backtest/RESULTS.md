# TASK-STR-BT-001 — Rigorous backtest results (BACKTEST-OOS)

All performance figures are **out-of-sample only** (walk-forward folds W1–W5, OOS window 2024-07-01 → 2026-11-01; earlier data is warm-up/in-sample only) and **net of costs**: Binance USDT-M futures taker, 5 bps fee + 3 bps spread/slippage per side = **16 bps round trip**. Data: Binance Vision public mainnet archives (no API key exists or is needed); every dataset hash-pinned in `data_provenance.json`; gap audits: 0 missing bars everywhere. Testnet candles deliberately not used.

## Factory-family verdict: NO — the five winners do not survive honest OOS testing

**(a) Selection procedure** (per fold, rank 204 variants on in-sample trades only, legacy sort key; top 5 judged on the fold's OOS trades): pooled OOS 4854 trades, WR 32.2%, expectancy -0.230%/trade, PF 0.81. IS distribution per fold (variants with PF > 1): W1: 9/204 (median PF 0.70), W2: 5/204 (median PF 0.68), W3: 2/204 (median PF 0.69), W4: 0/204 (median PF 0.68), W5: 0/204 (median PF 0.68).

**(b) Original five variants** (as parameterized in strategy_variations.json):

| variant | OOS trades | WR | expectancy net | PF net |
|---|---|---|---|---|
| 182 (factory_macd_bb_confluence_5m_182) | 16595 | 32.1% | -0.180% | 0.54 |
| 181 (factory_macd_bb_confluence_5m_181) | 18494 | 31.4% | -0.169% | 0.42 |
| 183 (factory_macd_bb_confluence_5m_183) | 19119 | 22.3% | -0.164% | 0.27 |
| 184 (factory_macd_bb_confluence_5m_184) | 13272 | 31.9% | -0.193% | 0.62 |
| 187 (factory_macd_bb_confluence_15m_187) | 6354 | 23.9% | -0.171% | 0.44 |

**(c) Deployed modules** — see governed table. Note: winner_2 as coded is bit-identical to winner_1 (SL/TP 1.5/3.0, not variant 181's 1.0/2.0); winners 3 and 5 are coded 1.5/4.5, not their variants' 0.5/1.5. Three of the five deployed modules do not implement the variants they were promoted as.

## Governed set — BACKTEST-OOS (pooled BTC/ETH/SOL)

| strategy | tf | OOS trades | WR | expectancy net | PF net | max DD (compounded) |
|---|---|---|---|---|---|---|
| strategy_bb_reversion | 15m | 12308 | 32.0% | -0.198% | 0.68 | -100.0% |
| strategy_factory_winner_1 | 5m | 17150 | 32.4% | -0.178% | 0.54 | -100.0% |
| strategy_factory_winner_2 | 5m | 17150 | 32.4% | -0.178% | 0.54 | -100.0% |
| strategy_factory_winner_3 | 5m | 14729 | 24.0% | -0.191% | 0.58 | -100.0% |
| strategy_factory_winner_4 | 5m | 13467 | 32.0% | -0.191% | 0.62 | -100.0% |
| strategy_factory_winner_5 | 15m | 4880 | 24.2% | -0.187% | 0.73 | -100.0% |
| strategy_supertrend | 15m | 5098 | 26.2% | -0.142% | 0.82 | -100.0% |
| strategy_adx_ema | 4h | 77 | 59.7% | +1.190% | 1.57 | -30.8% |

adx_ema is the only positive governed strategy — positive expectancy in all five folds — but on only 77 trades (~1.9σ): a forward-demo-protocol candidate, not a conclusion. It was judged as a bare signal engine; production's downstream BTC-regime gate and LONG_ONLY constraint are not part of the module and are not reflected here. Every other governed strategy has negative expectancy in every fold; their gross expectancy is ≈ 0 — the signals carry no measurable gross edge and costs turn noise into a steady bleed.

## Discovery (wider library) — BACKTEST-OOS

Candidates: 58. Evaluated: 7. All other rows are UNTESTABLE with the reason recorded in `phase_discovery.json` (not evaluated — session compute budget ended and the run was terminated by a sandbox service restart at 7 of 58 modules; no numbers exist for them). Pooled metrics for evaluated rows are summary-level; full per-fold rows are regenerable with `run_all.py discovery`.

| strategy | tf | status | OOS trades | expectancy net | PF net | governance |
|---|---|---|---|---|---|---|
| strategy_adx_ema_mtf | 5m | EVALUATED | 1721 | -0.143% | 0.74 | DISABLED |
| strategy_adx_trend | 1h | EVALUATED | 1058 | -0.004% | 1.00 | UNREGISTERED |
| strategy_aggressive_scalper | 5m | EVALUATED | 128541 | -0.169% | 0.34 | DISABLED |
| strategy_aggressor | 1h | EVALUATED | 3391 | -0.083% | 0.93 | DISABLED |
| strategy_atr_breakout | 1h | EVALUATED | 870 | +0.011% | 1.01 | UNREGISTERED |
| strategy_bbi_blend | 1h | EVALUATED | 2703 | -0.141% | 0.90 | UNREGISTERED |
| strategy_bollinger | 1h | EVALUATED | 2838 | -0.203% | 0.81 | UNREGISTERED |
| strategy_breakout_retest | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_breakout_vol | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_channel_breakout | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_choppiness_breakout | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_donchian_observe_only | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_donchian_turtle | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_ehlers_hma | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_ema_crossover | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_fast_ema_cross | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_higher_highs | 1d | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_hybrid | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_kama_adaptive | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_kaufman_efficiency | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_mean_reversion_scalper | 5m | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_ml | 1h | UNTESTABLE | — | — | — | DISABLED |
| strategy_momentum | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_momentum_rotation | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_multi_month | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_pullback_ema | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_rsi_burst | 1h | UNTESTABLE | — | — | — | DISABLED |
| strategy_rsi_divergence_scalper | 5m | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_rsi_extreme | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_scalper | 1h | UNTESTABLE | — | — | — | DISABLED |
| strategy_scalping_breakout | 5m | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_supertrend_atr | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_swing | 1h | UNTESTABLE | — | — | — | DISABLED |
| strategy_trend_continuation | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_trend_daily | 1d | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_trend_pullback | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_vol_regime | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_volatility_breakout | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_volume_breakout | 1d | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_vwap_scalper | 5m | UNTESTABLE | — | — | — | UNREGISTERED |
| strategy_vwap_trend | 1h | UNTESTABLE | — | — | — | DISABLED |
| adx_ema_trend | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| arb_scanner | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| bollinger_rsi_reversion | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| breakout_momentum | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| ema_crossover | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| ensemble_strategy | 5m | UNTESTABLE | — | — | — | UNREGISTERED |
| grid_trading | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| ml_ensemble | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| options_pricing | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| pair_trading | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| prediction_enhanced | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| quantitative_engine | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| regime_detector | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| scalping_microstructure | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| sentiment_strategy | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| statistical_arbitrage | 1h | UNTESTABLE | — | — | — | UNREGISTERED |
| vwap_volume_profile | 1h | UNTESTABLE | — | — | — | UNREGISTERED |

## Harness trust checks

- Replication vs the legacy mass_backtester on real data: all_match = True (8 variants incl. all five winners; max abs deviation 0.0 on compared trades).
- Governed results reproduced bit-identically in two independent runs on re-fetched data (dataset hashes asserted equal before evaluation).
- Supertrend's backtest (WR 26.2%, PF 0.82) agrees with its exchange-verified forward record (WR 26.6%, Sep 2025 ledger) — the harness reads reality correctly where reality is independently known.
- Feature pipelines are causality-checked per module (truncated-series output must match full-series output); non-causal pipelines are rejected as UNTESTABLE.
- 9 unit tests cover mechanics only (simulation semantics, fold attribution, gap honesty, cost math, causality checker, legacy-loop equivalence). All pass.

## Data provenance (summary; full manifests incl. per-zip SHA-256 in data_provenance.json)

| dataset | rows | range (UTC) | missing bars | csv_sha256 |
|---|---|---|---|---|
| BTCUSDT_5m | 307008 | 2023-12-01 → 2026-10-31 | 0 | 3bb402d7d7932db80bb48aa1eec18e3ab6b28a239901f5fc8a4e34ccd146d663 |
| ETHUSDT_5m | 307008 | 2023-12-01 → 2026-10-31 | 0 | fc27ecee84aa053329ca1d01bef41f955a7e49ecad2dd13cce7d4f26d509d075 |
| SOLUSDT_5m | 307008 | 2023-12-01 → 2026-10-31 | 0 | 0f1acdf60a90b867a08a091247f4064f5933f0af5a00fc69f05663c1a18537b2 |
| BTCUSDT_15m | 108192 | 2023-10-01 → 2026-10-31 | 0 | 7b1c3d1c3fbf6e9034c376a162e8ff92d6870cc682258f0e0a4bb609ea328a67 |
| ETHUSDT_15m | 108192 | 2023-10-01 → 2026-10-31 | 0 | 4461a568e00a0f684883a06ce1dd8935492d5d10d6481ad1415f1a4b5d69f206 |
| SOLUSDT_15m | 108192 | 2023-10-01 → 2026-10-31 | 0 | b12ccb6984b2cf2b571e633058044994170fdcc267dbd4c3765a1041f8095fcd |
| BTCUSDT_1h | 27048 | 2023-10-01 → 2026-10-31 | 0 | f03a10c221d2c85df07f3d47050d4e0c5c886b6d372959512bf6f6791cb8bbcc |
| ETHUSDT_1h | 27048 | 2023-10-01 → 2026-10-31 | 0 | dec88e73b2666a8c2ca8fcd8a9753ebab8ccca9a67e6523ef9ab28022e0b8c4e |
| SOLUSDT_1h | 27048 | 2023-10-01 → 2026-10-31 | 0 | 972c5f1405c1d21835803786c4e1fe901287566fc11f49baf30455c1f412ba0c |
| BTCUSDT_4h | 6762 | 2023-10-01 → 2026-10-31 | 0 | f03a10c221d2c85df07f3d47050d4e0c5c886b6d372959512bf6f6791cb8bbcc |
| ETHUSDT_4h | 6762 | 2023-10-01 → 2026-10-31 | 0 | dec88e73b2666a8c2ca8fcd8a9753ebab8ccca9a67e6523ef9ab28022e0b8c4e |
| SOLUSDT_4h | 6762 | 2023-10-01 → 2026-10-31 | 0 | 972c5f1405c1d21835803786c4e1fe901287566fc11f49baf30455c1f412ba0c |
| BTCUSDT_1d | 1127 | 2023-10-01 → 2026-10-31 | 0 | f03a10c221d2c85df07f3d47050d4e0c5c886b6d372959512bf6f6791cb8bbcc |
| ETHUSDT_1d | 1127 | 2023-10-01 → 2026-10-31 | 0 | dec88e73b2666a8c2ca8fcd8a9753ebab8ccca9a67e6523ef9ab28022e0b8c4e |
| SOLUSDT_1d | 1127 | 2023-10-01 → 2026-10-31 | 0 | 972c5f1405c1d21835803786c4e1fe901287566fc11f49baf30455c1f412ba0c |

Source for all primary datasets: Binance Vision monthly klines archives, `https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/{timeframe}/`. 4h and 1d are resampled from the hash-pinned 1h datasets (complete buckets only). OANDA: not needed — every strategy in scope trades Binance markets in production; OANDA hosts only SMT-v2, which is not a library strategy module and already has an exchange-verified record (−$167). No API keys were requested or used anywhere.
