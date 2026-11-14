"""TASK-REL-030 regression tests: Cortex A/B statistics must be real.

Two mounted frameworks computed "significance" without statistics:

* ``ab_test_framework.calculate_significance`` set
  ``p_value = erf(|z| / sqrt(2))`` — that quantity is the *confidence*
  (2*Phi(|z|) - 1), not the p-value — and then declared significance when
  ``p_value < 0.05``. The test was inverted: identical variants (z = 0)
  were declared significant with a winner, and a large real effect was
  declared not significant (and crashed on an unbound ``winner``).

* ``ab_experiment_framework.analyze_experiment`` fabricated the p-value
  from the participant count alone — ``p = clamp(0.05 / (N / 1000))`` —
  never looking at the conversion difference, so any experiment with
  N >= 50,000 and lift > 0 was declared significant with
  ``confidence_level = 1 - p_value``. Its Bayesian branch used a linear
  formula for ``probability_a_wins`` labelled "simulated" only in a code
  comment.

All expected values below are hand-computed from the standard pooled
two-proportion z-test, p = 2 * (1 - Phi(|z|)):

* A 100/1000 vs B 100/1000: z = 0, p = 1.0.
* A 100/1000 vs B 200/1000: pooled p = 0.15, se = sqrt(.15*.85*.002)
  = 0.015969, z = 6.262, p ~= 3.9e-10.
* control 5000/50000 (10.0%) vs treatment 5050/50000 (10.1%):
  pooled p = 0.1005, se = 0.0019016, z = 0.526, p ~= 0.599.
* A 500/1000 (50%) vs B 520/1000 (52%): pooled p = 0.51,
  se = sqrt(.51*.49*.002) = 0.022356, z = 0.894, p ~= 0.371.
  Bayesian P(B > A) via the normal approximation to the Beta posteriors
  (the same approximation ab_test_framework.bayesian_test uses):
  means 0.4995/0.5195 (with +1/+1 priors), posterior sd ~= 0.02234,
  P(B > A) = Phi(0.02 / 0.02234) ~= Phi(0.895) ~= 0.815.
"""

from __future__ import annotations

import pytest

from cortex_api.ab_experiment_framework import ABExperimentFramework
from cortex_api.ab_test_framework import ABTestFramework


# ── ab_test_framework.calculate_significance ────────────────────────────────


def test_identical_variants_are_not_significant():
    fw = ABTestFramework()
    result = fw.calculate_significance(
        {"conversions": 100, "visitors": 1000},
        {"conversions": 100, "visitors": 1000},
    )
    assert result.status == "not_significant"
    assert result.p_value == pytest.approx(1.0, abs=1e-9)
    assert result.winner in ("", None)


def test_large_effect_is_significant_with_correct_p_value():
    fw = ABTestFramework()
    result = fw.calculate_significance(
        {"conversions": 100, "visitors": 1000},
        {"conversions": 200, "visitors": 1000},
    )
    assert result.status == "significant"
    assert result.winner == "B"
    assert result.p_value == pytest.approx(3.9e-10, rel=0.05)
    assert result.confidence == pytest.approx(1.0 - 3.9e-10, rel=1e-4)


def test_moderate_effect_is_not_significant():
    fw = ABTestFramework()
    result = fw.calculate_significance(
        {"conversions": 500, "visitors": 1000},
        {"conversions": 520, "visitors": 1000},
    )
    assert result.status == "not_significant"
    assert result.p_value == pytest.approx(0.371, abs=0.01)


def test_zero_visitors_does_not_crash_or_invent_significance():
    fw = ABTestFramework()
    result = fw.calculate_significance(
        {"conversions": 0, "visitors": 0},
        {"conversions": 0, "visitors": 0},
    )
    assert result.status == "not_significant"
    assert result.p_value == pytest.approx(1.0, abs=1e-9)


# ── ab_experiment_framework.analyze_experiment ──────────────────────────────


def _seed_experiment(fw: ABExperimentFramework, counts: dict[str, tuple[int, int]]) -> str:
    """Create an experiment and set variant tallies directly.

    ``counts`` maps variant name -> (sample_count, conversion_count); the
    conversion_rate is maintained exactly as record_participant maintains
    it (conversions / samples).
    """
    exp = fw.create_experiment(name="rel030-probe")
    for variant in fw._variants.values():
        if variant.experiment_id != exp.experiment_id:
            continue
        samples, conversions = counts[variant.name]
        variant.sample_count = samples
        variant.conversion_count = conversions
        variant.conversion_rate = conversions / samples if samples else 0.0
    return exp.experiment_id


def test_huge_n_with_tiny_lift_is_not_significant():
    """The fabrication case: N=100,000 used to force p=0.001."""
    fw = ABExperimentFramework()
    exp_id = _seed_experiment(
        fw,
        {"control": (50_000, 5_000), "treatment": (50_000, 5_050)},
    )
    result = fw.analyze_experiment(exp_id)
    assert result.statistical_significance is False
    assert result.p_value == pytest.approx(0.599, abs=0.01)
    assert result.recommended_action == "Continue collecting data"


def test_identical_variants_have_p_value_one():
    fw = ABExperimentFramework()
    exp_id = _seed_experiment(
        fw,
        {"control": (1_000, 100), "treatment": (1_000, 100)},
    )
    result = fw.analyze_experiment(exp_id)
    assert result.statistical_significance is False
    assert result.p_value == pytest.approx(1.0, abs=1e-9)
    assert result.lift_pct == pytest.approx(0.0, abs=1e-9)


def test_real_effect_is_significant():
    fw = ABExperimentFramework()
    exp_id = _seed_experiment(
        fw,
        {"control": (1_000, 100), "treatment": (1_000, 200)},
    )
    result = fw.analyze_experiment(exp_id)
    assert result.statistical_significance is True
    assert result.p_value == pytest.approx(3.9e-10, rel=0.05)
    assert result.winning_variant == "treatment"
    assert result.confidence_level == pytest.approx(0.95, abs=1e-9)


def test_bayesian_probability_matches_normal_approximation():
    fw = ABExperimentFramework()
    exp_id = _seed_experiment(
        fw,
        {"control": (1_000, 500), "treatment": (1_000, 520)},
    )
    fw.analyze_experiment(exp_id, method="bayesian")
    bayes = fw._bayesian[exp_id]
    # _bayesian_analysis ranks variants by rate: A = treatment, B = control.
    assert bayes.variant_a == "treatment"
    assert bayes.probability_a_wins == pytest.approx(0.815, abs=0.01)


def test_bayesian_identical_variants_are_a_coin_flip():
    fw = ABExperimentFramework()
    exp_id = _seed_experiment(
        fw,
        {"control": (1_000, 100), "treatment": (1_000, 100)},
    )
    fw.analyze_experiment(exp_id, method="bayesian")
    bayes = fw._bayesian[exp_id]
    assert bayes.probability_a_wins == pytest.approx(0.5, abs=1e-9)
