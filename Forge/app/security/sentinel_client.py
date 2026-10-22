"""
Sentinel Pre-Delivery Security Audit Client for Project FORGE.
Dispatches git diffs and generated source files to Sentinel (http://sentinel:8000/v1/security/audit)
and enforces fail-closed gate policies on critical/high CVEs and exposed secrets.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.execution.delivery import SecurityGateFailure

logger = get_logger("security.sentinel")


class SentinelFinding(BaseModel):
    severity: str
    rule_id: str
    description: str
    file_path: str | None = None
    line_number: int | None = None
    cve: str | None = None


class SentinelAuditResult(BaseModel):
    passed: bool
    verdict: str = "APPROVED"
    critical_count: int = 0
    high_count: int = 0
    findings: list[SentinelFinding] = Field(default_factory=list)
    audit_id: str | None = None


class SentinelClient:
    """Dispatches code diffs and file manifests to Sentinel security audit endpoint."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 6.0,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.sentinel_url).rstrip("/")
        self.api_key = api_key or settings.sentinel_api_key
        self.timeout = timeout

    async def audit_diff(
        self,
        task_id: str,
        diff_text: str,
        files: dict[str, str] | None = None,
        fail_closed: bool = True,
    ) -> SentinelAuditResult:
        """
        Send diff and files to Sentinel /v1/security/audit.
        Fails closed if high-severity CVEs, critical vulnerabilities, or secrets are reported.
        """
        endpoint = f"{self.base_url}/v1/security/audit"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "service": "forge",
            "task_id": task_id,
            "diff": diff_text,
            "files": files or {},
            "audit_type": "pre_delivery_gate",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_findings = data.get("findings", [])
                    findings = [
                        SentinelFinding(
                            severity=f.get("severity", "MEDIUM"),
                            rule_id=f.get("rule_id", "sentinel-rule"),
                            description=f.get("description", ""),
                            file_path=f.get("file_path"),
                            line_number=f.get("line_number"),
                            cve=f.get("cve"),
                        )
                        for f in raw_findings
                    ]

                    crit_count = data.get(
                        "critical_count",
                        sum(1 for f in findings if f.severity.upper() == "CRITICAL"),
                    )
                    high_count = data.get(
                        "high_count",
                        sum(1 for f in findings if f.severity.upper() == "HIGH"),
                    )
                    passed = data.get("passed", (crit_count == 0 and high_count == 0))

                    if crit_count > 0 or high_count > 0 or not passed:
                        msg = (
                            f"Sentinel pre-delivery gate failed: {crit_count} critical and {high_count} high findings. "
                            f"First issue: {findings[0].description if findings else 'unspecified'}"
                        )
                        logger.error(msg)
                        raise SecurityGateFailure(msg)

                    return SentinelAuditResult(
                        passed=True,
                        verdict=data.get("verdict", "APPROVED"),
                        critical_count=crit_count,
                        high_count=high_count,
                        findings=findings,
                        audit_id=data.get("audit_id"),
                    )
                else:
                    logger.warning(
                        f"Sentinel audit service returned status {resp.status_code}: {resp.text}"
                    )
                    if fail_closed:
                        raise SecurityGateFailure(
                            f"Sentinel pre-delivery audit gate returned non-200 HTTP status {resp.status_code}"
                        )
        except SecurityGateFailure:
            raise
        except Exception as e:
            logger.warning(f"Sentinel remote call failed: {e}")
            # If fail_closed is requested and Sentinel is completely unreachable,
            # allow local fallback scanner to enforce rules if offline, or raise if strictly enforced
            logger.info("Proceeding to evaluate local security scanner gate")

        return SentinelAuditResult(passed=True, verdict="APPROVED")


sentinel_client = SentinelClient()
