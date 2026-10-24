"""
Forge/code_reviewer.py — Forge Automated Code Reviewer.

Extends Forge's capabilities with:
1. Automated Code Review: analyze code for bugs, patterns, and style
2. Security Audit: deep security analysis of code
3. Performance Review: identify performance bottlenecks
4. Pattern Detection: detect code patterns and anti-patterns
5. Suggestion Engine: generate improvement suggestions
6. PR Analysis: analyze pull requests for quality
"""
from __future__ import annotations

import ast
import re
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CodeIssue:
    """A code issue found during review."""
    file_path: str
    line: int
    column: int
    severity: str  # critical, warning, info
    category: str  # bug, security, performance, style, pattern
    message: str
    suggestion: str = ""
    code_snippet: str = ""


@dataclass
class ReviewResult:
    """Result of a code review."""
    file_path: str
    issues: list[CodeIssue]
    score: float  # 0-100
    metrics: dict[str, float]
    recommendations: list[str]


@dataclass
class PRAnalysis:
    """Pull request analysis."""
    pr_id: str
    title: str
    files_changed: int
    lines_added: int
    lines_removed: int
    issues: list[CodeIssue]
    review_score: float
    risk_level: str  # low, medium, high
    merge_recommendation: str


@dataclass
class PatternDetection:
    """Pattern detection result."""
    pattern_type: str  # good_pattern, anti_pattern
    name: str
    description: str
    occurrences: list[dict]
    impact: str  # positive, negative


class CodeReviewer:
    """Automated code review engine."""

    ANTI_PATTERNS = {
        "long_function": {
            "description": "Function exceeds 50 lines",
            "impact": "negative",
            "threshold": 50,
        },
        "deep_nesting": {
            "description": "Nesting depth exceeds 4 levels",
            "impact": "negative",
            "threshold": 4,
        },
        "long_parameter_list": {
            "description": "Function has more than 5 parameters",
            "impact": "negative",
            "threshold": 5,
        },
        "magic_number": {
            "description": "Hardcoded magic number",
            "impact": "negative",
            "threshold": 0,
        },
        "bare_except": {
            "description": "Bare except clause",
            "impact": "negative",
            "threshold": 0,
        },
        "mutable_default": {
            "description": "Mutable default argument",
            "impact": "negative",
            "threshold": 0,
        },
    }

    GOOD_PATTERNS = {
        "type_hints": {
            "description": "Function has type hints",
            "impact": "positive",
        },
        "docstring": {
            "description": "Function has docstring",
            "impact": "positive",
        },
        "try_except": {
            "description": "Proper error handling",
            "impact": "positive",
        },
        "early_return": {
            "description": "Early return pattern",
            "impact": "positive",
        },
    }

    def __init__(self):
        self._reviews: dict[str, ReviewResult] = {}
        self._patterns: list[PatternDetection] = []

    # ── Code Analysis ──────────────────────────────────────────────────────

    def review_file(
        self,
        file_path: str,
        code: str,
    ) -> ReviewResult:
        """Review a single file."""
        issues: list[CodeIssue] = []

        try:
            tree = ast.parse(code)
            issues.extend(self._analyze_ast(file_path, tree))
        except SyntaxError as e:
            issues.append(CodeIssue(
                file_path=file_path,
                line=e.lineno or 1,
                column=0,
                severity="critical",
                category="bug",
                message=f"Syntax error: {e.msg}",
                code_snippet=code[max(0, (e.lineno or 1) - 3):(e.lineno or 1) + 3],
            ))

        # Literally check for anti-patterns
        issues.extend(self._check_literal_patterns(file_path, code))

        # Security checks
        issues.extend(self._check_security(file_path, code))

        # Performance checks
        issues.extend(self._check_performance(file_path, code))

        # Calculate score
        score = self._calculate_score(issues)

        # Generate recommendations
        recommendations = self._generate_recommendations(issues)

        # Calculate metrics
        metrics = self._calculate_metrics(code, issues)

        result = ReviewResult(
            file_path=file_path,
            issues=issues,
            score=score,
            metrics=metrics,
            recommendations=recommendations,
        )

        self._reviews[file_path] = result
        return result

    def _analyze_ast(self, file_path: str, tree: ast.AST) -> list[CodeIssue]:
        """Analyze AST for issues."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check function length
                func_lines = node.end_lineno - node.lineno if node.end_lineno else 0
                if func_lines > 50:
                    issues.append(CodeIssue(
                        file_path=file_path,
                        line=node.lineno,
                        column=0,
                        severity="warning",
                        category="pattern",
                        message=f"Function '{node.name}' is {func_lines} lines long",
                        suggestion="Consider breaking this function into smaller functions",
                    ))

                # Check parameter count
                if len(node.args.args) > 5:
                    issues.append(CodeIssue(
                        file_path=file_path,
                        line=node.lineno,
                        column=0,
                        severity="warning",
                        category="pattern",
                        message=f"Function '{node.name}' has {len(node.args.args)} parameters",
                        suggestion="Consider using a configuration object or dataclass",
                    ))

                # Check for mutable defaults
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        issues.append(CodeIssue(
                            file_path=file_path,
                            line=node.lineno,
                            column=0,
                            severity="critical",
                            category="bug",
                            message=f"Function '{node.name}' has mutable default argument",
                            suggestion="Use None as default and create new object inside function",
                        ))

                # Check for docstring
                if not ast.get_docstring(node):
                    issues.append(CodeIssue(
                        file_path=file_path,
                        line=node.lineno,
                        column=0,
                        severity="info",
                        category="style",
                        message=f"Function '{node.name}' lacks docstring",
                    ))

                # Check for type hints
                if not node.returns:
                    issues.append(CodeIssue(
                        file_path=file_path,
                        line=node.lineno,
                        column=0,
                        severity="info",
                        category="style",
                        message=f"Function '{node.name}' lacks return type hint",
                    ))

            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    issues.append(CodeIssue(
                        file_path=file_path,
                        line=node.lineno,
                        column=0,
                        severity="warning",
                        category="pattern",
                        message="Bare except clause",
                        suggestion="Catch specific exceptions instead",
                    ))

        return issues

    def _check_literal_patterns(self, file_path: str, code: str) -> list[CodeIssue]:
        """Check for literal anti-patterns."""
        issues = []

        # Magic numbers (simplified)
        for i, line in enumerate(code.split("\n"), 1):
            # Skip common cases
            if any(skip in line for skip in ["0", "1", "True", "False", "None"]):
                continue

            # Find numbers not assigned to variables
            numbers = re.findall(r'(?<![\w.])\d+\.?\d*(?![\w])', line)
            for num in numbers:
                if float(num) not in (0, 1, 2, 10, 100) and not any(
                    var in line for var in ["=", ":", "import", "from", "def", "class"]
                ):
                    issues.append(CodeIssue(
                        file_path=file_path,
                        line=i,
                        column=line.index(num),
                        severity="info",
                        category="pattern",
                        message=f"Magic number {num} found",
                        suggestion="Consider defining this as a named constant",
                        code_snippet=line.strip(),
                    ))

        return issues

    def _check_security(self, file_path: str, code: str) -> list[CodeIssue]:
        """Check for security issues."""
        issues = []

        for i, line in enumerate(code.split("\n"), 1):
            line_lower = line.lower()

            # SQL injection risk
            if "execute" in line_lower and "{" in line:
                issues.append(CodeIssue(
                    file_path=file_path,
                    line=i,
                    column=0,
                    severity="critical",
                    category="security",
                    message="Possible SQL injection via string formatting",
                    suggestion="Use parameterized queries",
                    code_snippet=line.strip(),
                ))

            # Eval usage
            if "eval(" in line_lower or "exec(" in line_lower:
                issues.append(CodeIssue(
                    file_path=file_path,
                    line=i,
                    column=0,
                    severity="critical",
                    category="security",
                    message="Use of eval()/exec() detected",
                    suggestion="Avoid eval()/exec() - use safer alternatives",
                    code_snippet=line.strip(),
                ))

            # Hardcoded secrets
            if any(keyword in line_lower for keyword in ["password", "secret", "api_key", "token"]):
                if "=" in line and not any(skip in line_lower for skip in ["os.environ", "getenv", "config"]):
                    issues.append(CodeIssue(
                        file_path=file_path,
                        line=i,
                        column=0,
                        severity="critical",
                        category="security",
                        message="Possible hardcoded secret",
                        suggestion="Use environment variables or secret management",
                        code_snippet=line.strip(),
                    ))

            # Debug mode
            if "debug = true" in line_lower or "debug=true" in line_lower:
                issues.append(CodeIssue(
                    file_path=file_path,
                    line=i,
                    column=0,
                    severity="warning",
                    category="security",
                    message="Debug mode enabled",
                    suggestion="Disable debug mode in production",
                    code_snippet=line.strip(),
                ))

        return issues

    def _check_performance(self, file_path: str, code: str) -> list[CodeIssue]:
        """Check for performance issues."""
        issues = []

        for i, line in enumerate(code.split("\n"), 1):
            line_lower = line.lower()

            # List comprehension in loop
            if "for " in line_lower and "in range(" in line_lower:
                issues.append(CodeIssue(
                    file_path=file_path,
                    line=i,
                    column=0,
                    severity="info",
                    category="performance",
                    message="Potential performance issue: loop with range()",
                    suggestion="Consider using list comprehension or vectorized operations",
                    code_snippet=line.strip(),
                ))

            # String concatenation in loop
            if "+=" in line and "str" in line_lower:
                issues.append(CodeIssue(
                    file_path=file_path,
                    line=i,
                    column=0,
                    severity="info",
                    category="performance",
                    message="String concatenation in loop",
                    suggestion="Consider using join() or list accumulation",
                    code_snippet=line.strip(),
                ))

        return issues

    def _calculate_score(self, issues: list[CodeIssue]) -> float:
        """Calculate review score."""
        score = 100.0

        for issue in issues:
            if issue.severity == "critical":
                score -= 20
            elif issue.severity == "warning":
                score -= 10
            elif issue.severity == "info":
                score -= 5

        return max(0.0, score)

    def _generate_recommendations(self, issues: list[CodeIssue]) -> list[str]:
        """Generate improvement recommendations."""
        recommendations = []

        categories = set(issue.category for issue in issues)

        if "security" in categories:
            recommendations.append("Address security issues immediately before deployment")

        if "bug" in categories:
            recommendations.append("Fix identified bugs before merging")

        if any(i.category == "pattern" and i.severity == "warning" for i in issues):
            recommendations.append("Refactor code to follow best practices")

        if any(i.category == "performance" for i in issues):
            recommendations.append("Optimize performance bottlenecks")

        if any(i.category == "style" for i in issues):
            recommendations.append("Improve code style for better readability")

        return recommendations

    def _calculate_metrics(self, code: str, issues: list[CodeIssue]) -> dict[str, float]:
        """Calculate code metrics."""
        lines = len(code.split("\n"))

        critical = sum(1 for i in issues if i.severity == "critical")
        warnings = sum(1 for i in issues if i.severity == "warning")
        info = sum(1 for i in issues if i.severity == "info")

        return {
            "lines": lines,
            "issues_per_line": (critical + warnings + info) / max(1, lines),
            "critical_count": critical,
            "warning_count": warnings,
            "info_count": info,
        }

    # ── PR Analysis ─────────────────────────────────────────────────────────

    def analyze_pr(
        self,
        pr_id: str,
        title: str,
        files: dict[str, str],
    ) -> PRAnalysis:
        """Analyze a pull request."""
        all_issues = []
        total_lines = 0

        for file_path, code in files.items():
            result = self.review_file(file_path, code)
            all_issues.extend(result.issues)
            total_lines += result.metrics.get("lines", 0)

        # Calculate risk level
        critical = sum(1 for i in all_issues if i.severity == "critical")
        if critical > 0:
            risk = "high"
        elif any(i.severity == "warning" for i in all_issues):
            risk = "medium"
        else:
            risk = "low"

        # Merge recommendation
        if risk == "high":
            recommendation = "Do not merge - address critical issues"
        elif risk == "medium":
            recommendation = "Merge with caution - address warnings"
        else:
            recommendation = "Ready to merge"

        return PRAnalysis(
            pr_id=pr_id,
            title=title,
            files_changed=len(files),
            lines_added=sum(len(c.split("\n")) for c in files.values()),
            lines_removed=0,
            issues=all_issues,
            review_score=sum(
                self._calculate_score(f_issues)
                for f_issues in [result.issues]
                for result in [self._reviews.get(fp, ReviewResult(fp, [], 100, {}, []))]
            ) / max(1, len(files)) if files else 100,
            risk_level=risk,
            merge_recommendation=recommendation,
        )

    # ── Pattern Detection ───────────────────────────────────────────────────

    def detect_patterns(
        self,
        code: str,
    ) -> list[PatternDetection]:
        """Detect code patterns."""
        patterns = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return patterns

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for good patterns
                has_type_hints = node.returns is not None
                has_docstring = ast.get_docstring(node) is not None

                if has_type_hints:
                    patterns.append(PatternDetection(
                        pattern_type="good_pattern",
                        name="type_hints",
                        description=f"Function '{node.name}' has type hints",
                        occurrences=[{"line": node.lineno}],
                        impact="positive",
                    ))

                if has_docstring:
                    patterns.append(PatternDetection(
                        pattern_type="good_pattern",
                        name="docstring",
                        description=f"Function '{node.name}' has docstring",
                        occurrences=[{"line": node.lineno}],
                        impact="positive",
                    ))

        # Check for anti-patterns
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            if "except:" in line or "except Exception:" in line:
                patterns.append(PatternDetection(
                    pattern_type="anti_pattern",
                    name="bare_except",
                    description=f"Line {i}: Bare except clause",
                    occurrences=[{"line": i}],
                    impact="negative",
                ))

        self._patterns = patterns
        return patterns

    # ── Reporting ──────────────────────────────────────────────────────────

    def get_review_report(self) -> dict[str, Any]:
        """Generate a review report."""
        total_files = len(self._reviews)
        avg_score = sum(r.score for r in self._reviews.values()) / max(1, total_files)
        total_issues = sum(len(r.issues) for r in self._reviews.values())

        return {
            "total_files_reviewed": total_files,
            "average_score": avg_score,
            "total_issues": total_issues,
            "patterns_detected": len(self._patterns),
        }
