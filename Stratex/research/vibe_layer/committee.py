"""Committee-style research review (Vibe-Trading pattern, TASK-IG2-STR-03).

Upstream runs multi-agent 'investment committee' research teams. Ported as
a deterministic, LLM-free pattern for Stratex's demo-first programme: four
lenses score a factor/backtest proposal from fixed evidence (IC, Sharpe,
drawdown, trade count) and a weighted vote returns adopt / watch / reject
WITH reasons. No lens can promote anything to trading — 'adopt' means only
'eligible for the forward demo scorecard', which is where promotion is
actually decided.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProposalEvidence:
    factor_name: str
    ic: float
    sharpe: float
    max_drawdown: float  # negative or zero
    n_trades: int
    oos_sharpe: float | None = None  # walk-forward out-of-sample, if run


@dataclass
class CommitteeVerdict:
    factor_name: str
    verdict: str  # "adopt" | "watch" | "reject"
    score: float
    lens_votes: dict[str, str] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


def _lens_signal() -> tuple[str, list[str]]:
    return "watch", []


class ResearchCommittee:
    WEIGHTS = {"signal": 0.35, "risk": 0.30, "evidence": 0.20, "robustness": 0.15}

    def review(self, ev: ProposalEvidence) -> CommitteeVerdict:
        votes: dict[str, str] = {}
        reasons: list[str] = []
        score = 0.0

        # Signal lens: does the factor predict anything at all?
        if ev.ic >= 0.03:
            votes["signal"] = "adopt"; score += self.WEIGHTS["signal"]
            reasons.append(f"IC {ev.ic:.3f} >= 0.03 — measurable predictive signal")
        elif ev.ic >= 0.01:
            votes["signal"] = "watch"; score += self.WEIGHTS["signal"] * 0.5
            reasons.append(f"IC {ev.ic:.3f} weak (0.01–0.03) — watch only")
        else:
            votes["signal"] = "reject"
            reasons.append(f"IC {ev.ic:.3f} < 0.01 — no demonstrated signal")

        # Risk lens: decided Stratex caps — drawdown is a hard gate.
        if ev.max_drawdown <= -0.20:
            votes["risk"] = "reject"
            reasons.append(f"max drawdown {ev.max_drawdown:.1%} breaches the 20% research ceiling")
        elif ev.max_drawdown <= -0.10:
            votes["risk"] = "watch"; score += self.WEIGHTS["risk"] * 0.5
            reasons.append(f"max drawdown {ev.max_drawdown:.1%} elevated — watch")
        else:
            votes["risk"] = "adopt"; score += self.WEIGHTS["risk"]
            reasons.append(f"max drawdown {ev.max_drawdown:.1%} within research ceiling")

        # Evidence lens: sample size before statistics mean anything.
        if ev.n_trades >= 100:
            votes["evidence"] = "adopt"; score += self.WEIGHTS["evidence"]
            reasons.append(f"{ev.n_trades} trades — adequate sample")
        elif ev.n_trades >= 30:
            votes["evidence"] = "watch"; score += self.WEIGHTS["evidence"] * 0.5
            reasons.append(f"{ev.n_trades} trades — thin sample, watch")
        else:
            votes["evidence"] = "reject"
            reasons.append(f"{ev.n_trades} trades < 30 — insufficient evidence")

        # Robustness lens: out-of-sample must not collapse vs in-sample.
        if ev.oos_sharpe is None:
            votes["robustness"] = "watch"; score += self.WEIGHTS["robustness"] * 0.5
            reasons.append("no walk-forward OOS result — robustness unproven")
        elif ev.oos_sharpe > 0 and ev.sharpe > 0 and ev.oos_sharpe >= 0.5 * ev.sharpe:
            votes["robustness"] = "adopt"; score += self.WEIGHTS["robustness"]
            reasons.append(f"OOS Sharpe {ev.oos_sharpe:.2f} holds >= 50% of in-sample {ev.sharpe:.2f}")
        else:
            votes["robustness"] = "reject"
            reasons.append(f"OOS Sharpe {ev.oos_sharpe:.2f} collapses vs in-sample {ev.sharpe:.2f} — overfit")

        n_rejects = sum(1 for v in votes.values() if v == "reject")
        if votes["risk"] == "reject" or n_rejects >= 2 or score < 0.35:
            verdict = "reject"
        elif score >= 0.75 and "reject" not in votes.values():
            verdict = "adopt"
        else:
            verdict = "watch"
        return CommitteeVerdict(ev.factor_name, verdict, round(score, 4), votes, reasons)
