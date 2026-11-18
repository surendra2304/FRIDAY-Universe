"""The frozen judgement (TASK-STR-EXP-001).

A pure function of the pooled metrics and the global trial number —
the same bars every research round was judged under, unchanged:

PROVEN (full bar): expectancy > 0 AND PF >= 1.2 AND >= 200 trades AND
>= 4/5 positive folds AND Bonferroni one-sided p < 0.05 / N AND pooled
holdout expectancy > 0 (holdout must exist for every member — a
combination that cannot show its holdout cannot be proven).

FORWARD_TEST (owner's second tier, 2026-11-18): expectancy > 0 AND
PF >= 1.05 AND >= 200 trades.

Anything else: FAIL — recorded closed, never admitted, and its lesson
goes to the universal section as well as Stratex's private one
(owner rule R).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import bounds
from .runner import PooledMetrics


@dataclass
class Verdict:
    verdict: str  # "PROVEN" | "FORWARD_TEST" | "FAIL"
    checks: dict[str, bool] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "checks": self.checks,
            "reasons": self.reasons,
        }


def judge(metrics: PooledMetrics, n_global: int) -> Verdict:
    """Judge pooled metrics at global trial number n_global."""
    bonferroni_threshold = bounds.BONFERRONI_ALPHA / max(n_global, 1)
    checks = {
        "expectancy_gt_0": metrics.expectancy > 0,
        "pf_gte_full_bar": metrics.pf >= bounds.FULL_BAR_PF,
        "pf_gte_second_tier": metrics.pf >= bounds.SECOND_TIER_PF,
        "trades_gte_200": metrics.trades >= bounds.MIN_OOS_TRADES,
        "folds_gte_4_of_5": (
            metrics.positive_folds >= bounds.FULL_BAR_MIN_POSITIVE_FOLDS
        ),
        "bonferroni": metrics.p_one_sided < bonferroni_threshold,
        "holdout_present": metrics.holdout_expectancy is not None,
        "holdout_expectancy_gt_0": (
            metrics.holdout_expectancy is not None
            and metrics.holdout_expectancy > 0
        ),
    }
    full_bar = all(
        checks[k]
        for k in (
            "expectancy_gt_0",
            "pf_gte_full_bar",
            "trades_gte_200",
            "folds_gte_4_of_5",
            "bonferroni",
            "holdout_expectancy_gt_0",
        )
    )
    if full_bar:
        return Verdict(
            verdict="PROVEN",
            checks=checks,
            reasons=[
                f"full frozen bar cleared at N={n_global}: expectancy "
                f"{metrics.expectancy:+.4%}, PF {metrics.pf:.4f}, "
                f"{metrics.trades} trades, {metrics.positive_folds}/"
                f"{metrics.folds_with_trades} positive folds, p "
                f"{metrics.p_one_sided:.3g} < {bonferroni_threshold:.3g}, "
                f"holdout expectancy {metrics.holdout_expectancy:+.4%}"
            ],
        )
    second_tier = all(
        checks[k]
        for k in ("expectancy_gt_0", "pf_gte_second_tier", "trades_gte_200")
    )
    if second_tier:
        failed_full = [
            k
            for k in (
                "pf_gte_full_bar",
                "folds_gte_4_of_5",
                "bonferroni",
                "holdout_expectancy_gt_0",
            )
            if not checks[k]
        ]
        return Verdict(
            verdict="FORWARD_TEST",
            checks=checks,
            reasons=[
                f"second tier cleared (expectancy {metrics.expectancy:+.4%}, "
                f"PF {metrics.pf:.4f}, {metrics.trades} trades); full bar "
                f"not met on: {', '.join(failed_full) or 'none recorded'} — "
                f"demo forward evidence decides it"
            ],
        )
    failed_tier = [
        k
        for k in ("expectancy_gt_0", "pf_gte_second_tier", "trades_gte_200")
        if not checks[k]
    ]
    return Verdict(
        verdict="FAIL",
        checks=checks,
        reasons=[
            f"second tier not met on: {', '.join(failed_tier)} "
            f"(expectancy {metrics.expectancy:+.4%}, PF {metrics.pf:.4f}, "
            f"{metrics.trades} trades) — recorded closed"
        ],
    )
