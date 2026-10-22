"""
Domain models and data structures for the Automated Refactoring Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RefactoringRuleType(str, Enum):
    RENAME_SYMBOL = "rename_symbol"
    EXTRACT_FUNCTION = "extract_function"
    MODERNIZE_SYNTAX = "modernize_syntax"
    OPTIMIZE_IMPORTS = "optimize_imports"
    DEAD_CODE_ELIMINATION = "dead_code_elimination"
    REDUCE_COMPLEXITY = "reduce_complexity"
    MUTABLE_DEFAULT_FIX = "mutable_default_fix"
    BARE_EXCEPT_FIX = "bare_except_fix"
    TYPE_ANNOTATION_UPGRADE = "type_annotation_upgrade"


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class ComplexityMetrics:
    """Quantitative code complexity metrics for a function or module."""

    cyclomatic_complexity: int = 1
    cognitive_complexity: int = 0
    max_nesting_depth: int = 1
    lines_of_code: int = 0
    num_arguments: int = 0
    num_returns: int = 0

    @property
    def is_overly_complex(self) -> bool:
        """Determines if the function exceeds clean code thresholds."""
        return (
            self.cyclomatic_complexity > 10
            or self.max_nesting_depth > 4
            or self.lines_of_code > 50
        )


@dataclass(frozen=True, slots=True)
class RefactoringIssue:
    """An identified code smell, defect, or refactoring opportunity."""

    file_path: str
    line_number: int
    column: int
    rule_type: RefactoringRuleType
    severity: IssueSeverity
    message: str
    suggested_fix: str | None = None
    context_code: str = ""


@dataclass(frozen=True, slots=True)
class FileRefactoringChange:
    """Record of a safe code transformation applied to a file."""

    file_path: str
    rule_type: RefactoringRuleType
    original_code: str
    refactored_code: str
    diff: str
    description: str
    metrics_before: ComplexityMetrics | None = None
    metrics_after: ComplexityMetrics | None = None
    safety_score: float = 1.0


@dataclass(slots=True)
class RefactoringReport:
    """Overall summary report of a project-wide refactoring pass."""

    total_files_analyzed: int = 0
    total_issues_found: int = 0
    issues: list[RefactoringIssue] = field(default_factory=list)
    changes_applied: list[FileRefactoringChange] = field(default_factory=list)
    success: bool = True
    summary: str = ""
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
