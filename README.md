# FRIDAY Universe

**Production Multi-Agent Intelligence Platform — 10 Autonomous Specialist Agents · 100+ Deep Modules · Real Open-Source Library Integrations · 434+ Passing Tests**

FRIDAY Universe is an enterprise-grade autonomous multi-agent intelligence platform where each specialized agent operates with independent domain models, production API surfaces, and real open-source library integrations — eliminating stubs in favor of verified algorithmic and computational engines.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FRIDAY (Orchestrator)                           │
│     Autonomous Problem Solver · Agent Runtime · Goal-Directed Browser  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Unified Gateway & Dispatch Bus
     ┌──────────────┬───────────────┼───────────────┬──────────────┐
     │              │               │               │              │
┌────┴────┐   ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴────┐   ┌─────┴────┐
│ Stratex │   │  VyralX   │   │  Cortex   │   │Inference │   │  Forge   │
│ Trading │   │  Content  │   │   CRM     │   │LLM Router│   │  Coding  │
└────┬────┘   └─────┬─────┘   └─────┬─────┘   └─────┬────┘   └─────┬────┘
     │              │               │               │              │
┌────┴────┐   ┌─────┴─────┐   ┌─────┴─────┐         │              │
│ Memora  │   │  IntelX   │   │  Futuris  │         │              │
│ Memory  │   │ Threat-OS │   │ Forecast  │         │              │
└─────────┘   └─────┬─────┘   └───────────┘         │              │
                    │                               │              │
              ┌─────┴─────┐                         │              │
              │ Sentinel  │─────────────────────────┴──────────────┘
              │ Security  │
              └───────────┘
```

The system operates 10 specialized services coordinated through a unified API Gateway and event-driven dispatch bus with circuit breakers, capability-based authorization, and distributed context consolidation.

---

## 10 Autonomous Agents & Deep Capabilities

### 1. FRIDAY — Central Orchestrator & Meta-Agent
- **Role:** Central coordinator, autonomous task decomposition, multi-agent dispatch, and harness execution.
- **Port:** `10000` | **Stack:** Python, FastAPI
- **Deep Modules & Wiring:**
  - `agent_runtime.py` — Live `FridayAgentRuntime` supporting step-by-step execution, typed tool registry, and session tracing.
  - `real_browser_agent.py` — Indexed DOM parser, selector resolution, form filling, and goal-directed web runs.
  - `real_harness_engineering.py` — Autonomous agent loop, context compaction, permission gating, verification, and state checkpoints.
  - `universe_dispatch_bus.py` — Resilient dispatch across all 9 specialists with circuit breakers and fallback execution.
- **API Surface:** `/api/v1/friday/*` and `/v1/agent/{capabilities,plan,execute,context/compact,browser/run,trace}`

### 2. Stratex — Trading & Financial Intelligence
- **Role:** Algorithmic trading, multi-venue order execution, quantitative portfolio management, and prediction markets.
- **Port:** `8003` | **Stack:** Python, Flask, Oracle Autonomous Database
- **Live Open-Source Integrations:**
  - **CCXT (`ccxt`)**: Multi-exchange unified market data (`fetch_ticker`, `fetch_order_book`), rate-limited execution, and cross-venue spatial arbitrage.
  - **Backtrader (`backtrader`)**: Event-driven backtesting with `BtSmaCrossoverStrategy`, Pandas OHLCV feeds, and trade performance analyzers.
  - **Vectorbt (`vectorbt`)**: High-speed vectorized signal generation, `vbt.Portfolio.from_signals`, DateTimeIndex-aligned series, and Sharpe/drawdown calculation.
  - **Freqtrade (`freqtrade` & `ta`)**: Minimal ROI and stoploss hyperopt parameter optimization over OHLCV arrays.
  - **Lumibot (`lumibot` & `yfinance`)**: Algorithmic multi-asset strategy backtesting over Yahoo Finance feeds with deterministic fallback simulations.
  - **Polymarket (`py_clob_client`)**: CLOB orderbook inspection, live prediction market odds, and Kelly-criterion bankroll sizing.
  - **Hummingbot Tradecraft**: Avellaneda-Stoikov pure market making with inventory skew adjustment.
  - **TradingAgents**: Bull vs. Bear multi-agent deliberation with researcher and risk manager consensus.
  - **AutoHedge & Vibe-Trading**: Swarm consensus voting, Kelly fraction calculation, and GTJA 191 alpha factor library.
  - **FinceptTerminal**: Technical indicators (RSI, MACD, Bollinger Bands) and market regime classification.
  - `app/trading_hub.py` — High-level `TradingHub` coordinator uniting all 11 financial engines.
- **API Surface:** `/api/v1/trading/*` and `/api/v1/trading/engines/{ccxt,backtrader,vectorbt,freqtrade,hummingbot,lumibot,polymarket,trading-agents,suite}/*`

### 3. VyralX — Video & Content Intelligence
- **Role:** Autonomous content creation, audience analytics, video optimization, and automated growth packs.
- **Port:** `8010` (server 2) | **Stack:** Python, FastAPI
- **Deep Modules & Wiring:**
  - `app/services/real_media_routes.py` — Unified multi-modal `/api/v1/media/growth-pack` orchestrating ClaudeAds copy generation, TopRank SEO page audits, OpenHiggsfield video prompts, and Hyperframes storyboards.
  - `app/services/diagram_service.py` — Self-contained HTML+SVG diagram generation mounted under `/api/v1/diagrams/*`.
  - `content_optimizer.py` & `audience_analytics.py` — Retention curve analysis, virality scoring, and cohort segmentation.
- **API Surface:** `/api/v1/vyralx/*`, `/api/v1/diagrams/*`, and `/api/v1/media/*`

### 4. Cortex — Multi-Tenant CRM & Web Operations
- **Role:** CRM and website-operations platform: visitor identity resolution, lead capture and scoring, segmentation, campaigns, attribution, and closed-loop sales follow-up.
- **Port:** `8009` (server 2) | **Stack:** Python, FastAPI, SQLAlchemy async, Redis, Next.js
- **Core Modules:**
  - `enhanced_crm.py` — Weighted lead scoring with persisted score history, CLV/churn prediction, dynamic segments, smart follow-up.
  - `public_gateway.py` — Public website surface: `/v1/identify`, tenant-scoped visitors, leads, events, analytics.
  - `marketing_platform_integrator.py` & `marketing_automation.py` — HubSpot, Stripe and SendGrid connectors, campaign automation.
- **API Surface:** `/cortex/*`, `/api/v1/*`, `/v1/identify`

### 5. Inference — LLM Gateway & Model Router
- **Role:** Centralized model plane: aggregates provider API keys, routes each request to the best available model, quarantines failing keys, and serves an OpenAI-compatible API with streaming and fallback.
- **Port:** `8001` (server 1) | **Stack:** Python, FastAPI
- **Core Modules & Wiring:**
  - `app/providers/gateway.py` — `ModelGateway` + `KeyPool` with round-robin rotation, 60-second quarantine on 429/503, per-provider limits, and capability-matched OpenRouter fallback.
  - `app/routing/cost_router.py` & `self_optimizer.py` — Cost- and feedback-aware model selection.
  - `app/scientific_service.py` — Statistical power, hypothesis and evidence-audit skills under `/v1/scientific/*` (secondary to routing).
- **API Surface:** `/inference/*`, OpenAI-compatible `/v1/*`, `/api/v1/*`

### 6. Forge — Autonomous Software Engineering
- **Role:** Autonomous code generation, test generation, vulnerability remediation, and laptop automation.
- **Port:** `8006` | **Stack:** Python, FastAPI
- **Deep Modules:**
  - `autonomous_laptop_operator.py` — Full-stack autonomous engineering loop with browser automation and local execution.
  - `code_review_router.py` & `autonomous_code_repair.py` — AST analysis, automated vulnerability scanning, and test-driven code repair.
  - `deployment_pipeline_manager.py` — Automated CI/CD deployment pipeline and build health verification.
- **API Surface:** `/api/v1/forge/*`

### 7. Memora — Memory Intelligence
- **Role:** Persistent memory fabric, associative retrieval, temporal indexing, and context compaction.
- **Port:** `8002` | **Stack:** Python, FastAPI
- **Deep Modules & Wiring:**
  - `core/memory/context_service.py` — `viking://` context database (L0/L1/L2 memory hierarchy, scoped search, session commits, and knowledge wiki) mounted under `/v1/context/*`.
  - `semantic_memory_store.py` & `causal_memory_graph.py` — Vector embeddings, associative memory retrieval, and causal relationship tracking.
  - `memory_consolidation_engine.py` — Decay-weighted memory consolidation and cross-agent context synchronization.
- **API Surface:** `/api/v1/memora/*` and `/v1/context/*`

### 8. IntelX — Threat Intelligence & OSINT
- **Role:** OSINT investigation, breach monitoring, dark web reconnaissance, and entity correlation graphs.
- **Port:** `8005` | **Stack:** Python, FastAPI
- **Live Open-Source Integrations:**
  - **Intelligence X (`intelx`)**: Native SDK integration for phonebook search, selector lookup, and breach record retrieval.
  - **IntelBase REST**: Live REST lookup integration for email, username, and infostealer database queries.
  - **ShadowDragon Tradecraft**:
    - `GoogleDorkAssistant`: Automated search engine dork query synthesis across credentials, documents, and infrastructure.
    - `EmailPermutator`: Enterprise email permutation engine with domain locale packs.
    - `ImageForensics` (`Pillow`): Error Level Analysis (ELA) with JPEG re-save difference mapping.
  - **Maltego (`maltego-transforms`)**: Graph entity schema, relationship modeling, and `@register_transform` decorators.
  - **MalNet & Horizon**: Threat indicator correlation API and real-time security alert tracking.
  - `routers/real_osint_routes.py` — Mounted under `/api/v1/osint/*` and `/api/v1/intelx/*`.
- **API Surface:** `/api/v1/intelex/*`, `/api/v1/osint/*`, and `/api/v1/intelx/*`

### 9. Futuris — Predictive Intelligence & Forecasting
- **Role:** Time-series forecasting, market regime detection, ensemble calibration, and rare event prediction.
- **Port:** `8004` | **Stack:** Python, FastAPI
- **Deep Modules:**
  - `forecasting_engine.py` & `ensemble_reconciliation.py` — Multi-model ensemble forecasting (ARIMA, Holt-Winters, exponential smoothing) with automated error calibration.
  - `market_regime_detector.py` — Hidden Markov Model (HMM) regime detection and structural break identification.
  - `scenario_stress_tester.py` — Extreme tail-risk scenario simulation and propagation modeling.
- **API Surface:** `/api/v1/futuris/*`

### 10. Sentinel — Security Operations & Threat Hunting
- **Role:** Real-time SIEM monitoring, MITRE ATT&CK / NIST CSF alignment, and automated compliance auditing.
- **Port:** `8008` (server 2) | **Stack:** Python, FastAPI
- **Deep Modules & Wiring:**
  - `app/services/cyber_skills_service.py` — ATT&CK / NIST CSF / D3FEND / ATLAS skill engine mounted under `/v1/cyber/*`.
  - `security_monitor.py` & `realtime_threat_matcher.py` — Real-time threat pattern matching with IoC feeds and SIEM log correlation.
  - `zero_trust_enforcer.py` & `compliance_audit_trail.py` — Zero-trust access policies, cryptographic audit trails, and automated compliance scoring.
- **API Surface:** `/api/v1/sentinel/*` and `/v1/cyber/*`

---

## Quick Start

### 1. Requirements
- Python 3.10+ (Python 3.11 recommended)
- Node.js 18+ (for dashboard interfaces)
- Docker & Docker Compose (optional, for containerized multi-service deployment)

### 2. Environment Setup
```bash
# Clone repository
git clone https://github.com/surendra2304/FRIDAY-Universe.git
cd FRIDAY-Universe

# Install core and engine dependencies
pip install -r requirements.txt

# Or install real deep engine libraries
pip install ccxt backtrader vectorbt freqtrade lumibot py-clob-client intelx maltego-transforms Pillow yfinance ta

# Configure environment variables
cp .env.example .env
```

### 3. Running Services

#### FRIDAY (orchestrator and LLM gateway):
```bash
cd FRIDAY
python -m uvicorn friday.api.server:app --host 0.0.0.0 --port 10000 --reload
```

#### Stratex Trading Operations Desk:
```bash
cd Stratex
python dashboard.py
# Running on http://127.0.0.1:8003
```

> Production does not use Docker Compose. On the OCI hosts each agent is a systemd unit
> (`/opt/friday_universe/<Agent>`) behind Caddy; see `AGENTS.md` for the verified topology.

---

## Test Verification Suites

The universe includes automated multi-layer test gates verifying algorithmic correctness, library bindings, and inter-agent communication:

```bash
# 1. Full Deep Universe Engines Suite (18 tests)
python -m pytest tests/test_deep_universe_engines_full.py -v

# 2. Comprehensive Batch & Layer Suites (416 tests)
python -m pytest tests/test_real_batch4a.py tests/test_real_batch4b.py tests/test_real_deep_layer3j.py -v

# 3. Autonomous Cross-Agent Verification Gate (19 verification checks)
python scripts/verify_deep_wiring.py
```

### Test Results Summary (last recorded run — rerun to verify):
| Verification Suite | Target Areas | Tests / Checks | Status |
| :--- | :--- | :---: | :---: |
| `test_deep_universe_engines_full.py` | CCXT, Backtrader, Vectorbt, Freqtrade, Hummingbot, Lumibot, Polymarket, TradingAgents, IntelX, Maltego, MalNet, Growth Pack | 18 |  **PASS (100%)** |
| `test_real_batch4a.py` | Stratex Execution, CCXT Manager, Hummingbot Strategies, AutoHedge Consensus | 192 |  **PASS (100%)** |
| `test_real_batch4b.py` | Vectorbt, Freqtrade Hyperopt, Lumibot Backtesting, Polymarket Analyzers | 131 |  **PASS (100%)** |
| `test_real_deep_layer3j.py` | IntelX OSINT, ShadowDragon Tradecraft, Maltego Entity Graphs | 93 |  **PASS (100%)** |
| `verify_deep_wiring.py` | Inter-agent imports, HTTP routes, E2E flow, security guardrails | 19 |  **PASS (100%)** |
| **Total** | **Universe Verification Suite** | **453** | **Recorded (not rerun)** |

---

## Security & Reliability Architecture

- **Capability-Based Authorization**: Every agent invocation is verified against role capabilities.
- **Resilient Dispatch**: Specialist-to-specialist peer requests run behind circuit breakers with automated retry and fallback.
- **Zero Hardcoded Secrets**: All API tokens, secrets, and keys are loaded strictly from environment variables (`os.getenv()`) with automatic secret redaction in error envelopes.
- **Defensive Networking**: Built-in SSRF protection, strict path-traversal validation, and configurable CORS boundaries across all FastAPI and Flask routes.

---

## License

MIT License — see [LICENSE](LICENSE) for full details.
