"""TASK-INF-016 — adaptive routing at the FRIDAY escalation point.

Owner decision (2026-11-18): routing CHOOSES per task — complex tasks
(code, reasoning, multi-step, synthesis) go to the quality model;
simple tasks (a math sum, a lookup, a short rewrite) go to the fast
model. Neither provider is a fixed first choice.

Covered here:
* the fixed task battery: classify_task_complexity's level + reason
  and adaptive_escalation_decision's model pick, on the branch;
* the same battery run against pristine main fails at import (the
  classifier does not exist there) — the A/B control;
* the wire path: an escalated simple call requests the fast model and
  carries routing_level/routing_reason in its metadata, the turn
  context and the escalation event; a complex call keeps the REL-044
  quality pick;
* voice still never complexity-escalates (REL-044 rule, unchanged).
"""

from __future__ import annotations

import pytest

from friday.core.exceptions import LLMProviderError
from friday.core.types import Message, Role
from friday.llm.base import BaseLLMProvider
from friday.llm.escalation import (
    FAST_ESCALATION_MODEL,
    MODEL_PROFILES,
    EscalatingLLMProvider,
    InferenceChatProvider,
    TurnRouteContext,
    adaptive_escalation_decision,
    bind_turn_route_context,
    classify_task_complexity,
)

FAST = "gemini-3.5-flash-lite"
QUALITY_REASONING = "openai/gpt-oss-120b"
QUALITY_SYNTHESIS = "gemini-3.8-flash"

# (goal, expected level, expected reason prefix, expected model)
BATTERY = [
    ("What is 347 + 589?", "simple", "math_expression", FAST),
    ("Calculate 15% of 2400", "simple", "math_expression", FAST),
    ("What is 12 * 8?", "simple", "math_expression", FAST),
    ("What is the capital of France?", "simple", "short_lookup", FAST),
    ("How many days are there in a leap year?", "simple", "short_lookup", FAST),
    ("Translate 'good morning' to Telugu", "simple", "short_lookup", FAST),
    (
        "Rewrite this sentence to be shorter: The meeting has been postponed until further notice.",
        "simple",
        "short_rewrite",
        FAST,
    ),
    (
        "Write a Python function that merges two sorted lists",
        "complex",
        "complex_kind:code_generation",
        QUALITY_REASONING,
    ),
    (
        "Research the latest RBI rate decision and summarise it",
        "complex",
        "complex_kind:research",
        QUALITY_REASONING,
    ),
    (
        "Write a detailed report on the fleet's health this week",
        "complex",
        "complex_kind:long_form_synthesis",
        QUALITY_SYNTHESIS,
    ),
    (
        "First check the fleet status, then restart the failing service, and finally verify it is healthy",
        "complex",
        "complex_kind:multi_step",
        QUALITY_REASONING,
    ),
    (
        "Prove that the square root of 2 is irrational, step by step",
        "complex",
        "reasoning_marker",
        QUALITY_REASONING,
    ),
]


@pytest.mark.parametrize("goal,level,reason,model", BATTERY)
def test_battery_classifier(goal, level, reason, model):
    got_level, got_reason, _kinds = classify_task_complexity(goal)
    assert got_level == level
    assert got_reason.startswith(reason)


@pytest.mark.parametrize("goal,level,reason,model", BATTERY)
def test_battery_decision_model(goal, level, reason, model):
    bind_turn_route_context(None)
    decision = adaptive_escalation_decision(None, [Message(role=Role.USER, content=goal)])
    assert decision.level == level
    assert decision.reason.startswith(reason)
    assert decision.model == model


def test_battery_long_input_is_complex():
    goal = "Summarise the following document. " + (
        "The fleet ran normally and nothing unusual happened today. " * 30
    )
    level, reason, _ = classify_task_complexity(goal)
    assert level == "complex"
    assert reason == "long_input"


def test_tool_chain_depth_is_complex_even_for_a_short_goal():
    level, reason, _ = classify_task_complexity("hi", tool_iterations=3)
    assert level == "complex"
    assert reason.startswith("tool_chain_depth")


def test_decision_is_deterministic():
    msgs = [Message(role=Role.USER, content="What is 347 + 589?")]
    bind_turn_route_context(None)
    first = adaptive_escalation_decision(None, msgs)
    second = adaptive_escalation_decision(None, msgs)
    assert first == second


def test_every_decision_model_has_a_profile_tier():
    for goal, _level, _reason, _model in BATTERY:
        bind_turn_route_context(None)
        decision = adaptive_escalation_decision(None, [Message(role=Role.USER, content=goal)])
        assert MODEL_PROFILES[decision.model]["tier"] in ("fast", "quality", "standard")
    assert MODEL_PROFILES[FAST_ESCALATION_MODEL]["tier"] == "fast"
    assert MODEL_PROFILES[QUALITY_REASONING]["tier"] == "quality"
    assert MODEL_PROFILES[QUALITY_SYNTHESIS]["tier"] == "quality"


def test_decision_records_level_and_reason_on_context():
    ctx = bind_turn_route_context(
        TurnRouteContext(channel="chat", goal="What is 347 + 589?", task_kinds=frozenset())
    )
    decision = adaptive_escalation_decision(ctx)
    assert decision.level == "simple"
    assert ctx.complexity_level == "simple"
    assert ctx.complexity_reason.startswith("math_expression")


# ---------------------------------------------------------------------------
# Wire path (monkeypatched httpx, the REL-044 test pattern)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)[:200]

    def json(self):
        return self._payload


class _FakeClient:
    last_request: dict = {}
    next_response: _FakeResponse | None = None

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, json=None, headers=None):  # noqa: A002 - httpx kwarg name
        _FakeClient.last_request = {"url": url, "json": json, "headers": headers}
        return _FakeClient.next_response


def _inference_provider(monkeypatch) -> InferenceChatProvider:
    import httpx

    _FakeClient.next_response = _FakeResponse(
        200,
        {"model": "served-model", "choices": [{"message": {"role": "assistant", "content": "ok"}}]},
    )
    monkeypatch.setattr(httpx, "Client", _FakeClient)
    return InferenceChatProvider(
        base_url="http://127.0.0.1:8001", api_key="<redacted>", temperature=0.3, max_tokens=1024
    )


def test_simple_call_requests_fast_model_with_audit_metadata(monkeypatch):
    bind_turn_route_context(
        TurnRouteContext(channel="chat", goal="What is 347 + 589?", task_kinds=frozenset())
    )
    provider = _inference_provider(monkeypatch)
    out = provider.generate([Message(role=Role.USER, content="What is 347 + 589?")])
    assert _FakeClient.last_request["json"]["model"] == FAST
    assert out.metadata["routing_level"] == "simple"
    assert out.metadata["routing_reason"].startswith("math_expression")
    assert out.metadata["routing_tier"] == "fast"


def test_complex_call_keeps_quality_model_with_audit_metadata(monkeypatch):
    bind_turn_route_context(
        TurnRouteContext(
            channel="chat",
            goal="Write a Python function that merges two sorted lists",
            task_kinds=frozenset({"code_generation"}),
        )
    )
    provider = _inference_provider(monkeypatch)
    out = provider.generate([Message(role=Role.USER, content="write a sort")])
    assert _FakeClient.last_request["json"]["model"] == QUALITY_REASONING
    assert out.metadata["routing_level"] == "complex"
    assert out.metadata["routing_tier"] == "quality"


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


def test_simple_task_escalated_by_exhaustion_uses_fast_model(monkeypatch):
    own = _FakeProvider(
        "gemini", error=LLMProviderError("All providers failed: CREDENTIAL_EXHAUSTED")
    )
    inference = _inference_provider(monkeypatch)
    wrapped = EscalatingLLMProvider(own=own, inference=inference)
    ctx = bind_turn_route_context(
        TurnRouteContext(channel="chat", goal="What is 347 + 589?", task_kinds=frozenset())
    )
    out = wrapped.generate([Message(role=Role.USER, content="What is 347 + 589?")])
    assert out.content == "ok"
    assert _FakeClient.last_request["json"]["model"] == FAST
    assert out.metadata["escalation_trigger"] == "pool_exhausted"
    assert ctx.events[-1]["routing_level"] == "simple"
    assert ctx.events[-1]["routing_reason"].startswith("math_expression")


def test_voice_turn_still_never_complexity_escalates():
    own = _FakeProvider("gemini", content="voice answer")
    inf = _FakeProvider("inference")
    wrapped = EscalatingLLMProvider(own=own, inference=inf)
    bind_turn_route_context(
        TurnRouteContext(
            channel="voice",
            goal="Ask Stratex for the balance and then research the market",
            task_kinds=frozenset({"delegation", "research"}),
        )
    )
    out = wrapped.generate([Message(role=Role.USER, content="hello")])
    assert out.content == "voice answer"
    assert inf.calls == 0
