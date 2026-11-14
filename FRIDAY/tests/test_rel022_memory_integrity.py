"""TASK-REL-022 (2026-11-14): memory-answer integrity on the LLM path.

Production failure, verified live through the real console on 2026-11-14
(round 3, 20:20–20:35 IST):

1. "What is my safe word?" matched NONE of the chat recall gate's
   patterns (REL-005 added "what was my"/"what's my"; the present-tense
   "what is my" was missing), so the question fell to the LLM loop.
2. On the REL-010 Groq failover path, the provider's TPM retry stripped
   the tools from the request while the conversation still solicited
   them; gpt-oss-120b called memora_memory anyway and Groq rejected the
   call 400 tool_use_failed (journal 20:23:28 IST — the attempted call
   survives in the error body's failed_generation).
3. agent.py interpolated that raw provider exception into the
   user-visible reply.
4. When the stripped-tools retry instead returned plain text (20:31 IST,
   after the owner had forgotten the fact), the model — denied its memory
   tool and holding no store answer — confabulated a safe word
   ("blue-sky"). Store forensics: no fact record ever contained it; the
   only matching record is the dialogue echo that very turn created.

These tests pin the four fixes: the Groq provider resolves
tool_use_failed honestly (recover the attempted call when tools belonged
to the turn; plain-text nudge retry + sanitised error when they did
not), the agent never shows provider exception text to the user, the
chat recall gate owns "what is my", and the cognitive loop
short-circuits a recall question to the store's honest not-found when
the store has no answer.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# A. Groq provider: tool_use_failed handling
# ---------------------------------------------------------------------------

class _GroqError(Exception):
    """An SDK-shaped provider error (status_code + parsed body)."""

    def __init__(self, message, *, status_code=None, body=None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _tool_use_failed(failed_generation=None):
    error = {
        "message": "Tool choice is none, but model called a tool",
        "type": "invalid_request_error",
        "code": "tool_use_failed",
    }
    if failed_generation is not None:
        error["failed_generation"] = failed_generation
    body = {"error": error}
    return _GroqError(f"Error code: 400 - {body!r}", status_code=400, body=body)


def _tpm_error():
    body = {"error": {"message": "Request too large: tokens per minute (TPM) limit reached"}}
    return _GroqError(f"Error code: 413 - {body!r}", status_code=413, body=body)


def _completion(content="", tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _FakeCompletions:
    def __init__(self, script):
        self._script = list(script)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        action = self._script.pop(0)
        if isinstance(action, Exception):
            raise action
        return action


class _FakeClient:
    def __init__(self, script):
        self.completions = _FakeCompletions(script)
        self.chat = SimpleNamespace(completions=self.completions)


def _groq(script):
    from friday.llm.groq_provider import GroqLLMProvider

    client = _FakeClient(script)
    provider = GroqLLMProvider(api_key="sk-test", client=client)
    return provider, client.completions


def _user(text):
    from friday.core.types import Message, Role

    return Message(role=Role.USER, content=text)


_MEMORA_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "memora_memory",
            "parameters": {"type": "object", "properties": {"question": {"type": "string"}}},
        },
    }
]


def test_groq_tpm_strip_retry_recovers_attempted_tool_call():
    """The production probe-4 shape: TPM strip-retry -> the model calls
    memora_memory anyway -> Groq 400s. The provider must hand the agent
    loop the attempted call, not the 400."""
    failed_generation = '{"name": "memora_memory", "arguments": {"query": "safe word"}}'
    provider, completions = _groq([_tpm_error(), _tool_use_failed(failed_generation)])

    out = provider.generate([_user("What is my safe word?")], tools=_MEMORA_TOOL)

    assert len(completions.calls) == 2
    assert "tools" not in completions.calls[1]  # the TPM retry really stripped them
    assert out.tool_calls, "the attempted tool call must be recovered, not lost"
    assert out.tool_calls[0].name == "memora_memory"
    assert out.tool_calls[0].arguments == {"query": "safe word"}


def test_groq_tool_use_failed_in_text_only_mode_retries_with_plain_text_nudge():
    """Caller disabled tools (tools=None): no recovery into a tool call —
    one retry with an explicit plain-text instruction instead."""
    provider, completions = _groq([_tool_use_failed(), _completion(content="A plain answer.")])

    out = provider.generate([_user("Say hello.")], tools=None)

    assert out.content == "A plain answer."
    assert not out.tool_calls
    assert len(completions.calls) == 2
    retry = completions.calls[1]
    assert "tools" not in retry
    assert "plain text" in retry["messages"][-1]["content"]


def test_groq_tool_use_failed_unrecoverable_raises_sanitised_error():
    """Unparseable failed_generation + a failing nudge retry: the raised
    error names the condition but carries none of the raw provider body
    (which embeds the model's refused generation)."""
    from friday.core.exceptions import LLMProviderError

    raw_generation = '{"name": "python", "arguments": import datetime, zoneinfo\nprint(1)}'
    provider, _ = _groq([_tool_use_failed(raw_generation), _tool_use_failed()])

    with pytest.raises(LLMProviderError) as excinfo:
        provider.generate([_user("What time is it in New York?")], tools=_MEMORA_TOOL)

    text = str(excinfo.value)
    assert "tool_use_failed" in text
    assert "failed_generation" not in text
    assert "Error code: 400" not in text
    assert "import datetime" not in text


def test_groq_other_400_errors_keep_existing_behaviour():
    """A non-tool_use_failed 400 is untouched: same LLMProviderError
    surface as before TASK-REL-022."""
    from friday.core.exceptions import LLMProviderError

    body = {"error": {"message": "invalid request shape", "code": "invalid_request"}}
    err = _GroqError(f"Error code: 400 - {body!r}", status_code=400, body=body)
    provider, _ = _groq([err])

    with pytest.raises(LLMProviderError) as excinfo:
        provider.generate([_user("Hello")], tools=_MEMORA_TOOL)
    assert "Groq API request failed" in str(excinfo.value)


# ---------------------------------------------------------------------------
# B. Agent: provider exception text never reaches the user
# ---------------------------------------------------------------------------

def test_agent_llm_failure_reply_hides_provider_error():
    from friday.agent.agent import FridayAgent
    from friday.core.config import Settings
    from friday.core.exceptions import LLMProviderError
    from friday.llm.openai_provider import OpenAILLMProvider

    raw = (
        "Groq API request failed: Error code: 400 - {'error': {'message': "
        "'Tool choice is none, but model called a tool', 'code': 'tool_use_failed', "
        "'failed_generation': '{\"name\": \"memora_memory\"}'}}"
    )

    class FailingProvider(OpenAILLMProvider):
        def generate(self, messages, tools=None):
            raise LLMProviderError(raw)

    agent = FridayAgent(
        settings=Settings(env="testing"),
        llm_provider=FailingProvider(api_key="<redacted>"),
    )
    response = agent.process_message("Please summarize the project status.")

    assert response.is_done
    assert "I'm having trouble connecting to my intelligence core" in response.content
    assert "tool_use_failed" not in response.content
    assert "Error code: 400" not in response.content
    assert "failed_generation" not in response.content
    assert response.metadata["success"] is False


# ---------------------------------------------------------------------------
# C. Agent recall guard: the store's not-found beats an LLM free-answer
# ---------------------------------------------------------------------------

class _StubProvider:
    def __init__(self, content=""):
        from friday.llm.base import BaseLLMProvider  # noqa: F401  (shape reference)

        self._content = content
        self.calls = 0

    @property
    def provider_name(self):
        return "stub"

    def generate(self, messages, tools=None):
        from friday.core.types import Message, Role

        self.calls += 1
        return Message(role=Role.ASSISTANT, content=self._content)


class _FakeMemora:
    def __init__(self, hits=None, error=None):
        self._hits = hits or []
        self._error = error

    def recall_memories(self, agent, query, limit=10):
        if self._error is not None:
            raise self._error
        return list(self._hits)

    def build_context_block(self, agent, goal):
        return ""

    def build_self_upgrade_context(self, agent, goal, domain=None):
        return ""


def _agent_with_stub(monkeypatch, stub, memora):
    import friday.memory.memora_client as memora_module
    from friday.agent.agent import FridayAgent
    from friday.core.config import Settings
    from friday.llm.base import BaseLLMProvider

    monkeypatch.setattr(memora_module, "memora_client", memora)

    class _Provider(BaseLLMProvider):
        def __init__(self):
            super().__init__(model="stub", temperature=0.0, max_tokens=16)

        @property
        def provider_name(self):
            return "stub"

        def generate(self, messages, tools=None):
            return stub.generate(messages, tools)

    return FridayAgent(settings=Settings(env="testing"), llm_provider=_Provider())


def test_recall_guard_answers_not_found_without_calling_the_llm(monkeypatch):
    stub = _StubProvider(content='Your safe word is **"blue-sky"**.')
    agent = _agent_with_stub(monkeypatch, stub, _FakeMemora(hits=[]))

    response = agent.execute_complex_task("What is my safe word?")

    assert stub.calls == 0, "the LLM must never get to improvise a stored fact"
    assert "don't have anything stored" in response.content
    assert "blue-sky" not in response.content
    assert response.metadata["memory_not_found"] is True


def test_recall_guard_treats_dialogue_echo_as_no_answer(monkeypatch):
    """The production pollution shape: the store's only 'safe word' hit is
    the echo of a previous hallucinated answer. Echoes are not facts."""
    echo = {
        "content_text": (
            "User: What is my safe word? | Assistant: Your safe word is "
            '**"blue‑sky"**.'
        )
    }
    stub = _StubProvider(content="unused")
    agent = _agent_with_stub(monkeypatch, stub, _FakeMemora(hits=[echo]))

    response = agent.execute_complex_task("What is my safe word?")

    assert stub.calls == 0
    assert "don't have anything stored" in response.content


def test_recall_guard_passes_through_when_store_holds_the_fact(monkeypatch):
    fact = {"content_text": 'my safe word is "crimson tiger 8"'}
    stub = _StubProvider(content="stub answer")
    agent = _agent_with_stub(monkeypatch, stub, _FakeMemora(hits=[fact]))

    agent.execute_complex_task("What is my safe word?")

    assert stub.calls >= 1, "with a stored fact present, the normal loop answers"


def test_recall_guard_never_hijacks_a_task_goal(monkeypatch):
    goal = (
        "Please research the market and tell me what is my current exposure "
        "across all of the open portfolio positions today"
    )
    stub = _StubProvider(content="stub answer")
    agent = _agent_with_stub(monkeypatch, stub, _FakeMemora(hits=[]))

    agent.execute_complex_task(goal)

    assert stub.calls >= 1


def test_recall_guard_store_failure_falls_through(monkeypatch):
    stub = _StubProvider(content="stub answer")
    memora = _FakeMemora(error=RuntimeError("store down"))
    agent = _agent_with_stub(monkeypatch, stub, memora)

    response = agent.execute_complex_task("What is my safe word?")

    assert stub.calls >= 1, "an unreachable store is the normal paths' call, not the guard's"
    assert response is not None


# ---------------------------------------------------------------------------
# D. Chat gate: the exact round-3 sequence through _dispatch_command
# ---------------------------------------------------------------------------

def test_chat_gate_owns_what_is_my_roundtrip(tmp_path, monkeypatch):
    from friday.api.server import _dispatch_command
    import friday.memory.memora_client as memora_module
    from friday.memory.memora_client import MemoraClient

    client = MemoraClient(local_db_path=str(tmp_path / "rel022.db"), remote_enabled=False)
    monkeypatch.setattr(memora_module, "memora_client", client)
    try:
        saved = asyncio.run(_dispatch_command('remember that my safe word is "crimson tiger 8"'))
        assert saved["metadata"]["memory_store"] is True

        recalled = asyncio.run(_dispatch_command("What is my safe word?"))
        assert recalled["metadata"].get("memory_recall") is True
        assert "crimson tiger 8" in recalled["reply"]

        forgotten = asyncio.run(_dispatch_command("forget my safe word"))
        assert forgotten["metadata"].get("forget_status") == "deleted", forgotten

        recalled_after = asyncio.run(_dispatch_command("What is my safe word?"))
        assert recalled_after["metadata"].get("memory_recall") is True
        assert "crimson tiger" not in recalled_after["reply"]
        assert "don't have anything stored" in recalled_after["reply"]
    finally:
        client._executor.shutdown(wait=True)
