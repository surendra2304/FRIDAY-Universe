"""TASK-REL-031 — Groq failover tool discipline (the TASK-REL-010 residual).

When the Gemini pool exhausts, FRIDAY's chat fails over to Groq
(``ExhaustionFailoverProvider``). REL-010's live proof recorded the
quality gap: failover-mode answers degraded — "time in Tokyo" was
answered with a hedged text guess and no clock tool was ever called.

Root cause (in ``GroqLLMProvider._generate_with_key_and_model``): on a
TPM / request-too-large failure the provider's ONE retry stripped the
tools entirely and compacted the conversation, so the model could only
answer from text. If it complied, the user got a guess dressed as an
answer; if it still tried to call a tool, REL-022's recovery had to
rescue the call from Groq's 400 body.

Fix: the TPM retry ladder now compacts the conversation but KEEPS the
tools attached first. Only if the compacted request still exceeds the
limit does it fall back to a text-only retry — and that retry carries
an explicit instruction not to guess at facts a tool would check, so
the degraded answer is honest ("I can't check that right now") instead
of a fabricated one.

These tests fail on clean main and pass with the fix (the
tool_use_failed recovery test is a no-regression guard that passes on
both).
"""

import json
from types import SimpleNamespace

from friday.core.types import Message, Role
from friday.llm.groq_provider import GroqLLMProvider

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current time in a timezone.",
            "parameters": {
                "type": "object",
                "properties": {"timezone": {"type": "string"}},
                "required": ["timezone"],
            },
        },
    }
]
MESSAGES = [Message(role=Role.USER, content="What time is it in Tokyo right now?")]


class _ScriptedCompletions:
    """Fake OpenAI-SDK completions endpoint: plays a script of outcomes."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self._script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _make_provider(script):
    completions = _ScriptedCompletions(script)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = GroqLLMProvider(api_key="test-key", client=client)
    return provider, completions


def _tpm_error():
    return Exception(
        "Error code: 413 - {'error': {'message': 'Request too large: "
        "tokens per minute (TPM) limit exceeded'}}"
    )


def _tool_call_response():
    tc = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="get_current_time", arguments='{"timezone": "Asia/Tokyo"}'
        ),
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[tc]))]
    )


def _text_response(text="It is probably around 6 PM in Tokyo."):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=None))
        ]
    )


def test_tpm_retry_keeps_tools_attached():
    """First TPM retry must compact, not disarm: tools stay on the request."""
    provider, completions = _make_provider([_tpm_error(), _tool_call_response()])

    result = provider.generate(MESSAGES, TOOLS)

    assert len(completions.calls) == 2
    retry_kwargs = completions.calls[1]
    assert retry_kwargs.get("tools"), (
        "TPM retry stripped the tools — failover mode cannot call the clock "
        "tool and will guess instead (the REL-010 residual)"
    )
    assert result.tool_calls, "expected the model's tool call to reach the agent loop"
    assert result.tool_calls[0].name == "get_current_time"
    assert result.tool_calls[0].arguments == {"timezone": "Asia/Tokyo"}


def test_tpm_last_resort_strips_tools_but_forbids_guessing():
    """If even the compacted request is too large, the text-only fallback
    must carry the honesty instruction: no invented tool-shaped facts."""
    provider, completions = _make_provider(
        [_tpm_error(), _tpm_error(), _text_response("I can't check that right now.")]
    )

    result = provider.generate(MESSAGES, TOOLS)

    assert len(completions.calls) == 3, (
        f"expected full-then-compact-with-tools-then-text-only ladder, "
        f"got {len(completions.calls)} calls"
    )
    assert completions.calls[1].get("tools"), "second attempt should keep tools"
    last = completions.calls[2]
    assert not last.get("tools"), "last-resort attempt should be text-only"
    joined = " ".join(
        str(m.get("content") or "") for m in last["messages"]
    ).lower()
    assert "do not guess" in joined or "not guess" in joined, (
        "text-only fallback carries no anti-guessing instruction — the model "
        "is free to invent the time (the REL-010 hedged-answer failure)"
    )
    assert result.content == "I can't check that right now."


def test_tool_use_failed_recovery_still_works_after_compact_retry():
    """No-regression guard (passes on clean main too): a tool call Groq
    refuses with tool_use_failed is still recovered as a real ToolCall."""
    body = {
        "error": {
            "code": "tool_use_failed",
            "failed_generation": json.dumps(
                {"name": "get_current_time", "arguments": {"timezone": "Asia/Tokyo"}}
            ),
        }
    }
    err = Exception("Error code: 400 - tool_use_failed")
    err.body = body
    provider, completions = _make_provider([_tpm_error(), err])

    result = provider.generate(MESSAGES, TOOLS)

    assert result.tool_calls, "REL-022 recovery regressed: no ToolCall returned"
    assert result.tool_calls[0].name == "get_current_time"
    assert result.tool_calls[0].arguments == {"timezone": "Asia/Tokyo"}
