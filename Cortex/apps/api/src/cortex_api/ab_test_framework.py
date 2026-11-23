import unittest
from cortex_api.ab_test_framework import (
    ABTestFramework,
    TestVariant,
    TestMetric,
    TestResult,
    BayesianResult
)

class TestABTestFramework(unittest.TestCase):
    def setUp(self):
        self.framework = ABTestFramework()
        self.test_id = "test_collab_hub_35"
        self.variants = [
            TestVariant(variant_id="control", name="Control", allocation=0.5, is_control=True),
            TestVariant(variant_id="treatment", name="Treatment", allocation=0.5, is_control=False)
        ]
        self.metrics = [
            TestMetric(metric_id="claim_success", name="Task Claim Success", type="binary")
        ]

    def test_create_and_get_test(self):
        self.framework.create_test(
            test_id=self.test_id,
            name="Task Claim & Ownership Hand-off Test",
            variants=self.variants,
            metrics=self.metrics
        )
        test_data = self.framework.get_test(self.test_id)
        self.assertIsNotNone(test_data)
        self.assertEqual(test_data["name"], "Task Claim & Ownership Hand-off Test")
        self.assertEqual(len(test_data["variants"]), 2)

    def test_record_and_calculate_results(self):
        self.framework.create_test(
            test_id=self.test_id,
            name="Task Claim & Ownership Hand-off Test",
            variants=self.variants,
            metrics=self.metrics
        )
        
        # Simulate recording metrics for shared task claims/handoffs
        for _ in range(100):
            self.framework.record_event(self.test_id, "control", "claim_success", 1)
            self.framework.record_event(self.test_id, "treatment", "claim_success", 1)
        for _ in range(50):
            self.framework.record_event(self.test_id, "control", "claim_success", 0)
            self.framework.record_event(self.test_id, "treatment", "claim_success", 0)

        result = self.framework.calculate_results(self.test_id)
        self.assertIsInstance(result, TestResult)
        self.assertEqual(result.test_id, self.test_id)

    def test_bayesian_analysis(self):
        self.framework.create_test(
            test_id=self.test_id,
            name="Task Claim & Ownership Hand-off Test",
            variants=self.variants,
            metrics=self.metrics
        )
        
        bayesian_res = self.framework.calculate_bayesian(self.test_id)
        self.assertIsInstance(bayesian_res, BayesianResult)
        self.assertEqual(bayesian_res.test_id, self.test_id)

if __name__ == "__main__":
    unittest.main()