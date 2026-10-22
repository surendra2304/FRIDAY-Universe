from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from dataclasses import dataclass
from typing import Literal

RecordStatus = Literal["in_flight", "completed"]


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    key: str
    response_hash: str | None
    created_at: float
    status: RecordStatus = "completed"


class IdempotencyCapacityError(RuntimeError):
    """Raised when the bounded store cannot evict a live in-flight operation."""


class IdempotencyStore:
    """Thread-safe, bounded in-memory idempotency registry.

    `try_claim` atomically reserves a new key before side effects begin. A duplicate
    key returns False whether its original operation is still in-flight or completed.
    `remember` stores the completion fingerprint and starts the completed-record TTL.
    Failed operations may release only their own in-flight reservation.
    """

    def __init__(self, ttl_seconds: float = 3600, max_items: int = 50000):
        try:
            ttl_value = float(ttl_seconds)
        except (OverflowError, TypeError, ValueError) as exc:
            raise ValueError("ttl_seconds must be a finite positive number") from exc
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, (int, float))
            or not math.isfinite(ttl_value)
            or ttl_value <= 0
        ):
            raise ValueError("ttl_seconds must be a finite positive number")
        if isinstance(max_items, bool) or not isinstance(max_items, int):
            raise TypeError("max_items must be an integer")
        if max_items <= 0:
            raise ValueError("max_items must be positive")

        self.ttl = ttl_value
        self.max_items = max_items
        self._items: dict[str, IdempotencyRecord] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _require_nonempty(value: str, name: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        if not value.strip():
            raise ValueError(f"{name} must not be empty")
        return value

    @classmethod
    def make_key(cls, task_id: str, intent_hash: str) -> str:
        """Build a stable digest using an unambiguous canonical encoding."""
        identity = [
            cls._require_nonempty(task_id, "task_id"),
            cls._require_nonempty(intent_hash, "intent_hash"),
        ]
        serialized = json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _purge_expired_locked(self, now: float) -> None:
        # The TTL is a completed-result retention policy, not a lease on active work.
        # Expiring a still-running claim can admit duplicate side effects while its first
        # execution is still in progress. A crashed in-memory process loses the whole
        # registry on restart, so active entries are deliberately retained until release
        # or completion instead of being guessed stale based on elapsed wall time.
        expired = [
            key
            for key, record in self._items.items()
            if record.status == "completed" and now - record.created_at >= self.ttl
        ]
        for key in expired:
            self._items.pop(key, None)

    def _make_room_locked(self, now: float) -> None:
        self._purge_expired_locked(now)
        if len(self._items) < self.max_items:
            return

        # Never evict a live in-flight reservation: doing so would allow the same
        # side effect to be admitted twice. Prefer the oldest completed response.
        completed = [
            record
            for record in self._items.values()
            if record.status == "completed"
        ]
        if not completed:
            raise IdempotencyCapacityError(
                "idempotency capacity is full of in-flight operations"
            )
        oldest = min(completed, key=lambda record: record.created_at)
        self._items.pop(oldest.key, None)

    def try_claim(self, key: str) -> bool:
        """Atomically reserve a new key; return False if a live key already exists."""
        key = self._require_nonempty(key, "key")
        with self._lock:
            now = time.monotonic()
            self._purge_expired_locked(now)
            if key in self._items:
                return False
            self._make_room_locked(now)
            self._items[key] = IdempotencyRecord(
                key=key,
                response_hash=None,
                created_at=now,
                status="in_flight",
            )
            return True

    def seen(self, key: str) -> bool:
        """Return whether a live in-flight or completed key is recorded."""
        key = self._require_nonempty(key, "key")
        with self._lock:
            now = time.monotonic()
            self._purge_expired_locked(now)
            return key in self._items

    def get(self, key: str) -> IdempotencyRecord | None:
        """Return the live record, including its in-flight/completed status."""
        key = self._require_nonempty(key, "key")
        with self._lock:
            now = time.monotonic()
            self._purge_expired_locked(now)
            return self._items.get(key)

    def remember(self, key: str, response_hash: str) -> None:
        """Store a completed response, updating an existing key without evicting others."""
        key = self._require_nonempty(key, "key")
        response_hash = self._require_nonempty(response_hash, "response_hash")
        with self._lock:
            now = time.monotonic()
            self._purge_expired_locked(now)
            # Completion of a claimed key does not consume another slot. Resetting
            # created_at starts its retention window when the result becomes durable.
            self._items[key] = IdempotencyRecord(
                key=key,
                response_hash=response_hash,
                created_at=now,
                status="completed",
            ) if key in self._items else self._new_completed_record_locked(
                key, response_hash, now
            )

    def _new_completed_record_locked(
        self, key: str, response_hash: str, now: float
    ) -> IdempotencyRecord:
        self._make_room_locked(now)
        return IdempotencyRecord(
            key=key,
            response_hash=response_hash,
            created_at=now,
            status="completed",
        )

    def release(self, key: str) -> bool:
        """Release a failed in-flight claim without erasing completed idempotency data."""
        key = self._require_nonempty(key, "key")
        with self._lock:
            now = time.monotonic()
            self._purge_expired_locked(now)
            record = self._items.get(key)
            if record is None or record.status != "in_flight":
                return False
            self._items.pop(key, None)
            return True
