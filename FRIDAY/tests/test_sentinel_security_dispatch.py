"""Checklist F19/C8 (MASTER_COMPLETION_CHECKLIST): Sentinel security via chat.

The owner asks for the fleet's security posture or the open security findings
in plain words and gets Sentinel's REAL data — the same engines behind
Sentinel's /api/v1/friday/posture and /api/v1/findings endpoints. Read-only
by construction: an actual security assessment is NOT performed (Sentinel's
delegation ingress stays fail-closed behind a complete owner-authorized
scope) and every answer states that.

Contracts locked here:
- the routing table sends security questions to TOOL_EXECUTION
  (sentinel_security), never VISION_MODEL, never DIRECT_REASONING guessing;
- the security fast-path answers posture and findings asks with the tool's
  real output, and runs BEFORE the fleet-status probe so "check the fleet's
  security posture" is a security lookup, not a fleet-health ping;
- delegation-shaped asks ("tell Sentinel to run a security scan") stay with
  the delegation fast-path — the two paths cannot fight over a message;
- FleetClient.ask_sentinel_findings reports findings, honest empties and
  honest failures (HTTP errors, connection errors) — never a fabricated list.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.agent.agent import FridayAgent  # noqa: E402
from friday.core.config import Settings  # noqa: E402
from friday.llm.mock_provider import MockLLMProvider  # noqa: E402
from friday.routing.capability_router import CapabilityRouter  # noqa: E402
from friday.tools.builtin.sentinel_security import SentinelSecurityTool  # noqa: E402


# ---------------------------------------------------------------------------
# routing table
# ---------------------------------------------------------------------------

class TestRouting:
    @pytest.mark.parametrize(
        "phrase",
        [
            "what is the security posture",
            "run a security check",
            "any vulnerabilities right now",
            "any security findings",
            "how secure is the fleet",
            "check the fleet security posture",
            "what's our cybersecurity status",
        ],
    )
    def test_security_questions_route_to_tool_execution(self, phrase: str) -> None:
        decision = CapabilityRouter().route_request(phrase)
        assert decision.selected_capability.value == "TOOL_EXECUTION"
        assert "sentinel_security" in (
            decision.candidate_evaluations[0].required_tools or []
            if decision.candidate_evaluations
            else []
        ) or any(
            "sentinel_security" in (c.required_tools or [])
            for c in decision.candidate_evaluations
        )

    @pytest.mark.parametrize(
        "phrase",
        [
            "what is the security posture",
            "run a security scan",
            "any vulnerabilities",
            "is sentinel online",
        ],
    )
    def test_security_questions_never_conversational(self, phrase: str) -> None:
        decision = CapabilityRouter().route_request(phrase)
        assert decision.selected_capability.value != "DIRECT_REASONING"

    def test_plain_fleet_status_is_not_a_security_question(self) -> None:
        decision = CapabilityRouter().route_request("how's the fleet")
        assert decision.selected_capability.value == "TOOL_EXECUTION"  # fleet status tool
        assert not any(
            "sentinel_security" in (c.required_tools or [])
            for c in decision.candidate_evaluations
        )


# ---------------------------------------------------------------------------
# tool contract (fake client — the real client's HTTP behavior is below)
# ---------------------------------------------------------------------------

class _FakeSentinelClient:
    def __init__(self, posture: dict[str, Any] | None = None, findings: dict[str, Any] | None = None, error: Exception | None = None):
        self._posture = posture if posture is not None else {
            "reply": "🛡️ Posture 92.5 | trend stable | audit chain valid",
            "metadata": {"agent_id": "sentinel", "posture_score": 92.5},
        }
        self._findings = findings if findings is not None else {
            "reply": "🛡️ [SENTINEL FINDINGS] 1 open finding(s):\n• [HIGH] Exposed admin route",
            "metadata": {"agent_id": "sentinel", "finding_count": 1},
            "success": True,
        }
        self._error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def ask_sentinel(self, query: str) -> dict[str, Any]:
        self.calls.append(("posture", {"query": query}))
        if self._error:
            raise self._error
        return self._posture

    async def ask_sentinel_findings(self, severity: str = "", limit: int = 10) -> dict[str, Any]:
        self.calls.append(("findings", {"severity": severity, "limit": limit}))
        if self._error:
            raise self._error
        return self._findings


class TestToolContract:
    def test_posture_action_uses_ask_sentinel(self) -> None:
        client = _FakeSentinelClient()
        result = SentinelSecurityTool(fleet_client=client).execute(question="security posture", action="posture")
        assert result.is_error is False
        assert "92.5" in result.content
        assert client.calls[0][0] == "posture"
        meta = result.metadata["sentinel"]
        assert meta["read_only"] is True
        assert meta["assessment_completed"] is False
        assert meta["action"] == "posture"

    def test_findings_action_with_severity_filter(self) -> None:
        client = _FakeSentinelClient()
        result = SentinelSecurityTool(fleet_client=client).execute(
            question="any critical findings", action="findings", severity="critical"
        )
        assert result.is_error is False
        assert client.calls[0][0] == "findings"
        assert client.calls[0][1]["severity"] == "critical"
        assert "Exposed admin route" in result.content

    def test_invalid_action_falls_back_to_posture(self) -> None:
        client = _FakeSentinelClient()
        SentinelSecurityTool(fleet_client=client).execute(question="posture", action="nuke-everything")
        assert client.calls[0][0] == "posture"

    def test_connection_failure_is_honest(self) -> None:
        client = _FakeSentinelClient(error=RuntimeError("no route to host"))
        result = SentinelSecurityTool(fleet_client=client).execute(question="posture")
        assert result.is_error is True
        assert "no route to host" in result.content
        assert "won't guess" in result.content

    def test_empty_reply_is_honest(self) -> None:
        client = _FakeSentinelClient(posture={"reply": "", "metadata": {}})
        result = SentinelSecurityTool(fleet_client=client).execute(question="posture")
        assert result.is_error is True
        assert "nothing was invented" in result.content


# ---------------------------------------------------------------------------
# FleetClient.ask_sentinel_findings (HTTP-level contract against a fake transport)
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class _FakeHTTPClient:
    def __init__(self, response: _FakeResponse | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.gets: list[str] = []

    async def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.gets.append(url)
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


class _FakeBreaker:
    async def can_execute(self) -> bool:
        return True

    async def record_success(self, *_a: Any, **_k: Any) -> None:
        pass

    async def record_failure(self, *_a: Any, **_k: Any) -> None:
        pass


class _FleetClientForFindings:
    """Just enough FleetClient surface for ask_sentinel_findings."""

    sentinel_url = "http://sentinel.internal:8000"
    sentinel_key = "test-sentinel-key"

    def __init__(self, response: _FakeResponse | None = None, error: Exception | None = None):
        self._http = _FakeHTTPClient(response=response, error=error)
        self._breaker = _FakeBreaker()

    def get_circuit_breaker(self, target: str):
        return self._breaker

    def get_shared_client(self):
        return self._http


class TestAskSentinelFindings:
    def test_real_findings_formatted(self) -> None:
        import asyncio

        from friday.ecosystem.fleet_client import FleetClient

        payload = [
            {
                "severity": "HIGH",
                "title": "Exposed admin route",
                "description": "/api/admin has no auth",
                "confidence": 0.9,
            }
        ]
        client = _FleetClientForFindings(response=_FakeResponse(200, payload))
        result = asyncio.run(FleetClient.ask_sentinel_findings(client))
        assert result["success"] is True
        assert "1 open finding" in result["reply"]
        assert "Exposed admin route" in result["reply"]
        assert "no security assessment was performed" in result["reply"]
        assert result["metadata"]["finding_count"] == 1

    def test_empty_findings_honest(self) -> None:
        import asyncio

        from friday.ecosystem.fleet_client import FleetClient

        client = _FleetClientForFindings(response=_FakeResponse(200, []))
        result = asyncio.run(FleetClient.ask_sentinel_findings(client))
        assert result["success"] is True
        assert "No open security findings" in result["reply"]

    def test_http_error_honest(self) -> None:
        import asyncio

        from friday.ecosystem.fleet_client import FleetClient

        client = _FleetClientForFindings(response=_FakeResponse(403, {"detail": "forbidden"}))
        result = asyncio.run(FleetClient.ask_sentinel_findings(client))
        assert result["success"] is False
        assert "403" in result["reply"]

    def test_connection_error_honest(self) -> None:
        import asyncio

        from friday.ecosystem.fleet_client import FleetClient

        client = _FleetClientForFindings(error=RuntimeError("connection refused"))
        result = asyncio.run(FleetClient.ask_sentinel_findings(client))
        assert result["success"] is False
        assert "connection refused" in result["reply"]


# ---------------------------------------------------------------------------
# fast-path behavior (real agent, patched tool client)
# ---------------------------------------------------------------------------

def _agent() -> FridayAgent:
    return FridayAgent(
        settings=Settings(env="testing", embedding_provider="none"),
        llm_provider=MockLLMProvider(),
        authorizer=__import__("friday.core.auth", fromlist=["AutoApproveAuthorizer"]).AutoApproveAuthorizer.create_for_testing(),
    )


class TestSecurityFastPath:
    @pytest.mark.parametrize(
        "phrase,action",
        [
            ("what is the security posture", "posture"),
            ("run a security check", "posture"),
            ("check the fleet security posture", "posture"),
            ("any vulnerabilities right now", "findings"),
            ("show me any security findings", "findings"),
        ],
    )
    def test_security_phrasings_fire(self, phrase: str, action: str) -> None:
        agent = _agent()
        client = _FakeSentinelClient()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(SentinelSecurityTool, "_client", lambda self: client)
            response = agent.process_message(phrase)
        assert response is not None
        assert response.metadata.get("security_lookup") is True
        assert response.metadata.get("action") == action
        assert client.calls, "the security tool must have run"

    def test_security_beats_fleet_status(self) -> None:
        """'check the fleet security posture' is a security lookup, not a fleet ping."""
        agent = _agent()
        client = _FakeSentinelClient()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(SentinelSecurityTool, "_client", lambda self: client)
            response = agent.process_message("check the fleet security posture")
        assert response.metadata.get("security_lookup") is True
        assert client.calls and client.calls[0][0] == "posture"

    @pytest.mark.parametrize(
        "phrase",
        [
            "tell Sentinel to run a security scan",  # delegation owns this
            "assign a quick task to Sentinel: security posture check",  # delegation
            "how's the fleet",  # plain fleet status
            "hello friday",  # greeting
            "what time is it",  # local calc
        ],
    )
    def test_non_security_phrasings_untouched(self, phrase: str) -> None:
        agent = _agent()
        client = _FakeSentinelClient()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(SentinelSecurityTool, "_client", lambda self: client)
            response = agent.process_message(phrase)
        if response is not None and response.metadata.get("fast_path"):
            assert response.metadata.get("security_lookup") is None

    def test_tool_registered_in_default_registry(self) -> None:
        agent = _agent()
        registered = getattr(agent.tools, "_tools", {}) or {}
        assert any(
            getattr(t, "name", "") == "sentinel_security" for t in registered.values()
        ), "sentinel_security must be registered in the default tool registry"
