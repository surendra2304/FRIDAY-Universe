"""
Self-repair and autonomous healing subsystem for Forge.
"""

from app.selfrepair.engine import SelfRepairEngine
from app.selfrepair.models import (
    RepairAttempt,
    RepairResult,
    RepairStrategyType,
)
from app.selfrepair.proposer import (
    CandidateFix,
    GitSelfRepairProposer,
    ProposalOutcome,
    RepairProposalRequest,
    TestRun,
)

__all__ = [
    "CandidateFix",
    "GitSelfRepairProposer",
    "ProposalOutcome",
    "RepairAttempt",
    "RepairProposalRequest",
    "RepairResult",
    "RepairStrategyType",
    "SelfRepairEngine",
    "TestRun",
]
