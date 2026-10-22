"""
Data models and telemetry structures for the Autonomous Closed-Loop Self-Healing Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RepairStrategyType(str, Enum):
    AST_REWRITE = "ast_rewrite"
    IMPORT_INJECTION = "import_injection"
    SYNTAX_CORRECTION = "syntax_correction"
    HEURISTIC_PATCH = "heuristic_patch"


@dataclass(frozen=True, slots=True)
class RepairAttempt:
    """Record of a single repair cycle attempt."""

    attempt_number: int
    strategy: RepairStrategyType
    target_file: str
    patch_applied: str
    verification_passed: bool
    output_message: str
    duration_ms: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(slots=True)
class RepairResult:
    """Consolidated outcome of the self-repair loop."""

    success: bool
    rounds_executed: int
    resolved_files: list[str] = field(default_factory=list)
    summary: str = ""
    attempts: list[RepairAttempt] = field(default_factory=list)
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
