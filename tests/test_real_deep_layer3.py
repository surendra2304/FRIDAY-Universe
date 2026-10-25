"""
tests/test_real_deep_layer3.py — Functional tests for Layer 3 deep engines.

Tests real working implementations:
- Inference: MetaCognitiveEngine, AbductiveReasoningEngine, TemporalReasoningEngine,
  CounterfactualReasoner, AnalogicalTransferEngine
- Memora: EpisodicMemoryEngine, SemanticMemoryEngine, ProceduralMemoryEngine,
  WorkingMemoryEngine, MemoryReconsolidationEngine, CrossModalAssociator
- Distributed Tracing: TraceContext, Span, TraceExporter, TraceAnalyzer
"""
import sys
import pytest
import os
import tempfile
import shutil
import importlib.util
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module(relpath, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


inference_deep = load_module("Inference/app/agents/real_deep_reasoning.py", "deep_inference")
memora_deep = load_module("Memora/core/memory/real_deep_memory.py", "deep_memora")
tracing = load_module("FRIDAY/apps/core/src/friday_core/real_distributed_tracing.py", "tracing")


@pytest.fixture
def temp_state():
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


# ── Inference Deep Engines ────────────────────────────────────────────────

class TestMetaCognitiveEngine:
    def test_reasoning_trace(self):
        engine = inference_deep.MetaCognitiveEngine()
        trace = engine.reason("Why did the market crash?", {"context": "economic"})
        assert trace.confidence > 0
        assert len(trace.steps) >= 4
        assert trace.total_time_ms >= 0

    def test_causal_reasoning(self):
        engine = inference_deep.MetaCognitiveEngine()
        trace = engine.reason("Why is the sky blue?", {})
        assert any("causal" in str(s.get("detail", "")).lower() for s in trace.steps)

    def test_alternative_generation(self):
        engine = inference_deep.MetaCognitiveEngine()
        # Multiple reasoning calls to build pattern history
        for i in range(5):
            trace = engine.reason(f"Test question {i}", {})
        assert trace.confidence > 0


class TestAbductiveReasoningEngine:
    def test_best_explanation(self):
        engine = inference_deep.AbductiveReasoningEngine()
        hypotheses = [
            {"description": "Server crashed", "evidence_supporting": ["timeout", "500 error"],
             "evidence_contradicting": []},
            {"description": "Database overload", "evidence_supporting": ["high CPU", "slow queries"],
             "evidence_contradicting": []},
        ]
        best = engine.infer_best_explanation("Service is down", hypotheses)
        assert best.likelihood > 0
        assert len(best.evidence_supporting) >= 2


class TestTemporalReasoningEngine:
    def test_causal_chain(self):
        engine = inference_deep.TemporalReasoningEngine()
        t1 = engine.add_event("Server started", time.time(), effects=["Service running"])
        t2 = engine.add_event("Service running", time.time() + 10, causes=["Server started"])

        trace = engine.trace_causality(t2.event_id)
        assert len(trace) >= 1

    def test_predict_future(self):
        engine = inference_deep.TemporalReasoningEngine()
        event = engine.add_event("Deploy complete", time.time(), effects=["Traffic increase", "Monitoring"])
        predictions = engine.predict_future(event.event_id)
        assert len(predictions) >= 1


class TestCounterfactualReasoner:
    def test_counterfactual_generation(self):
        engine = inference_deep.CounterfactualReasoner()
        result = engine.generate_counterfactuals(
            "System is operational",
            ["Change the database", "Remove the cache", "Add more servers"]
        )
        assert len(result) == 3
        assert all(0 <= cf.probability <= 1 for cf in result)


class TestAnalogicalTransferEngine:
    def test_find_analogy(self):
        engine = inference_deep.AnalogicalTransferEngine()
        analogy = engine.find_analogy("cell biology", "computer architecture")
        assert analogy.source_domain == "cell biology"
        assert analogy.target_domain == "computer architecture"
        assert len(analogy.mapping) >= 3
        assert analogy.confidence > 0

    def test_transfer_knowledge(self):
        engine = inference_deep.AnalogicalTransferEngine()
        analogy = engine.find_analogy("business", "ecology")
        transferred = engine.transfer_knowledge(analogy, "source_components interact")
        assert "Transferred" in transferred or "source_components" in transferred


# ── Memora Deep Engines ───────────────────────────────────────────────────

class TestEpisodicMemoryEngine:
    @pytest.fixture
    def engine(self, temp_state):
        return memora_deep.EpisodicMemoryEngine(state_dir=os.path.join(temp_state, "epi"))

    def test_store_episode(self, engine):
        episode = engine.store_episode(
            "Met with the team about the project",
            episode_type="experience",
            location="office",
            emotional_valence=0.8,
            tags=["meeting", "project"],
            importance=0.7,
        )
        assert episode.episode_type == "experience"
        assert episode.location == "office"

    def test_recall_episodes(self, engine):
        engine.store_episode("Had a productive meeting about Q4 planning", tags=["meeting", "planning"])
        engine.store_episode("Reviewed the latest code changes", tags=["code", "review"])

        results = engine.recall_episodes("meeting planning")
        assert len(results) >= 1

    def test_get_timeline(self, engine):
        engine.store_episode("Event 1", tags=["test"])
        engine.store_episode("Event 2", tags=["test"])
        timeline = engine.get_timeline(days=7)
        assert len(timeline) == 2

    def test_emotional_filter(self, engine):
        engine.store_episode("Great day", emotional_valence=0.9, tags=["positive"])
        engine.store_episode("Bad day", emotional_valence=-0.9, tags=["negative"])

        positive = engine.recall_episodes("day", emotional_filter=0.8)
        assert len(positive) >= 1


class TestSemanticMemoryEngine:
    @pytest.fixture
    def engine(self, temp_state):
        return memora_deep.SemanticMemoryEngine(state_dir=os.path.join(temp_state, "sem"))

    def test_add_concept(self, engine):
        node = engine.add_concept(
            "Database", "A structured collection of data",
            properties={"type": "storage", "access": "SQL"},
            category="technology"
        )
        assert node.concept == "Database"
        assert node.category == "technology"

    def test_add_relation(self, engine):
        node1 = engine.add_concept("Database", "Storage")
        node2 = engine.add_concept("SQLite", "Lightweight DB")
        engine.add_relation(node1.node_id, node2.node_id, "has_instance")

    def test_query_concept(self, engine):
        node1 = engine.add_concept("Database", "Storage")
        node2 = engine.add_concept("SQLite", "Lightweight DB")
        engine.add_relation(node1.node_id, node2.node_id, "has_instance")

        result = engine.query_concept("Database")
        assert result["concept"] == "Database"
        assert len(result["related_concepts"]) >= 1


class TestProceduralMemoryEngine:
    @pytest.fixture
    def engine(self, temp_state):
        return memora_deep.ProceduralMemoryEngine(state_dir=os.path.join(temp_state, "proc"))

    def test_store_procedure(self, engine):
        proc = engine.store_procedure(
            "deploy_app", "Deploy application to server",
            steps=["git pull", "pip install", "uvicorn start"],
            parameters={"server": "localhost", "port": "8000"}
        )
        assert proc.name == "deploy_app"
        assert len(proc.steps) == 3

    def test_execute_procedure(self, engine):
        proc = engine.store_procedure(
            "deploy_app", "Deploy",
            steps=["git pull", "pip install", "uvicorn start --port {port}"],
            parameters={"port": "8000"}
        )
        result = engine.execute_procedure(proc.procedure_id, {"port": "8000"})
        assert result["success"] is True
        assert len(result["steps"]) == 3
        assert "8000" in result["steps"][-1]

    def test_success_rate(self, engine):
        proc = engine.store_procedure("test_proc", "Test", ["step1"])
        engine.execute_procedure(proc.procedure_id, {})
        engine.execute_procedure(proc.procedure_id, {})
        result = engine.execute_procedure(proc.procedure_id, {})
        assert result["success_rate"] > 0


class TestWorkingMemoryEngine:
    def test_hold_and_recall(self):
        engine = memora_deep.WorkingMemoryEngine(capacity=5)
        item = engine.hold("Important thought", category="conceptual")
        results = engine.recall("Important")
        assert len(results) >= 1
        assert results[0].rehearsal_count == 1

    def test_capacity_limit(self):
        engine = memora_deep.WorkingMemoryEngine(capacity=3)
        for i in range(5):
            engine.hold(f"Item {i}")
        assert len(engine.get_all()) <= 3

    def test_strength_increases(self):
        engine = memora_deep.WorkingMemoryEngine()
        item = engine.hold("Test item")
        engine.recall("Test")
        engine.recall("Test")
        assert item.strength > 0.5

    def test_forget_weakest(self):
        engine = memora_deep.WorkingMemoryEngine(capacity=5)
        engine.hold("Strong", category="conceptual")
        engine.hold("Weak", category="conceptual")
        engine.recall("Strong")
        engine.recall("Strong")

        assert engine.forget_weakest() is True
        remaining = engine.get_all()
        assert all("Strong" not in item.content or item.strength > 0.5 for item in remaining)


class TestMemoryReconsolidationEngine:
    def test_reconsolidate(self):
        engine = memora_deep.MemoryReconsolidationEngine()
        result = engine.reconsolidate("mem_1", 0.5, "new information")
        assert result.new_strength > result.original_strength
        assert result.updates_applied == 1

    def test_reconsolidate_no_new_info(self):
        engine = memora_deep.MemoryReconsolidationEngine()
        result = engine.reconsolidate("mem_2", 0.8)
        assert result.updates_applied == 0
        assert result.new_strength >= result.original_strength


class TestCrossModalAssociator:
    def test_associate(self):
        engine = memora_deep.CrossModalAssociator()
        link = engine.associate("text", "image", "mem_1", "img_1", strength=0.7)
        assert link.source_modality == "text"
        assert link.target_modality == "image"
        assert link.association_strength == 0.7

    def test_retrieve_multimodal(self):
        engine = memora_deep.CrossModalAssociator()
        engine.associate("text", "image", "mem_1", "img_1")
        engine.associate("audio", "text", "audio_1", "mem_1")

        links = engine.retrieve_multimodal("mem_1")
        assert len(links) == 2


# ── Distributed Tracing ───────────────────────────────────────────────────

class TestDistributedTracing:
    @pytest.fixture
    def engine(self, temp_state):
        exporter = tracing.TraceExporter(state_dir=os.path.join(temp_state, "tracing"))
        return tracing.AgentTracingMiddleware(exporter)

    def test_create_trace(self, engine):
        context, span = engine.create_trace("Cortex")
        assert context.trace_id.startswith("trace_")
        assert span.span_id.startswith("span_")
        assert span.agent_name == "Cortex"

    def test_child_span(self, engine):
        parent_ctx, parent_span = engine.create_trace("FRIDAY")
        child_ctx, child_span = engine.start_child_span(parent_ctx, "Cortex", "decision")

        assert child_span.parent_span_id == parent_ctx.span_id
        assert child_span.trace_id == parent_ctx.trace_id

    def test_finish_span(self, engine):
        context, span = engine.create_trace("Sentinel")
        span.set_attribute("endpoint", "/api/security/scan")
        engine.finish_span(span)
        assert span.status == "ok"
        assert span.duration_ms > 0

    def test_analyze_trace(self, engine):
        context, span1 = engine.create_trace("FRIDAY")
        child_ctx, span2 = engine.start_child_span(context, "Cortex", "decision")
        engine.finish_span(span1)
        engine.finish_span(span2)

        metrics = engine.analyze(context.trace_id)
        assert metrics.total_spans == 2
        assert metrics.error_count == 0
        assert "FRIDAY" in metrics.agent_breakdown
        assert "Cortex" in metrics.agent_breakdown

    def test_error_span(self, engine):
        context, span = engine.create_trace("IntelX")
        span.add_event("error", {"message": "Connection failed"})
        engine.finish_span(span, status="error")

        metrics = engine.analyze(context.trace_id)
        assert metrics.error_count == 1

    def test_trace_context_propagation(self):
        ctx = tracing.TraceContext(trace_id="trace_test", span_id="span_root", agent_name="FRIDAY")
        child = ctx.new_span("Cortex")
        grandchild = child.new_span("Sentinel")

        assert child.trace_id == ctx.trace_id
        assert grandchild.trace_id == ctx.trace_id
        assert grandchild.parent_span_id == child.span_id

    def test_find_bottlenecks(self, engine):
        for i in range(5):
            context, span = engine.create_trace("TestAgent")
            span.set_attribute("operation", f"slow_op_{i}")
            # Simulate slow operation
            time.sleep(0.01)
            engine.finish_span(span)

        analyzer = tracing.TraceAnalyzer()
        bottlenecks = analyzer.find_bottlenecks(engine._exporter)
        assert len(bottlenecks) >= 1
        assert bottlenecks[0]["duration_ms"] > 0
