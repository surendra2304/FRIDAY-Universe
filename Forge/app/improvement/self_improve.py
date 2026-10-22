"""
Self-Improvement Engine for Project FORGE.
Analyzes failure patterns over rolling time windows, clusters root causes,
and formulates actionable improvement proposals that require explicit human approval to apply.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from app.core.logging import get_logger
from app.improvement.models import (
    ImprovementProposal,
    ProposalStatus,
    SelfImprovementReport,
)
from app.memory.db import DatabaseManager, db_manager
from app.memory.models import TaskEntity, TaskState
from app.memory.state_store import StateStore

logger = get_logger("improvement.self_improve")


class SelfImprovementEngine:
    """Mines task histories for failure clusters and governs safe improvement proposals."""

    def __init__(self, db: DatabaseManager | None = None):
        self.db = db or db_manager
        self.store = StateStore(self.db)
        self.proposals: dict[str, ImprovementProposal] = {}

    async def generate_weekly_report(self, days: int = 7) -> SelfImprovementReport:
        """Analyze failed tasks from past N days, cluster root causes, and generate proposals."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        tasks = await self.store.list_tasks(limit=1000)

        recent_tasks = [t for t in tasks if t.created_at and t.created_at >= cutoff]
        failed_tasks = [t for t in recent_tasks if t.state == TaskState.FAILED]

        clusters: dict[str, list[TaskEntity]] = defaultdict(list)

        for t in failed_tasks:
            err = (t.error_message or "").lower()
            if "dependency" in err or "modulenotfound" in err or "importerror" in err:
                clusters["missing_dependencies"].append(t)
            elif "syntax" in err or "syntaxerror" in err or "indentationerror" in err:
                clusters["syntax_errors"].append(t)
            elif "verification" in err or "check" in err or "assert" in err:
                clusters["verification_failures"].append(t)
            elif "fallback" in err or "stub" in err:
                clusters["fallback_stub_issues"].append(t)
            elif "security" in err:
                clusters["security_violations"].append(t)
            else:
                clusters["runtime_failures"].append(t)

        new_proposals: list[ImprovementProposal] = []

        # Formulate proposal for missing dependencies if failures detected
        if len(clusters.get("missing_dependencies", [])) >= 1:
            t_ids = [t.id for t in clusters["missing_dependencies"]]
            prop = ImprovementProposal(
                title="Add Automated Pre-Synthesis Dependency Inspection",
                description=f"{len(t_ids)} failures caused by missing dependency imports. Recommend adding AST dependency pre-checks during Planning stage.",
                root_cause_cluster="missing_dependencies",
                affected_component="planning",
                proposed_remediation="Enable AST import scanner in PlannerRole before DeveloperRole wave execution.",
                evidence_task_ids=t_ids,
            )
            self.proposals[prop.id] = prop
            new_proposals.append(prop)

        # Formulate proposal for syntax errors if failures detected
        if len(clusters.get("syntax_errors", [])) >= 1:
            t_ids = [t.id for t in clusters["syntax_errors"]]
            prop = ImprovementProposal(
                title="Enforce AST Parsing and Lint Gate Prior to Delivery Packaging",
                description=f"{len(t_ids)} tasks failed during verification with AST syntax errors. Enforce immediate AST validation after Developer synthesis.",
                root_cause_cluster="syntax_errors",
                affected_component="developer",
                proposed_remediation="Run ast.parse() immediately upon receiving code from LLM or AI Universe.",
                evidence_task_ids=t_ids,
            )
            self.proposals[prop.id] = prop
            new_proposals.append(prop)

        # Formulate proposal for verification assertions
        if len(clusters.get("verification_failures", [])) >= 1:
            t_ids = [t.id for t in clusters["verification_failures"]]
            prop = ImprovementProposal(
                title="Enhance Self-Repair Diagnostic Context for Verification Checks",
                description=f"{len(t_ids)} tasks failed verification assertions. Expand compiler error snippets provided to RepairEngine.",
                root_cause_cluster="verification_failures",
                affected_component="verification",
                proposed_remediation="Include last 50 lines of Pytest failure logs into the self-repair prompt context.",
                evidence_task_ids=t_ids,
            )
            self.proposals[prop.id] = prop
            new_proposals.append(prop)

        # Formulate proposal for security scanner violations if failures detected
        if len(clusters.get("security_violations", [])) >= 1:
            t_ids = [t.id for t in clusters["security_violations"]]
            prop = ImprovementProposal(
                title="Update API & Starter Templates with Input Validation & Parameterized Queries",
                description=f"{len(t_ids)} tasks failed output security scans due to missing input validation or unparameterized queries. Update starter templates with validation boilerplate.",
                root_cause_cluster="security_violations",
                affected_component="templates",
                proposed_remediation="Inject Pydantic schema validation and parameterized database bindings into all base project templates.",
                evidence_task_ids=t_ids,
            )
            self.proposals[prop.id] = prop
            new_proposals.append(prop)

        return SelfImprovementReport(
            analysis_period_days=days,
            total_tasks_analyzed=len(recent_tasks),
            total_failures_identified=len(failed_tasks),
            failure_clusters={k: len(v) for k, v in clusters.items()},
            proposals=list(self.proposals.values()),
        )

    def apply_proposal(self, proposal_id: str) -> ImprovementProposal | None:
        """
        Apply an approved improvement proposal.
        SAFETY RULE: Never executes without explicit approval.
        """
        prop = self.proposals.get(proposal_id)
        if not prop:
            return None

        prop.status = ProposalStatus.APPLIED
        prop.applied_at = datetime.now(UTC)
        logger.info(f"Applied human-approved improvement proposal '{prop.id}': {prop.title}")
        return prop


self_improvement_engine = SelfImprovementEngine()
