"""
Unit Tests for Futuris Capacity and Success Prediction Integration in Project FORGE.
"""

import pytest

from app.integrations.futuris_client import (
    FuturisBuildClient,
)
from app.monitoring.production_monitor import ProductionMonitor


@pytest.fixture
def futuris_client():
    return FuturisBuildClient()


def test_predict_build_success_ranking(futuris_client: FuturisBuildClient):
    """Test predicted pass probability ranking across candidate templates."""
    goal = "Build a distributed event processing backend using Kafka and Redis"
    candidates = ["in_memory_crud", "modular_service", "minimal_script"]

    predictions = futuris_client.predict_build_success(goal, candidates)

    assert len(predictions) == 3
    # modular_service should have highest probability for complex goal
    assert predictions[0].template_name == "modular_service"
    assert predictions[0].predicted_pass_probability >= 0.85
    # in_memory should have risk factors flagged
    in_mem_pred = next(p for p in predictions if p.template_name == "in_memory_crud")
    assert len(in_mem_pred.risk_factors) >= 1


def test_forecast_duration_complexity_scaling(futuris_client: FuturisBuildClient):
    """Test duration forecasting scales with task complexity and provides p50/p90 bounds."""
    simple_goal = "Create a simple CLI calculator"
    simple_forecast = futuris_client.forecast_duration(simple_goal)

    complex_goal = "Build a fullstack SaaS dashboard with GraphQL and PostgreSQL"
    complex_forecast = futuris_client.forecast_duration(complex_goal)

    assert complex_forecast.estimated_duration_seconds > simple_forecast.estimated_duration_seconds
    assert complex_forecast.p90_seconds > complex_forecast.p50_seconds
    assert simple_forecast.p90_seconds > simple_forecast.p50_seconds
    assert complex_forecast.complexity_score > simple_forecast.complexity_score


def test_capacity_aware_queueing_decision(futuris_client: FuturisBuildClient):
    """Test capacity check triggers queueing when concurrency limits are approached."""
    # Under low load: immediate scheduling
    low_load = futuris_client.check_capacity(
        current_active_tasks=2, max_capacity=10, estimated_duration=20.0
    )
    assert low_load.should_queue is False
    assert low_load.scheduling_tier == "immediate"
    assert low_load.estimated_wait_seconds == 0.0

    # Under high load (concurrency >= limit): queued scheduling with wait estimate
    high_load = futuris_client.check_capacity(
        current_active_tasks=11, max_capacity=10, estimated_duration=30.0
    )
    assert high_load.should_queue is True
    assert high_load.scheduling_tier in ["queued_fast", "queued_standard"]
    assert high_load.estimated_wait_seconds > 0.0
    assert high_load.queue_priority == 300  # 30.0 * 10

    # Shorter task gets prioritized (lower queue_priority number)
    short_task_load = futuris_client.check_capacity(
        current_active_tasks=11, max_capacity=10, estimated_duration=8.0
    )
    assert short_task_load.queue_priority < high_load.queue_priority


def test_full_assessment_generation(futuris_client: FuturisBuildClient):
    """Test consolidated pre-build assessment generation."""
    goal = "Create a personal portfolio website with dark mode toggle"
    assessment = futuris_client.get_full_assessment(goal=goal, current_active_tasks=1)

    assert assessment.prediction_id.startswith("fut_")
    assert assessment.best_template.predicted_pass_probability >= 0.85
    assert assessment.duration_forecast.estimated_duration_seconds > 0
    assert assessment.capacity_check.should_queue is False


def test_report_build_outcome_calibration(futuris_client: FuturisBuildClient):
    """Test reporting build outcome back to Futuris calibration engine."""
    outcome = futuris_client.report_build_outcome(
        prediction_id="fut_test123",
        goal="Test goal",
        template_used="modular_service",
        actual_duration_seconds=18.4,
        passed=True,
    )

    assert outcome["prediction_id"] == "fut_test123"
    assert outcome["passed"] is True
    assert len(futuris_client.calibration_history) >= 1


def test_production_monitor_futuris_metrics():
    """Test ProductionMonitor tracking Futuris predictions and Prometheus exporter."""
    monitor = ProductionMonitor()
    monitor.record_futuris_consultation()
    monitor.record_futuris_consultation()
    monitor.record_prediction_informed_selection()
    monitor.record_capacity_queue_decision()

    assert monitor.futuris_predictions_consulted_total == 2
    assert monitor.prediction_informed_template_selections_total == 1
    assert monitor.capacity_aware_queuing_decisions_total == 1

    prom_text = monitor.export_prometheus_metrics()
    assert "forge_futuris_predictions_consulted_total 2" in prom_text
    assert "forge_prediction_informed_template_selections_total 1" in prom_text
    assert "forge_capacity_aware_queuing_decisions_total 1" in prom_text
