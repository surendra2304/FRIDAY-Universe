"""
Integration Test: Futuris Prediction-Informed Builds & Capacity-Aware Queueing Flow.
"""

import tempfile
from pathlib import Path

import pytest

from app.integrations.futuris_client import (
    get_futuris_client,
)
from app.monitoring.production_monitor import production_monitor


@pytest.fixture
def mock_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        (ws / "main.py").write_text("print('Prediction informed build')\n", encoding="utf-8")
        yield ws


@pytest.mark.asyncio
async def test_futuris_prediction_informed_build_flow(mock_workspace: Path):
    """
    Test End-to-End Futuris Integration:
    1. Pre-build assessment with success predictions across candidates.
    2. Capacity check for concurrency load management.
    3. Outcome reporting for calibration.
    """
    goal = "Create a high-concurrency event stream processor using WebSockets and Redis"
    candidates = ["in_memory_crud", "modular_service", "minimal_script"]

    futuris = get_futuris_client()

    # 1. Execute full assessment
    assessment = futuris.get_full_assessment(
        goal=goal,
        current_active_tasks=3,
        max_capacity=10,
        template_candidates=candidates,
    )

    production_monitor.record_futuris_consultation()
    production_monitor.record_prediction_informed_selection()

    assert assessment.prediction_id.startswith("fut_")
    assert assessment.best_template.template_name == "modular_service"
    assert assessment.best_template.predicted_pass_probability >= 0.85
    assert assessment.duration_forecast.estimated_duration_seconds > 0
    assert assessment.capacity_check.should_queue is False

    # 2. Test high-load capacity-aware queueing condition
    high_load_assessment = futuris.get_full_assessment(
        goal=goal,
        current_active_tasks=12,
        max_capacity=10,
        template_candidates=candidates,
    )
    if high_load_assessment.capacity_check.should_queue:
        production_monitor.record_capacity_queue_decision()

    assert high_load_assessment.capacity_check.should_queue is True
    assert high_load_assessment.capacity_check.estimated_wait_seconds > 0
    assert high_load_assessment.capacity_check.scheduling_tier in ["queued_fast", "queued_standard"]

    # 3. Report completed build outcome for model calibration
    outcome_record = futuris.report_build_outcome(
        prediction_id=assessment.prediction_id,
        goal=goal,
        template_used=assessment.best_template.template_name,
        actual_duration_seconds=14.2,
        passed=True,
    )

    assert outcome_record["prediction_id"] == assessment.prediction_id
    assert outcome_record["passed"] is True
    assert outcome_record["actual_duration_seconds"] == 14.2

    # 4. Verify Prometheus metrics reflect consultations and queue decisions
    prom_metrics = production_monitor.export_prometheus_metrics()
    assert "forge_futuris_predictions_consulted_total" in prom_metrics
    assert "forge_prediction_informed_template_selections_total" in prom_metrics
    assert "forge_capacity_aware_queuing_decisions_total" in prom_metrics
