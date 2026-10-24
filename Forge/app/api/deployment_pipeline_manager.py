"""
Forge/app/api/deployment_pipeline_manager.py — Forge Deployment Pipeline Manager.

Manages deployment pipelines: build orchestration, environment promotion,
rollback management, deployment validation, and release coordination.
Provides CI/CD automation with safety checks and approval workflows.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class PipelineConfig:
    """Deployment pipeline configuration."""
    config_id: str
    name: str
    project_id: str
    stages: list[str] = field(default_factory=lambda: ["build", "test", "staging", "production"])
    auto_deploy_staging: bool = True
    auto_deploy_production: bool = False
    require_approval: bool = True
    rollback_enabled: bool = True
    max_rollback_attempts: int = 3
    created_at: float = 0.0


@dataclass
class DeploymentStage:
    """A deployment stage."""
    stage_id: str
    pipeline_id: str
    stage_name: str
    status: str = "pending"  # pending, running, passed, failed, skipped
    started_at: float = 0.0
    completed_at: float = 0.0
    artifact_url: str = ""
    duration_ms: float = 0.0
    checks: list[str] = field(default_factory=list)


@dataclass
class DeploymentRecord:
    """A deployment record."""
    deployment_id: str
    pipeline_id: str
    environment: str
    version: str
    status: str = "pending"  # pending, deploying, deployed, failed, rolled_back
    started_at: float = 0.0
    completed_at: float = 0.0
    deployed_by: str = ""
    approval: str = "pending"  # pending, approved, rejected
    rollback_available: bool = False


@dataclass
class RollbackRecord:
    """A rollback record."""
    rollback_id: str
    deployment_id: str
    from_version: str
    to_version: str
    status: str = "pending"  # pending, rolling_back, completed, failed
    reason: str = ""
    initiated_by: str = ""
    initiated_at: float = 0.0


@dataclass
class ApprovalRequest:
    """An approval request for deployment."""
    approval_id: str
    deployment_id: str
    requested_by: str
    approver: str = ""
    status: str = "pending"  # pending, approved, rejected
    reason: str = ""
    requested_at: float = 0.0
    resolved_at: float = 0.0


@dataclass
class DeploymentMetrics:
    """Deployment metrics."""
    pipeline_id: str
    total_deployments: int = 0
    successful_deployments: int = 0
    failed_deployments: int = 0
    avg_deployment_time_min: float = 0.0
    avg_rollback_time_min: float = 0.0
    deployment_frequency: str = ""  # daily, weekly, monthly
    change_failure_rate: float = 0.0
    lead_time_minutes: float = 0.0


class DeploymentPipelineManager:
    """Deployment pipeline management engine."""

    def __init__(self):
        self._configs: dict[str, PipelineConfig] = {}
        self._stages: dict[str, DeploymentStage] = {}
        self._deployments: dict[str, DeploymentRecord] = {}
        self._rollbacks: list[RollbackRecord] = []
        self._approvals: list[ApprovalRequest] = []
        self._metrics: dict[str, DeploymentMetrics] = {}

    def create_config(self, name: str, project_id: str, auto_prod: bool = False) -> PipelineConfig:
        """Create a pipeline configuration."""
        config = PipelineConfig(
            config_id=hashlib.md5(
                f"config:{name}:{time.time()}".encode()
            ).hexdigest()[:12],
            name=name,
            project_id=project_id,
            auto_deploy_staging=True,
            auto_deploy_production=auto_prod,
            require_approval=not auto_prod,
            created_at=time.time(),
        )
        self._configs[config.config_id] = config
        return config

    def create_deployment(self, pipeline_id: str, environment: str, version: str, deployed_by: str = "") -> DeploymentRecord:
        """Create a deployment record."""
        deploy = DeploymentRecord(
            deployment_id=hashlib.md5(
                f"deploy:{pipeline_id}:{version}:{time.time()}".encode()
            ).hexdigest()[:12],
            pipeline_id=pipeline_id,
            environment=environment,
            version=version,
            status="pending",
            started_at=time.time(),
            deployed_by=deployed_by,
            approval="pending",
        )

        self._deployments[deploy.deployment_id] = deploy

        # Create approval request for production
        if environment == "production":
            approval = ApprovalRequest(
                approval_id=hashlib.md5(
                    f"approval:{deploy.deployment_id}:{time.time()}".encode()
                ).hexdigest()[:12],
                deployment_id=deploy.deployment_id,
                requested_by=deployed_by,
                status="pending",
                requested_at=time.time(),
            )
            self._approvals.append(approval)

        return deploy

    def approve_deployment(self, deployment_id: str, approver: str, approved: bool, reason: str = "") -> ApprovalRequest:
        """Approve or reject a deployment."""
        approval = None
        for a in self._approvals:
            if a.deployment_id == deployment_id and a.status == "pending":
                approval = a
                break

        if not approval:
            raise HTTPException(404, f"No pending approval for {deployment_id}")

        approval.approver = approver
        approval.status = "approved" if approved else "rejected"
        approval.reason = reason
        approval.resolved_at = time.time()

        deploy = self._deployments.get(deployment_id)
        if deploy:
            if approved:
                deploy.approval = "approved"
                deploy.status = "deploying"
            else:
                deploy.approval = "rejected"
                deploy.status = "failed"

        return approval

    def run_stage(self, stage_id: str) -> DeploymentStage:
        """Run a deployment stage."""
        stage = self._stages.get(stage_id)
        if not stage:
            raise HTTPException(404, f"Stage {stage_id} not found")

        stage.status = "running"
        stage.started_at = time.time()

        # Simulate stage execution
        time.sleep(0.1)  # Simulated work

        # Run checks
        stage.checks = ["security_scan", "unit_tests", "integration_tests", "performance_check"]

        stage.status = "passed"
        stage.completed_at = time.time()
        stage.duration_ms = (stage.completed_at - stage.started_at) * 1000
        stage.artifact_url = f"https://artifacts.example.com/{stage_id}/artifact.tar.gz"

        return stage

    def complete_deployment(self, deployment_id: str) -> DeploymentRecord:
        """Mark a deployment as complete."""
        deploy = self._deployments.get(deployment_id)
        if not deploy:
            raise HTTPException(404, f"Deployment {deployment_id} not found")

        deploy.status = "deployed"
        deploy.completed_at = time.time()
        deploy.rollback_available = True

        # Update metrics
        metrics = self._metrics.get(deploy.pipeline_id)
        if not metrics:
            metrics = DeploymentMetrics(pipeline_id=deploy.pipeline_id)
            self._metrics[deploy.pipeline_id] = metrics

        metrics.total_deployments += 1
        metrics.successful_deployments += 1
        deployment_time = (deploy.completed_at - deploy.started_at) / 60
        metrics.avg_deployment_time_min = (metrics.avg_deployment_time_min * 0.9 + deployment_time * 0.1)
        metrics.change_failure_rate = metrics.failed_deployments / max(1, metrics.total_deployments)

        return deploy

    def initiate_rollback(self, deployment_id: str, reason: str, initiated_by: str) -> RollbackRecord:
        """Initiate a rollback."""
        deploy = self._deployments.get(deployment_id)
        if not deploy:
            raise HTTPException(404, f"Deployment {deployment_id} not found")

        if not deploy.rollback_available:
            raise HTTPException(400, "Rollback not available for this deployment")

        rollback = RollbackRecord(
            rollback_id=hashlib.md5(
                f"rollback:{deployment_id}:{time.time()}".encode()
            ).hexdigest()[:12],
            deployment_id=deployment_id,
            from_version=deploy.version,
            to_version="previous_stable",
            status="rolling_back",
            reason=reason,
            initiated_by=initiated_by,
            initiated_at=time.time(),
        )

        self._rollbacks.append(rollback)

        # Mark deployment as rolled back
        deploy.status = "rolled_back"

        # Update metrics
        metrics = self._metrics.get(deploy.pipeline_id)
        if metrics:
            metrics.failed_deployments += 1
            metrics.change_failure_rate = metrics.failed_deployments / max(1, metrics.total_deployments)

        return rollback

    def get_metrics(self, pipeline_id: str) -> DeploymentMetrics:
        """Get deployment metrics."""
        metrics = self._metrics.get(pipeline_id)
        if not metrics:
            metrics = DeploymentMetrics(pipeline_id=pipeline_id)
            self._metrics[pipeline_id] = metrics
        return metrics

    def get_report(self) -> dict:
        """Get deployment pipeline manager report."""
        return {
            "total_configs": len(self._configs),
            "total_stages": len(self._stages),
            "total_deployments": len(self._deployments),
            "total_rollbacks": len(self._rollbacks),
            "total_approvals": len(self._approvals),
            "total_metrics": len(self._metrics),
            "deployed": sum(1 for d in self._deployments.values() if d.status == "deployed"),
            "failed": sum(1 for d in self._deployments.values() if d.status == "failed"),
            "rolled_back": sum(1 for d in self._deployments.values() if d.status == "rolled_back"),
            "pending_approvals": sum(1 for a in self._approvals if a.status == "pending"),
            "recent_deployments": [
                {"environment": d.environment, "version": d.version, "status": d.status, "approval": d.approval}
                for d in list(self._deployments.values())[-10:]
            ],
            "recent_rollbacks": [
                {"from": r.from_version, "to": r.to_version, "reason": r.reason[:60], "status": r.status}
                for r in self._rollbacks[-5:]
            ],
            "metrics_summary": [
                {
                    "pipeline": m.pipeline_id,
                    "total": m.total_deployments,
                    "success_rate": m.successful_deployments / max(1, m.total_deployments),
                    "avg_deploy_time_min": round(m.avg_deployment_time_min, 1),
                    "change_failure_rate": round(m.change_failure_rate, 3),
                }
                for m in self._metrics.values()
            ],
        }


deployment_manager = DeploymentPipelineManager()


@router.post("/api/v1/forge/deployment/configs")
async def create_config(payload: dict):
    """Create a pipeline configuration."""
    config = deployment_manager.create_config(
        name=payload["name"],
        project_id=payload["project_id"],
        auto_prod=payload.get("auto_prod", False),
    )
    return {"config_id": config.config_id, "name": config.name, "stages": config.stages}


@router.post("/api/v1/forge/deployment/deployments")
async def create_deployment(payload: dict):
    """Create a deployment."""
    deploy = deployment_manager.create_deployment(
        pipeline_id=payload["pipeline_id"],
        environment=payload["environment"],
        version=payload["version"],
        deployed_by=payload.get("deployed_by", ""),
    )
    return {"deployment_id": deploy.deployment_id, "environment": deploy.environment, "version": deploy.version, "status": deploy.status}


@router.post("/api/v1/forge/deployment/deployments/{deploy_id}/approve")
async def approve_deployment(deploy_id: str, payload: dict):
    """Approve or reject a deployment."""
    approval = deployment_manager.approve_deployment(
        deployment_id=deploy_id,
        approver=payload["approver"],
        approved=payload["approved"],
        reason=payload.get("reason", ""),
    )
    return {"approval_id": approval.approval_id, "status": approval.status, "approver": approval.approver}


@router.post("/api/v1/forge/deployment/deployments/{deploy_id}/complete")
async def complete_deployment(deploy_id: str):
    """Complete a deployment."""
    deploy = deployment_manager.complete_deployment(deploy_id)
    return {"deployment_id": deploy.deployment_id, "status": deploy.status, "rollback_available": deploy.rollback_available}


@router.post("/api/v1/forge/deployment/deployments/{deploy_id}/rollback")
async def initiate_rollback(deploy_id: str, payload: dict):
    """Initiate a rollback."""
    rollback = deployment_manager.initiate_rollback(
        deployment_id=deploy_id,
        reason=payload["reason"],
        initiated_by=payload.get("initiated_by", ""),
    )
    return {"rollback_id": rollback.rollback_id, "from": rollback.from_version, "to": rollback.to_version, "status": rollback.status}


@router.get("/api/v1/forge/deployment/report")
async def get_report():
    """Get deployment pipeline manager report."""
    return deployment_manager.get_report()
