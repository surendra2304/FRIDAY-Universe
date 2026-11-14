"""
tests/test_intent_classifier_tier.py — TASK-INTENT-001 regression coverage.

Contract locked in:
1. Fail-open: provider timeout/error/malformed output => classify() returns
   None and the caller must proceed identically.
2. Weak-signal gate: the classifier fires only when 0 or >=2 keyword tables
   matched; a single deterministic table hit never calls the provider.
3. Upgrade-only confidence fold: a strong verdict may raise understanding
   confidence (rescuing the 0.3 ambiguous-pattern score), never lower it.
4. Steering: a highly confident verdict with tools adds the routing hint to
   the EXECUTION goal only (memory keeps the clean input).
5. Parsing: JSON extraction, tool-name sanitization, confidence bounds.
6. Cache: identical messages hit the cache (provider called once).
"""

import concurrent.futures
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from friday.core.types import Message, Role
from friday.routing.capability_router import CapabilityRouter
from friday.routing.intent_classifier import (
    CLARITY_CONFIDENCE,
    STEER_CONFIDENCE,
    IntentClassification,
    LLMIntentClassifier,
)


class FakeProvider:
    """Labelled test double: scripted replies, records calls."""

    def __init__(self, reply: str | None, fail: bool = False, slow: bool = False):
        self.reply = reply
        self.fail = fail
        self.slow = slow
        self.calls: list[list[Message]] = []

    def generate(self, messages: list[Message], tools=None) -> Message:
        self.calls.append(messages)
        if self.fail:
            raise RuntimeError("provider down (test double)")
        if self.slow:
            raise concurrent.futures.TimeoutError("simulated hang")
        return Message(role=Role.ASSISTANT, content=self.reply or "")


def _classifier(reply: str | None, timeout: float = 2.5, **kwargs) -> LLMIntentClassifier:
    settings = SimpleNamespace(intent_classify_timeout=timeout, intent_classify_enabled=True)
    return LLMIntentClassifier(settings=settings, provider=FakeProvider(reply, **kwargs))


_VALID_REPLY = (
    '{"intent": "research", "capability": "intelx_research", '
    '"required_tools": ["intelx_research"], "confidence": 0.9, "operand": "fusion energy"}'
)


# ---------------------------------------------------------------------------
# 1. Fail-open contract
# ---------------------------------------------------------------------------


def test_provider_failure_returns_none():
    c = _classifier(_VALID_REPLY, fail=True)
    assert c.classify("research quantum fusion energy papers") is None


def test_provider_timeout_returns_none():
    c = _classifier(_VALID_REPLY, slow=True, timeout=1.5)
    assert c.classify("research quantum fusion energy papers") is None


def test_malformed_reply_returns_none():
    for bad in (None, "", "I am not json", '{"intent": ""}', '{"confidence": 5.0, "intent": "x"}'):
        assert _classifier(bad).classify("hello there") is None


def test_json_in_prose_is_extracted():
    c = _classifier(f'Sure! {_VALID_REPLY} hope that helps.')
    result = c.classify("research quantum fusion energy")
    assert result is not None
    assert result.intent == "research"
    assert result.required_tools == ["intelx_research"]


def test_plausible_tool_names_only():
    reply = (
        '{"intent": "x", "required_tools": ["intelx_research", "Bad Name!", '
        '"rm -rf", "a", "dup", "dup"], "confidence": 0.8}'
    )
    result = _classifier(reply).classify("do the thing")
    assert result is not None
    assert result.required_tools == ["intelx_research", "dup"]


# ---------------------------------------------------------------------------
# 2. Weak-signal gate
# ---------------------------------------------------------------------------


def test_signal_weak_when_no_table_matches():
    router = CapabilityRouter()
    assert LLMIntentClassifier.signal_is_weak("explain the theory of general relativity to me", router) is True


def test_signal_weak_when_two_tables_match():
    # "write a script" matches BOTH SCRIPT_KEYWORDS and CODE_TASK_KEYWORDS
    # (documented overlap) — ambiguous by construction.
    router = CapabilityRouter()
    assert LLMIntentClassifier.signal_is_weak("write a script to bulk-rename my photos", router) is True


def test_strong_signal_never_calls_provider():
    router = CapabilityRouter()
    # Single unambiguous table hit: "research X" matches RESEARCH only.
    assert LLMIntentClassifier.signal_is_weak("research the latest fusion energy papers", router) is False


# ---------------------------------------------------------------------------
# 3+4. Confidence fold + steering (through the real process_message path)
# ---------------------------------------------------------------------------


def _agent_with_classifier(
    monkeypatch, tmp_path, reply: str | None, det_confidence: float | None = None,
    **provider_kwargs,
):
    """Build a real agent with the classifier singleton injected.

    ``det_confidence`` optionally replaces the real cognitive engine with a
    stub returning a REAL CognitiveDecision carrying that understanding
    confidence. The real engine always reports 1.0 when it stays in PLAN
    phase (low scores only co-occur with CLARIFY, which early-returns before
    execution), so without this the upgrade-only fold is unreachable through
    process_message and the fold contract could not be exercised end-to-end.
    """
    import friday.routing.intent_classifier as ic_module
    from friday.agent.agent import FridayAgent

    classifier = _classifier(reply, **provider_kwargs)
    monkeypatch.setattr(ic_module, "_singleton", classifier)

    agent = FridayAgent.__new__(FridayAgent)  # skip __init__ heavy wiring
    # Minimal attribute surface for process_message's deterministic ladders:
    from friday.agent.cognitive import (
        CognitiveDecision,
        CognitivePhase,
        CognitiveIntelligenceEngine,
        ConfidenceAssessment,
    )
    from friday.routing.capability_router import CapabilityRouter
    from friday.agent.state import ReasoningStateMachine
    from friday.memory.sqlite import SQLiteConversationMemory

    if det_confidence is None:
        agent.cognitive_engine = CognitiveIntelligenceEngine()
    else:
        decision = CognitiveDecision(
            current_phase=CognitivePhase.PLAN,
            confidence=ConfidenceAssessment(
                understanding_confidence=det_confidence,
                reasons=["deterministic stub decision"],
            ),
        )
        agent.cognitive_engine = SimpleNamespace(evaluate_request=lambda user_input: decision)
    agent.capability_router = CapabilityRouter()
    agent.state_machine = ReasoningStateMachine()
    memory_backend = SQLiteConversationMemory(db_path=str(tmp_path / "intent_memory.db"))
    agent.memory = memory_backend
    agent.task_context = None
    agent.tools = {}
    # Attribute surface the deterministic ladders touch before the cognitive
    # hook (fast paths read settings; tool-loop callbacks are absent).
    agent.settings = SimpleNamespace(user_name="Surendra")
    agent.notifications = None
    agent.tool_callback = None
    # Final response metadata reads the provider identity off self.llm.
    agent.llm = SimpleNamespace(provider_name="test-provider", model="test-model")
    monkeypatch.setattr(
        agent, "execute_complex_task", lambda goal, context=None: SimpleNamespace(
            content="done", tool_calls=None, tool_results=None,
            metadata={"is_successful": True}, is_done=True,
        ), raising=False,
    )
    return agent


def _run_process_message(agent, text: str):
    # process_message lives on the mixin; call it through the class to get the
    # real ladder without touching server-side fast paths.
    from friday.agent.mixins.cognitive import CognitiveMixin

    return CognitiveMixin.process_message(agent, text)


# Falls through EVERY deterministic fast path (greeting/conversational/
# pipeline/task-status/delegation/security/forecast/batch3/diagnostics/fleet/
# research/portfolio/desktop — verified 2026-11-13) and matches ZERO intent
# keyword tables, so signal_is_weak is True and the hook actually fires. The
# original "look into ..." input is eaten by _research_dispatch_fast_path
# (its regex includes "look into") before the hook is ever reached.
_HOOK_INPUT = "what is the significance of the rosetta stone"


def test_confident_classification_steers_goal_and_folds_confidence(monkeypatch, tmp_path):
    agent = _agent_with_classifier(monkeypatch, tmp_path, _VALID_REPLY, det_confidence=0.3)
    captured: dict = {}

    def fake_execute(goal, context=None):
        captured["goal"] = goal
        captured["context"] = context
        return SimpleNamespace(content="done", tool_calls=None, tool_results=None,
                               metadata={"is_successful": True}, is_done=True)

    monkeypatch.setattr(agent, "execute_complex_task", fake_execute, raising=False)
    resp = _run_process_message(agent, _HOOK_INPUT)
    assert resp.is_done
    # Steering: the execution goal carries the routing hint...
    assert "prefer the tool(s) intelx_research" in captured["goal"]
    assert captured["goal"].startswith(_HOOK_INPUT)  # hint appended, input preserved
    assert captured["context"]["intent_classification"]["intent"] == "research"
    # ...and the fold: the 0.9 verdict upgrades the deterministic 0.3 score.
    confidence = resp.metadata["confidence"]
    assert confidence["understanding_confidence"] == 0.9
    assert any("LLM intent tier" in reason for reason in confidence["reasons"])


def test_weak_classifier_verdict_changes_nothing(monkeypatch, tmp_path):
    low_reply = (
        '{"intent": "unknown_thing", "required_tools": [], "confidence": 0.2}'
    )
    agent = _agent_with_classifier(monkeypatch, tmp_path, low_reply, det_confidence=0.3)
    captured: dict = {}

    def fake_execute(goal, context=None):
        captured["goal"] = goal
        captured["context"] = context
        return SimpleNamespace(content="done", tool_calls=None, tool_results=None,
                               metadata={"is_successful": True}, is_done=True)

    monkeypatch.setattr(agent, "execute_complex_task", fake_execute, raising=False)
    resp = _run_process_message(agent, _HOOK_INPUT)
    assert resp.is_done
    # A weak (0.2) verdict changes no behaviour: no steering hint, and the
    # upgrade-only fold never moves the deterministic 0.3 score.
    assert "prefer the tool(s)" not in captured["goal"]
    assert resp.metadata["confidence"]["understanding_confidence"] == 0.3
    # The verdict IS recorded as context telemetry (proof the hook ran), but
    # with its weak confidence and empty tool list it steers nothing.
    verdict = captured["context"]["intent_classification"]
    assert verdict["confidence"] == 0.2
    assert verdict["required_tools"] == []


def test_classifier_failure_leaves_pipeline_unchanged(monkeypatch, tmp_path):
    agent = _agent_with_classifier(monkeypatch, tmp_path, _VALID_REPLY, fail=True, det_confidence=0.3)
    captured: dict = {}

    def fake_execute(goal, context=None):
        captured["goal"] = goal
        captured["context"] = context
        return SimpleNamespace(content="done", tool_calls=None, tool_results=None,
                               metadata={"is_successful": True}, is_done=True)

    monkeypatch.setattr(agent, "execute_complex_task", fake_execute, raising=False)
    resp = _run_process_message(agent, _HOOK_INPUT)
    assert resp.is_done
    # Fail-open: no steering, no telemetry, no confidence change.
    assert "prefer the tool(s)" not in captured["goal"]
    assert "intent_classification" not in (captured["context"] or {})
    assert resp.metadata["confidence"]["understanding_confidence"] == 0.3


# ---------------------------------------------------------------------------
# 5+6. Constants and cache
# ---------------------------------------------------------------------------


def test_threshold_constants_are_ordered():
    assert CLARITY_CONFIDENCE >= 0.6
    assert STEER_CONFIDENCE > CLARITY_CONFIDENCE


def test_cache_hits_provider_once():
    provider = FakeProvider(_VALID_REPLY)
    settings = SimpleNamespace(intent_classify_timeout=2.5, intent_classify_enabled=True)
    classifier = LLMIntentClassifier(settings=settings, provider=provider)
    msg = "Research how solid state batteries work"
    first = classifier.classify(msg)
    second = classifier.classify(msg)
    assert first is not None and second is not None
    assert len(provider.calls) == 1
    classifier.reset_cache()
    classifier.classify(msg)
    assert len(provider.calls) == 2


def test_reset_intent_classifier_clears_singleton(monkeypatch):
    import friday.routing.intent_classifier as ic_module

    monkeypatch.setattr(ic_module, "_singleton", None)
    # conftest defaults FRIDAY_INTENT_CLASSIFIER=off (suite hermeticity);
    # clear it here so lazy CREATION is exercised, then re-arm the switch.
    monkeypatch.delenv("FRIDAY_INTENT_CLASSIFIER", raising=False)
    first = ic_module.get_intent_classifier()
    assert first is not None
    ic_module.reset_intent_classifier()
    assert ic_module._singleton is None
    monkeypatch.setenv("FRIDAY_INTENT_CLASSIFIER", "off")
    assert ic_module.get_intent_classifier() is None
    # The kill switch vetoes CREATION, never injected test doubles
    # (hermetic suites inject before the env is read).
    injected = _classifier(_VALID_REPLY)
    monkeypatch.setattr(ic_module, "_singleton", injected)
    assert ic_module.get_intent_classifier() is injected
