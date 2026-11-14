"""TASK-REL-027 (2026-11-14): FRIDAY chat reply hygiene.

Three user-visible reply defects in FRIDAY's chat composition layer:

(a) REL-022 residual (b): when a memory recall returned only noise hits —
    above all agent experience records ("[FAILURE WARNING ...]" learnings)
    — the deterministic chat recall gate listed them under the confident
    header "Of course I remember, Boss. Here's what I'm holding onto:" as
    if they were the owner's stored facts. Experience records are the
    agent's own operational learnings, never facts the owner told FRIDAY.
    The gate (and the REL-022 store-authoritative guard, and the
    single-line memory picks in greetings) now treat noise AND experience
    records as unpresentable: only a genuine fact counts as an answer,
    otherwise the reply is the honest not-found.

(b) server.py's device/screen fast-path catch-all returned
    f"Fast-path error: {e}" — the raw exception as the chat reply (the
    defect class REL-022 closed in agent.py, still open here).

(c) agent.py's tool loop ended a failed request with
    f"I encountered persistent errors ...: {last_error}" — the raw tool
    error content (provider bodies, HTTP payloads) as the chat reply.
    The reply now names the failed step and what the failure means; the
    raw text lives in the log and the response metadata only.
"""
from __future__ import annotations

import asyncio

import pytest

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# A1. Hygiene predicates: experience records are identifiable, facts are not
# ---------------------------------------------------------------------------

_FAILURE_HIT = {
    "content_text": (
        "[FAILURE WARNING in 'tool_execution'] Task: deployment checklist export. "
        "Trigger: connection failed after 3 retries. "
        "[LEARNED BEST PRACTICE]: Verify endpoint health before dispatch."
    ),
    "memory_type": "experience",
}

_SUCCESS_HIT = {
    "content_text": (
        "[PROVEN SUCCESS PATTERN in 'tool_execution'] Task: nightly export. "
        "Configuration 'compressed bundle' succeeded. Replicate this strategy."
    ),
    "memory_type": "experience",
}

_FACT_HIT = {
    "content_text": "my deployment checklist lives in the blue notebook",
    "memory_type": "semantic",
}


def test_experience_records_identified_by_content_markers():
    from friday.memory.hygiene import is_experience_hit, is_experience_record

    assert is_experience_record(_FAILURE_HIT["content_text"])
    assert is_experience_record(_SUCCESS_HIT["content_text"])
    assert is_experience_hit(_FAILURE_HIT)
    assert is_experience_hit(_SUCCESS_HIT)
    assert not is_experience_record(_FACT_HIT["content_text"])
    assert not is_experience_hit(_FACT_HIT)


def test_experience_records_identified_by_memory_type_alone():
    """A learning whose text carries no bracket marker is still an
    experience record when the row says so (both stores carry the type)."""
    from friday.memory.hygiene import is_experience_hit

    hit = {"content_text": "deployment checklist weekly outcomes compiled", "memory_type": "experience"}
    assert is_experience_hit(hit)


def test_unpresentable_predicate_covers_noise_and_experience_not_facts():
    from friday.memory.hygiene import is_unpresentable_recall_hit

    assert is_unpresentable_recall_hit(_FAILURE_HIT)
    assert is_unpresentable_recall_hit(
        {"content_text": "RAM usage is at 90% on the host", "memory_type": "episodic"}
    )
    assert not is_unpresentable_recall_hit(_FACT_HIT)


# ---------------------------------------------------------------------------
# A2. Chat gate: noise-only recall answers the honest not-found
# ---------------------------------------------------------------------------

class _GateMemora:
    def __init__(self, hits):
        self._hits = hits

    def recall_memories(self, agent, query, limit=10):
        return list(self._hits)


def _gate_dispatch(monkeypatch, hits, command):
    import friday.memory.memora_client as memora_module
    from friday.api.server import _dispatch_command

    monkeypatch.setattr(memora_module, "memora_client", _GateMemora(hits))
    return asyncio.run(_dispatch_command(command))


def test_gate_recall_with_only_experience_hits_is_honest_not_found(monkeypatch):
    out = _gate_dispatch(
        monkeypatch,
        [_FAILURE_HIT, _SUCCESS_HIT],
        "what do you remember about my deployment checklist?",
    )
    assert out["metadata"].get("memory_recall") is True
    assert "don't have anything stored" in out["reply"]
    assert "Of course I remember" not in out["reply"]
    assert "FAILURE WARNING" not in out["reply"]
    assert "PROVEN SUCCESS PATTERN" not in out["reply"]
    assert out["metadata"].get("remembered_count") == 0


def test_gate_recall_excludes_type_only_experience_hit(monkeypatch):
    hit = {"content_text": "deployment checklist weekly outcomes compiled", "memory_type": "experience"}
    out = _gate_dispatch(
        monkeypatch, [hit], "what do you remember about my deployment checklist?"
    )
    assert "don't have anything stored" in out["reply"]
    assert "weekly outcomes compiled" not in out["reply"]


def test_gate_recall_lists_the_fact_and_not_the_experience_record(monkeypatch):
    out = _gate_dispatch(
        monkeypatch,
        [_FAILURE_HIT, _FACT_HIT],
        "what do you remember about my deployment checklist?",
    )
    assert "blue notebook" in out["reply"]
    assert "FAILURE WARNING" not in out["reply"]
    assert out["metadata"].get("remembered_count") == 1


# ---------------------------------------------------------------------------
# A3. Agent recall guard: experience-only store is a store with no answer
# ---------------------------------------------------------------------------

class _FakeMemora:
    def __init__(self, hits=None):
        self._hits = hits or []

    def recall_memories(self, agent, query, limit=10):
        return list(self._hits)

    def build_context_block(self, agent, goal):
        return ""

    def build_self_upgrade_context(self, agent, goal, domain=None):
        return ""


class _StubProvider:
    def __init__(self, content=""):
        self._content = content
        self.calls = 0

    def generate(self, messages, tools=None):
        from friday.core.types import Message, Role

        self.calls += 1
        return Message(role=Role.ASSISTANT, content=self._content)


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


def test_guard_answers_not_found_when_store_holds_only_experience_records(monkeypatch):
    experience = {
        "content_text": (
            "[FAILURE WARNING in 'tool_execution'] Task: memora_memory. "
            "Trigger: safe word lookup failed. [LEARNED BEST PRACTICE]: retry later."
        ),
        "memory_type": "experience",
    }
    stub = _StubProvider(content='Your safe word is **"blue-sky"**.')
    agent = _agent_with_stub(monkeypatch, stub, _FakeMemora(hits=[experience]))

    response = agent.execute_complex_task("What is my safe word?")

    assert stub.calls == 0, "experience records must not count as a stored answer"
    assert "don't have anything stored" in response.content
    assert "FAILURE WARNING" not in response.content
    assert response.metadata["memory_not_found"] is True


def test_guard_still_passes_through_with_a_genuine_fact(monkeypatch):
    fact = {"content_text": 'my safe word is "crimson tiger 8"', "memory_type": "semantic"}
    stub = _StubProvider(content="stub answer")
    agent = _agent_with_stub(monkeypatch, stub, _FakeMemora(hits=[_FAILURE_HIT, fact]))

    agent.execute_complex_task("What is my safe word?")

    assert stub.calls >= 1, "a genuine fact present: the normal loop answers"


# ---------------------------------------------------------------------------
# B. Fast-path error surface: no raw exception in the reply
# ---------------------------------------------------------------------------

def test_fast_path_failure_reply_is_sanitised(monkeypatch):
    import friday.api.server as server_module
    import friday.devices.windows_friday as windows_module
    from friday.api.server import _dispatch_command

    def _boom(app):
        raise RuntimeError("RAWBOMB-27 win32 COM failure 0x80004005 at C:\\private\\launcher.py")

    # The Windows master controller (its own try/except, log-only) must not
    # claim the command, so dispatch reaches the app-launcher fast-path
    # whose catch-all this test exercises.
    monkeypatch.setattr(
        windows_module.windows_friday,
        "handle_directive",
        lambda raw, authorizer=None: (False, "", {}),
    )
    monkeypatch.setattr(server_module, "launch_desktop_app", _boom)
    out = asyncio.run(_dispatch_command("open calculator"))

    assert out["metadata"].get("error") is True
    assert out["metadata"].get("fast_path_error") == "RuntimeError"
    assert "hit a snag" in out["reply"]
    assert "RAWBOMB-27" not in out["reply"]
    assert "Fast-path error" not in out["reply"]
    assert "0x80004005" not in out["reply"]


# ---------------------------------------------------------------------------
# C. Tool-failure reply: honest outcome, no raw error text
# ---------------------------------------------------------------------------

_RAW_TOOL_ERROR = (
    "Error: fleet dispatch failed: HTTP 401 Unauthorized "
    "{\"detail\": \"token Bearer RAWBOMB-27-secret rejected\", "
    "\"provider\": \"stratex\"} Traceback (most recent call last): "
    "File \"C:\\\\private\\\\fleet.py\", line 91, in dispatch"
)


def test_user_facing_tool_failure_categories_hide_raw_text():
    from friday.agent.agent import user_facing_tool_failure

    cases = [
        (_RAW_TOOL_ERROR, "rejected my access credentials"),
        ("Error: request timed out after 30s", "timed out"),
        ("Error: 403 Forbidden from upstream", "permission was denied"),
        ("Error: connection refused by 10.0.0.121", "could not be reached"),
        ("Error: HTTP 429 too many requests", "rate-limited"),
        ("Error: position 8841 not found", "could not find"),
        ("Circuit breaker open for tool 'send_email'. Execution blocked.", "temporarily paused after repeated failures"),
        ("Error: something entirely unexpected happened", "returned an error"),
    ]
    for raw, meaning in cases:
        reply = user_facing_tool_failure("stratex_portfolio", raw)
        assert "stratex_portfolio" in reply
        assert meaning in reply
        assert "RAWBOMB" not in reply
        assert "Traceback" not in reply
        assert "Bearer" not in reply


def test_agent_tool_failure_final_reply_is_sanitised(monkeypatch):
    from friday.core.types import Message, Role, ToolCall, ToolResult
    from friday.core.types import SafetyLevel

    class _ToolCallingProvider:
        def __init__(self):
            self.calls = 0

        def generate(self, messages, tools=None):
            self.calls += 1
            return Message(
                role=Role.ASSISTANT,
                content="",
                tool_calls=[
                    ToolCall(
                        id="call-27-1",
                        name="stratex_portfolio",
                        arguments={},
                    )
                ],
            )

    stub = _ToolCallingProvider()
    agent = _agent_with_stub(monkeypatch, stub, _FakeMemora())

    def _failing_execute(tc, timeout=None):
        return ToolResult(
            tool_call_id=tc.id,
            name=tc.name,
            content=_RAW_TOOL_ERROR,
            is_error=True,
            safety_level=SafetyLevel.SAFE,
        )

    monkeypatch.setattr(agent, "_execute_single_tool_call", _failing_execute)

    response = agent.execute_complex_task("Check the Stratex portfolio status for me now.")

    assert "stratex_portfolio" in response.content
    assert "rejected my access credentials" in response.content
    assert "RAWBOMB" not in response.content
    assert "Traceback" not in response.content
    assert "Bearer" not in response.content
    assert "401" not in response.content
    # The raw detail is preserved for operators, in metadata only.
    assert response.metadata["tool_error_detail"] == _RAW_TOOL_ERROR
    assert response.metadata["tool_error_tool"] == "stratex_portfolio"
    assert response.metadata["is_successful"] is False
