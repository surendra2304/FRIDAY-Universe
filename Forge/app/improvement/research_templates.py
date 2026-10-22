"""
Research-Backed Templates Engine for Project FORGE.
When IntelX technical research discovers superior patterns or architectural best practices,
proposes template updates via self-improvement proposals that require approval.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.improvement.self_improve import ImprovementProposal, ProposalStatus, SelfImprovementEngine
from app.improvement.template_evolution import TemplateEvolutionEngine
from app.integrations.intelx_client import IntelXResearchResult

logger = get_logger("improvement.research_templates")


class ResearchTemplatePattern(BaseModel):
    """A template pattern derived from IntelX technical research."""

    technology: str
    archetype: str
    pattern_name: str
    code_pattern: str
    research_finding_id: str
    source_recommendation: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResearchBackedTemplatesManager:
    """
    Evaluates IntelX technical research findings against current starter templates.
    Generates self-improvement proposals for superior patterns and promotes approved templates.
    """

    def __init__(
        self,
        template_engine: TemplateEvolutionEngine | None = None,
        improvement_engine: SelfImprovementEngine | None = None,
    ):
        self.template_engine = template_engine or TemplateEvolutionEngine()
        self.improvement_engine = improvement_engine
        self.research_patterns: dict[str, ResearchTemplatePattern] = {}
        self._initialize_seed_patterns()

    def _initialize_seed_patterns(self):
        """Seed initial research-backed patterns from IntelX intelligence."""
        self.register_research_pattern(
            technology="redis",
            archetype="api",
            pattern_name="redis_connection_pool_singleton",
            code_pattern="""
import redis.asyncio as aioredis
from functools import lru_cache

@lru_cache
def get_redis_pool():
    # Research Finding [S:301]: Connection pooling with bounded limits
    return aioredis.ConnectionPool.from_url("redis://localhost:6379", max_connections=20)
""".strip(),
            research_finding_id="S:301",
            source_recommendation="Always use connection pooling with max_connections limit [S:301]",
        )

        self.register_research_pattern(
            technology="graphql",
            archetype="api",
            pattern_name="graphql_dataloader_batching",
            code_pattern="""
from strawberry.dataloader import DataLoader

async def load_users_batch(keys: list[int]):
    # Research Finding [S:102]: DataLoader pattern solving N+1 query problem
    return await db.fetch_users_by_ids(keys)

user_loader = DataLoader(load_fn=load_users_batch)
""".strip(),
            research_finding_id="S:102",
            source_recommendation="Use DataLoader pattern for batching and caching to solve N+1 query problems [S:102]",
        )

        self.register_research_pattern(
            technology="websockets",
            archetype="api",
            pattern_name="websocket_heartbeat_manager",
            code_pattern="""
class WebSocketConnectionManager:
    # Research Finding [S:201]: Heartbeat & stateful connection tracking
    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            await connection.send_json(message)
""".strip(),
            research_finding_id="S:201",
            source_recommendation="Implement heartbeat / ping-pong frames and connection manager [S:201]",
        )

    def register_research_pattern(
        self,
        technology: str,
        archetype: str,
        pattern_name: str,
        code_pattern: str,
        research_finding_id: str,
        source_recommendation: str,
    ) -> ResearchTemplatePattern:
        """Register a research-backed code pattern and link to template variant."""
        pattern = ResearchTemplatePattern(
            technology=technology,
            archetype=archetype,
            pattern_name=pattern_name,
            code_pattern=code_pattern,
            research_finding_id=research_finding_id,
            source_recommendation=source_recommendation,
        )
        self.research_patterns[pattern_name] = pattern

        # Register or update in template evolution engine
        self.template_engine.register_variant(
            name=pattern_name,
            archetype=archetype,
            code_pattern=code_pattern,
        )
        return pattern

    def propose_template_update_from_research(
        self,
        research_result: IntelXResearchResult,
    ) -> list[ImprovementProposal]:
        """
        Evaluate research findings and generate self-improvement proposals
        for new or updated template patterns requiring human approval.
        """
        generated_proposals: list[ImprovementProposal] = []

        for finding in research_result.findings:
            if finding.category in ["best_practices", "recommended_patterns"]:
                pattern_name = (
                    f"{research_result.technology}_{finding.id.replace(':', '_').lower()}_pattern"
                )
                if pattern_name in self.research_patterns:
                    continue

                proposal = ImprovementProposal(
                    title=f"Adopt IntelX Researched Pattern for {research_result.technology.title()} [{finding.id}]",
                    description=(
                        f"IntelX Technical Research identified superior pattern for '{research_result.technology}': "
                        f"'{finding.title}'. Recommendation: {finding.recommendation}"
                    ),
                    root_cause_cluster="research_backed_improvement",
                    affected_component="templates",
                    proposed_remediation=(
                        f"Incorporate research pattern [{finding.id}] into '{research_result.technology}' "
                        f"starter template boilerplate: {finding.detail}"
                    ),
                    evidence_task_ids=[f"INTELX-{finding.id}"],
                )

                if self.improvement_engine:
                    self.improvement_engine.proposals[proposal.id] = proposal

                generated_proposals.append(proposal)
                logger.info(
                    f"Generated research-backed template proposal: '{proposal.title}' ({proposal.id})"
                )

        return generated_proposals

    def apply_approved_research_proposal(
        self,
        proposal: ImprovementProposal,
        code_pattern: str,
        technology: str,
        archetype: str = "api",
    ) -> ResearchTemplatePattern | None:
        """
        Promote an approved proposal into active research template library.
        """
        if proposal.status != ProposalStatus.APPROVED:
            logger.warning(
                f"Cannot apply unapproved proposal {proposal.id} (status={proposal.status})"
            )
            return None

        finding_id = proposal.evidence_task_ids[0] if proposal.evidence_task_ids else "S:GEN"
        pattern_name = f"{technology}_{finding_id.replace(':', '_').lower()}_template"

        pattern = self.register_research_pattern(
            technology=technology,
            archetype=archetype,
            pattern_name=pattern_name,
            code_pattern=code_pattern,
            research_finding_id=finding_id,
            source_recommendation=proposal.proposed_remediation,
        )
        return pattern

    def get_pattern_for_technology(self, technology: str) -> ResearchTemplatePattern | None:
        """Retrieve the active research template for a technology."""
        tech_clean = technology.lower().strip()
        for p in self.research_patterns.values():
            if p.technology.lower() == tech_clean and p.is_active:
                return p
        return None
