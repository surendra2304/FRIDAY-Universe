"""TASK-ORCH-008 (checklist C13) + checklist I8 regression suite.

C13 — task status queries: "what happened to that IntelX task?" / "status of
task_xxx" must answer from the REAL unified TaskRecordStore (router + dispatch
bus records), never from invention. Locked here: the TaskStatusQueryTool
contract and the deterministic chat fast-path.

I8 — contacts fast-path hijack: "get IntelX to research crypto" was intercepted
by the contacts lookup because `is_contact_directive` matched any
"get/save/remember <words>" sentence. Locked here: delegation/memory/fleet
phrasings are NOT contact directives, while every documented contact form
still is.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe monorepo root
_CORE_SRC = REPO / "FRIDAY" / "apps" / "core" / "src"
if _CORE_SRC.is_dir() and str(_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(_CORE_SRC))

from friday_core.task_records import TaskRecordStore  # noqa: E402

from friday.tools.builtin.fleet_dispatch import (  # noqa: E402
    FLEET_AGENTS,
    normalize_agent,
)
from friday.tools.builtin.task_status_query import (  # noqa: E402
    TaskStatusQueryTool,
    _TASK_ID_RE,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _populated_store() -> TaskRecordStore:
    """A store with the full M1-trace-style lifecycle for two agents."""
    store = TaskRecordStore()
    store.create("task_aaa111bbb222", "Research crypto market highlights", "intelx")
    store.record_assignment("task_aaa111bbb222", "intelx", rationale="research keywords")
    store.record_dispatch("task_aaa111bbb222")
    store.record_completion(
        "task_aaa111bbb222", {"result": "BTC holding support; 3 citations found."}
    )
    store.create("task_ccc333ddd444", "Portfolio snapshot", "stratex")
    store.record_assignment("task_ccc333ddd444", "stratex", rationale="portfolio keywords")
    store.record_dispatch("task_ccc333ddd444")
    store.record_failure("task_ccc333ddd444", "HTTP 501: no evidence-backed handler")
    return store


# ---------------------------------------------------------------------------
# C13 — the tool
# ---------------------------------------------------------------------------

class TestTaskStatusQueryTool:
    def test_agent_question_returns_real_record(self):
        tool = TaskStatusQueryTool(store=_populated_store())
        result = tool.execute(query="what happened to the IntelX task?")
        assert not result.is_error
        assert "task_aaa111bbb222" in result.content
        assert "COMPLETED" in result.content
        assert "BTC holding support" in result.content  # the REAL result text
        assert "INTELX" in result.content.upper()

    def test_receipt_id_lookup(self):
        tool = TaskStatusQueryTool(store=_populated_store())
        result = tool.execute(query="status of task_ccc333ddd444")
        assert not result.is_error
        assert "FAILED" in result.content
        assert "HTTP 501" in result.content  # the REAL error text

    def test_failed_record_reports_error_not_success(self):
        tool = TaskStatusQueryTool(store=_populated_store())
        result = tool.execute(query="did the stratex task finish?")
        assert not result.is_error
        assert "FAILED" in result.content
        assert "COMPLETED" not in result.content

    def test_unknown_id_is_honest_not_fabricated(self):
        tool = TaskStatusQueryTool(store=_populated_store())
        result = tool.execute(query="status of task_0000000000")
        assert not result.is_error
        assert "no matching record" in result.content
        assert "task_0000000000 isn't in the ledger" in result.content

    def test_empty_store_says_ledger_empty_and_teaches_receipts(self):
        tool = TaskStatusQueryTool(store=TaskRecordStore())
        result = tool.execute(query="what happened to the intelx task?")
        assert not result.is_error
        assert "ledger is empty" in result.content
        # teaches how records are created + that receipts exist
        assert "assign" in result.content.lower()
        assert "receipt" in result.content.lower()

    def test_miss_reports_what_is_known(self):
        tool = TaskStatusQueryTool(store=_populated_store())
        result = tool.execute(query="status of task_0000000000")
        assert "2 task record(s)" in result.content
        assert "intelx (1)" in result.content and "stratex (1)" in result.content

    def test_empty_query_is_an_error_not_a_guess(self):
        tool = TaskStatusQueryTool(store=_populated_store())
        result = tool.execute(query="")
        assert result.is_error
        assert "Which task" in result.content

    def test_agent_filter_via_param(self):
        tool = TaskStatusQueryTool(store=_populated_store())
        result = tool.execute(query="my task", agent="stratex")
        assert "task_ccc333ddd444" in result.content

    def test_result_never_invented_when_store_raises(self):
        class ExplodingStore:
            def get(self, *_):
                raise RuntimeError("ledger unavailable")

            def list(self, *_a, **_k):
                raise RuntimeError("ledger unavailable")

            def report(self):
                raise RuntimeError("ledger unavailable")

        tool = TaskStatusQueryTool(store=ExplodingStore())
        result = tool.execute(query="status of task_aaa111bbb222")
        assert result.is_error
        assert "could not read the task records" in result.content
        assert "won't invent" in result.content

    def test_limit_bounds_agent_listing(self):
        store = _populated_store()
        for i in range(5):
            tid = f"task_f{i:02d}aaa0bbb1"
            store.create(tid, f"intelx research {i}", "intelx")
        tool = TaskStatusQueryTool(store=store)
        result = tool.execute(query="intelx tasks", agent="intelx", limit=3)
        assert "+3 more" in result.content

    def test_ist_timestamps_in_output(self):
        tool = TaskStatusQueryTool(store=_populated_store())
        result = tool.execute(query="status of task_aaa111bbb222")
        assert "IST" in result.content

    def test_lifecycle_trail_rendered(self):
        tool = TaskStatusQueryTool(store=_populated_store())
        result = tool.execute(query="status of task_aaa111bbb222")
        assert "submitted" in result.content
        assert "dispatched" in result.content


# ---------------------------------------------------------------------------
# C13 — the deterministic chat fast-path
# ---------------------------------------------------------------------------

class TestTaskStatusFastPathMatching:
    """The fast path fires ONLY on status questions with a receipt or agent+task."""

    @staticmethod
    def _matches(text: str) -> bool:
        """Reimplement the fast-path gate predicates 1:1 for contract tests."""
        low = text.lower().strip().rstrip(".!? ")
        id_hit = _TASK_ID_RE.search(low)
        import re

        status_marker = re.search(
            r"\b(?:status|what happened|happened|finished|finish|done|completed|"
            r"progress|result|outcome|any news|any update|check on|checking on)\b",
            low,
        )
        agent_reference = None
        m = re.search(
            r"\b(?:intelx|stratex|forge|sentinel|cortex|futuris|vyralx|memora|inference)\b"
            r"|\b(?:intelix|sentinal|viralx|vyral|memoria|inferance|futuristic)\b"
            r"[^.?!]*\b(?:task|assignment|job|dispatch|brief)\b"
            r"|\b(?:task|assignment|job|dispatch|brief)\b[^.?!]*"
            r"\b(?:intelx|stratex|forge|sentinel|cortex|futuris|vyralx|memora|inference)\b"
            r"|\b(?:task|assignment|job|dispatch|brief)\b[^.?!]*"
            r"\b(?:intelix|sentinal|viralx|vyral|memoria|inferance|futuristic)\b",
            low,
        )
        if m:
            for token in re.findall(r"[a-z]+", m.group(0)):
                agent_reference = normalize_agent(token) or agent_reference
                if agent_reference:
                    break
        if id_hit:
            return bool(status_marker) or len(low) <= 60
        return bool(status_marker and agent_reference)

    @pytest.mark.parametrize(
        "phrase",
        [
            "what happened to the IntelX task?",
            "status of task_aaa111bbb222",
            "did the stratex assignment finish?",
            "any news on the forge task",
            "what's the status of my intelx research brief",
            "task_aaa111bbb222",
            "check on the sentinal dispatch",  # spelling variant still resolves
        ],
    )
    def test_status_phrases_fire(self, phrase):
        assert self._matches(phrase), f"expected fast path to fire: {phrase!r}"

    @pytest.mark.parametrize(
        "phrase",
        [
            "assign a quick task to IntelX",           # delegation — not status
            "send this task to Sentinel: scan the logs",
            "have VyralX write a video script",       # delegation
            "how's the fleet?",                        # fleet-status path
            "research crypto and give me highlights",  # research path
            "what's IntelX",                           # bare agent question
            "hello friday",                            # greeting
            "update my portfolio",                     # portfolio path
        ],
    )
    def test_non_status_phrases_do_not_fire(self, phrase):
        assert not self._matches(phrase), f"fast path must NOT fire: {phrase!r}"


class TestFastPathWiring:
    def test_task_status_path_registered_in_cognitive_chain_before_delegation(self):
        source = (REPO / "FRIDAY" / "src" / "friday" / "agent" / "mixins" / "cognitive.py").read_text()
        status_pos = source.find("_task_status_fast_path")
        delegation_pos = source.find("_delegation_fast_path")
        assert status_pos != -1, "cognitive chain must call _task_status_fast_path"
        assert delegation_pos != -1
        assert status_pos < delegation_pos, (
            "task-status must run BEFORE delegation so status questions are "
            "never re-dispatched as new work"
        )

    def test_tool_registered_in_default_registry(self):
        source = (REPO / "FRIDAY" / "src" / "friday" / "agent" / "mixins" / "tools.py").read_text()
        assert "TaskStatusQueryTool()" in source, "agent registry must instantiate TaskStatusQueryTool"

    def test_prompt_rule_forbids_invented_status(self):
        source = (REPO / "FRIDAY" / "src" / "friday" / "agent" / "prompts.py").read_text()
        assert "task_status tool" in source
        assert "never invent a status" in source


# ---------------------------------------------------------------------------
# I8 — contacts matcher hijack
# ---------------------------------------------------------------------------

class TestContactsMatcherNoHijack:
    @pytest.fixture(scope="class")
    def matcher(self):
        from friday.devices.windows_friday import WindowsFridayController

        return WindowsFridayController.is_contact_directive

    HIJACK_CASES = [
        # The live delegation incident (checklist I8 reproduces test_delegation).
        "get IntelX to research crypto markets",
        "get intelx to do a research task",
        "have VyralX write a script about the campaign",
        "tell intelx to check the news",
        "assign a quick task to IntelX",
        "send this task to Sentinel",
        # Memory statements must not be eaten by contacts either.
        "remember that the market crashed today",
        "remember this: my favorite color is blue",
        # Fleet/portfolio/research paths stay reachable.
        "get the fleet status",
        "update the portfolio allocation",
        "search for the best crypto research",
        "show me the forecast results",
        # Casual chat with a contact-field word but no contact intent.
        "get me the number for tonight's game",
        "what is the phone number of the nearest pharmacy",  # general question, cognitive path
    ]

    CONTACT_CASES = [
        "contacts",
        "list contacts",
        "show contacts",
        "my contacts",
        "address book",
        "save contact John 9876543210",
        "save a contact Priya 9876543210",
        "add contact John john@example.com",
        "remember contact John 9876543210",
        "update contact John's phone +91 98765 43210",
        "delete contact John",
        "remove contact John",
        "lookup contact John",
        "find contact John",
        "search contact John",
        "get contact John",
        "show contact John",
        "who is John",
        "contact details of John",
        "contact John",
        "find John's phone",
        "find John's number",
        "get John's email",
        "John's phone is +91 9876543210",
        "John's email is john@example.com",
        "John is +91 9876543210",
    ]

    @pytest.mark.parametrize("phrase", HIJACK_CASES)
    def test_delegation_and_memory_not_hijacked(self, matcher, phrase):
        assert not matcher(object(), phrase), (
            f"checklist I8 regression: {phrase!r} was intercepted by the contacts matcher"
        )

    @pytest.mark.parametrize("phrase", CONTACT_CASES)
    def test_real_contact_forms_still_match(self, matcher, phrase):
        assert matcher(object(), phrase), (
            f"contact directive must still match its documented form: {phrase!r}"
        )


class TestAgentNameNormalization:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("IntelX", "intelx"),
            ("the IntelX agent", "intelx"),
            ("Sentinal", "sentinel"),       # documented typo
            ("ViralX", "vyralx"),
            ("memoria", "memora"),
            ("research", "intelx"),
            ("Rajesh", None),
            ("", None),
        ],
    )
    def test_normalize(self, raw, expected):
        assert normalize_agent(raw) == expected

    def test_nine_fleet_agents(self):
        assert len(FLEET_AGENTS) == 9
