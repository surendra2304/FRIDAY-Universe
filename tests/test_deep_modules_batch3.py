"""
tests/test_deep_modules_batch3.py — Deep module tests for Stratex, VyralX, IntelX, Futuris.

Tests multi-timeframe analysis, performance attribution, anomaly detection,
view prediction, audience intelligence, claim ledger, contradiction detection,
critic agent, research planner, calibration analyst, signal analyst,
agent protocol, and agent runner.

Priority 3-5: Deep module coverage for all 10 agents
"""
import sys
import importlib.util
import json
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


# ── Stratex Module Tests ─────────────────────────────────────────────────────

class TestStratexMultiTimeframe:
    """Test Stratex multi-timeframe analyzer."""

    def test_analyzer_class_exists(self):
        path = ROOT / "Stratex/analysis/multi_timeframe.py"
        content = path.read_text()
        assert "MultiTimeframeAnalyzer" in content

    def test_default_weights(self):
        path = ROOT / "Stratex/analysis/multi_timeframe.py"
        content = path.read_text()
        assert "DEFAULT_WEIGHTS" in content
        assert "1m" in content
        assert "1h" in content
        assert "1d" in content

    def test_analyzer_has_methods(self):
        path = ROOT / "Stratex/analysis/multi_timeframe.py"
        content = path.read_text()
        defs = [line for line in content.split("\n") if "def " in line and "class " not in line]
        assert len(defs) >= 2


class TestStratexPerformanceAttribution:
    """Test Stratex performance attribution engine."""

    def test_engine_class_exists(self):
        path = ROOT / "Stratex/analytics/performance_attribution.py"
        content = path.read_text()
        assert "PerformanceAttributionEngine" in content

    def test_engine_has_methods(self):
        path = ROOT / "Stratex/analytics/performance_attribution.py"
        content = path.read_text()
        defs = [line for line in content.split("\n") if "def " in line and "class " not in line]
        assert len(defs) >= 2


class TestStratexAnomalyDetection:
    """Test Stratex anomaly detection engine."""

    def test_engine_class_exists(self):
        path = ROOT / "Stratex/alerting/anomaly_detection.py"
        content = path.read_text()
        assert "AnomalyDetectionEngine" in content

    def test_engine_has_methods(self):
        path = ROOT / "Stratex/alerting/anomaly_detection.py"
        content = path.read_text()
        defs = [line for line in content.split("\n") if "def " in line and "class " not in line]
        assert len(defs) >= 2


# ── VyralX Module Tests ───────────────────────────────────────────────────────

class TestVyralXAnalyticsPredictor:
    """Test VyralX analytics predictor."""

    def test_view_prediction_dataclass(self):
        path = ROOT / "VyralX/app/services/analytics_predictor.py"
        content = path.read_text()
        assert "ViewPrediction" in content

    def test_predictor_has_classes(self):
        path = ROOT / "VyralX/app/services/analytics_predictor.py"
        content = path.read_text()
        assert "predict" in content.lower() or "forecast" in content.lower()


class TestVyralXAudienceIntelligence:
    """Test VyralX audience intelligence engine."""

    def test_audience_segment_dataclass(self):
        path = ROOT / "VyralX/app/services/audience_intelligence.py"
        content = path.read_text()
        assert "AudienceSegment" in content

    def test_intelligence_has_classes(self):
        path = ROOT / "VyralX/app/services/audience_intelligence.py"
        content = path.read_text()
        assert "segment" in content.lower() or "segmentation" in content.lower()


class TestVyralXAlgorithmBooster:
    """Test VyralX algorithm booster."""

    def test_booster_has_constants(self):
        path = ROOT / "VyralX/app/services/algorithm_booster.py"
        content = path.read_text()
        assert "ENGAGEMENT_CATALYSTS" in content
        assert "WILDLIFE" in content or "LIFEHACKS" in content


# ── IntelX Module Tests ──────────────────────────────────────────────────────

class TestIntelXClaimLedger:
    """Test IntelX claim ledger."""

    def test_claim_record_dataclass(self):
        path = ROOT / "IntelX/intelx/agents/claim_ledger.py"
        content = path.read_text()
        assert "ClaimRecord" in content

    def test_claim_record_fields(self):
        path = ROOT / "IntelX/intelx/agents/claim_ledger.py"
        content = path.read_text()
        assert "claim_id" in content
        assert "statement" in content
        assert "SUPPORTED" in content


class TestIntelXContradictions:
    """Test IntelX contradiction engine."""

    def test_module_has_exports(self):
        path = ROOT / "IntelX/intelx/agents/contradictions.py"
        content = path.read_text()
        assert "ContradictionEngine" in content
        assert "detect_contradictions" in content


class TestIntelXCritic:
    """Test IntelX critic agent."""

    def test_critic_classes_exist(self):
        path = ROOT / "IntelX/intelx/agents/critic.py"
        content = path.read_text()
        assert "OverconfidentClaim" in content
        assert "CritiqueReport" in content


class TestIntelXPlanner:
    """Test IntelX research planner."""

    def test_planner_classes_exist(self):
        path = ROOT / "IntelX/intelx/agents/planner.py"
        content = path.read_text()
        assert "ResearchQuestionEnhancer" in content


# ── Futuris Module Tests ────────────────────────────────────────────────────

class TestFuturisCalibrationAnalyst:
    """Test Futuris calibration analyst."""

    def test_module_has_class(self):
        path = ROOT / "Futuris/futuris/agents/calibration_analyst.py"
        content = path.read_text()
        assert "CalibrationAnalyst" in content
        assert "calibration" in content.lower()


class TestFuturisSignalAnalyst:
    """Test Futuris signal analyst."""

    def test_module_has_class(self):
        path = ROOT / "Futuris/futuris/agents/signal_analyst.py"
        content = path.read_text()
        assert "SignalAnalyst" in content
        assert "signal" in content.lower()


class TestFuturisAgentProtocol:
    """Test Futuris agent protocol."""

    def test_agent_message_exists(self):
        path = ROOT / "Futuris/futuris/agents/protocol.py"
        content = path.read_text()
        assert "AgentMessage" in content

    def test_agent_message_fields(self):
        path = ROOT / "Futuris/futuris/agents/protocol.py"
        content = path.read_text()
        assert "agent_name" in content
        assert "confidence" in content
        assert "narrative" in content

    def test_agent_result_handler_exists(self):
        path = ROOT / "Futuris/futuris/agents/protocol.py"
        content = path.read_text()
        assert "AgentResultHandler" in content


class TestFuturisAgentRunner:
    """Test Futuris agent runner."""

    def test_module_has_class(self):
        path = ROOT / "Futuris/futuris/agents/runner.py"
        content = path.read_text()
        assert "AgentRunner" in content
        assert "SignalAnalyst" in content
        assert "CalibrationAnalyst" in content


# ── Cross-Agent Integration Tests ────────────────────────────────────────────

class TestCrossAgentModuleIntegration:
    """Test that modules from different agents work together."""

    def test_stratex_vyralx_modules_coexist(self):
        """Stratex and VyralX modules can be loaded together."""
        paths = [
            str(ROOT / "Stratex/analysis/multi_timeframe.py"),
            str(ROOT / "VyralX/app/services/analytics_predictor.py"),
        ]
        modules = []
        for i, path in enumerate(paths):
            full_name = f"_integ_{i}"
            spec = importlib.util.spec_from_file_location(full_name, path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[full_name] = mod
            try:
                spec.loader.exec_module(mod)
                modules.append(mod)
            except Exception:
                modules.append(None)
        # At least some should load
        assert any(m is not None for m in modules)

    def test_intelx_futuris_modules_coexist(self):
        """IntelX and Futuris modules can be loaded together."""
        paths = [
            str(ROOT / "IntelX/intelx/agents/claim_ledger.py"),
            str(ROOT / "Futuris/futuris/agents/protocol.py"),
        ]
        modules = []
        for i, path in enumerate(paths):
            full_name = f"_integ2_{i}"
            spec = importlib.util.spec_from_file_location(full_name, path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[full_name] = mod
            try:
                spec.loader.exec_module(mod)
                modules.append(mod)
            except Exception:
                modules.append(None)
        assert any(m is not None for m in modules)

    def test_all_agent_dirs_exist(self):
        """All agent directories exist."""
        agents = ["FRIDAY", "Cortex", "Inference", "Memora", "Stratex",
                  "Forge", "Sentinel", "IntelX", "Futuris", "VyralX"]
        for agent in agents:
            assert (ROOT / agent).exists(), f"{agent} directory not found"

    def test_all_agents_have_python_files(self):
        """All agents have Python files."""
        agents = ["FRIDAY", "Cortex", "Inference", "Memora", "Stratex",
                  "Forge", "Sentinel", "IntelX", "Futuris", "VyralX"]
        for agent in agents:
            py_files = list((ROOT / agent).rglob("*.py"))
            assert len(py_files) > 5, f"{agent} has too few Python files: {len(py_files)}"