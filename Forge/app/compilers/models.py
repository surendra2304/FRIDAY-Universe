"""
Domain models and diagnostic structures for the Polyglot Compiler & Build Matrix Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class LanguageTarget(str, Enum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CPP = "cpp"
    C = "c"


class CompilationStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"
    TOOL_NOT_FOUND = "tool_not_found"


class DiagnosticSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class CompilerDiagnostic:
    """Individual compiler error, warning, or linter note."""

    file_path: str
    line: int
    column: int
    severity: DiagnosticSeverity
    message: str
    code_snippet: str = ""
    rule_code: str | None = None


@dataclass(frozen=True, slots=True)
class CompilationOptions:
    """Configuration options for compilation and type-checking runs."""

    timeout_seconds: float = 30.0
    optimization_level: str = "O0"
    strict_mode: bool = True
    extra_flags: list[str] = field(default_factory=list)
    working_dir: Path | None = None
    output_dir: Path | None = None


@dataclass(slots=True)
class CompilationResult:
    """Outcome of a compilation, syntax check, or build operation."""

    target_language: LanguageTarget
    status: CompilationStatus
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    command_executed: list[str] = field(default_factory=list)
    diagnostics: list[CompilerDiagnostic] = field(default_factory=list)
    artifact_path: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status == CompilationStatus.SUCCESS and self.exit_code == 0

    @property
    def error_count(self) -> int:
        return sum(
            1 for d in self.diagnostics if d.severity == DiagnosticSeverity.ERROR
        )

    @property
    def warning_count(self) -> int:
        return sum(
            1 for d in self.diagnostics if d.severity == DiagnosticSeverity.WARNING
        )
