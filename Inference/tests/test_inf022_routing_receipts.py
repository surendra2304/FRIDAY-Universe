"""TASK-INF-022 routing receipts + prompt-size deadline classes.

Two changes, both measured in INF-LLM-003:

1. Deadline classes: prompts are classified "short" or "large" on the
   calibrated token estimate (TASK-INF-021). Short prompts keep the
   tight default budget and the 15 s primary slice. A large prompt for
   the Gemini primary is routed DIRECTLY to the fallback ladder (no
   primary attempt) when the caller set no explicit timeout: INF-LLM-003
   measured the Gemini primary cut at 14.7 s on 3/3 gateway trials for
   the 13,519-token INF-019 shape, with direct completions at 6.4 s /
   67.3 s / 99.3 s / >150 s -- no sane primary-slice deadline covers
   that tail, and the fallback already serves a correct answer
   end-to-end. The budget itself is UNCHANGED for both classes
   (INF-LLM-003 recommendation: KEEP the deadline).
2. Routing receipts: every gateway execute() records a receipt (task
   class / capability, requested vs served provider/model, latency,
   deadline class, fallback use + direct-to-fallback flag), kept in a
   bounded in-memory ring and surfaced on the health /status endpoint.
"""

import asyncio
import time

import pytest

import app.providers
from app.core.config import settings
from app.providers.base import ProviderMessage, ProviderRequest, ProviderResponse
from app.providers.errors import GatewayError
from app.providers.gateway import (
    GROQ_PROMPT_TOKEN_LIMIT,
    LARGE_PROMPT_TOKEN_THRESHOLD,
    KeyPool,
    ModelGateway,
    _ROUTING_RECEIPTS,
    estimate_prompt_tokens,
    prompt_deadline_class,
    record_routing_receipt,
    routing_receipt_counts,
    routing_receipts,
)


class _Limiter:
    async def acquire(self):
        return None

    def release(self):
        return None


class _Health:
    def __init__(self):
        self.successes = []
        self.failures = []

    def record_success(self, provider, latency):
        self.successes.append((provider, latency))

    def record_failure(self, provider, error, **kwargs):
        self.failures.append((provider, error, kwargs))


class _RecordingProvider:
    """Fake provider that records generate() calls and optionally fails."""

    def __init__(self, name, calls, fail=False):
        self._name = name
        self._calls = calls
        self._fail = fail

    async def generate(self, request):
        self._calls.append(self._name)
        if self._fail:
            raise RuntimeError(f"{self._name} is down")
        return ProviderResponse(
            content=f"answer from {self._name}",
            model=request.model or "fake",
            provider=self._name,
            raw_response={},
        )


class _OpenRouterFake(_RecordingProvider):
    async def get_best_free_model(self, _capability):
        return "test/free-model"


def _gateway(pools=None):
    gateway = ModelGateway.__new__(ModelGateway)
    gateway.key_pools = pools or {}
    gateway.rate_limiters = {name: _Limiter() for name in (pools or {})}
    gateway.health_tracker = _Health()
    return gateway


def _request(content="hello", timeout=None):
    # No explicit timeout by default: the direct-to-fallback rule only
    # applies to default-budget requests (an explicit timeout opts out).
    return ProviderRequest(
        messages=[ProviderMessage(role="user", content=content)],
        model="gemini-flash-latest",
        extra_params={"timeout": timeout} if timeout is not None else {},
    )


@pytest.fixture(autouse=True)
def _no_local_tier(monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_ENABLED", False)
    monkeypatch.setattr(settings, "LOCAL_PREFERRED", False)


@pytest.fixture(autouse=True)
def _clear_receipts():
    _ROUTING_RECEIPTS.clear()
    yield
    _ROUTING_RECEIPTS.clear()


def _wire_providers(monkeypatch, calls, fail=()):
    """Route every provider construction to recording fakes."""

    def get_provider(name, **kwargs):
        if name == "openrouter":
            return _OpenRouterFake(name, calls, fail=name in fail)
        return _RecordingProvider(name, calls, fail=name in fail)

    monkeypatch.setattr(app.providers, "get_provider", get_provider)
    monkeypatch.setattr(
        "app.providers.gateway.provider_has_credentials", lambda provider: True
    )


_INF019_SNIPPET = (
    "# module utils.py - helper %d\n"
    "def add(a, b):\n    \"\"\"Return a + b.\"\"\"\n    return a + b\n\n"
)

_INF019_HEADER = (
    "Review the following Python module for bugs and style issues. "
    "List each finding on its own line; if none, say NO FINDINGS.\n\n"
)


def _inf019_prompt() -> str:
    # Byte-identical rebuild of the INF-019 probe A prompt (35,214 chars),
    # the same construction TASK-INF-LLM-003 measured (13,519 Gemini tokens).
    return _INF019_HEADER + "".join(_INF019_SNIPPET % i for i in range(400))


def _large_request():
    return _request(content=_inf019_prompt())


# ---------------------------------------------------------------------------
# Deadline classes
# ---------------------------------------------------------------------------


def test_deadline_class_boundary_is_the_groq_guard_limit():
    # The class boundary is the codebase's existing oversized-prompt line.
    assert LARGE_PROMPT_TOKEN_THRESHOLD == GROQ_PROMPT_TOKEN_LIMIT == 7000
    # Exactly at the limit (18,200 chars -> 7,000 tokens) is short;
    # one token over is large.
    assert prompt_deadline_class(_request(content="x" * 18_200)) == "short"
    assert prompt_deadline_class(_request(content="x" * 18_203)) == "large"
    assert prompt_deadline_class(_request(content="short prompt")) == "short"


def test_inf019_prompt_is_large_class():
    # The INF-019 shape Gemini counts at 13,519 tokens (calibrated
    # estimate 13,543) is large by a wide margin.
    req = _large_request()
    assert len(_inf019_prompt()) == 35_214
    assert estimate_prompt_tokens(req) == pytest.approx(13_519, rel=0.01)
    assert prompt_deadline_class(req) == "large"


# ---------------------------------------------------------------------------
# Direct-to-fallback routing for large Gemini prompts
# ---------------------------------------------------------------------------


def test_execute_routes_large_gemini_prompt_directly_to_fallback(monkeypatch):
    calls = []
    _wire_providers(monkeypatch, calls)
    gateway = _gateway(
        {
            "gemini": KeyPool("gemini", ["k1"]),
            "openrouter": KeyPool("openrouter", ["k1"]),
        }
    )

    resp = asyncio.run(gateway.execute("gemini", _large_request(), capability="code_review"))

    # The Gemini primary was never attempted; the ladder served it.
    assert "gemini" not in calls
    assert "openrouter" in calls
    assert resp.provider == "openrouter"
    assert resp.content == "answer from openrouter"

    receipts = routing_receipts()
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["outcome"] == "success"
    assert receipt["capability"] == "code_review"
    assert receipt["provider_requested"] == "gemini"
    assert receipt["provider_served"] == "openrouter"
    assert receipt["deadline_class"] == "large"
    assert receipt["prompt_tokens_est"] == pytest.approx(13_519, rel=0.01)
    assert receipt["fallback_used"] is True
    assert receipt["fallback_direct"] is True
    assert receipt["latency_ms"] is not None and receipt["latency_ms"] >= 0


def test_explicit_timeout_opts_out_of_direct_skip(monkeypatch):
    # A caller that sets its own timeout asked to wait for Gemini: the
    # primary is attempted even for a large prompt.
    calls = []
    _wire_providers(monkeypatch, calls)
    gateway = _gateway({"gemini": KeyPool("gemini", ["k1"])})

    resp = asyncio.run(
        gateway.execute("gemini", _request(content=_inf019_prompt(), timeout=10.0))
    )

    assert calls == ["gemini"]
    assert resp.provider == "gemini"
    receipt = routing_receipts()[0]
    assert receipt["deadline_class"] == "large"
    assert receipt["fallback_used"] is False
    assert receipt["fallback_direct"] is False


def test_execute_records_short_prompt_receipt_from_primary(monkeypatch):
    calls = []
    _wire_providers(monkeypatch, calls)
    gateway = _gateway({"gemini": KeyPool("gemini", ["k1"])})

    resp = asyncio.run(gateway.execute("gemini", _request(), capability="general"))

    assert resp.provider == "gemini"
    assert calls == ["gemini"]
    receipt = routing_receipts()[0]
    assert receipt["outcome"] == "success"
    assert receipt["capability"] == "general"
    assert receipt["provider_requested"] == "gemini"
    assert receipt["provider_served"] == "gemini"
    assert receipt["model_requested"] == "gemini-flash-latest"
    assert receipt["model_served"] == "gemini-flash-latest"
    assert receipt["deadline_class"] == "short"
    assert receipt["fallback_used"] is False
    assert receipt["fallback_direct"] is False
    assert receipt["timeout_budget_s"] == pytest.approx(60.0)
    assert receipt["latency_ms"] is not None and receipt["latency_ms"] >= 0


def test_execute_records_error_receipt_and_reraises(monkeypatch):
    calls = []
    _wire_providers(monkeypatch, calls, fail={"gemini", "openrouter", "groq"})
    gateway = _gateway({"gemini": KeyPool("gemini", ["k1"])})

    with pytest.raises(GatewayError):
        asyncio.run(gateway.execute("gemini", _request(), capability="general"))

    receipt = routing_receipts()[0]
    assert receipt["outcome"] == "error"
    assert receipt["error"]
    assert receipt["provider_served"] is None
    assert receipt["latency_ms"] is not None and receipt["latency_ms"] >= 0


# ---------------------------------------------------------------------------
# Receipt store
# ---------------------------------------------------------------------------


def test_receipt_store_caps_at_limit_and_counts():
    for i in range(105):
        record_routing_receipt(
            {
                "outcome": "success" if i % 2 == 0 else "error",
                "fallback_used": i % 3 == 0,
                "fallback_direct": i % 5 == 0,
            }
        )
    assert len(_ROUTING_RECEIPTS) == 100
    counts = routing_receipt_counts()
    assert counts["total"] == 100
    assert counts["success"] + counts["error"] == 100
    # Newest first.
    assert routing_receipts(limit=1)[0]["outcome"] == ("success" if 104 % 2 == 0 else "error")


def test_receipts_newest_first():
    record_routing_receipt({"outcome": "success", "n": 1})
    record_routing_receipt({"outcome": "error", "n": 2})
    recent = routing_receipts(limit=2)
    assert [r["n"] for r in recent] == [2, 1]
    assert routing_receipts(limit=0) == []
