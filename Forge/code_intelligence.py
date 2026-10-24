"""
Forge/code_intelligence.py — Forge Code Intelligence Engine.

Extends Forge's capabilities with:
1. Code Complexity Analysis: analyze code complexity metrics
2. Architecture Pattern Detection: detect architectural patterns
3. Code Health Scoring: score code health
4. Dependency Analysis: analyze code dependencies
5. Code Duplication Detection: detect duplicated code
6. Technical Debt Assessment: assess technical debt
7. Security Vulnerability Scanning: scan for security issues
8. Code Documentation Generation: generate documentation
"""
from __future__ import annotations

import ast
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class ComplexityMetrics:
    """Code complexity metrics."""
    file: str
    cyclomatic_complexity: float
    cognitive_complexity: float
    lines_of_code: int
    branche_count: int
    function_count: int
    nesting_depth: int
    maintainability_index: float
    risk_level: str  # low, medium, high


@dataclass
class ArchitecturePattern:
    """Detected architecture pattern."""
    pattern: str  # mvc, repository, singleton, observer, factory, strategy
    confidence: float
    description: str
    files: list[str]
    recommendation: str = ""


@dataclass
class CodeHealthScore:
    """Code health score."""
    file: str
    score: float  # 0-100
    grade: str  # A, B, C, D, F
    factors: dict[str, float]
    issues: list[str]
    recommendations: list[str]


@dataclass
class DependencyNode:
    """A dependency node."""
    name: str
    type: str  # module, class, function
    dependencies: list[str]
    dependents: list[str]
    depth: int
    is_leaf: bool = False
    is_root: bool = False


@dataclass
class Duplication:
    """Detected code duplication."""
    file_a: str
    file_b: str
    similarity: float
    shared_lines: int
    type: str  # exact, near-exact, cloned
    description: str


@dataclass
class TechnicalDebt:
    """Technical debt assessment."""
    category: str  # complexity, duplication, testing, documentation, security
    severity: str  # low, medium, high, critical
    description: str
    effort_to_fix: float  # estimated hours
    impact: str
    remediation: str


@dataclass
class SecurityVulnerability:
    """Detected security vulnerability."""
    vulnerability_id: str
    type: str  # injection, XSS, auth, crypto, etc.
    severity: str
    file: str
    line: int
    description: str
    remediation: str
    cwe: str = ""


@dataclass
class Documentation:
    """Generated documentation."""
    file: str
    summary: str
    classes: list[dict]
    functions: list[dict]
    modules: list[str]
    dependencies: list[str]


class CodeIntelligenceEngine:
    """Code intelligence engine."""

    def __init__(self):
        self._complexity: dict[str, ComplexityMetrics] = {}
        self._patterns: list[ArchitecturePattern] = []
        self._health: dict[str, CodeHealthScore] = {}
        self._dependencies: dict[str, DependencyNode] = {}
        self._duplications: list[Duplication] = []
        self._debt: list[TechnicalDebt] = []
        self._vulnerabilities: list[SecurityVulnerability] = []
        self._docs: dict[str, Documentation] = {}

    # ── Code Complexity Analysis ─────────────────────────────────────────

    def analyze_complexity(
        self,
        file_path: str,
        source_code: str,
    ) -> ComplexityMetrics:
        """Analyze code complexity."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return ComplexityMetrics(
                file=file_path,
                cyclomatic_complexity=0,
                cognitive_complexity=0,
                lines_of_code=len(source_code.splitlines()),
                branche_count=0,
                function_count=0,
                nesting_depth=0,
                maintainability_index=0,
                risk_level="high",
            )

        # Cyclomatic complexity
        branches = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                branches += 1
            elif isinstance(node, ast.BoolOp):
                branches += len(node.values) - 1

        cyclomatic = branches + 1

        # Cognitive complexity (simplified)
        cognitive = cyclomatic

        # Lines of code
        loc = len(source_code.splitlines())

        # Branch count
        branche_count = branches

        # Function count
        function_count = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        )

        # Nesting depth
        max_depth = 0
        def _nesting(node, depth=0):
            nonlocal max_depth
            max_depth = max(max_depth, depth)
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.Try)):
                    _nesting(child, depth + 1)
                else:
                    _nesting(child, depth)
        _nesting(tree)

        # Maintainability index
        mi = max(0, 171 - 5.2 * cyclomatic - 0.23 * loc - 16.2 * math.log(max(1, function_count)))
        mi = mi * 100 / 171 if mi > 0 else 0

        # Risk level
        if cyclomatic > 20 or mi < 20:
            risk = "high"
        elif cyclomatic > 10 or mi < 40:
            risk = "medium"
        else:
            risk = "low"

        metrics = ComplexityMetrics(
            file=file_path,
            cyclomatic_complexity=cyclomatic,
            cognitive_complexity=cognitive,
            lines_of_code=loc,
            branche_count=branche_count,
            function_count=function_count,
            nesting_depth=max_depth,
            maintainability_index=mi,
            risk_level=risk,
        )

        self._complexity[file_path] = metrics
        return metrics

    # ── Architecture Pattern Detection ───────────────────────────────────

    def detect_patterns(
        self,
        source_code: str,
        file_path: str = "",
    ) -> list[ArchitecturePattern]:
        """Detect architecture patterns."""
        patterns = []

        # Check for MVC pattern
        if any(
            keyword in source_code.lower()
            for keyword in ["controller", "model", "view", "template"]
        ):
            patterns.append(ArchitecturePattern(
                pattern="MVC",
                confidence=0.7,
                description="Model-View-Controller pattern detected",
                files=[file_path],
                recommendation="Good separation of concerns",
            ))

        # Check for Repository pattern
        if any(
            keyword in source_code.lower()
            for keyword in ["repository", "repo", "dao", "data_access"]
        ):
            patterns.append(ArchitecturePattern(
                pattern="Repository",
                confidence=0.6,
                description="Repository pattern detected for data access",
                files=[file_path],
                recommendation="Ensures clean data access layer",
            ))

        # Check for Singleton
        if any(
            keyword in source_code.lower()
            for keyword in ["singleton", "_instance", "get_instance", "getinstance"]
        ):
            patterns.append(ArchitecturePattern(
                pattern="Singleton",
                confidence=0.6,
                description="Singleton pattern detected",
                files=[file_path],
                recommendation="Consider if singleton is necessary; can introduce testability issues",
            ))

        # Check for Observer
        if any(
            keyword in source_code.lower()
            for keyword in ["observer", "subscribe", "notify", "listener", "listener"]
        ):
            patterns.append(ArchitecturePattern(
                pattern="Observer",
                confidence=0.6,
                description="Observer pattern detected",
                files=[file_path],
                recommendation="Good for event-driven architecture",
            ))

        # Check for Factory
        if any(
            keyword in source_code.lower()
            for keyword in ["factory", "create", "produce", "build"]
        ) and "class" in source_code.lower():
            patterns.append(ArchitecturePattern(
                pattern="Factory",
                confidence=0.5,
                description="Factory pattern detected",
                files=[file_path],
                recommendation="Good for object creation abstraction",
            ))

        # Check for Strategy
        if any(
            keyword in source_code.lower()
            for keyword in ["strategy", "algorithm", "policy"]
        ):
            patterns.append(ArchitecturePattern(
                pattern="Strategy",
                confidence=0.5,
                description="Strategy pattern detected",
                files=[file_path],
                recommendation="Good for interchangeable algorithms",
            ))

        self._patterns.extend(patterns)
        return patterns

    # ── Code Health Scoring ──────────────────────────────────────────────

    def score_code_health(
        self,
        file_path: str,
        source_code: str,
    ) -> CodeHealthScore:
        """Score code health."""
        # Analyze complexity
        complexity = self.analyze_complexity(file_path, source_code)

        # Score factors
        factors = {}
        factors["complexity"] = max(0, 100 - complexity.cyclomatic_complexity * 5)
        factors["maintainability"] = complexity.maintainability_index
        factors["testability"] = 100.0 if complexity.function_count < 20 else max(0, 100 - (complexity.function_count - 20) * 2)
        factors["documentation"] = 50.0  # Default, needs actual doc analysis
        factors["security"] = 80.0  # Default, needs actual security scan

        # Overall score
        score = sum(factors.values()) / len(factors)

        # Grade
        if score >= 90:
            grade = "A"
        elif score >= 80:
            grade = "B"
        elif score >= 70:
            grade = "C"
        elif score >= 50:
            grade = "D"
        else:
            grade = "F"

        # Issues
        issues = []
        if complexity.cyclomatic_complexity > 15:
            issues.append(f"High cyclomatic complexity ({complexity.cyclomatic_complexity})")
        if complexity.maintainability_index < 30:
            issues.append(f"Low maintainability index ({complexity.maintainability_index:.1f})")
        if complexity.nesting_depth > 4:
            issues.append(f"Deep nesting ({complexity.nesting_depth} levels)")

        # Recommendations
        recommendations = []
        if complexity.cyclomatic_complexity > 15:
            recommendations.append("Refactor into smaller functions")
        if complexity.maintainability_index < 30:
            recommendations.append("Improve code structure and readability")
        if complexity.nesting_depth > 4:
            recommendations.append("Reduce nesting with early returns or guard clauses")

        health = CodeHealthScore(
            file=file_path,
            score=score,
            grade=grade,
            factors=factors,
            issues=issues,
            recommendations=recommendations,
        )

        self._health[file_path] = health
        return health

    # ── Dependency Analysis ──────────────────────────────────────────────

    def analyze_dependencies(
        self,
        source_code: str,
        file_path: str,
    ) -> DependencyNode:
        """Analyze code dependencies."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return DependencyNode(name=file_path, type="file", dependencies=[], dependents=[])

        dependencies = []

        # Extract imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    dependencies.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    dependencies.append(node.module)

        # Extract class/function definitions
        definitions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                definitions.append(node.name)

        return DependencyNode(
            name=file_path,
            type="module",
            dependencies=dependencies,
            dependents=[],
            depth=0,
            is_leaf=len(dependencies) == 0,
            is_root=len(definitions) > 0,
        )

    # ── Code Duplication Detection ───────────────────────────────────────

    def detect_duplication(
        self,
        files: dict[str, str],
    ) -> list[Duplication]:
        """Detect code duplication across files."""
        duplications = []
        file_names = list(files.keys())

        for i, file_a in enumerate(file_names):
            lines_a = set(files[file_a].splitlines())

            for file_b in file_names[i+1:]:
                lines_b = set(files[file_b].splitlines())

                shared = lines_a & lines_b
                similarity = len(shared) / max(1, min(len(lines_a), len(lines_b)))

                if similarity > 0.3 and len(shared) > 10:
                    duplication_type = (
                        "exact" if similarity > 0.8 else
                        "near-exact" if similarity > 0.5 else
                        "cloned"
                    )

                    duplications.append(Duplication(
                        file_a=file_a,
                        file_b=file_b,
                        similarity=similarity,
                        shared_lines=len(shared),
                        type=duplication_type,
                        description=f"{len(shared)} shared lines ({similarity:.0%} similarity)",
                    ))

        self._duplications.extend(duplications)
        return sorted(duplications, key=lambda d: -d.similarity)

    # ── Technical Debt Assessment ───────────────────────────────────────

    def assess_technical_debt(
        self,
        health: CodeHealthScore,
        complexity: ComplexityMetrics,
        duplications: list[Duplication],
    ) -> list[TechnicalDebt]:
        """Assess technical debt."""
        debt = []

        # Complexity debt
        if complexity.cyclomatic_complexity > 10:
            debt.append(TechnicalDebt(
                category="complexity",
                severity="high" if complexity.cyclomatic_complexity > 20 else "medium",
                description=f"High cyclomatic complexity: {complexity.cyclomatic_complexity}",
                effort_to_fix=complexity.cyclomatic_complexity * 2,
                impact="Reduced maintainability, increased bug risk",
                remediation="Refactor into smaller, focused functions",
            ))

        # Duplication debt
        if duplications:
            debt.append(TechnicalDebt(
                category="duplication",
                severity="high" if len(duplications) > 5 else "medium",
                description=f"{len(duplications)} duplication instances detected",
                effort_to_fix=len(duplications) * 4,
                impact="Increased maintenance burden, potential for inconsistent fixes",
                remediation="Extract shared code into common utilities or modules",
            ))

        # Testing debt
        if health.factors.get("testability", 100) < 50:
            debt.append(TechnicalDebt(
                category="testing",
                severity="medium",
                description="Low testability score",
                effort_to_fix=10,
                impact="Difficult to test, increased regression risk",
                remediation="Improve code structure for better testability",
            ))

        # Documentation debt
        if health.factors.get("documentation", 100) < 30:
            debt.append(TechnicalDebt(
                category="documentation",
                severity="low",
                description="Insufficient documentation",
                effort_to_fix=5,
                impact="Reduced code understanding, slower onboarding",
                remediation="Add docstrings and inline comments",
            ))

        self._debt.extend(debt)
        return debt

    # ── Security Vulnerability Scanning ─────────────────────────────────

    def scan_security(
        self,
        source_code: str,
        file_path: str,
    ) -> list[SecurityVulnerability]:
        """Scan for security vulnerabilities."""
        vulnerabilities = []
        lines = source_code.splitlines()

        vuln_patterns = {
            "sql_injection": {
                "patterns": ["execute(", "cursor.execute", "raw query", "format(", "%s" + "%"],
                "severity": "high",
                "description": "Potential SQL injection via string formatting",
                "remediation": "Use parameterized queries",
                "cwe": "CWE-89",
            },
            "xss": {
                "patterns": ["innerHTML", "document.write", "render_template_string", "Markup("],
                "severity": "medium",
                "description": "Potential XSS via unescaped output",
                "remediation": "Use template engine auto-escaping or escape user input",
                "cwe": "CWE-79",
            },
            "hardcoded_secrets": {
                "patterns": ["password=", "secret=", "api_key=", "token=", "aws_access_key"],
                "severity": "high",
                "description": "Hardcoded secret detected",
                "remediation": "Use environment variables or secret management system",
                "cwe": "CWE-798",
            },
            "weak_crypto": {
                "patterns": ["md5(", "sha1(", "DES(", "random.random(", "random.seed"],
                "severity": "medium",
                "description": "Weak cryptographic algorithm or insecure randomness",
                "remediation": "Use SHA-256+ and secrets module",
                "cwe": "CWE-327",
            },
            "insecure_deserialization": {
                "patterns": ["pickle.loads", "yaml.load(", "eval(", "exec("],
                "severity": "high",
                "description": "Insecure deserialization or code execution",
                "remediation": "Use safe loaders, avoid eval/exec on untrusted input",
                "cwe": "CWE-502",
            },
            "path_traversal": {
                "patterns": ["os.path.join(", "open(", "Path(", "../"],
                "severity": "medium",
                "description": "Potential path traversal vulnerability",
                "remediation": "Validate and sanitize file paths",
                "cwe": "CWE-22",
            },
        }

        for i, line in enumerate(lines, 1):
            line_lower = line.lower()
            for vuln_type, data in vuln_patterns.items():
                if any(p in line_lower for p in data["patterns"]):
                    vulnerabilities.append(SecurityVulnerability(
                        vulnerability_id=hashlib.md5(
                            f"vuln:{file_path}:{i}:{time.time()}".encode()
                        ).hexdigest()[:12],
                        type=vuln_type,
                        severity=data["severity"],
                        file=file_path,
                        line=i,
                        description=data["description"],
                        remediation=data["remediation"],
                        cwe=data["cwe"],
                    ))

        self._vulnerabilities.extend(vulnerabilities)
        return vulnerabilities

    # ── Code Documentation Generation ───────────────────────────────────

    def generate_documentation(
        self,
        source_code: str,
        file_path: str,
    ) -> Documentation:
        """Generate documentation for code."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return Documentation(file=file_path, summary="", classes=[], functions=[], modules=[], dependencies=[])

        # Extract summary
        docstring = ast.get_docstring(tree) or ""
        summary = docstring.split("\n")[0] if docstring else f"Module: {file_path}"

        # Extract classes and functions
        classes = []
        functions = []
        modules = []
        dependencies = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [
                    n.name for n in ast.iter_child_nodes(node)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                class_doc = ast.get_docstring(node) or ""
                classes.append({
                    "name": node.name,
                    "methods": methods,
                    "description": class_doc.split("\n")[0] if class_doc else "",
                    "line": node.lineno,
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_doc = ast.get_docstring(node) or ""
                functions.append({
                    "name": node.name,
                    "args": [a.arg for a in node.args.args],
                    "description": func_doc.split("\n")[0] if func_doc else "",
                    "line": node.lineno,
                    "returns": isinstance(node.returns, ast.Name) and node.returns.id or "Any",
                })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    dependencies.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    dependencies.append(node.module)

        doc = Documentation(
            file=file_path,
            summary=summary,
            classes=classes,
            functions=functions,
            modules=list(set(dependencies)),
            dependencies=list(set(dependencies)),
        )

        self._docs[file_path] = doc
        return doc

    # ── Reporting ────────────────────────────────────────────────────────

    def get_project_health(self) -> dict:
        """Get overall project health."""
        if not self._health:
            return {"status": "No code analyzed yet"}

        avg_score = sum(h.score for h in self._health.values()) / len(self._health)
        total_debt = sum(d.effort_to_fix for d in self._debt)
        total_vulns = len(self._vulnerabilities)
        high_vulns = sum(1 for v in self._vulnerabilities if v.severity == "high")

        return {
            "files_analyzed": len(self._health),
            "average_health_score": avg_score,
            "average_grade": (
                "A" if avg_score >= 90 else
                "B" if avg_score >= 80 else
                "C" if avg_score >= 70 else
                "D" if avg_score >= 50 else
                "F"
            ),
            "total_technical_debt_hours": total_debt,
            "total_vulnerabilities": total_vulns,
            "high_severity_vulnerabilities": high_vulns,
            "total_duplications": len(self._duplications),
            "patterns_detected": len(self._patterns),
        }


# Module-level singleton
code_intelligence = CodeIntelligenceEngine()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/forge/code/complexity")
async def analyze_complexity(payload: dict):
    """Analyze code complexity."""
    metrics = code_intelligence.analyze_complexity(
        payload["file_path"],
        payload["source_code"],
    )
    return metrics.__dict__


@router.post("/api/v1/forge/code/patterns")
async def detect_patterns(payload: dict):
    """Detect architecture patterns."""
    patterns = code_intelligence.detect_patterns(
        payload["source_code"],
        payload.get("file_path", ""),
    )
    return [p.__dict__ for p in patterns]


@router.post("/api/v1/forge/code/health")
async def score_code_health(payload: dict):
    """Score code health."""
    health = code_intelligence.score_code_health(
        payload["file_path"],
        payload["source_code"],
    )
    return health.__dict__


@router.post("/api/v1/forge/code/dependencies")
async def analyze_dependencies(payload: dict):
    """Analyze dependencies."""
    deps = code_intelligence.analyze_dependencies(
        payload["source_code"],
        payload["file_path"],
    )
    return deps.__dict__


@router.post("/api/v1/forge/code/duplication")
async def detect_duplication(payload: dict):
    """Detect code duplication."""
    dups = code_intelligence.detect_duplication(payload["files"])
    return [d.__dict__ for d in dups]


@router.post("/api/v1/forge/code/technical_debt")
async def assess_technical_debt(payload: dict):
    """Assess technical debt."""
    debt = code_intelligence.assess_technical_debt(
        code_intelligence.score_code_health(payload["file_path"], payload["source_code"]),
        code_intelligence.analyze_complexity(payload["file_path"], payload["source_code"]),
        code_intelligence.detect_duplication(payload.get("files", {})),
    )
    return [d.__dict__ for d in debt]


@router.post("/api/v1/forge/code/security")
async def scan_security(payload: dict):
    """Scan for security vulnerabilities."""
    vulns = code_intelligence.scan_security(
        payload["source_code"],
        payload["file_path"],
    )
    return [v.__dict__ for v in vulns]


@router.post("/api/v1/forge/code/documentation")
async def generate_documentation(payload: dict):
    """Generate documentation."""
    doc = code_intelligence.generate_documentation(
        payload["source_code"],
        payload["file_path"],
    )
    return doc.__dict__


@router.get("/api/v1/forge/code/project_health")
async def get_project_health():
    """Get project health."""
    return code_intelligence.get_project_health()
