from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class AuditRecord:
    timestamp: str
    task_id: str
    event: str
    actor: str
    details: dict[str, Any]


class AuditLog:
    def __init__(self):
        self.records: list[AuditRecord] = []

    def append(
        self, task_id: str, event: str, actor: str, details: dict[str, Any] | None = None
    ) -> None:
        self.records.append(
            AuditRecord(
                datetime.now(timezone.utc).isoformat(),
                task_id,
                event,
                actor,
                details or {},
            )
        )

    def dump(self) -> str:
        return json.dumps([asdict(x) for x in self.records], indent=2, sort_keys=True, default=str)

    def find(self, event: str) -> list[AuditRecord]:
        return [x for x in self.records if x.event == event]
