"""
Forge/app/services/real_code_engine.py — Real Code Engine.

Actual working code generation and analysis with:
- Code synthesis from specifications
- Syntax analysis and validation
- Code complexity measurement (Cyclomatic, Halstead)
- Pattern matching and template generation
- Test generation from code
- Code review with automated checks
"""
from __future__ import annotations

import ast
import math
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import json
import os


@dataclass
class CodeAnalysis:
    """Analysis result for a piece of code."""
    code: str
    language: str
    lines_of_code: int
    number_of_methods: int
    number_of_classes: int
    cyclomatic_complexity: int
    halstead_complexity: float
    maintainability_index: float
    issues: list[str]
    suggestions: list[str]


@dataclass
class GeneratedCode:
    """Generated code result."""
    filename: str
    language: str
    code: str
    description: str
    line_count: int
    function_names: list[str]


@dataclass
class TestResult:
    """Test generation result."""
    filename: str
    language: str
    test_code: str
    coverage_targets: list[str]
    test_count: int


class CodeEngine:
    """Real code engine with analysis, synthesis, and test generation."""

    def __init__(self, template_dir: str | None = None) -> None:
        self._template_dir = template_dir or os.path.join(
            os.path.dirname(__file__), "..", "templates"
        )
        os.makedirs(self._template_dir, exist_ok=True)
        self._templates = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Load code templates."""
        self._templates = {
            "function": 'def {name}({args}):\n    """{doc}"""\n    {body}\n',
            "class": 'class {name}:\n    """{doc}"""\n\n    def __init__(self, {init_args}):\n        {init_body}\n',
            "test": 'def test_{name}():\n    """Test {name}."""\n    {test_body}\n',
            "api_endpoint": '@router.{method}("{path}")\ndef {func_name}({params}):\n    """{doc}"""\n    return {{"result": "success"}}\n',
            "dataclass": '@dataclass\nclass {name}:\n    """{doc}"""\n    {fields}\n',
        }

    # ── Code Analysis ───────────────────────────────────────────────────────

    def analyze(self, code: str, language: str = "python") -> CodeAnalysis:
        """Analyze code for complexity, issues, and suggestions."""
        if language != "python":
            return CodeAnalysis(
                code=code, language=language,
                lines_of_code=len(code.split("\n")),
                number_of_methods=0, number_of_classes=0,
                cyclomatic_complexity=1, halstead_complexity=0.0,
                maintainability_index=50.0,
                issues=["Only Python analysis is currently supported"],
                suggestions=[],
            )

        issues = []
        suggestions = []

        # Parse AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            issues.append(f"Syntax error: {e}")
            return CodeAnalysis(
                code=code, language=language,
                lines_of_code=len(code.split("\n")),
                number_of_methods=0, number_of_classes=0,
                cyclomatic_complexity=1, halstead_complexity=0.0,
                maintainability_index=0.0,
                issues=issues, suggestions=suggestions,
            )

        # Count elements
        num_classes = 0
        num_methods = 0
        num_functions = 0
        cyclomatic = 1  # baseline

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                num_classes += 1
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                num_functions += 1
                if any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree) if hasattr(parent, "body") and node in getattr(parent, "body", [])):
                    num_methods += 1
                # Cyclomatic complexity: count decision points
                cyclomatic += sum(
                    1 for child in ast.walk(node)
                    if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler))
                )

        # Halstead complexity
        tokens = re.findall(r'\w+|[^\w\s]', code)
        n1 = len(set(tokens))  # unique operators/operands
        n2 = len(tokens)  # total tokens
        n = n2  # program length
        n1_ = max(1, n1)  # vocabulary
        vocab = n1_
        length = n
        volume = length * math.log2(vocab) if vocab > 0 else 0.0
        difficulty = (length / 2) / (n1 / 2) if n1 > 0 else 0.0
        effort = difficulty * volume
        halstead = round(effort / 100, 2) if effort > 0 else 0.0

        # Maintainability index
        loc = len([l for l in code.split("\n") if l.strip() and not l.strip().startswith("#")])
        comments = len([l for l in code.split("\n") if l.strip().startswith("#")])
        comment_ratio = comments / max(loc, 1)

        # Simplified MI formula
        mi = 171 - 5.2 * math.log10(max(halstead, 1)) - 0.23 * cyclomatic - 16.2 * math.log10(max(loc, 1))
        mi = max(0.0, min(100.0, mi * (1 + comment_ratio)))
        mi = round(mi, 1)

        # Detect issues
        if cyclomatic > 10:
            issues.append(f"High cyclomatic complexity: {cyclomatic}")
            suggestions.append("Consider breaking down into smaller functions")

        if halstead > 50:
            issues.append(f"High Halstead complexity: {halstead}")
            suggestions.append("Code may be too complex — refactor needed")

        if loc > 200:
            issues.append(f"Large file: {loc} lines")
            suggestions.append("Consider splitting into multiple modules")

        if comment_ratio < 0.05:
            issues.append("Low comment ratio")
            suggestions.append("Add more documentation")

        if num_classes > 20:
            issues.append(f"Many classes: {num_classes}")
            suggestions.append("Consider grouping related classes")

        if not code.endswith("\n"):
            issues.append("File does not end with newline")
            suggestions.append("Add trailing newline")

        if "\t" in code:
            issues.append("Tab characters found")
            suggestions.append("Use spaces instead of tabs")

        if len([l for l in code.split("\n") if len(l) > 120]) > 0:
            issues.append("Lines over 120 characters found")
            suggestions.append("Break long lines (PEP 8 recommends 79)")

        return CodeAnalysis(
            code=code, language=language,
            lines_of_code=loc,
            number_of_methods=num_methods + num_functions,
            number_of_classes=num_classes,
            cyclomatic_complexity=cyclomatic,
            halstead_complexity=halstead,
            maintainability_index=mi,
            issues=issues,
            suggestions=suggestions,
        )

    # ── Code Generation ─────────────────────────────────────────────────────

    def generate_function(
        self, name: str, args: list[str], doc: str, body: str = "pass"
    ) -> GeneratedCode:
        """Generate a function from specification."""
        args_str = ", ".join(args)
        template = self._templates["function"]
        code = template.format(name=name, args=args_str, doc=doc, body=body)

        return GeneratedCode(
            filename=f"{name}.py",
            language="python",
            code=code,
            description=f"Function: {name}({args_str})",
            line_count=len(code.split("\n")),
            function_names=[name],
        )

    def generate_class(
        self, name: str, doc: str, init_args: list[str],
        init_body: str = "pass", methods: list[dict[str, Any]] | None = None
    ) -> GeneratedCode:
        """Generate a class from specification."""
        methods = methods or []
        args_str = ", ".join(init_args)
        template = self._templates["class"]
        code = template.format(name=name, doc=doc, init_args=args_str, init_body=init_body)

        function_names = []
        for method in methods:
            m_name = method.get("name", "unknown")
            m_args = ", ".join(method.get("args", []))
            m_doc = method.get("doc", "")
            m_body = method.get("body", "pass")
            code += f"\n    def {m_name}({m_args}):\n"
            code += f'        """{m_doc}"""\n'
            for line in m_body.split("\n"):
                code += f"        {line}\n"
            function_names.append(m_name)

        return GeneratedCode(
            filename=f"{name}.py",
            language="python",
            code=code,
            description=f"Class: {name} with {len(methods)} methods",
            line_count=len(code.split("\n")),
            function_names=function_names,
        )

    def generate_dataclass(
        self, name: str, doc: str, fields: list[tuple[str, str]]
    ) -> GeneratedCode:
        """Generate a dataclass from specification."""
        field_strs = []
        for fname, ftype in fields:
            field_strs.append(f"{fname}: {ftype}")

        template = self._templates["dataclass"]
        code = template.format(name=name, doc=doc, fields="\n    ".join(field_strs))

        return GeneratedCode(
            filename=f"{name}.py",
            language="python",
            code=code,
            description=f"Dataclass: {name} with {len(fields)} fields",
            line_count=len(code.split("\n")),
            function_names=[],
        )

    def generate_api_endpoint(
        self, path: str, method: str, func_name: str,
        params: list[str], doc: str
    ) -> GeneratedCode:
        """Generate an API endpoint from specification."""
        params_str = ", ".join(params)
        template = self._templates["api_endpoint"]
        code = template.format(
            method=method, path=path, func_name=func_name,
            params=params_str, doc=doc,
        )

        return GeneratedCode(
            filename=f"{func_name}.py",
            language="python",
            code=code,
            description=f"API Endpoint: {method} {path}",
            line_count=len(code.split("\n")),
            function_names=[func_name],
        )

    # ── Test Generation ─────────────────────────────────────────────────────

    def generate_tests(self, code: str, class_name: str | None = None) -> TestResult:
        """Generate test code for the given source code."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return TestResult(
                filename="test.py", language="python",
                test_code="", coverage_targets=[], test_count=0,
            )

        coverage_targets = []
        test_bodies = []
        test_count = 0

        # Find functions and classes
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_name = node.name
                if func_name.startswith("test_") or func_name.startswith("_"):
                    continue  # skip test functions and private
                coverage_targets.append(func_name)
                test_count += 1

                # Generate test
                args = [a.arg for a in node.args.args if a.arg != "self"]
                test_body = (
                    f"    # Test {func_name}\n"
                    f"    # TODO: Add test assertions\n"
                    f"    result = {func_name}({', '.join([repr(None) for _ in args])})\n"
                    f"    assert result is not None\n"
                )
                test_bodies.append(f"def test_{func_name}():\n{test_body}")

            elif isinstance(node, ast.ClassDef):
                if class_name and node.name != class_name:
                    continue
                coverage_targets.append(node.name)

                # Generate tests for methods
                for child in ast.walk(node):
                    if isinstance(child, ast.FunctionDef) and child != node:
                        if child.name.startswith("_"):
                            continue
                        coverage_targets.append(f"{node.name}.{child.name}")
                        test_count += 1

                        args = [a.arg for a in child.args.args if a.arg not in ("self", "cls")]
                        test_body = (
                            f"    # Test {node.name}.{child.name}\n"
                            f"    obj = {node.name}()\n"
                            f"    result = obj.{child.name}({', '.join([repr(None) for _ in args])})\n"
                            f"    assert result is not None\n"
                        )
                        test_bodies.append(f"def test_{node.name}_{child.name}():\n{test_body}")

        test_code = "# Auto-generated tests\n\n"
        test_code += "import pytest\n\n\n"
        test_code += "\n\n".join(test_bodies)

        return TestResult(
            filename="test_generated.py",
            language="python",
            test_code=test_code,
            coverage_targets=coverage_targets,
            test_count=test_count,
        )

    # ── Code Review ──────────────────────────────────────────────────────────

    def review(self, code: str) -> dict[str, Any]:
        """Review code and return findings."""
        analysis = self.analyze(code)

        findings = {
            "summary": {
                "lines_of_code": analysis.lines_of_code,
                "classes": analysis.number_of_classes,
                "methods": analysis.number_of_methods,
                "complexity": analysis.cyclomatic_complexity,
                "maintainability": analysis.maintainability_index,
            },
            "issues": analysis.issues,
            "suggestions": analysis.suggestions,
            "score": self._calculate_score(analysis),
        }

        return findings

    def _calculate_score(self, analysis: CodeAnalysis) -> float:
        """Calculate a code quality score (0-100)."""
        score = 100.0
        score -= max(0, analysis.cyclomatic_complexity - 5) * 2
        score -= max(0, analysis.halstead_complexity - 20) * 1
        score -= max(0, analysis.lines_of_code - 100) * 0.1

        # Bonus for comments
        comments = len([l for l in analysis.code.split("\n") if l.strip().startswith("#")])
        loc = max(analysis.lines_of_code, 1)
        if comments / loc > 0.1:
            score += 5

        return round(max(0.0, min(100.0, score)), 1)


engine = CodeEngine()
