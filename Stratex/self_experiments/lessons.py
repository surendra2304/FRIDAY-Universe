"""Lesson delivery — Memora via the shared memory fabric.

Mirrors Forge's FabricLessonWriter (TASK-FRG-017) with Stratex's
identity: lessons are procedural-type memories written through
mesh.memory_fabric with owner_agent="STRATEX". A delivery counts as
made when record() returns without raising; anything else leaves the
lesson pending in the loop's local lessons ledger for retry
(loop.flush_pending_lessons).

Scopes: every lesson goes to Stratex's private section
(MemoryScope.AGENT). A FAILED experiment's lesson is ALSO delivered
at MemoryScope.UNIVERSAL — the owner's standing rule R, so one
agent's mistake teaches all ten.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("stratex.self_experiments.lessons")


class FabricLessonWriter:
    """Delivers lessons to Memora through mesh.memory_fabric."""

    def __init__(self, fabric: Any | None = None):
        self._fabric = fabric

    def _get_fabric(self) -> Any:
        if self._fabric is None:
            from mesh.memory_fabric import UniversalMemoryFabric

            self._fabric = UniversalMemoryFabric()
        return self._fabric

    def deliver(
        self, content: str, metadata: dict[str, Any], *, universal: bool
    ) -> bool:
        try:
            from mesh.memory_fabric import MemoryScope

            fabric = self._get_fabric()
            fabric.record(
                owner_agent="STRATEX",
                content_text=content,
                scope=MemoryScope.UNIVERSAL if universal else MemoryScope.AGENT,
                memory_type="procedural",
                source="stratex_self_experiment",
                importance=0.8,
                confidence=1.0,
                metadata=metadata,
            )
            return True
        except Exception as exc:
            logger.warning(f"self-experiment lesson delivery failed: {exc}")
            return False
