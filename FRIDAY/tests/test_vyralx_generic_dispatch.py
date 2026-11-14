"""TASK-VYR-002 — generic chat delegation to VyralX must not be blanket-BLOCKED.

The generic delegation tool (FleetDispatchTool) builds action="execute" /
capability="vyralx.task" envelopes. FleetClient's vyralx branch used to
reject that requested type without any HTTP call, so EVERY generic VyralX
assignment returned BLOCKED while the typed vyralx_* tools worked (system
map 2026-11-14). These tests pin the fix:

- a generic free-text task is translated into the VyralX capability it
  actually asks for and really submitted;
- capabilities that cannot be honestly built from free text (publish,
  render, project, voiceover) stay BLOCKED — with the specific reason;
- the chat tool waits (bounded) for VyralX's async task and returns its
  real finished output; a task that outlasts the wait is reported as still
  in progress, never as a failure or a success.

On clean main the translation tests fail (BLOCKED, no request captured)
and the settle tests fail (the tool had no settle path: PENDING was
rendered as "could not complete that assignment: status pending").
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from friday.core.task_envelope import TaskEnvelope, TaskResult, TaskStatus
from friday.ecosystem.fleet_client import FleetClient
from friday.tools.builtin import fleet_dispatch as fleet_dispatch_module
from friday.tools.builtin.fleet_dispatch import FleetDispatchTool


_TEST_KEY = "unit" + "-test-" + "key"


def _fleet() -> FleetClient:
    return FleetClient(
        settings=SimpleNamespace(
            vyralx_url="http://vyralx:8000",
            vyralx_api_key=_TEST_KEY,
        )
    )


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_generic_execute_envelope_submits_content_generate(monkeypatch):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            202,
            json={"task_id": "gen-1", "status": "queued", "status_url": "/api/v1/tasks/gen-1"},
            request=request,
        )

    client = _mock_client(handler)
    fleet = _fleet()
    monkeypatch.setattr(fleet, "get_shared_client", lambda: client)
    envelope = TaskEnvelope(
        task_id="gen-1",
        target_agent="vyralx",
        capability="vyralx.task",
        action="execute",
        objective="generate a content pack about the history of the telegraph",
        payload={
            "task": "generate a content pack about the history of the telegraph",
            "prompt": "generate a content pack about the history of the telegraph",
        },
    )
    try:
        result = await fleet.dispatch_task(envelope)
    finally:
        await client.aclose()

    assert captured["url"] == "http://vyralx:8000/api/v1/tasks"
    assert captured["payload"]["task_type"] == "content.generate"
    assert "telegraph" in captured["payload"]["input"]["topic"]
    assert result.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_generic_publish_request_blocked_with_specific_reason(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no network request expected for a blocked dispatch")

    client = _mock_client(handler)
    fleet = _fleet()
    monkeypatch.setattr(fleet, "get_shared_client", lambda: client)
    envelope = TaskEnvelope(
        task_id="gen-2",
        target_agent="vyralx",
        capability="vyralx.task",
        action="execute",
        objective="publish the video to YouTube now",
        payload={"task": "publish the video to YouTube now", "prompt": "publish the video to YouTube now"},
    )
    try:
        result = await fleet.dispatch_task(envelope)
    finally:
        await client.aclose()

    assert result.status == TaskStatus.BLOCKED
    assert "publish.request" in (result.error or "")
    assert "explicit approval" in (result.error or "")
    assert "No task was submitted" in (result.error or "")


@pytest.mark.asyncio
async def test_generic_pexels_discovery_translates(monkeypatch):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            202,
            json={"task_id": "gen-3", "status": "queued", "status_url": "/api/v1/tasks/gen-3"},
            request=request,
        )

    client = _mock_client(handler)
    fleet = _fleet()
    monkeypatch.setattr(fleet, "get_shared_client", lambda: client)
    envelope = TaskEnvelope(
        task_id="gen-3",
        target_agent="vyralx",
        capability="vyralx.task",
        action="execute",
        objective="find stock footage of ocean waves on Pexels",
        payload={"task": "find stock footage of ocean waves on Pexels", "prompt": "find stock footage of ocean waves on Pexels"},
    )
    try:
        result = await fleet.dispatch_task(envelope)
    finally:
        await client.aclose()

    assert captured["payload"]["task_type"] == "discover.pexels"
    assert captured["payload"]["input"]["query"]
    assert result.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_prefixed_capability_normalizes_to_bare_type(monkeypatch):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            202,
            json={"task_id": "gen-4", "status": "queued", "status_url": "/api/v1/tasks/gen-4"},
            request=request,
        )

    client = _mock_client(handler)
    fleet = _fleet()
    monkeypatch.setattr(fleet, "get_shared_client", lambda: client)
    envelope = TaskEnvelope(
        task_id="gen-4",
        target_agent="vyralx",
        action="vyralx.content.generate",
        payload={"topic": "How solar panels generate electricity"},
    )
    try:
        result = await fleet.dispatch_task(envelope)
    finally:
        await client.aclose()

    assert captured["payload"]["task_type"] == "content.generate"
    assert captured["payload"]["input"]["topic"] == "How solar panels generate electricity"
    assert result.status == TaskStatus.PENDING


class _FakeVyralxClient:
    """Minimal FleetClient stand-in for tool-level settle tests."""

    def __init__(self, task_states: list[dict]):
        self._states = list(task_states)
        self.dispatched: list = []

    async def dispatch_task(self, envelope) -> TaskResult:
        self.dispatched.append(envelope)
        return TaskResult(
            task_id=envelope.task_id,
            target_agent="vyralx",
            status=TaskStatus.PENDING,
            result={"status_url": f"/api/v1/tasks/{envelope.task_id}"},
            summary="vyralx accepted the request; completion is pending verification.",
        )

    async def fetch_vyralx_task(self, task_id: str):
        if self._states:
            return self._states.pop(0)
        return {"task_id": task_id, "status": "queued", "result": {}}


def _fast_settle(monkeypatch):
    monkeypatch.setattr(fleet_dispatch_module, "_VYRALX_SETTLE_POLL_SECONDS", 0.01)
    monkeypatch.setattr(fleet_dispatch_module, "_VYRALX_SETTLE_BUDGET_SECONDS", 5.0)


def test_tool_settles_vyralx_task_and_renders_real_pack(monkeypatch):
    _fast_settle(monkeypatch)
    pack = {
        "content_pack_id": 7,
        "status": "generated",
        "content_pack": {
            "title_options": ["The Telegraph Changed Everything"],
            "hook": "Before phones, there was the wire.",
            "script": "In 1844 a single line carried a message faster than any horse.",
            "scene_plan": [{"timecode": "00:00-00:05"}, {"timecode": "00:05-00:10"}],
        },
    }
    client = _FakeVyralxClient([
        {"task_id": "x", "status": "queued", "result": {}},
        {"task_id": "x", "status": "completed", "result": pack},
    ])
    tool = FleetDispatchTool(fleet_client=client)
    result = tool.execute(agent="VyralX", task="generate a content pack about the history of the telegraph")
    assert result.is_error is False
    assert "The Telegraph Changed Everything" in result.content
    assert "Before phones, there was the wire." in result.content
    assert "Content pack #7" in result.content
    assert "Task receipt:" in result.content


def test_tool_reports_vyralx_failure_honestly(monkeypatch):
    _fast_settle(monkeypatch)
    client = _FakeVyralxClient([
        {"task_id": "x", "status": "failed", "error": "RuntimeError: INFERENCE_URL must be configured", "result": {}},
    ])
    tool = FleetDispatchTool(fleet_client=client)
    result = tool.execute(agent="VyralX", task="generate a content pack about anything")
    assert result.is_error is True
    assert "INFERENCE_URL" in result.content


def test_tool_pending_is_in_progress_not_failure(monkeypatch):
    monkeypatch.setattr(fleet_dispatch_module, "_VYRALX_SETTLE_POLL_SECONDS", 0.01)
    monkeypatch.setattr(fleet_dispatch_module, "_VYRALX_SETTLE_BUDGET_SECONDS", 0.05)
    client = _FakeVyralxClient([])
    tool = FleetDispatchTool(fleet_client=client)
    result = tool.execute(agent="VyralX", task="generate a content pack about slow topics")
    assert "still working on it" in result.content
    assert "could not complete" not in result.content
