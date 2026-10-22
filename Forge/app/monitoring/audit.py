"""
Structured JSON Logging and Audit Trail Logger for Project FORGE.
Captures compliance and security events for sensitive operations with key redaction.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("monitoring.audit")


class AuditEvent(BaseModel):
    """Structured audit log entry for critical system events."""

    event_type: str  # task_submitted, task_cancelled, proposal_applied, backup_created
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    task_id: str | None = None
    client_key_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = None


class AuditLogger:
    """Manages appending and reading JSONL audit logs."""

    def __init__(self):
        self.settings = get_settings()

    def _get_audit_file(self) -> Path:
        audit_dir = self.settings.data_dir / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        return audit_dir / f"audit_{today}.jsonl"

    def record_event(
        self,
        event_type: str,
        task_id: str | None = None,
        raw_key: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Record an audit event to disk with API key identifier redaction."""
        key_id = None
        if raw_key:
            # Show only first 4 chars for auditing, redact the rest
            key_id = f"{raw_key[:4]}...{raw_key[-2:]}" if len(raw_key) > 6 else "key_***"

        event = AuditEvent(
            event_type=event_type,
            task_id=task_id,
            client_key_id=key_id,
            details=details or {},
            ip_address=ip_address,
        )

        try:
            audit_file = self._get_audit_file()
            line = event.model_dump_json() + "\n"
            with open(audit_file, "a", encoding="utf-8") as f:
                f.write(line)
            logger.info(f"Audit event recorded: {event_type} (task={task_id})")
        except Exception as e:
            logger.warning(f"Could not persist audit record: {e}")

        return event


audit_logger = AuditLogger()
