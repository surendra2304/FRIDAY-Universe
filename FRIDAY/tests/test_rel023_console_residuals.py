"""TASK-REL-023 regression tests: console round-3 residuals.

Round 3 (2026-11-14, human-style browser test) evidence pinned here:

* (a) History restore: a 15-exchange session restored as "LAST SESSION ·
  24 MESSAGES" — TASK-REL-012 fixed the render slice, but the history
  FETCH stayed at 12 entries. The fetch window must cover the render
  window: RESTORE_LIMIT (entries) x 2 >= MAX_RENDERED (bubbles).
* (b) Forge outcomes: the palindrome task's terminal failure landed at
  ~150s, after the chat turn had been abandoned (UI ceiling 75s, server
  budget 120s, Forge dispatch budget 210s). Budgets are now aligned
  (UI CHAT_TIMEOUT_MS and the server default both 300s), and Forge's
  delegate result carries the primary source file's content so the
  reply can SHOW the code — on success and on failure.
* (d) Latency: a one-fact question paid the full cognitive loop
  (measured 12.4s idle, 50-60s under load). The general-knowledge lane
  answers it with one no-tools provider call and falls through to the
  loop on any doubt.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parent.parent.parent
_CORE_SRC = _REPO / "FRIDAY" / "apps" / "core" / "src"
if str(_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(_CORE_SRC))

import friday_core.task_records as tr_module
from friday_core.task_records import TaskRecordStore

from friday.api import server


# --------------------------------------------------------------------- (a)

_CHATPANEL = _REPO / "FRIDAY" / "ui" / "components" / "ChatPanel.tsx"


def _ui_const(name: str) -> int:
    text = _CHATPANEL.read_text(encoding="utf-8")
    m = re.search(rf"const {name} = ([\d_]+);", text)
    assert m, f"{name} not found in ChatPanel.tsx"
    return int(m.group(1).replace("_", ""))


def test_history_fetch_window_covers_render_window():
    restore = _ui_const("RESTORE_LIMIT")
    rendered = _ui_const("MAX_RENDERED")
    assert restore * 2 >= rendered, (
        "history fetch (entries) must cover the render window (bubbles); "
        "round 3 restored 12 exchanges of a 15-exchange session"
    )
    assert restore >= 20


def test_ui_chat_timeout_aligned_with_server_budget():
    assert _ui_const("CHAT_TIMEOUT_MS") >= 300_000
    text = _CHATPANEL.read_text(encoding="utf-8")
    assert "`No answer within ${Math.round(CHAT_TIMEOUT_MS / 1000)} seconds" in text, (
        "the timeout copy must derive from CHAT_TIMEOUT_MS, not a stale literal"
    )


# --------------------------------------------------------------------- (b)


@pytest.fixture()
def fresh_store(monkeypatch):
    store = TaskRecordStore()
    monkeypatch.setattr(tr_module, "get_shared_task_records", lambda: store)
    return store


class _FakeResult:
    def __init__(self, status: str, result: dict[str, Any] | None = None,
                 error: str | None = None, summary: str = "", task_id: str = "task_fake1"):
        self.status = status
        self.result = result or {}
        self.error = error
        self.summary = summary
        self.task_id = task_id
        self.execution_time_ms = 1200


class _FakeFleetClient:
    def __init__(self, result):
        self._result = result

    async def dispatch_task(self, envelope):
        return self._result


_SOURCE = {"path": "/ws/project/main.py", "name": "main.py",
           "content": "def is_palindrome(s):\n    return s == s[::-1]\n", "truncated": False}
_MANIFEST_OK = {"stages": [{"check_name": "tests", "category": "test", "status": "passed", "passed": True, "exit_code": 0}]}


def test_forge_success_reply_shows_the_code(fresh_store):
    from friday.tools.builtin.forge_code_task import ForgeCodeTool

    ok = _FakeResult("SUCCESS", result={
        "status": "SUCCESS",
        "result": {"artifacts": ["/ws/project/main.py"], "primary_source": _SOURCE,
                   "verification_manifest": _MANIFEST_OK},
        "verification_manifest": _MANIFEST_OK,
    }, summary="Forge successfully synthesized and verified goal", task_id="task_show_code")
    res = ForgeCodeTool(fleet_client=_FakeFleetClient(ok)).execute(goal="write a palindrome checker and show me the code")
    assert not res.is_error
    assert "is_palindrome" in res.content, "the reply must contain the produced code"
    assert "```py" in res.content


def test_forge_failure_reply_shows_code_and_honest_failure(fresh_store):
    from friday.tools.builtin.forge_code_task import ForgeCodeTool

    failed = _FakeResult("ERROR", result={
        "status": "PARTIAL_FAILURE",
        "result": {"artifacts": ["/ws/project/main.py"], "primary_source": _SOURCE,
                   "state": "FAILED", "manifest": {"failure_summary": "tests missing"}},
        "summary": "Code generation finished, but verification failed: no test files discovered",
    }, error="Verification gate 'Automated Test Suite & Verification Gate' returned status=failed",
        task_id="task_gate_fail")
    res = ForgeCodeTool(fleet_client=_FakeFleetClient(failed)).execute(goal="write a palindrome checker and show me the code")
    assert res.is_error, "a failed build must still be reported as a failure"
    assert "could not complete" in res.content
    assert "is_palindrome" in res.content, "the produced code must accompany the honest failure"
    assert "nothing was fabricated" in res.content


# --------------------------------------------------------------------- (c)

def test_fleet_probe_budgets_aligned_with_measured_latency():
    from friday.ecosystem import fleet_client

    assert fleet_client.FLEET_PROBE_DEADLINE_SECONDS == 20.0
    src = (Path(fleet_client.__file__)).read_text(encoding="utf-8")
    # Round-3 forensics: peers answer /health in <=0.25s by direct curl,
    # but FRIDAY's in-process probes took 3.6s/5.0s under load — the old
    # 3.5s/5.0s budgets reported healthy agents UNREACHABLE.
    assert 'self.cortex_url}{health_path}", headers=headers, timeout=8.0' in src
    assert 'self.sentinel_url}{health_path}", headers=headers, timeout=10.0' in src
    assert 'self.forge_url}{health_path}", headers=headers, timeout=10.0' in src
    assert 'self.futuris_local_url}/health", timeout=2.5' in src
    assert "timeout=3.5" not in src


# --------------------------------------------------------------------- (d)

@pytest.mark.parametrize("question", [
    "what is the capital of australia?",
    "who wrote romeo and juliet?",
    "what is the tallest mountain on earth",
    "when was the eiffel tower built?",
    "how many continents are there?",
    "why is the sky blue?",
    "which planet is known as the red planet?",
])
def test_lane_claims_simple_factual_questions(question):
    assert server._looks_like_simple_factual_question(question)


@pytest.mark.parametrize("question", [
    "what is my safe word?",                      # owner's own information
    "what time is it in tokyo?",                   # needs the clock tool
    "what is the current price of gold?",          # live data
    "what is the latest news on the election?",    # current events
    "what is the status of my portfolio?",         # fleet data + personal
    "how is my stratex portfolio doing?",          # delegation target
    "tell me a joke, and what time is it in tokyo?",  # compound
    "what is the capital of france, and what time is it there?",  # compound
    "what is 17 plus 25?",                         # arithmetic tool owns it
    "what should i name my dog?",                  # advice, not a fact
    "remember that my safe word is crimson tiger 8",  # memory action
    "write a python function that checks palindromes",  # build action
    "who are you?",                                # persona question
    "",                                            # empty
])
def test_lane_rejects_anything_needing_tools_or_actions(question):
    assert not server._looks_like_simple_factual_question(question)


class _FakeLLM:
    provider_name = "gemini"
    model = "fake-model"

    def __init__(self, content: str = "", tool_calls=None, raises: bool = False):
        self._content = content
        self._tool_calls = tool_calls
        self._raises = raises
        self.calls: list = []

    def generate(self, messages, tools=None):
        self.calls.append((messages, tools))
        if self._raises:
            raise RuntimeError("provider down")

        class _Resp:
            pass

        r = _Resp()
        r.content = self._content
        r.tool_calls = self._tool_calls
        return r


def test_lane_answers_with_one_no_tools_call(monkeypatch):
    llm = _FakeLLM(content="Canberra, Boss.")
    monkeypatch.setattr(server.agent, "llm", llm)
    assert server._simple_question_answer("What is the capital of Australia?") == "Canberra, Boss."
    assert len(llm.calls) == 1
    assert llm.calls[0][1] is None, "the lane must attach NO tool schemas"


def test_lane_falls_through_on_no_lane_verdict(monkeypatch):
    monkeypatch.setattr(server.agent, "llm", _FakeLLM(content="NO_LANE"))
    assert server._simple_question_answer("What is the capital of Australia?") is None


def test_lane_falls_through_on_provider_error(monkeypatch):
    monkeypatch.setattr(server.agent, "llm", _FakeLLM(raises=True))
    assert server._simple_question_answer("What is the capital of Australia?") is None


def test_lane_falls_through_on_tool_calls(monkeypatch):
    monkeypatch.setattr(server.agent, "llm", _FakeLLM(content="", tool_calls=[{"name": "x"}]))
    assert server._simple_question_answer("What is the capital of Australia?") is None
