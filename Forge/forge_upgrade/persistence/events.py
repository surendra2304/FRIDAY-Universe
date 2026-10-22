from __future__ import annotations

import json
import os
from pathlib import Path


class DurableEventLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: dict) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True, default=str) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        rows = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rows.append(json.loads(line))
        return rows
