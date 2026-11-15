"""Operations alerting & monitoring REST endpoints (TASK-SEN-008).

Mounts the operations modules in the live API (previously unreachable):
- Alert feed + operator lifecycle (acknowledge / resolve) for the
  operations AlertEngine, whose alerts now dispatch to the shared human
  channel (see sentinel.modules.operations.dispatch).
- Scheduler job registry for the operations AssessmentScheduler, whose
  run loop is started by the API lifespan.
- Aggregated operations dashboard metrics.
- A drill endpoint that fires ONE synthetic operations alert through the
  real path (engine -> dispatcher -> channel) for verification; resolve
  the returned alert id afterwards to clean up the drill artifact.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sentinel.core.models import SeverityLevel
from sentinel.modules.operations.alerting import alert_engine
from sentinel.modules.operations.baseline import BaselineDelta, ChangeType
from sentinel.modules.operations.dashboard import dashboard_aggregator
from sentinel.modules.operations.scheduler import assessment_scheduler

operations_router = APIRouter(prefix="/operations", tags=["Operations Alerting"])


class AcknowledgeRequest(BaseModel):
    operator: str = "operator"


class DrillRequest(BaseModel):
    target_ref: str = "sen008-drill"
    severity: SeverityLevel = SeverityLevel.HIGH
    description: str | None = None


@operations_router.get("/alerts")
async def list_operations_alerts() -> dict[str, Any]:
    alerts = alert_engine.list_alerts()
    return {"alerts": [a.model_dump(mode="json") for a in alerts], "count": len(alerts)}


@operations_router.get("/alerts/{alert_id}")
async def get_operations_alert(alert_id: str) -> dict[str, Any]:
    for alert in alert_engine.list_alerts():
        if alert.alert_id == alert_id:
            return alert.model_dump(mode="json")
    raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")


@operations_router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_operations_alert(alert_id: str, request: AcknowledgeRequest) -> dict[str, Any]:
    try:
        alert = alert_engine.acknowledge_alert(alert_id, operator=request.operator)
    except KeyError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    return alert.model_dump(mode="json")


@operations_router.post("/alerts/{alert_id}/resolve")
async def resolve_operations_alert(alert_id: str) -> dict[str, Any]:
    try:
        alert = alert_engine.resolve_alert(alert_id)
    except KeyError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    return alert.model_dump(mode="json")


@operations_router.get("/jobs")
async def list_operations_jobs() -> dict[str, Any]:
    jobs = assessment_scheduler.list_jobs()
    return {
        "jobs": [j.model_dump(mode="json") for j in jobs],
        "count": len(jobs),
        "scheduler_running": assessment_scheduler.is_running,
    }


@operations_router.get("/dashboard")
async def get_operations_dashboard() -> dict[str, Any]:
    return dashboard_aggregator.get_operational_metrics().model_dump(mode="json")


@operations_router.post("/drill")
async def fire_operations_drill(request: DrillRequest) -> dict[str, Any]:
    """Fire ONE synthetic operations alert through the real dispatch path.

    The alert is created by the AlertEngine from a synthetic baseline delta
    (unique per call, so deduplication never suppresses a drill) and is
    dispatched by whatever dispatcher the lifespan wired in — in production
    that is the shared human channel. Clean up afterwards with
    POST /operations/alerts/{alert_id}/resolve.
    """
    nonce = secrets.token_hex(4)
    description = request.description or (
        f"TASK-SEN-008 synthetic operations drill alert "
        f"({datetime.now(UTC).isoformat()}, nonce {nonce}) — no real incident; "
        f"resolve this alert after verifying delivery."
    )
    delta = BaselineDelta(
        delta_id=f"delta-drill-{nonce}",
        target_ref=request.target_ref,
        change_type=ChangeType.NEW_FINDING,
        severity=request.severity,
        description=description,
    )
    alert = alert_engine.process_delta(delta)
    return {
        "alert": alert.model_dump(mode="json"),
        "dispatched": alert.dispatched,
        "dispatch_channels": alert.dispatch_channels,
        "dispatch_queued": alert.dispatch_queued,
        "cleanup": f"POST /operations/alerts/{alert.alert_id}/resolve",
    }
