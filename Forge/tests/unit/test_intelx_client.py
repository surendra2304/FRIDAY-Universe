"""
Unit Tests for IntelX Technical Research Integration and Research-Backed Templates in Project FORGE.
"""

import pytest

from app.improvement.research_templates import ResearchBackedTemplatesManager
from app.improvement.self_improve import ProposalStatus
from app.improvement.template_evolution import TemplateEvolutionEngine
from app.integrations.intelx_client import (
    IntelXResearchFinding,
    IntelXResearchResult,
    IntelXTechClient,
)
from app.monitoring.production_monitor import ProductionMonitor


@pytest.fixture
def intelx_client():
    return IntelXTechClient()


@pytest.fixture
def research_manager():
    template_engine = TemplateEvolutionEngine()
    return ResearchBackedTemplatesManager(template_engine=template_engine)


def test_detect_unfamiliar_technologies(intelx_client: IntelXTechClient):
    """Test technology detector identifying unfamiliar or complex technologies in task goal."""
    goal1 = "Create a real-time event streaming pipeline using Kafka and WebSockets"
    detected1 = intelx_client.detect_unfamiliar_technologies(goal1)
    assert "kafka" in detected1
    assert "websockets" in detected1

    goal2 = "Build a GraphQL API with Redis caching and Celery background workers"
    detected2 = intelx_client.detect_unfamiliar_technologies(goal2)
    assert "graphql" in detected2
    assert "redis" in detected2
    assert "celery" in detected2

    goal3 = "Create a simple personal portfolio website in HTML and CSS"
    detected3 = intelx_client.detect_unfamiliar_technologies(goal3)
    assert len(detected3) == 0


@pytest.mark.asyncio
async def test_research_technology_builtin_intelligence(intelx_client: IntelXTechClient):
    """Test querying technical research for known complex technologies."""
    result = await intelx_client.research_technology("graphql")

    assert result.technology == "graphql"
    assert len(result.best_practices) >= 2
    assert len(result.pitfalls_to_avoid) >= 1
    assert len(result.recommended_patterns) >= 1
    assert result.confidence >= 0.85

    # Check finding IDs
    finding_ids = [f.id for f in result.findings]
    assert any("S:10" in fid or "IX" in fid for fid in finding_ids)


@pytest.mark.asyncio
async def test_research_technology_dynamic_synthesis(intelx_client: IntelXTechClient):
    """Test querying technical research for novel technologies."""
    result = await intelx_client.research_technology("weaviate")

    assert result.technology == "weaviate"
    assert len(result.findings) >= 2
    assert result.confidence > 0.70


def test_format_research_context_for_prompt(intelx_client: IntelXTechClient):
    """Test constructing prompt injection context with research citations."""
    finding = IntelXResearchFinding(
        id="S:301",
        technology="redis",
        category="best_practices",
        title="Connection Pooling",
        detail="Use connection pooling with bounded max_connections",
        recommendation="Always use connection pooling with max_connections limit [S:301]",
    )
    result = IntelXResearchResult(
        query="Best practices for redis?",
        technology="redis",
        findings=[finding],
        best_practices=[finding.recommendation],
        pitfalls_to_avoid=["Avoid KEYS * in production [S:304]"],
        recommended_patterns=["Cache-Aside with connection pool [S:306]"],
        performance_considerations=["Use redis ConnectionPool singleton [S:308]"],
    )

    formatted = intelx_client.format_research_context_for_prompt([result])
    assert "INTELX TECHNICAL RESEARCH FINDINGS & MANDATORY PATTERNS:" in formatted
    assert "REDIS" in formatted
    assert "[S:301]" in formatted
    assert "[S:304]" in formatted


def test_research_backed_template_proposal_generation(
    research_manager: ResearchBackedTemplatesManager,
):
    """Test generating self-improvement proposals from research results."""
    finding = IntelXResearchFinding(
        id="S:999",
        technology="custom_db",
        category="recommended_patterns",
        title="Write-Ahead Log Pattern",
        detail="Append writes to WAL before memory table flush",
        recommendation="Implement WAL pattern for crash consistency [S:999]",
    )
    result = IntelXResearchResult(
        query="Best practices for custom_db?",
        technology="custom_db",
        findings=[finding],
        recommended_patterns=[finding.recommendation],
    )

    proposals = research_manager.propose_template_update_from_research(result)
    assert len(proposals) >= 1
    assert "Adopt IntelX Researched Pattern for Custom_Db [S:999]" in proposals[0].title
    assert proposals[0].status == ProposalStatus.PROPOSED

    # Test applying approved proposal
    proposals[0].status = ProposalStatus.APPROVED
    pattern = research_manager.apply_approved_research_proposal(
        proposal=proposals[0],
        code_pattern="class WALManager: pass",
        technology="custom_db",
        archetype="api",
    )
    assert pattern is not None
    assert pattern.technology == "custom_db"
    assert pattern.research_finding_id == "INTELX-S:999"


def test_production_monitor_intelx_metrics():
    """Test ProductionMonitor tracking IntelX research queries and Prometheus export."""
    monitor = ProductionMonitor()
    monitor.record_intelx_query()
    monitor.record_intelx_query()
    monitor.record_research_informed_build()

    assert monitor.intelx_research_queries_total == 2
    assert monitor.research_informed_builds_total == 1

    prom_text = monitor.export_prometheus_metrics()
    assert "forge_intelx_research_queries_total 2" in prom_text
    assert "forge_research_informed_builds_total 1" in prom_text
