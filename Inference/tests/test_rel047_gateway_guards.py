"""TASK-REL-047 gateway routing guards.

Two changes decided in TASK-REL-045's tuning table:

1. Groq prompt-size guard — prompts estimated over 7,000 tokens must never
   reach a Groq rung (Groq's free tier caps a request at 8,000 TPM;
   TASK-INF-004 measured deterministic HTTP 413s on 9,876–11,207-token
   prompts). The chat/completions path steered long prompts away from Groq
   at selection time (TASK-REL-043); the unified/agent-role path had no
   guard. The guard lives in the gateway every path traverses.
2. NVIDIA rung disabled by configuration — the configured model id 404s on
   both fleet accounts (TASK-INF-004; TASK-SEN-003 counted 62 retries), so
   the rung is skipped until INFERENCE_NVIDIA_RUNG_ENABLED is turned on
   with a probe-verified model id. The adapter code is untouched.
"""

import asyncio
import time

import pytest

import app.providers
from app.core.config import settings
from app.providers.base import ProviderMessage, ProviderRequest, ProviderResponse
from app.providers.errors import (
    GatewayError,
    ProviderUnconfiguredError,
    TemporaryUnavailableError,
)
from app.providers.gateway import (
    GROQ_PROMPT_TOKEN_LIMIT,
    KeyPool,
    ModelGateway,
    estimate_prompt_tokens,
    groq_prompt_over_limit,
    nvidia_rung_enabled,
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


def _request(content="hello", timeout=10.0):
    return ProviderRequest(
        messages=[ProviderMessage(role="user", content=content)],
        model="some-model",
        extra_params={"timeout": timeout},
    )


def _big_request():
    # 30,000 chars = 11,538 estimated tokens (calibrated, TASK-INF-021) >
    # the 7,000 guard.
    return _request(content="x" * 30_000)


@pytest.fixture(autouse=True)
def _no_local_tier(monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_ENABLED", False)
    monkeypatch.setattr(settings, "LOCAL_PREFERRED", False)


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


# ---------------------------------------------------------------------------
# Estimation + guard predicate
# ---------------------------------------------------------------------------


def test_estimate_prompt_tokens_counts_messages_and_system():
    req = ProviderRequest(
        messages=[ProviderMessage(role="user", content="a" * 400)],
        system_instruction="b" * 400,
        model="m",
    )
    # 800 chars at the calibrated 2.6 chars/token (800 * 5 // 13).
    assert estimate_prompt_tokens(req) == 307


def test_groq_guard_boundary():
    # Exactly at the limit (18,200 chars -> 7,000 tokens at the calibrated
    # 2.6 chars/token, TASK-INF-021) is allowed; one token over is not.
    # The decided rule is prompts OVER 7,000 tokens.
    assert GROQ_PROMPT_TOKEN_LIMIT == 7000
    assert not groq_prompt_over_limit(_request(content="x" * 18_202))
    assert groq_prompt_over_limit(_request(content="x" * 18_203))
    assert not groq_prompt_over_limit(_request(content="short prompt"))


# ---------------------------------------------------------------------------
# TASK-INF-021 calibration: the estimator tracks Gemini counted tokens
# ---------------------------------------------------------------------------

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
    # the same construction TASK-INF-LLM-003 measured.
    return _INF019_HEADER + "".join(_INF019_SNIPPET % i for i in range(400))


def test_estimate_prompt_tokens_calibrated_to_gemini_inf019():
    # Gemini counts 13,519 prompt tokens for the INF-019 prompt on every
    # INF-LLM-003 trial (generate usageMetadata; countTokens agrees).
    # The calibrated estimator must track that within 1% — the old
    # chars // 4 gave 8,803, 35% low.
    req = _request(content=_inf019_prompt())
    assert estimate_prompt_tokens(req) == pytest.approx(13_519, rel=0.01)
    assert groq_prompt_over_limit(req)


_CODE_FN = (
    "def process_record(record, seen):\n"
    "    \"\"\"Validate one record and merge it into the running totals.\"\"\"\n"
    "    if record.get(\"id\") in seen:\n"
    "        return None\n"
    "    seen.add(record[\"id\"])\n"
    "    total = sum(item[\"value\"] for item in record[\"items\"])\n"
    "    return {\"id\": record[\"id\"], \"total\": total, \"n\": len(record[\"items\"])}\n\n"
)


def test_groq_guard_blocks_dense_code_prompt_the_old_estimator_passed():
    # A 27,900-char code prompt: the old chars // 4 estimator read 6,975
    # tokens and let it through, while Gemini counts ~8,270 true tokens —
    # over Groq's 8,000 TPM cap (the live gap). The calibrated estimator
    # reads 10,730 and the guard blocks it.
    code = "".join(
        _CODE_FN.replace("process_record", "process_record_%d" % i)
        for i in range(90)
    )[:27_854]
    prompt = "Review the following Python module for bugs.\n\n" + code
    assert len(prompt) == 27_900
    assert len(prompt) // 4 <= GROQ_PROMPT_TOKEN_LIMIT  # old estimator: passed
    assert estimate_prompt_tokens(_request(content=prompt)) == 10_730
    assert groq_prompt_over_limit(_request(content=prompt))


# ---------------------------------------------------------------------------
# NVIDIA rung gate
# ---------------------------------------------------------------------------


def test_nvidia_rung_disabled_by_default_and_reversible(monkeypatch):
    assert settings.INFERENCE_NVIDIA_RUNG_ENABLED is False
    assert nvidia_rung_enabled() is False
    monkeypatch.setattr(settings, "INFERENCE_NVIDIA_RUNG_ENABLED", True)
    assert nvidia_rung_enabled() is True


def test_execute_never_attempts_nvidia_primary_while_disabled(monkeypatch):
    calls = []
    _wire_providers(monkeypatch, calls, fail={"groq", "openrouter", "gemini"})
    gateway = _gateway({"openrouter": KeyPool("openrouter", ["k1"])})

    with pytest.raises(ProviderUnconfiguredError, match="disabled by configuration"):
        asyncio.run(gateway.execute("nvidia", _request()))

    # The ladder ran (and failed) without ever constructing the nvidia rung.
    assert "nvidia" not in calls
    assert "openrouter" in calls


def test_execute_nvidia_primary_reaches_credential_gate_when_reenabled(monkeypatch):
    calls = []
    _wire_providers(monkeypatch, calls, fail={"groq", "openrouter", "gemini"})
    monkeypatch.setattr(settings, "INFERENCE_NVIDIA_RUNG_ENABLED", True)
    # No credentials anywhere: with the rung re-enabled, the request must get
    # past the REL-047 gate and fail on the ordinary credential gate instead.
    monkeypatch.setattr(
        "app.providers.gateway.provider_has_credentials", lambda provider: False
    )
    gateway = _gateway()

    with pytest.raises(ProviderUnconfiguredError, match="no configured credential"):
        asyncio.run(gateway.execute("nvidia", _request()))
    assert calls == []


# ---------------------------------------------------------------------------
# Groq size guard
# ---------------------------------------------------------------------------


def test_execute_routes_oversized_prompt_away_from_groq_primary(monkeypatch):
    calls = []
    _wire_providers(monkeypatch, calls, fail={"groq", "openrouter", "gemini"})
    gateway = _gateway({"openrouter": KeyPool("openrouter", ["k1"])})

    with pytest.raises(TemporaryUnavailableError, match="Groq guard"):
        asyncio.run(gateway.execute("groq", _big_request()))

    assert "groq" not in calls


def test_execute_serves_small_prompt_from_groq_primary(monkeypatch):
    calls = []
    _wire_providers(monkeypatch, calls)
    gateway = _gateway({"groq": KeyPool("groq", ["k1"])})

    resp = asyncio.run(gateway.execute("groq", _request()))

    assert resp.content == "answer from groq"
    assert calls == ["groq"]


def test_waterfall_skips_groq_rung_for_oversized_prompt(monkeypatch):
    calls = []
    _wire_providers(monkeypatch, calls, fail={"openrouter"})
    gateway = _gateway({"openrouter": KeyPool("openrouter", ["k1"])})

    with pytest.raises(GatewayError, match="primary failed"):
        asyncio.run(
            gateway._execute_dynamic_fallback(
                failed_provider="gemini",
                request=_big_request(),
                capability="general",
                stage_name="test",
                last_error=GatewayError("primary failed", provider="gemini"),
                deadline=time.monotonic() + 10,
            )
        )

    # The waterfall's first rung for a gemini failure is Groq — skipped for
    # size. Only OpenRouter was attempted (dynamic rung + waterfall rung).
    assert "groq" not in calls
    assert calls == ["openrouter", "openrouter"]


def test_speculative_race_drops_groq_for_oversized_prompt(monkeypatch):
    gateway = _gateway()
    raced = []

    async def fake_execute(provider_name, request, **kwargs):
        raced.append(provider_name)
        return ProviderResponse(
            content="ok", model="m", provider=provider_name, raw_response={}
        )

    monkeypatch.setattr(gateway, "execute", fake_execute)

    resp = asyncio.run(
        gateway.execute_speculative(["groq", "gemini"], _big_request(), timeout=5.0)
    )

    assert resp.provider == "gemini"
    assert raced == ["gemini"]


def test_stream_refuses_guarded_providers(monkeypatch):
    gateway = _gateway()

    async def _first_chunk(provider, request):
        return await gateway.stream(provider, request).__anext__()

    with pytest.raises(GatewayError, match="Groq guard"):
        asyncio.run(_first_chunk("groq", _big_request()))

    with pytest.raises(ProviderUnconfiguredError, match="disabled by configuration"):
        asyncio.run(_first_chunk("nvidia", _request()))
