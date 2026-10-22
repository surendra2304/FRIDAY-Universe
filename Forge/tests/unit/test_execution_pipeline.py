"""
Unit tests for the Event-Driven Execution Pipeline subsystem.
"""

from __future__ import annotations

import asyncio

import pytest

from app.pipeline.bus import PipelineEventBus, get_event_bus
from app.pipeline.events import PipelineEvent, PipelineEventType


def test_pipeline_event_serialization() -> None:
    event = PipelineEvent(
        task_id="task_123",
        event_type=PipelineEventType.SYNTHESIS_STAGE_STARTED,
        payload={"stage": "ast_generation", "files_count": 5},
    )
    d = event.to_dict()
    assert d["task_id"] == "task_123"
    assert d["event_type"] == "synthesis.stage.started"
    assert d["payload"]["stage"] == "ast_generation"

    json_str = event.to_json()
    assert '"task_id": "task_123"' in json_str

    deserialized = PipelineEvent.from_dict(d)
    assert deserialized.task_id == event.task_id
    assert deserialized.event_type == event.event_type
    assert deserialized.payload == event.payload


@pytest.mark.asyncio
async def test_pipeline_bus_publish_subscribe() -> None:
    bus = PipelineEventBus()
    received_events: list[PipelineEvent] = []

    async def on_event(ev: PipelineEvent) -> None:
        received_events.append(ev)

    token = bus.subscribe(on_event, event_types=[PipelineEventType.FILE_WRITTEN])

    ev1 = PipelineEvent(
        task_id="task_abc",
        event_type=PipelineEventType.FILE_WRITTEN,
        payload={"path": "main.py"},
    )
    ev2 = PipelineEvent(
        task_id="task_abc",
        event_type=PipelineEventType.TASK_STARTED,
    )

    await bus.publish(ev1)
    await bus.publish(ev2)

    # Only ev1 should match the subscription filter
    assert len(received_events) == 1
    assert received_events[0].event_type == PipelineEventType.FILE_WRITTEN

    # History should contain both
    history = bus.get_history("task_abc")
    assert len(history) == 2

    # Unsubscribe
    assert bus.unsubscribe(token) is True
    await bus.publish(ev1)
    assert len(received_events) == 1


@pytest.mark.asyncio
async def test_pipeline_bus_streaming() -> None:
    bus = PipelineEventBus()
    streamed: list[PipelineEvent] = []

    async def producer() -> None:
        await asyncio.sleep(0.01)
        await bus.publish(
            PipelineEvent(
                task_id="stream_task",
                event_type=PipelineEventType.TASK_STARTED,
            )
        )
        await asyncio.sleep(0.01)
        await bus.publish(
            PipelineEvent(
                task_id="stream_task",
                event_type=PipelineEventType.COMPILATION_COMPLETED,
            )
        )
        await asyncio.sleep(0.01)
        await bus.publish(
            PipelineEvent(
                task_id="stream_task",
                event_type=PipelineEventType.TASK_COMPLETED,
            )
        )

    async def consumer() -> None:
        async for event in bus.stream_events(task_id="stream_task", timeout_seconds=2.0):
            streamed.append(event)

    await asyncio.gather(producer(), consumer())

    assert len(streamed) == 3
    assert streamed[0].event_type == PipelineEventType.TASK_STARTED
    assert streamed[-1].event_type == PipelineEventType.TASK_COMPLETED


def test_global_event_bus_singleton() -> None:
    bus1 = get_event_bus()
    bus2 = get_event_bus()
    assert bus1 is bus2
