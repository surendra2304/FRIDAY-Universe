"""
Forge/documentation_generator.py — Forge Documentation Generator.

Extends Forge's capabilities with:
1. API Documentation: auto-generate API documentation from code
2. README Generation: create comprehensive README files
3. Code Example Generation: generate usage examples
4. Architecture Diagrams: create architecture documentation
5. Changelog Generation: auto-generate changelogs from commits
6. Technical Documentation: generate in-depth technical docs
"""
from __future__ import annotations

import ast
import re
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class APIEndpoint:
    """An API endpoint."""
    path: str
    method: str
    description: str
    parameters: list[dict] = field(default_factory=list)
    returns: dict = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)


@dataclass
class FunctionDoc:
    """Documentation for a function."""
    name: str
    signature: str
    description: str
    params: list[dict]
    returns: dict
    examples: list[str]
    complexity: str


@dataclass
class ClassDoc:
    """Documentation for a class."""
    name: str
    description: str
    methods: list[FunctionDoc] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


@dataclass
class READMEContent:
    """Generated README content."""
    title: str
    description: str
    installation: str
    usage: str
    examples: list[str]
    api_reference: list[str]
    contributing: str
    license: str


class DocumentationGenerator:
    """Automated documentation generator."""

    def __init__(self):
        self._function_docs: dict[str, FunctionDoc] = {}
        self._class_docs: dict[str, ClassDoc] = {}
        self._api_endpoints: dict[str, APIEndpoint] = {}

    # ── API Documentation ────────────────────────────────────────────────────

    def generate_api_docs(
        self,
        code: str,
        file_path: str = "",
    ) -> list[APIEndpoint]:
        """Generate API documentation from code."""
        endpoints = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return endpoints

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if it's a route handler
                if any(
                    "route" in str(decorator) or "get" in str(decorator).lower() or "post" in str(decorator).lower()
                    for decorator in node.decorator_list
                ):
                    # Extract path from decorator
                    path = self._extract_path_from_decorators(node.decorator_list)
                    method = self._extract_method_from_decorators(node.decorator_list)

                    endpoint = APIEndpoint(
                        path=path or f"/{node.name}",
                        method=method or "GET",
                        description=self._get_docstring(node) or f"Endpoint for {node.name}",
                        parameters=self._extract_params(node),
                        returns=self._extract_return_type(node),
                    )

                    endpoints.append(endpoint)
                    self._api_endpoints[f"{method}_{path}"] = endpoint

        return endpoints

    def _extract_path_from_decorators(self, decorators: list[ast.AST]) -> str:
        """Extract path from route decorators."""
        for decorator in decorators:
            # Check for @router.get("/path") or @app.route("/path")
            if isinstance(decorator, ast.Call):
                if decorator.args:
                    arg = decorator.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        return arg.value
        return ""

    def _extract_method_from_decorators(self, decorators: list[ast.AST]) -> str:
        """Extract HTTP method from decorators."""
        for decorator in decorators:
            if isinstance(decorator, ast.Call):
                func = decorator.func
                if isinstance(func, ast.Attribute):
                    method = func.attr.upper()
                    if method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                        return method
                elif isinstance(func, ast.Name):
                    if func.id.upper() in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                        return func.id.upper()
        return "GET"

    def _get_docstring(self, node: ast.FunctionDef) -> str:
        """Get docstring from function."""
        return ast.get_docstring(node) or ""

    def _extract_params(self, node: ast.FunctionDef) -> list[dict]:
        """Extract function parameters."""
        params = []

        for arg in node.args.args:
            param = {
                "name": arg.arg,
                "type": self._get_annotation_name(arg.annotation),
                "description": "",
            }
            params.append(param)

        return params

    def _extract_return_type(self, node: ast.FunctionDef) -> dict:
        """Extract return type."""
        return {
            "type": self._get_annotation_name(node.returns),
            "description": "",
        }

    def _get_annotation_name(self, annotation: ast.AST | None) -> str:
        """Get annotation name."""
        if annotation is None:
            return "Any"
        if isinstance(annotation, ast.Name):
            return annotation.id
        if isinstance(annotation, ast.Attribute):
            return annotation.attr
        if isinstance(annotation, ast.Subscript):
            base = self._get_annotation_name(annotation.value)
            slice = self._get_annotation_name(annotation.slice)
            return f"{base}[{slice}]"
        return "Any"

    # ── README Generation ───────────────────────────────────────────────────

    def generate_readme(
        self,
        project_name: str,
        code: str,
        description: str = "",
    ) -> READMEContent:
        """Generate a README file."""
        # Extract description from code
        if not description:
            # Try to get module docstring
            try:
                tree = ast.parse(code)
                module_doc = ast.get_docstring(tree)
                if module_doc:
                    description = module_doc
            except SyntaxError:
                pass

        if not description:
            description = f"{project_name} - A Python project"

        # Generate examples
        examples = self._generate_examples(code)

        # Generate API reference
        api_ref = [
            f"### {ep.method} {ep.path}"
            f"\n{ep.description}"
            for ep in self._api_endpoints.values()
        ]

        readme = READMEContent(
            title=f"# {project_name}",
            description=description,
            installation="```bash\npip install -r requirements.txt\n```",
            usage="```python\nfrom " + project_name + " import *\n```",
            examples=examples,
            api_reference=api_ref,
            contributing="1. Fork the repository\n2. Create a branch\n3. Commit changes\n4. Push and open PR",
            license="MIT",
        )

        return readme

    def _generate_examples(self, code: str) -> list[str]:
        """Generate usage examples from code."""
        examples = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return examples

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                examples.append(
                    f"```python\n# Using {node.name}\nobj = {node.name}()\n# ...\n```"
                )

            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                examples.append(
                    f"```python\n# Using {node.name}\nresult = {node.name}(arg)\n```"
                )

        return examples[:5]

    # ── Code Example Generation ─────────────────────────────────────────────

    def generate_examples(
        self,
        code: str,
        num_examples: int = 5,
    ) -> list[dict]:
        """Generate code examples."""
        examples = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return examples

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Generate instantiation example
                example = {
                    "type": "class_usage",
                    "name": node.name,
                    "code": f"instance = {node.name}()\n# Use the instance",
                    "description": f"How to use {node.name}",
                }
                examples.append(example)

            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                # Generate function call example
                params = [a.arg for a in node.args.args]
                args = ", ".join(f"arg_{i}" for i in range(len(params)))

                example = {
                    "type": "function_usage",
                    "name": node.name,
                    "code": f"result = {node.name}({args})\n# Use the result",
                    "description": f"How to call {node.name}",
                }
                examples.append(example)

        return examples[:num_examples]

    # ── Changelog Generation ────────────────────────────────────────────────

    def generate_changelog(
        self,
        commits: list[dict],
        version: str = "1.0.0",
    ) -> str:
        """Generate a changelog from commits."""
        sections = {"Added": [], "Changed": [], "Fixed": [], "Removed": []}

        for commit in commits:
            message = commit.get("message", "")
            # Classify commit
            lower = message.lower()

            if any(kw in lower for kw in ["add", "feat", "new"]):
                sections["Added"].append(message)
            elif any(kw in lower for kw in ["change", "update", "modify", "refactor"]):
                sections["Changed"].append(message)
            elif any(kw in lower for kw in ["fix", "bug", "correct"]):
                sections["Fixed"].append(message)
            elif any(kw in lower for kw in ["remove", "delete", "drop"]):
                sections["Removed"].append(message)

        # Generate changelog
        changelog = f"# Changelog\n\n## [{version}] - {time.strftime('%Y-%m-%d')}\n\n"

        for section, items in sections.items():
            if items:
                changelog += f"### {section}\n"
                for item in items:
                    changelog += f"- {item}\n"
                changelog += "\n"

        return changelog

    # ── Architecture Documentation ───────────────────────────────────────────

    def generate_architecture_docs(
        self,
        code: str,
        module_name: str,
    ) -> dict[str, Any]:
        """Generate architecture documentation."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"error": "Invalid Python code"}

        # Analyze imports
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(f"from {node.module}")

        # Analyze classes
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [
                    n.name for n in node.body if isinstance(n, ast.FunctionDef)
                ]
                classes.append({
                    "name": node.name,
                    "methods": methods,
                    "description": ast.get_docstring(node) or "",
                })

        # Analyze dependencies
        dependencies = set()
        for imp in imports:
            if not imp.startswith("from"):
                dependencies.add(imp.split(".")[0])

        return {
            "module": module_name,
            "dependencies": list(dependencies),
            "classes": classes,
            "total_classes": len(classes),
            "architecture": "Modular design with clear separation of concerns",
        }

    # ── Technical Documentation ─────────────────────────────────────────────

    def generate_technical_docs(
        self,
        code: str,
        topic: str,
    ) -> dict[str, Any]:
        """Generate in-depth technical documentation."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"error": "Invalid Python code"}

        # Analyze complexity
        complexity = self._calculate_complexity(code)

        # Extract all functions
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    "name": node.name,
                    "lines": node.end_lineno - node.lineno if node.end_lineno else 0,
                    "params": len(node.args.args),
                    "complexity": self._function_complexity(node),
                    "docstring": ast.get_docstring(node) or "",
                })

        # Generate docs
        docs = {
            "topic": topic,
            "overview": f"Technical documentation for {topic}",
            "complexity_score": complexity,
            "functions": functions,
            "total_functions": len(functions),
            "avg_function_lines": sum(f["lines"] for f in functions) / max(1, len(functions)),
            "most_complex": max(functions, key=lambda f: f["complexity"], default=None),
            "recommendations": self._technical_recommendations(functions),
        }

        return docs

    def _calculate_complexity(self, code: str) -> float:
        """Calculate overall cyclomatic complexity."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return 0.0

        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For)):
                complexity += 1
            elif isinstance(node, ast.ExceptHandler):
                complexity += 1

        return complexity

    def _function_complexity(self, node: ast.FunctionDef) -> float:
        """Calculate function complexity."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1

        return complexity

    def _technical_recommendations(self, functions: list[dict]) -> list[str]:
        """Generate technical recommendations."""
        recs = []

        long_funcs = [f for f in functions if f["lines"] > 50]
        if long_funcs:
            recs.append(f"Consider refactoring {len(long_funcs)} functions that exceed 50 lines")

        complex_funcs = [f for f in functions if f["complexity"] > 10]
        if complex_funcs:
            recs.append(f"Consider simplifying {len(complex_funcs)} functions with high complexity")

        undocumented = [f for f in functions if not f["docstring"]]
        if undocumented:
            recs.append(f"Add docstrings to {len(undocumented)} undocumented functions")

        return recs

    # ── Reporting ──────────────────────────────────────────────────────────

    def get_doc_report(self) -> dict[str, Any]:
        """Generate a documentation report."""
        return {
            "functions_documented": len(self._function_docs),
            "classes_documented": len(self._class_docs),
            "api_endpoints": len(self._api_endpoints),
        }
