"""
Health, Readiness, Diagnostics, and Prometheus Metrics Endpoints for Project FORGE.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.integrations.ai_universe_deep import deep_ai_universe
from app.memory.db import db_manager, ping_statement
from app.monitoring.production_monitor import AlertStatus, production_monitor

health_router = APIRouter(tags=["Health & Monitoring"])
logger = logging.getLogger(__name__)


def _observed_at() -> str:
    """Single source for the instant a probe answered, reused by every evidence field."""
    return datetime.now(timezone.utc).isoformat()


class LivenessResponse(BaseModel):
    status: str = "ok"
    service: str = "forge"
    version: str = "0.1.0"
    uptime_seconds: float
    database_connected: bool
    evidence_class: str = "process_liveness"
    observed_at: str = Field(default_factory=_observed_at)


class ReadinessResponse(BaseModel):
    status: str = "ready"
    service: str = "forge"
    version: str = "0.1.0"
    database_connected: bool = True
    database: str = "connected"
    database_backend: str = "unconfigured"
    workspaces_writable: bool = True
    evidence_class: str = "dependency_readiness"
    observed_at: str = Field(default_factory=_observed_at)


class DiagnosticResponse(BaseModel):
    status: str = "healthy"
    service: str = "forge"
    version: str = "0.1.0"
    environment: str = "development"
    database: dict[str, Any]
    ai_universe: dict[str, Any]
    intelx: dict[str, Any] = Field(default_factory=dict)
    system_metrics: dict[str, Any]
    security_scanner: dict[str, Any] = Field(default_factory=dict)
    alerts: AlertStatus


@health_router.api_route(
    "/health", methods=["GET", "HEAD"], response_model=LivenessResponse, summary="Liveness Probe"
)
async def health_liveness():
    """Report process liveness and an observed database connectivity check."""
    settings = get_settings()
    sys_m = production_monitor.get_system_metrics()
    db_ok = False
    try:
        async with db_manager.connection() as conn:
            # Oracle needs "SELECT 1 FROM DUAL"; resolved after connecting.
            cursor = await conn.execute(ping_statement(db_manager))
            row = await cursor.fetchone()
            db_ok = row is not None and next(iter(row.values()), None) == 1
    except Exception:
        # Keep liveness independent from database health: callers still receive
        # the process status, while readiness reports whether it can serve work.
        logger.warning("Forge liveness database probe failed", exc_info=True)
        db_ok = False
    return LivenessResponse(
        status="ok",
        service="forge",
        version=settings.app_version,
        uptime_seconds=sys_m["uptime_seconds"],
        database_connected=db_ok,
        evidence_class="process_liveness",
        observed_at=_observed_at(),
    )


@health_router.api_route(
    "/health/ready",
    methods=["GET", "HEAD"],
    response_model=ReadinessResponse,
    summary="Readiness Probe",
)
@health_router.api_route(
    "/ready",
    methods=["GET", "HEAD"],
    response_model=ReadinessResponse,
    summary="Readiness Probe Alias",
    include_in_schema=False,
)
async def health_readiness():
    """Readiness probe checking database connectivity and workspace filesystem write access."""
    db_ok = False
    ws_ok = False

    try:
        async with db_manager.connection() as conn:
            cursor = await conn.execute(ping_statement(db_manager))
            row = await cursor.fetchone()
            db_ok = row is not None and next(iter(row.values()), None) == 1
    except Exception:
        logger.warning("Forge readiness database probe failed", exc_info=True)
        db_ok = False

    settings = get_settings()
    try:
        ws_dir = (
            settings.base_dir / settings.workspaces_dir
            if not settings.workspaces_dir.is_absolute()
            else settings.workspaces_dir
        )
        ws_dir.mkdir(parents=True, exist_ok=True)
        test_file = ws_dir / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        ws_ok = True
    except Exception:
        logger.warning("Forge readiness workspace probe failed for %s", settings.workspaces_dir, exc_info=True)
        ws_ok = False

    # Read database backend from the SQLAlchemy engine (via DatabaseManager)
    db_backend = getattr(db_manager, "dialect_name", "unconfigured")
    if not db_backend or db_backend == "unconfigured":
        engine = getattr(db_manager, "_async_engine", None)
        if engine is not None and hasattr(engine, "dialect"):
            db_backend = str(getattr(engine.dialect, "name", "unconfigured"))
        else:
            url = getattr(db_manager, "get_effective_url", lambda: "")()
            db_backend_lower = url.lower()
            if "oracle" in db_backend_lower:
                db_backend = "oracle"
            elif "postgresql" in db_backend_lower or "+asyncpg" in db_backend_lower:
                db_backend = "postgresql"
            else:
                db_backend = "sqlite"

    if not db_ok or not ws_ok:
        observed_at = _observed_at()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "service": "forge",
                "database_connected": db_ok,
                "database": "connected" if db_ok else "unavailable",
                "database_backend": db_backend,
                "workspaces_writable": ws_ok,
                "evidence_class": "dependency_readiness",
                "observed_at": observed_at,
            },
        )

    # Keep production readiness semantics: non-Oracle backend in production = 503
    is_prod = getattr(settings, "APP_ENV", "development").lower() == "production"
    if is_prod and db_backend != "oracle" and (db_ok and ws_ok):
        observed_at = _observed_at()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "service": "forge",
                "database_connected": db_ok,
                "database": "connected" if db_ok else "unavailable",
                "database_backend": db_backend,
                "workspaces_writable": ws_ok,
                "evidence_class": "dependency_readiness",
                "observed_at": observed_at,
                "message": f"Production requires Oracle backend; got {db_backend}",
            },
        )

    return ReadinessResponse(
        status="ready",
        service="forge",
        version=settings.app_version,
        database_connected=db_ok,
        database="connected" if db_ok else "unavailable",
        database_backend=db_backend,
        workspaces_writable=ws_ok,
        observed_at=_observed_at(),
    )


@health_router.get(
    "/health/detailed", response_model=DiagnosticResponse, summary="Detailed Diagnostics"
)
@health_router.get(
    "/status", response_model=DiagnosticResponse, summary="Detailed Diagnostics Alias", include_in_schema=False
)
async def health_detailed():
    """Comprehensive diagnostic diagnostics across storage, AI-Universe, and system resources."""
    settings = get_settings()

    # DB Health & Latency
    db_start = time.time()
    db_ok = True
    try:
        async with db_manager.connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM tasks")
            row = await cursor.fetchone()
            task_count = row[0] if row else 0
    except Exception:
        db_ok = False
        task_count = 0
    db_latency_ms = round((time.time() - db_start) * 1000.0, 2)

    # AI-Universe Health
    aiu_ok = deep_ai_universe.check_health()

    sys_m = production_monitor.get_system_metrics()
    alerts = production_monitor.check_alerts()

    overall_status = "healthy"
    if alerts.has_active_alerts:
        overall_status = "degraded"
    if not db_ok:
        overall_status = "unhealthy"

    from app.verification.security_scanner import CVE_VULNERABILITY_DB

    return DiagnosticResponse(
        status=overall_status,
        service="forge",
        version=settings.app_version,
        environment=settings.env,
        database={
            "connected": db_ok,
            "latency_ms": db_latency_ms,
            "total_tasks_recorded": task_count,
        },
        ai_universe={
            "healthy": aiu_ok,
            "url": settings.ai_universe_url,
        },
        intelx={
            "url": getattr(settings, "intelx_url", "http://localhost:8002"),
            "research_queries_total": production_monitor.intelx_research_queries_total,
            "research_informed_builds_total": production_monitor.research_informed_builds_total,
        },
        system_metrics=sys_m,
        security_scanner={
            "active": True,
            "cve_database_entries": len(CVE_VULNERABILITY_DB),
            "scans_total": production_monitor.security_scans_total,
            "scans_passed": production_monitor.security_scans_passed,
            "scans_blocked": production_monitor.security_scans_blocked,
            "findings_detected_total": production_monitor.security_findings_total,
        },
        alerts=alerts,
    )


@health_router.get("/metrics", summary="Prometheus Metrics Exporter")
async def get_metrics():
    """Expose Prometheus-compatible metrics for scraping."""
    metrics_text = production_monitor.export_prometheus_metrics()
    return Response(content=metrics_text, media_type="text/plain; version=0.0.4")
