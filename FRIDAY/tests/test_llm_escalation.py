"""TASK-REL-044 — FRIDAY LLM escalation to Inference (owner routing policy).

Owner's policy (2026-11-15): FRIDAY chats on the API keys in its own env;
when he assigns a COMPLEX task — where its own keys/usage are not enough —
FRIDAY uses Inference to get more usage.

Covered here:
* the deterministic complexity classifier (signals, not vibes);
* EscalatingLLMProvider routing: chat → own pool; complex turn →
  Inference with trigger + served model + provenance recorded;
  voice turns never complexity-escalate; tool-chain depth escalates;
  Inference failure falls back to the own pool (never hard-fails);
  own-pool exhaustion escalates (the REL-010 integration rung);
* InferenceChatProvider's wire contract against a monkeypatched httpx:
  message flattening, the markup tool protocol, provenance passthrough,
  and degraded/unavailable → LLMProviderError.
"""

from __future__ import annotations

import pytest

from friday.core.exceptions import LLMProviderError
from friday.core.types import Message, Role, ToolCall
from friday.llm.base import BaseLLMProvider
from friday.llm.escalation import (
    COMPLEX_KINDS,
    EscalatingLLMProvider,
    InferenceChatProvider,
    TurnRouteContext,
    bind_turn_route_context,
    classify_turn_complexity,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeProvider(BaseLLMProvider):
    def __init__(self, name: str, *, content: str = "answer", error: Exception | None = None):
        super().__init__(model=f"{name}-model")
        self._name = name
        self._content = content
        self._error = error
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return self._name

    def generate(self, messages, tools=None):  # noqa: ANN001 - test fake
        self.calls += 1
        if self._error is not None:
            raise self._error
        return Message(role=Role.ASSISTANT, content=self._content)


def _bind(ctx: TurnRouteContext) -> TurnRouteContext:
    return bind_turn_route_context(ctx)


def _msgs(text: str = "hello") -> list[Message]:
    return [Message(role=Role.USER, content=text)]


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


def test_classifier_delegation_phrasing():
    kinds = classify_turn_complexity("Ask Stratex for the current portfolio status")
    assert "delegation" in kinds


def test_classifier_research_phrasing():
    kinds = classify_turn_complexity("Research the latest RBI rate decision and summarise it")
    assert "research" in kinds


def test_classifier_code_generation():
    kinds = classify_turn_complexity("Write a Python function that merges two sorted lists")
    assert "code_generation" in kinds


def test_classifier_synthesis():
    kinds = classify_turn_complexity("Write a detailed report on the fleet's health this week")
    assert "long_form_synthesis" in kinds


def test_classifier_multi_step_chain():
    kinds = classify_turn_complexity(
        "First check the fleet status, then restart the failing service, and finally verify it is healthy"
    )
    assert "multi_step" in kinds


def test_classifier_required_tools_signals():
    assert "delegation" in classify_turn_complexity("do it", required_tools=["fleet_dispatch"])
    assert "research" in classify_turn_complexity("do it", required_tools=["web_search"])
    assert "code_generation" in classify_turn_complexity("do it", required_tools=["forge_code_task"])
    assert "long_form_synthesis" in classify_turn_complexity(
        "do it", required_tools=["synthesize_information"]
    )


def test_classifier_background_task_capability_is_delegation():
    kinds = classify_turn_complexity("run this in the background", routed_capability="BACKGROUND_TASK")
    assert "delegation" in kinds


@pytest.mark.parametrize(
    "text",
    [
        "Hi FRIDAY, how are you today?",
        "What time is it in Tokyo right now?",
        "What is the capital of France?",
        "What did I ask you about yesterday?",
        "Tell me a joke",
    ],
)
def test_classifier_plain_chat_is_not_complex(text):
    assert classify_turn_complexity(text) == frozenset()


def test_classifier_single_tool_execution_is_not_complex():
    # One device action (the common smart-home case) is a single tool
    # call, not a complex task — TOOL_EXECUTION alone must not escalate.
    kinds = classify_turn_complexity(
        "Turn off the living room light", routed_capability="tool_execution"
    )
    assert kinds == frozenset()


def test_complex_kinds_cover_classifier_outputs():
    for text in (
        "Ask Stratex for the balance",
        "Research quantum computing breakthroughs",
        "Write a Python script to parse logs",
        "Write a detailed report on the results",
        "First do A, then do B, and finally do C",
    ):
        assert classify_turn_complexity(text) <= COMPLEX_KINDS


# ---------------------------------------------------------------------------
# EscalatingLLMProvider
# ---------------------------------------------------------------------------


def test_chat_turn_stays_on_own_pool():
    own = _FakeProvider("gemini", content="own answer")
    inf = _FakeProvider("inference", content="inference answer")
    wrapped = EscalatingLLMProvider(own=own, inference=inf)
    _bind(TurnRouteContext(channel="chat", goal="hi", task_kinds=frozenset()))
    out = wrapped.generate(_msgs())
    assert out.content == "own answer"
    assert inf.calls == 0
    assert out.metadata["llm_route"] == "own"


def test_complex_turn_escalates_with_event_and_metadata():
    own = _FakeProvider("gemini")
    inf = _FakeProvider("inference", content="deep answer")
    wrapped = EscalatingLLMProvider(own=own, inference=inf)
    ctx = _bind(
        TurnRouteContext(
            channel="chat",
            goal="Ask Stratex for the balance",
            task_kinds=frozenset({"delegation"}),
        )
    )
    out = wrapped.generate(_msgs())
    assert out.content == "deep answer"
    assert own.calls == 0
    assert out.metadata["llm_route"] == "inference"
    assert out.metadata["escalation_trigger"].startswith("complex_task:")
    assert ctx.events and ctx.events[-1]["route"] == "inference"
    assert ctx.events[-1]["trigger"].startswith("complex_task:")


def test_voice_turn_never_complexity_escalates():
    own = _FakeProvider("gemini", content="voice answer")
    inf = _FakeProvider("inference")
    wrapped = EscalatingLLMProvider(own=own, inference=inf)
    _bind(
        TurnRouteContext(
            channel="voice",
            goal="Ask Stratex for the balance and then research the market",
            task_kinds=frozenset({"delegation", "research"}),
        )
    )
    out = wrapped.generate(_msgs())
    assert out.content == "voice answer"
    assert inf.calls == 0


def test_tool_chain_depth_escalates_via_context_counter():
    own = _FakeProvider("gemini")
    inf = _FakeProvider("inference", content="deep chain answer")
    wrapped = EscalatingLLMProvider(own=own, inference=inf, depth_threshold=3)
    ctx = _bind(TurnRouteContext(channel="chat", goal="hi", task_kinds=frozenset()))
    ctx.tool_iterations = 3
    out = wrapped.generate(_msgs())
    assert out.content == "deep chain answer"
    assert out.metadata["escalation_trigger"].startswith("tool_chain_depth:")


def test_tool_chain_depth_escalates_via_message_shape_without_context():
    own = _FakeProvider("gemini")
    inf = _FakeProvider("inference", content="shape answer")
    wrapped = EscalatingLLMProvider(own=own, inference=inf, depth_threshold=2)
    bind_turn_route_context(None)
    trail = [
        Message(role=Role.USER, content="go"),
        Message(role=Role.TOOL, content="r1", name="t"),
        Message(role=Role.TOOL, content="r2", name="t"),
    ]
    out = wrapped.generate(trail)
    assert out.content == "shape answer"


def test_inference_failure_falls_back_to_own_pool():
    own = _FakeProvider("gemini", content="own rescue")
    inf = _FakeProvider("inference", error=LLMProviderError("INFERENCE_UNAVAILABLE: down"))
    wrapped = EscalatingLLMProvider(own=own, inference=inf)
    ctx = _bind(
        TurnRouteContext(
            channel="chat", goal="research x", task_kinds=frozenset({"research"})
        )
    )
    out = wrapped.generate(_msgs())
    assert out.content == "own rescue"
    assert out.metadata["llm_route"] == "own"
    assert any("escalation_failed" in e for e in ctx.events[-1])


def test_own_pool_exhaustion_escalates_to_inference():
    own = _FakeProvider(
        "gemini", error=LLMProviderError("All providers failed: CREDENTIAL_EXHAUSTED")
    )
    inf = _FakeProvider("inference", content="inference rescue")
    wrapped = EscalatingLLMProvider(own=own, inference=inf)
    ctx = _bind(TurnRouteContext(channel="chat", goal="hi", task_kinds=frozenset()))
    out = wrapped.generate(_msgs())
    assert out.content == "inference rescue"
    assert out.metadata["llm_route"] == "inference"
    assert out.metadata["escalation_trigger"] == "pool_exhausted"
    assert ctx.events[-1]["trigger"] == "pool_exhausted"


def test_both_down_propagates_original_exhaustion_error():
    own = _FakeProvider(
        "gemini", error=LLMProviderError("All providers failed: CREDENTIAL_EXHAUSTED")
    )
    inf = _FakeProvider("inference", error=LLMProviderError("INFERENCE_UNAVAILABLE: down"))
    wrapped = EscalatingLLMProvider(own=own, inference=inf)
    _bind(TurnRouteContext(channel="chat", goal="hi", task_kinds=frozenset()))
    with pytest.raises(LLMProviderError, match="CREDENTIAL_EXHAUSTED"):
        wrapped.generate(_msgs())


def test_kill_switch_disables_escalation(monkeypatch):
    monkeypatch.setenv("FRIDAY_LLM_ESCALATION", "off")
    own = _FakeProvider("gemini", content="own only")
    inf = _FakeProvider("inference")
    wrapped = EscalatingLLMProvider(own=own, inference=inf)
    _bind(
        TurnRouteContext(
            channel="chat", goal="research x", task_kinds=frozenset({"research"})
        )
    )
    out = wrapped.generate(_msgs())
    assert out.content == "own only"
    assert inf.calls == 0


# ---------------------------------------------------------------------------
# InferenceChatProvider wire contract (monkeypatched httpx — no network)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)[:200]

    def json(self):
        return self._payload


class _FakeClient:
    """Stands in for httpx.Client; records the last request."""

    last_request: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, json=None, headers=None):  # noqa: A002 - httpx kwarg name
        _FakeClient.last_request = {"url": url, "json": json, "headers": headers}
        return _FakeClient.next_response


def _provider(monkeypatch, response: _FakeResponse) -> InferenceChatProvider:
    import httpx

    # escalation.py imports httpx lazily inside generate(); patch the
    # real module's Client for the duration of the test.
    _FakeClient.next_response = response
    monkeypatch.setattr(httpx, "Client", _FakeClient)
    return InferenceChatProvider(
        base_url="http://127.0.0.1:8001", api_key="test-key", temperature=0.3, max_tokens=1024
    )


def test_inference_provider_parses_answer_and_provenance(monkeypatch):
    bind_turn_route_context(None)  # isolate from other tests' bindings
    provider = _provider(
        monkeypatch,
        _FakeResponse(
            200,
            {
                "model": "gemini-3.6-flash",
                "choices": [{"message": {"role": "assistant", "content": "the answer"}}],
                "provenance": {"requested_model": "openai/gpt-oss-120b", "downgrade": True},
            },
        ),
    )
    out = provider.generate(_msgs("explain recursion"))
    assert out.content == "the answer"
    assert out.metadata["provider"] == "inference"
    assert out.metadata["model"] == "gemini-3.6-flash"
    assert out.metadata["requested_model"] == "openai/gpt-oss-120b"
    assert out.metadata["inference_provenance"]["downgrade"] is True
    sent = _FakeClient.last_request
    assert sent["url"].endswith("/v1/chat/completions")
    assert sent["json"]["model"] == "openai/gpt-oss-120b"  # default kind-less request


def test_inference_provider_flattens_tool_results_and_teaches_markup(monkeypatch):
    bind_turn_route_context(None)  # isolate from other tests' bindings
    provider = _provider(
        monkeypatch,
        _FakeResponse(
            200,
            {
                "model": "openai/gpt-oss-120b",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": 'Checking now. <tool name="fleet_dispatch" params=\'{"agent": "stratex"}\'/>',
                        }
                    }
                ],
            },
        ),
    )
    tools = [{"name": "fleet_dispatch", "description": "d", "parameters": {"type": "object"}}]
    messages = [
        Message(role=Role.SYSTEM, content="You are FRIDAY."),
        Message(role=Role.USER, content="ask stratex"),
        Message(
            role=Role.ASSISTANT,
            content="",
            tool_calls=[ToolCall(id="c1", name="web_search", arguments={"q": "x"})],
        ),
        Message(role=Role.TOOL, content="search result body", name="web_search", tool_call_id="c1"),
    ]
    out = provider.generate(messages, tools=tools)
    # Markup tool call recovered into a structured call.
    assert out.tool_calls and out.tool_calls[0].name == "fleet_dispatch"
    assert out.tool_calls[0].arguments == {"agent": "stratex"}
    sent_messages = _FakeClient.last_request["json"]["messages"]
    joined = "\n".join(m["content"] for m in sent_messages)
    assert "[Result from tool 'web_search']: search result body" in joined
    assert "[TOOL USE" in joined  # the model was taught the markup spelling
    assert _FakeClient.last_request["json"]["model"] == "openai/gpt-oss-120b"


def test_inference_provider_503_raises_unavailable(monkeypatch):
    provider = _provider(
        monkeypatch,
        _FakeResponse(503, {"error": {"code": "provider_degraded", "retryable": True}}),
    )
    with pytest.raises(LLMProviderError, match="INFERENCE_UNAVAILABLE"):
        provider.generate(_msgs())


def test_inference_provider_prefers_reasoning_model_for_code(monkeypatch):
    provider = _provider(
        monkeypatch,
        _FakeResponse(
            200,
            {"model": "openai/gpt-oss-120b", "choices": [{"message": {"content": "ok"}}]},
        ),
    )
    ctx = _bind(
        TurnRouteContext(
            channel="chat", goal="write code", task_kinds=frozenset({"code_generation"})
        )
    )
    provider.generate(_msgs("write a sort"))
    assert _FakeClient.last_request["json"]["model"] == "openai/gpt-oss-120b"
    assert ctx is not None  # binding sanity


def test_inference_provider_prefers_gemini_for_synthesis_only(monkeypatch):
    _provider(
        monkeypatch,
        _FakeResponse(
            200,
            {"model": "gemini-3.6-flash", "choices": [{"message": {"content": "ok"}}]},
        ),
    )
    _bind(
        TurnRouteContext(
            channel="chat",
            goal="write a report",
            task_kinds=frozenset({"long_form_synthesis"}),
        )
    )
    provider = InferenceChatProvider(base_url="http://127.0.0.1:8001", api_key="k")
    provider.generate(_msgs("write the report"))
    assert _FakeClient.last_request["json"]["model"] == "gemini-3.8-flash"
