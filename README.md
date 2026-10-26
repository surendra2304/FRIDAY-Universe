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
│ Trading │   │  Content  │   │ Decision  │   │Reasoning │   │  Coding  │
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
- **Port:** `5000` | **Stack:** Python, FastAPI, React
- **Deep Modules & Wiring:**
  - `agent_runtime.py` — Live `FridayAgentRuntime` supporting step-by-step execution, typed tool registry, and session tracing.
  - `real_browser_agent.py` — Indexed DOM parser, selector resolution, form filling, and goal-directed web runs.
  - `real_harness_engineering.py` — Autonomous agent loop, context compaction, permission gating, verification, and state checkpoints.
  - `universe_dispatch_bus.py` — Resilient dispatch across all 9 specialists with circuit breakers and fallback execution.
- **API Surface:** `/api/v1/friday/*` and `/v1/agent/{capabilities,plan,execute,context/compact,browser/run,trace}`

### 2. Stratex — Trading & Financial Intelligence
- **Role:** Algorithmic trading, multi-venue order execution, quantitative portfolio management, and prediction markets.
- **Port:** `5001` | **Stack:** Python, Flask, SQLite
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
- **Port:** `5002` | **Stack:** Python, FastAPI
- **Deep Modules & Wiring:**
  - `app/services/real_media_routes.py` — Unified multi-modal `/api/v1/media/growth-pack` orchestrating ClaudeAds copy generation, TopRank SEO page audits, OpenHiggsfield video prompts, and Hyperframes storyboards.
  - `app/services/diagram_service.py` — Self-contained HTML+SVG diagram generation mounted under `/api/v1/diagrams/*`.
  - `content_optimizer.py` & `audience_analytics.py` — Retention curve analysis, virality scoring, and cohort segmentation.
- **API Surface:** `/api/v1/vyralx/*`, `/api/v1/diagrams/*`, and `/api/v1/media/*`

### 4. Cortex — Decision Intelligence
- **Role:** Multi-criteria decision analysis, predictive modeling, scenario simulation, and causal inference.
- **Port:** `5003` | **Stack:** Python, FastAPI, Next.js
- **Deep Modules:**
  - `decision_engine.py` — Multi-criteria decision analysis with uncertainty quantification and fatigue detection.
  - `scenario_analyzer.py` — Monte Carlo simulation and stress testing across economic and operational variables.
  - `contextual_bandit_optimizer.py` — Contextual bandit optimization for real-time strategy selection.
  - `causal_impact_analyzer.py` — Counterfactual reasoning and causal impact estimation.
- **API Surface:** `/api/v1/cortex/*`

### 5. Inference — Reasoning Engine
- **Role:** Multi-step logical inference, causal reasoning, hypothesis evaluation, and scientific verification.
- **Port:** `5004` | **Stack:** Python, FastAPI
- **Deep Modules & Wiring:**
  - `app/scientific_service.py` — Research-skill routing, statistical power calculation, hypothesis generation, and evidence auditing under `/v1/scientific/*`.
  - `reasoning_engine.py` & `multi_model_deliberation_engine.py` — Multi-model deliberation and consensus validation.
  - `causal_inference_engine.py` — Structural equation modeling and counterfactual verification.
- **API Surface:** `/api/v1/inference/*` and `/v1/scientific/*`

### 6. Forge — Autonomous Software Engineering
- **Role:** Autonomous code generation, test generation, vulnerability remediation, and laptop automation.
- **Port:** `5005` | **Stack:** Python, FastAPI
- **Deep Modules:**
  - `autonomous_laptop_operator.py` — Full-stack autonomous engineering loop with browser automation and local execution.
  - `code_review_router.py` & `autonomous_code_repair.py` — AST analysis, automated vulnerability scanning, and test-driven code repair.
  - `deployment_pipeline_manager.py` — Automated CI/CD deployment pipeline and build health verification.
- **API Surface:** `/api/v1/forge/*`

### 7. Memora — Memory Intelligence
- **Role:** Persistent memory fabric, associative retrieval, temporal indexing, and context compaction.
- **Port:** `5006` | **Stack:** Python, FastAPI
- **Deep Modules & Wiring:**
  - `core/memory/context_service.py` — `viking://` context database (L0/L1/L2 memory hierarchy, scoped search, session commits, and knowledge wiki) mounted under `/v1/context/*`.
  - `semantic_memory_store.py` & `causal_memory_graph.py` — Vector embeddings, associative memory retrieval, and causal relationship tracking.
  - `memory_consolidation_engine.py` — Decay-weighted memory consolidation and cross-agent context synchronization.
- **API Surface:** `/api/v1/memora/*` and `/v1/context/*`

### 8. IntelX — Threat Intelligence & OSINT
- **Role:** OSINT investigation, breach monitoring, dark web reconnaissance, and entity correlation graphs.
- **Port:** `5007` | **Stack:** Python, FastAPI
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
- **Port:** `5008` | **Stack:** Python, FastAPI
- **Deep Modules:**
  - `forecasting_engine.py` & `ensemble_reconciliation.py` — Multi-model ensemble forecasting (ARIMA, Holt-Winters, exponential smoothing) with automated error calibration.
  - `market_regime_detector.py` — Hidden Markov Model (HMM) regime detection and structural break identification.
  - `scenario_stress_tester.py` — Extreme tail-risk scenario simulation and propagation modeling.
- **API Surface:** `/api/v1/futuris/*`

### 10. Sentinel — Security Operations & Threat Hunting
- **Role:** Real-time SIEM monitoring, MITRE ATT&CK / NIST CSF alignment, and automated compliance auditing.
- **Port:** `5009` | **Stack:** Python, Flask
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

#### Central API Gateway (FRIDAY Orchestrator):
```bash
python -m uvicorn friday_core.real_api_server:app --host 0.0.0.0 --port 5000 --reload
```

#### Stratex Trading Operations Desk:
```bash
cd Stratex
python dashboard.py
# Running on http://127.0.0.1:5001
```

#### Docker Compose (All 10 Services):
```bash
docker compose up -d --build
```

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

### Test Results Summary:
| Verification Suite | Target Areas | Tests / Checks | Status |
| :--- | :--- | :---: | :---: |
| `test_deep_universe_engines_full.py` | CCXT, Backtrader, Vectorbt, Freqtrade, Hummingbot, Lumibot, Polymarket, TradingAgents, IntelX, Maltego, MalNet, Growth Pack | 18 |  **PASS (100%)** |
| `test_real_batch4a.py` | Stratex Execution, CCXT Manager, Hummingbot Strategies, AutoHedge Consensus | 192 |  **PASS (100%)** |
| `test_real_batch4b.py` | Vectorbt, Freqtrade Hyperopt, Lumibot Backtesting, Polymarket Analyzers | 131 |  **PASS (100%)** |
| `test_real_deep_layer3j.py` | IntelX OSINT, ShadowDragon Tradecraft, Maltego Entity Graphs | 93 |  **PASS (100%)** |
| `verify_deep_wiring.py` | Inter-agent imports, HTTP routes, E2E flow, security guardrails | 19 |  **PASS (100%)** |
| **Total** | **Universe Verification Suite** | **453** | ** 100% Passed** |

---

## Security & Reliability Architecture

- **Capability-Based Authorization**: Every agent invocation is verified against role capabilities.
- **Resilient Dispatch**: Specialist-to-specialist peer requests run behind circuit breakers with automated retry and fallback.
- **Zero Hardcoded Secrets**: All API tokens, secrets, and keys are loaded strictly from environment variables (`os.getenv()`) with automatic secret redaction in error envelopes.
- **Defensive Networking**: Built-in SSRF protection, strict path-traversal validation, and configurable CORS boundaries across all FastAPI and Flask routes.

---

## License

MIT License — see [LICENSE](LICENSE) for full details.
