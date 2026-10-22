"""
Static Code Quality Analyzer for Project FORGE.
Evaluates cyclomatic complexity, function/file lengths, duplicate code, dead code, naming conventions, and documentation coverage.
"""

import ast
import hashlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.verification.advanced_battery import VerificationCheck

logger = get_logger("verification.quality_analyzer")


class CyclomaticComplexityVisitor(ast.NodeVisitor):
    """Calculates McCabe cyclomatic complexity of Python AST nodes."""

    def __init__(self):
        self.complexity = 1

    def visit_If(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_IfExp(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_Try(self, node):
        self.complexity += len(node.handlers)
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_Match(self, node):
        self.complexity += len(node.cases)
        self.generic_visit(node)


class CodeQualityAnalyzer:
    """Performs deep static code quality analysis beyond basic linting."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def analyze_cyclomatic_complexity(self) -> VerificationCheck:
        """Measure cyclomatic complexity per function (warn >15, fail >25)."""
        warnings = []
        failures = []

        for py_file in self.workspace_path.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        visitor = CyclomaticComplexityVisitor()
                        for child in node.body:
                            visitor.visit(child)
                        score = visitor.complexity
                        func_info = {
                            "file": py_file.name,
                            "function": node.name,
                            "line": node.lineno,
                            "complexity": score,
                        }
                        if score > 25:
                            failures.append(func_info)
                        elif score > 15:
                            warnings.append(func_info)
            except Exception as e:
                logger.debug(f"Complexity parse error in {py_file}: {e}")

        status = "pass"
        if failures:
            status = "fail"
        elif warnings:
            status = "warn"

        return VerificationCheck(
            name="Cyclomatic Complexity Analysis",
            category="quality",
            status=status,
            evidence={
                "critical_functions (>25)": failures,
                "complex_functions (>15)": warnings,
            },
            fix_suggestions=[
                f"Refactor function '{f['function']}' in {f['file']} (complexity={f['complexity']}) into smaller helper functions."
                for f in (failures + warnings)[:5]
            ],
        )

    def analyze_function_and_file_lengths(self) -> VerificationCheck:
        """Inspect function lengths (warn >50, fail >100) and file lengths (warn >500)."""
        long_functions = []
        long_files = []

        for p in self.workspace_path.rglob("*"):
            if not p.is_file() or p.name.startswith(".") or "node_modules" in str(p):
                continue
            if p.suffix.lower() not in [".py", ".js", ".ts", ".html", ".css"]:
                continue

            try:
                lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
                if len(lines) > 500:
                    long_files.append({"file": p.name, "lines": len(lines)})

                # Python specific function lengths
                if p.suffix.lower() == ".py":
                    tree = ast.parse("\n".join(lines))
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            end_lineno = getattr(node, "end_lineno", node.lineno)
                            length = end_lineno - node.lineno + 1
                            if length > 50:
                                long_functions.append(
                                    {
                                        "file": p.name,
                                        "function": node.name,
                                        "start_line": node.lineno,
                                        "length": length,
                                        "severity": "fail" if length > 100 else "warn",
                                    }
                                )
            except Exception as e:
                logger.debug(f"Length check error in {p}: {e}")

        status = "pass"
        if any(f["severity"] == "fail" for f in long_functions):
            status = "fail"
        elif long_functions or long_files:
            status = "warn"

        return VerificationCheck(
            name="Function & File Length Analysis",
            category="quality",
            status=status,
            evidence={"long_functions": long_functions, "long_files": long_files},
            fix_suggestions=[
                f"Decompose {f['function']}() in {f['file']} ({f['length']} lines) into distinct single-responsibility routines."
                for f in long_functions[:5]
            ]
            + [
                f"Split {f['file']} ({f['lines']} lines) into separate submodules."
                for f in long_files[:3]
            ],
        )

    def analyze_duplicate_code(self) -> VerificationCheck:
        """Detect near-duplicate code blocks across codebase files using rolling hash shingles."""
        block_hashes: dict[str, list[dict[str, Any]]] = defaultdict(list)
        duplicates = []

        for p in self.workspace_path.rglob("*"):
            if not p.is_file() or p.name.startswith(".") or "node_modules" in str(p):
                continue
            if p.suffix.lower() not in [".py", ".js", ".ts"]:
                continue

            try:
                lines = [
                    line_text.strip()
                    for line_text in p.read_text(encoding="utf-8", errors="ignore").splitlines()
                    if line_text.strip() and not line_text.strip().startswith(("#", "//"))
                ]
                # 6-line sliding window shingle
                for i in range(len(lines) - 5):
                    chunk = "\n".join(lines[i : i + 6])
                    h = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
                    block_hashes[h].append({"file": p.name, "start_line": i + 1})
            except Exception:
                pass

        for h, occurrences in block_hashes.items():
            if len(occurrences) > 1:
                # Check if occurrences are from different files or different line ranges
                distinct_files = {o["file"] for o in occurrences}
                if len(distinct_files) > 1 or len(occurrences) > 2:
                    duplicates.append({"occurrences": occurrences[:4]})

        status = "warn" if duplicates else "pass"
        return VerificationCheck(
            name="Duplicate Code Detection",
            category="quality",
            status=status,
            evidence={
                "duplicate_block_count": len(duplicates),
                "sample_duplicates": duplicates[:5],
            },
            fix_suggestions=[
                "Extract duplicate logic across files into shared utility modules or helper classes."
            ]
            if duplicates
            else [],
        )

    def analyze_dead_code_and_unused_imports(self) -> VerificationCheck:
        """Inspect Python files for unused imports and unreachable statements."""
        dead_code_items = []

        for py_file in self.workspace_path.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content)

                imported_names: set[str] = set()
                used_names: set[str] = set()

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                        for alias in node.names:
                            imported_names.add(alias.asname or alias.name)
                    elif isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Store):
                        used_names.add(node.id)

                unused = imported_names - used_names
                # Filter special names
                unused = {u for u in unused if not u.startswith("__")}
                if unused:
                    dead_code_items.append(
                        {
                            "file": py_file.name,
                            "unused_imports": sorted(list(unused)),
                        }
                    )
            except Exception as e:
                logger.debug(f"Dead code analysis error in {py_file}: {e}")

        status = "warn" if dead_code_items else "pass"
        return VerificationCheck(
            name="Dead Code & Unused Imports",
            category="quality",
            status=status,
            evidence={"dead_code_findings": dead_code_items},
            fix_suggestions=[
                f"Remove unused imports {item['unused_imports']} from {item['file']}."
                for item in dead_code_items[:5]
            ],
        )

    def analyze_naming_conventions(self) -> VerificationCheck:
        """Verify PEP 8 naming conventions for Python (snake_case functions/vars, PascalCase classes)."""
        naming_violations = []

        for py_file in self.workspace_path.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    # Classes should be PascalCase
                    if isinstance(node, ast.ClassDef):
                        if not re.match(r"^[A-Z][a-zA-Z0-9]*$", node.name):
                            naming_violations.append(
                                {
                                    "file": py_file.name,
                                    "line": node.lineno,
                                    "name": node.name,
                                    "type": "class",
                                    "expected": "PascalCase",
                                }
                            )
                    # Functions should be snake_case
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not re.match(r"^[a-z_][a-z0-9_]*$", node.name) and not (
                            node.name.startswith("__") and node.name.endswith("__")
                        ):
                            naming_violations.append(
                                {
                                    "file": py_file.name,
                                    "line": node.lineno,
                                    "name": node.name,
                                    "type": "function",
                                    "expected": "snake_case",
                                }
                            )
            except Exception as e:
                logger.debug(f"Naming convention parse error in {py_file}: {e}")

        status = "warn" if len(naming_violations) > 0 else "pass"
        return VerificationCheck(
            name="Naming Convention Adherence",
            category="quality",
            status=status,
            evidence={
                "violations_count": len(naming_violations),
                "violations": naming_violations[:10],
            },
            fix_suggestions=[
                f"Rename {v['type']} '{v['name']}' in {v['file']} (line {v['line']}) to follow {v['expected']} convention."
                for v in naming_violations[:5]
            ],
        )

    def analyze_documentation_coverage(self) -> VerificationCheck:
        """Calculate docstring coverage across public functions and classes."""
        total_symbols = 0
        documented_symbols = 0
        missing_docs = []

        for py_file in self.workspace_path.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name.startswith("_") and not node.name.startswith("__"):
                            continue  # skip private
                        total_symbols += 1
                        docstring = ast.get_docstring(node)
                        if docstring:
                            documented_symbols += 1
                        else:
                            missing_docs.append(
                                {"file": py_file.name, "symbol": node.name, "line": node.lineno}
                            )
            except Exception:
                pass

        coverage_pct = (
            round((documented_symbols / total_symbols * 100.0), 1) if total_symbols > 0 else 100.0
        )
        status = "pass" if coverage_pct >= 60.0 else "warn"

        return VerificationCheck(
            name="Documentation Coverage",
            category="quality",
            status=status,
            evidence={
                "total_public_symbols": total_symbols,
                "documented_symbols": documented_symbols,
                "coverage_percent": coverage_pct,
                "missing_docstrings": missing_docs[:10],
            },
            fix_suggestions=[
                f"Add docstring to public symbol '{m['symbol']}' in {m['file']} (line {m['line']})."
                for m in missing_docs[:5]
            ]
            if coverage_pct < 60.0
            else [],
        )

    def analyze_web_aesthetic_and_interactivity(self) -> VerificationCheck | None:
        """
        Evaluates frontend web projects against Lovable/Bolt/Durable design & interactivity standards:
        - 3D WebGL / Canvas presence
        - Glassmorphism design tokens & CSS variables
        - Dynamic event wiring (theme, modals, filters)
        - Zero low-effort placeholder strings ('Lorem ipsum', 'Project Alpha', etc.)
        """
        html_files = list(self.workspace_path.rglob("*.html"))
        if not html_files:
            return None

        css_files = list(self.workspace_path.rglob("*.css"))
        js_files = list(self.workspace_path.rglob("*.js"))

        html_content = "\n".join(f.read_text(encoding="utf-8", errors="ignore") for f in html_files)
        css_content = "\n".join(f.read_text(encoding="utf-8", errors="ignore") for f in css_files)
        js_content = "\n".join(f.read_text(encoding="utf-8", errors="ignore") for f in js_files)

        checks_passed: list[str] = []
        warnings: list[str] = []
        failures: list[str] = []

        # 1. 3D Canvas / WebGL Check
        has_canvas = "<canvas" in html_content.lower()
        has_3d_engine = (
            "three" in html_content.lower()
            or "three" in js_content.lower()
            or "webgl" in js_content.lower()
            or "particles" in js_content.lower()
            or "canvas" in js_content.lower()
        )
        if has_canvas and has_3d_engine:
            checks_passed.append("3D WebGL / Canvas interactive graphics engine detected")
        elif has_canvas:
            warnings.append("Canvas element present but 3D / animation engine not fully initialized")
        else:
            warnings.append("No 3D Canvas or WebGL visual viewport detected")

        # 2. Glassmorphism & Modern CSS Tokens
        has_glass = "backdrop-filter" in css_content.lower() or "blur(" in css_content.lower()
        has_css_vars = ":root" in css_content and "--" in css_content
        if has_glass and has_css_vars:
            checks_passed.append("Modern glassmorphism and CSS design tokens present")
        elif has_css_vars:
            checks_passed.append("CSS variables defined")
        else:
            warnings.append("Missing CSS variables and glassmorphic design tokens")

        # 3. Dynamic Interactivity & Event Handlers
        has_event_listeners = (
            "addeventlistener" in js_content.lower()
            or "onclick" in html_content.lower()
            or "click" in js_content.lower()
        )
        if has_event_listeners:
            checks_passed.append("Dynamic JavaScript event wiring and interactions present")
        else:
            warnings.append("No dynamic JavaScript event listeners detected")

        # 4. Zero Placeholder Text Check
        placeholder_patterns = [
            r"\blorem ipsum\b",
            r"\bproject alpha\b",
            r"\bproject beta\b",
            r"\buntitled project\b",
            r"\bfoo bar\b",
        ]
        found_placeholders: list[str] = []
        for pat in placeholder_patterns:
            if re.search(pat, html_content, re.IGNORECASE):
                clean_name = pat.replace(r"\b", "")
                found_placeholders.append(clean_name)

        if found_placeholders:
            failures.append(f"Low-effort placeholder copy detected: {', '.join(found_placeholders)}")
        else:
            checks_passed.append("Zero placeholder text verified")

        status = "fail" if failures else ("warn" if len(warnings) > 1 else "pass")
        return VerificationCheck(
            name="Web Aesthetic & 3D Interactivity Analysis",
            category="quality",
            status=status,
            evidence={
                "checks_passed": checks_passed,
                "warnings": warnings,
                "failures": failures,
                "canvas_detected": has_canvas,
                "glassmorphic_tokens": has_glass,
            },
            fix_suggestions=[
                f"Enhance website: {w}" for w in warnings + failures
            ],
        )

    def run_all(self) -> list[VerificationCheck]:
        """Run all code quality checks."""
        checks = [
            self.analyze_cyclomatic_complexity(),
            self.analyze_function_and_file_lengths(),
            self.analyze_duplicate_code(),
            self.analyze_dead_code_and_unused_imports(),
            self.analyze_naming_conventions(),
            self.analyze_documentation_coverage(),
        ]
        web_check = self.analyze_web_aesthetic_and_interactivity()
        if web_check is not None:
            checks.append(web_check)
        return checks
