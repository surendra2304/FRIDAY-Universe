"""TASK-DIAG-001 (2026-11-12): the "run diagnostics" chat fast path + /api/diagnostics.

The owner asks FRIDAY to check itself ("run diagnostics", "system check") and
the answer must come from the REAL FridayDoctor probe — the same twelve
component measurements the CLI doctor reports — never from the LLM's
imagination. The API surface (/api/diagnostics) exposes the same report to the
SYSTEM tab, control-access protected.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from friday.agent.agent import FridayAgent
from friday.core.config import Settings
from friday.llm.mock_provider import MockLLMProvider
from friday.memory.in_memory import InMemoryConversationMemory


@pytest.fixture
def agent() -> FridayAgent:
    """A hermetic FridayAgent with a mock provider.

    The mock provider stands sentinel: if the diagnostics request falls
    through to the LLM, these tests fail on the sentinel reply.
    """
    settings = Settings(env="testing", llm_provider="mock", agent_name="FRIDAY", user_name="Surendra")
    return FridayAgent(
        settings=settings,
        llm_provider=MockLLMProvider(),
        memory=InMemoryConversationMemory(),
    )


# ── the chat fast path ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "phrase",
    [
        "run diagnostics",
        "friday, run diagnostics",
        "run a diagnostic",
        "do a system check",
        "run a self check",
        "check your systems",
    ],
)
def test_diagnostics_phrases_hit_the_real_doctor(agent: FridayAgent, phrase: str) -> None:
    """Every diagnostics phrasing answers from the real probe, not the LLM."""
    response = agent.process_message(phrase)
    assert response.metadata.get("diagnostics") is True
    assert response.metadata.get("fast_path") is True
    # The mock provider never ran: the reply is the doctor's report.
    assert "sentinel" not in response.content.lower()
    # The real report states the measured overall status, never a guess.
    assert "Overall:" in response.content
    assert "components are green or configured" in response.content


def test_diagnostics_names_the_real_overall_status(agent: FridayAgent) -> None:
    """The overall status echoed in chat is the doctor's measured value."""
    from friday.core.doctor import FridayDoctor

    report = FridayDoctor(settings=agent.settings).run_full_diagnostics()
    response = agent.process_message("run diagnostics")
    assert f"Overall: {report.overall_status.value}." in response.content


def test_diagnostics_reports_notable_components_with_truth(agent: FridayAgent) -> None:
    """Components that are not green/configured are named, honestly."""
    from friday.core.doctor import DiagnosticStatus, FridayDoctor

    report = FridayDoctor(settings=agent.settings).run_full_diagnostics()
    response = agent.process_message("run diagnostics")
    quiet = {DiagnosticStatus.AVAILABLE.value, DiagnosticStatus.CONFIGURED.value}
    notable = [c for c in report.components.values() if c.status.value not in quiet]
    if notable:
        for comp in notable:
            assert f"- {comp.name}: {comp.status.value}" in response.content
    # A quiet component is never listed as a problem line.
    for comp in report.components.values():
        if comp.status.value in quiet:
            assert f"- {comp.name}: {comp.status.value}" not in response.content


def test_diagnostics_doctor_failure_is_reported_honestly(agent: FridayAgent) -> None:
    """A crashing probe is an honest failure, never a fabricated green report."""
    from unittest.mock import patch

    with patch("friday.core.doctor.FridayDoctor.run_full_diagnostics", side_effect=RuntimeError("probe exploded")):
        response = agent.process_message("run diagnostics")
    assert response.metadata.get("probe_success") is False
    assert "failed" in response.content.lower()
    assert "probe exploded" not in response.content  # exception type only, no noise
    assert "RuntimeError" in response.content


# ── the fast path does not hijack other traffic ───────────────────────────


@pytest.mark.parametrize(
    "phrase",
    [
        "how are the agents",      # fleet status stays a fleet probe
        "run a research check on the market",  # research stays research
        "how are you doing",      # small talk stays conversational
        "research diagnostics trends",        # 'diagnostics' as a TOPIC, not a command
    ],
)
def test_diagnostics_path_does_not_hijack_other_intents(agent: FridayAgent, phrase: str) -> None:
    """Only explicit self-diagnostics phrasings fire the path."""
    response = agent.process_message(phrase)
    assert response.metadata.get("diagnostics") is None


def test_fleet_status_still_reaches_the_fleet_probe(agent: FridayAgent) -> None:
    """"How are the agents" must remain a fleet probe after the diagnostics gate."""
    response = agent.process_message("how are the agents")
    assert response.metadata.get("fleet_status") is True
    assert response.metadata.get("diagnostics") is None


# ── the API surface ────────────────────────────────────────────────────────


def test_api_diagnostics_returns_the_real_report(monkeypatch) -> None:
    """/api/doctor runs the real doctor and returns every component."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("FRIDAY_API_KEY", "test-control-key-for-diagnostics")
    from friday.api.server import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        "/api/doctor", headers={"X-FRIDAY-API-Key": "test-control-key-for-diagnostics"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["overall_status"] in ("AVAILABLE", "CONFIGURED", "DEGRADED", "ERROR")
    assert "components" in data
    assert "memory_database" in data["components"]
    assert "configuration" in data["components"]
    # Every component carries a measured status, not a fabricated green.
    for comp in data["components"].values():
        assert comp["status"] in ("AVAILABLE", "CONFIGURED", "DEGRADED", "UNAVAILABLE", "ERROR", "COOLDOWN")


def test_api_diagnostics_requires_control_access(monkeypatch) -> None:
    """Anonymous callers are refused - the report names configuration internals.

    The loopback bypass (127.0.0.1 without loopback hardening) is the documented
    local-dev affordance; the remote-exposure contract (RENDER set) must demand
    the key.
    """
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("FRIDAY_API_KEY", "test-control-key-for-diagnostics")
    from friday.api.server import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/doctor")
    assert response.status_code in (401, 403)
