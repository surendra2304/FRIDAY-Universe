"""
Unit tests for Continuous Template Evolution Engine.
"""

from app.improvement.template_evolution import TemplateEvolutionEngine


def test_template_evolution_scoring_and_promotion():
    engine = TemplateEvolutionEngine()

    engine.register_variant("fastapi_v1", "api", "from fastapi import FastAPI\napp = FastAPI()")
    engine.register_variant(
        "fastapi_v2", "api", "from fastapi import FastAPI, APIRouter\napp = FastAPI()"
    )

    # Record 4 successes for v2, 1 failure
    for _ in range(4):
        engine.record_outcome("fastapi_v2", passed_verification=True)
    engine.record_outcome("fastapi_v2", passed_verification=False)

    # Record 1 success for v1, 3 failures
    engine.record_outcome("fastapi_v1", passed_verification=True)
    for _ in range(3):
        engine.record_outcome("fastapi_v1", passed_verification=False)

    winner = engine.get_winning_variant("api")
    assert winner is not None
    assert winner.name == "fastapi_v2"
    assert winner.success_rate == 80.0


def test_template_ab_evaluation():
    engine = TemplateEvolutionEngine()
    engine.record_outcome("css_flexbox_base", passed_verification=True)
    engine.record_outcome("css_grid_base", passed_verification=False)

    ab_res = engine.evaluate_ab_variants("css_flexbox_base", "css_grid_base")
    assert ab_res["promoted_winner"] == "css_flexbox_base"
