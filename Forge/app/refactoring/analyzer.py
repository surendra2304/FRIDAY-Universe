"""
AST Code Analyzer for identifying code smells, anti-patterns, and complexity hotspots.
"""

from __future__ import annotations

import ast

from app.refactoring.models import (
    ComplexityMetrics,
    IssueSeverity,
    RefactoringIssue,
    RefactoringRuleType,
)


class ComplexityVisitor(ast.NodeVisitor):
    """Computes Cyclomatic Complexity, Max Nesting Depth, and Function Metrics."""

    def __init__(self) -> None:
        self.complexity: int = 1
        self.nesting_depth: int = 0
        self.max_nesting_depth: int = 0
        self.num_returns: int = 0

    def generic_visit(self, node: ast.AST) -> None:
        super().generic_visit(node)

    def _enter_block(self, node: ast.AST) -> None:
        self.nesting_depth += 1
        if self.nesting_depth > self.max_nesting_depth:
            self.max_nesting_depth = self.nesting_depth
        self.generic_visit(node)
        self.nesting_depth -= 1

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self._enter_block(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self._enter_block(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.complexity += 1
        self._enter_block(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self._enter_block(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self._enter_block(node)

    def visit_With(self, node: ast.With) -> None:
        self._enter_block(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._enter_block(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # Each operator in `a and b and c` adds an independent path branch
        self.complexity += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        self.num_returns += 1
        self.generic_visit(node)


class ASTCodeAnalyzer:
    """
    Parses Python code into an Abstract Syntax Tree (AST) to extract structural
    metrics and identify refactoring opportunities.
    """

    @classmethod
    def analyze_source(
        cls,
        source_code: str,
        file_path: str = "snippet.py",
    ) -> tuple[list[RefactoringIssue], dict[str, ComplexityMetrics]]:
        """
        Analyze Python source code and return identified issues along with per-function metrics.
        """
        issues: list[RefactoringIssue] = []
        function_metrics: dict[str, ComplexityMetrics] = {}

        if not source_code.strip():
            return issues, function_metrics

        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError as err:
            issues.append(
                RefactoringIssue(
                    file_path=file_path,
                    line_number=err.lineno or 1,
                    column=err.offset or 1,
                    rule_type=RefactoringRuleType.MODERNIZE_SYNTAX,
                    severity=IssueSeverity.CRITICAL,
                    message=f"Syntax Error in source: {err.msg}",
                    context_code=err.text or "",
                )
            )
            return issues, function_metrics

        source_lines = source_code.splitlines()

        for node in ast.walk(tree):
            # Check 1: Mutable default arguments
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cls._check_mutable_defaults(node, file_path, source_lines, issues)
                cls._analyze_function_metrics(node, file_path, source_lines, issues, function_metrics)

            # Check 2: Bare except clauses
            elif isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    line = node.lineno
                    issues.append(
                        RefactoringIssue(
                            file_path=file_path,
                            line_number=line,
                            column=node.col_offset,
                            rule_type=RefactoringRuleType.BARE_EXCEPT_FIX,
                            severity=IssueSeverity.WARNING,
                            message="Bare 'except:' catches BaseException (including KeyboardInterrupt and SystemExit). Use 'except Exception:' instead.",
                            suggested_fix="except Exception:",
                            context_code=source_lines[line - 1] if line <= len(source_lines) else "",
                        )
                    )

            # Check 3: Legacy typing imports (typing.List, typing.Dict, etc.)
            elif isinstance(node, ast.ImportFrom):
                if node.module == "typing":
                    cls._check_legacy_typing(node, file_path, source_lines, issues)

        return issues, function_metrics

    @classmethod
    def _check_mutable_defaults(
        cls,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        source_lines: list[str],
        issues: list[RefactoringIssue],
    ) -> None:
        """Flags mutable default values like def fn(x=[]): or def fn(y={}):"""
        for default in func_node.args.defaults + func_node.args.kw_defaults:
            if default is not None and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                line = default.lineno
                issues.append(
                    RefactoringIssue(
                        file_path=file_path,
                        line_number=line,
                        column=default.col_offset,
                        rule_type=RefactoringRuleType.MUTABLE_DEFAULT_FIX,
                        severity=IssueSeverity.WARNING,
                        message=f"Mutable default argument '{ast.unparse(default)}' in function '{func_node.name}'. Use None as default and initialize inside function body.",
                        suggested_fix="None",
                        context_code=source_lines[line - 1] if line <= len(source_lines) else "",
                    )
                )

    @classmethod
    def _analyze_function_metrics(
        cls,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        source_lines: list[str],
        issues: list[RefactoringIssue],
        metrics_map: dict[str, ComplexityMetrics],
    ) -> None:
        """Calculates complexity, lines of code, and nesting depth for a function."""
        visitor = ComplexityVisitor()
        for stmt in func_node.body:
            visitor.visit(stmt)

        loc = max(1, (func_node.end_lineno or func_node.lineno) - func_node.lineno + 1)
        args_count = len(func_node.args.args) + len(func_node.args.kwonlyargs)

        metrics = ComplexityMetrics(
            cyclomatic_complexity=visitor.complexity,
            max_nesting_depth=visitor.max_nesting_depth,
            lines_of_code=loc,
            num_arguments=args_count,
            num_returns=visitor.num_returns,
        )
        metrics_map[func_node.name] = metrics

        # Flag high cyclomatic complexity
        if metrics.cyclomatic_complexity > 10:
            issues.append(
                RefactoringIssue(
                    file_path=file_path,
                    line_number=func_node.lineno,
                    column=func_node.col_offset,
                    rule_type=RefactoringRuleType.REDUCE_COMPLEXITY,
                    severity=IssueSeverity.WARNING,
                    message=f"Function '{func_node.name}' has high cyclomatic complexity ({metrics.cyclomatic_complexity} > 10). Recommend decomposing into modular sub-functions.",
                    context_code=source_lines[func_node.lineno - 1] if func_node.lineno <= len(source_lines) else "",
                )
            )

        # Flag excessive nesting depth
        if metrics.max_nesting_depth > 4:
            issues.append(
                RefactoringIssue(
                    file_path=file_path,
                    line_number=func_node.lineno,
                    column=func_node.col_offset,
                    rule_type=RefactoringRuleType.REDUCE_COMPLEXITY,
                    severity=IssueSeverity.WARNING,
                    message=f"Function '{func_node.name}' has excessive nesting depth ({metrics.max_nesting_depth} > 4). Use early returns or extract guard clauses.",
                    context_code=source_lines[func_node.lineno - 1] if func_node.lineno <= len(source_lines) else "",
                )
            )

        # Flag oversized functions
        if metrics.lines_of_code > 50:
            issues.append(
                RefactoringIssue(
                    file_path=file_path,
                    line_number=func_node.lineno,
                    column=func_node.col_offset,
                    rule_type=RefactoringRuleType.EXTRACT_FUNCTION,
                    severity=IssueSeverity.INFO,
                    message=f"Function '{func_node.name}' is {metrics.lines_of_code} lines long (threshold: 50 lines). Consider breaking it down into focused helper routines.",
                    context_code=source_lines[func_node.lineno - 1] if func_node.lineno <= len(source_lines) else "",
                )
            )

    @classmethod
    def _check_legacy_typing(
        cls,
        node: ast.ImportFrom,
        file_path: str,
        source_lines: list[str],
        issues: list[RefactoringIssue],
    ) -> None:
        """Flags deprecated Python typing aliases that can be replaced by built-in generics (PEP 585/604)."""
        legacy_names = {"List", "Dict", "Set", "Tuple", "FrozenSet"}
        for alias in node.names:
            if alias.name in legacy_names:
                line = node.lineno
                issues.append(
                    RefactoringIssue(
                        file_path=file_path,
                        line_number=line,
                        column=node.col_offset,
                        rule_type=RefactoringRuleType.TYPE_ANNOTATION_UPGRADE,
                        severity=IssueSeverity.INFO,
                        message=f"Import of legacy 'typing.{alias.name}' detected. Python 3.9+ supports built-in '{alias.name.lower()}' syntax directly.",
                        suggested_fix=alias.name.lower(),
                        context_code=source_lines[line - 1] if line <= len(source_lines) else "",
                    )
                )
