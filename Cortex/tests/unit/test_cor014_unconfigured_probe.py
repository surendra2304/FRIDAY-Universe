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

TASK-CTX-002: the probe is a real HTTP check now, not DNS-only — it does
``GET {base}/health`` (5s timeout, no proxy env) and reports HEALTHY only
on HTTP 200 from a gateway that says it is healthy. With both env URLs
unset it probes the fleet-default Inference gateway
(``http://10.0.0.121:8001``) instead of reporting UNCONFIGURED: in
production the probe observes the real dependency instead of nothing.
The tri-state contract above is unchanged for the unparseable-URL case.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import MagicMock

import httpx
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


class _FakeHealthResponse:
    """Minimal stand-in for the httpx response of ``GET {base}/health``."""

    def __init__(
        self, status_code: int = 200, json_body=None, json_raises: bool = False
    ):
        self.status_code = status_code
        self._json_body = json_body
        self._json_raises = json_raises

    def json(self):
        if self._json_raises:
            raise ValueError("not JSON")
        return self._json_body


class _FakeAsyncClient:
    """Fake ``httpx.AsyncClient`` recording the URLs it is asked to GET."""

    def __init__(
        self, response: _FakeHealthResponse | None = None, exc: Exception | None = None
    ):
        self._response = response
        self._exc = exc
        self.get_calls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url: str):
        self.get_calls.append(url)
        if self._exc is not None:
            raise self._exc
        assert self._response is not None
        return self._response


def _patch_http(
    monkeypatch,
    *,
    status: int = 200,
    json_body=None,
    json_raises: bool = False,
    exc: Exception | None = None,
):
    """Point the probe's ``httpx.AsyncClient`` at a fake; return (client, ctor_kwargs).

    ``ctor_kwargs`` captures the keyword arguments the probe passed to the
    client constructor (timeout, trust_env) so tests can pin them.
    """
    client = _FakeAsyncClient(
        response=_FakeHealthResponse(status, json_body, json_raises), exc=exc
    )
    ctor_kwargs: dict = {}

    def _factory(*args, **kwargs):
        ctor_kwargs.update(kwargs)
        return client

    monkeypatch.setattr("httpx.AsyncClient", _factory)
    return client, ctor_kwargs


def _clear_url_env(monkeypatch):
    monkeypatch.delenv("INFERENCE_BASE_URL", raising=False)
    monkeypatch.delenv("AI_UNIVERSE_BASE_URL", raising=False)


def test_probe_uses_fleet_default_when_both_urls_unset(monkeypatch):
    """TASK-CTX-002: unset env no longer means "nothing to probe".

    The probe checks the fleet-default Inference gateway (Server 1:8001)
    and reports what it finds there — in production this is the live
    dependency, not a standing unconfigured notice.
    """
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    client, _ctor = _patch_http(
        monkeypatch, status=200, json_body={"status": "healthy"}
    )

    assert _run(probe_ai_universe()) is ProbeResult.HEALTHY
    assert client.get_calls == ["http://10.0.0.121:8001/health"]


def test_probe_unhealthy_when_fleet_default_is_down(monkeypatch):
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    client, _ctor = _patch_http(
        monkeypatch, exc=httpx.ConnectError("refused", request=MagicMock())
    )

    assert _run(probe_ai_universe()) is ProbeResult.UNHEALTHY
    assert client.get_calls == ["http://10.0.0.121:8001/health"]


def test_probe_unconfigured_when_url_has_no_host(monkeypatch):
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    monkeypatch.setenv("INFERENCE_BASE_URL", "not-a-url")
    assert _run(probe_ai_universe()) is ProbeResult.UNCONFIGURED


def test_probe_prefers_inference_url_over_legacy(monkeypatch):
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    monkeypatch.setenv("INFERENCE_BASE_URL", "http://inference:8001")
    monkeypatch.setenv("AI_UNIVERSE_BASE_URL", "http://legacy:8000")
    client, _ctor = _patch_http(
        monkeypatch, status=200, json_body={"status": "healthy"}
    )

    assert _run(probe_ai_universe()) is ProbeResult.HEALTHY
    assert client.get_calls == ["http://inference:8001/health"]


def test_probe_uses_legacy_url_when_inference_unset(monkeypatch):
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    monkeypatch.setenv("AI_UNIVERSE_BASE_URL", "http://ai-universe.local:8000")
    client, _ctor = _patch_http(
        monkeypatch, status=200, json_body={"status": "healthy"}
    )

    assert _run(probe_ai_universe()) is ProbeResult.HEALTHY
    assert client.get_calls == ["http://ai-universe.local:8000/health"]


def test_probe_unhealthy_when_health_endpoint_unreachable(monkeypatch):
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    monkeypatch.setenv("INFERENCE_BASE_URL", "http://inference.invalid:8001")
    client, _ctor = _patch_http(
        monkeypatch,
        exc=httpx.ConnectError("name resolution failed", request=MagicMock()),
    )

    assert _run(probe_ai_universe()) is ProbeResult.UNHEALTHY
    assert client.get_calls == ["http://inference.invalid:8001/health"]


def test_probe_unhealthy_on_timeout(monkeypatch):
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    monkeypatch.setenv("INFERENCE_BASE_URL", "http://inference:8001")
    _client, _ctor = _patch_http(
        monkeypatch, exc=httpx.TimeoutException("timed out", request=MagicMock())
    )

    assert _run(probe_ai_universe()) is ProbeResult.UNHEALTHY


def test_probe_unhealthy_when_health_status_is_not_healthy(monkeypatch):
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    monkeypatch.setenv("INFERENCE_BASE_URL", "http://inference:8001")
    _client, _ctor = _patch_http(
        monkeypatch, status=200, json_body={"status": "degraded"}
    )

    assert _run(probe_ai_universe()) is ProbeResult.UNHEALTHY


def test_probe_unhealthy_on_non_200(monkeypatch):
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    monkeypatch.setenv("INFERENCE_BASE_URL", "http://inference:8001")
    _client, _ctor = _patch_http(
        monkeypatch, status=503, json_body={"status": "unhealthy"}
    )

    assert _run(probe_ai_universe()) is ProbeResult.UNHEALTHY


def test_probe_healthy_on_200_without_status_field(monkeypatch):
    """A 200 whose body carries no status is liveness, not a verdict against."""
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    monkeypatch.setenv("INFERENCE_BASE_URL", "http://inference:8001")
    _client, _ctor = _patch_http(
        monkeypatch, status=200, json_body={"service": "inference"}
    )

    assert _run(probe_ai_universe()) is ProbeResult.HEALTHY


def test_probe_healthy_on_200_non_json_body(monkeypatch):
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    monkeypatch.setenv("INFERENCE_BASE_URL", "http://inference:8001")
    _client, _ctor = _patch_http(monkeypatch, status=200, json_raises=True)

    assert _run(probe_ai_universe()) is ProbeResult.HEALTHY


def test_probe_uses_short_timeout_without_proxy_env(monkeypatch):
    """The probe must not hang the 30s loop tick or be proxy-intercepted."""
    from cortex_api.self_healing import PROBE_TIMEOUT_SECONDS, probe_ai_universe

    _clear_url_env(monkeypatch)
    _client, ctor = _patch_http(
        monkeypatch, status=200, json_body={"status": "healthy"}
    )

    assert _run(probe_ai_universe()) is ProbeResult.HEALTHY
    assert ctor.get("timeout") == PROBE_TIMEOUT_SECONDS == 5.0
    assert ctor.get("trust_env") is False


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


@pytest.mark.parametrize(
    "env,http_kwargs,expect",
    [
        # TASK-CTX-002: with no env the probe checks the fleet default and,
        # when Inference answers healthy, the supervisor sees a plain pass.
        ({}, {"status": 200, "json_body": {"status": "healthy"}}, "healthy"),
        # Same setup, gateway down: the failure path still escalates once
        # the repair budget is exhausted.
        ({}, {"exc": httpx.ConnectError("refused", request=MagicMock())}, "escalated"),
        # An explicitly configured gateway that is down escalates the same way.
        (
            {"INFERENCE_BASE_URL": "http://inference.invalid:8001"},
            {"exc": httpx.ConnectError("down", request=MagicMock())},
            "escalated",
        ),
    ],
)
def test_end_to_end_probe_through_supervisor(monkeypatch, env, http_kwargs, expect):
    """The real probe + registry + supervisor, driven only by env + HTTP."""
    from cortex_api.self_healing import probe_ai_universe

    _clear_url_env(monkeypatch)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    _patch_http(monkeypatch, **http_kwargs)

    registry, supervisor, repairs = _supervisor_with_probe(probe_ai_universe)
    runs = [_run(supervisor.run_cycle()) for _ in range(4)]

    if expect == "healthy":
        assert all(run.unconfigured == [] for run in runs)
        assert all(run.unhealthy == [] for run in runs)
        assert repairs["attempts"] == 0
        assert supervisor.escalations == []
    else:
        assert all(run.unconfigured == [] for run in runs)
        assert runs[-1].escalated == ["ai_universe"]
