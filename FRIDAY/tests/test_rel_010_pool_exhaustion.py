"""TASK-REL-010 regression tests: Gemini pool exhaustion incident, 2026-11-14.

Production evidence (round-2 live test, 17:01-17:20 IST):
- Every key in FRIDAY's Gemini pool took ONE quota-classified 429 during a
  Google high-demand burst and was benched until the next-day daily-reset
  instant (~20h), because report_failure honoured Google's stated retry
  delay unboundedly. Four of the five keys answered HTTP 200 on a direct
  probe minutes later, yet chat stayed dead: CREDENTIAL_EXHAUSTED.
- With FRIDAY_LLM_PROVIDER=gemini the factory returned a bare Gemini
  provider, so the owner's designated text fallback (Groq) never engaged.
- The offline (no-model) path ran get_time_date with no arguments, so
  "time in Tokyo" answered with the owner's IST clock.
"""

import json
from datetime import datetime, timedelta

import pytest

from friday.auth.credential_pool import (
    MAX_COOLDOWN_SECONDS,
    FailureCategory,
    GeminiCredentialPool,
)
from friday.core.exceptions import LLMProviderError
from friday.core.types import Message, Role
from friday.llm.base import BaseLLMProvider
from friday.llm.fallback_chain_provider import ExhaustionFailoverProvider

KEYS = ["KEY_PRIMARY", "KEY_FALLBACK_1", "KEY_FALLBACK_2"]


def _pool() -> GeminiCredentialPool:
    pool = GeminiCredentialPool(keys=KEYS)
    pool.load_keys(KEYS)
    pool.reset_all()
    return pool


# ---------------------------------------------------------------------------
# 1. Cooldown cap: one 429 must not bench a key for ~20 hours
# ---------------------------------------------------------------------------

def test_quota_retry_delay_is_capped():
    pool = _pool()
    err = Exception(
        "429 RESOURCE_EXHAUSTED. Quota exceeded for quota metric "
        "'Generate requests'. Please retry in 73000s"
    )
    pool.report_failure(KEYS[0], error=err)
    cred = pool._find_by_key(KEYS[0])
    assert cred.last_failure_category == FailureCategory.QUOTA_EXHAUSTED
    delta = (cred.cooldown_until - cred.last_failed_at).total_seconds()
    assert 0 < delta <= MAX_COOLDOWN_SECONDS + 5


def test_rate_limit_cooldown_stays_short():
    pool = _pool()
    pool.report_failure(KEYS[1], error=Exception("429 Too Many Requests"))
    cred = pool._find_by_key(KEYS[1])
    assert cred.last_failure_category == FailureCategory.RATE_LIMIT
    delta = (cred.cooldown_until - cred.last_failed_at).total_seconds()
    assert 0 < delta <= 65


def test_auth_failure_cooldown_is_not_capped():
    """A genuinely invalid key stays benched: the cap must not resurrect it."""
    pool = _pool()
    pool.report_failure(KEYS[2], error=Exception("400 API_KEY_INVALID"))
    cred = pool._find_by_key(KEYS[2])
    assert cred.last_failure_category == FailureCategory.AUTH_FAILED
    delta = (cred.cooldown_until - cred.last_failed_at).total_seconds()
    assert delta > MAX_COOLDOWN_SECONDS


def test_persisted_long_cooldown_is_clamped_on_load(tmp_path):
    pool = _pool()
    state_file = tmp_path / "gemini_pool_state.json"
    now = datetime.utcnow()
    state = {}
    for label, key in zip(["PRIMARY", "FALLBACK 1"], KEYS[:2]):
        cred = pool._find_by_key(key)
        state[label] = {
            "project_label": label,
            "key_fingerprint": cred.key_fingerprint,
            "failure_count": 1,
            "failure_category": "quota_exceeded",
            "cooldown_until": (now + timedelta(hours=20)).isoformat(),
            "last_failed_at": now.isoformat(),
            "last_success_at": None,
        }
    state_file.write_text(json.dumps(state))
    pool.state_file = state_file
    try:
        pool._load_persisted_state()
        cred = pool._find_by_key(KEYS[0])
        remaining = (cred.cooldown_until - datetime.utcnow()).total_seconds()
        assert 0 < remaining <= MAX_COOLDOWN_SECONDS + 5
    finally:
        pool.reset_all()
        pool.state_file = None


# ---------------------------------------------------------------------------
# 2. Exhaustion failover: Groq answers when the Gemini pool is benched
# ---------------------------------------------------------------------------

class _StubProvider(BaseLLMProvider):
    def __init__(self, name: str, *, content: str | None = None, error: Exception | None = None):
        super().__init__(model="stub-model")
        self._name = name
        self._content = content
        self._error = error

    @property
    def provider_name(self) -> str:
        return self._name

    def generate(self, messages, tools=None):
        if self._error is not None:
            raise self._error
        return Message(role=Role.ASSISTANT, content=self._content or "")


def test_failover_on_credential_exhausted():
    primary = _StubProvider(
        "gemini",
        error=LLMProviderError("CREDENTIAL_EXHAUSTED: All Gemini credentials in pool are exhausted or in cooldown."),
    )
    fallback = _StubProvider("groq", content="answered by the text fallback")
    wrapped = ExhaustionFailoverProvider(primary=primary, fallback=fallback)
    out = wrapped.generate([Message(role=Role.USER, content="capital of Australia?")])
    assert out.content == "answered by the text fallback"
    assert wrapped.provider_name == "gemini"


def test_no_failover_on_other_errors():
    primary = _StubProvider("gemini", error=LLMProviderError("Gemini invalid request (not retryable)"))
    fallback = _StubProvider("groq", content="must not be used")
    wrapped = ExhaustionFailoverProvider(primary=primary, fallback=fallback)
    with pytest.raises(LLMProviderError):
        wrapped.generate([Message(role=Role.USER, content="hi")])


def test_primary_success_passes_through():
    primary = _StubProvider("gemini", content="gemini answer")
    fallback = _StubProvider("groq", content="must not be used")
    wrapped = ExhaustionFailoverProvider(primary=primary, fallback=fallback)
    out = wrapped.generate([Message(role=Role.USER, content="hi")])
    assert out.content == "gemini answer"


def test_factory_wraps_gemini_with_groq_failover(monkeypatch):
    monkeypatch.setenv("FRIDAY_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("FRIDAY_GEMINI_API_KEY", "dummy-gemini-key")
    monkeypatch.setenv("FRIDAY_GROQ_API_KEY", "dummy-groq-key")
    from friday.core.config import Settings
    from friday.llm.factory import create_llm_provider
    from friday.llm.gemini_provider import GeminiLLMProvider
    from friday.llm.groq_provider import GroqLLMProvider

    provider = create_llm_provider(Settings())
    assert isinstance(provider, ExhaustionFailoverProvider)
    assert isinstance(provider.primary, GeminiLLMProvider)
    assert isinstance(provider.fallback, GroqLLMProvider)


def test_factory_without_groq_returns_bare_gemini(monkeypatch):
    monkeypatch.setenv("FRIDAY_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("FRIDAY_GEMINI_API_KEY", "dummy-gemini-key")
    monkeypatch.delenv("FRIDAY_GROQ_API_KEY", raising=False)
    import friday.llm.factory as factory

    monkeypatch.setattr(factory, "groq_credential_pool", _EmptyPool())
    from friday.core.config import Settings

    settings = Settings()
    object.__setattr__(settings, "groq_api_key", None) if hasattr(settings, "groq_api_key") else None
    provider = factory.create_llm_provider(settings)
    from friday.llm.gemini_provider import GeminiLLMProvider

    assert isinstance(provider, GeminiLLMProvider)
    assert not isinstance(provider, ExhaustionFailoverProvider)


class _EmptyPool:
    credentials: list = []


# ---------------------------------------------------------------------------
# 3. Offline path: a named place must reach the time tool's timezone argument
# ---------------------------------------------------------------------------

class _Step:
    arguments: dict = {}


class _Tool:
    def __init__(self, properties: dict):
        self.parameters = {"type": "object", "properties": properties}


def test_offline_time_arguments_carry_named_zone():
    from friday.cognition.offline import _arguments_for

    tool = _Tool({"timezone": {"type": "string"}})
    assert _arguments_for(tool, _Step(), "what time is it in Tokyo?") == {"timezone": "Asia/Tokyo"}
    assert _arguments_for(tool, _Step(), "current time in London please") == {"timezone": "Europe/London"}
    assert _arguments_for(tool, _Step(), "tell me the time in New York") == {"timezone": "America/New_York"}


def test_offline_time_arguments_explicit_iana_and_default():
    from friday.cognition.offline import _arguments_for

    tool = _Tool({"timezone": {"type": "string"}})
    assert _arguments_for(tool, _Step(), "time in Asia/Tokyo right now") == {"timezone": "Asia/Tokyo"}
    # No place named: no argument, the tool's own default (owner IST) applies.
    assert _arguments_for(tool, _Step(), "what time is it?") == {}
    # A place we do not know is not guessed.
    assert _arguments_for(tool, _Step(), "what time is it in Atlantis?") == {}


def test_offline_arguments_unchanged_for_other_tools():
    from friday.cognition.offline import _arguments_for

    input_tool = _Tool({"input": {"type": "string"}})
    assert _arguments_for(input_tool, _Step(), "count the words: hello world") == {"input": "count the words: hello world"}
    path_tool = _Tool({"path": {"type": "string"}})
    assert _arguments_for(path_tool, _Step(), "read the file in Tokyo") == {}
