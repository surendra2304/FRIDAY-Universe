from __future__ import annotations

import hashlib
import threading
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RepairAttempt:
    task_id: str
    failure_signature: str
    patch_hash: str
    attempt: int
    stage: str


class RepairController:
    def __init__(self, per_failure: int = 3, total: int = 8):
        self.per_failure = per_failure
        self.total = total
        self._lock = threading.RLock()
        self._attempts: dict[str, list[RepairAttempt]] = defaultdict(list)

    @staticmethod
    def failure_signature(category: str, message: str) -> str:
        normalized = " ".join(message.strip().lower().split())
        return hashlib.sha256(f"{category}|{normalized}".encode()).hexdigest()

    @staticmethod
    def patch_hash(patch_text: str) -> str:
        return hashlib.sha256(patch_text.strip().encode()).hexdigest()

    def allow(self, task_id: str, category: str, message: str, patch_text: str) -> tuple[bool, str]:
        with self._lock:
            attempts = self._attempts[task_id]
            signature = self.failure_signature(category, message)
            ph = self.patch_hash(patch_text)
            if len(attempts) >= self.total:
                return False, "total repair cap reached"
            same_failure = [a for a in attempts if a.failure_signature == signature]
            if len(same_failure) >= self.per_failure:
                return False, "per-failure repair cap reached"
            if any(a.patch_hash == ph for a in attempts):
                return False, "duplicate patch rejected"
            return True, "repair permitted"

    def record(
        self, task_id: str, category: str, message: str, patch_text: str, stage: str
    ) -> RepairAttempt:
        with self._lock:
            sig = self.failure_signature(category, message)
            attempt = len([a for a in self._attempts[task_id] if a.failure_signature == sig]) + 1
            record = RepairAttempt(task_id, sig, self.patch_hash(patch_text), attempt, stage)
            self._attempts[task_id].append(record)
            return record

    def snapshot(self, task_id: str) -> tuple[RepairAttempt, ...]:
        with self._lock:
            return tuple(self._attempts[task_id])
