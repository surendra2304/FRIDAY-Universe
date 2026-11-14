"""
Cortex/apps/api/src/cortex_api/ab_experiment_framework.py — Cortex A/B Experiment Framework.

Manages A/B tests and experiments: experiment design, traffic splitting,
statistical analysis, significance testing, and automated experiment
optimization with Bayesian and frequentist approaches.
"""
from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class Experiment:
    """An A/B experiment."""
    experiment_id: str
    name: str
    description: str = ""
    variants: list[dict] = field(default_factory=list)  # [{name, allocation, config}]
    metric: str = ""
    target_sample_size: int = 10000
    significance_level: float = 0.05
    status: str = "draft"  # draft, running, paused, completed, archived
    start_date: str = ""
    end_date: str = ""
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0


@dataclass
class ExperimentVariant:
    """A variant in an experiment."""
    variant_id: str
    experiment_id: str
    name: str
    allocation: float = 0.5
    configuration: dict = field(default_factory=dict)
    sample_count: int = 0
    conversion_count: int = 0
    conversion_rate: float = 0.0
    confidence_interval: list[float] = field(default_factory=list)


@dataclass
class ExperimentResult:
    """Results of an experiment."""
    experiment_id: str
    total_participants: int
    variant_results: list[dict] = field(default_factory=list)
    winning_variant: str = ""
    p_value: float = 0.0
    statistical_significance: bool = False
    lift_pct: float = 0.0
    confidence_level: float = 0.0
    recommended_action: str = ""
    analysis_method: str = "frequentist"


@dataclass
class ExperimentAnalysis:
    """Statistical analysis of an experiment."""
    experiment_id: str
    variant_a: str
    variant_b: str
    conversion_rate_a: float = 0.0
    conversion_rate_b: float = 0.0
    lift: float = 0.0
    p_value: float = 0.0
    confidence_interval: list[float] = field(default_factory=list)
    significant: bool = False
    method: str = "z_test"


@dataclass
class BayesianAnalysis:
    """Bayesian analysis results."""
    experiment_id: str
    variant_a: str
    variant_b: str
    probability_a_wins: float = 0.5
    expected_loss_a: float = 0.0
    expected_loss_b: float = 0.0
    posterior_a: list[float] = field(default_factory=list)
    posterior_b: list[float] = field(default_factory=list)
    map_estimate: str = ""
    confidence: float = 0.0


@dataclass
class ExperimentTimeline:
    """Timeline of experiment events."""
    timeline_id: str
    experiment_id: str
    events: list[dict] = field(default_factory=list)
    milestones: list[dict] = field(default_factory=list)


def _two_proportion_p_value(conv_a: int, n_a: int, conv_b: int, n_b: int) -> float:
    """Two-sided p-value of the pooled two-proportion z-test.

    Returns 1.0 (no evidence of a difference) when either side has no
    observations or the pooled standard error is zero.
    """
    if n_a <= 0 or n_b <= 0:
        return 1.0
    p_pool = (conv_a + conv_b) / (n_a + n_b)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    if se <= 0:
        return 1.0
    z = (conv_b / n_b - conv_a / n_a) / se
    return max(0.0, min(1.0, 1.0 - math.erf(abs(z) / math.sqrt(2))))


def _beta_posterior(conversions: int, samples: int) -> tuple[float, float, float, float]:
    """Beta(conversions+1, samples-conversions+1) posterior.

    Returns (alpha, beta, mean, variance) of the posterior.
    """
    alpha = conversions + 1
    beta = samples - conversions + 1
    total = alpha + beta
    mean = alpha / total
    variance = alpha * beta / (total * total * (total + 1))
    return alpha, beta, mean, variance


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2)))


def _expected_loss_normal(mu: float, sd: float) -> float:
    """E[max(X, 0)] for X ~ N(mu, sd^2) — the Bayesian expected loss of
    choosing the other variant when the true difference is X."""
    if sd <= 0:
        return max(0.0, mu)
    phi = math.exp(-0.5 * (mu / sd) ** 2) / math.sqrt(2 * math.pi)
    return sd * phi + mu * _normal_cdf(mu / sd)


class ABExperimentFramework:
    """A/B experiment framework engine."""

    def __init__(self):
        self._experiments: dict[str, Experiment] = {}
        self._variants: dict[str, ExperimentVariant] = {}
        self._results: dict[str, ExperimentResult] = {}
        self._analyses: dict[str, ExperimentAnalysis] = {}
        self._bayesian: dict[str, BayesianAnalysis] = {}

    def create_experiment(
        self,
        name: str,
        description: str = "",
        metric: str = "conversion_rate",
        variants: list[dict] | None = None,
        target_sample_size: int = 10000,
        significance_level: float = 0.05,
    ) -> Experiment:
        """Create an A/B experiment."""
        experiment = Experiment(
            experiment_id=hashlib.md5(
                f"experiment:{name}:{time.time()}".encode()
            ).hexdigest()[:12],
            name=name,
            description=description,
            metric=metric,
            target_sample_size=target_sample_size,
            significance_level=significance_level,
            created_at=time.time(),
            variants=variants or [
                {"name": "control", "allocation": 0.5, "config": {}},
                {"name": "treatment", "allocation": 0.5, "config": {}},
            ],
        )
        self._experiments[experiment.experiment_id] = experiment

        # Create variants
        for v in experiment.variants:
            variant = ExperimentVariant(
                variant_id=hashlib.md5(
                    f"variant:{experiment.experiment_id}:{v['name']}:{time.time()}".encode()
                ).hexdigest()[:12],
                experiment_id=experiment.experiment_id,
                name=v["name"],
                allocation=v["allocation"],
                configuration=v.get("config", {}),
            )
            self._variants[variant.variant_id] = variant

        return experiment

    def start_experiment(self, experiment_id: str) -> dict:
        """Start an experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise HTTPException(404, f"Experiment {experiment_id} not found")

        experiment.status = "running"
        experiment.started_at = time.time()

        return {"experiment_id": experiment_id, "status": "running"}

    def record_participant(
        self,
        experiment_id: str,
        variant_name: str,
        converted: bool = False,
    ) -> dict:
        """Record a participant in an experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise HTTPException(404, f"Experiment {experiment_id} not found")

        variant = None
        for v in self._variants.values():
            if v.experiment_id == experiment_id and v.name == variant_name:
                variant = v
                break

        if not variant:
            raise HTTPException(404, f"Variant {variant_name} not found in experiment")

        variant.sample_count += 1
        if converted:
            variant.conversion_count += 1

        variant.conversion_rate = variant.conversion_count / max(1, variant.sample_count)

        return {
            "experiment_id": experiment_id,
            "variant": variant_name,
            "sample_count": variant.sample_count,
            "conversion_rate": variant.conversion_rate,
        }

    def analyze_experiment(
        self,
        experiment_id: str,
        method: str = "frequentist",
    ) -> ExperimentResult:
        """Analyze experiment results."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise HTTPException(404, f"Experiment {experiment_id} not found")

        variants = [v for v in self._variants.values() if v.experiment_id == experiment_id]

        # Calculate results
        total_participants = sum(v.sample_count for v in variants)

        # Find winner
        sorted_variants = sorted(variants, key=lambda v: v.conversion_rate, reverse=True)
        winning_variant = sorted_variants[0].name if sorted_variants else ""

        # Calculate lift and a real p-value (pooled two-proportion z-test
        # between the control and the best-performing variant).
        # TASK-REL-030: the previous body fabricated the p-value from the
        # participant count alone — p = clamp(0.05 / (N / 1000)) — without
        # ever looking at the conversion difference, so any experiment
        # with N >= 50,000 and lift > 0 was declared significant.
        if len(variants) >= 2:
            control = next((v for v in variants if v.name == "control"), variants[0])
            treatment = sorted_variants[0]
            lift = (treatment.conversion_rate - control.conversion_rate) / max(0.01, control.conversion_rate) * 100
            p_value = _two_proportion_p_value(
                control.conversion_count,
                control.sample_count,
                treatment.conversion_count,
                treatment.sample_count,
            )
        else:
            lift = 0.0
            p_value = 1.0

        significant = p_value < experiment.significance_level

        # Determine recommended action
        if significant and lift > 0:
            action = f"Launch variant {winning_variant}"
        elif significant and lift < 0:
            action = "Revert to control, discard treatment"
        else:
            action = "Continue collecting data"

        result = ExperimentResult(
            experiment_id=experiment_id,
            total_participants=total_participants,
            variant_results=[
                {
                    "variant": v.name,
                    "sample_count": v.sample_count,
                    "conversion_rate": v.conversion_rate,
                    "conversions": v.conversion_count,
                }
                for v in variants
            ],
            winning_variant=winning_variant,
            p_value=p_value,
            statistical_significance=significant,
            lift_pct=lift,
            confidence_level=1 - experiment.significance_level,
            recommended_action=action,
            analysis_method=method,
        )

        self._results[experiment_id] = result

        # Bayesian analysis if requested
        if method == "bayesian":
            bayesian = self._bayesian_analysis(experiment_id, variants)
            self._bayesian[experiment_id] = bayesian

        return result

    def _bayesian_analysis(
        self,
        experiment_id: str,
        variants: list[ExperimentVariant],
    ) -> BayesianAnalysis:
        """Perform Bayesian analysis."""
        sorted_variants = sorted(variants, key=lambda v: v.conversion_rate, reverse=True)

        if len(sorted_variants) >= 2:
            variant_a = sorted_variants[0]
            variant_b = sorted_variants[1]
        else:
            variant_a = variants[0]
            variant_b = variants[0]

        # Probability A wins: normal approximation to the Beta posteriors
        # (the same approximation ab_test_framework.bayesian_test uses).
        # TASK-REL-030: this was a linear formula in the raw rate gap —
        # 0.5 + 10 * (rate_a - rate_b), clamped — labelled "simulated"
        # only in a code comment while the API presented it as a measured
        # probability.
        alpha_a, beta_a, mean_a, var_a = _beta_posterior(
            variant_a.conversion_count, variant_a.sample_count
        )
        alpha_b, beta_b, mean_b, var_b = _beta_posterior(
            variant_b.conversion_count, variant_b.sample_count
        )
        diff_sd = math.sqrt(var_a + var_b)
        if diff_sd > 0:
            prob_a_wins = _normal_cdf((mean_a - mean_b) / diff_sd)
        else:
            prob_a_wins = 0.5
        prob_a_wins = max(0.0, min(1.0, prob_a_wins))

        # Expected loss of shipping a variant = E[max(other - own, 0)]
        # under the normal approximation to the posterior difference.
        expected_loss_a = _expected_loss_normal(mean_b - mean_a, diff_sd)
        expected_loss_b = _expected_loss_normal(mean_a - mean_b, diff_sd)

        bayesian = BayesianAnalysis(
            experiment_id=experiment_id,
            variant_a=variant_a.name,
            variant_b=variant_b.name,
            probability_a_wins=prob_a_wins,
            expected_loss_a=expected_loss_a,
            expected_loss_b=expected_loss_b,
            posterior_a=[float(alpha_a), float(beta_a)],
            posterior_b=[float(alpha_b), float(beta_b)],
            map_estimate=variant_a.name if prob_a_wins > 0.5 else variant_b.name,
            confidence=abs(prob_a_wins - 0.5) * 2,
        )

        return bayesian

    def complete_experiment(self, experiment_id: str) -> dict:
        """Complete an experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise HTTPException(404, f"Experiment {experiment_id} not found")

        result = self.analyze_experiment(experiment_id)

        experiment.status = "completed"
        experiment.completed_at = time.time()

        return {
            "experiment_id": experiment_id,
            "status": "completed",
            "winning_variant": result.winning_variant,
            "lift_pct": result.lift_pct,
            "significant": result.statistical_significance,
            "recommended_action": result.recommended_action,
        }

    def get_report(self) -> dict:
        """Get A/B experiment framework report."""
        return {
            "total_experiments": len(self._experiments),
            "total_variants": len(self._variants),
            "total_results": len(self._results),
            "total_bayesian_analyses": len(self._bayesian),
            "experiments_by_status": {
                s: sum(1 for e in self._experiments.values() if e.status == s)
                for s in ["draft", "running", "paused", "completed", "archived"]
            },
            "experiments": [
                {
                    "name": e.name,
                    "metric": e.metric,
                    "status": e.status,
                    "variants": len(e.variants),
                    "target_sample": e.target_sample_size,
                }
                for e in self._experiments.values()
            ],
        }


# Module-level singleton
ab_framework = ABExperimentFramework()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/cortex/ab/experiments")
async def create_experiment(payload: dict):
    """Create an A/B experiment."""
    experiment = ab_framework.create_experiment(
        name=payload["name"],
        description=payload.get("description", ""),
        metric=payload.get("metric", "conversion_rate"),
        variants=payload.get("variants", []),
        target_sample_size=payload.get("target_sample_size", 10000),
        significance_level=payload.get("significance_level", 0.05),
    )
    return {"experiment_id": experiment.experiment_id, "name": experiment.name, "status": experiment.status}


@router.post("/api/v1/cortex/ab/experiments/{experiment_id}/start")
async def start_experiment(experiment_id: str):
    """Start an experiment."""
    return ab_framework.start_experiment(experiment_id)


@router.post("/api/v1/cortex/ab/experiments/{experiment_id}/participants")
async def record_participant(experiment_id: str, payload: dict):
    """Record a participant."""
    return ab_framework.record_participant(
        experiment_id=experiment_id,
        variant_name=payload["variant_name"],
        converted=payload.get("converted", False),
    )


@router.get("/api/v1/cortex/ab/experiments/{experiment_id}/analyze")
async def analyze_experiment(experiment_id: str, method: str = "frequentist"):
    """Analyze experiment results."""
    result = ab_framework.analyze_experiment(experiment_id, method)
    return {
        "experiment_id": result.experiment_id,
        "winning_variant": result.winning_variant,
        "p_value": result.p_value,
        "lift_pct": result.lift_pct,
        "significant": result.statistical_significance,
        "confidence_level": result.confidence_level,
        "recommended_action": result.recommended_action,
        "variant_results": result.variant_results,
    }


@router.post("/api/v1/cortex/ab/experiments/{experiment_id}/complete")
async def complete_experiment(experiment_id: str):
    """Complete an experiment."""
    return ab_framework.complete_experiment(experiment_id)


@router.get("/api/v1/cortex/ab/report")
async def get_report():
    """Get A/B experiment framework report."""
    return ab_framework.get_report()
