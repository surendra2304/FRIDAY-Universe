"""TASK-REL-051 — Groq failover tool cap (the 128-tool validation wall).

When the Gemini pool exhausts, FRIDAY's chat fails over to Groq
(``ExhaustionFailoverProvider``) with the production registry's tool
schemas attached (``agent.py``: ``llm.generate(messages,
tools=self.tools.get_schemas())``). The production registry carries
149 schemas (measured 2026-11-17 via the production-registry harness;
FRD-016 measured 145 earlier) — but Groq's OpenAI-compatible API
accepts at most 128 function tools per request, so the failover
request was a guaranteed request-validation HTTP 400. The 400 is
neither TPM-shaped nor ``tool_use_failed``, so no existing recovery
engaged: the error became a generic ``LLMProviderError`` out of the
fallback itself and the turn died. EVERY tool turn that failed over
to Groq was broken.

Fix (``friday/llm/groq_provider.py``): the provider scopes the tool
set deterministically BEFORE the first request
(``scope_tools_for_groq``: conversation-exercised tools first, then
tools named in the latest user message, then the caller's order, up
to ``GROQ_MAX_TOOLS`` = 128; drops are logged with names), and a
too-many-tools 400 that still lands is recognised explicitly and
retried once rescoped to the cap the error names.

The fake completions endpoint below emulates Groq's documented
request validation (tools array capped at a configurable maximum,
defaulting to the documented 128). The behavioural tests fail on
clean main (the turn dies with LLMProviderError) and pass with the
fix; the pass-through test is a no-regression guard.
"""

from types import SimpleNamespace

import pytest

from friday.core.exceptions import LLMProviderError
from friday.core.types import Message, Role, ToolCall
from friday.llm.groq_provider import GroqLLMProvider


def _make_tools(n):
    return [
        {
            "type": "function",
            "function": {
                "name": f"tool_{i:03d}",
                "description": f"Tool number {i}.",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for i in range(n)
    ]


def _tool_count_error(sent, cap):
    body = {
        "error": {
            "message": (
                f"'tools' array length {sent} exceeds the maximum of "
                f"{cap} items"
            ),
            "type": "invalid_request_error",
            "param": "tools",
            "code": "too_many_tools",
        }
    }
    err = Exception(f"Error code: 400 - {body}")
    err.body = body
    err.status_code = 400
    return err


def _tool_call_response(name):
    tc = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name=name, arguments="{}"),
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[tc]))]
    )


class _GroqEmulatingCompletions:
    """Groq-shaped endpoint: rejects tools arrays above ``cap``."""

    def __init__(self, cap=128, answer_tool="tool_007", always_reject=False):
        self.cap = cap
        self.answer_tool = answer_tool
        self.always_reject = always_reject
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        tools = kwargs.get("tools") or []
        if self.always_reject or len(tools) > self.cap:
            raise _tool_count_error(len(tools), self.cap)
        return _tool_call_response(self.answer_tool)


def _make_provider(completions):
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return GroqLLMProvider(api_key="test-key", client=client)


MESSAGES = [Message(role=Role.USER, content="Use a tool to check this for me.")]


def test_oversized_toolset_is_scoped_before_the_first_request():
    """145 tools (the production failover shape) must reach Groq as
    <=128 on request #1 — no burned 400, and the model's tool call
    reaches the agent loop."""
    completions = _GroqEmulatingCompletions(cap=128)
    provider = _make_provider(completions)

    result = provider.generate(MESSAGES, _make_tools(145))

    assert len(completions.calls) == 1, (
        "expected exactly one request: pre-flight scoping should make "
        "the first request valid instead of burning it on a 400"
    )
    sent = completions.calls[0].get("tools") or []
    assert 0 < len(sent) <= 128, f"first request carried {len(sent)} tools"
    assert result.tool_calls, "the model's tool call never reached the agent loop"
    assert result.tool_calls[0].name == "tool_007"


def test_history_referenced_tool_survives_scoping():
    """A tool already exercised in this conversation sits at the END
    of the registry order (index 144); scoping must keep it — dropping
    it would strand the model's own context."""
    completions = _GroqEmulatingCompletions(cap=128, answer_tool="tool_144")
    provider = _make_provider(completions)
    messages = [
        Message(role=Role.USER, content="Check it, then check again."),
        Message(
            role=Role.ASSISTANT,
            content="",
            tool_calls=[ToolCall(id="c1", name="tool_144", arguments={})],
        ),
        Message(role=Role.TOOL, content="result", tool_call_id="c1", name="tool_144"),
        Message(role=Role.USER, content="And once more, please."),
    ]

    result = provider.generate(messages, _make_tools(145))

    sent_names = [
        t["function"]["name"] for t in completions.calls[0].get("tools") or []
    ]
    assert "tool_144" in sent_names, (
        "the conversation's own tool was scoped out — the model would "
        "lose the thread of its in-flight work"
    )
    assert result.tool_calls and result.tool_calls[0].name == "tool_144"


def test_user_mentioned_tool_survives_scoping():
    """A tool named verbatim in the latest user message is kept even
    when it sits beyond the cap in registry order."""
    completions = _GroqEmulatingCompletions(cap=128, answer_tool="tool_140")
    provider = _make_provider(completions)
    messages = [
        Message(role=Role.USER, content="Please run tool_140 on this input.")
    ]

    provider.generate(messages, _make_tools(145))

    sent_names = [
        t["function"]["name"] for t in completions.calls[0].get("tools") or []
    ]
    assert "tool_140" in sent_names


def test_scoping_is_deterministic():
    """Same inputs -> same scoped list, with conversation tools first."""
    from friday.llm.groq_provider import scope_tools_for_groq

    tools = _make_tools(145)
    messages = [
        Message(
            role=Role.ASSISTANT,
            content="",
            tool_calls=[ToolCall(id="c1", name="tool_144", arguments={})],
        ),
        Message(role=Role.USER, content="go"),
    ]

    first = scope_tools_for_groq(tools, messages)
    second = scope_tools_for_groq(tools, messages)

    assert first == second
    assert len(first) == 128
    assert first[0]["function"]["name"] == "tool_144"


def test_at_cap_toolset_passes_through_untouched():
    """No-regression guard: at or under the cap nothing is scoped,
    reordered or copied — the exact caller list goes out."""
    from friday.llm.groq_provider import scope_tools_for_groq

    tools = _make_tools(128)
    assert scope_tools_for_groq(tools, MESSAGES) is tools

    completions = _GroqEmulatingCompletions(cap=128)
    provider = _make_provider(completions)
    provider.generate(MESSAGES, tools)
    assert completions.calls[0].get("tools") == tools


def test_lower_server_cap_is_rescoped_and_retried_once():
    """Defence in depth: if the live cap is below the documented 128,
    the first (128-scoped) request 400s naming the real maximum; the
    provider rescopes to that cap and retries exactly once."""
    completions = _GroqEmulatingCompletions(cap=100)
    provider = _make_provider(completions)

    result = provider.generate(MESSAGES, _make_tools(145))

    assert len(completions.calls) == 2, (
        f"expected scoped-128 then rescoped-100, got "
        f"{len(completions.calls)} requests"
    )
    assert len(completions.calls[0].get("tools") or []) == 128
    assert len(completions.calls[1].get("tools") or []) <= 100
    assert result.tool_calls, "the rescoped retry's tool call was lost"


def test_unshrinkable_tool_count_error_still_raises():
    """A tool-count rejection that no rescope can satisfy (the set is
    already smaller than the named cap) must surface as a sanitised
    LLMProviderError after exactly one request — never a retry loop,
    never a raw provider body leaking upstream as the reply."""
    completions = _GroqEmulatingCompletions(cap=128, always_reject=True)
    provider = _make_provider(completions)

    with pytest.raises(LLMProviderError):
        provider.generate(MESSAGES, _make_tools(10))

    assert len(completions.calls) == 1
