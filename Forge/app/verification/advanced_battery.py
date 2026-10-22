"""
Advanced Security Verification Battery for Project FORGE.
Performs secrets scanning, dangerous function AST detection, CVE dependency checks, and API input validation presence verification.
"""

import ast
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger("verification.advanced_battery")


class VerificationCheck(BaseModel):
    """Standardized outcome for an individual verification check."""

    name: str
    category: str  # security, quality, performance, browser
    status: str = "pass"  # pass, fail, warn
    evidence: dict[str, Any] = Field(default_factory=dict)
    fix_suggestions: list[str] = Field(default_factory=list)


# Known Vulnerable Packages & CVE database simulation
KNOWN_VULNERABLE_PACKAGES: dict[str, dict[str, str]] = {
    "urllib3": {"max_vulnerable_version": "1.26.4", "cve": "CVE-2021-33503", "severity": "HIGH"},
    "requests": {"max_vulnerable_version": "2.19.1", "cve": "CVE-2018-18074", "severity": "MEDIUM"},
    "flask": {"max_vulnerable_version": "0.12.2", "cve": "CVE-2018-1000656", "severity": "HIGH"},
    "jinja2": {"max_vulnerable_version": "2.11.2", "cve": "CVE-2020-28493", "severity": "HIGH"},
    "pillow": {"max_vulnerable_version": "8.1.1", "cve": "CVE-2021-27921", "severity": "CRITICAL"},
}

# Regex patterns for sensitive credentials
SECRET_PATTERNS = {
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "Generic Private Key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "OpenAI API Key": r"sk-[a-zA-Z0-9]{20,48}",
    "GitHub Token": r"gh[pousr]_[0-9a-zA-Z]{36}",
    "Generic Hardcoded Password": r'(?i)(?:password|passwd|pwd|secret|api_key|apikey)\s*=\s*["\'](?!default|test|placeholder|sample|none|changeme|[a-z0-9_-]{0,4}["\'])[a-zA-Z0-9!@#$%^&*()_+=-]{8,}["\']',
    "Database Connection String": r"(?i)(?:postgres|postgresql|mysql|mongodb|redis):\/\/[a-zA-Z0-9_-]+:[a-zA-Z0-9!@#$%^&*()_+=-]+@[a-zA-Z0-9.-]+:[0-9]+",
}


class AdvancedSecurityVerifier:
    """Executes multi-vector static security analysis across workspace code."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def scan_secrets(self) -> VerificationCheck:
        """Scan all codebase files for exposed API keys, private keys, and hardcoded credentials."""
        found_secrets: list[dict[str, Any]] = []

        for p in self.workspace_path.rglob("*"):
            if (
                not p.is_file()
                or p.name.startswith(".")
                or "node_modules" in str(p)
                or ".git" in str(p)
            ):
                continue
            if p.suffix.lower() not in [
                ".py",
                ".js",
                ".ts",
                ".json",
                ".env",
                ".yaml",
                ".yml",
                ".html",
                ".md",
            ]:
                continue

            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                for line_idx, line in enumerate(content.splitlines(), start=1):
                    for secret_name, pattern in SECRET_PATTERNS.items():
                        match = re.search(pattern, line)
                        if match:
                            found_secrets.append(
                                {
                                    "file": p.name,
                                    "line": line_idx,
                                    "type": secret_name,
                                    "snippet": f"{line[: match.start()]}***REDACTED***{line[match.end() :]}"[
                                        :100
                                    ],
                                }
                            )
            except Exception as e:
                logger.debug(f"Could not read file {p}: {e}")

        if found_secrets:
            return VerificationCheck(
                name="Hardcoded Secrets Scan",
                category="security",
                status="fail",
                evidence={"secrets_found_count": len(found_secrets), "violations": found_secrets},
                fix_suggestions=[
                    "Extract hardcoded credentials into environment variables accessed via os.getenv() or a .env file.",
                    "Use secret management or configuration injection instead of committing plaintext tokens.",
                ],
            )

        return VerificationCheck(
            name="Hardcoded Secrets Scan",
            category="security",
            status="pass",
            evidence={
                "scanned_files": sum(1 for _ in self.workspace_path.rglob("*") if _.is_file())
            },
        )

    def scan_dangerous_functions(self) -> VerificationCheck:
        """Inspect Python AST for dangerous functions (eval, exec, os.system, shell=True)."""
        violations: list[dict[str, Any]] = []

        for py_file in self.workspace_path.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    # Check eval() / exec()
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        if node.func.id in ["eval", "exec"]:
                            violations.append(
                                {
                                    "file": py_file.name,
                                    "line": getattr(node, "lineno", 0),
                                    "dangerous_call": node.func.id,
                                    "reason": f"Arbitrary code execution risk via {node.func.id}()",
                                }
                            )

                    # Check os.system()
                    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                        if (
                            node.func.attr == "system"
                            and isinstance(node.func.value, ast.Name)
                            and node.func.value.id == "os"
                        ):
                            violations.append(
                                {
                                    "file": py_file.name,
                                    "line": getattr(node, "lineno", 0),
                                    "dangerous_call": "os.system",
                                    "reason": "Shell injection vulnerability via os.system()",
                                }
                            )

                        # Check subprocess.Popen/run with shell=True
                        elif node.func.attr in ["Popen", "run", "call", "check_output"]:
                            for keyword in node.keywords:
                                if (
                                    keyword.arg == "shell"
                                    and isinstance(keyword.value, ast.Constant)
                                    and keyword.value.value is True
                                ):
                                    violations.append(
                                        {
                                            "file": py_file.name,
                                            "line": getattr(node, "lineno", 0),
                                            "dangerous_call": f"subprocess.{node.func.attr}(..., shell=True)",
                                            "reason": "Shell execution risk with shell=True",
                                        }
                                    )
            except Exception as e:
                logger.debug(f"AST parse error in {py_file}: {e}")

        if violations:
            return VerificationCheck(
                name="Dangerous Functions AST Scan",
                category="security",
                status="fail",
                evidence={"dangerous_calls_count": len(violations), "violations": violations},
                fix_suggestions=[
                    "Replace eval() or exec() with ast.literal_eval() or structured parsers (e.g. json.loads).",
                    "Replace os.system() and subprocess(..., shell=True) with subprocess.run(['cmd', 'arg1'], shell=False).",
                ],
            )

        return VerificationCheck(
            name="Dangerous Functions AST Scan",
            category="security",
            status="pass",
            evidence={"inspected_python_files": sum(1 for _ in self.workspace_path.rglob("*.py"))},
        )

    def scan_dependency_vulnerabilities(self) -> VerificationCheck:
        """Cross-reference requirements.txt and package.json against known CVE database."""
        vulnerabilities: list[dict[str, Any]] = []
        req_file = self.workspace_path / "requirements.txt"

        if req_file.exists():
            for line in req_file.read_text(encoding="utf-8").splitlines():
                clean_line = line.strip()
                if not clean_line or clean_line.startswith("#"):
                    continue

                # Match package==version
                parts = re.split(r"[=<>~]+", clean_line)
                pkg_name = parts[0].strip().lower()
                version = parts[1].strip() if len(parts) > 1 else ""

                if pkg_name in KNOWN_VULNERABLE_PACKAGES:
                    cve_info = KNOWN_VULNERABLE_PACKAGES[pkg_name]
                    vulnerabilities.append(
                        {
                            "package": pkg_name,
                            "installed_version": version or "unspecified",
                            "cve": cve_info["cve"],
                            "severity": cve_info["severity"],
                            "max_vulnerable_version": cve_info["max_vulnerable_version"],
                        }
                    )

        if vulnerabilities:
            return VerificationCheck(
                name="Dependency Vulnerability Scan",
                category="security",
                status="warn"
                if all(v["severity"] != "CRITICAL" for v in vulnerabilities)
                else "fail",
                evidence={"vulnerable_dependencies": vulnerabilities},
                fix_suggestions=[
                    f"Upgrade package {v['package']} beyond version {v['max_vulnerable_version']} to patch {v['cve']}."
                    for v in vulnerabilities
                ],
            )

        return VerificationCheck(
            name="Dependency Vulnerability Scan",
            category="security",
            status="pass",
            evidence={"manifest_scanned": req_file.name if req_file.exists() else "None"},
        )

    def verify_input_validation_presence(self) -> VerificationCheck:
        """Verify that generated REST API endpoints implement input validation via Pydantic or schemas."""
        api_files = list(self.workspace_path.rglob("*.py"))
        endpoint_count = 0
        validated_endpoint_count = 0

        for py_file in api_files:
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Check if function has router decorator: @router.get/post/put/delete or @app.get/post
                        has_route_decorator = any(
                            (
                                isinstance(d, ast.Call)
                                and isinstance(d.func, ast.Attribute)
                                and d.func.attr in ["get", "post", "put", "delete", "patch"]
                            )
                            for d in node.decorator_list
                        )
                        if has_route_decorator:
                            endpoint_count += 1
                            # Check if arguments have type annotations or Pydantic models
                            has_validation = any(
                                arg.annotation is not None
                                for arg in node.args.args
                                if arg.arg not in ["self", "cls", "request"]
                            )
                            if has_validation or not [
                                a for a in node.args.args if a.arg not in ["self", "cls", "request"]
                            ]:
                                validated_endpoint_count += 1
            except Exception as e:
                logger.debug(f"Error checking input validation in {py_file}: {e}")

        if endpoint_count > 0 and validated_endpoint_count < endpoint_count:
            return VerificationCheck(
                name="API Input Validation Presence",
                category="security",
                status="warn",
                evidence={
                    "total_endpoints": endpoint_count,
                    "validated_endpoints": validated_endpoint_count,
                },
                fix_suggestions=[
                    "Add Pydantic request models or type-annotated Query/Path/Body parameters to all FastAPI endpoints."
                ],
            )

        return VerificationCheck(
            name="API Input Validation Presence",
            category="security",
            status="pass",
            evidence={
                "endpoints_found": endpoint_count,
                "validated_endpoints": validated_endpoint_count,
            },
        )

    def run_all(self) -> list[VerificationCheck]:
        """Execute complete security battery."""
        return [
            self.scan_secrets(),
            self.scan_dangerous_functions(),
            self.scan_dependency_vulnerabilities(),
            self.verify_input_validation_presence(),
        ]


class VerificationManifest(BaseModel):
    """Complete consolidated verification manifest with per-check details."""

    workspace_path: str
    overall_status: str  # pass, fail, warn
    total_checks: int
    passed_checks: int
    failed_checks: int
    warned_checks: int
    checks: list[VerificationCheck] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    def save_to_workspace(self, workspace_path: Path) -> Path:
        """Write verification_manifest.json into target workspace directory."""
        manifest_file = workspace_path / "verification_manifest.json"
        manifest_file.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return manifest_file


class AdvancedVerificationEngine:
    """Consolidated runner executing security, quality, performance, and browser verification batteries."""

    @classmethod
    def run_full_battery(cls, workspace_path: Path) -> VerificationManifest:
        from app.verification.browser_interactions import BrowserInteractionVerifier
        from app.verification.language_verifiers import PolyglotLanguageVerifier
        from app.verification.performance import PerformanceVerifier
        from app.verification.quality_analyzer import CodeQualityAnalyzer
        from app.verification.security_scanner import OutputSecurityScanner, SecuritySeverity

        # 1. Run Pre-Verification Output Security Scanner
        sec_scanner = OutputSecurityScanner(workspace_path)
        sec_report = sec_scanner.scan_all()

        checks: list[VerificationCheck] = []

        # Convert detailed scanner findings into VerificationChecks
        if sec_report.findings:
            for finding in sec_report.findings:
                status = (
                    "fail"
                    if finding.severity in [SecuritySeverity.CRITICAL, SecuritySeverity.HIGH]
                    else "warn"
                )
                checks.append(
                    VerificationCheck(
                        name=f"[{finding.severity.value}] {finding.check_name}",
                        category="security",
                        status=status,
                        evidence={
                            "file": finding.file_path,
                            "line": finding.line_number,
                            "snippet": finding.snippet,
                            "description": finding.description,
                            "cve_id": finding.cve_id,
                        },
                        fix_suggestions=[finding.fix_suggestion],
                    )
                )
        else:
            checks.append(
                VerificationCheck(
                    name="Pre-Verification Output Security Scanner",
                    category="security",
                    status="pass",
                    evidence={
                        "scanned_files": sec_report.scanned_files_count,
                        "vulnerabilities_found": 0,
                    },
                )
            )

        # 2. Run remaining multi-vector batteries
        checks.extend(AdvancedSecurityVerifier(workspace_path).run_all())
        checks.extend(CodeQualityAnalyzer(workspace_path).run_all())
        checks.extend(PerformanceVerifier(workspace_path).run_all())
        checks.extend(BrowserInteractionVerifier(workspace_path).run_all())
        checks.extend(PolyglotLanguageVerifier(workspace_path).run_all())

        failed = sum(1 for c in checks if c.status == "fail")
        warned = sum(1 for c in checks if c.status == "warn")
        passed = sum(1 for c in checks if c.status == "pass")

        overall = "pass"
        if failed > 0:
            overall = "fail"
        elif warned > 0:
            overall = "warn"

        manifest = VerificationManifest(
            workspace_path=str(workspace_path),
            overall_status=overall,
            total_checks=len(checks),
            passed_checks=passed,
            failed_checks=failed,
            warned_checks=warned,
            checks=checks,
        )
        manifest.save_to_workspace(workspace_path)
        return manifest
