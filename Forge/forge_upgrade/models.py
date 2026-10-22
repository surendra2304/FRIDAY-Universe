from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence


class TaskPhase(str, Enum):
    INTAKE = "intake"
    UNDERSTAND = "understand"
    PLAN = "plan"
    IMPLEMENT = "implement"
    TEST = "test"
    REVIEW = "review"
    REPAIR = "repair"
    DELIVER = "deliver"
    BLOCKED = "blocked"
    COMPLETE = "complete"
    FAILED = "failed"


class NodeStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class RepoSnapshot:
    repo_path: str
    commit_sha: str
    dirty: bool
    tracked_files: int
    fingerprint: str

    @classmethod
    def from_listing(
        cls, repo_path: str, commit_sha: str, dirty: bool, paths: Sequence[str]
    ) -> "RepoSnapshot":
        normalized = "\n".join(sorted(paths))
        fp = hashlib.sha256(normalized.encode()).hexdigest()
        return cls(repo_path, commit_sha, dirty, len(paths), fp)


@dataclass(frozen=True, slots=True)
class TaskIdentity:
    task_id: str
    goal: str
    requirements: tuple[str, ...] = ()
    repo_url: str | None = None
    local_path: str | None = None


@dataclass(frozen=True, slots=True)
class TaskBudget:
    max_usd: float = 10.0
    max_model_calls: int = 100
    max_commands: int = 200
    max_runtime_seconds: int = 3600


@dataclass(frozen=True, slots=True)
class PlanNode:
    node_id: str
    title: str
    description: str
    phase: TaskPhase
    dependencies: tuple[str, ...] = ()
    assigned_role: str = "developer"
    expected_outputs: tuple[str, ...] = ()
    verification_commands: tuple[str, ...] = ()


@dataclass(slots=True)
class PlanGraph:
    graph_id: str
    nodes: dict[str, PlanNode]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def validate(self) -> list[str]:
        errors: list[str] = []
        for key, node in self.nodes.items():
            if key != node.node_id:
                errors.append(f"node key mismatch: {key!r} != {node.node_id!r}")
            for dep in node.dependencies:
                if dep == node.node_id:
                    errors.append(f"self dependency: {node.node_id}")
                elif dep not in self.nodes:
                    errors.append(f"missing dependency: {node.node_id}->{dep}")
        # Kahn cycle detection
        indeg = {k: 0 for k in self.nodes}
        out: dict[str, list[str]] = {k: [] for k in self.nodes}
        for n in self.nodes.values():
            for dep in n.dependencies:
                if dep in self.nodes:
                    indeg[n.node_id] += 1
                    out[dep].append(n.node_id)
        queue = [k for k, v in indeg.items() if v == 0]
        seen = 0
        while queue:
            x = queue.pop()
            seen += 1
            for y in out[x]:
                indeg[y] -= 1
                if indeg[y] == 0:
                    queue.append(y)
        if seen != len(self.nodes):
            errors.append("dependency cycle detected")
        return errors


@dataclass(frozen=True, slots=True)
class ToolIntent:
    task_id: str
    role: str
    tool: str
    action: str
    arguments: Mapping[str, Any]
    risk: RiskLevel
    intent_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def fingerprint(self) -> str:
        raw = json.dumps(
            {
                "task_id": self.task_id,
                "role": self.role,
                "tool": self.tool,
                "action": self.action,
                "arguments": self.arguments,
                "risk": self.risk.value,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ToolResult:
    intent_id: str
    success: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    artifact_paths: tuple[str, ...] = ()
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class FileChange:
    path: str
    before_sha256: str | None
    after_sha256: str | None
    operation: str
    bytes_changed: int = 0


@dataclass(frozen=True, slots=True)
class PatchCandidate:
    patch_id: str
    files: tuple[FileChange, ...]
    rationale: str
    content_fingerprint: str
    base_commit_sha: str
    generated_by: str

    @classmethod
    def fingerprint_for(cls, changes: Sequence[FileChange]) -> str:
        raw = "\n".join(
            f"{x.operation}|{x.path}|{x.before_sha256}|{x.after_sha256}"
            for x in sorted(changes, key=lambda x: x.path)
        )
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class VerificationCheck:
    name: str
    command: str
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    mandatory: bool = True
    stdout_truncated: bool = False
    stderr_truncated: bool = False


@dataclass(frozen=True, slots=True)
class VerificationReport:
    task_id: str
    checks: tuple[VerificationCheck, ...]
    baseline: bool = False
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def passed(self) -> bool:
        return all(x.passed for x in self.checks if x.mandatory)

    @property
    def mandatory_failures(self) -> tuple[str, ...]:
        return tuple(x.name for x in self.checks if x.mandatory and not x.passed)


@dataclass(frozen=True, slots=True)
class Checkpoint:
    task_id: str
    sequence: int
    phase: TaskPhase
    commit_sha: str | None
    graph_hash: str
    workspace_hash: str
    verification_passed: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class BudgetLedger:
    usd_spent: float = 0.0
    model_calls: int = 0
    commands: int = 0
    runtime_seconds: float = 0.0

    def within(self, budget: TaskBudget) -> bool:
        return (
            self.usd_spent <= budget.max_usd
            and self.model_calls <= budget.max_model_calls
            and self.commands <= budget.max_commands
            and self.runtime_seconds <= budget.max_runtime_seconds
        )
