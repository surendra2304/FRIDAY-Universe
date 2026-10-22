"""
Analytics API Endpoints for Project FORGE.
Exposes high-level performance summaries, project type metrics, and failure analyses.
"""

from fastapi import APIRouter

from app.analytics.task_analytics import (
    AnalyticsSummary,
    FailureAnalysis,
    TypePerformance,
    task_analytics_service,
)

analytics_router = APIRouter(prefix="/analytics", tags=["Analytics"])


@analytics_router.get(
    "/summary", response_model=AnalyticsSummary, summary="Overall Task Execution Metrics"
)
async def get_analytics_summary() -> AnalyticsSummary:
    """Return high-level summary of total tasks, success rate, durations, and budget."""
    return await task_analytics_service.get_summary()


@analytics_router.get(
    "/types", response_model=list[TypePerformance], summary="Performance by Project Category"
)
async def get_analytics_by_type() -> list[TypePerformance]:
    """Return performance and duration metrics segmented by project archetype."""
    return await task_analytics_service.get_type_performance()


@analytics_router.get(
    "/failures", response_model=FailureAnalysis, summary="Failure Root Cause Analysis"
)
async def get_analytics_failures() -> FailureAnalysis:
    """Return breakdown and frequency distribution of failure reasons."""
    return await task_analytics_service.get_failure_analysis()
