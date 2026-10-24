# FRIDAY Universe — Agent Architecture Documentation

## Overview

The FRIDAY Universe is a multi-agent AI platform where each agent is a specialized service with independent APIs, domain expertise, and operational autonomy. Agents communicate through a shared Gateway and can collaborate on cross-domain tasks.

## Agents (10)

### 1. FRIDAY — Multi-Agent Orchestrator
**Role:** Central coordinator and meta-agent that manages the FRIDAY Universe.
**Port:** 5000 | **Stack:** Python, FastAPI, React

**Deep Modules:**
- `general_cognitive_coordinator.py` — Cross-domain orchestration with sub-task decomposition
- `autonomous_problem_solver.py` — Autonomous goal-oriented problem solving with multi-step reasoning

**API:** `/api/v1/friday/*`

### 2. Stratex — Trading Intelligence Agent
**Role:** Algorithmic trading, portfolio management, market intelligence.
**Port:** 5001 | **Stack:** Python, Flask, SQLite

**Deep Modules:**
- `strategy_engine.py` — Multi-strategy trading engine with backtesting
- `portfolio_optimizer.py` — Portfolio optimization with risk constraints
- `market_data_processor.py` — Real-time market data processing and feature extraction
- `multi_venue_execution.py` — Multi-venue order routing and execution
- `algorithmic_strategy_library.py` — Library of algorithmic trading strategies with parameter tuning
- `portfolio_risk_analytics.py` — VaR, stress testing, scenario analysis, Monte Carlo simulation
- `algorithmic_market_making.py` — Quote generation, inventory management, adverse selection detection

**API:** `/api/v1/trading/*`

### 3. VyralX — Video Content Intelligence Agent
**Role:** Video analytics, content creation, audience engagement.
**Port:** 5002 | **Stack:** Python, FastAPI

**Deep Modules:**
- `content_optimizer.py` — Video content optimization with audience targeting
- `audience_analytics.py` — Audience behavior analysis with cohort tracking
- `multilingual_content_translator.py` — AI-powered multilingual content translation and localization
- `personalized_recommendation.py` — Personalized content recommendations with real-time adaptation
- `video_analytics_dashboard.py` — Video metrics, demographics, retention curves, virality
- `content_calendar_manager.py` — Content scheduling, pipelines, cross-platform distribution

**API:** `/api/v1/vyralx/*`

### 4. Cortex — Decision Intelligence Agent
**Role:** Predictive analytics, decision support, scenario planning.
**Port:** 5003 | **Stack:** Python, FastAPI

**Deep Modules:**
- `decision_engine.py` — Multi-criteria decision analysis with uncertainty quantification
- `scenario_analyzer.py` — Scenario planning with Monte Carlo simulation
- `predictive_model_manager.py` — ML model lifecycle management with auto-retraining
- `ab_experiment_framework.py` — A/B testing framework with statistical significance
- `competitive_intelligence.py` — Competitor monitoring, product tracking, pricing analysis, SWOT

**API:** `/api/v1/cortex/*`

### 5. Inference — Reasoning Engine Agent
**Role:** Logical reasoning, inference, knowledge graph operations.
**Port:** 5004 | **Stack:** Python, FastAPI

**Deep Modules:**
- `reasoning_engine.py` — Multi-step logical inference with confidence tracking
- `knowledge_graph_processor.py` — Knowledge graph operations with query optimization
- `reasoning_chain_optimizer.py` — Reasoning chain optimization with strategy recommendations

**API:** `/api/v1/inference/*`

### 6. Forge — Autonomous Coding Agent
**Role:** Code generation, testing, deployment automation.
**Port:** 5005 | **Stack:** Python, FastAPI

**Deep Modules:**
- `autonomous_laptop_operator.py` — Full-stack autonomous development with browser automation
- `code_synthesis_engine.py` — AI-powered code synthesis with multi-language support
- `distributed_dev_environment.py` — Multi-environment development with state synchronization
- `code_review_router.py` — Automated code review with security scanning and reviewer suggestions

**API:** `/api/v1/forge/*`

### 7. Memora — Memory Intelligence Agent
**Role:** Persistent memory, knowledge storage, context management.
**Port:** 5006 | **Stack:** Python, FastAPI

**Deep Modules:**
- `semantic_memory_store.py` — Semantic memory with vector-based retrieval
- `episodic_memory_manager.py` — Episodic memory with temporal indexing
- `causal_memory_graph.py` — Causal relationships between memories with inference
- `memory_consolidation_engine.py` — Memory consolidation with importance scoring, decay, merging

**API:** `/api/v1/memora/*`

### 8. IntelX — Threat Intelligence Agent
**Role:** Cybersecurity, threat intelligence, OSINT, breach monitoring.
**Port:** 5007 | **Stack:** Python, FastAPI

**Deep Modules:**
- `threat_detection_engine.py` — Multi-source threat detection with correlation
- `osint_collector.py` — OSINT data collection with multi-source aggregation
- `dynamic_osint_collector.py` — Adaptive OSINT collection with real-time targeting
- `threat_intel_knowledge_base.py` — TTPs, actor profiles, incidents, IoCs, relationship graph
- `dark_web_monitor.py` — Dark web leak monitoring, breach alerts, credential tracking

**API:** `/api/v1/intelex/*`

### 9. Futuris — Predictive Intelligence Agent
**Role:** Forecasting, predictive modeling, scenario simulation.
**Port:** 5008 | **Stack:** Python, FastAPI

**Deep Modules:**
- `forecasting_engine.py` — Multi-model forecasting with calibration and accuracy tracking
- `realtime_event_impact.py` — Real-time event impact assessment with propagation modeling
- `ensemble_reconciliation.py` — Multi-model ensemble forecasting with reconciliation
- `predictive_maintenance.py` — Predictive maintenance with failure mode analysis
- `market_regime_detector.py` — Market regime detection with HMM and transition modeling

**API:** `/api/v1/futuris/*`

### 10. Sentinel — Security Operations Agent
**Role:** Security monitoring, threat hunting, compliance auditing.
**Port:** 5009 | **Stack:** Python, Flask

**Deep Modules:**
- `security_monitor.py` — Real-time security monitoring with SIEM integration
- `threat_hunting_assistant.py` — AI-assisted threat hunting with hypothesis generation
- `zero_trust_enforcer.py` — Zero-trust policy enforcement with identity verification
- `compliance_audit_trail.py` — Automated compliance auditing with evidence collection

**API:** `/api/v1/sentinel/*`

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FRIDAY (Orchestrator)                    │
│              Manages all agents, routes tasks               │
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
    │ Inference│  │ Forge   │   │ Memora  │
    │ Reasoning│  │ Coding  │   │ Memory  │
    └────┬────┘   └────┬────┘   └────┬────┘
         │             │             │
    ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
    │ IntelX  │   │ Futuris │   │ Sentinel│
    │ Security│   │ Forecast│   │ Security│
    └─────────┘   └─────────┘   └─────────┘
```

## Communication Flow

1. **FRIDAY** receives a task from the user
2. **FRIDAY** decomposes the task into sub-tasks
3. **FRIDAY** routes sub-tasks to appropriate agents via the Gateway
4. Agents execute sub-tasks autonomously
5. Agents return results to FRIDAY via the Gateway
6. **FRIDAY** aggregates results and responds to the user

## API Gateway

The Gateway provides:
- **Request routing** — Routes requests to the correct agent
- **Authentication** — Validates API keys and permissions
- **Rate limiting** — Prevents abuse
- **Load balancing** — Distributes load across agent instances
- **Response aggregation** — Aggregates responses from multiple agents

## Deep Module Pattern

Each deep module follows a consistent pattern:
- **Dataclasses** for structured data
- **Class-based engine** with methods for operations
- **API Router** (FastAPI) or **Blueprint** (Flask) exposing the engine
- **Module-level singleton** for shared state
- **Comprehensive error handling** with HTTPException
- **Report/summary methods** for monitoring

## Testing

All modules are validated with:
- **py_compile** — Syntax validation
- **pytest** — Test suite covering imports, instantiation, and method calls
- **114/114 tests passing** (29 skipped)
