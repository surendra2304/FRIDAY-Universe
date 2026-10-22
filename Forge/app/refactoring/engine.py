"""
Autonomous Refactoring Engine for single files and project-wide cleanups.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.refactoring.analyzer import ASTCodeAnalyzer
from app.refactoring.models import (
    ComplexityMetrics,
    FileRefactoringChange,
    IssueSeverity,
    RefactoringIssue,
    RefactoringReport,
    RefactoringRuleType,
)
from app.refactoring.transformer import ASTCodeTransformer

logger = logging.getLogger("forge.refactoring.engine")


class RefactoringEngine:
    """
    Coordinates AST analysis, safe transformations, diff generation, and verification.
    """

    DEFAULT_EXCLUDES = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "sandbox_runs",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
    }

    def __init__(self, workspace_root: Path | str | None = None) -> None:
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else None

    def analyze_code(
        self,
        source_code: str,
        file_path: str = "snippet.py",
    ) -> tuple[list[RefactoringIssue], dict[str, ComplexityMetrics]]:
        """Analyzes a source string and returns discovered issues and function complexity metrics."""
        return ASTCodeAnalyzer.analyze_source(source_code, file_path=file_path)

    def refactor_code(
        self,
        source_code: str,
        file_path: str = "snippet.py",
        rules: list[RefactoringRuleType] | None = None,
    ) -> tuple[str, list[FileRefactoringChange]]:
        """
        Applies refactoring transformations to source code in memory.
        Returns the transformed code string and the list of applied changes.
        """
        changes = ASTCodeTransformer.apply_transformations(
            source_code, file_path=file_path, rules=rules
        )
        if not changes:
            return source_code, []

        final_code = changes[-1].refactored_code
        return final_code, changes

    def refactor_file(
        self,
        file_path: Path | str,
        dry_run: bool = False,
        rules: list[RefactoringRuleType] | None = None,
    ) -> tuple[bool, list[FileRefactoringChange], str | None]:
        """
        Refactors a single file on disk.
        Returns (success, applied_changes, error_message).
        """
        path = Path(file_path).resolve()
        if not path.is_file():
            return False, [], f"File not found: {path}"

        try:
            original_content = path.read_text(encoding="utf-8")
        except Exception as exc:
            return False, [], f"Failed to read file {path}: {exc}"

        final_code, changes = self.refactor_code(
            original_content,
            file_path=str(path),
            rules=rules,
        )

        if not changes:
            return True, [], None

        if not dry_run:
            try:
                path.write_text(final_code, encoding="utf-8")
                logger.info(
                    "Applied %d refactorings to %s",
                    len(changes),
                    path.name,
                )
            except Exception as exc:
                return False, changes, f"Failed to write refactored file {path}: {exc}"

        return True, changes, None

    def refactor_project(
        self,
        directory: Path | str,
        dry_run: bool = False,
        rules: list[RefactoringRuleType] | None = None,
        file_pattern: str = "*.py",
        exclude_dirs: set[str] | None = None,
    ) -> RefactoringReport:
        """
        Analyzes and refactors all matching files in a project directory.
        Returns a complete RefactoringReport with issues discovered and changes made.
        """
        target_dir = Path(directory).resolve()
        if not target_dir.is_dir():
            return RefactoringReport(
                success=False,
                summary=f"Target directory does not exist: {target_dir}",
                error_message=f"Directory not found: {target_dir}",
            )

        excludes = exclude_dirs or self.DEFAULT_EXCLUDES
        report = RefactoringReport()

        python_files: list[Path] = []
        for p in target_dir.rglob(file_pattern):
            # Check exclusions
            parts = set(p.parts)
            if parts.intersection(excludes):
                continue
            if p.is_file():
                python_files.append(p)

        report.total_files_analyzed = len(python_files)

        for file_path in python_files:
            try:
                rel_path = str(file_path.relative_to(target_dir))
            except ValueError:
                rel_path = str(file_path)

            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception as exc:
                report.issues.append(
                    RefactoringIssue(
                        file_path=rel_path,
                        line_number=1,
                        column=1,
                        rule_type=RefactoringRuleType.MODERNIZE_SYNTAX,
                        severity=IssueSeverity.WARNING,
                        message=f"Could not read file: {exc}",
                    )
                )
                continue

            # 1. Analyze
            issues, _ = self.analyze_code(content, file_path=rel_path)
            report.issues.extend(issues)

            # 2. Refactor
            success, changes, err = self.refactor_file(
                file_path=file_path,
                dry_run=dry_run,
                rules=rules,
            )
            if changes:
                report.changes_applied.extend(changes)
            if not success and err:
                report.error_message = err

        report.total_issues_found = len(report.issues)
        report.success = report.error_message is None
        mode = "Dry Run" if dry_run else "In-Place"
        report.summary = (
            f"Refactoring pass ({mode}): Analyzed {report.total_files_analyzed} files, "
            f"found {report.total_issues_found} issues, applied {len(report.changes_applied)} changes."
        )
        return report
