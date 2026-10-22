"""
Anti-Loop Controller for Project FORGE Recovery Subsystem.
Prevents infinite repair loops, duplicate patch application, and escalates unresolved failures.
"""

import hashlib

from app.core.logging import get_logger
from app.recovery.classifier import FailureClass

logger = get_logger("recovery.loop_guard")


class RepairLoopDetectedError(RuntimeError):
    """Raised when an infinite repair loop or duplicate patch application is detected."""


class AntiLoopController:
    """Enforces retry budgets, deduplicates patches, and governs escalation boundaries."""

    def __init__(self, max_retries_per_class: int = 3, max_total_retries: int = 8):
        self.max_retries_per_class = max_retries_per_class
        self.max_total_retries = max_total_retries
        # task_id -> {FailureClass: count}
        self._class_retries: dict[str, dict[FailureClass, int]] = {}
        # task_id -> Set of patch hashes
        self._patch_hashes: dict[str, set[str]] = {}

    def _get_hash(self, patch_content: str) -> str:
        return hashlib.sha256(patch_content.strip().encode("utf-8")).hexdigest()

    def can_attempt_repair(
        self,
        task_id: str,
        failure_class: FailureClass,
        patch_content: str | None = None,
    ) -> tuple[bool, str]:
        """
        Check if a repair attempt is permitted under anti-loop constraints.
        Returns (allowed: bool, reason: str).
        """
        if task_id not in self._class_retries:
            self._class_retries[task_id] = {}
        if task_id not in self._patch_hashes:
            self._patch_hashes[task_id] = set()

        total_retries = sum(self._class_retries[task_id].values())
        if total_retries >= self.max_total_retries:
            msg = f"Total recovery budget exhausted ({total_retries}/{self.max_total_retries} attempts)."
            logger.warning(f"[Task {task_id}] {msg}")
            return False, msg

        current_class_count = self._class_retries[task_id].get(failure_class, 0)
        if current_class_count >= self.max_retries_per_class:
            msg = f"Class recovery limit reached for '{failure_class.value}' ({current_class_count}/{self.max_retries_per_class} attempts)."
            logger.warning(f"[Task {task_id}] {msg}")
            return False, msg

        if patch_content:
            p_hash = self._get_hash(patch_content)
            if p_hash in self._patch_hashes[task_id]:
                msg = (
                    "Duplicate patch detected without new evidence. Anti-loop prevention triggered."
                )
                logger.warning(f"[Task {task_id}] {msg}")
                return False, msg

        return True, "Repair attempt permitted."

    def assert_can_attempt_repair(
        self,
        task_id: str,
        failure_class: FailureClass,
        patch_content: str | None = None,
    ) -> None:
        """Check if repair attempt is permitted. Raises RepairLoopDetectedError on violation."""
        allowed, reason = self.can_attempt_repair(
            task_id=task_id,
            failure_class=failure_class,
            patch_content=patch_content,
        )
        if not allowed:
            raise RepairLoopDetectedError(f"Anti-Loop Violation: {reason}")

    def record_repair_attempt(
        self,
        task_id: str,
        failure_class: FailureClass,
        patch_content: str,
    ) -> None:
        """Record a repair attempt and register the patch hash."""
        if task_id not in self._class_retries:
            self._class_retries[task_id] = {}
        if task_id not in self._patch_hashes:
            self._patch_hashes[task_id] = set()

        self._class_retries[task_id][failure_class] = (
            self._class_retries[task_id].get(failure_class, 0) + 1
        )
        p_hash = self._get_hash(patch_content)
        self._patch_hashes[task_id].add(p_hash)

        logger.info(
            f"[Task {task_id}] Recorded repair attempt for '{failure_class.value}' "
            f"(count={self._class_retries[task_id][failure_class]}, hash={p_hash[:8]})"
        )

    def get_retry_count(self, task_id: str, failure_class: FailureClass | None = None) -> int:
        """Get retry count for a specific class or all classes."""
        if task_id not in self._class_retries:
            return 0
        if failure_class:
            return self._class_retries[task_id].get(failure_class, 0)
        return sum(self._class_retries[task_id].values())

    def reset_task(self, task_id: str) -> None:
        """Reset anti-loop tracking for a task upon full recovery."""
        self._class_retries.pop(task_id, None)
        self._patch_hashes.pop(task_id, None)


anti_loop_controller = AntiLoopController()
