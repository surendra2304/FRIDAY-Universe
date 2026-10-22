"""
Pydantic Request and Response Schemas for the FORGE REST & FRIDAY Management API.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.memory.models import TaskMode, TaskState
from app.providers.base import ProviderCapabilities, ProviderHealthStatus

# --- Task Metadata & Requests ---


class TaskMetadata(BaseModel):
    source: str | None = Field(default=None, description="Optional caller identifier")
    priority: str = Field(
        default="normal", description="Task execution priority: normal | high | urgent"
    )
    deadline: datetime | None = Field(default=None, description="Optional target deadline")
    tags: list[str] = Field(default_factory=list, description="Categorization or project tags")
    webhook_url: str | None = Field(
        default=None, description="Optional webhook URL for progress and lifecycle notifications"
    )
    archived: bool = Field(default=False, description="Soft-archive status")


class TaskCreateRequest(BaseModel):
    # `goal` used to have no upper bound at all -- only the global 8 MB
    # request-body middleware limit (app/main.py) applied. Live-reproduced
    # (2026-10-07): a single 500 KB goal took ~7 seconds for plain task
    # *intake* alone (before any synthesis/execution even starts), because
    # the raw text is repeatedly scanned by goal classification, keyword
    # matching, and template detection. A client submitting even a handful
    # of such requests concurrently could starve the whole process. 20,000
    # characters is already far more than any legitimate engineering brief
    # needs (the deterministic synthesizer itself only ever uses the first
    # 200 characters of `raw` in generated docstrings/descriptions).
    goal: str = Field(
        ...,
        description="High-level engineering objective",
        min_length=3,
        max_length=20_000,
    )
    requirements: list[str] = Field(
        default_factory=list,
        description="Explicit constraints or requirements",
        max_length=200,
    )
    mode: TaskMode = Field(default=TaskMode.AUTONOMOUS, description="Execution mode")
    workspace: str | None = Field(
        default=None, description="Optional custom workspace path or identifier"
    )
    repo_url: str | None = Field(
        default=None, description="Optional remote Git repository URL to clone"
    )
    local_path: str | None = Field(
        default=None, description="Optional local directory path to copy into project sandbox"
    )
    max_budget: float = Field(default=10.0, ge=0.1, description="Maximum allowed budget in USD")
    task_metadata: TaskMetadata | None = Field(
        default=None, description="Optional caller task metadata"
    )
    webhook_url: str | None = Field(
        default=None, description="Optional webhook URL for progress events"
    )


class TaskActionRequest(BaseModel):
    reason: str | None = Field(default=None, description="Optional explanation for the action")


# --- Task Responses ---


class TaskSummaryResponse(BaseModel):
    id: str
    goal: str
    state: TaskState
    progress_percentage: int
    project_type: str = "default"
    priority: str = "normal"
    created_at: datetime
    updated_at: datetime
    archived: bool = False


class TaskResponse(BaseModel):
    id: str
    goal: str
    requirements: list[str]
    mode: TaskMode
    workspace_path: str
    max_budget: float
    budget_consumed: float
    state: TaskState
    progress_percentage: int
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class TaskDetailResponse(TaskResponse):
    workspace_dirs: dict[str, str] = Field(default_factory=dict)
    current_stage: str | None = None
    estimated_remaining_seconds: float | None = None
    estimated_completion_at: datetime | None = None
    provenance_summary: str | None = None
    latest_checkpoint_id: str | None = None
    checkpoints_count: int = 0


class TaskActionResponse(BaseModel):
    task_id: str
    previous_state: TaskState
    current_state: TaskState
    message: str
    checkpoint_id: str | None = None


# --- Deep Inspection & Logs ---


class FileInspection(BaseModel):
    path: str
    size_bytes: int
    lines_count: int


class TaskInspectResponse(BaseModel):
    task_id: str
    goal: str
    state: TaskState
    files_created: list[FileInspection] = Field(default_factory=list)
    verification_summary: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class LogEntry(BaseModel):
    timestamp: str | None = None
    level: str = "INFO"
    message: str


class TaskLogsResponse(BaseModel):
    task_id: str
    total_lines: int
    logs: list[LogEntry] = Field(default_factory=list)


# --- Run / Audit Event Schemas ---


class AuditEventResponse(BaseModel):
    id: str
    task_id: str
    event_type: str
    payload: dict[str, Any]
    timestamp: datetime


class RunAuditResponse(BaseModel):
    task_id: str
    total_events: int
    events: list[AuditEventResponse]


# --- Artifact Schemas ---


class ArtifactResponse(BaseModel):
    id: str
    task_id: str
    name: str
    path: str
    file_type: str
    size_bytes: int
    checksum: str | None = None
    created_at: datetime


# --- Capabilities & Diagnostic Schemas ---


class EngineCapabilitiesResponse(BaseModel):
    engine_name: str = "FORGE Autonomous Software Engineering Engine"
    version: str
    supported_modes: list[str]
    lifecycle_states: list[str]
    features: dict[str, bool]
    provider: ProviderCapabilities


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    database_connected: bool
    default_provider: ProviderHealthStatus
    capabilities: ProviderCapabilities


class TimelineEvent(BaseModel):
    id: str
    task_id: str
    run_id: str
    stage: str
    agent_id: str
    provider_model: str
    action: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    duration_ms: float = 0.0
    checkpoint_id: str | None = None
    timestamp: datetime


class TimelineResponse(BaseModel):
    task_id: str
    total_events: int
    stages_covered: list[str]
    timeline: list[TimelineEvent]
