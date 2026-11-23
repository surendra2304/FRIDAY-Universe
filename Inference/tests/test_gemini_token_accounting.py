"""TASK-INF-009 — Gemini route token accounting regression tests.

Defect (measured live by TASK-INF-005 against the production gateway):
gemini-3.6-flash answers served through Inference truncated with
finish_reason MAX_TOKENS on 14/17 calls, showing 0-15 *visible*
completion tokens while total_tokens ran 330-518. Root cause: the
adapter passed the caller's max_tokens verbatim as Gemini's
maxOutputTokens and never set thinkingConfig. Gemini thinking models
think by default, and maxOutputTokens is a hard ceiling on
thoughts + visible output combined — so the hidden reasoning burn
(usageMetadata.thoughtsTokenCount, which the adapter never read)
consumed the caller's entire visible budget.

These tests drive GeminiProvider.generate() through a fake transport
that reproduces the Gemini API's documented accounting rules:

  * thinking runs first and burns `thinking_demand` tokens, capped by
    thinkingConfig.thinkingBudget when one is sent;
  * thoughts + visible output are jointly capped by maxOutputTokens;
  * usageMetadata reports promptTokenCount / candidatesTokenCount /
    thoughtsTokenCount / totalTokenCount separately;
  * finishReason is MAX_TOKENS when the combined cap cuts generation.

A model variant that ignores thinkingBudget models a model that cannot
honour the split — the route must then say so in its accounting
metadata instead of truncating silently.
"""

import json

import pytest

from app.providers import gemini as gemini_module
from app.providers.base import ProviderMessage, ProviderRequest
from app.providers.gemini import GeminiProvider

PROMPT_TOKENS = 100

ANSWER_WORDS = (
    "The six-week study found that daily walking improved sleep quality "
    "and reduced reported stress across all age groups in the trial"
).split()
ANSWER_TEXT = " ".join(ANSWER_WORDS)

EXTRACT_JSON = {"title": "Meridian approval", "score": 42, "tags": ["solar", "grid"]}
EXTRACT_WORDS = json.dumps(EXTRACT_JSON).split()
EXTRACT_TEXT = " ".join(EXTRACT_WORDS)


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class FakeGeminiClient:
    """Simulates Gemini generateContent accounting for one model."""

    def __init__(self, *, model, thinking_demand, answer_words, honour_thinking_budget=True):
        self.model = model
        self.thinking_demand = thinking_demand
        self.answer_words = answer_words
        self.honour_thinking_budget = honour_thinking_budget
        self.captured_payload = None

    async def post(self, url, headers=None, json=None, timeout=None):  # noqa: A002 - mirrors httpx
        payload = json
        self.captured_payload = payload
        gen = payload.get("generationConfig", {})
        max_out = gen.get("maxOutputTokens")
        thinking_cfg = gen.get("thinkingConfig", {}) or {}

        # Flash-Lite thinks only when a thinking config explicitly enables it;
        # every other current Gemini model thinks by default.
        thinks = self.thinking_demand > 0 and ("lite" not in self.model or bool(thinking_cfg))
        thoughts = 0
        if thinks:
            thoughts = self.thinking_demand
            budget = thinking_cfg.get("thinkingBudget")
            if budget is not None and self.honour_thinking_budget:
                thoughts = min(thoughts, budget)

        answer_tokens = len(self.answer_words)
        if max_out is None:
            visible = answer_tokens
        else:
            visible = max(0, min(answer_tokens, max_out - thoughts))
        finish = "STOP" if visible >= answer_tokens else "MAX_TOKENS"
        text = " ".join(self.answer_words[:visible])
        body = {
            "candidates": [
                {
                    "content": {"parts": [{"text": text}]},
                    "finishReason": finish,
                }
            ],
            "usageMetadata": {
                "promptTokenCount": PROMPT_TOKENS,
                "candidatesTokenCount": visible,
                "thoughtsTokenCount": thoughts,
                "totalTokenCount": PROMPT_TOKENS + visible + thoughts,
            },
        }
        return _FakeResponse(body)


def _install_fake(monkeypatch, fake):
    async def _get_client():
        return fake

    monkeypatch.setattr(gemini_module, "get_shared_client", _get_client)


def _provider():
    return GeminiProvider(api_key="test-key")


def _request(**overrides):
    base = dict(
        messages=[ProviderMessage(role="user", content="Summarise the study.")],
        model="gemini-3.6-flash",
        temperature=0.0,
        max_tokens=200,
    )
    base.update(overrides)
    return ProviderRequest(**base)


async def test_modest_budget_completion_finishes_stop_with_full_answer(monkeypatch):
    """Thinking demand 300 + a 21-token answer must fit a 200-token
    declared budget once thinking is accounted separately."""
    fake = FakeGeminiClient(model="gemini-3.6-flash", thinking_demand=300, answer_words=ANSWER_WORDS)
    _install_fake(monkeypatch, fake)

    resp = await _provider().generate(_request(max_tokens=200))

    assert resp.finish_reason == "STOP"
    assert resp.content == ANSWER_TEXT
    assert resp.completion_tokens == len(ANSWER_WORDS)


async def test_payload_separates_thinking_from_visible_budget(monkeypatch):
    """The wire payload must reserve the declared budget for visible
    output: maxOutputTokens = declared + thinking allowance, with the
    allowance hard-capped via thinkingConfig.thinkingBudget.

    TASK-INF-011 changed the DEFAULT Flash budget to 0 (thinking off),
    so this INF-009 split is now exercised with an explicit caller
    thinking_budget — the allowance machinery itself is unchanged."""
    fake = FakeGeminiClient(model="gemini-3.6-flash", thinking_demand=10, answer_words=ANSWER_WORDS)
    _install_fake(monkeypatch, fake)

    await _provider().generate(
        _request(max_tokens=200, extra_params={"thinking_budget": 1024})
    )

    gen = fake.captured_payload["generationConfig"]
    assert gen["maxOutputTokens"] > 200
    assert gen["thinkingConfig"]["thinkingBudget"] == gen["maxOutputTokens"] - 200


async def test_extract_request_returns_parseable_json(monkeypatch):
    """An extract-shaped request (JSON mode) under a modest budget must
    return complete, parseable JSON — not scaffolding cut mid-object."""
    fake = FakeGeminiClient(model="gemini-3.6-flash", thinking_demand=280, answer_words=EXTRACT_WORDS)
    _install_fake(monkeypatch, fake)

    resp = await _provider().generate(
        _request(max_tokens=150, response_schema={"type": "object"})
    )

    assert resp.finish_reason == "STOP"
    assert json.loads(resp.content) == EXTRACT_JSON


async def test_usage_reports_reasoning_tokens_and_accounting(monkeypatch):
    """The hidden burn must be visible in the route's own accounting:
    reasoning_tokens on the response and a token_accounting block whose
    parts sum to the reported total."""
    fake = FakeGeminiClient(model="gemini-3.6-flash", thinking_demand=300, answer_words=ANSWER_WORDS)
    _install_fake(monkeypatch, fake)

    # Explicit caller budget (TASK-INF-011 made 0 the Flash default):
    # the accounting must still surface a real thinking burn.
    resp = await _provider().generate(
        _request(max_tokens=200, extra_params={"thinking_budget": 1024})
    )

    assert getattr(resp, "reasoning_tokens", None) == 300
    assert resp.completion_tokens == len(ANSWER_WORDS)
    assert resp.total_tokens == PROMPT_TOKENS + len(ANSWER_WORDS) + 300
    accounting = (resp.raw_response or {}).get("token_accounting") or {}
    assert accounting.get("thoughts_tokens") == 300
    assert accounting.get("visible_tokens") == len(ANSWER_WORDS)
    assert accounting.get("declared_max_tokens") == 200
    assert accounting.get("truncated") is False


async def test_caller_thinking_budget_zero_disables_thinking(monkeypatch):
    """A caller that explicitly budgets zero thinking gets exactly the
    old visible-only accounting: no allowance is added."""
    fake = FakeGeminiClient(model="gemini-3.6-flash", thinking_demand=300, answer_words=ANSWER_WORDS)
    _install_fake(monkeypatch, fake)

    resp = await _provider().generate(
        _request(max_tokens=200, extra_params={"thinking_budget": 0})
    )

    gen = fake.captured_payload["generationConfig"]
    assert gen["thinkingConfig"]["thinkingBudget"] == 0
    assert gen["maxOutputTokens"] == 200
    assert resp.finish_reason == "STOP"
    assert resp.content == ANSWER_TEXT


async def test_thinking_overflow_is_flagged_not_silent(monkeypatch):
    """A model that ignores the thinking cap can still truncate — but
    the response must carry the degradation in its accounting metadata
    (truncated + thinking_overflow + the actual burn), not pass the
    truncated text off as a normal answer."""
    fake = FakeGeminiClient(
        model="gemini-3.6-flash",
        thinking_demand=5000,
        answer_words=ANSWER_WORDS,
        honour_thinking_budget=False,
    )
    _install_fake(monkeypatch, fake)

    resp = await _provider().generate(_request(max_tokens=200))

    assert resp.finish_reason == "MAX_TOKENS"
    assert getattr(resp, "reasoning_tokens", None) == 5000
    accounting = (resp.raw_response or {}).get("token_accounting") or {}
    assert accounting.get("truncated") is True
    assert accounting.get("thinking_overflow") is True
    assert accounting.get("thoughts_tokens") == 5000


async def test_lite_model_payload_unchanged(monkeypatch):
    """Guard: Flash-Lite does not think by default — its payload must
    keep the caller's budget verbatim and gain no thinkingConfig."""
    fake = FakeGeminiClient(model="gemini-2.5-flash-lite", thinking_demand=300, answer_words=ANSWER_WORDS)
    _install_fake(monkeypatch, fake)

    resp = await _provider().generate(_request(model="gemini-2.5-flash-lite", max_tokens=200))

    gen = fake.captured_payload["generationConfig"]
    assert gen["maxOutputTokens"] == 200
    assert "thinkingConfig" not in gen
    assert resp.finish_reason == "STOP"
    assert resp.content == ANSWER_TEXT


async def test_no_max_tokens_leaves_payload_unchanged(monkeypatch):
    """Guard: with no declared budget there is nothing to protect —
    no maxOutputTokens is sent, exactly as before."""
    fake = FakeGeminiClient(model="gemini-3.6-flash", thinking_demand=10, answer_words=ANSWER_WORDS)
    _install_fake(monkeypatch, fake)

    await _provider().generate(_request(max_tokens=None))

    gen = fake.captured_payload["generationConfig"]
    assert "maxOutputTokens" not in gen


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


# ---------------------------------------------------------------------------
# TASK-INF-026: the 503 failover to gemini-3.6-flash carries provenance
# ---------------------------------------------------------------------------


class _FailoverFakeClient:
    """503s the requested flagship, serves the 3.6 fallback (live shape)."""

    def __init__(self):
        self.called_models = []

    async def post(self, url, headers=None, json=None, timeout=None):  # noqa: A002 - mirrors httpx
        model = url.split("/models/")[1].split(":")[0]
        self.called_models.append(model)
        if model == "gemini-3.8-flash":
            return _FakeResponse({"error": {"message": "high demand"}}, status_code=503)
        body = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "fallback answer"}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": PROMPT_TOKENS,
                "candidatesTokenCount": 2,
                "totalTokenCount": PROMPT_TOKENS + 2,
            },
        }
        return _FakeResponse(body)


async def test_503_failover_serves_36_with_provenance(monkeypatch):
    """gemini-3.8-flash 503 -> gemini-3.6-flash serves, and the response
    discloses the substitution with its cause. Before this fix the
    provenance block reported fallback_reason null while the selected
    flagship had not served (measured live 2026-11-23)."""
    fake = _FailoverFakeClient()
    _install_fake(monkeypatch, fake)

    resp = await _provider().generate(_request(model="gemini-3.8-flash"))

    assert fake.called_models == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert resp.model == "gemini-3.6-flash"
    assert resp.content == "fallback answer"
    provenance = (resp.raw_response or {}).get("fallback_provenance") or {}
    assert provenance.get("requested_model") == "gemini-3.8-flash"
    assert provenance.get("actual_model") == "gemini-3.6-flash"
    assert "503" in (provenance.get("fallback_reason") or "")


async def test_direct_36_serve_carries_no_failover_provenance(monkeypatch):
    """A model that serves under its own name must not be labelled a
    substitution — no provenance is attached when no failover happened."""
    fake = _FailoverFakeClient()
    _install_fake(monkeypatch, fake)

    resp = await _provider().generate(_request(model="gemini-3.6-flash"))

    assert fake.called_models == ["gemini-3.6-flash"]
    assert resp.model == "gemini-3.6-flash"
    assert (resp.raw_response or {}).get("fallback_provenance") is None
