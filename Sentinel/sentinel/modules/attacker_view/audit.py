"""Attacker-view self-audit engine (TASK-IG-SEN-01).

Runs four defensive, read-only checks against the owner's OWN fleet and
devices, then reports findings through the shared operations AlertEngine
(the SEN-006/SEN-008 dispatch channel) as BaselineDeltas — this module
creates no alert path of its own.

Checks:
1. Service exposure — a non-public port answering on a fleet host is the
   exact failure SEN-002 F-01 found by hand (FRIDAY :10000 public). The
   hardening arc (SEN-015/016/017) closed the known cases; this audit is
   the recurring automated check that they stay closed.
2. Auth posture — an endpoint that must require auth answering an
   unauthenticated GET with 200 is a login-bypass / auth-misconfiguration
   surface (corpus item DWWlMNyCA2O).
3. Camera exposure — an owner camera whose snapshot endpoint answers
   unauthenticated is "left open, not hacked" (corpus item DVYxqjPE5km).
4. Wi-Fi posture — observed AP configurations are assessed by the
   EXISTING WirelessConfigAssessmentAdapter (wireless rules WIFI-001..003,
   incl. the WPS rule from corpus item DXb4CpmDBcx); nothing is
   re-implemented here.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable
from urllib.parse import urlparse

from sentinel.core.models import ActionRequest, SeverityLevel
from sentinel.modules.attacker_view.models import (
    AuditConfig,
    AuditFinding,
    AuditReport,
    CameraTarget,
    HttpTarget,
    ServiceTarget,
    WifiObservation,
)
from sentinel.modules.attacker_view.probes import HttpResponse, http_get, tcp_connect
from sentinel.modules.operations.baseline import BaselineDelta, ChangeType
from sentinel.modules.wireless.adapters import WirelessConfigAssessmentAdapter

_SEVERITY_BY_NAME = {
    "INFO": SeverityLevel.INFO,
    "LOW": SeverityLevel.LOW,
    "MEDIUM": SeverityLevel.MEDIUM,
    "HIGH": SeverityLevel.HIGH,
    "CRITICAL": SeverityLevel.CRITICAL,
}


class AttackerViewAudit:
    """Coordinates the four attacker-view checks over an AuditConfig."""

    def __init__(
        self,
        tcp_probe: Callable[[str, int], bool] = tcp_connect,
        http_probe: Callable[[str], HttpResponse | None] = http_get,
        wifi_adapter: WirelessConfigAssessmentAdapter | None = None,
    ):
        self._tcp = tcp_probe
        self._http = http_probe
        self._wifi = wifi_adapter or WirelessConfigAssessmentAdapter()

    # -- allowlist ------------------------------------------------------

    @staticmethod
    def _allowed(config: AuditConfig, host: str) -> bool:
        return host in config.allowed_hosts

    # -- individual checks ----------------------------------------------

    def check_service_exposure(
        self, config: AuditConfig, report: AuditReport
    ) -> None:
        for svc in config.services:
            ref = f"{svc.host}:{svc.port}"
            if not self._allowed(config, svc.host):
                report.refused_targets.append(ref)
                continue
            report.checks_run.append(f"tcp_connect {ref}")
            reachable = self._tcp(svc.host, svc.port)
            label = svc.label or ref
            if reachable and not svc.expect_public:
                report.findings.append(
                    AuditFinding(
                        rule_id="AV-EXP-001",
                        title="Non-public service answering on fleet host",
                        severity=SeverityLevel.HIGH,
                        target_ref=ref,
                        description=(
                            f"{label} answers TCP connections on {ref} but is "
                            "not part of the documented public surface "
                            "(22/80/443, SEN-016 end-state). An attacker "
                            "scanning the host sees this service directly, "
                            "bypassing the Caddy TLS front door."
                        ),
                        remediation=(
                            "Bind the service to loopback/VPC only or remove "
                            "the public ingress rule, per SEN-015/016."
                        ),
                        evidence=f"tcp_connect({ref}) -> open",
                    )
                )
            elif not reachable and svc.expect_public:
                report.unreachable_targets.append(ref)
                report.findings.append(
                    AuditFinding(
                        rule_id="AV-EXP-002",
                        title="Documented public service unreachable",
                        severity=SeverityLevel.INFO,
                        target_ref=ref,
                        description=(
                            f"{label} is part of the documented public "
                            f"surface but did not answer on {ref} during "
                            "this audit. Availability note, not an exposure."
                        ),
                        remediation="Verify the service and its ingress rule.",
                        evidence=f"tcp_connect({ref}) -> closed/filtered",
                    )
                )

    def check_auth_posture(self, config: AuditConfig, report: AuditReport) -> None:
        for target in config.http_targets:
            host = urlparse(target.url).hostname or ""
            if not self._allowed(config, host):
                report.refused_targets.append(target.url)
                continue
            report.checks_run.append(f"http_get {target.url}")
            resp = self._http(target.url)
            if resp is None:
                report.unreachable_targets.append(target.url)
                continue
            if target.auth_required and resp.status == 200:
                report.findings.append(
                    AuditFinding(
                        rule_id="AV-AUTH-001",
                        title="Endpoint answers without authentication",
                        severity=SeverityLevel.HIGH,
                        target_ref=target.url,
                        description=(
                            f"{target.label or target.url} returned HTTP 200 "
                            "to an unauthenticated GET although the endpoint "
                            "is expected to require authentication. This is "
                            "the login-bypass / auth-misconfiguration surface: "
                            "whatever this endpoint serves is public."
                        ),
                        remediation=(
                            "Enforce authentication on the endpoint or "
                            "document it as intentionally public."
                        ),
                        evidence=f"GET {target.url} -> 200 (no credentials sent)",
                    )
                )

    def check_camera_exposure(
        self, config: AuditConfig, report: AuditReport
    ) -> None:
        for cam in config.cameras:
            ref = f"{cam.host}:{cam.port}"
            if not self._allowed(config, cam.host):
                report.refused_targets.append(ref)
                continue
            url = f"http://{cam.host}:{cam.port}{cam.snapshot_path}"
            report.checks_run.append(f"http_get {url}")
            resp = self._http(url)
            if resp is None:
                report.unreachable_targets.append(ref)
                continue
            label = cam.label or ref
            if resp.status == 200 and resp.content_type.startswith("image/"):
                report.findings.append(
                    AuditFinding(
                        rule_id="AV-CAM-001",
                        title="Camera snapshot exposed without authentication",
                        severity=SeverityLevel.CRITICAL,
                        target_ref=ref,
                        description=(
                            f"Camera {label} served a snapshot image at "
                            f"{url} to an unauthenticated request. Exposed "
                            "cameras are almost never hacked — they are left "
                            "open exactly like this."
                        ),
                        remediation=(
                            "Require authentication on the camera, move it "
                            "behind the VPN/VPC, and rotate its credentials."
                        ),
                        evidence=f"GET {url} -> 200 {resp.content_type}",
                    )
                )
            elif resp.status == 200:
                report.findings.append(
                    AuditFinding(
                        rule_id="AV-CAM-002",
                        title="Camera endpoint answers without authentication",
                        severity=SeverityLevel.MEDIUM,
                        target_ref=ref,
                        description=(
                            f"Camera {label} answered an unauthenticated "
                            f"request at {url} with HTTP 200 (non-image "
                            "response). The device interface is reachable "
                            "without credentials."
                        ),
                        remediation=(
                            "Require authentication on the device interface "
                            "and restrict it to the local network/VPN."
                        ),
                        evidence=f"GET {url} -> 200 {resp.content_type}",
                    )
                )

    async def check_wifi_posture(
        self, config: AuditConfig, report: AuditReport
    ) -> None:
        """Assess observed APs via the existing wireless adapter."""
        for obs in config.wifi:
            report.checks_run.append(f"wifi_assess {obs.ssid}")
            request = ActionRequest(
                id=f"ig-sen-01-{uuid.uuid4().hex[:12]}",
                task_id="task-ig-sen-01",
                agent="sentinel",
                action_type="wireless.config_audit",
                parameters={
                    "config_data": {
                        "security_mode": obs.security_mode,
                        "wps_enabled": obs.wps_enabled,
                        "management_on_wireless": obs.management_on_wireless,
                    }
                },
                target_refs=[obs.ssid],
            )
            _result, raw, _mime = await self._wifi.run(request)
            data = json.loads(raw.decode("utf-8"))
            for item in data.get("findings", []):
                report.findings.append(
                    AuditFinding(
                        rule_id=item.get("rule_id", "WIFI-000"),
                        title=item.get("title", "Wireless posture issue"),
                        severity=_SEVERITY_BY_NAME.get(
                            str(item.get("severity", "MEDIUM")).upper(),
                            SeverityLevel.MEDIUM,
                        ),
                        target_ref=f"wifi:{obs.ssid}",
                        description=item.get("description", ""),
                        remediation=item.get("remediation", ""),
                        evidence=f"wireless_config_assessment ssid={obs.ssid}",
                    )
                )

    # -- orchestration ----------------------------------------------------

    async def run(self, config: AuditConfig) -> AuditReport:
        report = AuditReport(target_ref=config.target_ref)
        self.check_service_exposure(config, report)
        self.check_auth_posture(config, report)
        self.check_camera_exposure(config, report)
        await self.check_wifi_posture(config, report)
        return report

    @staticmethod
    def emit_alerts(report: AuditReport, engine: Any) -> list[Any]:
        """Feed every finding into the shared operations AlertEngine.

        ``engine`` is the operations AlertEngine (the SEN-006/SEN-008
        dispatch channel). Findings become BaselineDeltas of type
        NEW_FINDING; the engine's fingerprint dedupe applies unchanged.
        """
        alerts = []
        for idx, finding in enumerate(report.findings):
            delta = BaselineDelta(
                delta_id=f"igsen01-{report.target_ref}-{finding.rule_id}-{idx}",
                target_ref=finding.target_ref,
                change_type=ChangeType.NEW_FINDING,
                severity=finding.severity,
                description=(
                    f"[{finding.rule_id}] {finding.title} — "
                    f"{finding.description} Remediation: {finding.remediation}"
                ),
                new_state={"evidence": finding.evidence},
            )
            alerts.append(engine.process_delta(delta))
        return alerts


# ---------------------------------------------------------------------------
# Default fleet configuration (documented surface from SEN-013/015/016/017)
# ---------------------------------------------------------------------------

#: Agent ports that must never answer on a public host (AGENTS.md layout).
FLEET_AGENT_PORTS: dict[int, str] = {
    10000: "FRIDAY",
    8001: "Inference",
    8002: "Memora",
    8003: "Stratex",
    8004: "Futuris",
    8005: "IntelX",
    8006: "Forge",
    8008: "Sentinel",
    8009: "Cortex",
    8010: "VyralX",
    8011: "Bridge",
}

#: The documented public surface after the SEN-015/016/017 hardening arc.
PUBLIC_PORTS: dict[int, str] = {22: "SSH", 80: "HTTP (Caddy)", 443: "HTTPS (Caddy)"}


def default_fleet_config(server1_public: str, server2_public: str) -> AuditConfig:
    """Audit config for the two production hosts' PUBLIC interfaces.

    Only the documented public surface may answer publicly; every agent
    port answering on a public IP is AV-EXP-001. Both hosts are placed on
    the allowlist by construction — any other host is refused.
    """
    services: list[ServiceTarget] = []
    for host in (server1_public, server2_public):
        for port, label in PUBLIC_PORTS.items():
            services.append(
                ServiceTarget(host=host, port=port, label=label, expect_public=True)
            )
        for port, label in FLEET_AGENT_PORTS.items():
            services.append(
                ServiceTarget(host=host, port=port, label=label, expect_public=False)
            )
    return AuditConfig(
        allowed_hosts=[server1_public, server2_public],
        target_ref="fleet-public-surface",
        services=services,
    )
