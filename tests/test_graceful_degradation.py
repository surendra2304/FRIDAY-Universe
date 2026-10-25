from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent


def _clean_app(agent_subpath: str):
    to_remove = [k for k in list(sys.modules.keys()) if k == "app" or k.startswith("app.")]
    for k in to_remove:
        sys.modules.pop(k, None)
    agent_path = str(ROOT / agent_subpath)
    if agent_path in sys.path:
        sys.path.remove(agent_path)
    sys.path.insert(0, agent_path)


def test_inference_graceful_degradation_on_unsupported_evidence():
    _clean_app("Inference")
    from app.scientific_service import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # Auditing claims with missing citations must return 200 with verdict "warn", not 500
    res = client.post("/v1/scientific/audit", json={
        "claims": [{"text": "Synthetic claim with no real citation", "evidence": ["non_existent_ref"]}],
        "evidence": [],
    })
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] in ("warn", "fail")
    assert "warnings" in data
    assert len(data["warnings"]) >= 1


def test_vyralx_graceful_degradation_on_attach_explainer():
    _clean_app("VyralX")
    from app.services.diagram_service import attach_explainer

    class FailingStudio:
        def flowchart(self, *args, **kwargs):
            raise RuntimeError("Renderer engine simulated failure")

    pack = {"topic": "Chaos test", "scene_plan": []}
    result = attach_explainer(pack, "Chaos test", service=FailingStudio())
    # Must return 200-style payload with error captured, never raise
    assert "explainer_diagram" in result
    assert "error" in result["explainer_diagram"]
    assert "RuntimeError" in result["explainer_diagram"]["error"]


def test_sentinel_graceful_degradation_on_unauthorized_destructive_action():
    _clean_app("Sentinel")
    from app.services.cyber_skills_service import CyberSkillsService

    service = CyberSkillsService()
    # Unapproved destructive action must fail closed with blocked_pending_approval, never 500 / crash
    res = service.execute_playbook_action("wipe_host", target="critical-db-01", approved=False)
    assert res["status"] == "blocked_pending_approval"
    assert "authorization" in res["reason"].lower() or "requires" in res["reason"].lower()


def test_memora_graceful_degradation_on_missing_context():
    _clean_app("Memora")
    from core.memory.context_service import MemoraContextService

    service = MemoraContextService()
    # Recalling non-existent key must return empty or fallback gracefully, never raise
    level, hits = service.recall_layered("completely_unknown_token_12345")
    assert isinstance(level, str)
    assert hits == []


def test_friday_harness_graceful_degradation_on_denied_permission():
    from friday_core.agent_runtime import FridayAgentRuntime

    runtime = FridayAgentRuntime()
    # Step requesting unpermitted tool must be gated and observed as denied, not raise uncaught exception
    res = runtime.execute("unsafe task", [{"tool": "unauthorized_cmd", "params": {}}])
    assert res.denied >= 1
    assert any("denied" in obs.lower() for obs in res.observations)


def test_friday_harness_budget_enforcement():
    from friday_core.real_harness_engineering import AgentLoop, LoopAction

    # 1. max_steps enforcement
    loop_steps = AgentLoop(max_steps=2, budget=1000)
    res_steps = loop_steps.run(
        "test task",
        lambda task, steps: LoopAction(kind="tool", tool="count_tokens", arguments={"text": f"hi {len(steps)}"}),
    )
    assert res_steps.stop_reason == "max_steps"
    assert len(res_steps.steps) == 2

    # 2. budget exhaustion enforcement
    loop_budget = AgentLoop(max_steps=10, budget=10)
    res_budget = loop_budget.run(
        "A prompt that exceeds the budget limit of ten tokens right away",
        lambda task, steps: LoopAction(kind="tool", tool="count_tokens", arguments={"text": "hi"}),
    )
    assert res_budget.stop_reason == "budget_exhausted"
