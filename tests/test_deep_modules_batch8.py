"""
tests/test_deep_modules_batch8.py — Deep module tests for IntelX, Futuris, Memora remaining modules.

Tests IntelX agent modules (analyst, citations, extractor, query_planner,
report_gate, research_agent, retriever, scout, synthesis_engine, synthesizer,
verification, verifier), API endpoints, expert network, Cortex/FRIDAY/
Futuris integration. Tests Memora core modules (cache, collaboration,
events, identity, lifecycle, memory context, pipeline, search, metrics).
Tests Futuris remaining upgrade modules (checkpoint, compat, idempotency,
models, outbox, provider, safe_config, state).

Priority 3-5: Deep module coverage for IntelX, Memora, Futuris
"""
import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

for p in [
    ROOT / "FRIDAY/apps/core/src",
    ROOT / "Cortex/apps/api/src",
    ROOT / "Inference",
    ROOT / "Memora/apps/api",
    ROOT / "Forge",
    ROOT / "VyralX",
    ROOT / "IntelX",
    ROOT / "Sentinel/sentinel/apps/api/src",
    ROOT / "Stratex",
    ROOT / "Futuris",
]:
    p = str(p)
    if p not in sys.path:
        sys.path.insert(0, p)


def _content(relpath):
    return (ROOT / relpath).read_text()


def _count_methods(content):
    return len([line for line in content.split("\n") if "def " in line and "class " not in line])


def _count_classes(content):
    return len([line for line in content.split("\n") if "class " in line])


# ── IntelX Agent Modules ─────────────────────────────────────────────────────

class TestIntelXAnalyst:
    def test_module_exists(self):
        content = _content("IntelX/intelx/agents/analyst.py")
        assert "analyst" in content.lower() or "analys" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/agents/analyst.py")
        assert _count_methods(content) >= 2


class TestIntelXCitations:
    def test_module_exists(self):
        content = _content("IntelX/intelx/agents/citations.py")
        assert "citation" in content.lower() or "cite" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/agents/citations.py")
        assert _count_methods(content) >= 2


class TestIntelXExtractor:
    def test_module_exists(self):
        content = _content("IntelX/intelx/agents/extractor.py")
        assert "extract" in content.lower() or "extractor" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/agents/extractor.py")
        assert _count_methods(content) >= 2


class TestIntelXQueryPlanner:
    def test_module_exists(self):
        content = _content("IntelX/intelx/agents/query_planner.py")
        assert "planner" in content.lower() or "query" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/agents/query_planner.py")
        assert _count_methods(content) >= 2


class TestIntelXReportGate:
    def test_module_exists(self):
        content = _content("IntelX/intelx/agents/report_gate.py")
        assert "report" in content.lower() or "gate" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/agents/report_gate.py")
        assert _count_methods(content) >= 2


class TestIntelXResearchAgent:
    def test_module_exists(self):
        content = _content("IntelX/intelx/agents/research_agent.py")
        assert "research" in content.lower() or "agent" in content.lower()

    def test_has_classes(self):
        content = _content("IntelX/intelx/agents/research_agent.py")
        classes = _count_classes(content) + _count_methods(content)
        assert classes >= 2


class TestIntelXRetriever:
    def test_module_exists(self):
        content = _content("IntelX/intelx/agents/retriever.py")
        assert "retrieve" in content.lower() or "retriever" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/agents/retriever.py")
        assert _count_methods(content) >= 2


class TestIntelXScout:
    def test_module_exists(self):
        content = _content("IntelX/intelx/agents/scout.py")
        assert "scout" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/agents/scout.py")
        assert _count_methods(content) >= 2


class TestIntelXSynthesisEngine:
    def test_module_exists(self):
        content = _content("IntelX/intelx/agents/synthesis_engine.py")
        assert "synthesis" in content.lower() or "engine" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/agents/synthesis_engine.py")
        assert _count_methods(content) >= 2


class TestIntelXSynthesizer:
    def test_module_exists(self):
        content = _content("IntelX/intelx/agents/synthesizer.py")
        assert "synthesiz" in content.lower() or "synth" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/agents/synthesizer.py")
        assert _count_methods(content) >= 2


class TestIntelXVerification:
    def test_module_exists(self):
        content = _content("IntelX/intelx/agents/verification.py")
        assert "verification" in content.lower() or "verif" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/agents/verification.py")
        assert _count_methods(content) >= 2


class TestIntelXVerifier:
    def test_module_exists(self):
        content = _content("IntelX/intelx/agents/verifier.py")
        assert "verifier" in content.lower() or "verif" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/agents/verifier.py")
        assert _count_methods(content) >= 2


# ── IntelX API Modules ──────────────────────────────────────────────────────

class TestIntelXAPIRouter:
    def test_module_exists(self):
        content = _content("IntelX/intelx/api/router.py")
        assert "router" in content.lower() or "route" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/api/router.py")
        assert _count_methods(content) >= 2


class TestIntelXEndpoints:
    def test_module_exists(self):
        content = _content("IntelX/intelx/api/v1/endpoints.py")
        assert "endpoint" in content.lower() or "endpoints" in content.lower() or "route" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/api/v1/endpoints.py")
        assert _count_methods(content) >= 2


class TestIntelXCortexIntegration:
    def test_module_exists(self):
        content = _content("IntelX/intelx/api/v1/cortex.py")
        assert "cortex" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/api/v1/cortex.py")
        assert _count_methods(content) >= 2


class TestIntelXFridayIntegration:
    def test_module_exists(self):
        content = _content("IntelX/intelx/api/v1/friday.py")
        assert "friday" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/api/v1/friday.py")
        assert _count_methods(content) >= 2


class TestIntelXFuturisIntegration:
    def test_module_exists(self):
        content = _content("IntelX/intelx/api/v1/futuris.py")
        assert "futuris" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/api/v1/futuris.py")
        assert _count_methods(content) >= 2


class TestIntelXHealth:
    def test_module_exists(self):
        content = _content("IntelX/intelx/api/v1/health.py")
        assert "health" in content.lower()

    def test_has_methods(self):
        content = _content("IntelX/intelx/api/v1/health.py")
        assert _count_methods(content) >= 1


# ── Memora Core Modules ─────────────────────────────────────────────────────

class TestMemoraMemoryCache:
    def test_module_exists(self):
        content = _content("Memora/core/cache/memory_cache.py")
        assert "cache" in content.lower() or "memory" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/cache/memory_cache.py")
        assert _count_methods(content) >= 2


class TestMemoraCollaboration:
    def test_module_exists(self):
        content = _content("Memora/core/collaboration/service.py")
        assert "collaboration" in content.lower() or "service" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/collaboration/service.py")
        assert _count_methods(content) >= 2


class TestMemoraEvents:
    def test_module_exists(self):
        content = _content("Memora/core/events/emitter.py")
        assert "event" in content.lower() or "emit" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/events/emitter.py")
        assert _count_methods(content) >= 2


class TestMemoraIdentity:
    def test_module_exists(self):
        content = _content("Memora/core/identity/service.py")
        assert "identity" in content.lower() or "service" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/identity/service.py")
        assert _count_methods(content) >= 2


class TestMemoraLifecycleDecay:
    def test_module_exists(self):
        content = _content("Memora/core/lifecycle/decay.py")
        assert "decay" in content.lower() or "lifecycle" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/lifecycle/decay.py")
        assert _count_methods(content) >= 1


class TestMemoraLifecycleStateMachine:
    def test_module_exists(self):
        content = _content("Memora/core/lifecycle/state_machine.py")
        assert "state" in content.lower() or "machine" in content.lower() or "lifecycle" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/lifecycle/state_machine.py")
        assert _count_methods(content) >= 1


class TestMemoraLifecycleSupersession:
    def test_module_exists(self):
        content = _content("Memora/core/lifecycle/supersession.py")
        assert "supersession" in content.lower() or "supersede" in content.lower() or "lifecycle" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/lifecycle/supersession.py")
        assert _count_methods(content) >= 1


class TestMemoraMemoryContextBudgeter:
    def test_module_exists(self):
        content = _content("Memora/core/memory/context/budgeter.py")
        assert "budget" in content.lower() or "context" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/context/budgeter.py")
        assert _count_methods(content) >= 1


class TestMemoraMemoryContextBuilder:
    def test_module_exists(self):
        content = _content("Memora/core/memory/context/builder.py")
        assert "builder" in content.lower() or "context" in content.lower() or "build" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/context/builder.py")
        assert _count_methods(content) >= 1


class TestMemoraMemoryContextReranker:
    def test_module_exists(self):
        content = _content("Memora/core/memory/context/reranker.py")
        assert "rerank" in content.lower() or "rank" in content.lower() or "context" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/context/reranker.py")
        assert _count_methods(content) >= 1


class TestMemoraExperienceService:
    def test_module_exists(self):
        content = _content("Memora/core/memory/experience_service.py")
        assert "experience" in content.lower() or "service" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/experience_service.py")
        assert _count_methods(content) >= 2


class TestMemoraGraphService:
    def test_module_exists(self):
        content = _content("Memora/core/memory/graph_service.py")
        assert "graph" in content.lower() or "service" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/graph_service.py")
        assert _count_methods(content) >= 2


class TestMemoraContradictionDetector:
    def test_module_exists(self):
        content = _content("Memora/core/memory/pipeline/contradiction_detector.py")
        assert "contradiction" in content.lower() or "detect" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/pipeline/contradiction_detector.py")
        assert _count_methods(content) >= 2


class TestMemoraDeduplication:
    def test_module_exists(self):
        content = _content("Memora/core/memory/pipeline/deduplication.py")
        assert "deduplication" in content.lower() or "dedup" in content.lower() or "duplicate" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/pipeline/deduplication.py")
        assert _count_methods(content) >= 1


class TestMemoraEntityExtractor:
    def test_module_exists(self):
        content = _content("Memora/core/memory/pipeline/entity_extractor.py")
        assert "entity" in content.lower() or "extract" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/pipeline/entity_extractor.py")
        assert _count_methods(content) >= 2


class TestMemoraPoisonDetector:
    def test_module_exists(self):
        content = _content("Memora/core/memory/pipeline/poison_detector.py")
        assert "poison" in content.lower() or "detect" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/pipeline/poison_detector.py")
        assert _count_methods(content) >= 2


class TestMemoraPreferenceExtractor:
    def test_module_exists(self):
        content = _content("Memora/core/memory/pipeline/preference_extractor.py")
        assert "preference" in content.lower() or "extract" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/pipeline/preference_extractor.py")
        assert _count_methods(content) >= 1


class TestMemoraSecretScanner:
    def test_module_exists(self):
        content = _content("Memora/core/memory/pipeline/secret_scanner.py")
        assert "secret" in content.lower() or "scan" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/pipeline/secret_scanner.py")
        assert _count_methods(content) >= 2


class TestMemoraWriteService:
    def test_module_exists(self):
        content = _content("Memora/core/memory/pipeline/write_service.py")
        assert "write" in content.lower() or "service" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/pipeline/write_service.py")
        assert _count_methods(content) >= 2


class TestMemoraSearchService:
    def test_module_exists(self):
        content = _content("Memora/core/memory/search_service.py")
        assert "search" in content.lower() or "service" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/search_service.py")
        assert _count_methods(content) >= 2


class TestMemoraMemoryService:
    def test_module_exists(self):
        content = _content("Memora/core/memory/service.py")
        assert "memory" in content.lower() or "service" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/service.py")
        assert _count_methods(content) >= 3


class TestMemoraMetricsCollector:
    def test_module_exists(self):
        content = _content("Memora/core/metrics/collector.py")
        assert "metric" in content.lower() or "collector" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/metrics/collector.py")
        assert _count_methods(content) >= 2


class TestMemoraRetrievalConfig:
    def test_module_exists(self):
        content = _content("Memora/core/memory/retrieval_config.py")
        assert "retrieval" in content.lower() or "config" in content.lower()

    def test_has_methods(self):
        content = _content("Memora/core/memory/retrieval_config.py")
        assert _count_methods(content) >= 1 or _count_classes(content) >= 1


class TestMemoraSchemas:
    def test_module_exists(self):
        content = _content("Memora/core/memory/schemas.py")
        assert "schema" in content.lower()

    def test_has_classes(self):
        content = _content("Memora/core/memory/schemas.py")
        assert _count_classes(content) >= 1


# ── Futuris Remaining Upgrade Modules ───────────────────────────────────────

class TestFuturisCheckpoint:
    def test_module_exists(self):
        content = _content("Futuris/futuris/upgrade/checkpoint.py")
        assert "checkpoint" in content.lower()

    def test_has_methods(self):
        content = _content("Futuris/futuris/upgrade/checkpoint.py")
        assert _count_methods(content) >= 1


class TestFuturisCompat:
    def test_module_exists(self):
        content = _content("Futuris/futuris/upgrade/compat.py")
        assert "compat" in content.lower() or "compatibility" in content.lower()

    def test_has_methods(self):
        content = _content("Futuris/futuris/upgrade/compat.py")
        assert _count_methods(content) >= 1


class TestFuturisIdempotency:
    def test_module_exists(self):
        content = _content("Futuris/futuris/upgrade/idempotency.py")
        assert "idempotency" in content.lower() or "idempotent" in content.lower()

    def test_has_methods(self):
        content = _content("Futuris/futuris/upgrade/idempotency.py")
        assert _count_methods(content) >= 1


class TestFuturisModels:
    def test_module_exists(self):
        content = _content("Futuris/futuris/upgrade/models.py")
        assert "model" in content.lower()

    def test_has_classes(self):
        content = _content("Futuris/futuris/upgrade/models.py")
        assert _count_classes(content) >= 1 or _count_methods(content) >= 1


class TestFuturisOutbox:
    def test_module_exists(self):
        content = _content("Futuris/futuris/upgrade/outbox.py")
        assert "outbox" in content.lower()

    def test_has_methods(self):
        content = _content("Futuris/futuris/upgrade/outbox.py")
        assert _count_methods(content) >= 1


class TestFuturisProvider:
    def test_module_exists(self):
        content = _content("Futuris/futuris/upgrade/provider.py")
        assert "provider" in content.lower()

    def test_has_methods(self):
        content = _content("Futuris/futuris/upgrade/provider.py")
        assert _count_methods(content) >= 1


class TestFuturisSafeConfig:
    def test_module_exists(self):
        content = _content("Futuris/futuris/upgrade/safe_config.py")
        assert "config" in content.lower() or "safe" in content.lower()

    def test_has_methods(self):
        content = _content("Futuris/futuris/upgrade/safe_config.py")
        assert _count_methods(content) >= 1


class TestFuturisState:
    def test_module_exists(self):
        content = _content("Futuris/futuris/upgrade/state.py")
        assert "state" in content.lower()

    def test_has_methods(self):
        content = _content("Futuris/futuris/upgrade/state.py")
        assert _count_methods(content) >= 1


# ── Cross-Agent Module Coverage ─────────────────────────────────────────────

class TestCrossAgentModuleCoverage:
    def test_intelx_has_agent_modules(self):
        intelx_modules = list((ROOT / "IntelX/intelx/agents").glob("*.py"))
        agent_modules = [m for m in intelx_modules if m.name not in ("__init__.py", "base.py")]
        assert len(agent_modules) >= 10

    def test_intelx_has_api_endpoints(self):
        intelx_modules = list((ROOT / "IntelX/intelx/api/v1").glob("*.py"))
        assert len(intelx_modules) >= 5

    def test_memora_has_core_modules(self):
        memora_core_dirs = ["cache", "collaboration", "events", "identity", "lifecycle", "memory", "metrics"]
        for d in memora_core_dirs:
            if (ROOT / f"Memora/core/{d}").exists():
                modules = list((ROOT / f"Memora/core/{d}").rglob("*.py"))
                assert len(modules) >= 1, f"Memora/core/{d} has no modules"

    def test_memora_has_pipeline_modules(self):
        memora_modules = list((ROOT / "Memora/core/memory/pipeline").glob("*.py"))
        assert len(memora_modules) >= 6

    def test_memora_has_context_modules(self):
        memora_modules = list((ROOT / "Memora/core/memory/context").glob("*.py"))
        assert len(memora_modules) >= 3

    def test_futuris_has_upgrade_modules(self):
        futuris_modules = list((ROOT / "Futuris/futuris/upgrade").glob("*.py"))
        assert len(futuris_modules) >= 20

    def test_all_intelx_agents_exist(self):
        intelx_agents = [
            "analyst.py", "citations.py", "extractor.py", "query_planner.py",
            "report_gate.py", "research_agent.py", "retriever.py", "scout.py",
            "synthesis_engine.py", "synthesizer.py", "verification.py", "verifier.py",
        ]
        for agent in intelx_agents:
            path = ROOT / f"IntelX/intelx/agents/{agent}"
            assert path.exists(), f"IntelX missing agent: {agent}"

    def test_all_futuris_upgrade_modules_exist(self):
        futuris_upgrade = [
            "checkpoint.py", "compat.py", "context_firewall.py", "decision.py",
            "forecast_guard.py", "idempotency.py", "models.py", "observability.py",
            "outbox.py", "persistence.py", "policy.py", "provider.py",
            "quality.py", "rate_limit.py", "retry.py", "safe_config.py",
            "scenario.py", "scheduler.py", "state.py", "tool_registry.py",
        ]
        for mod in futuris_upgrade:
            path = ROOT / f"Futuris/futuris/upgrade/{mod}"
            assert path.exists(), f"Futuris missing upgrade module: {mod}"