# FRIDAY Universe — Unified Multi-Agent Intelligence Platform

> **10 Autonomous Agents · 100+ Deep Modules · Real Open-Source Library Integrations**

> **Deployment status (verified 2026-10-26):** production runs as systemd services behind Caddy on
> two Oracle Cloud VMs. The Dokploy/Docker Swarm/Traefik/PostgreSQL stack described in older
> documents is not running. See `AGENTS.md` for the verified host/port table and per-agent caveats.

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
    │ Trading │   │ Video   │   │   CRM   │
    └────┬────┘   └────┬────┘   └────┬────┘
         │             │             │
    ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
    │Inference│   │ Forge   │   │ Memora  │
    │LLM Router│  │ Coding  │   │ Memory  │
    └────┬────┘   └────┬────┘   └────┬────┘
         │             │             │
    ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
    │ IntelX  │   │ Futuris │   │ Sentinel│
    │ Security│   │ Forecast│   │ Security│
    └─────────┘   └─────────┘   └─────────┘
```

---

## The 10 Autonomous Specialist Agents

### 1. FRIDAY (Port 10000) — Central Orchestrator
- **Core Role**: Multi-agent orchestration, autonomous goal decomposition, and harness engineering.
- **Deep Modules**:
  - `agent_runtime.py` — Live `FridayAgentRuntime` mounted under `/v1/agent/*`.
  - `real_browser_agent.py` — Indexed DOM parser, selector resolution, and goal-directed browser runs.
  - `real_harness_engineering.py` — Context compaction, typed tools, permission gates, and verification.
  - `universe_dispatch_bus.py` — Specialist dispatch bus with circuit breakers.
- **Key API Routes**: `/api/v1/friday/*`, `/v1/agent/capabilities`, `/v1/agent/plan`, `/v1/agent/execute`, `/v1/agent/browser/run`.

### 2. Stratex (Port 8003) — Trading Intelligence
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

### 3. VyralX (Port 8010) — Video & Content Intelligence
- **Core Role**: Video analytics, automated content growth packs, and diagram generation.
- **Deep Modules**:
  - `app/services/real_media_routes.py`: Unified `/api/v1/media/growth-pack` orchestrating ClaudeAds, TopRank SEO, OpenHiggsfield video generation, and Hyperframes.
  - `app/services/diagram_service.py`: SVG+HTML diagram generation under `/api/v1/diagrams/*`.
  - `content_optimizer.py` & `audience_analytics.py`: Retention curve and audience segmentation.
- **Key API Routes**: `/api/v1/vyralx/*`, `/api/v1/diagrams/*`, `/api/v1/media/growth-pack`.

### 4. Cortex (Port 8009) — Multi-Tenant CRM & Web Operations
- **Core Role**: CRM and website-operations platform: visitor identity resolution, lead capture and scoring, segmentation, campaigns, attribution, experiments, and closed-loop sales follow-up.
- **Core Modules**:
  - `enhanced_crm.py`: Weighted lead scoring with persisted score history, CLV/churn prediction, dynamic segments, smart follow-up.
  - `public_gateway.py`: Public website surface — `/v1/identify`, tenant-scoped visitors, leads, events, analytics.
  - `marketing_platform_integrator.py` & `marketing_automation.py`: HubSpot, Stripe and SendGrid connectors, campaign automation.
- **Key API Routes**: `/v1/identify`, `/v1/visitors/{id}`, `/v1/leads`, `/api/v1/leads/score`, `/api/v1/crm/report`.
- **Persistence**: Oracle Autonomous Database (`CORTEX` login/schema on the FRIDAY Universe DB). PostgreSQL and SQLite are not supported.

### 5. Inference (Port 8001) — LLM Gateway & Model Router
- **Core Role**: Centralized model plane — aggregates provider API keys, routes each request to the best available model, quarantines failing keys, and serves an OpenAI-compatible API with streaming and fallback.
- **Core Modules**:
  - `app/providers/gateway.py`: `ModelGateway` + `KeyPool` with round-robin rotation, 60-second quarantine on 429/503, per-provider limits, capability-matched OpenRouter fallback.
  - `app/routing/cost_router.py` & `self_optimizer.py`: Cost- and feedback-aware model selection.
  - `app/scientific_service.py`: Statistical power, hypothesis and evidence-audit skills under `/v1/scientific/*` (secondary to routing).
- **Key API Routes**: `/v1/chat/completions`, `/v1/models`, `/api/v1/inference/*`, `/v1/scientific/*`.

### 6. Forge (Port 8006) — Autonomous Coding
- **Core Role**: Autonomous software engineering, AST refactoring, and automated repairs.
- **Deep Modules**:
  - `autonomous_laptop_operator.py`: Autonomous development loop and browser automation.
  - `code_review_router.py`: AST static code analysis and security scanning.
  - `autonomous_code_repair.py`: Test-driven code repair and bug fix synthesis.
- **Key API Routes**: `/api/v1/forge/repair`, `/api/v1/forge/review`, `/api/v1/forge/synthesize`.

### 7. Memora (Port 8002) — Memory Intelligence
- **Core Role**: Distributed memory fabric, vector storage, and context management.
- **Deep Modules**:
  - `core/memory/context_service.py`: `viking://` context database mounted under `/v1/context/*`.
  - `semantic_memory_store.py`: Vector embeddings and semantic retrieval.
  - `memory_consolidation_engine.py`: Decay-weighted consolidation and cross-agent sharing.
- **Key API Routes**: `/api/v1/memora/*`, `/v1/context/*`.

### 8. IntelX (Port 8005) — Threat Intelligence & OSINT
- **Core Role**: Open-source intelligence, threat correlation, and dark web monitoring.
- **Live Library Integrations**:
  - `intelx`: Native Intelligence X search and phonebook lookup.
  - `IntelBase REST`: Live account enumeration and breach record lookup.
  - `ShadowDragon Tradecraft`: Google dork assistant, email permutator, and Pillow Error Level Analysis (ELA).
  - `maltego-transforms`: Maltego entity graphs and transform registration.
  - `MalNet` & `Horizon`: Indicator correlation and threat alert feeds.
- **Key API Routes**: `/api/v1/osint/search`, `/api/v1/osint/phonebook`, `/api/v1/osint/dorks`, `/api/v1/osint/image-forensics`, `/api/v1/intelx/maltego/graph`, `/api/v1/intelx/malnet/correlate`, `/api/v1/intelx/horizon/alerts`.

### 9. Futuris (Port 8004) — Predictive Intelligence
- **Core Role**: Multi-model forecasting, market regime detection, and scenario stress testing.
- **Deep Modules**:
  - `forecasting_engine.py`: Multi-model ensemble forecasting (ARIMA, Holt-Winters, exponential smoothing).
  - `market_regime_detector.py`: Hidden Markov Model (HMM) regime transitions.
  - `scenario_stress_tester.py`: Tail-risk simulation and propagation modeling.
- **Key API Routes**: `/api/v1/futuris/forecast`, `/api/v1/futuris/regime`, `/api/v1/futuris/stress`.

### 10. Sentinel (Port 8008) — Security Operations
- **Core Role**: Real-time SIEM, threat hunting, and compliance auditing.
- **Deep Modules**:
  - `app/services/cyber_skills_service.py`: MITRE ATT&CK, NIST CSF, and D3FEND framework alignment under `/v1/cyber/*`.
  - `security_monitor.py`: Real-time IoC matching and SIEM log correlation.
  - `zero_trust_enforcer.py`: Zero-trust policies and cryptographic audit trails.
- **Key API Routes**: `/api/v1/sentinel/monitor`, `/api/v1/sentinel/posture`, `/v1/cyber/*`.

---

## Test Verification

> **Status: historical snapshot, not a current guarantee.** The suites exist, but the counts below
> were recorded on an earlier tree and have not been re-run. A deployment check on 2026-10-26 found
> issues a 100% scorecard would hide (see `AGENTS.md`). Re-run before citing a pass rate.

```bash
# Run comprehensive deep engine test suite (18 tests)
python -m pytest tests/test_deep_universe_engines_full.py -v

# Run batch regression suites (416 tests)
python -m pytest tests/test_real_batch4a.py tests/test_real_batch4b.py tests/test_real_deep_layer3j.py -v

# Run autonomous cross-agent verification gate (19 checks)
python scripts/verify_deep_wiring.py
```

### Verification Scorecard (last recorded run — rerun to verify):
| Suite | Description | Status |
| :--- | :--- | :---: |
| `test_deep_universe_engines_full.py` | CCXT, Backtrader, Vectorbt, Freqtrade, Hummingbot, Lumibot, Polymarket, IntelX, Maltego, MalNet, Growth Pack | Recorded (18/18) |
| `test_real_batch4a.py` | Stratex Execution, CCXT Manager, Hummingbot, AutoHedge | Recorded (192/192) |
| `test_real_batch4b.py` | Vectorbt, Freqtrade Hyperopt, Lumibot, Polymarket | Recorded (131/131) |
| `test_real_deep_layer3j.py` | IntelX OSINT, ShadowDragon Tradecraft, Maltego Entity Graphs | Recorded (93/93) |
| `verify_deep_wiring.py` | Cross-agent imports, HTTP routes, end-to-end autonomous triage flow | Recorded (19/19) |
| **Total** | **FRIDAY Universe Automated Verification** | **453 recorded (not rerun)** |

### Current production smoke checks (2026-10-26)
- All ten agents return `200` on `/health`.
- `/ready` returns `200` on FRIDAY, Sentinel, Cortex and VyralX.
- VyralX `/ready` was `503` until the `FFMPEG_BIN` path was corrected on server 2.
- Cortex was serving from an unlinked `/dev/shm` SQLite file; it now uses the durable
  `data/cortex.db` with all 16 tables present across restarts.

---

## Security Architecture

- **Zero Hardcoded Secrets**: All keys, passwords, and tokens are read exclusively through environment variables (`os.getenv()`).
- **Cryptographic Audit**: Control-plane auditing and tamper-evident logging across agents.
- **SSRF & Path Traversal Protection**: Guardrails built into all dispatchers and route handlers.
- **Circuit Breakers & Retries**: Fault-tolerant inter-agent dispatch preventing cascading failures.
