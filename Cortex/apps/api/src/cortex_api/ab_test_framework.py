TestResult,
    BayesianResult,
)


@pytest.fixture
def ab_framework():
    return ABTestFramework()


def test_create_and_get_test(ab_framework):
    variants = [
        TestVariant(variant_id="control", name="Control", allocation=0.5, is_control=True),
        TestVariant(variant_id="treatment", name="Treatment", allocation=0.5),
    ]
    metrics = [
        TestMetric(metric_id="conversion", name="Conversion Rate", type="binary")
    ]
    
    test_id = "test_shared_task_claim"
    created = ab_framework.create_test(
        test_id=test_id,
        name="Shared Task Claims & Ownership Handoff Test",
        variants=variants,
        metrics=metrics,
    )
    
    assert created["test_id"] == test_id
    assert len(created["variants"]) == 2
    
    fetched = ab_framework.get_test(test_id)
    assert fetched is not None
    assert fetched["name"] == "Shared Task Claims & Ownership Handoff Test"


def test_assign_variant_consistency(ab_framework):
    variants = [
        TestVariant(variant_id="ctrl", name="Control", allocation=0.5, is_control=True),
        TestVariant(variant_id="feat", name="Feature", allocation=0.5),
    ]
    test_id = "handoff_consistency_test"
    ab_framework.create_test(
        test_id=test_id,
        name="Handoff Consistency Test",
        variants=variants,
        metrics=[TestMetric(metric_id="latency", name="Latency", type="continuous")]
    )
    
    user_id = "agent_node_789"
    assigned_first = ab_framework.assign_variant(test_id, user_id)
    assigned_second = ab_framework.assign_variant(test_id, user_id)
    
    assert assigned_first == assigned_second
    assert assigned_first in ["ctrl", "feat"]


def test_calculate_statistical_significance(ab_framework):
    test_id = "ownership_claim_metric_test"
    ab_framework.create_test(
        test_id=test_id,
        name="Ownership Claim Metric Test",
        variants=[
            TestVariant(variant_id="a", name="A", allocation=0.5, is_control=True),
            TestVariant(variant_id="b", name="B", allocation=0.5),
        ],
        metrics=[TestMetric(metric_id="success", name="Success", type="binary")]
    )
    
    # Simulate high conversion for variant B vs A to verify positive lift & p-value
    result = ab_framework.calculate_significance(
        test_id=test_id,
        control_conversions=100,
        control_samples=1000,
        treatment_conversions=150,
        treatment_samples=1000,
    )
    
    assert isinstance(result, TestResult)
    assert result.lift > 0
    assert result.p_value < 0.05
    assert result.winner == "b"


def test_bayesian_ab_test_evaluation(ab_framework):
    test_id = "bayesian_handoff_test"
    ab_framework.create_test(
        test_id=test_id,
        name="Bayesian Handoff Test",
        variants=[
            TestVariant(variant_id="control", name="Control", allocation=0.5, is_control=True),
            TestVariant(variant_id="treatment", name="Treatment", allocation=0.5),
        ],
        metrics=[TestMetric(metric_id="claim_speed", name="Claim Speed", type="continuous")]
    )
    
    bayes_res = ab_framework.evaluate_bayesian(
        test_id=test_id,
        control_successes=200,
        control_trials=1000,
        treatment_successes=250,
        treatment_trials=1000,
    )
    
    assert isinstance(bayes_res, BayesianResult)
    assert 0.0 <= bayes_res.variant_a_prob <= 1.0
    assert 0.0 <= bayes_res.variant_b_prob <= 1.0
    assert bayes_res.test_id == test_id