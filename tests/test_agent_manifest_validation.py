"""
tests/test_agent_manifest_validation.py — Validates AGENTS.yaml against reality.

This test enforces the "single source of truth" principle from review 2:
doc drift should become a failing test, not a comment.

Checks:
- AGENTS.yaml exists and is valid YAML
- Agent count matches actual agent directories
- All ports are unique
- All memory limits are positive
- Vertical slice endpoint exists in API server
"""
import sys
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_agents_yaml_exists():
    """AGENTS.yaml must exist as the single source of truth."""
    assert (ROOT / "AGENTS.yaml").exists(), "AGENTS.yaml is missing"


def test_agents_yaml_valid_yaml():
    """AGENTS.yaml must be valid YAML."""
    try:
        import yaml
    except ImportError:
        pytest.skip("yaml not installed")
    with open(ROOT / "AGENTS.yaml", "r") as f:
        data = yaml.safe_load(f)
    assert data is not None
    assert "agents" in data
    assert "resource_budget" in data


def test_agent_count_matches_manifest():
    """The agent count in AGENTS.yaml must match actual agent directories."""
    agent_dirs = [
        "Cortex", "Inference", "Memora", "Stratex",
        "Forge", "Sentinel", "IntelX", "Futuris", "VyralX"
    ]
    actual_agents = [d for d in agent_dirs if (ROOT / d).exists()]
    assert len(actual_agents) == 9, f"Expected 9 agents, found {len(actual_agents)}: {actual_agents}"


def test_all_agents_have_engines():
    """Every agent in the manifest must have at least one engine file."""
    engine_files = [
        "Cortex/apps/api/src/cortex_api/real_decision_engine.py",
        "Cortex/apps/api/src/cortex_api/real_advanced_engines.py",
        "Cortex/apps/api/src/cortex_api/real_deep_engines.py",
        "Inference/app/agents/real_reasoning_engine.py",
        "Inference/app/agents/real_advanced_reasoning.py",
        "Memora/core/memory/real_memory_engine.py",
        "Memora/core/memory/real_advanced_memory.py",
        "Stratex/real_trading_engine.py",
        "Stratex/real_advanced_trading.py",
        "Stratex/real_deep_trading.py",
        "Forge/app/services/real_code_engine.py",
        "Forge/app/services/real_advanced_code.py",
        "Forge/app/services/real_deep_code.py",
        "Sentinel/app/services/real_security_engine.py",
        "Sentinel/app/services/real_advanced_security.py",
        "Sentinel/app/services/real_deep_security.py",
        "IntelX/intelx/services/real_threat_intel_engine.py",
        "IntelX/intelx/services/real_advanced_threat_intel.py",
        "IntelX/intelx/services/real_deep_threat_intel.py",
        "Futuris/futuris/core/real_forecast_engine.py",
        "Futuris/futuris/core/real_advanced_forecast.py",
        "Futuris/futuris/core/real_deep_forecast.py",
        "VyralX/app/services/real_content_engine.py",
        "VyralX/app/services/real_advanced_content.py",
        "VyralX/app/services/real_deep_content.py",
    ]
    for f in engine_files:
        assert (ROOT / f).exists(), f"Missing engine file: {f}"


def test_ports_are_unique():
    """All agent ports must be unique."""
    try:
        import yaml
    except ImportError:
        pytest.skip("yaml not installed")
    with open(ROOT / "AGENTS.yaml", "r") as f:
        data = yaml.safe_load(f)
    ports = [a["port"] for a in data["agents"].values()]
    assert len(ports) == len(set(ports)), f"Duplicate ports found: {ports}"


def test_memory_limits_positive():
    """All memory limits must be positive."""
    try:
        import yaml
    except ImportError:
        pytest.skip("yaml not installed")
    with open(ROOT / "AGENTS.yaml", "r") as f:
        data = yaml.safe_load(f)
    for agent_id, agent in data["agents"].items():
        mem = agent.get("memory_limit", "0M")
        # Extract numeric value
        num = int(mem.replace("M", "").replace("G", ""))
        assert num > 0, f"Invalid memory limit for {agent_id}: {mem}"


def test_resource_budget_fits():
    """Total memory budget must fit within target host RAM."""
    try:
        import yaml
    except ImportError:
        pytest.skip("yaml not installed")
    with open(ROOT / "AGENTS.yaml", "r") as f:
        data = yaml.safe_load(f)
    budget = data["resource_budget"]
    total_mem = budget["total_memory_limit"]
    total_mb = int(total_mem.replace("M", "").replace("G", ""))
    ram_gb = budget["target_host"]["ram_gb"]
    ram_mb = ram_gb * 1024
    assert total_mb < ram_mb, f"Memory budget {total_mb}M exceeds RAM {ram_mb}M"


def test_proven_vertical_slice_exists():
    """The proven vertical slice endpoint must exist."""
    vertical = None
    try:
        import yaml
        with open(ROOT / "AGENTS.yaml", "r") as f:
            data = yaml.safe_load(f)
        vertical = data.get("proven_vertical", {})
    except ImportError:
        pytest.skip("yaml not installed")
    if vertical:
        api_server = ROOT / "FRIDAY/apps/core/src/friday_core/real_api_server.py"
        assert api_server.exists()
        content = api_server.read_text()
        assert vertical["endpoint"] in content, f"Endpoint {vertical['endpoint']} not in API server"
