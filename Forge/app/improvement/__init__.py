"""
Autonomous Self-Improvement Subsystem for Project FORGE.
"""

from app.improvement.models import (
    ImprovementProposal,
    ProposalStatus,
    SelfImprovementReport,
)
from app.improvement.self_improve import (
    SelfImprovementEngine,
    self_improvement_engine,
)

__all__ = [
    "ImprovementProposal",
    "ProposalStatus",
    "SelfImprovementEngine",
    "SelfImprovementReport",
    "self_improvement_engine",
]
