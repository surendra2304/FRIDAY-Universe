"""
Output Security Scanner & Security-First Verification for Project FORGE.
Executes multi-vector static security scanning BEFORE standard verification:
- Hardcoded secrets and credential scanning with automated redaction
- Dangerous function AST detection (eval, exec, os.system, subprocess with shell=True, pickle.loads)
- Injection vulnerability patterns (SQL concatenation, command injection, XSS via innerHTML)
- Insecure dependencies check against CVE database with automatic remediation
- Authentication bypass and missing decorator patterns
- Structured severity classification: CRITICAL, HIGH, MEDIUM, LOW
"""

import ast
import json
import re
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.monitoring.production_monitor import production_monitor

logger = get_logger("verification.security_scanner")


class SecuritySeverity(str, Enum):
    CRITICAL = "CRITICAL"  # Blocks delivery — must fix
    HIGH = "HIGH"  # Blocks delivery — must fix
    MEDIUM = "MEDIUM"  # Warning in report — delivery allowed
    LOW = "LOW"  # Informational notice


class SecurityFinding(BaseModel):
    """Detailed finding from static security analysis."""

    check_name: str
    severity: SecuritySeverity
    file_path: str
    line_number: int | None = None
    snippet: str = ""
    description: str
    fix_suggestion: str
    cve_id: str | None = None


class SecurityScanReport(BaseModel):
    """Aggregated security scan result across a workspace."""

    workspace_path: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    scanned_files_count: int = 0
    findings: list[SecurityFinding] = Field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    passed: bool = True
    blocks_delivery: bool = False


# Local CVE and Vulnerability Knowledge Base with Safe Versions
CVE_VULNERABILITY_DB: dict[str, dict[str, Any]] = {
    # Python Packages
    "urllib3": {
        "language": "python",
        "max_vulnerable_version": "1.26.4",
        "safe_version": "1.26.18",
        "cve": "CVE-2021-33503",
        "severity": SecuritySeverity.HIGH,
        "description": "ReDoS vulnerability in urllib3 URL authority parsing.",
    },
    "requests": {
        "language": "python",
        "max_vulnerable_version": "2.19.1",
        "safe_version": "2.31.0",
        "cve": "CVE-2018-18074",
        "severity": SecuritySeverity.MEDIUM,
        "description": "Session credentials leak across HTTP redirects.",
    },
    "flask": {
        "language": "python",
        "max_vulnerable_version": "0.12.2",
        "safe_version": "3.0.0",
        "cve": "CVE-2018-1000656",
        "severity": SecuritySeverity.HIGH,
        "description": "Unexpected JSON decoding dos vulnerability.",
    },
    "jinja2": {
        "language": "python",
        "max_vulnerable_version": "2.11.2",
        "safe_version": "3.1.3",
        "cve": "CVE-2020-28493",
        "severity": SecuritySeverity.HIGH,
        "description": "ReDoS vulnerability in Jinja2 urlize filter.",
    },
    "pillow": {
        "language": "python",
        "max_vulnerable_version": "8.1.1",
        "safe_version": "10.2.0",
        "cve": "CVE-2021-27921",
        "severity": SecuritySeverity.CRITICAL,
        "description": "Buffer overflow and arbitrary memory corruption in Pillow image parser.",
    },
    "pyyaml": {
        "language": "python",
        "max_vulnerable_version": "5.3.1",
        "safe_version": "6.0.1",
        "cve": "CVE-2020-14343",
        "severity": SecuritySeverity.CRITICAL,
        "description": "Arbitrary code execution via full_load or unsafe deserialization.",
    },
    "cryptography": {
        "language": "python",
        "max_vulnerable_version": "3.3.1",
        "safe_version": "42.0.0",
        "cve": "CVE-2020-36242",
        "severity": SecuritySeverity.HIGH,
        "description": "Buffer overflow and memory exhaustion in cryptography parsing.",
    },
    # Node / JavaScript Packages
    "lodash": {
        "language": "javascript",
        "max_vulnerable_version": "4.17.20",
        "safe_version": "4.17.21",
        "cve": "CVE-2021-23337",
        "severity": SecuritySeverity.HIGH,
        "description": "Prototype pollution and command injection via template function.",
    },
    "express": {
        "language": "javascript",
        "max_vulnerable_version": "4.16.0",
        "safe_version": "4.19.2",
        "cve": "CVE-2024-29041",
        "severity": SecuritySeverity.MEDIUM,
        "description": "Open redirect vulnerability in express router handling.",
    },
    "jsonwebtoken": {
        "language": "javascript",
        "max_vulnerable_version": "8.5.1",
        "safe_version": "9.0.0",
        "cve": "CVE-2022-23529",
        "severity": SecuritySeverity.CRITICAL,
        "description": "Insecure key retrieval allowing arbitrary remote code execution.",
    },
    "axios": {
        "language": "javascript",
        "max_vulnerable_version": "0.21.1",
        "safe_version": "1.6.8",
        "cve": "CVE-2021-3749",
        "severity": SecuritySeverity.HIGH,
        "description": "Regular expression denial of service in trim method.",
    },
}

# Regex patterns for secrets and private tokens
SECRET_SCAN_PATTERNS = {
    "AWS Access Key ID": (r"AKIA[0-9A-Z]{16}", SecuritySeverity.CRITICAL),
    "RSA / OpenSSH Private Key": (
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
        SecuritySeverity.CRITICAL,
    ),
    "OpenAI API Key": (r"sk-[a-zA-Z0-9]{20,48}", SecuritySeverity.CRITICAL),
    "Anthropic API Key": (r"sk-ant-api[a-zA-Z0-9_-]{20,80}", SecuritySeverity.CRITICAL),
    "GitHub Personal Access Token": (r"gh[pousr]_[0-9a-zA-Z]{36}", SecuritySeverity.CRITICAL),
    "Generic Hardcoded Secret/Password": (
        r'(?i)(?:password|passwd|pwd|secret_key|api_secret|auth_token)\s*=\s*["\'](?!default|test|placeholder|sample|none|changeme|[a-z0-9_-]{0,4}["\'])[a-zA-Z0-9!@#$%^&*()_+=-]{8,}["\']',
        SecuritySeverity.HIGH,
    ),
    "Database Credentials URI": (
        r"(?i)(?:postgres|postgresql|mysql|mongodb|redis):\/\/[a-zA-Z0-9_-]+:[a-zA-Z0-9!@#$%^&*()_+=-]+@[a-zA-Z0-9.-]+:[0-9]+",
        SecuritySeverity.CRITICAL,
    ),
}


class OutputSecurityScanner:
    """
    Comprehensive Static Security Scanner running before verification batteries.
    Evaluates hardcoded credentials, dangerous AST calls, injection patterns,
    vulnerable packages, and authentication bypasses.
    """

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def scan_all(self) -> SecurityScanReport:
        """Run all static security checks across the workspace."""
        findings: list[SecurityFinding] = []
        scanned_files = 0

        # 1. File content scans
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
                ".jsx",
                ".tsx",
                ".html",
                ".json",
                ".yaml",
                ".yml",
                ".env",
            ]:
                continue

            scanned_files += 1
            rel_path = str(p.relative_to(self.workspace_path))

            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.debug(f"Unable to read file {p}: {e}")
                continue

            # Hardcoded secrets
            findings.extend(self._scan_secrets_in_file(rel_path, content))

            # Dangerous functions & AST checks
            if p.suffix.lower() == ".py":
                findings.extend(self._scan_python_dangerous_ast(p, rel_path, content))
                findings.extend(self._scan_python_injections(p, rel_path, content))
                findings.extend(self._scan_python_auth_and_errors(p, rel_path, content))
            elif p.suffix.lower() in [".js", ".ts", ".jsx", ".tsx"]:
                findings.extend(self._scan_js_dangerous_patterns(rel_path, content))
                findings.extend(self._scan_js_injections(rel_path, content))

        # 2. Dependency security checks
        findings.extend(self.scan_dependencies())

        # Compute severity tallies
        crit = sum(1 for f in findings if f.severity == SecuritySeverity.CRITICAL)
        high = sum(1 for f in findings if f.severity == SecuritySeverity.HIGH)
        med = sum(1 for f in findings if f.severity == SecuritySeverity.MEDIUM)
        low = sum(1 for f in findings if f.severity == SecuritySeverity.LOW)

        blocks = crit > 0 or high > 0
        passed = len(findings) == 0 or not blocks

        # Feed the production monitor: record_security_scan() had no callers, so
        # security-scan telemetry never reached /metrics.
        production_monitor.record_security_scan(
            passed=passed, blocked=blocks, findings_count=len(findings)
        )

        return SecurityScanReport(
            workspace_path=str(self.workspace_path),
            scanned_files_count=scanned_files,
            findings=findings,
            critical_count=crit,
            high_count=high,
            medium_count=med,
            low_count=low,
            passed=passed,
            blocks_delivery=blocks,
        )

    def _scan_secrets_in_file(self, rel_path: str, content: str) -> list[SecurityFinding]:
        """Scan file text for hardcoded API keys, tokens, and credentials."""
        findings = []
        for line_num, line in enumerate(content.splitlines(), start=1):
            for secret_name, (pattern, severity) in SECRET_SCAN_PATTERNS.items():
                match = re.search(pattern, line)
                if match:
                    # Redact matching sensitive substring
                    snippet = f"{line[: match.start()]}***REDACTED***{line[match.end() :]}"[
                        :120
                    ].strip()
                    findings.append(
                        SecurityFinding(
                            check_name="Hardcoded Secret Detection",
                            severity=severity,
                            file_path=rel_path,
                            line_number=line_num,
                            snippet=snippet,
                            description=f"Exposed {secret_name} detected in source code.",
                            fix_suggestion="Extract credential to an environment variable loaded via os.getenv() or a .env file.",
                        )
                    )
        return findings

    def _scan_python_dangerous_ast(
        self, path: Path, rel_path: str, content: str
    ) -> list[SecurityFinding]:
        """Inspect Python AST for dangerous functions: eval, exec, os.system, shell=True, pickle.loads."""
        findings: list[SecurityFinding] = []
        try:
            tree = ast.parse(content, filename=str(path))
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # 1. eval()
                if isinstance(func, ast.Name) and func.id == "eval":
                    findings.append(
                        SecurityFinding(
                            check_name="Dangerous Function (eval)",
                            severity=SecuritySeverity.CRITICAL,
                            file_path=rel_path,
                            line_number=node.lineno,
                            snippet=f"eval(...) at line {node.lineno}",
                            description="Use of 'eval()' allows arbitrary remote code execution.",
                            fix_suggestion="Replace 'eval()' with safe parsers like ast.literal_eval() or json.loads().",
                        )
                    )
                # 2. exec()
                elif isinstance(func, ast.Name) and func.id == "exec":
                    findings.append(
                        SecurityFinding(
                            check_name="Dangerous Function (exec)",
                            severity=SecuritySeverity.CRITICAL,
                            file_path=rel_path,
                            line_number=node.lineno,
                            snippet=f"exec(...) at line {node.lineno}",
                            description="Use of 'exec()' dynamically executes untrusted Python statements.",
                            fix_suggestion="Refactor logic to invoke deterministic functions or dispatch tables instead of 'exec()'.",
                        )
                    )
                # 3. os.system()
                elif (
                    isinstance(func, ast.Attribute)
                    and func.attr == "system"
                    and getattr(func.value, "id", "") == "os"
                ):
                    findings.append(
                        SecurityFinding(
                            check_name="Dangerous Function (os.system)",
                            severity=SecuritySeverity.HIGH,
                            file_path=rel_path,
                            line_number=node.lineno,
                            snippet=f"os.system(...) at line {node.lineno}",
                            description="Use of 'os.system()' is susceptible to shell injection.",
                            fix_suggestion="Use 'subprocess.run([cmd, arg1, ...], shell=False)' with explicit argument lists.",
                        )
                    )
                # 4. subprocess with shell=True
                elif isinstance(func, ast.Attribute) and func.attr in [
                    "Popen",
                    "run",
                    "call",
                    "check_call",
                    "check_output",
                ]:
                    for kw in node.keywords:
                        if (
                            kw.arg == "shell"
                            and isinstance(kw.value, ast.Constant)
                            and kw.value.value is True
                        ):
                            findings.append(
                                SecurityFinding(
                                    check_name="Command Injection (subprocess shell=True)",
                                    severity=SecuritySeverity.CRITICAL,
                                    file_path=rel_path,
                                    line_number=node.lineno,
                                    snippet=f"subprocess.{func.attr}(..., shell=True) at line {node.lineno}",
                                    description="Subprocess invocation with shell=True facilitates command injection.",
                                    fix_suggestion="Pass command and arguments as a list with shell=False.",
                                )
                            )
                # 5. pickle.loads / pickle.load
                elif (
                    isinstance(func, ast.Attribute)
                    and func.attr in ["loads", "load"]
                    and getattr(func.value, "id", "") == "pickle"
                ):
                    findings.append(
                        SecurityFinding(
                            check_name="Insecure Deserialization (pickle)",
                            severity=SecuritySeverity.HIGH,
                            file_path=rel_path,
                            line_number=node.lineno,
                            snippet=f"pickle.{func.attr}(...) at line {node.lineno}",
                            description="Pickle deserialization executes arbitrary code during object reconstruction.",
                            fix_suggestion="Use standard JSON or Protocol Buffers for serializing data.",
                        )
                    )
                # 6. yaml.load without Loader=SafeLoader
                elif (
                    isinstance(func, ast.Attribute)
                    and func.attr == "load"
                    and getattr(func.value, "id", "") == "yaml"
                ):
                    has_safe_loader = any(
                        kw.arg == "Loader"
                        and "Safe" in getattr(kw.value, "id", getattr(kw.value, "attr", ""))
                        for kw in node.keywords
                    )
                    if not has_safe_loader:
                        findings.append(
                            SecurityFinding(
                                check_name="Insecure YAML Deserialization",
                                severity=SecuritySeverity.HIGH,
                                file_path=rel_path,
                                line_number=node.lineno,
                                snippet=f"yaml.load(...) at line {node.lineno}",
                                description="yaml.load() without SafeLoader executes arbitrary Python constructors.",
                                fix_suggestion="Use 'yaml.safe_load()' or pass 'Loader=yaml.SafeLoader'.",
                            )
                        )
        return findings

    def _scan_python_injections(
        self, path: Path, rel_path: str, content: str
    ) -> list[SecurityFinding]:
        """Detect SQL injection string concatenations and format strings in database queries."""
        findings = []
        lines = content.splitlines()

        for idx, line in enumerate(lines, start=1):
            # Check for SQL injection patterns
            sql_keywords = ["SELECT ", "INSERT INTO ", "UPDATE ", "DELETE FROM ", "DROP TABLE "]
            has_sql = any(k in line.upper() for k in sql_keywords)

            if has_sql:
                # 1. f-string formatting in SQL
                if re.search(r'f["\'].*(?:SELECT|INSERT|UPDATE|DELETE).*{.*}', line, re.IGNORECASE):
                    findings.append(
                        SecurityFinding(
                            check_name="SQL Injection Pattern (f-string)",
                            severity=SecuritySeverity.CRITICAL,
                            file_path=rel_path,
                            line_number=idx,
                            snippet=line.strip()[:100],
                            description="SQL query constructed via f-string interpolation rather than parameterized query.",
                            fix_suggestion="Use parameterized query placeholders (?, %s, or :param) with parameter bindings tuple.",
                        )
                    )
                # 2. String concatenation in SQL: "SELECT ... " + var
                elif re.search(
                    r'["\'].*(?:SELECT|INSERT|UPDATE|DELETE).*["\']\s*\+\s*[a-zA-Z_]',
                    line,
                    re.IGNORECASE,
                ):
                    findings.append(
                        SecurityFinding(
                            check_name="SQL Injection Pattern (String Concatenation)",
                            severity=SecuritySeverity.CRITICAL,
                            file_path=rel_path,
                            line_number=idx,
                            snippet=line.strip()[:100],
                            description="SQL query dynamically concatenated with string variables.",
                            fix_suggestion="Pass variables as a query parameter collection to execute().",
                        )
                    )
                # 3. % or .format() formatting in SQL
                elif re.search(
                    r'["\'].*(?:SELECT|INSERT|UPDATE|DELETE).*["\']\s*%\s*[a-zA-Z_(]',
                    line,
                    re.IGNORECASE,
                ) or re.search(
                    r'["\'].*(?:SELECT|INSERT|UPDATE|DELETE).*["\']\.format\(', line, re.IGNORECASE
                ):
                    findings.append(
                        SecurityFinding(
                            check_name="SQL Injection Pattern (String Formatting)",
                            severity=SecuritySeverity.CRITICAL,
                            file_path=rel_path,
                            line_number=idx,
                            snippet=line.strip()[:100],
                            description="SQL query built using string formatting (% or .format()).",
                            fix_suggestion="Use native database driver parameterized bindings.",
                        )
                    )
        return findings

    def _scan_python_auth_and_errors(
        self, path: Path, rel_path: str, content: str
    ) -> list[SecurityFinding]:
        """Detect missing authentication on sensitive routes and leaked internal stack traces."""
        findings = []
        lines = content.splitlines()

        # Check for stack trace leakage in error responses
        for idx, line in enumerate(lines, start=1):
            if "traceback.format_exc()" in line and any(
                k in line for k in ["detail=", "return ", "jsonify", "message="]
            ):
                findings.append(
                    SecurityFinding(
                        check_name="Information Disclosure (Stack Trace Leak)",
                        severity=SecuritySeverity.MEDIUM,
                        file_path=rel_path,
                        line_number=idx,
                        snippet=line.strip()[:100],
                        description="Internal stack trace exposed directly to client responses.",
                        fix_suggestion="Log the exception internally and return a generic error message (e.g. 'Internal Server Error').",
                    )
                )

        # Check for FastAPI / Flask endpoints missing auth decorators in admin/user routes
        if (
            "admin" in rel_path.lower()
            or "secure" in rel_path.lower()
            or "manage" in rel_path.lower()
        ):
            for idx, line in enumerate(lines, start=1):
                if re.search(r"@(?:app|router)\.(?:post|put|delete|patch)\(", line):
                    # Check if next 5 lines contain Depends / auth / token
                    context_window = "\n".join(lines[idx : min(len(lines), idx + 6)])
                    if not any(
                        k in context_window
                        for k in [
                            "Depends",
                            "auth",
                            "token",
                            "Security",
                            "api_key",
                            "get_current_user",
                        ]
                    ):
                        findings.append(
                            SecurityFinding(
                                check_name="Authentication Bypass (Missing Auth Check)",
                                severity=SecuritySeverity.HIGH,
                                file_path=rel_path,
                                line_number=idx,
                                snippet=line.strip(),
                                description=f"State-changing route in '{rel_path}' lacks authentication dependency/guard.",
                                fix_suggestion="Add authentication dependency (e.g. Depends(get_current_user) or Depends(validate_api_key)).",
                            )
                        )
        return findings

    def _scan_js_dangerous_patterns(self, rel_path: str, content: str) -> list[SecurityFinding]:
        """Detect dangerous JavaScript / Node.js function calls."""
        findings = []
        lines = content.splitlines()

        for idx, line in enumerate(lines, start=1):
            if re.search(r"\beval\s*\(", line):
                findings.append(
                    SecurityFinding(
                        check_name="Dangerous Function (JS eval)",
                        severity=SecuritySeverity.CRITICAL,
                        file_path=rel_path,
                        line_number=idx,
                        snippet=line.strip()[:100],
                        description="JavaScript 'eval()' execution permits arbitrary code execution.",
                        fix_suggestion="Avoid dynamic code evaluation; use JSON.parse() or dedicated parser logic.",
                    )
                )
            if re.search(r"child_process.*(?:exec|execSync)\s*\(", line):
                if not re.search(r"execFile", line):
                    findings.append(
                        SecurityFinding(
                            check_name="Command Injection (child_process.exec)",
                            severity=SecuritySeverity.HIGH,
                            file_path=rel_path,
                            line_number=idx,
                            snippet=line.strip()[:100],
                            description="child_process.exec executes strings inside a shell environment.",
                            fix_suggestion="Use 'execFile' or 'spawn' with parameterized argument arrays.",
                        )
                    )
        return findings

    def _scan_js_injections(self, rel_path: str, content: str) -> list[SecurityFinding]:
        """Detect Cross-Site Scripting (XSS) via unescaped innerHTML or dangerouslySetInnerHTML."""
        findings = []
        lines = content.splitlines()

        for idx, line in enumerate(lines, start=1):
            if ".innerHTML" in line and "=" in line:
                # Flag if assigning dynamic variable or template string
                if re.search(
                    r'\.innerHTML\s*=\s*(?!["\'][\s<a-zA-Z0-9_-]+["\'])[a-zA-Z0-9_$`]', line
                ):
                    findings.append(
                        SecurityFinding(
                            check_name="DOM XSS Pattern (innerHTML)",
                            severity=SecuritySeverity.HIGH,
                            file_path=rel_path,
                            line_number=idx,
                            snippet=line.strip()[:100],
                            description="Unsanitized assignment to .innerHTML enables Cross-Site Scripting (XSS).",
                            fix_suggestion="Use 'textContent', 'innerText', or sanitize HTML with DOMPurify before assignment.",
                        )
                    )
            if "dangerouslySetInnerHTML" in line:
                findings.append(
                    SecurityFinding(
                        check_name="React XSS Pattern (dangerouslySetInnerHTML)",
                        severity=SecuritySeverity.MEDIUM,
                        file_path=rel_path,
                        line_number=idx,
                        snippet=line.strip()[:100],
                        description="Use of dangerouslySetInnerHTML can introduce XSS if input is untrusted.",
                        fix_suggestion="Ensure content is sanitized with DOMPurify or render standard JSX elements.",
                    )
                )
        return findings

    def scan_dependencies(self) -> list[SecurityFinding]:
        """Verify dependencies in requirements.txt and package.json against known CVE database."""
        findings = []

        # 1. Python requirements.txt
        req_file = self.workspace_path / "requirements.txt"
        if req_file.exists():
            for line in req_file.read_text(encoding="utf-8").splitlines():
                cleaned = line.strip()
                if not cleaned or cleaned.startswith("#"):
                    continue
                pkg_name = cleaned.split("==")[0].split(">=")[0].split("<=")[0].strip().lower()
                version = ""
                if "==" in cleaned:
                    version = cleaned.split("==")[1].strip()
                elif "<=" in cleaned:
                    version = cleaned.split("<=")[1].strip()

                if pkg_name in CVE_VULNERABILITY_DB:
                    vuln = CVE_VULNERABILITY_DB[pkg_name]
                    # Check if version is known vulnerable
                    is_vuln = False
                    if version:
                        is_vuln = self._is_version_less_or_equal(
                            version, vuln["max_vulnerable_version"]
                        )
                    elif "==" in cleaned or "<=" in cleaned:
                        is_vuln = True

                    if is_vuln:
                        findings.append(
                            SecurityFinding(
                                check_name="Vulnerable Dependency (CVE)",
                                severity=vuln["severity"],
                                file_path="requirements.txt",
                                snippet=cleaned,
                                description=f"Package '{pkg_name}' version '{version or 'unknown'}' matches {vuln['cve']}: {vuln['description']}",
                                fix_suggestion=f"Upgrade '{pkg_name}' to safe version '{vuln['safe_version']}' or newer.",
                                cve_id=vuln["cve"],
                            )
                        )

        # 2. Node package.json
        pkg_file = self.workspace_path / "package.json"
        if pkg_file.exists():
            try:
                data = json.loads(pkg_file.read_text(encoding="utf-8"))
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                for pkg_name, ver in deps.items():
                    clean_name = pkg_name.lower()
                    clean_ver = ver.replace("^", "").replace("~", "").replace(">=", "").strip()
                    if clean_name in CVE_VULNERABILITY_DB:
                        vuln = CVE_VULNERABILITY_DB[clean_name]
                        if self._is_version_less_or_equal(
                            clean_ver, vuln["max_vulnerable_version"]
                        ):
                            findings.append(
                                SecurityFinding(
                                    check_name="Vulnerable Node Dependency (CVE)",
                                    severity=vuln["severity"],
                                    file_path="package.json",
                                    snippet=f'"{pkg_name}": "{ver}"',
                                    description=f"Package '{pkg_name}' version '{clean_ver}' matches {vuln['cve']}: {vuln['description']}",
                                    fix_suggestion=f"Upgrade '{pkg_name}' to safe version '{vuln['safe_version']}' in package.json.",
                                    cve_id=vuln["cve"],
                                )
                            )
            except Exception as e:
                logger.debug(f"Could not parse package.json for CVE scan: {e}")

        return findings

    def remediate_vulnerable_dependencies(self) -> list[str]:
        """
        Automatically patch vulnerable dependencies in requirements.txt and package.json
        to secure patched versions and generate verified lockfiles.
        """
        remediated = []

        # 1. Remediate Python requirements.txt
        req_file = self.workspace_path / "requirements.txt"
        if req_file.exists():
            lines = req_file.read_text(encoding="utf-8").splitlines()
            new_lines = []
            modified = False

            for line in lines:
                cleaned = line.strip()
                if not cleaned or cleaned.startswith("#"):
                    new_lines.append(line)
                    continue

                pkg_name = cleaned.split("==")[0].split(">=")[0].split("<=")[0].strip().lower()
                version = cleaned.split("==")[1].strip() if "==" in cleaned else ""

                if pkg_name in CVE_VULNERABILITY_DB:
                    vuln = CVE_VULNERABILITY_DB[pkg_name]
                    if not version or self._is_version_less_or_equal(
                        version, vuln["max_vulnerable_version"]
                    ):
                        safe_ver = vuln["safe_version"]
                        new_lines.append(f"{pkg_name}>={safe_ver}")
                        remediated.append(
                            f"Upgraded {pkg_name} to safe version >={safe_ver} (fixes {vuln['cve']})"
                        )
                        modified = True
                        continue
                new_lines.append(line)

            if modified:
                req_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                # Generate updated requirements.lock
                lock_file = self.workspace_path / "requirements.lock"
                lock_lines = [
                    f"{req_line.split('>=')[0]}=={req_line.split('>=')[1]}"
                    if ">=" in req_line
                    else req_line
                    for req_line in new_lines
                    if req_line.strip()
                ]
                lock_file.write_text("\n".join(lock_lines) + "\n", encoding="utf-8")

        # 2. Remediate Node package.json
        pkg_file = self.workspace_path / "package.json"
        if pkg_file.exists():
            try:
                data = json.loads(pkg_file.read_text(encoding="utf-8"))
                modified_pkg = False
                for section in ["dependencies", "devDependencies"]:
                    if section in data:
                        for pkg, ver in list(data[section].items()):
                            clean_pkg = pkg.lower()
                            clean_ver = (
                                ver.replace("^", "").replace("~", "").replace(">=", "").strip()
                            )
                            if clean_pkg in CVE_VULNERABILITY_DB:
                                vuln = CVE_VULNERABILITY_DB[clean_pkg]
                                if self._is_version_less_or_equal(
                                    clean_ver, vuln["max_vulnerable_version"]
                                ):
                                    data[section][pkg] = f"^{vuln['safe_version']}"
                                    remediated.append(
                                        f"Upgraded {pkg} to ^{vuln['safe_version']} (fixes {vuln['cve']})"
                                    )
                                    modified_pkg = True
                if modified_pkg:
                    pkg_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception as e:
                logger.debug(f"Could not remediate package.json: {e}")

        return remediated

    def format_feedback_for_regeneration(self, report: SecurityScanReport) -> str:
        """Construct targeted remediation instructions for AI-Universe re-generation attempts."""
        feedback_lines = [
            "SECURITY VULNERABILITIES DETECTED — RE-SYNTHESIS MANDATORY:",
            "Your previous code output contained critical/high security issues that must be remediated:",
        ]
        for idx, finding in enumerate(report.findings, start=1):
            if finding.severity in [SecuritySeverity.CRITICAL, SecuritySeverity.HIGH]:
                feedback_lines.append(
                    f"{idx}. [{finding.severity}] {finding.check_name} in `{finding.file_path}`"
                    f"{f' (line {finding.line_number})' if finding.line_number else ''}:\n"
                    f"   - Issue: {finding.description}\n"
                    f"   - Remediation: {finding.fix_suggestion}"
                )
        feedback_lines.append(
            "\nPlease output complete, remediated code adhering strictly to security best practices."
        )
        return "\n".join(feedback_lines)

    @staticmethod
    def _is_version_less_or_equal(v1: str, v2: str) -> bool:
        """Simple semver comparison."""
        try:
            p1 = [int(x) for x in re.findall(r"\d+", v1)]
            p2 = [int(x) for x in re.findall(r"\d+", v2)]
            # Pad with zeros
            while len(p1) < 3:
                p1.append(0)
            while len(p2) < 3:
                p2.append(0)
            return p1 <= p2
        except Exception:
            return v1 == v2
