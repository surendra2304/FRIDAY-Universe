"""
Sentinel/app/services/fleet_audit_pipeline.py — Multi-role DEFENSIVE audit
pipeline for FRIDAY's own fleet.

TASK-IG2-SEN-02: adapts the specialised-agent role design of PentAGI
(researcher → planner → executor → reflector/memorist → report) to a
purely defensive audit of FRIDAY's own fleet. PentAGI itself is an
offensive penetration-testing platform (MIT, vxcontrol/pentagi); only its
role design transfers — NO offensive tooling, NO Docker sandbox stack, and
NO scanning of third parties. Every target must be in the fleet inventory;
anything else is refused with ``OutOfScopeError`` before any probe runs.

Roles
-----
- ``InventoryResearcher`` — builds the audit target list from the fleet
  inventory (hosts, agent services, expected ports, HTTP endpoints).
- ``CheckPlanner`` — turns targets into a plan of allowlisted defensive
  checks only: expected-port reachability, unexpected-port exposure on
  fleet hosts, TLS certificate hygiene on fleet endpoints, HTTP security
  headers, and agent /health status.
- ``CheckExecutor`` — runs the plan through injectable probes (connect-only
  TCP, TLS handshake metadata, HTTP GET of the fleet endpoint itself).
- ``FindingReflector`` — independently re-runs the probe behind every
  finding; a finding that does not reproduce is dropped from the report
  (kept in ``dropped`` with its reason). This is the owner's standing
  verification standard applied to security findings.
- ``AuditReporter`` — renders the verified findings as JSON-able dict and
  markdown.

Finding ids are deterministic (``host/service/check``) so runs can be
diffed against a baseline (see audit_baseline.py, TASK-IG2-SEN-03).
"""
from __future__ import annotations

import socket
import ssl
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

# Ports that should never be exposed on a fleet host. Checked ONLY on
# hosts in the fleet inventory.
UNEXPECTED_PORTS: dict[int, str] = {
    21: "FTP", 23: "Telnet", 3306: "MySQL", 5432: "PostgreSQL",
    6379: "Redis", 9200: "Elasticsearch", 27017: "MongoDB",
}

# HTTP security headers expected on fleet web endpoints.
EXPECTED_SECURITY_HEADERS: dict[str, str] = {
    "strict-transport-security": "HSTS",
    "x-content-type-options": "content-type sniffing protection",
    "x-frame-options": "clickjacking protection",
}

TLS_EXPIRY_ALERT_DAYS = 21
PROBE_TIMEOUT_S = 3.0


class OutOfScopeError(ValueError):
    """Raised when an audit target is not in the FRIDAY fleet inventory."""


@dataclass(frozen=True)
class FleetService:
    name: str          # agent name, e.g. "FRIDAY"
    port: int
    scheme: str = "http"   # scheme of the service's own endpoint


@dataclass(frozen=True)
class FleetHost:
    name: str          # e.g. "server-1"
    address: str       # fleet address (private or public fleet IP/hostname)
    services: tuple[FleetService, ...] = ()


def default_fleet_inventory() -> list[FleetHost]:
    """The FRIDAY fleet as documented in the repo's AGENTS.md (2026-10-26).

    Server 1: FRIDAY/Inference/Memora/Stratex/Futuris/IntelX/Forge.
    Server 2: Sentinel/Cortex/VyralX. Addresses are the fleet's private
    addresses; the audit runs from inside the fleet.
    """
    return [
        FleetHost("server-1", "10.0.0.121", (
            FleetService("FRIDAY", 10000), FleetService("Inference", 8001),
            FleetService("Memora", 8002), FleetService("Stratex", 8003),
            FleetService("Futuris", 8004), FleetService("IntelX", 8005),
            FleetService("Forge", 8006),
        )),
        FleetHost("server-2", "10.0.0.120", (
            FleetService("Sentinel", 8008), FleetService("Cortex", 8009),
            FleetService("VyralX", 8010),
        )),
    ]


@dataclass(frozen=True)
class AuditTarget:
    host: str
    address: str
    service: str
    port: int
    scheme: str

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.address}:{self.port}"


@dataclass(frozen=True)
class PlannedCheck:
    target: AuditTarget
    check_id: str      # port-reachable | unexpected-ports | tls | headers | health


@dataclass
class Finding:
    finding_id: str    # deterministic: host/service/check
    host: str
    service: str
    check_id: str
    severity: str      # CRITICAL | HIGH | MEDIUM | LOW
    title: str
    detail: str
    verified: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id, "host": self.host,
            "service": self.service, "check_id": self.check_id,
            "severity": self.severity, "title": self.title,
            "detail": self.detail, "verified": self.verified,
        }


@dataclass
class ProbeSet:
    """Injectable probes. Defaults are connect-only / read-only."""

    tcp_open: Callable[[str, int], bool]
    tls_info: Callable[[str, int], dict[str, Any] | None]
    http_get: Callable[[str], tuple[int, dict[str, str]]]


def _default_tcp_open(address: str, port: int) -> bool:
    try:
        with socket.create_connection((address, port), timeout=PROBE_TIMEOUT_S):
            return True
    except OSError:
        return False


def _default_tls_info(address: str, port: int) -> dict[str, Any] | None:
    context = ssl.create_default_context()
    try:
        with socket.create_connection((address, port), timeout=PROBE_TIMEOUT_S) as raw:
            with context.wrap_socket(raw, server_hostname=address) as tls:
                cert = tls.getpeercert()
        not_after = cert.get("notAfter", "")
        expires = None
        if not_after:
            expires = datetime.strptime(
                not_after, "%b %d %H:%M:%S %Y %Z"
            ).replace(tzinfo=timezone.utc)
        return {"not_after": not_after, "expires_at": expires, "subject": str(cert.get("subject", ""))}
    except (OSError, ssl.SSLError, ValueError):
        return None


def _default_http_get(url: str) -> tuple[int, dict[str, str]]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT_S) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as error:  # a status is still information
        return error.code, {k.lower(): v for k, v in error.headers.items()}
    except (urllib.error.URLError, OSError):
        return 0, {}


def default_probes() -> ProbeSet:
    return ProbeSet(
        tcp_open=_default_tcp_open, tls_info=_default_tls_info,
        http_get=_default_http_get,
    )


class InventoryResearcher:
    """Role 1 (PentAGI 'researcher'): inventory → audit targets."""

    def __init__(self, inventory: Iterable[FleetHost]) -> None:
        self.inventory = list(inventory)
        self._addresses = {host.address for host in self.inventory}
        self._names = {host.name for host in self.inventory}

    def assert_in_scope(self, address: str) -> None:
        if address not in self._addresses and address not in self._names:
            raise OutOfScopeError(
                f"{address!r} is not in the FRIDAY fleet inventory; "
                "Sentinel audits its own fleet only"
            )

    def targets(self) -> list[AuditTarget]:
        return [
            AuditTarget(host.name, host.address, service.name, service.port,
                        service.scheme)
            for host in self.inventory for service in host.services
        ]


class CheckPlanner:
    """Role 2 (PentAGI 'planner'): targets → allowlisted defensive checks."""

    def plan(self, targets: Iterable[AuditTarget]) -> list[PlannedCheck]:
        plan: list[PlannedCheck] = []
        seen_hosts: set[str] = set()
        for target in targets:
            plan.append(PlannedCheck(target, "port-reachable"))
            plan.append(PlannedCheck(target, "health"))
            plan.append(PlannedCheck(target, "headers"))
            if target.scheme == "https":
                plan.append(PlannedCheck(target, "tls"))
            if target.address not in seen_hosts:
                seen_hosts.add(target.address)
                plan.append(PlannedCheck(target, "unexpected-ports"))
        return plan


class CheckExecutor:
    """Role 3 (PentAGI 'executor'): runs planned checks via probes."""

    def __init__(self, probes: ProbeSet) -> None:
        self.probes = probes

    def run_check(self, check: PlannedCheck) -> list[Finding]:
        handler = {
            "port-reachable": self._port_reachable,
            "unexpected-ports": self._unexpected_ports,
            "tls": self._tls,
            "headers": self._headers,
            "health": self._health,
        }[check.check_id]
        return handler(check.target)

    def _finding(self, target: AuditTarget, check_id: str, severity: str,
                 title: str, detail: str) -> Finding:
        return Finding(
            finding_id=f"{target.host}/{target.service}/{check_id}",
            host=target.host, service=target.service, check_id=check_id,
            severity=severity, title=title, detail=detail,
        )

    def _port_reachable(self, target: AuditTarget) -> list[Finding]:
        if self.probes.tcp_open(target.address, target.port):
            return []
        return [self._finding(
            target, "port-reachable", "HIGH",
            f"{target.service} port {target.port} unreachable",
            f"Expected {target.service} listening on "
            f"{target.address}:{target.port}; connection failed.",
        )]

    def _unexpected_ports(self, target: AuditTarget) -> list[Finding]:
        findings = []
        for port, label in sorted(UNEXPECTED_PORTS.items()):
            if self.probes.tcp_open(target.address, port):
                findings.append(self._finding(
                    target, "unexpected-ports", "HIGH",
                    f"Unexpected {label} port {port} open on {target.host}",
                    f"{target.address}:{port} ({label}) accepts connections; "
                    "it is not part of the fleet's service inventory.",
                ))
        return findings

    def _tls(self, target: AuditTarget) -> list[Finding]:
        info = self.probes.tls_info(target.address, target.port)
        if info is None:
            return [self._finding(
                target, "tls", "HIGH",
                f"TLS handshake/certificate invalid for {target.service}",
                f"No valid certificate obtained from "
                f"{target.address}:{target.port}.",
            )]
        expires = info.get("expires_at")
        if isinstance(expires, datetime):
            days = (expires - datetime.now(timezone.utc)).days
            if days < 0:
                return [self._finding(
                    target, "tls", "CRITICAL",
                    f"TLS certificate EXPIRED for {target.service}",
                    f"Certificate expired {-days} day(s) ago ({info.get('not_after')}).",
                )]
            if days <= TLS_EXPIRY_ALERT_DAYS:
                return [self._finding(
                    target, "tls", "MEDIUM",
                    f"TLS certificate expires in {days} day(s) for {target.service}",
                    f"Certificate not-after: {info.get('not_after')}.",
                )]
        return []

    def _headers(self, target: AuditTarget) -> list[Finding]:
        status, headers = self.probes.http_get(target.base_url + "/")
        if status == 0:
            return []  # unreachability is the port/health checks' finding
        missing = [
            label for header, label in EXPECTED_SECURITY_HEADERS.items()
            if header not in headers
        ]
        if not missing:
            return []
        return [self._finding(
            target, "headers", "LOW",
            f"{target.service} missing security headers: {', '.join(missing)}",
            f"{target.base_url}/ responded {status} without: "
            f"{', '.join(missing)}.",
        )]

    def _health(self, target: AuditTarget) -> list[Finding]:
        status, _ = self.probes.http_get(target.base_url + "/health")
        if status == 200:
            return []
        return [self._finding(
            target, "health", "HIGH",
            f"{target.service} /health returned {status or 'no response'}",
            f"GET {target.base_url}/health did not return 200.",
        )]


class FindingReflector:
    """Role 4 (PentAGI 'reflector'): independently re-verify each finding.

    A finding is kept only if re-running its check reproduces a finding
    with the same id; otherwise it is dropped and recorded with a reason.
    """

    def __init__(self, executor: CheckExecutor) -> None:
        self.executor = executor

    def verify(
        self, findings: Iterable[Finding], plan: Iterable[PlannedCheck],
    ) -> tuple[list[Finding], list[dict[str, str]]]:
        plan_by_key = {
            (c.target.host, c.target.service, c.check_id): c for c in plan
        }
        kept: list[Finding] = []
        dropped: list[dict[str, str]] = []
        for finding in findings:
            check = plan_by_key.get(
                (finding.host, finding.service, finding.check_id)
            )
            if check is None:
                dropped.append({
                    "finding_id": finding.finding_id,
                    "reason": "no planned check to re-verify against",
                })
                continue
            reproduced = {
                f.finding_id for f in self.executor.run_check(check)
            }
            if finding.finding_id in reproduced:
                finding.verified = True
                kept.append(finding)
            else:
                dropped.append({
                    "finding_id": finding.finding_id,
                    "reason": "did not reproduce on independent re-check",
                })
        return kept, dropped


@dataclass
class AuditReport:
    generated_at: str
    targets: int
    checks_run: int
    findings: list[Finding] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "targets": self.targets,
            "checks_run": self.checks_run,
            "findings": [f.as_dict() for f in self.findings],
            "dropped_unverified": self.dropped,
            "summary": {
                severity: sum(1 for f in self.findings if f.severity == severity)
                for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
            },
        }

    def to_markdown(self) -> str:
        lines = [
            "# Sentinel fleet audit",
            f"Generated: {self.generated_at} · targets: {self.targets} · "
            f"checks: {self.checks_run} · verified findings: {len(self.findings)}",
            "",
        ]
        if not self.findings:
            lines.append("No verified findings. The fleet matches its inventory.")
        for finding in self.findings:
            lines.append(
                f"- [{finding.severity}] {finding.title} — {finding.detail}"
            )
        if self.dropped:
            lines += ["", f"Unverified (dropped): {len(self.dropped)}"]
            for item in self.dropped:
                lines.append(f"- {item['finding_id']}: {item['reason']}")
        return "\n".join(lines) + "\n"


class FleetAuditPipeline:
    """Orchestrates researcher → planner → executor → reflector → report."""

    def __init__(
        self, inventory: Iterable[FleetHost] | None = None,
        probes: ProbeSet | None = None,
    ) -> None:
        self.researcher = InventoryResearcher(
            inventory if inventory is not None else default_fleet_inventory()
        )
        self.planner = CheckPlanner()
        self.executor = CheckExecutor(probes or default_probes())
        self.reflector = FindingReflector(self.executor)

    def run(self, extra_targets: Iterable[AuditTarget] = ()) -> AuditReport:
        targets = self.researcher.targets()
        for target in extra_targets:
            self.researcher.assert_in_scope(target.address)
            targets.append(target)
        plan = self.planner.plan(targets)
        raw_findings: list[Finding] = []
        for check in plan:
            raw_findings.extend(self.executor.run_check(check))
        findings, dropped = self.reflector.verify(raw_findings, plan)
        return AuditReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            targets=len(targets), checks_run=len(plan),
            findings=findings, dropped=dropped,
        )
