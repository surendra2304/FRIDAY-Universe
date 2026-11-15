"""TASK-FRD-003 (2026-11-15): FRIDAY chat latency — stage instrumentation
and the parallel Memora context legs.

Profiling (live probes + production journal, 2026-11-15) showed cognitive
turns costing 5.4-46.5s end to end. Code inspection found one purely
serial waste on every cognitive turn: ``execute_complex_task`` ran two
independent Memora reads — ``build_context_block`` (recall, 15s timeout)
and ``build_self_upgrade_context`` (experience, 3.5s timeout) — one after
the other before the first LLM call. They now run concurrently with
identical content and prompt ordering, and the per-stage timings ride
out in response metadata so the saving stays measurable in production:

- agent.execute_complex_task metadata["latency"]:
  memora_context_wall_seconds / memora_context_leg_seconds /
  memora_self_upgrade_leg_seconds
- cognitive.process_message metadata: intent_classify_seconds,
  local_recall_seconds, latency (forwarded)
- server.execute_command metadata["latency_ms"]:
  persist_begin_ms / dispatch_ms / persist_finalize_ms / total_ms
"""
from __future__ import annotations

import asyncio
import time

import pytest

pytestmark = [pytest.mark.unit]

LEG_SECONDS = 0.4


class _SlowMemora:
    """Both context legs sleep like a loaded Memora round trip."""

    def __init__(self, fail_context: bool = False):
        self.fail_context = fail_context

    def recall_memories(self, agent, query, limit=10):
        return []

    def build_context_block(self, agent, goal):
        time.sleep(LEG_SECONDS)
        if self.fail_context:
            raise RuntimeError("memora context leg down")
        return "CTXBLOCK-MARKER"

    def build_self_upgrade_context(self, agent, goal, domain=None):
        time.sleep(LEG_SECONDS)
        return "UPGBLOCK-MARKER"


class _RecordingStub:
    def __init__(self, content="stub answer"):
        self._content = content
        self.calls = 0
        self.seen_messages = []

    def generate(self, messages, tools=None):
        from friday.core.types import Message, Role

        self.calls += 1
        self.seen_messages = list(messages)
        return Message(role=Role.ASSISTANT, content=self._content)


def _agent_with_stub(monkeypatch, stub, memora):
    import friday.memory.memora_client as memora_module
    from friday.agent.agent import FridayAgent
    from friday.core.config import Settings
    from friday.llm.base import BaseLLMProvider

    monkeypatch.setattr(memora_module, "memora_client", memora)

    class _Provider(BaseLLMProvider):
        def __init__(self):
            super().__init__(model="stub", temperature=0.0, max_tokens=16)

        @property
        def provider_name(self):
            return "stub"

        def generate(self, messages, tools=None):
            return stub.generate(messages, tools)

    return FridayAgent(settings=Settings(env="testing"), llm_provider=_Provider())


def test_memora_context_legs_run_in_parallel(monkeypatch):
    stub = _RecordingStub()
    agent = _agent_with_stub(monkeypatch, stub, _SlowMemora())

    t0 = time.perf_counter()
    response = agent.execute_complex_task("Write a haiku about autumn rain")
    elapsed = time.perf_counter() - t0

    # Serial composition would cost >= 2 * LEG_SECONDS in the Memora legs
    # alone; the parallel wall must come in clearly under that.
    assert elapsed < LEG_SECONDS * 1.75, f"legs still serial? elapsed={elapsed:.2f}s"
    latency = response.metadata.get("latency") or {}
    assert latency.get("memora_context_wall_seconds", 99) < LEG_SECONDS * 1.75
    assert latency.get("memora_context_leg_seconds", 0) >= LEG_SECONDS * 0.9
    assert latency.get("memora_self_upgrade_leg_seconds", 0) >= LEG_SECONDS * 0.9

    # Content and prompt ordering unchanged: context block before
    # self-upgrade block inside the quarantined memory message.
    joined = "\n".join(str(getattr(m, "content", "")) for m in stub.seen_messages)
    assert "CTXBLOCK-MARKER" in joined
    assert "UPGBLOCK-MARKER" in joined
    assert joined.index("CTXBLOCK-MARKER") < joined.index("UPGBLOCK-MARKER")


def test_memora_leg_failure_stays_fail_open(monkeypatch):
    stub = _RecordingStub()
    agent = _agent_with_stub(monkeypatch, stub, _SlowMemora(fail_context=True))

    response = agent.execute_complex_task("Write a haiku about autumn rain")

    assert stub.calls >= 1, "one failed Memora leg must not kill the turn"
    joined = "\n".join(str(getattr(m, "content", "")) for m in stub.seen_messages)
    assert "UPGBLOCK-MARKER" in joined
    assert response.metadata.get("latency")


def test_execute_command_attaches_latency_breakdown(monkeypatch):
    import friday.api.server as server

    async def _fake_dispatch(command, *, boss_verified=False):
        return {"reply": "ok", "metadata": {"success": True}}

    monkeypatch.setattr(server, "_dispatch_command", _fake_dispatch)

    result = asyncio.run(
        server.execute_command(server.CommandRequest(command="latency probe"))
    )

    latency = result["metadata"]["latency_ms"]
    for key in ("persist_begin_ms", "dispatch_ms", "persist_finalize_ms", "total_ms"):
        assert isinstance(latency[key], (int, float)) and latency[key] >= 0
    assert latency["total_ms"] >= latency["dispatch_ms"]
