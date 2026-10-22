"""
Data Models for FORGE Self-Improvement Engine.
"""

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class ProposalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"


class ImprovementProposal(BaseModel):
    """Structured self-improvement proposal generated from failure pattern mining."""

    id: str = Field(default_factory=lambda: f"prop_{uuid4().hex[:8]}")
    title: str
    description: str
    root_cause_cluster: str
    affected_component: str
    proposed_remediation: str
    status: ProposalStatus = ProposalStatus.PROPOSED
    evidence_task_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    applied_at: datetime | None = None


class SelfImprovementReport(BaseModel):
    """Aggregate report on historical failure analysis and active improvement proposals."""

    analysis_period_days: int = 7
    total_tasks_analyzed: int = 0
    total_failures_identified: int = 0
    failure_clusters: dict[str, int] = Field(default_factory=dict)
    proposals: list[ImprovementProposal] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
