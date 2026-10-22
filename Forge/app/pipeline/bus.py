"""
Asynchronous Pub/Sub Event Bus and Streaming Channel for the Execution Pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.pipeline.events import PipelineEvent, PipelineEventType

logger = logging.getLogger("forge.pipeline.bus")

SubscriberCallback = Callable[[PipelineEvent], Awaitable[None]]


class PipelineEventBus:
    """
    In-memory async pub/sub bus with backpressure handling, subscriber routing,
    and event streaming.
    """

    def __init__(self, max_history_per_task: int = 1000) -> None:
        self.max_history_per_task = max_history_per_task
        self._subscribers: dict[str, tuple[SubscriberCallback, set[PipelineEventType] | None]] = {}
        self._history: dict[str, list[PipelineEvent]] = defaultdict(list)
        self._stream_queues: dict[str, asyncio.Queue[PipelineEvent | None]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, event: PipelineEvent) -> None:
        """Publishes an event to matching subscribers and streaming queues."""
        async with self._lock:
            # Store in history
            hist = self._history[event.task_id]
            hist.append(event)
            if len(hist) > self.max_history_per_task:
                hist.pop(0)

            # Copy subscribers snapshot
            current_subs = list(self._subscribers.values())
            current_queues = list(self._stream_queues.values())

        # Notify active streaming queues
        for q in current_queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Pipeline streaming queue full; dropping event %s", event.event_id)

        # Dispatch to async subscriber handlers concurrently
        coros: list[Any] = []
        for handler, event_types in current_subs:
            if event_types is None or event.event_type in event_types:
                coros.append(self._safe_invoke_handler(handler, event))

        if coros:
            await asyncio.gather(*coros, return_exceptions=True)

    async def _safe_invoke_handler(
        self,
        handler: SubscriberCallback,
        event: PipelineEvent,
    ) -> None:
        """Executes a subscriber handler safely without breaking publisher."""
        try:
            await handler(event)
        except Exception as exc:
            logger.error("Error in pipeline subscriber handler: %s", exc, exc_info=True)

    def subscribe(
        self,
        handler: SubscriberCallback,
        event_types: list[PipelineEventType] | None = None,
    ) -> str:
        """Registers an async subscriber callback. Returns a subscription token."""
        sub_id = str(uuid.uuid4())
        filter_set = set(event_types) if event_types is not None else None
        self._subscribers[sub_id] = (handler, filter_set)
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Removes a subscriber by its token. Returns True if removed."""
        return self._subscribers.pop(subscription_id, None) is not None

    async def stream_events(
        self,
        task_id: str | None = None,
        timeout_seconds: float = 300.0,
    ) -> AsyncIterator[PipelineEvent]:
        """
        Asynchronously streams live pipeline events, optionally filtered by task_id.
        Terminates on timeout or terminal task events (TASK_COMPLETED, TASK_FAILED).
        """
        queue_id = str(uuid.uuid4())
        queue: asyncio.Queue[PipelineEvent | None] = asyncio.Queue(maxsize=500)

        async with self._lock:
            self._stream_queues[queue_id] = queue

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=timeout_seconds)
                except asyncio.TimeoutError:
                    break

                if event is None:
                    break

                if task_id is None or event.task_id == task_id:
                    yield event
                    if event.event_type in (
                        PipelineEventType.TASK_COMPLETED,
                        PipelineEventType.TASK_FAILED,
                    ):
                        break
        finally:
            async with self._lock:
                self._stream_queues.pop(queue_id, None)

    def get_history(self, task_id: str) -> list[PipelineEvent]:
        """Returns chronological event history for a task."""
        return list(self._history.get(task_id, []))

    def clear_history(self, task_id: str | None = None) -> None:
        """Clears stored event history."""
        if task_id is not None:
            self._history.pop(task_id, None)
        else:
            self._history.clear()


# Global Singleton Bus
_GLOBAL_EVENT_BUS: PipelineEventBus | None = None


def get_event_bus() -> PipelineEventBus:
    """Returns the shared application pipeline event bus."""
    global _GLOBAL_EVENT_BUS
    if _GLOBAL_EVENT_BUS is None:
        _GLOBAL_EVENT_BUS = PipelineEventBus()
    return _GLOBAL_EVENT_BUS
