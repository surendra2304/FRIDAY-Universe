"""TASK-COR-014: unconfigured probes are a configuration notice, not a failure.

Root cause of the 2026-11-17→19 Telegram spam (247 sends): ``probe_ai_universe``
returned ``False`` whenever ``INFERENCE_BASE_URL`` / ``AI_UNIVERSE_BASE_URL``
were unset (both unset in production), so the supervisor treated "never
configured" as "down", burned its repair budget and escalated every cycle.

These tests pin the tri-state contract at three levels:

* probe — unset env / unparseable URL → ``ProbeResult.UNCONFIGURED``;
  set-but-unresolvable → ``UNHEALTHY``; set-and-resolving → ``HEALTHY``.
* registry — UNCONFIGURED records no circuit success/failure outcome.
* supervisor — UNCONFIGURED is listed as ``unconfigured`` (never
  ``unhealthy``), logged once per streak, and never repaired, counted as a
  repair failure or escalated; the configured paths are unchanged.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cortex_core.resilience import (
    CircuitState,
    EscalationNotifier,
    HealthRegistry,
    ProbeResult,
    SelfHealingSupervisor,
)


def _run(coro):
    return asyncio.run(coro)


# ── probe level: cortex_api.self_healing.probe_ai_universe ──────────────────


def _clear_url_env(monkeypatch):
    monkeypatch.delenv("INFERENCE_BASE_URL", raising=False)
    monkeypatch.delenv("AI_UNIVERSE_BASE_URL", raising=False)


def test_probe_unconfigured_when_both_urls_unset(monkeypatch):
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    assert _run(probe_ai_universe()) is ProbeResult.UNCONFIGURED


def test_probe_unconfigured_when_url_has_no_host(monkeypatch):
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    monkeypatch.setenv("INFERENCE_BASE_URL", "not-a-url")
    assert _run(probe_ai_universe()) is ProbeResult.UNCONFIGURED


def test_probe_unhealthy_when_configured_host_does_not_resolve(monkeypatch):
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    monkeypatch.setenv("INFERENCE_BASE_URL", "http://inference.invalid:8001")

    mock_loop = MagicMock()
    mock_loop.getaddrinfo = AsyncMock(side_effect=OSError("name resolution failed"))
    with patch("asyncio.get_running_loop", return_value=mock_loop):
        assert _run(probe_ai_universe()) is ProbeResult.UNHEALTHY
    mock_loop.getaddrinfo.assert_awaited_once()


def test_probe_healthy_when_configured_host_resolves(monkeypatch):
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    monkeypatch.setenv("AI_UNIVERSE_BASE_URL", "http://ai-universe.local:8000")

    mock_loop = MagicMock()
    mock_loop.getaddrinfo = AsyncMock(
        return_value=[(None, None, None, None, ("127.0.0.1", 8000))]
    )
    with patch("asyncio.get_running_loop", return_value=mock_loop):
        assert _run(probe_ai_universe()) is ProbeResult.HEALTHY
    mock_loop.getaddrinfo.assert_awaited_once()


def test_probe_result_coerce_keeps_bool_probes_working():
    assert ProbeResult.coerce(True) is ProbeResult.HEALTHY
    assert ProbeResult.coerce(False) is ProbeResult.UNHEALTHY
    assert ProbeResult.coerce(ProbeResult.UNCONFIGURED) is ProbeResult.UNCONFIGURED


# ── registry level: UNCONFIGURED records no circuit outcome ─────────────────


def test_registry_records_no_failure_for_unconfigured():
    registry = HealthRegistry()

    async def unconfigured() -> ProbeResult:
        return ProbeResult.UNCONFIGURED

    registry.register_probe("ai_universe", unconfigured)

    async def scenario():
        for _ in range(5):
            result = await registry.run_probe_result("ai_universe")
            assert result is ProbeResult.UNCONFIGURED
        # The bool view still reads "not healthy" for legacy callers…
        assert await registry.run_probe("ai_universe") is False

    _run(scenario())
    circuit = registry.circuit("ai_universe")
    snapshot = circuit.snapshot()
    assert snapshot["samples"] == 0
    assert snapshot["total_failures"] == 0
    assert snapshot["total_successes"] == 0
    assert snapshot["consecutive_failures"] == 0
    assert circuit.state is CircuitState.CLOSED
    last = registry.snapshot()["last_probes"]["ai_universe"]
    assert last["result"] == "UNCONFIGURED"
    assert last["healthy"] is None


def test_registry_bool_probe_still_records_outcomes():
    registry = HealthRegistry()

    async def down() -> bool:
        return False

    registry.register_probe("redis", down)
    _run(registry.run_probe_result("redis"))
    snapshot = registry.circuit("redis").snapshot()
    assert snapshot["samples"] == 1
    assert snapshot["total_failures"] == 1


# ── supervisor level ────────────────────────────────────────────────────────


def _supervisor_with_probe(probe, *, max_repairs=2):
    registry = HealthRegistry()
    registry.register_probe("ai_universe", probe)
    supervisor = SelfHealingSupervisor(
        registry,
        repair_cooldown_seconds=0.0,
        max_repairs_per_subsystem=max_repairs,
        notifier=EscalationNotifier(webhook_url=""),
    )
    repairs = {"attempts": 0}

    async def repair() -> bool:
        repairs["attempts"] += 1
        return False

    supervisor.register_repair("ai_universe", repair)
    return registry, supervisor, repairs


def test_unconfigured_never_escalates_repairs_or_counts_failures(caplog):
    async def unconfigured() -> ProbeResult:
        return ProbeResult.UNCONFIGURED

    registry, supervisor, repairs = _supervisor_with_probe(unconfigured)

    with caplog.at_level(logging.INFO, logger="cortex-core.resilience"):
        runs = [_run(supervisor.run_cycle()) for _ in range(6)]

    for run in runs:
        assert run.checked == ["ai_universe"]
        assert run.unconfigured == ["ai_universe"]
        assert run.unhealthy == []
        assert run.repairs == []
        assert run.escalated == []
        assert run.escalations_delivered == []
        assert run.as_dict()["unconfigured"] == ["ai_universe"]
    assert repairs["attempts"] == 0, "unconfigured must not consume repair attempts"
    assert supervisor.escalations == []
    assert supervisor._attempts.get("ai_universe", 0) == 0
    circuit = registry.circuit("ai_universe")
    assert circuit.state is CircuitState.CLOSED
    assert circuit.snapshot()["total_failures"] == 0

    notices = [r for r in caplog.records if "not configured" in r.getMessage()]
    assert len(notices) == 1, f"notice must log once per streak, got {len(notices)}"


def test_unconfigured_notice_repeats_only_after_a_new_streak(caplog):
    state = {"result": ProbeResult.UNCONFIGURED}

    async def probe() -> ProbeResult:
        return state["result"]

    _registry, supervisor, _repairs = _supervisor_with_probe(probe)

    with caplog.at_level(logging.INFO, logger="cortex-core.resilience"):
        _run(supervisor.run_cycle())  # streak 1: notice
        _run(supervisor.run_cycle())  # streak 1: silent
        state["result"] = ProbeResult.HEALTHY
        _run(supervisor.run_cycle())  # configured again: streak ends
        state["result"] = ProbeResult.UNCONFIGURED
        _run(supervisor.run_cycle())  # streak 2: notice again

    notices = [r for r in caplog.records if "not configured" in r.getMessage()]
    assert len(notices) == 2


def test_configured_but_down_keeps_the_existing_failure_path():
    async def down() -> ProbeResult:
        return ProbeResult.UNHEALTHY

    registry, supervisor, repairs = _supervisor_with_probe(down)

    _run(supervisor.run_cycle())  # repair attempt 1
    _run(supervisor.run_cycle())  # repair attempt 2
    third = _run(supervisor.run_cycle())  # budget exhausted -> escalate

    assert repairs["attempts"] == 2
    assert third.unconfigured == []
    assert third.unhealthy == ["ai_universe"]
    assert third.escalated == ["ai_universe"]
    assert registry.circuit("ai_universe").state is CircuitState.OPEN


def test_configured_and_healthy_is_a_plain_pass():
    async def up() -> ProbeResult:
        return ProbeResult.HEALTHY

    registry, supervisor, repairs = _supervisor_with_probe(up)
    run = _run(supervisor.run_cycle())

    assert run.unconfigured == []
    assert run.unhealthy == []
    assert run.repairs == []
    assert repairs["attempts"] == 0
    assert registry.circuit("ai_universe").snapshot()["samples"] == 1


def test_unconfigured_recovers_to_healthy_without_a_repair():
    state = {"result": ProbeResult.UNCONFIGURED}

    async def probe() -> ProbeResult:
        return state["result"]

    registry, supervisor, repairs = _supervisor_with_probe(probe)
    _run(supervisor.run_cycle())
    state["result"] = ProbeResult.HEALTHY
    run = _run(supervisor.run_cycle())

    assert run.unconfigured == []
    assert run.unhealthy == []
    assert repairs["attempts"] == 0
    assert registry.circuit("ai_universe").snapshot()["total_successes"] == 1


@pytest.mark.parametrize("env", [{}, {"INFERENCE_BASE_URL": "http://inference.invalid:8001"}])
def test_end_to_end_probe_through_supervisor(monkeypatch, env):
    """The real probe + registry + supervisor, driven only by the env."""
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    if env:
        mock_loop = MagicMock()
        mock_loop.getaddrinfo = AsyncMock(side_effect=OSError("down"))
        patcher = patch("asyncio.get_running_loop", return_value=mock_loop)
        patcher.start()
    else:
        patcher = None
    try:
        registry, supervisor, repairs = _supervisor_with_probe(probe_ai_universe)
        runs = [_run(supervisor.run_cycle()) for _ in range(4)]
    finally:
        if patcher is not None:
            patcher.stop()

    if not env:
        assert all(run.unconfigured == ["ai_universe"] for run in runs)
        assert all(run.unhealthy == [] for run in runs)
        assert repairs["attempts"] == 0
        assert supervisor.escalations == []
    else:
        assert all(run.unconfigured == [] for run in runs)
        assert runs[-1].escalated == ["ai_universe"]
