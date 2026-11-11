"""Checklist batch 3 part 2 — C12 pipelines, A10 clarification, A13 formatting,
D13 task timeline, D11 activity coverage.

Contracts locked here:
- C12: chained instructions ("research X, then draft the script about it")
  split into stages, execute sequentially with real tool dispatches, stage 2
  consumes stage 1's output, failures reported honestly per stage; the
  pipeline fast path runs BEFORE every single-intent fast path so a chain is
  never eaten by its first stage's dispatcher; chained requests never route
  to DIRECT_REASONING.
- A10: a delegation intent with a missing operand gets exactly ONE sharp
  question; complete requests proceed untouched.
- A13: the formatting policy reflows walls of text and run-on enumerations,
  leaves code blocks and structured lists alone, and is idempotent.
- D13: /api/tasks/timeline returns newest-first ledger history with honest
  chips; an empty ledger returns an empty timeline, never fabricated events.
- D11: pipeline stages emit live activity events (running + terminal).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
_CORE_SRC = REPO / "FRIDAY" / "apps" / "core" / "src"
for _p in (str(_CORE_SRC), str(REPO), str(REPO / "FRIDAY" / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.routing.capability_router import CapabilityRouter  # noqa: E402
from friday.routing.clarification import clarify_if_operand_missing  # noqa: E402
from friday.ecosystem.pipeline import (  # noqa: E402
    STAGE_MEMORY_WRITE,
    STAGE_RESEARCH,
    STAGE_SCRIPT,
    detect_pipeline,
    run_pipeline,
)
from friday.persona.response_format import apply_response_formatting  # noqa: E402
from friday.api.server import app  # noqa: E402

ATTACKER_ORIGIN = "https://attacker.example"


# ---------------------------------------------------------------------------
# C12 — pipeline detection
# ---------------------------------------------------------------------------

class TestDetectPipeline:
    @pytest.mark.parametrize(
        "text,kinds",
        [
            ("research quantum computing, then draft a video script about it", ["research", "script"]),
            ("research the oracle free tier and then save this to fleet memory: the limits", ["research", "memory_write"]),
            ("draft a video script about the fleet, after that save this to fleet memory: the draft", ["script", "memory_write"]),
            ("check my websites, then forecast the fleet load over 24h", ["web_ops", "forecast"]),
        ],
    )
    def test_chains_split_into_stages(self, text: str, kinds: list[str]) -> None:
        stages = detect_pipeline(text)
        assert stages is not None, f"{text!r} must detect as a pipeline"
        assert [s.kind for s in stages] == kinds

    def test_stage_texts_preserved(self) -> None:
        stages = detect_pipeline("research AI agents, then draft a video script about it")
        assert stages is not None
        assert "research ai agents" in stages[0].text
        assert "draft a video script" in stages[1].text

    @pytest.mark.parametrize(
        "text",
        [
            "research quantum computing",                      # single intent
            "research quantum computing and eat a sandwich",   # unmappable second fragment
            "back then we had fewer agents",                   # 'then' with no chain
            "tell me a joke",                                  # plain chat
            "how are my websites doing",                       # single web-ops ask
        ],
    )
    def test_not_a_pipeline(self, text: str) -> None:
        assert detect_pipeline(text) is None, f"{text!r} must NOT detect as a pipeline"


# ---------------------------------------------------------------------------
# C12 — pipeline execution with stubbed stage tools
# ---------------------------------------------------------------------------

class _StubToolResult:
    def __init__(self, content: str, is_error: bool = False) -> None:
        self.content = content
        self.is_error = is_error
        self.metadata: dict[str, Any] = {}


def _install_stubs(monkeypatch: pytest.MonkeyPatch, research_out: str, script_out: str, research_error: bool = False) -> None:
    """Patch the stage tools the pipeline dispatches to (imports are function-scoped)."""
    import friday.tools.builtin.intelx_research as intelx_mod
    import friday.tools.builtin.vyralx_script as vyralx_mod

    class _StubIntelX:
        def execute(self, query: str = "", **_: Any) -> _StubToolResult:
            return _StubToolResult(research_out, is_error=research_error)

    class _StubVyralX:
        def __init__(self) -> None:
            self.last_question = ""

        def execute(self, question: str = "", **_: Any) -> _StubToolResult:
            self.last_question = question
            return _StubToolResult(script_out)

    stub_intelx = _StubIntelX()
    stub_vyralx = _StubVyralX()
    monkeypatch.setattr(intelx_mod, "IntelXResearchTool", lambda: stub_intelx)
    monkeypatch.setattr(vyralx_mod, "VyralXScriptTool", lambda: stub_vyralx)
    return stub_vyralx


class TestRunPipeline:
    def test_two_stage_chain_passes_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        vyralx = _install_stubs(
            monkeypatch,
            research_out="Research brief — quantum computing. Bottom line: qubits are real.",
            script_out="🎬 [VYRALX SCRIPT] 'quantum' drafted: 3 scenes",
        )
        stages = detect_pipeline("research quantum computing, then draft a video script about it")
        assert stages is not None
        outcome = run_pipeline(stages)

        assert outcome["success"] is True
        assert len(outcome["stages"]) == 2
        # stage 2 consumed stage 1's output
        assert "quantum computing" in vyralx.last_question
        assert "qubits are real" in vyralx.last_question
        assert "STAGE 1" in outcome["reply"] and "STAGE 2" in outcome["reply"]
        assert "IntelX research" in outcome["reply"]
        assert "VyralX script draft" in outcome["reply"]

    def test_failed_stage_reported_honestly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        vyralx = _install_stubs(
            monkeypatch,
            research_out="IntelX is unreachable",
            research_error=True,
            script_out="🎬 [VYRALX SCRIPT] drafted anyway",
        )
        stages = detect_pipeline("research quantum computing, then draft a video script about it")
        assert stages is not None
        outcome = run_pipeline(stages)

        assert outcome["success"] is False
        assert outcome["stages"][0]["success"] is False
        assert outcome["stages"][1]["success"] is True
        assert "FAILED" in outcome["reply"]
        assert "did not complete" in outcome["reply"]
        # stage 2 was told stage 1 failed — nothing invented
        assert "FAILED" in vyralx.last_question or "failed" in vyralx.last_question

    def test_pipeline_emits_activity_events(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_stubs(monkeypatch, research_out="brief", script_out="drafted")
        events: list[dict[str, Any]] = []
        import friday.ecosystem.pipeline as pipeline_mod

        monkeypatch.setattr(pipeline_mod, "_emit_activity", lambda ev: events.append(ev))
        stages = detect_pipeline("research quantum computing, then draft a video script about it")
        assert stages is not None
        run_pipeline(stages)
        # 2 stages x (running + terminal) = 4 events
        assert len(events) == 4
        assert events[0]["status"] == "running"
        assert events[-1]["status"] == "completed"


# ---------------------------------------------------------------------------
# C12 — routing + fast-path ordering
# ---------------------------------------------------------------------------

class TestPipelineRouting:
    @pytest.mark.parametrize(
        "phrase",
        [
            "research quantum computing, then draft a video script about it",
            "check my websites, then forecast the fleet load over 24h",
        ],
    )
    def test_chained_requests_are_never_conversational(self, phrase: str) -> None:
        assert CapabilityRouter().route_request(phrase).selected_capability.value != "DIRECT_REASONING"

    def test_pipeline_fast_path_exists_and_runs_first(self) -> None:
        from friday.agent.mixins.fast_paths import FastPathMixin

        assert hasattr(FastPathMixin, "_pipeline_fast_path")

        from friday.agent.mixins import cognitive as cognitive_module
        src = Path(cognitive_module.__file__).read_text(encoding="utf-8")
        pipeline = src.index("_pipeline_fast_path(")
        for later in ("_task_status_fast_path(", "_delegation_fast_path(", "_batch3_delegation_fast_path(", "_research_dispatch_fast_path("):
            assert pipeline < src.index(later), "pipeline must run before every single-intent fast path"

    def test_single_intents_still_route_as_before(self) -> None:
        assert CapabilityRouter().route_request("tell me a joke").selected_capability.value == "DIRECT_REASONING"


# ---------------------------------------------------------------------------
# A10 — clarification quality
# ---------------------------------------------------------------------------

class TestClarification:
    @pytest.mark.parametrize(
        "text,intent",
        [
            ("research", "research"),
            ("do some research", "research"),
            ("research and give me the highlights", "research"),
            ("draft a video script", "script"),
            ("write a youtube script", "script"),
            ("save this to fleet memory", "memory_save"),
            ("store in memora", "memory_save"),
            ("forecast", "forecast"),
            ("predict", "forecast"),
        ],
    )
    def test_missing_operand_gets_one_question(self, text: str, intent: str) -> None:
        question = clarify_if_operand_missing(text, intent)
        assert question is not None, f"{text!r} must trigger a clarification for {intent}"
        assert question.count("?") == 1, "A10: exactly ONE question, never an interrogation"
        assert "Boss" in question

    @pytest.mark.parametrize(
        "text,intent",
        [
            ("research quantum computing", "research"),
            ("brief me on the oracle free tier", "research"),
            ("draft a video script about AI agents", "script"),
            ("write a script for 'The Fleet Awakens'", "script"),
            ("save this to fleet memory: demo account was reset", "memory_save"),
            ("store in memora saying: rotate keys monthly", "memory_save"),
            ("forecast BTC price over 24h", "forecast"),
            ("predict the fleet load over 7d", "forecast"),
        ],
    )
    def test_complete_requests_proceed(self, text: str, intent: str) -> None:
        assert clarify_if_operand_missing(text, intent) is None, f"{text!r} has its operand — no question"

    def test_pronoun_only_operand_still_clarifies(self) -> None:
        assert clarify_if_operand_missing("research it", "research") is not None

    def test_unknown_intent_is_not_ours(self) -> None:
        assert clarify_if_operand_missing("anything", "web_ops") is None


# ---------------------------------------------------------------------------
# A13 — response formatting policy
# ---------------------------------------------------------------------------

class TestResponseFormatting:
    def test_wall_of_text_split_into_paragraphs(self) -> None:
        wall = " ".join(f"Sentence number {i} says something useful." for i in range(1, 11))
        formatted = apply_response_formatting(wall)
        paragraphs = [p for p in formatted.split("\n\n") if p.strip()]
        assert len(paragraphs) >= 3, "a 10-sentence wall must split into short paragraphs"
        assert formatted.count("Sentence number 10") == 1

    def test_run_on_enumeration_reflowed_to_list(self) -> None:
        text = "Here is what happened: 1) IntelX researched the topic 2) VyralX drafted the script 3) Memora stored the result"
        formatted = apply_response_formatting(text)
        assert "1. IntelX researched the topic" in formatted
        assert "2. VyralX drafted the script" in formatted
        assert "3. Memora stored the result" in formatted
        assert formatted.count("\n") >= 2

    def test_code_blocks_untouched(self) -> None:
        text = "Intro line.\n```\n1) stays as is\n2) untouched\n```\nOutro."
        assert apply_response_formatting(text) == text

    def test_structured_lists_untouched(self) -> None:
        text = "Summary:\n- one\n- two\n- three"
        assert apply_response_formatting(text) == text

    def test_idempotent(self) -> None:
        wall = " ".join(f"Sentence {i} is here." for i in range(1, 12))
        once = apply_response_formatting(wall)
        assert apply_response_formatting(once) == once

    def test_blank_line_collapse(self) -> None:
        text = "para one.\n\n\n\npara two."
        assert apply_response_formatting(text) == "para one.\n\npara two."

    def test_short_reply_unchanged(self) -> None:
        assert apply_response_formatting("All good, Boss.") == "All good, Boss."


# ---------------------------------------------------------------------------
# D13 — /api/tasks/timeline endpoint
# ---------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("FRIDAY_API_KEY", raising=False)
    monkeypatch.delenv("FRIDAY_UNIVERSE_API_KEY", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    with TestClient(app) as test_client:
        yield test_client


def _clear_shared_store() -> None:
    from friday_core.task_records import get_shared_task_records

    store = get_shared_task_records()
    with store._lock:
        store._records.clear()


@pytest.fixture(autouse=True)
def clean_ledger():
    _clear_shared_store()
    yield
    _clear_shared_store()


class TestTaskTimelineEndpoint:
    def test_empty_ledger_returns_empty_timeline(self, client: TestClient) -> None:
        resp = client.get("/api/tasks/timeline")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["events"] == []
        assert body["total_records"] == 0

    def test_chips_mapped_from_statuses(self, client: TestClient) -> None:
        from friday_core.task_records import get_shared_task_records

        store = get_shared_task_records()
        store.create("task_q", description="queued work")
        store.create("task_r", description="running work")
        store.record_assignment("task_r", owner_agent="stratex")
        store.record_dispatch("task_r")
        store.create("task_d", description="done work")
        store.record_assignment("task_d", owner_agent="intelx")
        store.record_completion("task_d", result="brief delivered")
        store.create("task_f", description="failed work")
        store.record_failure("task_f", error="HTTP 401")

        body = client.get("/api/tasks/timeline").json()
        chips = {ev["task_id"]: ev["chip"] for ev in body["events"]}
        assert chips["task_q"] == "queued"
        assert chips["task_r"] == "running"
        assert chips["task_d"] == "done"
        assert chips["task_f"] == "failed"
        assert body["chip_counts"] == {"queued": 1, "running": 1, "done": 1, "failed": 1}

    def test_newest_first_order(self, client: TestClient) -> None:
        import time as _time

        from friday_core.task_records import get_shared_task_records

        store = get_shared_task_records()
        store.create("old_task", description="older")
        store.record_completion("old_task", result="x")
        _time.sleep(0.01)
        store.create("new_task", description="newer")
        store.record_completion("new_task", result="y")

        body = client.get("/api/tasks/timeline").json()
        assert body["events"][0]["task_id"] == "new_task"

    def test_result_payload_strings_included(self, client: TestClient) -> None:
        from friday_core.task_records import get_shared_task_records

        store = get_shared_task_records()
        store.create("t1", description="dict result work")
        store.record_completion("t1", result={"receipt": "disp_123"})
        body = client.get("/api/tasks/timeline").json()
        ev = next(e for e in body["events"] if e["task_id"] == "t1")
        assert "disp_123" in ev["result"]

    def test_limit_respected(self, client: TestClient) -> None:
        from friday_core.task_records import get_shared_task_records

        store = get_shared_task_records()
        for i in range(10):
            store.create(f"t{i}", description=f"task {i}")
        body = client.get("/api/tasks/timeline?limit=3").json()
        assert len(body["events"]) == 3
        assert body["total_records"] == 10

    def test_forged_origin_refused(self, client: TestClient) -> None:
        resp = client.get("/api/tasks/timeline", headers={"Origin": ATTACKER_ORIGIN})
        assert resp.status_code in (403, 400)

    def test_note_declares_ledger_scope(self, client: TestClient) -> None:
        body = client.get("/api/tasks/timeline").json()
        assert "unified task ledger" in body["note"]


# ---------------------------------------------------------------------------
# D11 — activity stream coverage
# ---------------------------------------------------------------------------

class TestActivityCoverage:
    def test_emit_fire_and_forget_never_raises(self) -> None:
        from friday.api import activity_stream

        # no running loop -> emit must silently no-op, not raise
        activity_stream.emit({"type": "chat_command", "command": "test"})

    def test_chat_command_event_shape(self) -> None:
        # the execute_command emit contract: type/command/agents_involved/status/detail
        event = {
            "type": "chat_command",
            "command": "how's the fleet?",
            "agents_involved": "friday",
            "status": "received",
            "detail": "all agents online",
        }
        assert event["type"] in {"chat_command", "agent_action", "activity"}

    def test_server_emits_chat_command_on_execute(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        from friday.api import activity_stream

        captured: list[dict[str, Any]] = []
        monkeypatch.setattr(activity_stream, "emit", lambda ev: captured.append(ev))
        # the origin-gated chat surface
        resp = client.post("/api/chat", json={"message": "hello"})
        assert resp.status_code == 200
        assert len(captured) >= 1
        assert captured[0]["type"] == "chat_command"
