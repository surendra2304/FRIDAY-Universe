# FRIDAY Universe — Agent Architecture Documentation

## Design System & Animation

**All web dashboards and frontend work must consult these docs first:**

- `docs/design-system.md` — Visual principles, design tokens, component standards, color palette, typography, spacing, motion tokens
- `docs/animation-playbook.md` — Animation patterns (scroll reveals, pinning, parallax, staggered text, micro-interactions), library selection matrix, cleanup patterns, performance budget
- `docs/design-references.md` — Reference catalogue with source URLs, transferable design lessons, implemented patterns
- `docs/design-qa.md` — Responsive, visual, functional, accessibility, and performance checklist

**Key rules:**
- Respect `prefers-reduced-motion` — all animations must have CSS fallbacks
- Prefer `transform` and `opacity` for animated properties
- Dashboards are data workspaces, not marketing pages — no hero animations, no decorative 3D
- Use CSS-only animations for reliability; add GSAP/Lenis only when scroll-driven storytelling is needed
- Monospace fonts (DM Mono) for all numeric data
- Single accent color per product (lime for Stratex, green for Forge)
- Panel-based layouts with consistent padding (18px desktop, 14px mobile)

**Current web assets:**
- `Stratex/static/` — Operations desk (index.html, style.css, app.js) with scroll progress, panel reveals, metric bump animations
- `Forge/app/dashboard/routes.py` — Engineering console with staggered entrances, scroll progress, IntersectionObserver reveals
- `Cortex/apps/dashboard/` — Next.js dashboard (React/TypeScript/Tailwind)

## Overview

The FRIDAY Universe is a multi-agent AI platform where each agent is a specialized service with independent APIs, domain expertise, and operational autonomy. Agents communicate through a shared Gateway and can collaborate on cross-domain tasks.

## Agents (10)

### 1. FRIDAY — Multi-Agent Orchestrator
**Role:** Central coordinator and meta-agent that manages the FRIDAY Universe.
**Port:** 5000 | **Stack:** Python, FastAPI, React

**Deep Modules (21):**
- `general_cognitive_coordinator.py` — Cross-domain orchestration with sub-task decomposition
- `autonomous_problem_solver.py` — Autonomous goal-oriented problem solving with multi-step reasoning
- `multi_agent_collaboration_protocol.py` — Agent-to-agent communication protocol
- `cross_domain_knowledge_transfer.py` — Knowledge sharing across agent domains
- `error_envelope.py` — Unified error handling with standard codes
- `universe_gateway.py` — Unified API gateway for all agents
- `universe_config.py` — Centralized configuration for all agents
- `universe_metrics.py` — Universe-level monitoring and Prometheus metrics
- `universe_health_monitor.py` — Health checking across all agents
- `agent_mesh_router.py` — Agent mesh routing with load balancing
- `universe_dispatch_bus.py` — Unified dispatch to all 9 specialists with circuit breakers
- `universe_auth.py` — Unified authentication, capability-based authorization
- `cross_agent_integration.py` — Specialist-to-specialist peer calls
- `security_hardening.py` — SSRF protection, path traversal defense, CORS config
- `universe_resilience.py` — Universe-wide fault tolerance and graceful degradation
- `universe_cost_optimizer.py` — Cross-agent cost tracking and budget management
- `real_browser_agent.py` — Indexed DOM understanding, selector resolution, form filling and goal-directed browser runs
- `real_harness_engineering.py` — Agent loop, context compaction, typed tools, permission gate, verification, tracing, checkpoints, evals
- `agent_runtime.py` — **live wiring**: `FridayAgentRuntime` used by `universe_orchestrator` workflows and mounted as `/v1/agent/*`

**API:** `/api/v1/friday/*` and `/v1/agent/{capabilities,plan,execute,context/compact,browser/run,trace}`

### 2. Stratex — Trading Intelligence Agent
**Role:** Algorithmic trading, portfolio management, market intelligence.
**Port:** 5001 | **Stack:** Python, Flask, SQLite

**Deep Modules (18):**
- `strategy_engine.py` — Multi-strategy trading engine with backtesting
- `portfolio_optimizer.py` — Portfolio optimization with risk constraints
- `market_data_processor.py` — Real-time market data processing and feature extraction
- `multi_venue_execution.py` — Multi-venue order routing and execution
- `algorithmic_strategy_library.py` — Library of algorithmic trading strategies with parameter tuning
- `portfolio_risk_analytics.py` — VaR, stress testing, scenario analysis, Monte Carlo simulation
- `algorithmic_market_making.py` — Quote generation, inventory management, adverse selection detection
- `extreme_events_detector.py` — Detection of extreme market events with early warning
- `dynamic_sizing_engine.py` — Dynamic position sizing with risk-adjusted Kelly criterion
- `trading_belief_revision.py` — Bayesian belief revision for trading decisions
- `cross_chain_yield_optimizer.py` — Multi-chain yield optimization
- `capital_allocator.py` — Capital allocation across strategies
- `portfolio_rebalancing_system.py` — Automated portfolio rebalancing with drift correction
- `portfolio_optimization_engine.py` — Modern portfolio theory with risk parity allocation
- `market_microstructure_analyzer.py` — Order book analysis, liquidity detection, market impact
- `regime_change_detector.py` — Market regime detection, structural break identification

**API:** `/api/v1/trading/*`

### 3. VyralX — Video Content Intelligence Agent
**Role:** Video analytics, content creation, audience engagement.
**Port:** 5002 | **Stack:** Python, FastAPI

**Deep Modules (76):**
- `content_optimizer.py` — Video content optimization with audience targeting
- `audience_analytics.py` — Audience behavior analysis with cohort tracking
- `multilingual_content_translator.py` — AI-powered multilingual content translation and localization
- `personalized_recommendation.py` — Personalized content recommendations with real-time adaptation
- `video_analytics_dashboard.py` — Video metrics, demographics, retention curves, virality
- `content_calendar_manager.py` — Content scheduling, pipelines, cross-platform distribution
- `workflow_manager.py` — Content workflow orchestration with approval gates
- `influencer_campaign_manager.py` — Influencer campaign management with ROI tracking
- `audience_segmentation_engine.py` — Advanced audience segmentation with clustering
- `content_monetization_optimizer.py` — Monetization strategy optimization
- `creator_collab_network.py` — Creator collaboration network with matchmaking
- `content_accessibility_enhancer.py` — Accessibility improvements with auto-captioning
- `realtime_collaboration.py` — Real-time collaborative editing and review
- `content_performance_analyzer.py` — Content performance metrics, engagement analysis, trend detection

- `app/services/diagram_service.py` — **live wiring**: self-contained HTML+SVG diagram rendering behind `/api/v1/diagrams/*` and automatic explainer diagrams in every generated content pack

**API:** `/api/v1/vyralx/*` and `/api/v1/diagrams/*`

### 4. Cortex — Decision Intelligence Agent
**Role:** Predictive analytics, decision support, scenario planning.
**Port:** 5003 | **Stack:** Python, FastAPI

**Deep Modules (41):**
- `decision_engine.py` — Multi-criteria decision analysis with uncertainty quantification
- `scenario_analyzer.py` — Scenario planning with Monte Carlo simulation
- `predictive_model_manager.py` — ML model lifecycle management with auto-retraining
- `ab_experiment_framework.py` — A/B testing framework with statistical significance
- `competitive_intelligence.py` — Competitor monitoring, product tracking, pricing analysis, SWOT
- `contextual_bandit_optimizer.py` — Contextual bandit optimization for real-time decision making
- `causal_impact_analyzer.py` — Causal impact analysis with counterfactual reasoning
- `strategic_planning_assistant.py` — Long-term strategic planning with roadmap generation
- `decision_tree_explorer.py` — Interactive decision tree exploration and analysis
- `predictive_customer_behavior_model.py` — Customer behavior prediction with churn analysis
- `marketing_attribution_modeler.py` — Marketing channel attribution with multi-touch modeling
- `autonomous_experiment_designer.py` — AI-powered experiment design and optimization
- `decision_impact_analyzer.py` — Decision outcome tracking and impact measurement

**API:** `/api/v1/cortex/*`

### 5. Inference — Reasoning Engine Agent
**Role:** Logical reasoning, inference, knowledge graph operations.
**Port:** 5004 | **Stack:** Python, FastAPI

**Deep Modules (29):**
- `reasoning_engine.py` — Multi-step logical inference with confidence tracking
- `knowledge_graph_processor.py` — Knowledge graph operations with query optimization
- `reasoning_chain_optimizer.py` — Reasoning chain optimization with strategy recommendations
- `multi_hypothesis_reasoner.py` — Multi-hypothesis reasoning with Bayesian updating
- `belief_revision_engine.py` — Belief revision with AGM axioms
- `multi_model_deliberation_engine.py` — Multi-model deliberation with consensus
- `argument_analysis_engine.py` — Argument structure analysis with validity checking
- `causal_inference_engine.py` — Causal inference with structural equation models
- `reasoning_path_explorer.py` — Reasoning path exploration with graph traversal
- `knowledge_conflict_resolver.py` — Knowledge conflict resolution with priority-based merging
- `temporal_reasoning_engine.py` — Time-aware reasoning with temporal logic
- `commonsense_reasoning_engine.py` — Commonsense knowledge application and everyday reasoning

- `app/scientific_service.py` — **live wiring**: research-skill routing, statistics, power, hypotheses and evidence audit behind `/v1/scientific/*` and the inter-agent `/v1/agent/research-plan`

**API:** `/api/v1/inference/*` and `/v1/scientific/*`

### 6. Forge — Autonomous Coding Agent
**Role:** Code generation, testing, deployment automation.
**Port:** 5005 | **Stack:** Python, FastAPI

**Deep Modules (27):**
- `autonomous_laptop_operator.py` — Full-stack autonomous development with browser automation
- `code_synthesis_engine.py` — AI-powered code synthesis with multi-language support
- `distributed_dev_environment.py` — Multi-environment development with state synchronization
- `code_review_router.py` — Automated code review with security scanning and reviewer suggestions
- `autonomous_code_repair.py` — Autonomous code repair with test-driven debugging
- `deployment_pipeline_manager.py` — CI/CD pipeline management with deployment automation
- `test_generation_engine.py` — Automated test generation with coverage optimization
- `code_refactoring_engine.py` — Code refactoring with pattern detection
- `dependency_analyzer.py` — Dependency graph analysis with vulnerability detection
- `performance_profiler.py` — Code performance profiling with bottleneck detection
- `quantum_flow_optimizer.py` — Quantum-inspired optimization for code execution paths
- `code_analysis_engine.py` — Static code analysis with complexity metrics
- `build_pipeline_manager.py` — Build orchestration with CI/CD integration

**API:** `/api/v1/forge/*`

### 7. Memora — Memory Intelligence Agent
**Role:** Persistent memory, knowledge storage, context management.
**Port:** 5006 | **Stack:** Python, FastAPI

**Deep Modules (33):**
- `semantic_memory_store.py` — Semantic memory with vector-based retrieval
- `episodic_memory_manager.py` — Episodic memory with temporal indexing
- `causal_memory_graph.py` — Causal relationships between memories with inference
- `memory_consolidation_engine.py` — Memory consolidation with importance scoring, decay, merging
- `emotional_memory_processor.py` — Emotional memory processing with affect-aware retrieval
- `prospective_memory_tracker.py` — Prospective memory with future task reminders
- `working_memory_manager.py` — Working memory with limited capacity management
- `spatial_memory_mapper.py` — Spatial memory with location-based indexing
- `cultural_memory_archive.py` — Cultural knowledge archive with community memory
- `memory_access_pattern_analyzer.py` — Access pattern analysis with caching optimization
- `memory_consolidation_coordinator.py` — Cross-memory-type consolidation coordination
- `memory_distillation_engine.py` — Memory distillation for long-term retention
- `memory_provenance_tracker.py` — Memory provenance tracking with source verification
- `memory_retrieval_engine.py` — Semantic memory retrieval with context-aware search

- `core/memory/context_service.py` — **live wiring**: `viking://` context database (L0/L1/L2, scoped search, session commits, wiki) behind `/v1/context/*` and the shared `mesh.memory_fabric`

**API:** `/api/v1/memora/*` and `/v1/context/*`

### 8. IntelX — Threat Intelligence Agent
**Role:** Cybersecurity, threat intelligence, OSINT, breach monitoring.
**Port:** 5007 | **Stack:** Python, FastAPI

**Deep Modules (13):**
- `threat_detection_engine.py` — Multi-source threat detection with correlation
- `osint_collector.py` — OSINT data collection with multi-source aggregation
- `dynamic_osint_collector.py` — Adaptive OSINT collection with real-time targeting
- `threat_intel_knowledge_base.py` — TTPs, actor profiles, incidents, IoCs, relationship graph
- `dark_web_monitor.py` — Dark web leak monitoring, breach alerts, credential tracking
- `predictive_threat_analyzer.py` — Predictive threat analysis with attack path modeling
- `adversary_emulation_engine.py` — Adversary emulation with MITRE ATT&CK mapping
- `threat_campaign_tracker.py` — Multi-incident campaign tracking and correlation
- `threat_intel_correlation_engine.py` — Cross-source threat correlation with confidence scoring
- `threat_forecast_engine.py` — Threat forecasting with temporal pattern analysis
- `threat_hunting_query_optimizer.py` — Query optimization for threat hunting
- `intel_sharing_manager.py` — Intelligence sharing with STIX/TAXII compatibility
- `disinformation_detector.py` — False information detection with source credibility analysis

**API:** `/api/v1/intelex/*`

### 9. Futuris — Predictive Intelligence Agent
**Role:** Forecasting, predictive modeling, scenario simulation.
**Port:** 5008 | **Stack:** Python, FastAPI

**Deep Modules (11):**
- `forecasting_engine.py` — Multi-model forecasting with calibration and accuracy tracking
- `realtime_event_impact.py` — Real-time event impact assessment with propagation modeling
- `ensemble_reconciliation.py` — Multi-model ensemble forecasting with reconciliation
- `predictive_maintenance.py` — Predictive maintenance with failure mode analysis
- `market_regime_detector.py` — Market regime detection with HMM and transition modeling
- `event_probability_forecaster.py` — Probability forecasting for rare events
- `scenario_stress_tester.py` — Stress testing with extreme scenario generation
- `prediction_calibration_optimizer.py` — Forecast calibration with bias correction
- `skill_acquisition_planner.py` — Skill gap analysis and learning path generation

**API:** `/api/v1/futuris/*`

### 10. Sentinel — Security Operations Agent
**Role:** Security monitoring, threat hunting, compliance auditing.
**Port:** 5009 | **Stack:** Python, Flask

**Deep Modules (20):**
- `security_monitor.py` — Real-time security monitoring with SIEM integration
- `threat_hunting_assistant.py` — AI-assisted threat hunting with hypothesis generation
- `zero_trust_enforcer.py` — Zero-trust policy enforcement with identity verification
- `compliance_audit_trail.py` — Automated compliance auditing with evidence collection
- `vulnerability_scanner.py` — Automated vulnerability scanning with CVSS scoring
- `realtime_threat_matcher.py` — Real-time threat pattern matching with IoC feeds
- `security_posture_assessor.py` — Security posture scoring with trend analysis
- `behavioral_anomaly_detector.py` — Behavioral anomaly detection with baseline profiling
- `vulnerability_management_system.py` — Vulnerability lifecycle management with remediation tracking
- `siem_integration_bridge.py` — SIEM integration with log ingestion and correlation
- `incident_response_playbook.py` — Automated incident response with playbook execution
- `security_slade_engine.py` — Security SLA tracking and compliance posture scoring
- `threat_hunting_automation_engine.py` — Automated threat hunting with hypothesis generation

- `app/services/cyber_skills_service.py` — **live wiring**: ATT&CK/NIST CSF/D3FEND/ATLAS/F3 skill engine behind `/v1/cyber/*`, incident-triage crosswalk and posture-report CSF alignment

**API:** `/api/v1/sentinel/*` and `/v1/cyber/*`

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

## Cross-Agent Integration

The FRIDAY Universe implements full cross-agent integration:

- **Dispatch Bus** — FRIDAY dispatches to all 9 specialists with circuit breakers and retry
- **Peer Calls** — Specialists call each other directly (8 pre-configured integrations)
- **Unified Auth** — Capability-based authorization across all agents
- **Security Hardening** — SSRF protection, path traversal defense, input validation

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
- **149/149 tests passing** (17 skipped)

## Cross-Cutting Infrastructure

| Module | Description |
|--------|-------------|
| `universe_dispatch_bus.py` | Unified dispatch to all 9 specialists |
| `universe_auth.py` | Unified authentication and authorization |
| `cross_agent_integration.py` | Specialist-to-specialist peer calls |
| `security_hardening.py` | SSRF, path traversal, CORS, input validation |
| `universe_gateway.py` | Unified API gateway |
| `universe_config.py` | Centralized configuration |
| `universe_metrics.py` | Prometheus-compatible metrics |
| `universe_health_monitor.py` | Cross-agent health checking |
| `agent_mesh_router.py` | Agent mesh routing |
| `error_envelope.py` | Unified error handling |
| `universe_resilience.py` | Universe-wide fault tolerance |
| `universe_cost_optimizer.py` | Cross-agent cost tracking |

## Total: 100 new deep modules across 10 agents + 21 cross-cutting infrastructure modules
