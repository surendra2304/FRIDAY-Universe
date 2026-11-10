"""TASK-ORCH-006 (checklist C6/C14): generic fleet delegation through chat.

Live incident (2026-11-11 IST): "assign a quick task to IntelX: one-line
research note on why the sky is blue" — with no delegation tool registered,
the model invented a `<execute_agent name="IntelX" ...>` XML tag as plain
text instead of dispatching anything. These tests pin the corrected
behavior: a real fleet_dispatch tool exists, normalizes every way the owner
might name an agent, dispatches a typed TaskEnvelope, and returns the
agent's REAL result with a task-id receipt — or an honest failure.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.unit]

from friday.agent.agent import FridayAgent
from friday.core.config import Settings
from friday.tools.builtin.fleet_dispatch import (
    FLEET_AGENTS,
    FleetDispatchTool,
    normalize_agent,
)


class _FakeResult:
    def __init__(self, status: str, result: dict[str, Any] | None = None, error: str | None = None, task_id: str = "task_receipt_1"):
        self.status = status
        self.result = result or {}
        self.error = error
        self.task_id = task_id
        self.execution_time_ms = 432


class _FakeFleetClient:
    def __init__(self, result):
        self._result = result
        self.envelopes = []

    async def dispatch_task(self, envelope):
        self.envelopes.append(envelope)
        return self._result


class _BrokenFleetClient:
    async def dispatch_task(self, envelope):
        raise ConnectionError("mesh down")


class TestAgentNormalization:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("IntelX", "intelx"),
            ("intelx", "intelx"),
            ("INTELX", "intelx"),
            ("the IntelX agent", "intelx"),
            ("Intelix", "intelx"),
            ("intel x", "intelx"),
            ("Sentinel", "sentinel"),
            ("Sentinal", "sentinel"),     # common typo
            ("VyralX", "vyralx"),
            ("vyral", "vyralx"),
            ("ViralX", "vyralx"),
            ("the Memora agent", "memora"),
            ("Memoria", "memora"),
            ("Forge", "forge"),
            ("Stratex", "stratex"),
            ("Futuris", "futuris"),
            ("Cortex", "cortex"),
            ("Inference", "inference"),
        ],
    )
    def test_normalizes_owner_phrasings(self, raw: str, expected: str) -> None:
        assert normalize_agent(raw) == expected

    def test_unknown_agent_is_none(self) -> None:
        assert normalize_agent("skynet") is None
        assert normalize_agent("") is None

    def test_friday_is_not_a_dispatch_target(self) -> None:
        assert normalize_agent("friday") is None
        assert "friday" not in FLEET_AGENTS
        assert len(FLEET_AGENTS) == 9


class TestFleetDispatchToolTruth:
    def test_success_returns_real_result_and_receipt(self) -> None:
        client = _FakeFleetClient(_FakeResult("SUCCESS", {
            "response": "Rayleigh scattering: air molecules scatter short blue wavelengths.",
        }))
        result = FleetDispatchTool(fleet_client=client).execute(agent="IntelX", task="why is the sky blue")
        assert not result.is_error
        assert "Rayleigh scattering" in result.content
        assert "IntelX" in result.content
        assert "[Task receipt: task_receipt_1]" in result.content
        # the envelope went to intelx with the owner's task
        env = client.envelopes[0]
        assert env.target_agent == "intelx"
        assert env.payload["task"] == "why is the sky blue"

    def test_alias_agent_still_dispatches(self) -> None:
        client = _FakeFleetClient(_FakeResult("SUCCESS", {"response": "scan clean"}))
        FleetDispatchTool(fleet_client=client).execute(agent="Sentinal", task="run a security scan")
        assert client.envelopes[0].target_agent == "sentinel"

    def test_failed_status_is_honest_error(self) -> None:
        result = FleetDispatchTool(fleet_client=_FakeFleetClient(
            _FakeResult("FAILED", error="agent task endpoint 503")
        )).execute(agent="Sentinel", task="scan")
        assert result.is_error
        assert "could not complete" in result.content
        assert "503" in result.content
        assert "fabricated" in result.content

    def test_blocked_circuit_breaker_reported_as_is(self) -> None:
        result = FleetDispatchTool(fleet_client=_FakeFleetClient(
            _FakeResult("BLOCKED", error="Circuit breaker OPEN")
        )).execute(agent="Cortex", task="check site")
        assert result.is_error
        assert "Circuit breaker" in result.content

    def test_dispatch_crash_is_honest_error(self) -> None:
        result = FleetDispatchTool(fleet_client=_BrokenFleetClient()).execute(agent="VyralX", task="script")
        assert result.is_error
        assert "could not reach" in result.content
        assert "ConnectionError" in result.content

    def test_unknown_agent_lists_the_fleet(self) -> None:
        result = FleetDispatchTool(fleet_client=_FakeFleetClient(_FakeResult("SUCCESS"))).execute(agent="skynet", task="x")
        assert result.is_error
        assert "not one of my nine agents" in result.content
        for agent in FLEET_AGENTS:
            assert agent in result.content.lower()

    def test_empty_task_is_rejected(self) -> None:
        result = FleetDispatchTool(fleet_client=_FakeFleetClient(_FakeResult("SUCCESS"))).execute(agent="intelx", task="  ")
        assert result.is_error
        assert "need the task" in result.content

    def test_empty_agent_response_is_not_invented(self) -> None:
        result = FleetDispatchTool(fleet_client=_FakeFleetClient(_FakeResult("SUCCESS", {}))).execute(agent="intelx", task="x")
        assert not result.is_error
        assert "empty response" in result.content


class TestToolIsRegistered:
    def test_default_agent_registry_has_fleet_dispatch(self) -> None:
        agent = FridayAgent(settings=Settings(env="testing", embedding_provider="none"))
        names = {t.name for t in agent.tools.list_tools()}
        assert "fleet_dispatch" in names, "fleet_dispatch must be in the default registry"
