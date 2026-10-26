# FRIDAY Universe — Unified Multi-Agent Intelligence Platform

> **10 Autonomous Agents · 100+ Deep Modules · Real Open-Source Library Integrations · 450+ Verified Tests**

## Overview

FRIDAY Universe is an enterprise-grade autonomous multi-agent intelligence platform where each specialist agent executes deep, genuine algorithms and real open-source library integrations. The architecture is engineered around 10 autonomous services connected via a central API Gateway and resilient dispatch bus.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FRIDAY (Orchestrator)                    │
│   Unified Gateway · Agent Runtime · Goal-Directed Browser   │
└──────────────────────┬──────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
    │ Stratex │   │ VyralX  │   │ Cortex  │
    │ Trading │   │ Video   │   │ Decision│
    └────┬────┘   └────┬────┘   └────┬────┘
         │             │             │
    ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
    │Inference│   │ Forge   │   │ Memora  │
    │Reasoning│   │ Coding  │   │ Memory  │
    └────┬────┘   └────┬────┘   └────┬────┘
         │             │             │
    ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
    │ IntelX  │   │ Futuris │   │ Sentinel│
    │ Security│   │ Forecast│   │ Security│
    └─────────┘   └─────────┘   └─────────┘
```

---

## The 10 Autonomous Specialist Agents

### 1. FRIDAY (Port 5000) — Central Orchestrator
- **Core Role**: Multi-agent orchestration, autonomous goal decomposition, and harness engineering.
- **Deep Modules**:
  - `agent_runtime.py` — Live `FridayAgentRuntime` mounted under `/v1/agent/*`.
  - `real_browser_agent.py` — Indexed DOM parser, selector resolution, and goal-directed browser runs.
  - `real_harness_engineering.py` — Context compaction, typed tools, permission gates, and verification.
  - `universe_dispatch_bus.py` — Specialist dispatch bus with circuit breakers.
- **Key API Routes**: `/api/v1/friday/*`, `/v1/agent/capabilities`, `/v1/agent/plan`, `/v1/agent/execute`, `/v1/agent/browser/run`.

### 2. Stratex (Port 5001) — Trading Intelligence
- **Core Role**: Algorithmic trading, portfolio optimization, quantitative risk, and prediction markets.
- **Live Library Integrations**:
  - `ccxt`: Multi-exchange market feeds, spatial arbitrage, and rate-limited order execution.
  - `backtrader`: Event-driven backtesting with SMA crossover strategies and trade metrics.
  - `vectorbt`: High-performance vectorized portfolio simulation and Sharpe/drawdown calculation.
  - `freqtrade`: Hyperopt parameter optimization over minimal ROI and stoploss spaces.
  - `lumibot` & `yfinance`: Multi-asset strategy backtesting over Yahoo Finance feeds.
  - `py_clob_client`: Polymarket CLOB orderbook tracking and Kelly-criterion sizing.
  - `app/trading_hub.py`: High-level `TradingHub` coordinator unifying all 11 financial engines.
- **Key API Routes**: `/api/v1/trading/*`, `/api/v1/trading/engines/ccxt/*`, `/api/v1/trading/engines/backtrader/*`, `/api/v1/trading/engines/vectorbt/*`, `/api/v1/trading/engines/lumibot/*`, `/api/v1/trading/engines/polymarket/*`, `/api/v1/trading/engines/trading-agents/*`.

### 3. VyralX (Port 5002) — Video & Content Intelligence
- **Core Role**: Video analytics, automated content growth packs, and diagram generation.
- **Deep Modules**:
  - `app/services/real_media_routes.py`: Unified `/api/v1/media/growth-pack` orchestrating ClaudeAds, TopRank SEO, OpenHiggsfield video generation, and Hyperframes.
  - `app/services/diagram_service.py`: SVG+HTML diagram generation under `/api/v1/diagrams/*`.
  - `content_optimizer.py` & `audience_analytics.py`: Retention curve and audience segmentation.
- **Key API Routes**: `/api/v1/vyralx/*`, `/api/v1/diagrams/*`, `/api/v1/media/growth-pack`.

### 4. Cortex (Port 5003) — Decision Intelligence
- **Core Role**: Multi-criteria decision analysis, scenario simulation, and causal impact modeling.
- **Deep Modules**:
  - `decision_engine.py`: Weighted multi-criteria scoring and fatigue detection.
  - `scenario_analyzer.py`: Monte Carlo simulation and stress testing.
  - `contextual_bandit_optimizer.py`: Real-time bandit policy optimization.
- **Key API Routes**: `/api/v1/cortex/decide`, `/api/v1/cortex/scenario`, `/api/v1/cortex/causal`.

### 5. Inference (Port 5004) — Reasoning Engine
- **Core Role**: Logical inference, hypothesis testing, and scientific validation.
- **Deep Modules**:
  - `app/scientific_service.py`: Scientific routing and hypothesis auditing under `/v1/scientific/*`.
  - `reasoning_engine.py` & `multi_hypothesis_reasoner.py`: Bayesian updating and multi-hypothesis evaluation.
  - `causal_inference_engine.py`: Structural equation modeling.
- **Key API Routes**: `/api/v1/inference/*`, `/v1/scientific/*`.

### 6. Forge (Port 5005) — Autonomous Coding
- **Core Role**: Autonomous software engineering, AST refactoring, and automated repairs.
- **Deep Modules**:
  - `autonomous_laptop_operator.py`: Autonomous development loop and browser automation.
  - `code_review_router.py`: AST static code analysis and security scanning.
  - `autonomous_code_repair.py`: Test-driven code repair and bug fix synthesis.
- **Key API Routes**: `/api/v1/forge/repair`, `/api/v1/forge/review`, `/api/v1/forge/synthesize`.

### 7. Memora (Port 5006) — Memory Intelligence
- **Core Role**: Distributed memory fabric, vector storage, and context management.
- **Deep Modules**:
  - `core/memory/context_service.py`: `viking://` context database mounted under `/v1/context/*`.
  - `semantic_memory_store.py`: Vector embeddings and semantic retrieval.
  - `memory_consolidation_engine.py`: Decay-weighted consolidation and cross-agent sharing.
- **Key API Routes**: `/api/v1/memora/*`, `/v1/context/*`.

### 8. IntelX (Port 5007) — Threat Intelligence & OSINT
- **Core Role**: Open-source intelligence, threat correlation, and dark web monitoring.
- **Live Library Integrations**:
  - `intelx`: Native Intelligence X search and phonebook lookup.
  - `IntelBase REST`: Live account enumeration and breach record lookup.
  - `ShadowDragon Tradecraft`: Google dork assistant, email permutator, and Pillow Error Level Analysis (ELA).
  - `maltego-transforms`: Maltego entity graphs and transform registration.
  - `MalNet` & `Horizon`: Indicator correlation and threat alert feeds.
- **Key API Routes**: `/api/v1/osint/search`, `/api/v1/osint/phonebook`, `/api/v1/osint/dorks`, `/api/v1/osint/image-forensics`, `/api/v1/intelx/maltego/graph`, `/api/v1/intelx/malnet/correlate`, `/api/v1/intelx/horizon/alerts`.

### 9. Futuris (Port 5008) — Predictive Intelligence
- **Core Role**: Multi-model forecasting, market regime detection, and scenario stress testing.
- **Deep Modules**:
  - `forecasting_engine.py`: Multi-model ensemble forecasting (ARIMA, Holt-Winters, exponential smoothing).
  - `market_regime_detector.py`: Hidden Markov Model (HMM) regime transitions.
  - `scenario_stress_tester.py`: Tail-risk simulation and propagation modeling.
- **Key API Routes**: `/api/v1/futuris/forecast`, `/api/v1/futuris/regime`, `/api/v1/futuris/stress`.

### 10. Sentinel (Port 5009) — Security Operations
- **Core Role**: Real-time SIEM, threat hunting, and compliance auditing.
- **Deep Modules**:
  - `app/services/cyber_skills_service.py`: MITRE ATT&CK, NIST CSF, and D3FEND framework alignment under `/v1/cyber/*`.
  - `security_monitor.py`: Real-time IoC matching and SIEM log correlation.
  - `zero_trust_enforcer.py`: Zero-trust policies and cryptographic audit trails.
- **Key API Routes**: `/api/v1/sentinel/monitor`, `/api/v1/sentinel/posture`, `/v1/cyber/*`.

---

## Test Verification

The system includes over 450 automated tests verifying genuine functionality:

```bash
# Run comprehensive deep engine test suite (18 tests)
python -m pytest tests/test_deep_universe_engines_full.py -v

# Run batch regression suites (416 tests)
python -m pytest tests/test_real_batch4a.py tests/test_real_batch4b.py tests/test_real_deep_layer3j.py -v

# Run autonomous cross-agent verification gate (19 checks)
python scripts/verify_deep_wiring.py
```

### Verification Scorecard:
| Suite | Description | Status |
| :--- | :--- | :---: |
| `test_deep_universe_engines_full.py` | CCXT, Backtrader, Vectorbt, Freqtrade, Hummingbot, Lumibot, Polymarket, IntelX, Maltego, MalNet, Growth Pack |  PASS (18/18) |
| `test_real_batch4a.py` | Stratex Execution, CCXT Manager, Hummingbot, AutoHedge |  PASS (192/192) |
| `test_real_batch4b.py` | Vectorbt, Freqtrade Hyperopt, Lumibot, Polymarket |  PASS (131/131) |
| `test_real_deep_layer3j.py` | IntelX OSINT, ShadowDragon Tradecraft, Maltego Entity Graphs |  PASS (93/93) |
| `verify_deep_wiring.py` | Cross-agent imports, HTTP routes, end-to-end autonomous triage flow |  PASS (19/19) |
| **Total** | **FRIDAY Universe Automated Verification** | ** 453 Passed** |

---

## Security Architecture

- **Zero Hardcoded Secrets**: All keys, passwords, and tokens are read exclusively through environment variables (`os.getenv()`).
- **Cryptographic Audit**: Control-plane auditing and tamper-evident logging across agents.
- **SSRF & Path Traversal Protection**: Guardrails built into all dispatchers and route handlers.
- **Circuit Breakers & Retries**: Fault-tolerant inter-agent dispatch preventing cascading failures.
