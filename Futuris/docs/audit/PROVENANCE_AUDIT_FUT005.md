# TASK-FUT-005 — Futuris Data-Provenance Audit (2026-11-15)

Scope: every input Futuris forecasts from — series, source, refresh cadence —
verified real / current / honestly labelled in outputs. Code trace on fresh
main (base 337a1e3, PR #280 head at audit start) plus batched read-only live
probes of production Futuris (Server 1, port 8004) on 2026-11-15 ~13:47 IST
(08:17 UTC). statsforecast is NOT installed in production (post-ARM, owner
decision): every model adapter raises `StatsForecastUnavailableError`, the
pipeline/scheduler skip with an explicit log line, and no forecast is
computed from a substitute model. That behaviour is honest and unchanged.

## Per-input provenance table

| # | Input (series / data) | Source (code) | Refresh cadence | Real? | Label in outputs | Verdict |
|---|---|---|---|---|---|---|
| 1 | Scheduler telemetry series `checkout:requests_per_minute` (5-min steps) | `SyntheticTelemetryConnector` (deterministic generator, seed 42) via `connectors/factory.py`; `FUTURIS_TELEMETRY_SOURCE` default `synthetic` (`infra/config.py`) | ingest job 15 min; forecast refresh 60 min (`infra/scheduler.py`) | NO — generated | `evidence_class=synthetic`, `evidence_source="telemetry:synthetic via SyntheticTelemetryConnector [SYNTHETIC data]"`, `input_telemetry_verified=false` (REL-018 `connectors/provenance.py`, fail-closed) | HONEST |
| 2 | NEXUS broker telemetry (optional source) | `NexusConnector` GET `{NEXUS_URL}/api/v1/telemetry`, only when `FUTURIS_TELEMETRY_SOURCE=nexus` | same scheduler jobs | Real if broker is real; NOT configured in production (default synthetic) | Derived from observation `source` strings by `resolve_provenance`; any fabricated marker (`synthetic/fallback/simulated/mock`) forces SYNTHETIC | HONEST (dormant) |
| 3 | VyralX trend telemetry `vyralx:trend:virality_index` | `VyralXConnector.fetch` GET `{VYRALX_URL}/v1/trends/telemetry`; on failure/circuit-open returns `_generate_fallback_observations` with `source="vyralx:fallback"` | scheduler when `FUTURIS_TELEMETRY_SOURCE=vyralx`; not the production default | Mixed: live when VyralX answers, generated when degraded | Fallback source contains `fallback` → provenance resolves SYNTHETIC (weakest-input rule) | HONEST (dormant) |
| 4 | Stratex trading telemetry (equity / volatility / drawdown / position_exposure / advisory_accuracy) | `TradingBotConnector.fetch` GET `{STRATEX_URL}/api/v1/telemetry/trading`; 404 → single status snapshot (`source=stratex:status_snapshot`, never a manufactured series); no API key → returns [] (fail-closed, FUT-001) | market forecast on request; scheduler dynamic-pair sync hourly | Real when Stratex answers. PRODUCTION STATE 2026-11-15: UNAUTHORIZED — risk payload reports `positions_data_status="unauthorized"`, `pair_discovery_status="unauthorized"` (the Futuris-side Stratex credential does not authenticate to Stratex's positions API) | Market router: requires fresh volatility+drawdown or HTTP 503 (no placeholder forecast); persisted forecast `evidence_class=live`, `evidence_source=stratex_telemetry`, `model_version="heuristic:telemetry_vol_rule@v2"` (TRUST-001: not labelled statsforecast) | HONEST but CURRENTLY UNAVAILABLE in production (credential mismatch — see Findings F4) |
| 5 | Stratex ticker price series `trading:{SYM}:price` | `TradingBotConnector.fetch_ticker_series` GET `/api/v1/telemetry/market/{SYM}` | on request (risk audit) | Real when reachable; [] when unconfigured | Feeds risk audit returns; labelled by this task (F1 fix) | HONEST after FUT-005 fix |
| 6 | Stratex positions + futures funding | `fetch_active_positions` GET `/api/v1/positions`; `fetch_futures_funding_telemetry` GET `/api/v1/ccxt/funding` | risk pulse 5 min; portfolio on request | Real when reachable; production: unauthorized (see #4) | Statuses exposed verbatim (`available/empty/unauthorized/not_configured/...`); funding returns `status` + `source`, never the old neutral 0.0001 estimate | HONEST |
| 7 | Core watchlist BTC/ETH/SOL (fallback pair list) | Hardcoded defaults in `discover_active_trade_pairs` | — | NOT a measurement — a research watchlist | Portfolio payload: `pair_discovery_source="core_watchlist"` HONEST. Pairs endpoint `GET /v1/risk/stratex/pairs`: hardcoded `"source": "stratex"` — MISLABELLED (live-verified) | **DEFECT F2 — fixed in this PR** |
| 8 | Stored observations (Oracle `observations` table) | Written by ingest job from the configured connector (#1–#3); read by risk audit / lifecycle / calibration resolution | continuous | Only as real as what was ingested (production: synthetic generator output) | Risk audit now labels `returns_source=stored_observations` (F1 fix); forecast rows carry their own evidence fields | HONEST after FUT-005 fix |
| 9 | Risk-audit return series (VaR/CVaR/Kupiec inputs) | Priority: stored observations → Stratex ticker → `_generate_calibrated_returns` (Student-t draws from hardcoded per-asset vol: BTC 2.5%, ETH 3.5%, SOL 4.5%, SPY 1.2%) | on request; portfolio per pair | Fallback is INVENTED. LIVE PROOF 2026-11-15: `GET /v1/risk/portfolio` returned `sample_size=100` (= the generator's size) for all 3 assets with full VaR/CVaR/Kupiec numbers and NO source label, while positions were unauthorized | NO label existed: no `returns_source`, no `evidence_class` in audit / stream-update / portfolio asset rows | **DEFECT F1 — fixed in this PR** |
| 10 | Fan-chart base price (risk pulse) | Verified position `current_price`, else hardcoded constants BTC 67000 / ETH 2600 / other 170 (`infra/scheduler.py` `stream_risk_pulse_job`) | 5 min broadcast | Fallback constants are stale invented prices; production path today (no verified positions) | Broadcast field named `current_price` with NO source label | **DEFECT F3 — fixed in this PR** (`price_source` + `evidence_class` added) |
| 11 | IntelX research context (exogenous sentiment / volatility modifiers) | `IntelXContextInjector.fetch_recent_research` (IntelX context/query APIs) + `fetch_durable_notice_context` (stored IntelX notices in Futuris DB) | per market forecast / engine run; lookback 7 d | Real when IntelX has research; synthetic baseline report explicitly filtered (`intelx-baseline-report` skipped); any failure → [] and neutral modifiers (1.0 / 1.0 / 0.0), never invented findings | Market payload: `intelx_context_included` bool; drivers name the finding when present, else the literal `intelx:market_liquidity_baseline` | HONEST |
| 12 | Caller-supplied telemetry (FRIDAY delegation `telemetry_data`, universe `context.point_estimate/...`) | Request payload, `api/routers/friday.py`, `core/universe_forecasting.py` | on request | Caller-asserted, unverifiable | `evidence_class=synthetic`, `evidence_source="caller-supplied telemetry_data in the FRIDAY delegation payload"` / `caller_supplied_context` | HONEST |
| 13 | Stored forecasts served back (`/trends`, `/v1/forecasts`, FRIDAY surfaces, `/simulate` base) | Oracle `forecasts` table rows written by #1/#4/#12 paths | on request | As labelled at write time | Every row carries `evidence_class` / `evidence_source` / `input_telemetry_verified` (FUT-002/003; live-verified 2026-11-15: `/trends` rows = synthetic / telemetry:synthetic / false). Scenario results inherit the base forecast's provenance; `perturbed_probability=null`, `probability_status=not_recomputed_by_scenario_engine` | HONEST |
| 14 | Model backend | statsforecast adapters (`models/adapters.py`, `models/selection.py`) | per forecast | NOT INSTALLED (post-ARM) | `StatsForecastUnavailableError` → 503 on API paths, explicit skip log per scheduler subscription (8 skips/cycle, 0 fits — FUT-003 production evidence). Forecast payloads name the actual producer (`heuristic:telemetry_vol_rule@v2` for market; pipeline refuses) | HONEST |
| 15 | Demo seed (180-day workspace) | `DemoSeeder` over `SyntheticTelemetryConnector`; startup seed gated OFF in production (`STARTUP_DEMO_SEED_ENABLED=false` default + non-prod env check); manual trigger is admin-only (`POST /v1/ecosystem/seed`) | manual only | Generated | Seeded forecasts flow through the same labelled paths (#1/#13) | HONEST, with nit F5 |
| 16 | Legacy `predict/*` deep modules (hash-derived numbers) | `Futuris/predict/*.py` | — | Fabricated by construction (md5-hash values) | Routers UNMOUNTED since TRUST-001 (app.py comment + include list verified); modules remain on disk for reference only | NOT SERVED — no action |
| 17 | Extra `/api/v1/futuris/*` routers (ensemble selector, explainability, drift detector, skill planner, counterfactual, quantum forecast, prediction market) | `predict/` + `futuris/services/*`, mounted in app.py | on request | Caller-parameter computations / in-memory simulations; they consume NO external telemetry and claim none | No provenance/evidence fields on their outputs — a reader cannot tell they are parameter-driven simulations from the payload alone | FLAG F6 — labelling or retirement is the FUT-002 residual ("extra routers retire-or-label"); not fixed here to avoid colliding with sibling crews' surfaces |
| 18 | Peer health / ecosystem probes | `ecosystem_adapter.probe_peers` | on request | Measured (HTTP probe) | `evidence_class` per peer in payload | HONEST |
| 19 | Memora forecast advisories (outbound) | `publish_forecast_advisory` publishes only persisted, evidence-backed forecasts | per market forecast | — | Carries the forecast's own provenance | HONEST |

## Findings

- **F1 (FIXED, this PR)** — Risk surfaces silently computed VaR/CVaR/Kupiec
  statistics from the synthetic calibrated-returns generator and presented
  them unlabelled. Production-verified live: with Stratex unauthorized,
  `GET /v1/risk/portfolio` reported `sample_size=100` of invented returns
  per asset. Fix: `returns_source` + `evidence_class` on the audit and
  stream-update payloads, per-asset `returns_source` plus
  `synthetic_return_assets` / `measured_return_assets` on the portfolio
  payload (`futuris/api/routers/risk.py`).
- **F2 (FIXED, this PR)** — `GET /v1/risk/stratex/pairs` hardcoded
  `"source": "stratex"` for what was, in production, the built-in core
  watchlist (same-minute portfolio payload: `pair_discovery_status=
  "unauthorized"`, `pair_discovery_source="core_watchlist"`). Fix: the
  endpoint now returns the connector's real `last_pairs_source` +
  `pair_discovery_status`. The pre-existing test that asserted the false
  label was updated with disclosure.
- **F3 (FIXED, this PR)** — The 5-minute risk pulse broadcast a fan chart
  whose `current_price` fell back to hardcoded constants (BTC 67000) with no
  label; with positions unauthorized this fallback is the production path.
  Fix: fan-chart payload gains `price_source`
  (`verified_position_price` / `hardcoded_fallback_estimate`) and
  `evidence_class` (`live` / `synthetic`) (`futuris/infra/scheduler.py`).
- **F4 (FLAGGED, not fixed — credential/ops, not labelling)** — Futuris's
  Stratex reads are unauthorized in production (`positions_data_status=
  "unauthorized"`): the configured Futuris-side Stratex credential does not
  authenticate to Stratex's positions/telemetry APIs, so every Stratex-fed
  input is currently unavailable and the fail-closed paths (503s, empty
  positions, watchlist labels) are what production actually serves. Fixing
  the credential pairing is an ops action for the coordinator/owner, not a
  code change in this audit's scope.
- **F5 (nit, flagged)** — `DemoSeeder` registers an active model
  `auto_arima@v1` with invented benchmark scores (`mae 40.2, ece 0.045,
  coverage 0.91`) in the model registry. Demo-seed scope only (production
  startup never seeds), but the registry row does not say it is demo data.
- **F6 (flagged)** — The `/api/v1/futuris/*` extra routers (#17) return
  simulation results with no evidence labelling. They consume no live
  inputs, so nothing synthetic is presented *as live telemetry*, but the
  payloads do not say what produced them. This is the known FUT-002
  residual (retire-or-label).
- **Staleness note** — The newest stored forecasts served by `/trends` were
  written 2026-11-14 (~19 h before the probe): with statsforecast absent
  the refresh job skips every cycle, so no new pipeline forecasts exist.
  The rows are honestly labelled synthetic; the staleness is a consequence
  of the post-ARM statsforecast decision, not a labelling defect.

## What "produced it" labels say today (post-fix contract)

- Pipeline/engine forecasts: statsforecast or an explicit 503/skip — never
  a substitute model.
- Market forecasts: `model_version="heuristic:telemetry_vol_rule@v2"` over
  live Stratex telemetry, or 503.
- Risk numbers: `returns_source` names the actual series origin;
  `evidence_class` is `synthetic` whenever the generator supplied returns.
- Fan charts: `price_source` + `evidence_class` name the price origin.
- Everything else forecast-shaped: `evidence_class` / `evidence_source` /
  `input_telemetry_verified` carried end-to-end (REL-018/FUT-002/FUT-003).
