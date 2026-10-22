"""
Pydantic data models for State, Memory, Task Lifecycle, Checkpoints, and Audit Events in FORGE.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    """The 8 formal states of the FORGE Task State Lifecycle."""

    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# Backward compatibility alias
TaskStatus = TaskState


class TaskMode(str, Enum):
    """Execution modes for FORGE tasks."""

    AUTONOMOUS = "autonomous"
    INTERACTIVE = "interactive"
    PLAN_ONLY = "plan_only"
    VERIFY_ONLY = "verify_only"


def generate_task_id(sequence_num: int = 1) -> str:
    """Generate a human-readable unique task identifier formatted as: task<task_num><DDMMYYYY><HHMMSS>."""
    now = datetime.now(UTC)
    return f"task{sequence_num:02d}{now.strftime('%d%m%Y%H%M%S')}"


class ProjectWorkspace(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., description="Project name")
    description: str | None = Field(default=None, description="Project purpose or goal")
    workspace_path: str = Field(
        ..., description="Absolute or relative filesystem path to isolated workspace"
    )
    config: dict[str, Any] = Field(
        default_factory=dict, description="Project specific configurations"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskEntity(BaseModel):
    """Persistent representation of an engineering task in FORGE."""

    id: str = Field(default_factory=generate_task_id)
    goal: str = Field(..., description="High-level engineering objective")
    requirements: list[str] = Field(
        default_factory=list, description="Explicit functional or technical constraints"
    )
    mode: TaskMode = Field(default=TaskMode.AUTONOMOUS, description="Execution mode")
    workspace_path: str = Field(..., description="Root path of task isolated sandbox")
    max_budget: float = Field(default=10.0, description="Max USD budget allocated for this task")
    budget_consumed: float = Field(
        default=0.0, description="Total USD budget spent on provider inference"
    )
    state: TaskState = Field(default=TaskState.PENDING, description="Current lifecycle state")
    progress_percentage: int = Field(
        default=0, ge=0, le=100, description="Estimated completion progress"
    )
    error_message: str | None = Field(
        default=None, description="Error reason if state is FAILED or BLOCKED"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary task metadata and correlated identifiers"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditEvent(BaseModel):
    """Structured telemetry/audit event emitted during task lifecycle."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str = Field(..., description="Associated Task ID")
    event_type: str = Field(
        ..., description="Event identifier (e.g. task.created, plan.created, etc.)"
    )
    payload: dict[str, Any] = Field(default_factory=dict, description="Event payload data")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ArtifactRecord(BaseModel):
    """Metadata record for files generated in the artifacts directory."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str = Field(..., description="Associated Task ID")
    name: str = Field(..., description="Artifact filename or identifier")
    path: str = Field(..., description="Filesystem path to artifact")
    file_type: str = Field(default="text/plain", description="MIME or file type")
    size_bytes: int = Field(default=0, description="File size in bytes")
    checksum: str | None = Field(default=None, description="SHA256 checksum")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(..., description="Short task title")
    description: str = Field(default="", description="Detailed step instructions")
    status: TaskState = Field(default=TaskState.PENDING)
    dependencies: list[str] = Field(default_factory=list, description="IDs of prerequisite tasks")
    assigned_agent: str | None = Field(default=None, description="Agent type or name assigned")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary task context and metadata"
    )
    result: dict[str, Any] | None = Field(
        default=None, description="Output artifacts or return data"
    )
    error: str | None = Field(default=None, description="Error message if failed")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskEdge(BaseModel):
    source: str = Field(..., description="Source TaskNode ID")
    target: str = Field(..., description="Target TaskNode ID")
    condition: str | None = Field(
        default=None, description="Optional conditional transition expression"
    )


class TaskGraph(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str = Field(..., description="Associated ProjectWorkspace or Task ID")
    goal: str = Field(..., description="High-level engineering goal")
    nodes: dict[str, TaskNode] = Field(
        default_factory=dict, description="Lookup of task nodes by ID"
    )
    edges: list[TaskEdge] = Field(
        default_factory=list, description="Directed dependencies between nodes"
    )
    status: TaskState = Field(default=TaskState.PENDING)
    current_node_id: str | None = Field(default=None, description="Currently executing node")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def add_node(self, node: TaskNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, source_id: str, target_id: str, condition: str | None = None) -> None:
        self.edges.append(TaskEdge(source=source_id, target=target_id, condition=condition))
        if target_id in self.nodes and source_id not in self.nodes[target_id].dependencies:
            self.nodes[target_id].dependencies.append(source_id)


class Checkpoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str = Field(..., description="Associated ProjectWorkspace or Task ID")
    task_id: str | None = Field(default=None, description="Current TaskNode ID at checkpoint")
    step_number: int = Field(default=0, description="Sequential step counter")
    state_data: dict[str, Any] = Field(
        default_factory=dict, description="Serialized snapshot state"
    )
    checksum: str | None = Field(default=None, description="Integrity hash of the state")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    description: str | None = Field(
        default=None, description="Human-readable milestone description"
    )
