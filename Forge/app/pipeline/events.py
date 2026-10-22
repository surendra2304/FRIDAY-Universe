"""
Structured event definitions and data schemas for the Execution Pipeline.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PipelineEventType(str, Enum):
    TASK_STARTED = "task.started"
    SYNTHESIS_STAGE_STARTED = "synthesis.stage.started"
    SYNTHESIS_STAGE_COMPLETED = "synthesis.stage.completed"
    FILE_WRITTEN = "file.written"
    REFACTORING_APPLIED = "refactoring.applied"
    COMPILATION_STARTED = "compilation.started"
    COMPILATION_COMPLETED = "compilation.completed"
    TESTS_STARTED = "tests.started"
    TESTS_COMPLETED = "tests.completed"
    SECURITY_AUDIT_STARTED = "security.audit.started"
    SECURITY_AUDIT_COMPLETED = "security.audit.completed"
    DELIVERY_COMPLETED = "delivery.completed"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"


@dataclass(frozen=True, slots=True)
class PipelineEvent:
    """Immutable event payload propagated across the Forge pipeline bus."""

    task_id: str
    event_type: PipelineEventType
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Converts event to dictionary format for JSON serialization."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        return data

    def to_json(self) -> str:
        """Serializes event to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineEvent:
        """Constructs an event from a dictionary."""
        return cls(
            task_id=data["task_id"],
            event_type=PipelineEventType(data["event_type"]),
            payload=data.get("payload", {}),
            event_id=data.get("event_id", str(uuid.uuid4())),
            timestamp=data.get(
                "timestamp", datetime.now(timezone.utc).isoformat()
            ),
            error=data.get("error"),
        )
