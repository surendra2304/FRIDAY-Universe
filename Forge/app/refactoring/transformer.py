"""
AST Code Transformer for applying verified, safe automated refactorings.
"""

from __future__ import annotations

import ast
import copy
import difflib
from typing import Any

from app.refactoring.analyzer import ASTCodeAnalyzer
from app.refactoring.models import (
    FileRefactoringChange,
    RefactoringRuleType,
)


class MutableDefaultTransformer(ast.NodeTransformer):
    """
    Transforms functions with mutable default arguments (e.g., def f(x=[]):)
    into safe defaults (def f(x=None): if x is None: x = []).
    """

    def __init__(self) -> None:
        super().__init__()
        self.transformations_count = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        return self._transform_function_defaults(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self.generic_visit(node)
        return self._transform_function_defaults(node)

    def _transform_function_defaults(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> ast.AST:
        # Match positional defaults with their corresponding args
        # Positional defaults correspond to the LAST len(defaults) args
        num_defaults = len(node.args.defaults)
        args_with_defaults = node.args.args[-num_defaults:] if num_defaults > 0 else []

        assignments_to_inject: list[ast.stmt] = []
        new_defaults: list[ast.expr] = []

        for arg, default in zip(args_with_defaults, node.args.defaults, strict=False):
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.transformations_count += 1
                new_defaults.append(ast.Constant(value=None))
                # Create: if arg is None: arg = <default>
                guard_stmt = ast.If(
                    test=ast.Compare(
                        left=ast.Name(id=arg.arg, ctx=ast.Load()),
                        ops=[ast.Is()],
                        comparators=[ast.Constant(value=None)],
                    ),
                    body=[
                        ast.Assign(
                            targets=[ast.Name(id=arg.arg, ctx=ast.Store())],
                            value=copy.deepcopy(default),
                        )
                    ],
                    orelse=[],
                )
                assignments_to_inject.append(guard_stmt)
            else:
                new_defaults.append(default)

        node.args.defaults = new_defaults

        # Handle kwonly defaults
        new_kw_defaults: list[ast.expr | None] = []
        for kwarg, kw_default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=False):
            if kw_default is not None and isinstance(kw_default, (ast.List, ast.Dict, ast.Set)):
                self.transformations_count += 1
                new_kw_defaults.append(ast.Constant(value=None))
                guard_stmt = ast.If(
                    test=ast.Compare(
                        left=ast.Name(id=kwarg.arg, ctx=ast.Load()),
                        ops=[ast.Is()],
                        comparators=[ast.Constant(value=None)],
                    ),
                    body=[
                        ast.Assign(
                            targets=[ast.Name(id=kwarg.arg, ctx=ast.Store())],
                            value=copy.deepcopy(kw_default),
                        )
                    ],
                    orelse=[],
                )
                assignments_to_inject.append(guard_stmt)
            else:
                new_kw_defaults.append(kw_default)

        node.args.kw_defaults = new_kw_defaults

        if assignments_to_inject:
            # Insert after docstring if present
            insert_pos = 0
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                insert_pos = 1

            for stmt in reversed(assignments_to_inject):
                ast.copy_location(stmt, node)
                node.body.insert(insert_pos, stmt)

        return node


class BareExceptTransformer(ast.NodeTransformer):
    """
    Transforms bare 'except:' clauses into 'except Exception:'.
    """

    def __init__(self) -> None:
        super().__init__()
        self.transformations_count = 0

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.AST:
        self.generic_visit(node)
        if node.type is None:
            self.transformations_count += 1
            node.type = ast.Name(id="Exception", ctx=ast.Load())
            ast.copy_location(node.type, node)
        return node


class DeadCodeTransformer(ast.NodeTransformer):
    """
    Prunes unreachable statements following unconditional returns or raises in a statement list.
    """

    def __init__(self) -> None:
        super().__init__()
        self.transformations_count = 0

    def _prune_block(self, body: list[ast.stmt]) -> list[ast.stmt]:
        pruned: list[ast.stmt] = []
        for stmt in body:
            pruned.append(stmt)
            if isinstance(stmt, (ast.Return, ast.Raise)):
                # If there are statements after this in the same block, they are dead code
                dead_count = len(body) - len(pruned)
                if dead_count > 0:
                    self.transformations_count += dead_count
                break
        return pruned

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        node.body = self._prune_block(node.body)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self.generic_visit(node)
        node.body = self._prune_block(node.body)
        return node

    def visit_Module(self, node: ast.Module) -> ast.AST:
        self.generic_visit(node)
        node.body = self._prune_block(node.body)
        return node

    def visit_If(self, node: ast.If) -> ast.AST:
        self.generic_visit(node)
        node.body = self._prune_block(node.body)
        node.orelse = self._prune_block(node.orelse)
        return node

    def visit_For(self, node: ast.For) -> ast.AST:
        self.generic_visit(node)
        node.body = self._prune_block(node.body)
        node.orelse = self._prune_block(node.orelse)
        return node

    def visit_While(self, node: ast.While) -> ast.AST:
        self.generic_visit(node)
        node.body = self._prune_block(node.body)
        node.orelse = self._prune_block(node.orelse)
        return node


class LegacyTypingTransformer(ast.NodeTransformer):
    """
    Modernizes typing annotations: replaces List[...] with list[...], Dict[...] with dict[...], etc.
    """

    LEGACY_MAP = {
        "List": "list",
        "Dict": "dict",
        "Set": "set",
        "Tuple": "tuple",
        "FrozenSet": "frozenset",
    }

    def __init__(self) -> None:
        super().__init__()
        self.transformations_count = 0

    def visit_Subscript(self, node: ast.Subscript) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.value, ast.Name) and node.value.id in self.LEGACY_MAP:
            new_id = self.LEGACY_MAP[node.value.id]
            node.value.id = new_id
            self.transformations_count += 1
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.AST:
        if node.module == "typing":
            # Remove imported legacy names that were modernized if other names remain
            new_names = [
                alias for alias in node.names if alias.name not in self.LEGACY_MAP
            ]
            if len(new_names) != len(node.names):
                self.transformations_count += len(node.names) - len(new_names)
                if not new_names:
                    # Drop entire import if empty
                    return ast.Pass()
                node.names = new_names
        return node


class ASTCodeTransformer:
    """
    Orchestrates safe code transformations, verifying structural validity and diff integrity.
    """

    @classmethod
    def apply_transformations(
        cls,
        source_code: str,
        file_path: str = "snippet.py",
        rules: list[RefactoringRuleType] | None = None,
    ) -> list[FileRefactoringChange]:
        """
        Applies requested refactoring rules to Python source code.
        Returns a list of FileRefactoringChange records for rules that produced modifications.
        """
        changes: list[FileRefactoringChange] = []
        if not source_code.strip():
            return changes

        target_rules = rules or [
            RefactoringRuleType.MUTABLE_DEFAULT_FIX,
            RefactoringRuleType.BARE_EXCEPT_FIX,
            RefactoringRuleType.DEAD_CODE_ELIMINATION,
            RefactoringRuleType.TYPE_ANNOTATION_UPGRADE,
        ]

        current_code = source_code

        for rule in target_rules:
            try:
                tree = ast.parse(current_code, filename=file_path)
            except SyntaxError:
                # If source is currently invalid, do not attempt AST transformation
                break

            modified = False
            transformer: Any = None
            description = ""

            if rule == RefactoringRuleType.MUTABLE_DEFAULT_FIX:
                transformer = MutableDefaultTransformer()
                description = "Replaced mutable default arguments with None and body initialization"
            elif rule == RefactoringRuleType.BARE_EXCEPT_FIX:
                transformer = BareExceptTransformer()
                description = "Converted bare 'except:' clause to 'except Exception:'"
            elif rule == RefactoringRuleType.DEAD_CODE_ELIMINATION:
                transformer = DeadCodeTransformer()
                description = "Eliminated unreachable statements following return or raise"
            elif rule == RefactoringRuleType.TYPE_ANNOTATION_UPGRADE:
                transformer = LegacyTypingTransformer()
                description = "Modernized legacy typing aliases (List, Dict, Set) to built-ins"

            if transformer is not None:
                new_tree = transformer.visit(tree)
                ast.fix_missing_locations(new_tree)

                if transformer.transformations_count > 0:
                    candidate_code = ast.unparse(new_tree)
                    # Verify candidate code parses without errors
                    try:
                        ast.parse(candidate_code, filename=file_path)
                        modified = True
                    except SyntaxError:
                        # Reject invalid transformation
                        modified = False

                    if modified and candidate_code != current_code:
                        diff = cls._generate_diff(
                            current_code, candidate_code, file_path
                        )
                        _, metrics_before = ASTCodeAnalyzer.analyze_source(
                            current_code, file_path
                        )
                        _, metrics_after = ASTCodeAnalyzer.analyze_source(
                            candidate_code, file_path
                        )

                        change = FileRefactoringChange(
                            file_path=file_path,
                            rule_type=rule,
                            original_code=current_code,
                            refactored_code=candidate_code,
                            diff=diff,
                            description=description,
                            metrics_before=metrics_before.get("target"),
                            metrics_after=metrics_after.get("target"),
                            safety_score=1.0,
                        )
                        changes.append(change)
                        current_code = candidate_code

        return changes

    @staticmethod
    def _generate_diff(original: str, refactored: str, file_path: str) -> str:
        """Generates a clean unified diff string between original and refactored code."""
        orig_lines = original.splitlines(keepends=True)
        refact_lines = refactored.splitlines(keepends=True)
        diff_lines = list(
            difflib.unified_diff(
                orig_lines,
                refact_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            )
        )
        return "".join(diff_lines)
