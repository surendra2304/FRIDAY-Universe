from __future__ import annotations

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent


def _ensure_inference_app():
    to_remove = [k for k in list(sys.modules.keys()) if k == "app" or k.startswith("app.")]
    for k in to_remove:
        sys.modules.pop(k, None)
    inf_path = str(ROOT / "Inference")
    if inf_path in sys.path:
        sys.path.remove(inf_path)
    sys.path.insert(0, inf_path)


def test_task_router_consults_skill_matcher():
    _ensure_inference_app()
    from app.agents.router import TaskRouter

    router = TaskRouter()
    # Scientific task that should match scientific skills
    decision = router.route_task("Design a randomized controlled clinical trial with statistical power and biomarker endpoints")
    assert "scientific_analyst" in decision.selected_agent_ids
    assert decision.mode in ("fast", "review", "debate")


def test_evidence_discipline_and_soft_failure():
    _ensure_inference_app()
    from app.scientific_service import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # Claim without evidence should warn, not 500
    resp = client.post("/v1/scientific/audit", json={
        "claims": [{"text": "Drug X reduces mortality by 50%", "evidence": ["missing_e1"]}],
        "evidence": [{"id": "e2", "title": "Other trial", "source": "PubMed"}],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] in ("warn", "fail")
    assert "warnings" in data
    assert len(data["warnings"]) >= 1


def test_power_calculation_with_sample_size():
    _ensure_inference_app()
    from app.scientific_service import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # Power with explicit sample size
    resp = client.post("/v1/scientific/power", json={
        "effect_size": 0.5,
        "alpha": 0.05,
        "power": 0.8,
        "sample_size": 100,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["actual_sample_size"] == 100
    assert "achieved_power" in data
    assert 0.0 < data["achieved_power"] < 1.0


def test_orchestrator_research_step_feeds_content_workflow():
    from friday_core.universe_orchestrator import FullUniverseOrchestrator
    import tempfile

    orch = FullUniverseOrchestrator(state_dir=tempfile.mkdtemp())
    result = orch.run_deep_content(
        "CRISPR gene editing mechanisms",
        "An in-depth explainer on guide RNAs and Cas9 specificity.",
        [{"id": "u1", "watch_time": 120}],
    )
    actions = [s.action for s in result.steps]
    assert "research_planning" in actions
    research_step = next(s for s in result.steps if s.action == "research_planning")
    assert research_step.agent == "Inference"
    assert "skills" in research_step.result
    assert "effect_size" in research_step.result
