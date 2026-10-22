"""
Autonomous Closed-Loop Self-Healing Engine.
Coordinates failure diagnosis, candidate repair generation, and closed-loop verification.
"""

from __future__ import annotations

import ast
import asyncio
import logging
import re
import time
from pathlib import Path

from app.compilers.polyglot import PolyglotCompilerMatrix
from app.refactoring.models import RefactoringRuleType
from app.refactoring.transformer import ASTCodeTransformer
from app.selfrepair.models import (
    RepairAttempt,
    RepairResult,
    RepairStrategyType,
)

logger = logging.getLogger("forge.selfrepair.engine")


class SelfRepairEngine:
    """
    Automated multi-round self-repair loop that diagnoses build/test failures,
    generates targeted candidate patches, and verifies fixes in-place.
    """

    # Common standard library and typing symbols for automated import injection
    KNOWN_SYMBOL_IMPORTS: dict[str, str] = {
        "json": "import json",
        "re": "import re",
        "sys": "import sys",
        "os": "import os",
        "time": "import time",
        "math": "import math",
        "asyncio": "import asyncio",
        "Path": "from pathlib import Path",
        "datetime": "from datetime import datetime",
        "timezone": "from datetime import timezone",
        "dataclass": "from dataclasses import dataclass",
        "field": "from dataclasses import field",
        "uuid": "import uuid",
        "uuid4": "from uuid import uuid4",
        "Any": "from typing import Any",
        "Callable": "from typing import Callable",
        "Optional": "from typing import Optional",
        "Union": "from typing import Union",
        "dict": "",  # built-in
        "list": "",  # built-in
    }

    def __init__(self, workspace_root: Path | str | None = None) -> None:
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else None
        self.compiler_matrix = PolyglotCompilerMatrix()

    async def repair_workspace(
        self,
        workspace: Path | str,
        initial_error: str = "",
        test_command: str | None = None,
        max_attempts: int = 3,
        scan_ast_smells: bool = True,
    ) -> RepairResult:
        """
        Executes a multi-round self-healing loop over a workspace.
        Diagnoses errors, applies candidate fixes, and validates via compiler or test command.
        """
        ws = Path(workspace).resolve()
        if not ws.is_dir():
            return RepairResult(
                success=False,
                rounds_executed=0,
                error_message=f"Workspace directory not found: {ws}",
            )

        resolved_files: set[str] = set()
        attempts: list[RepairAttempt] = []
        current_error = initial_error

        # If no initial error provided, run compiler matrix to find syntax/compilation issues
        if not current_error.strip():
            compile_results = self.compiler_matrix.compile_matrix(ws)
            error_diagnostics: list[str] = []
            for lang, res in compile_results.items():
                if not res.is_success:
                    error_diagnostics.append(f"[{lang.value}] {res.stderr}")
            current_error = "\n".join(error_diagnostics)

        # Check for AST code smells if compilation has no errors
        has_ast_smells = False
        if not current_error.strip() and scan_ast_smells:
            for py_file in ws.rglob("*.py"):
                parts = set(py_file.parts)
                if parts.intersection({".venv", "venv", "__pycache__", ".pytest_cache"}):
                    continue
                try:
                    content = py_file.read_text(encoding="utf-8")
                    changes = ASTCodeTransformer.apply_transformations(
                        content,
                        file_path=str(py_file),
                        rules=[
                            RefactoringRuleType.MUTABLE_DEFAULT_FIX,
                            RefactoringRuleType.BARE_EXCEPT_FIX,
                            RefactoringRuleType.DEAD_CODE_ELIMINATION,
                        ],
                    )
                    if changes:
                        has_ast_smells = True
                        break
                except Exception:
                    continue

        if not current_error.strip() and not test_command and not has_ast_smells:
            return RepairResult(
                success=True,
                rounds_executed=0,
                summary="Workspace is clean with 0 compilation errors.",
            )

        # Multi-round repair loop
        for round_idx in range(1, max_attempts + 1):
            start_time = time.perf_counter()
            target_file, strategy, candidate_code = self._diagnose_and_generate_fix(
                ws, current_error
            )

            if not target_file or not candidate_code:
                # Cannot synthesize further fixes
                break

            target_path = ws / target_file
            original_code = ""
            if target_path.is_file():
                original_code = target_path.read_text(encoding="utf-8")

            # Apply candidate fix
            target_path.write_text(candidate_code, encoding="utf-8")

            # Verify fix
            verification_passed, verify_output = await self._verify(
                ws, target_path, test_command
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            attempt = RepairAttempt(
                attempt_number=round_idx,
                strategy=strategy,
                target_file=str(target_file),
                patch_applied=f"Updated {target_file} with {strategy.value}",
                verification_passed=verification_passed,
                output_message=verify_output,
                duration_ms=duration_ms,
            )
            attempts.append(attempt)

            if verification_passed:
                resolved_files.add(str(target_file))
                logger.info(
                    "Round %d succeeded: Self-repair verified on %s via %s",
                    round_idx,
                    target_file,
                    strategy.value,
                )
                return RepairResult(
                    success=True,
                    rounds_executed=round_idx,
                    resolved_files=sorted(resolved_files),
                    summary=f"Successfully repaired {len(resolved_files)} file(s) in {round_idx} round(s).",
                    attempts=attempts,
                )
            else:
                # Revert change if it made things worse or did not fix the problem
                target_path.write_text(original_code, encoding="utf-8")
                current_error = verify_output

        return RepairResult(
            success=False,
            rounds_executed=len(attempts),
            resolved_files=sorted(resolved_files),
            summary=f"Self-repair exhausted {len(attempts)} attempt(s) without full convergence.",
            attempts=attempts,
            error_message=current_error,
        )

    def _diagnose_and_generate_fix(
        self,
        workspace: Path,
        error_context: str,
    ) -> tuple[str | None, RepairStrategyType, str | None]:
        """
        Analyzes error messages and generates a candidate repair.
        Returns (relative_file_path, strategy_type, candidate_source_code).
        """
        # Diagnostic 1: NameError -> Missing import
        name_error_match = re.search(r"NameError: name '([a-zA-Z0-9_]+)' is not defined", error_context)
        file_match = re.search(r'File "([^"]+)", line (\d+)', error_context)

        if name_error_match and file_match:
            missing_symbol = name_error_match.group(1)
            raw_fpath = file_match.group(1)
            target_path = Path(raw_fpath)
            if not target_path.is_absolute():
                target_path = workspace / target_path

            if target_path.is_file() and missing_symbol in self.KNOWN_SYMBOL_IMPORTS:
                import_stmt = self.KNOWN_SYMBOL_IMPORTS[missing_symbol]
                if import_stmt:
                    content = target_path.read_text(encoding="utf-8")
                    if import_stmt not in content:
                        candidate = f"{import_stmt}\n{content}"
                        rel_path = str(target_path.relative_to(workspace)) if target_path.is_relative_to(workspace) else target_path.name
                        return rel_path, RepairStrategyType.IMPORT_INJECTION, candidate

        # Diagnostic 2: Python files with AST issues or code smells
        for py_file in workspace.rglob("*.py"):
            parts = set(py_file.parts)
            if parts.intersection({".venv", "venv", "__pycache__", ".pytest_cache"}):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue

            # Check if file has syntax error
            try:
                ast.parse(content)
            except SyntaxError:
                # Syntax error present in this file
                continue

            # Apply AST transformations (mutable defaults, bare excepts, typing upgrades)
            changes = ASTCodeTransformer.apply_transformations(
                content,
                file_path=str(py_file),
                rules=[
                    RefactoringRuleType.MUTABLE_DEFAULT_FIX,
                    RefactoringRuleType.BARE_EXCEPT_FIX,
                    RefactoringRuleType.DEAD_CODE_ELIMINATION,
                ],
            )
            if changes:
                candidate = changes[-1].refactored_code
                rel_path = str(py_file.relative_to(workspace)) if py_file.is_relative_to(workspace) else py_file.name
                return rel_path, RepairStrategyType.AST_REWRITE, candidate

        return None, RepairStrategyType.HEURISTIC_PATCH, None

    async def _verify(
        self,
        workspace: Path,
        target_file: Path,
        test_command: str | None = None,
    ) -> tuple[bool, str]:
        """
        Validates whether the candidate repair succeeds.
        Uses test_command if given; otherwise falls back to Polyglot compilation check.
        """
        # Step 1: Always verify compilation first
        compile_res = self.compiler_matrix.compile(target_file)
        if not compile_res.is_success:
            return False, f"Compilation failed: {compile_res.stderr}"

        # Step 2: If test command specified, execute it
        if test_command:
            try:
                proc = await asyncio.create_subprocess_shell(
                    test_command,
                    cwd=str(workspace),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=60.0
                )
                stdout = stdout_b.decode("utf-8", errors="replace")
                stderr = stderr_b.decode("utf-8", errors="replace")
                if proc.returncode == 0:
                    return True, "All tests passed cleanly."
                return False, f"Test failed with exit {proc.returncode}:\n{stdout}\n{stderr}"
            except Exception as exc:
                return False, f"Test execution failed: {exc}"

        return True, "Compilation and AST check passed cleanly."
