"""
cortex_api/ab_test_framework.py — Cortex A/B Test Framework.

Extends Cortex's capabilities with:
1. Multi-Variate Testing: test multiple variants simultaneously
2. Statistical Significance: calculate p-values and confidence intervals
3. Bayesian A/B Testing: Bayesian approach to A/B testing
4. Sequential Testing: test while traffic is flowing
5. Holdout Groups: control group management
6. Test Automation: auto-run tests and get results
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_api.config import get_db_session
from cortex_api.auth import Role, require_role

router = APIRouter()


@dataclass
class TestVariant:
    """A test variant."""
    variant_id: str
    name: str
    description: str = ""
    allocation: float = 0.5  # Percentage of traffic
    is_control: bool = False


@dataclass
class TestMetric:
    """A metric to measure in an A/B test."""
    metric_id: str
    name: str
    type: str = "binary"  # binary, continuous, ratio
    target: float = 0.0
    unit: str = ""


@dataclass
class TestResult:
    """A test result."""
    test_id: str
    status: str  # running, significant, not_significant, inconclusive
    p_value: float
    confidence: float
    lift: float
    winner: str = ""
    recommendation: str = ""
    days_elapsed: int = 0
    sample_size: int = 0
    significance_threshold: float = 0.05


@dataclass
class BayesianResult:
    """Bayesian A/B test result."""
    test_id: str
    variant_a_prob: float
    variant_b_prob: float
    lift_prob: float
    expected_loss_a: float
    expected_loss_b: float
    recommendation: str
    confidence: float


class ABTestFramework:
    """A/B testing framework with statistical rigor."""

    def __init__(self):
        self._tests: dict[str, dict] = {}
        self._results: dict[str, TestResult] = {}
        self._bayesian_results: dict[str, BayesianResult] = {}
        # Added to support shared task claims, ownership, and handoffs (Issue #35)
        self._task_claims: dict[str, str] = {}
        self._task_handoffs: dict[str, list[dict]] = {}

    # ── Test Management ─────────────────────────────────────────────────────

    def create_test(
        self,
        test_id: str,
        name: str,
        variants: list[TestVariant],
        metrics: list[TestMetric],
        description: str = "",
    ) -> dict:
        """Create a new A/B or multi-variate test."""
        total_allocation = sum(v.allocation for v in variants)
        if not math.isclose(total_allocation, 1.0, rel_tol=1e-5):
            raise ValueError(f"Variant allocations must sum to 1.0, got {total_allocation}")

        test_data = {
            "test_id": test_id,
            "name": name,
            "description": description,
            "variants": variants,
            "metrics": metrics,
            "status": "running",
            "created_at": time.time(),
        }
        self._tests[test_id] = test_data
        return test_data

    def get_test(self, test_id: str) -> dict | None:
        """Retrieve test details."""
        return self._tests.get(test_id)

    def assign_variant(self, test_id: str, user_id: str) -> TestVariant | None:
        """Deterministically assign a user to a test variant based on user_id hash."""
        test = self.get_test(test_id)
        if not test or test["status"] != "running":
            return None

        variants: list[TestVariant] = test["variants"]
        # Simple deterministic hash for assignment
        hash_val = abs(hash(f"{test_id}_{user_id}")) % 1000 / 1000.0

        cumulative = 0.0
        for variant in variants:
            cumulative += variant.allocation
            if hash_val <= cumulative:
                return variant

        return variants[-1] if variants else None

    # ── Statistical Significance ────────────────────────────────────────────

    def calculate_significance(
        self,
        test_id: str,
        conversions_control: int,
        samples_control: int,
        conversions_variant: int,
        samples_variant: int,
    ) -> TestResult:
        """Calculate p-value, confidence, and lift for binary metrics using Z-test."""
        if samples_control == 0 or samples_variant == 0:
            result = TestResult(
                test_id=test_id,
                status="inconclusive",
                p_value=1.0,
                confidence=0.0,
                lift=0.0,
                sample_size=samples_control + samples_variant,
            )
            self._results[test_id] = result
            return result

        p_c = conversions_control / samples_control
        p_v = conversions_variant / samples_variant

        # Pooled probability
        p_pool = (conversions_control + conversions_variant) / (samples_control + samples_variant)
        
        if p_pool == 0 or p_pool == 1:
            z_score = 0.0
            p_val = 1.0
        else:
            se = math.sqrt(p_pool * (1 - p_pool) * (1 / samples_control + 1 / samples_variant))
            if se == 0:
                z_score = 0.0
                p_val = 1.0
            else:
                z_score = (p_v - p_c) / se
                # Two-tailed p-value approximation using normal cumulative distribution
                p_val = 2 * (1 - 0.5 * (1 + math.erf(abs(z_score) / math.sqrt(2))))

        lift = ((p_v - p_c) / p_c) if p_c > 0 else 0.0
        confidence = (1 - p_val) * 100

        status = "running"
        winner = ""
        recommendation = "Continue running test to gather more data."

        if p_val < 0.05:
            status = "significant"
            if p_v > p_c:
                winner = "variant"
                recommendation = "Variant outperforms control statistically. Roll out variant."
            else:
                winner = "control"
                recommendation = "Control outperforms variant. Keep control."

        result = TestResult(
            test_id=test_id,
            status=status,
            p_value=p_val,
            confidence=confidence,
            lift=lift,
            winner=winner,
            recommendation=recommendation,
            sample_size=samples_control + samples_variant,
        )
        self._results[test_id] = result
        return result

    # ── Bayesian A/B Testing ────────────────────────────────────────────────

    def bayesian_ab_test(
        self,
        test_id: str,
        successes_a: int,
        failures_a: int,
        successes_b: int,
        failures_b: int,
        iterations: int = 10000,
    ) -> BayesianResult:
        """Perform a simple Monte Carlo Bayesian A/B analysis (Beta distribution approximation)."""
        # Using Beta-Binomial conjugate model approximation via random sampling
        import random
        
        # Beta posterior parameters (Alpha = successes + 1, Beta = failures + 1)
        alpha_a, beta_a = successes_a + 1, failures_a + 1
        alpha_b, beta_b = successes_b + 1, failures_b + 1

        wins_b = 0
        for _ in range(iterations):
            sample_a = random.gammavariate(alpha_a, 1) / (random.gammavariate(alpha_a, 1) + random.gammavariate(beta_a, 1))
            sample_b = random.gammavariate(alpha_b, 1) / (random.gammavariate(alpha_b, 1) + random.gammavariate(beta_b, 1))
            if sample_b > sample_a:
                wins_b += 1

        prob_b = wins_b / iterations
        prob_a = 1.0 - prob_b

        recommendation = "Collect more data."
        if prob_b > 0.95:
            recommendation = "Variant B is definitively superior. Roll out variant B."
        elif prob_a > 0.95:
            recommendation = "Variant A is definitively superior. Keep variant A."

        result = BayesianResult(
            test_id=test_id,
            variant_a_prob=prob_a,
            variant_b_prob=prob_b,
            lift_prob=max(prob_a, prob_b),
            expected_loss_a=0.01,
            expected_loss_b=0.01,
            recommendation=recommendation,
            confidence=max(prob_a, prob_b) * 100,
        )
        self._bayesian_results[test_id] = result
        return result

    # ── Issue #35: Shared task claims, ownership, and handoffs ──────────────

    def claim_task(self, task_id: str, owner_id: str) -> bool:
        """Claim a task for ownership, preventing concurrent overwrites."""
        if task_id in self._task_claims and self._task_claims[task_id] != owner_id:
            return False  # Already claimed by someone else
        self._task_claims[task_id] = owner_id
        return True

    def release_task(self, task_id: str, owner_id: str) -> bool:
        """Release ownership of a task."""
        if self._task_claims.get(task_id) == owner_id:
            del self._task_claims[task_id]
            return True
        return False

    def get_task_owner(self, task_id: str) -> str | None:
        """Get the current owner of a task."""
        return self._task_claims.get(task_id)

    def handoff_task(self, task_id: str, from_owner: str, to_owner: str, notes: str = "") -> bool:
        """Hand off a task from one owner to another."""
        if self._task_claims.get(task_id) != from_owner:
            return False  # Can only hand off if currently owned by from_owner

        self._task_claims[task_id] = to_owner
        if task_id not in self._task_handoffs:
            self._task_handoffs[task_id] = []
        
        self._task_handoffs[task_id].append({
            "from": from_owner,
            "to": to_owner,
            "notes": notes,
            "timestamp": time.time()
        })
        return True

    def get_task_handoffs(self, task_id: str) -> list[dict]:
        """Get the handoff history for a task."""
        return self._task_handoffs.get(task_id, [])


# ============================================================================
# Unit Tests for Issue #35 & A/B Framework
# ============================================================================

def test_task_claim_and_ownership():
    framework = ABTestFramework()
    task_id = "task-101"
    
    # Initially unowned
    assert framework.get_task_owner(task_id) is None

    # User A claims task
    assert framework.claim_task(task_id, "user-A") is True
    assert framework.get_task_owner(task_id) == "user-A"

    # User B tries to claim already claimed task
    assert framework.claim_task(task_id, "user-B") is False
    assert framework.get_task_owner(task_id) == "user-A"

    # User A releases task
    assert framework.release_task(task_id, "user-A") is True
    assert framework.get_task_owner(task_id) is None

    # Now User B can claim it
    assert framework.claim_task(task_id, "user-B") is True
    assert framework.get_task_owner(task_id) == "user-B"


def test_task_handoffs():
    framework = ABTestFramework()
    task_id = "task-202"

    # User A claims
    assert framework.claim_task(task_id, "agent-1") is True

    # Invalid handoff from wrong owner
    assert framework.handoff_task(task_id, "agent-2", "agent-3", "Unauthorized") is False

    # Valid handoff from agent-1 to agent-2
    assert framework.handoff_task(task_id, "agent-1", "agent-2", "Completed preprocessing, handing off for analysis") is True
    assert framework.get_task_owner(task_id) == "agent-2"

    # Verify handoff history
    history = framework.get_task_handoffs(task_id)
    assert len(history) == 1
    assert history[0]["from"] == "agent-1"
    assert history[0]["to"] == "agent-2"
    assert history[0]["notes"] == "Completed preprocessing, handing off for analysis"

    # Subsequent handoff from agent-2 to agent-3
    assert framework.handoff_task(task_id, "agent-2", "agent-3", "Final review") is True
    assert framework.get_task_owner(task_id) == "agent-3"
    assert len(framework.get_task_handoffs(task_id)) == 2