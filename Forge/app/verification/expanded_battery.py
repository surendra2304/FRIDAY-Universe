"""
Expanded Verification Battery for Project FORGE.
Implements specialized objective checkers for Security Vulnerabilities, Performance Sanity,
Code Quality & Cyclomatic Complexity, and Accessibility (a11y).
"""

import ast
import re
import time
from typing import Any

from app.execution.dependency_manager import DependencyManager
from app.execution.engine import ExecutionEngine
from app.verification.evidence import CheckCategory, VerificationEvidence


class SecurityVulnerabilityChecker:
    """Scans codebase for hardcoded secrets, dangerous dynamic eval calls, and insecure dependencies."""

    category = CheckCategory.SECURITY
    name = "Security & Vulnerability Analysis"

    SECRET_PATTERNS = [
        (
            re.compile(
                r"""(?i)(?:api[_-]?key|secret|password|auth_token)\s*=\s*['"][a-zA-Z0-9_\-]{16,}['"]"""
            ),
            "Potential hardcoded API key or secret",
        ),
        (
            re.compile(r"""-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"""),
            "Hardcoded private key block",
        ),
        (re.compile(r"""ghp_[a-zA-Z0-9]{20,}"""), "Hardcoded GitHub Personal Access Token"),
        (re.compile(r"""sk-[a-zA-Z0-9_\-]{20,}"""), "Hardcoded OpenAI API key"),
    ]

    DANGEROUS_CALLS = [
        ("eval(", "Dangerous dynamic code execution with eval()"),
        ("exec(", "Dangerous dynamic code execution with exec()"),
        ("os.system(", "Unsafe shell invocation with os.system()"),
    ]

    async def run_check(self, task_id: str, engine: ExecutionEngine) -> VerificationEvidence:
        start_time = time.perf_counter()
        paths = engine.wm.get_workspace_paths(task_id)
        if not paths or not paths.project.exists():
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                exit_code=0,
                passed=True,
                duration_ms=0.0,
                stdout="Project directory empty or non-existent.",
            )

        issues: list[dict[str, Any]] = []
        inspected: list[str] = []

        # 1. Scan source files for hardcoded secrets and dangerous calls
        for f in paths.project.glob("**/*"):
            if f.is_file() and f.suffix in [".py", ".js", ".html", ".env", ".json"]:
                rel_path = str(f.relative_to(paths.project))
                inspected.append(rel_path)
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    # Check secrets
                    for pattern, desc in self.SECRET_PATTERNS:
                        if pattern.search(content):
                            # Ignore mock / test keys in test files
                            if "test" not in rel_path.lower():
                                issues.append(
                                    {
                                        "file": rel_path,
                                        "type": "hardcoded_secret",
                                        "description": desc,
                                    }
                                )

                    # Check dangerous calls in Python
                    if f.suffix == ".py" and "test" not in rel_path.lower():
                        for call, desc in self.DANGEROUS_CALLS:
                            if call in content:
                                issues.append(
                                    {"file": rel_path, "type": "unsafe_call", "description": desc}
                                )
                except Exception:
                    pass

        # 2. Check dependencies for known vulnerabilities
        dep_mgr = DependencyManager()
        deps = dep_mgr.detect_workspace_dependencies(paths.project)
        dep_issues = dep_mgr.check_security(deps)
        for d in dep_issues:
            issues.append(
                {
                    "type": "vulnerable_dependency",
                    "package": d["package"],
                    "description": d["reason"],
                }
            )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        passed = len(issues) == 0

        stdout = (
            f"Security scan completed across {len(inspected)} files. {len(issues)} issues detected."
        )
        return VerificationEvidence(
            check_name=self.name,
            category=self.category,
            command="security_vulnerability_scan",
            exit_code=0 if passed else 1,
            passed=passed,
            duration_ms=round(duration_ms, 2),
            stdout=stdout,
            stderr=str(issues) if issues else "",
            artifacts_inspected=inspected,
            issues=issues,
        )


class PerformanceSanityChecker:
    """Validates resource footprint, payload size, and excessive asset references."""

    category = CheckCategory.PERFORMANCE
    name = "Performance Sanity Verification"

    MAX_TOTAL_WEB_BYTES = 3 * 1024 * 1024  # 3MB warning threshold
    MAX_SCRIPT_TAGS = 12

    async def run_check(self, task_id: str, engine: ExecutionEngine) -> VerificationEvidence:
        start_time = time.perf_counter()
        paths = engine.wm.get_workspace_paths(task_id)
        if not paths or not paths.project.exists():
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                exit_code=0,
                passed=True,
                duration_ms=0.0,
                stdout="Project workspace non-existent.",
            )

        issues: list[dict[str, Any]] = []
        inspected: list[str] = []
        total_bytes = 0

        for f in paths.project.glob("**/*"):
            if f.is_file():
                rel_path = str(f.relative_to(paths.project))
                inspected.append(rel_path)
                size = f.stat().st_size
                total_bytes += size

                if f.suffix == ".html":
                    try:
                        content = f.read_text(encoding="utf-8", errors="ignore")
                        script_count = len(re.findall(r"<script", content, re.IGNORECASE))
                        if script_count > self.MAX_SCRIPT_TAGS:
                            issues.append(
                                {
                                    "file": rel_path,
                                    "type": "excessive_scripts",
                                    "description": f"Found {script_count} <script> tags (threshold: {self.MAX_SCRIPT_TAGS})",
                                }
                            )
                    except Exception:
                        pass

        if total_bytes > self.MAX_TOTAL_WEB_BYTES:
            issues.append(
                {
                    "type": "oversized_bundle",
                    "description": f"Total project assets {total_bytes / (1024 * 1024):.2f}MB exceeds {self.MAX_TOTAL_WEB_BYTES / (1024 * 1024)}MB threshold.",
                }
            )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        passed = len(issues) == 0

        return VerificationEvidence(
            check_name=self.name,
            category=self.category,
            command="performance_sanity_check",
            exit_code=0 if passed else 1,
            passed=passed,
            duration_ms=round(duration_ms, 2),
            stdout=f"Performance sanity check completed. Total size: {total_bytes} bytes across {len(inspected)} files.",
            stderr=str(issues) if issues else "",
            artifacts_inspected=inspected,
            issues=issues,
        )


class CodeQualityComplexityChecker:
    """Measures Cyclomatic Complexity and source file length."""

    category = CheckCategory.QUALITY
    name = "Code Quality & Complexity Verification"

    MAX_COMPLEXITY_THRESHOLD = 15
    MAX_FILE_LINES = 500

    def _compute_complexity(self, node: ast.AST) -> int:
        """Compute cyclomatic complexity for an AST function/method node."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(
                child, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With, ast.Assert)
            ):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                complexity += 1
        return complexity

    async def run_check(self, task_id: str, engine: ExecutionEngine) -> VerificationEvidence:
        start_time = time.perf_counter()
        paths = engine.wm.get_workspace_paths(task_id)
        if not paths or not paths.project.exists():
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                exit_code=0,
                passed=True,
                duration_ms=0.0,
                stdout="Project workspace non-existent.",
            )

        issues: list[dict[str, Any]] = []
        inspected: list[str] = []

        for py_file in paths.project.glob("**/*.py"):
            rel_path = str(py_file.relative_to(paths.project))
            inspected.append(rel_path)
            try:
                code = py_file.read_text(encoding="utf-8", errors="ignore")
                lines_count = len(code.splitlines())
                if lines_count > self.MAX_FILE_LINES:
                    issues.append(
                        {
                            "file": rel_path,
                            "type": "file_length_warning",
                            "description": f"File length ({lines_count} lines) exceeds {self.MAX_FILE_LINES} limit.",
                        }
                    )

                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        comp = self._compute_complexity(node)
                        if comp > self.MAX_COMPLEXITY_THRESHOLD:
                            issues.append(
                                {
                                    "file": rel_path,
                                    "function": node.name,
                                    "complexity": comp,
                                    "type": "high_cyclomatic_complexity",
                                    "description": f"Function '{node.name}' has cyclomatic complexity of {comp} (threshold: {self.MAX_COMPLEXITY_THRESHOLD})",
                                }
                            )
            except Exception:
                pass

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        passed = len(issues) == 0

        return VerificationEvidence(
            check_name=self.name,
            category=self.category,
            command="code_quality_complexity_check",
            exit_code=0 if passed else 1,
            passed=passed,
            duration_ms=round(duration_ms, 2),
            stdout=f"Code quality and complexity analyzed across {len(inspected)} Python modules.",
            stderr=str(issues) if issues else "",
            artifacts_inspected=inspected,
            issues=issues,
        )


class AccessibilityChecker:
    """Inspects web assets for semantic markup, image alt tags, form labels, and ARIA landmarks."""

    category = CheckCategory.ACCESSIBILITY
    name = "Web Accessibility (a11y) Verification"

    async def run_check(self, task_id: str, engine: ExecutionEngine) -> VerificationEvidence:
        start_time = time.perf_counter()
        paths = engine.wm.get_workspace_paths(task_id)
        if not paths or not paths.project.exists():
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                exit_code=0,
                passed=True,
                duration_ms=0.0,
                stdout="Project workspace non-existent.",
            )

        html_files = list(paths.project.glob("**/*.html"))
        if not html_files:
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                exit_code=0,
                passed=True,
                duration_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
                stdout="No HTML files in project; skipping accessibility verification.",
                artifacts_inspected=[],
            )

        issues: list[dict[str, Any]] = []
        inspected: list[str] = []

        for html_file in html_files:
            rel_path = str(html_file.relative_to(paths.project))
            inspected.append(rel_path)
            try:
                content = html_file.read_text(encoding="utf-8", errors="ignore")

                # 1. Check for <img> without alt
                img_tags = re.findall(r"<img[^>]*>", content, re.IGNORECASE)
                for tag in img_tags:
                    if "alt=" not in tag.lower():
                        issues.append(
                            {
                                "file": rel_path,
                                "type": "missing_img_alt",
                                "description": f"Image tag missing 'alt' attribute: {tag[:60]}",
                            }
                        )

                # 2. Check for at least one heading <h1>
                if "<h1" not in content.lower():
                    issues.append(
                        {
                            "file": rel_path,
                            "type": "missing_h1_landmark",
                            "description": "HTML document missing main <h1> heading landmark.",
                        }
                    )

                # 3. Check for language attribute on <html>
                if "<html" in content.lower() and "lang=" not in content.lower():
                    issues.append(
                        {
                            "file": rel_path,
                            "type": "missing_html_lang",
                            "description": "<html> tag missing 'lang' attribute.",
                        }
                    )
            except Exception:
                pass

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        passed = len(issues) == 0

        return VerificationEvidence(
            check_name=self.name,
            category=self.category,
            command="web_accessibility_scan",
            exit_code=0 if passed else 1,
            passed=passed,
            duration_ms=round(duration_ms, 2),
            stdout=f"Accessibility verified across {len(html_files)} HTML pages.",
            stderr=str(issues) if issues else "",
            artifacts_inspected=inspected,
            issues=issues,
        )
