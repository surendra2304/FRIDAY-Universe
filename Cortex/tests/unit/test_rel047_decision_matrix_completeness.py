"""TASK-REL-047: an incomplete decision matrix is rejected with HTTP 422.

Before this change, ``DecisionRecommendationSystem.recommend`` silently
filled every unscored alternative-by-criterion cell with 0.5. TASK-COR-002's
controlled live probe supplied 1 of 4 cells in a 2x2 matrix and received a
confident recommendation (confidence 0.5833) in which 75% of the inputs
were that invented default, with no hint in the output. TASK-REL-045's
tuning table decided: no silent default — reject the incomplete matrix.

These tests pin both halves of the contract: the rejection (engine level
and over the real HTTP routes, as a clean 422 rather than a crash) and the
complete-matrix path, which must keep producing recommendations exactly as
before.
"""

from __future__ import annotations

import pytest
from cortex_api.decision_recommendation_system import (
    DecisionRecommendationSystem,
    router as decision_router,
)
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


def _system_with_matrix(supplied: dict[tuple[str, str], float]):
    """A 2-criterion x 2-alternative system; ``supplied`` maps
    (alternative_name, criterion_name) -> score for the cells to fill."""
    system = DecisionRecommendationSystem()
    crit_a = system.add_criterion("cost", weight=1.0, direction="minimize")
    crit_b = system.add_criterion("quality", weight=2.0, direction="maximize")
    alt_x = system.add_alternative("option-x")
    alt_y = system.add_alternative("option-y")
    crits = {"cost": crit_a, "quality": crit_b}
    alts = {"option-x": alt_x, "option-y": alt_y}
    for (alt_name, crit_name), score in supplied.items():
        system.score_alternative(
            alts[alt_name].alternative_id, crits[crit_name].criterion_id, score
        )
    return system


def test_cor002_probe_shape_is_rejected_422():
    """The exact TASK-COR-002 probe: 1 of 4 cells supplied."""
    system = _system_with_matrix({("option-x", "cost"): 0.9})

    with pytest.raises(HTTPException) as excinfo:
        system.recommend("which option?")

    assert excinfo.value.status_code == 422
    detail = excinfo.value.detail
    # Every missing cell is named; the one supplied cell is not.
    assert "option-x / quality" in detail
    assert "option-y / cost" in detail
    assert "option-y / quality" in detail
    assert "option-x / cost" not in detail


def test_empty_matrix_cells_are_rejected_not_defaulted():
    system = _system_with_matrix({})

    with pytest.raises(HTTPException) as excinfo:
        system.recommend("which option?")

    assert excinfo.value.status_code == 422
    assert "Incomplete decision matrix" in excinfo.value.detail


def test_complete_matrix_still_recommends():
    system = _system_with_matrix(
        {
            ("option-x", "cost"): 0.2,  # minimize: low cost is good
            ("option-x", "quality"): 0.9,
            ("option-y", "cost"): 0.8,
            ("option-y", "quality"): 0.4,
        }
    )

    rec = system.recommend("which option?")

    # Weighted: x = ((1-0.2)*1 + 0.9*2) / 3 = 0.8667; y = ((1-0.8)*1 + 0.4*2) / 3 = 0.3333
    assert rec.best_alternative == "option-x"
    assert rec.alternatives_ranking[0]["score"] == pytest.approx(0.8667, abs=1e-3)
    assert 0.0 < rec.confidence <= 1.0


def test_http_surface_returns_422_then_200_when_completed():
    """Drive the real routes: existing callers get a clean 422 for an
    incomplete matrix (never a 500/crash), and 200 once it is complete."""
    app = FastAPI()
    app.include_router(decision_router)
    client = TestClient(app, raise_server_exceptions=False)

    crit_a = client.post(
        "/api/v1/cortex/decision/criteria", json={"name": "rel047-cost", "weight": 1.0}
    ).json()["criterion_id"]
    crit_b = client.post(
        "/api/v1/cortex/decision/criteria", json={"name": "rel047-quality", "weight": 1.0}
    ).json()["criterion_id"]
    alt = client.post(
        "/api/v1/cortex/decision/alternatives", json={"name": "rel047-only-option"}
    ).json()["alternative_id"]

    # Score only one of the two cells -> recommend must 422.
    r = client.post(
        f"/api/v1/cortex/decision/alternatives/{alt}/score",
        json={"criterion_id": crit_a, "score": 0.5},
    )
    assert r.status_code == 200
    r = client.post(
        "/api/v1/cortex/decision/recommend",
        json={"problem_statement": "rel047 http surface"},
    )
    assert r.status_code == 422
    assert "Incomplete decision matrix" in r.json()["detail"]

    # Complete the matrix -> the same call succeeds.
    r = client.post(
        f"/api/v1/cortex/decision/alternatives/{alt}/score",
        json={"criterion_id": crit_b, "score": 0.7},
    )
    assert r.status_code == 200
    r = client.post(
        "/api/v1/cortex/decision/recommend",
        json={"problem_statement": "rel047 http surface"},
    )
    assert r.status_code == 200
    assert r.json()["best_alternative"] == "rel047-only-option"
