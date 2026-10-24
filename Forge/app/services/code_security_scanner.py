"""
Forge/app/services/code_security_scanner.py — Forge Code Security Scanner.

Security vulnerability detection, secret scanning, dependency security,
and code security posture assessment.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class Vulnerability:
    """A detected vulnerability."""
    vuln_id: str
    file_path: str
    line: int = 0
    severity: str = "medium"  # low, medium, high, critical
    cwe_id: str = ""
    category: str = ""  # injection, auth, crypto, ssrf, xss, secret
    description: str = ""
    remediation: str = ""


@dataclass
class SecretFinding:
    """A secret found in code."""
    finding_id: str
    file_path: str
    line: int = 0
    secret_type: str = ""  # api_key, password, token, private_key
    masked_value: str = ""
    severity: str = "high"


@dataclass
class SecurityReport:
    """A comprehensive security scan report."""
    report_id: str
    project_path: str
    total_vulnerabilities: int = 0
    critical_vulns: int = 0
    high_vulns: int = 0
    secrets_found: int = 0
    security_score: float = 0.0
    scanned_files: int = 0
    scanned_at: float = field(default_factory=time.time)


class CodeSecurityScanner:
    """Engine for code security scanning."""

    def __init__(self) -> None:
        self._vulns: list[Vulnerability] = []
        self._secrets: list[SecretFinding] = []
        self._reports: list[SecurityReport] = []

    def scan_code(self, file_path: str, code: str) -> list[Vulnerability]:
        """Scan code for vulnerabilities."""
        found = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            line_lower = line.lower()

            # SQL injection
            if "execute(" in line_lower and ("query" in line_lower or "sql" in line_lower):
                found.append(Vulnerability(
                    vuln_id=f"v_{uuid.uuid4().hex[:8]}", file_path=file_path, line=i,
                    severity="critical", cwe_id="CWE-89", category="injection",
                    description="Potential SQL injection",
                    remediation="Use parameterized queries",
                ))

            # XSS
            if "render_template_string" in line_lower or "innerhtml" in line_lower:
                found.append(Vulnerability(
                    vuln_id=f"v_{uuid.uuid4().hex[:8]}", file_path=file_path, line=i,
                    severity="high", cwe_id="CWE-79", category="xss",
                    description="Potential XSS vulnerability",
                    remediation="Use template auto-escaping",
                ))

            # SSRF
            if "requests.get(" in line_lower or "urllib.request" in line_lower:
                if "http://" in line or "https://" in line:
                    found.append(Vulnerability(
                        vuln_id=f"v_{uuid.uuid4().hex[:8]}", file_path=file_path, line=i,
                        severity="high", cwe_id="CWE-918", category="ssrf",
                        description="Potential SSRF via external URL",
                        remediation="Validate and restrict URLs",
                ))

            # Hardcoded secrets
            if any(keyword in line_lower for keyword in ["password", "api_key", "secret", "token"]):
                if "=" in line and len(line.split("=", 1)[1].strip()) > 8:
                    found.append(Vulnerability(
                        vuln_id=f"v_{uuid.uuid4().hex[:8]}", file_path=file_path, line=i,
                        severity="critical", cwe_id="CWE-798", category="secret",
                        description="Hardcoded secret detected",
                        remediation="Use environment variables or secret manager",
                ))

        self._vulns.extend(found)
        return found

    def scan_secrets(self, file_path: str, code: str) -> list[SecretFinding]:
        """Scan code for secrets."""
        found = []
        lines = code.split("\n")
        secret_patterns = {
            "api_key": ["api_key", "apikey", "api-key"],
            "password": ["password", "passwd", "pwd"],
            "token": ["token", "bearer", "auth_token"],
            "private_key": ["-----begin", "private key"],
        }

        for i, line in enumerate(lines, 1):
            line_lower = line.lower()
            for secret_type, patterns in secret_patterns.items():
                for pattern in patterns:
                    if pattern in line_lower:
                        # Check if value looks like a real secret
                        parts = line.split("=", 1)
                        if len(parts) > 1 and len(parts[1].strip()) > 10:
                            masked = parts[1][:3] + "..." + parts[1][-3:]
                            found.append(SecretFinding(
                                finding_id=f"s_{uuid.uuid4().hex[:8]}",
                                file_path=file_path, line=i,
                                secret_type=secret_type,
                                masked_value=masked,
                                severity="high" if secret_type in ("api_key", "password") else "medium",
                            ))

        self._secrets.extend(found)
        return found

    def generate_report(self, project_path: str, scanned_files: int = 1) -> SecurityReport:
        """Generate a security report."""
        report_id = f"sec_{uuid.uuid4().hex[:12]}"
        report = SecurityReport(
            report_id=report_id, project_path=project_path,
            scanned_files=scanned_files,
        )
        report.total_vulnerabilities = len(self._vulns)
        report.critical_vulns = sum(1 for v in self._vulns if v.severity == "critical")
        report.high_vulns = sum(1 for v in self._vulns if v.severity == "high")
        report.secrets_found = len(self._secrets)

        penalty = report.critical_vulns * 25 + report.high_vulns * 10 + report.secrets_found * 15
        report.security_score = max(0.0, 100.0 - penalty)

        self._reports.append(report)
        return report

    def get_vulnerabilities(self, severity: str | None = None) -> list[dict[str, Any]]:
        """Get vulnerabilities."""
        vulns = self._vulns
        if severity:
            vulns = [v for v in vulns if v.severity == severity]
        return [
            {"file": v.file_path, "line": v.line, "severity": v.severity,
             "category": v.category, "description": v.description[:60]}
            for v in vulns
        ]

    def get_report(self) -> dict[str, Any]:
        """Get engine report."""
        return {
            "total_vulnerabilities": len(self._vulns),
            "total_secrets": len(self._secrets),
            "total_reports": len(self._reports),
            "engine_status": "operational",
        }


engine = CodeSecurityScanner()


@router.post("/forge/security/scan")
async def scan_code(file_path: str, code: str):
    """Scan code for vulnerabilities."""
    vulns = engine.scan_code(file_path, code)
    secrets = engine.scan_secrets(file_path, code)
    return {
        "file_path": file_path,
        "vulnerability_count": len(vulns),
        "secret_count": len(secrets),
    }


@router.post("/forge/security/report")
async def generate_report(project_path: str, scanned_files: int = 1):
    """Generate security report."""
    report = engine.generate_report(project_path, scanned_files)
    return {
        "report_id": report.report_id,
        "security_score": report.security_score,
        "critical_vulns": report.critical_vulns,
        "high_vulns": report.high_vulns,
        "secrets_found": report.secrets_found,
    }


@router.get("/forge/security/vulnerabilities")
async def get_vulnerabilities(severity: str | None = None):
    """Get vulnerabilities."""
    return {"vulnerabilities": engine.get_vulnerabilities(severity)}


@router.get("/forge/security/report")
async def security_report():
    """Get security scanner report."""
    return engine.get_report()
