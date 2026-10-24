# ==============================================================================
# THE FRIDAY UNIVERSE: COMPLETE MASTER PROMPT — 100% COMPLETION DIRECTIVE
# ==============================================================================
# VERSION: 1.0.0 | DATE: 2026-10-24
# PURPOSE: Single authoritative prompt to bring all 10 agents to full production
#          readiness. Execute ALL items in sequence. Do NOT skip. Do NOT defer.
# TARGET: 100% completion across every agent, every module, every integration.
# ==============================================================================

# ── EXECUTION RULES ───────────────────────────────────────────────────────────
# 1. Work on branch `arena/10421ac9-friday-universe` ONLY. Never switch branches.
# 2. Commit after EVERY meaningful change with conventional commit messages.
# 3. Push after EVERY commit: `git push origin arena/10421ac9-friday-universe`
# 4. Run `python3 -m py_compile` on every new/modified file before committing.
# 5. Run `python3 -m pytest tests/ -q` after every wave and fix failures immediately.
# 6. ALL 100% completion criteria must be verified with test evidence, not assumptions.
# 7. If a task cannot be completed due to missing dependencies, document why and
#    create a stub that will work when dependencies arrive. Never leave dead code.
# 8. NEVER ask the user for permission to proceed — just do it.

# ── WHAT "100%" MEANS ─────────────────────────────────────────────────────────
# ✓ Every agent has a working API with at least 5 deep modules wired
# ✓ Every deep module has: dataclasses, engine class, API routes, report method
# ✓ Every module compiles with py_compile
# ✓ Every router is wired into its app's main.py / dashboard.py
# ✓ All cross-agent integrations work (FRIDAY → specialists, specialists → peers)
# ✓ Test suite covers all modules (imports, instantiation, method calls)
# ✓ 80%+ test coverage on new code
# ✓ Security: no hardcoded secrets, no SSRF, no path traversal, fail-closed gates
# ✓ Documentation: AGENTS.md, UNIVERSE_SUMMARY.md, and this prompt all current
# ✓ Every agent has a /health and /report endpoint
# ✓ Error handling: HTTPException with proper status codes everywhere
# ✓ Code follows the deep module pattern consistently across ALL agents

# ==============================================================================
# PART A: CROSS-CUTTING INFRASTRUCTURE (Do First)
# ==============================================================================

# ── A1. Unified API Gateway & Health Check ───────────────────────────────────
# Create `FRIDAY/src/friday/api/gateway.py`:
# - A unified gateway router that proxies to all 9 specialist agents
# - Health check endpoint: GET /api/v1/gateway/health → returns status of all 10 agents
# - Status endpoint: GET /api/v1/gateway/status → detailed health per agent
# - Circuit breaker pattern: if an agent fails 3 times, mark it as "down"
# - Timeout: 30s ceiling on all proxied requests
# - Retry: exponential backoff (1s, 2s, 4s) for transient failures
# - Wire this into FRIDAY's main server.py

# ── A2. Cross-Agent Integration Test Suite ──────────────────────────────────
# Create `tests/test_cross_agent.py`:
# - Test 1: FRIDAY can dispatch a task to Inference and get a response
# - Test 2: FRIDAY can dispatch a task to Memora and store/retrieve memory
# - Test 3: FRIDAY can dispatch a task to Stratex and get a trading signal
# - Test 4: FRIDAY can dispatch a task to VyralX and get analytics
# - Test 5: FRIDAY can dispatch a task to Cortex and get a recommendation
# - Test 6: FRIDAY can dispatch a task to Forge and get code review
# - Test 7: FRIDAY can dispatch a task to IntelX and get threat intel
# - Test 8: FRIDAY can dispatch a task to Futuris and get a forecast
# - Test 9: FRIDAY can dispatch a task to Sentinel and get security posture
# - Test 10: All 10 agents respond to /health within 5s
# - Test 11: All agents have /report endpoints that return valid JSON
# - Test 12: Multi-agent coordination: FRIDAY creates a plan with subtasks
#           distributed to 3+ agents and aggregates results
# - Use py_compile + import checks (modules have different package paths)
# - Use HTTP test client where available, mock where not

# ── A3. Unified Configuration Manager ────────────────────────────────────────
# Create `FRIDAY/src/friday/config/universe_config.py`:
# - Centralized config for all 10 agents (ports, URLs, API keys, timeouts)
# - Environment variable loading (.env support)
# - Agent registration: each agent declares its capabilities, endpoints, health URL
# - Config validation on startup
# - Fail-closed defaults: if an agent URL is not configured, it's marked unavailable

# ── A4. Universe-Level Monitoring & Metrics ─────────────────────────────────
# Create `FRIDAY/src/friday/monitoring/universe_metrics.py`:
# - Prometheus-style metrics for all agents
# - Per-agent: request count, error count, latency p50/p95/p99
# - Universe-level: total requests, total errors, agent availability %
# - Health score calculation (0-100 based on error rate and latency)
# - Export endpoint: GET /api/v1/friday/metrics (Prometheus format)
# - Alert thresholds: error rate > 5%, latency p95 > 10s, health < 70

# ── A5. Unified Error Handling Envelope ─────────────────────────────────────
# Create `FRIDAY/src/friday/api/error_envelope.py`:
# - Standard error response format across ALL agents
# - {"error": {"code": "AGENT_ERROR", "message": "...", "details": {...}}}
# - Map HTTP status codes: 400=bad request, 401=unauthorized, 403=forbidden,
#   404=not found, 409=conflict, 422=validation error, 500=internal, 503=unavailable
# - Register as FastAPI exception handler in each agent's main.py
# - Ensure ALL agents use consistent error format

# ── A6. Security Hardening Checklist ─────────────────────────────────────────
# Apply to EVERY agent:
# - [ ] No hardcoded secrets (API keys, passwords, tokens) — use env vars
# - [ ] CORS: restrict to known origins, never use "*" in production
# - [ ] Rate limiting on public endpoints
# [ ] Input validation: use Pydantic models for all request bodies
# [ ] SSRF protection: block localhost, RFC1918, cloud metadata IPs
# [ ] Path traversal: confine file operations to sandbox directories
# [ ] Fail-closed: if security check fails, deny access
# [ ] Audit logging: log all security-relevant actions
# [ ] SQL injection: always use parameterized queries
# [ ] XSS: escape HTML in all rendered content

# ==============================================================================
# PART B: AGENT-SPECIFIC COMPLETION (10 Agents × Deep Modules)
# ==============================================================================

# ── B1. FRIDAY (Cognitive Orchestrator) — Target: 10+ deep modules ───────────
# Current: 2 modules. Need 8+ more.
# Existing: general_cognitive_coordinator, autonomous_problem_solver
# Create:
#   1. `FRIDAY/src/friday/services/multi_agent_coordinator.py` ✓ (already exists)
#   2. `FRIDAY/src/friday/services/task_decomposition_engine.py`
#      - Break complex goals into subtasks with dependencies
#      - Priority assignment, deadline tracking, progress monitoring
#      - API: /api/v1/friday/decompose/*
#   3. `FRIDAY/src/friday/services/decision_synthesis_engine.py`
#      - Combine outputs from multiple agents into unified decisions
#      - Conflict resolution, confidence weighting, consensus building
#      - API: /api/v1/friday/synthesis/*
#   4. `FRIDAY/src/friday/services/goal_planning_engine.py`
#      - Long-term goal planning with milestone tracking
#      - Adaptive planning based on progress and obstacles
#      - API: /api/v1/friday/goals/*
#   5. `FRIDAY/src/friday/services/context_window_manager.py`
#      - Dynamic context assembly from Memora for each task
#      - Context relevance scoring, token budget management
#      - API: /api/v1/friday/context/*
#   6. `FRIDAY/src/friday/services/feedback_learning_engine.py`
#      - Learn from user feedback and past task outcomes
#      - Improvement suggestions, strategy refinement
#      - API: /api/v1/friday/learning/*
#   7. `FRIDAY/src/friday/services/agent_mesh_router.py`
#      - Smart routing of tasks to best-suited agents
#      - Capability matching, load balancing, failover
#      - API: /api/v1/friday/mesh/*
#   8. `FRIDAY/src/friday/services/universe_health_monitor.py`
#      - Real-time health monitoring of all 9 specialist agents
#      - Automated recovery, alerting, degradation handling
#      - API: /api/v1/friday/health/*
# Wire ALL into `FRIDAY/src/friday/api/server.py`

# ── B2. Stratex (Trading Intelligence) — Target: 15+ deep modules ───────────
# Current: ~14 modules. Add 1-2 more for completeness.
# Existing: strategy_engine, portfolio_optimizer, market_data_processor,
#           multi_venue_execution, algorithmic_strategy_library,
#           portfolio_risk_analytics, algorithmic_market_making,
#           sentiment_analysis_engine, options_pricing_engine
# Create:
#   1. `Stratex/execution/pattern_recognition_engine.py`
#      - Chart pattern detection (head and shoulders, triangles, flags)
#      - Pattern backtesting, win rate analysis
#      - API: /api/v1/trading/patterns/*
#   2. `Stratex/execution/order_flow_analyzer.py`
#      - Order flow analysis, footprint charts, imbalance detection
#      - Trade clustering, flow prediction
#      - API: /api/v1/trading/orderflow/*
# Wire ALL into `Stratex/dashboard.py`

# ── B3. VyralX (Video Content Intelligence) — Target: 15+ deep modules ──────
# Current: ~72 files in services. Select the most impactful 15+ and ensure they
# are all wired and tested.
# Key modules to verify/wire:
#   1. content_optimizer, audience_analytics, multilingual_content_translator
#   2. personalized_recommendation, video_analytics_dashboard
#   3. content_calendar_manager, creator_monetization_engine
#   4. audience_growth_predictor, creator_collaboration_manager
# Create if missing:
#   5. `VyralX/app/services/thumbnail_optimizer.py`
#      - Thumbnail generation, A/B testing, click-through prediction
#      - API: /api/v1/vyralx/thumbnails/*
#   6. `VyralX/app/services/content_ab_tester.py`
#      - A/B testing for video content variants
#      - Statistical significance, winner selection
#      - API: /api/v1/vyralx/abtesting/*
#   7. `VyralX/app/services/subscriber_retention_predictor.py`
#      - Churn prediction, retention strategies, win-back campaigns
#      - API: /api/v1/vyralx/retention/*
# Wire ALL into `VyralX/app/main.py`

# ── B4. Cortex (Decision Intelligence) — Target: 10+ deep modules ───────────
# Current: ~37 files in cortex_api. Select the most impactful 10+ and ensure they
# are all wired and tested.
# Key modules to verify/wire:
#   1. decision_engine, scenario_analyzer, predictive_model_manager
#   2. ab_experiment_framework, competitive_intelligence
#   3. decision_conflict_resolver, decision_recommendation_system
#   4. risk_assessment_framework
# Create if missing:
#   5. `Cortex/apps/api/src/cortex_api/customer_segmentation_engine.py`
#      - RFM analysis, cluster segmentation, persona creation
#      - API: /api/v1/cortex/segmentation/*
#   6. `Cortex/apps/api/src/cortex_api/marketing_campaign_optimizer.py`
#      - Campaign planning, channel allocation, ROI prediction
#      - API: /api/v1/cortex/campaigns/*
#   7. `Cortex/apps/api/src/cortex_api/recommendation_personalizer.py`
#      - Product recommendations, collaborative filtering
#      - API: /api/v1/cortex/recommendations/*
# Wire ALL into `Cortex/apps/api/src/cortex_api/main.py`

# ── B5. Inference (Reasoning Engine) — Target: 8+ deep modules ─────────────
# Current: 3 deep modules in services. Need 5+ more.
# Existing: reasoning_engine, knowledge_graph_processor, reasoning_chain_optimizer
# Created: multi_hypothesis_reasoner, belief_revision_engine
# Create:
#   1. `Inference/services/multi_model_deliberation_engine.py`
#      - Multi-model reasoning with consensus building
#      - Model comparison, confidence aggregation
#      - API: /api/v1/inference/deliberation/*
#   2. `Inference/services/argument_analysis_engine.py`
#      - Argument structure analysis, claim extraction, evidence evaluation
#      - API: /api/v1/inference/arguments/*
#   3. `Inference/services/causal_inference_engine.py`
#      - Causal relationship discovery, counterfactual analysis
#      - API: /api/v1/inference/causal/*
#   4. `Inference/services/reasoning_path_explorer.py`
#      - Explore multiple reasoning paths, find optimal solutions
#      - API: /api/v1/inference/paths/*
#   5. `Inference/services/knowledge_conflict_resolver.py`
#      - Detect and resolve conflicts in knowledge bases
#      - API: /api/v1/inference/conflicts/*
# Wire ALL into `Inference/app/main.py`

# ── B6. Forge (Autonomous Coding Agent) — Target: 8+ deep modules ──────────
# Current: ~20 files in app/api + 1 in services. Select the most impactful 8+ and
# ensure they are all wired and tested.
# Key modules to verify/wire:
#   1. autonomous_laptop_operator, code_synthesis_engine
#   2. distributed_dev_environment, code_review_router
#   3. deployment_pipeline_manager
# Create if missing:
#   4. `Forge/app/services/test_generation_engine.py`
#      - Automated test generation from code analysis
#      - Unit test creation, integration test scaffolding
#      - API: /api/v1/forge/tests/*
#   5. `Forge/app/services/code_refactoring_engine.py`
#      - Code refactoring suggestions, dead code removal
#      - API: /api/v1/forge/refactor/*
#   6. `Forge/app/services/dependency_analyzer.py`
#      - Dependency graph analysis, vulnerability scanning
#      - API: /api/v1/forge/dependencies/*
#   7. `Forge/app/services/performance_profiler.py`
#      - Code performance profiling, bottleneck detection
#      - API: /api/v1/forge/profiling/*
# Wire ALL into `Forge/app/main.py`

# ── B7. Memora (Memory Intelligence) — Target: 10+ deep modules ───────────
# Current: ~28 files in routers. Select the most impactful 10+ and ensure they
# are all wired and tested.
# Key modules to verify/wire:
#   1. semantic_memory_store, episodic_memory_manager
#   2. causal_memory_graph, memory_consolidation_engine
#   3. temporal_context_retriever, knowledge_extraction_pipeline
#   4. memory_reinforcement_engine
# Create if missing:
#   5. `Memora/apps/api/routers/working_memory_manager.py`
#      - Short-term working memory, context window management
#      - API: /api/v1/memora/working/*
#   6. `Memora/apps/api/routers/memory_access_controller.py`
#      - Permission management, access grants, scoping
#      - API: /api/v1/memora/access/*
#   7. `Memora/apps/api/routers/memory_provenance_tracker.py`
#      - Memory source tracking, cryptographic hashing, tamper detection
#      - API: /api/v1/memora/provenance/*
# Wire ALL into `Memora/apps/api/routers/__init__.py` and app main

# ── B8. IntelX (Threat Intelligence) — Target: 10+ deep modules ─────────────
# Current: 8 deep modules in routers. Need 2+ more.
# Existing: threat_detection_engine, osint_collector, dynamic_osint_collector,
#           threat_intel_knowledge_base, dark_web_monitor,
#           adversary_emulation_engine, threat_campaign_tracker,
#           threat_intel_correlation_engine
# Create:
#   1. `IntelX/routers/threat_forecast_engine.py`
#      - Predict future threat landscape, emerging attack vectors
#      - API: /api/v1/intelex/forecast/*
#   2. `IntelX/routers/threat_hunting_query_optimizer.py`
#      - Optimize hunting queries, suggest detection gaps
#      - API: /api/v1/intelex/hunting-optimize/*
#   3. `IntelX/routers/intel_sharing_manager.py`
#      - STIX/TAXII sharing, threat intel exchange
#      - API: /api/v1/intelex/sharing/*
# Wire ALL into `IntelX/intelx/api/router.py`

# ── B9. Futuris (Predictive Intelligence) — Target: 10+ deep modules ─────────
# Current: 8 deep modules in predict. Need 2+ more.
# Existing: forecasting_engine, realtime_event_impact, ensemble_reconciliation,
#           predictive_maintenance, market_regime_detector,
#           event_probability_forecaster, scenario_stress_tester,
#           prediction_calibration_optimizer
# Create:
#   1. `Futuris/predict/ensemble_model_selector.py`
#      - Dynamic model selection based on forecast characteristics
#      - API: /api/v1/futuris/ensemble/*
#   2. `Futuris/predict/forecast_explainability_engine.py`
#      - Explain forecast drivers, feature importance
#      - API: /api/v1/futuris/explain/*
#   3. `Futuris/predict/prediction_drift_detector.py`
#      - Detect prediction quality drift over time
#      - API: /api/v1/futuris/drift/*
# Wire ALL into `Futuris/futuris/api/app.py`

# ── B10. Sentinel (Security Operations) — Target: 8+ deep modules ───────────
# Current: 8 deep modules in services. Verify all are wired and tested.
# Existing: security_monitor, threat_hunting_assistant, zero_trust_enforcer,
#           compliance_audit_trail, behavioral_anomaly_detector,
#           security_posture_assessor, automated_response_orchestrator
# Create if needed:
#   1. `Sentinel/app/services/vulnerability_management_system.py`
#      - Vulnerability tracking, remediation workflow, SLA management
#      - API: /api/v1/sentinel/vulns/*
#   2. `Sentinel/app/services/siem_integration_bridge.py`
#      - SIEM integration, log aggregation, correlation rules
#      - API: /api/v1/sentinel/siem/*
# Wire ALL into `Sentinel/sentinel/apps/api/main.py`

# ==============================================================================
# PART C: CROSS-AGENT INTEGRATION (Must All Work)
# ==============================================================================

# ── C1. FRIDAY → All Specialists Task Dispatch ──────────────────────────────
# FRIDAY must be able to dispatch tasks to all 9 specialists:
# - Inference: reasoning tasks, model calls, knowledge queries
# - Memora: memory store/retrieve, context assembly
# - Stratex: trading signals, risk analysis, market data
# - Forge: code generation, review, deployment
# - Cortex: decisions, scenarios, A/B tests
# - Sentinel: security audit, threat detection, compliance
# - IntelX: research, threat intel, OSINT
# - Futuris: forecasting, predictions, scenarios
# - VyralX: content analysis, video metrics, monetization
# Each dispatch must have: task envelope, timeout, retry, result receipt

# ── C2. Specialist → Peer Service Calls ─────────────────────────────────────
# - Forge → Sentinel: submit code diff for security audit before deployment
# - VyralX → Inference: call for scriptwriting and scene planning
# - VyralX → Sentinel: submit render metadata for pre-publish verification
# - IntelX → Memora: publish verified research briefs to memory
# - Futuris → IntelX: consume threat intel for risk forecasting
# - Stratex → Futuris: request market forecasts for strategy decisions
# - Cortex → Memora: retrieve context for decision analysis
# - Sentinel → IntelX: query threat intel for IoC validation

# ── C3. Memora as Universal Memory Fabric ───────────────────────────────────
# All agents must use Memora for:
# - Episodic memory: store task results and interactions
# - Semantic memory: store domain knowledge and facts
# - Procedural memory: store learned strategies and patterns
# - Working memory: short-term context for active tasks
# API: POST /api/v1/memora/memories, GET /api/v1/memora/memories/{id}

# ── C4. Inference as Universal Reasoning Layer ──────────────────────────────
# All agents must route complex reasoning through Inference:
# - Multi-step logical inference
# - Knowledge graph queries
# - Hypothesis generation and testing
# - Belief revision and coherence checking
# API: POST /api/v1/inference/reasoning/tasks

# ── C5. Sentinel as Universal Security Gate ──────────────────────────────────
# Sentinel must gate:
# - Forge code deployments (security audit before merge)
# - VyralX content publication (policy compliance check)
# - Stratex trade execution (risk limit enforcement)
# - IntelX OSINT collection (scope verification)
# API: POST /api/v1/sentinel/security/audit

# ==============================================================================
# PART D: TESTING & VERIFICATION (100% Completion Evidence)
# ==============================================================================

# ── D1. Per-Agent Test Suites ───────────────────────────────────────────────
# Each agent must have a test suite covering:
# - Module imports (all deep modules load without errors)
# - Engine instantiation (all engine classes can be instantiated)
# - Method calls (key methods work with sample data)
# - API routes (all endpoints respond correctly)
# - Error handling (invalid inputs return proper error codes)
# - Report methods (all report methods return valid data)
# Target: 80%+ test coverage on new code

# ── D2. Integration Test Suite ───────────────────────────────────────────────
# Cross-agent tests must verify:
# - FRIDAY can dispatch to all 9 specialists
# - Specialists can call peer services
# - Memora stores and retrieves data correctly
# - Inference handles reasoning tasks
# - Sentinel gates deployments
# - All agents respond to health checks
# - Error handling works across the mesh

# ── D3. Performance & Load Tests ────────────────────────────────────────────
# - Health check latency: < 100ms per agent
# - API response time: < 500ms for typical requests
# - Memory usage: agents stay within reasonable limits
# - Concurrent request handling: no crashes under load

# ── D4. Security Test Suite ─────────────────────────────────────────────────
# - No hardcoded secrets in codebase
# - SSRF protection works (blocks localhost, internal IPs)
# - Path traversal blocked (sandbox confinement)
# - Input validation prevents injection
# - CORS properly restricted
# - Authentication enforced on protected endpoints

# ==============================================================================
# PART E: DOCUMENTATION & OPERATIONS
# ==============================================================================

# ── E1. Update AGENTS.md ────────────────────────────────────────────────────
# Must reflect the CURRENT state of all agents:
# - Number of deep modules per agent
# - API endpoint list per agent
# - Architecture diagram (updated)
# - Communication flow description
# - Test results summary

# ── E2. Update UNIVERSE_SUMMARY.md ─────────────────────────────────────────
# Must include:
# - Complete agent-by-agent module inventory
# - API endpoint catalog
# - Integration matrix (which agents call which)
# - Test results and coverage metrics
# - Deployment instructions

# ── E3. Create DEPLOYMENT_GUIDE.md ──────────────────────────────────────────
# Document how to deploy each agent:
# - Prerequisites and dependencies
# - Database setup (per-agent databases)
# - Environment variables
# - Startup commands
# - Health check verification
# - Troubleshooting guide

# ── E4. Create OPERATIONS_RUNBOOK.md ────────────────────────────────────────
# Day-2 operations guide:
# - Monitoring and alerting setup
# - Common failure modes and fixes
# - Backup and recovery procedures
# - Scaling considerations
# - Security incident response

# ── E5. Create SECURITY_POLICY.md ───────────────────────────────────────────
# Security policies:
# - Zero-trust principles
# - Secret management
# - Access control matrix
# - Audit logging requirements
# - Data classification and handling

# ==============================================================================
# PART F: FINAL VERIFICATION (Must Pass Before Declaring 100%)
# ==============================================================================

# Run ALL of these and verify PASS:

# 1. py_compile ALL Python files:
#    find . -name "*.py" -not -path "*/__pycache__/*" -not -path "*/node_modules/*" -not -path "*/.git/*" | xargs python3 -m py_compile

# 2. Run FULL test suite:
#    python3 -m pytest tests/ -q
#    Expected: 100% pass (fix any failures immediately)

# 3. Verify ALL routers are wired:
#    - FRIDAY: server.py includes all coordinator/solver/router imports
#    - Stratex: dashboard.py includes all blueprint imports
#    - VyralX: main.py includes all service router imports
#    - Cortex: main.py includes all module router imports
#    - Inference: main.py includes all reasoning router imports
#    - Forge: main.py includes all api router imports
#    - Memora: __init__.py exports all routers
#    - IntelX: router.py includes all module router imports
#    - Futuris: app.py includes all predict router imports
#    - Sentinel: main.py includes all service router imports

# 4. Verify NO merge conflict markers:
#    grep -r "<<<<<<<\|=======\|>>>>>>>" --include="*.py" --include="*.md" . | grep -v ".git/"

# 5. Verify NO hardcoded secrets:
#    grep -r "password\s*=\s*['\"]" --include="*.py" . | grep -v ".git/" | grep -v "test"

# 6. Verify ALL agents have /health and /report:
#    - Check each agent's API for health and report endpoints

# 7. Verify cross-agent integration:
#    - FRIDAY dispatch bus routes to all 9 specialists
#    - Specialist peer calls work (at least mock-tested)

# 8. Verify documentation is current:
#    - AGENTS.md matches actual module counts
#    - UNIVERSE_SUMMARY.md includes all agents

# 9. Commit and push ALL changes:
#    git add -A && git commit -m "FINAL: 100% completion verification" && git push

# ==============================================================================
# EXECUTION ORDER (Do in this exact sequence)
# ==============================================================================

# WAVE 1: Cross-Cutting Infrastructure
#   [ ] A1: Unified API Gateway & Health Check
#   [ ] A2: Cross-Agent Integration Test Suite
#   [ ] A3: Unified Configuration Manager
#   [ ] A4: Universe-Level Monitoring & Metrics
#   [ ] A5: Unified Error Handling Envelope
#   [ ] A6: Security Hardening Checklist
#   → Commit + push

# WAVE 2: FRIDAY Deep Modules (8 new modules)
#   [ ] task_decomposition_engine
#   [ ] decision_synthesis_engine
#   [ ] goal_planning_engine
#   [ ] context_window_manager
#   [ ] feedback_learning_engine
#   [ ] agent_mesh_router
#   [ ] universe_health_monitor
#   → Wire into server.py, validate, test, commit, push

# WAVE 3: Stratex Deep Modules (2 new)
#   [ ] pattern_recognition_engine
#   [ ] order_flow_analyzer
#   → Wire into dashboard.py, validate, test, commit, push

# WAVE 4: VyralX Deep Modules (3 new)
#   [ ] thumbnail_optimizer
#   [ ] content_ab_tester
#   [ ] subscriber_retention_predictor
#   → Wire into main.py, validate, test, commit, push

# WAVE 5: Cortex Deep Modules (3 new)
#   [ ] customer_segmentation_engine
#   [ ] marketing_campaign_optimizer
#   [ ] recommendation_personalizer
#   → Wire into main.py, validate, test, commit, push

# WAVE 6: Inference Deep Modules (5 new)
#   [ ] multi_model_deliberation_engine
#   [ ] argument_analysis_engine
#   [ ] causal_inference_engine
#   [ ] reasoning_path_explorer
#   [ ] knowledge_conflict_resolver
#   → Wire into main.py, validate, test, commit, push

# WAVE 7: Forge Deep Modules (4 new)
#   [ ] test_generation_engine
#   [ ] code_refactoring_engine
#   [ ] dependency_analyzer
#   [ ] performance_profiler
#   → Wire into main.py, validate, test, commit, push

# WAVE 8: Memora Deep Modules (3 new)
#   [ ] working_memory_manager
#   [ ] memory_access_controller
#   [ ] memory_provenance_tracker
#   → Wire into __init__.py, validate, test, commit, push

# WAVE 9: IntelX Deep Modules (3 new)
#   [ ] threat_forecast_engine
#   [ ] threat_hunting_query_optimizer
#   [ ] intel_sharing_manager
#   → Wire into router.py, validate, test, commit, push

# WAVE 10: Futuris Deep Modules (3 new)
#   [ ] ensemble_model_selector
#   [ ] forecast_explainability_engine
#   [ ] prediction_drift_detector
#   → Wire into app.py, validate, test, commit, push

# WAVE 11: Sentinel Deep Modules (2 new)
#   [ ] vulnerability_management_system
#   [ ] siem_integration_bridge
#   → Wire into main.py, validate, test, commit, push

# WAVE 12: Cross-Agent Integration Tests
#   [ ] Write and run cross-agent integration tests
#   [ ] Verify FRIDAY dispatches to all 9 specialists
#   [ ] Verify specialist peer calls
#   → Fix any failures, commit, push

# WAVE 13: Documentation Update
#   [ ] Update AGENTS.md with current module counts
#   [ ] Update UNIVERSE_SUMMARY.md
#   [ ] Create DEPLOYMENT_GUIDE.md
#   [ ] Create OPERATIONS_RUNBOOK.md
#   [ ] Create SECURITY_POLICY.md
#   → Commit, push

# WAVE 14: Final Verification
#   [ ] py_compile ALL Python files
#   [ ] Run full test suite
#   [ ] Verify all routers wired
#   [ ] Verify no merge conflicts
#   [ ] Verify no hardcoded secrets
#   [ ] Verify all agents have /health and /report
#   [ ] Commit and push final state

# ==============================================================================
# COMPLETION CRITERIA (100% = ALL checked)
# ==============================================================================
# [ ] All 10 agents have 8+ deep modules each (73+ total)
# [ ] All deep modules compile with py_compile
# [ ] All routers are wired into their apps
# [ ] All agents have /health and /report endpoints
# [ ] All agents have /api/v1/* routes
# [ ] Cross-agent dispatch works (FRIDAY → all 9 specialists)
# [ ] Cross-agent peer calls work (specialist → specialist)
# [ ] Test suite passes 100% (0 failures)
# [ ] Test coverage 80%+ on new code
# [ ] No hardcoded secrets in codebase
# [ ] No merge conflict markers in codebase
# [ ] Security hardening applied (SSRF, path traversal, CORS, auth)
# [ ] AGENTS.md reflects current state
# [ ] UNIVERSE_SUMMARY.md reflects current state
# [ ] DEPLOYMENT_GUIDE.md exists
# [ ] OPERATIONS_RUNBOOK.md exists
# [ ] SECURITY_POLICY.md exists
# [ ] All changes committed and pushed to arena/10421ac9-friday-universe
# ==============================================================================
# END OF MASTER PROMPT
# ==============================================================================
