from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from .models import Checkpoint


class CheckpointStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def save(self, checkpoint: Checkpoint) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(checkpoint)
        for key, value in list(payload.items()):
            if hasattr(value, "value"):
                payload[key] = value.value
        fd, tmp = tempfile.mkstemp(
            prefix=".forge-checkpoint-", suffix=".json", dir=self.path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True, default=str)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def load(self) -> dict:
        with self.path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
