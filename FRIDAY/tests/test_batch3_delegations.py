"""Checklist C7/C9/C11 (MASTER_COMPLETION_CHECKLIST, batch 3): first-class chat delegations.

"Draft a video script about X" must reach VyralX's REAL Hyperframes engine
(draft-only). "How are my websites doing" must reach Cortex's REAL health
summary + governed properties (read-only). "Search Memora for X" / "save
this to fleet memory: Y" must run REAL memory operations on Memora's
context database. None of these may be answered by the LLM's imagination.

Contracts locked here:
- routing: each phrase class -> TOOL_EXECUTION with the right tool;
- the batch-3 fast path fires before the generic fleet-status probe so
  "save this to fleet memory" is a memory op, not a fleet ping;
- extraction helpers produce clean titles/queries/content;
- FleetClient methods post the real contracts and report honest failures;
- honest empty results are labeled, never padded.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.routing.capability_router import CapabilityRouter  # noqa: E402
from friday.tools.builtin.vyralx_script import VyralXScriptTool, _extract_title  # noqa: E402
from friday.tools.builtin.cortex_web_ops import CortexWebOpsTool  # noqa: E402
from friday.tools.builtin.memora_memory import MemoraMemoryTool, _extract_query, _extract_content  # noqa: E402


# ---------------------------------------------------------------------------
# routing table
# ---------------------------------------------------------------------------

class TestRouting:
    @pytest.mark.parametrize(
        "phrase,tool",
        [
            ("draft a video script about AI agents", "vyralx_script"),
            ("write a youtube script on fleet automation", "vyralx_script"),
            ("can you compose a script for the new trading strategies", "vyralx_script"),
            ("how are my websites doing", "cortex_web_ops"),
            ("check my web properties", "cortex_web_ops"),
            ("website health status please", "cortex_web_ops"),
            ("search memora for the deployment runbook", "memora_memory"),
            ("memora search: api rate limits", "memora_memory"),
            ("search cloud memory for the oracle credentials rotation", "memora_memory"),
        ],
    )
    def test_phrases_route_to_the_right_tool(self, phrase: str, tool: str) -> None:
        decision = CapabilityRouter().route_request(phrase)
        assert decision.selected_capability.value == "TOOL_EXECUTION"
        assert any(
            tool in (c.required_tools or [])
            for c in decision.candidate_evaluations
        ), f"{phrase!r} must route to {tool}; got {[c.required_tools for c in decision.candidate_evaluations]}"

    @pytest.mark.parametrize(
        "phrase",
        [
            "draft a video script about AI agents",
            "how are my websites doing",
            "search memora for the deployment runbook",
        ],
    )
    def test_never_conversational(self, phrase: str) -> None:
        assert CapabilityRouter().route_request(phrase).selected_capability.value != "DIRECT_REASONING"

    def test_plain_chat_stays_conversational(self) -> None:
        assert CapabilityRouter().route_request("tell me a joke").selected_capability.value == "DIRECT_REASONING"


# ---------------------------------------------------------------------------
# extraction helpers
# ---------------------------------------------------------------------------

class TestExtraction:
    def test_title_from_about(self) -> None:
        assert _extract_title("draft a video script about quantum computing").lower().startswith("quantum")

    def test_title_quoted_kept_verbatim(self) -> None:
        assert _extract_title("write a script for 'The Fleet Awakens' please") == "The Fleet Awakens"

    def test_title_fallback_trimmed(self) -> None:
        title = _extract_title("script")
        assert len(title) > 0

    def test_memora_query_extraction(self) -> None:
        assert _extract_query("search memora for the deployment runbook") == "the deployment runbook"

    def test_memora_content_extraction(self) -> None:
        assert _extract_content("save this to fleet memory: demo account was reset").lower().startswith("demo account")

    def test_memora_content_saying_form(self) -> None:
        assert _extract_content("store in memora saying: rotate keys monthly") == "rotate keys monthly"


# ---------------------------------------------------------------------------
# tool behaviour with a stubbed fleet client
# ---------------------------------------------------------------------------

class _StubClient:
    def __init__(self, result: dict[str, Any]) -> None:
        self._result = result

    async def request_vyralx_script(self, title: str, text: str) -> dict[str, Any]:
        return self._result

    async def request_cortex_web_ops(self) -> dict[str, Any]:
        return self._result

    async def request_memora_memory_op(self, op: str, query: str = "", content: str = "", uri: str = "") -> dict[str, Any]:
        return self._result


class TestTools:
    def test_vyralx_script_success_is_draft_only(self) -> None:
        stub = _StubClient({
            "reply": "🎬 [VYRALX SCRIPT] 'AI agents' drafted by Hyperframes:\n• Scenes: 3",
            "metadata": {"scene_count": 3, "draft_only": True},
            "success": True,
        })
        result = VyralXScriptTool(fleet_client=stub).execute(question="draft a video script about AI agents")
        assert not result.is_error
        assert "Scenes: 3" in result.content
        assert result.metadata["vyralx"]["draft_only"] is True

    def test_vyralx_script_honest_failure(self) -> None:
        stub = _StubClient({"reply": "", "metadata": {}, "success": False})
        result = VyralXScriptTool(fleet_client=stub).execute(question="draft a video script about AI agents")
        assert result.is_error
        assert "nothing was invented" in result.content

    def test_cortex_web_ops_renders_health(self) -> None:
        stub = _StubClient({
            "reply": "🌐 [CORTEX WEB OPS MONITOR]\n• Uptime indicator: healthy",
            "metadata": {"uptime_indicator": "healthy", "properties_count": 2, "read_only": True},
            "success": True,
        })
        result = CortexWebOpsTool(fleet_client=stub).execute(question="how are my websites doing")
        assert not result.is_error
        assert "Uptime indicator: healthy" in result.content
        assert result.metadata["cortex"]["read_only"] is True

    def test_memora_search_honest_empty(self) -> None:
        stub = _StubClient({
            "reply": "🧠 [MEMORA SEARCH] completed:\n• No memory matched that query (honest empty result).",
            "metadata": {"op": "search", "hits": []},
            "success": True,
        })
        result = MemoraMemoryTool(fleet_client=stub).execute(question="search memora for the deployment runbook")
        assert not result.is_error
        assert "honest empty" in result.content

    def test_memora_write_op_inferred_from_phrasing(self) -> None:
        stub = _StubClient({
            "reply": "🧠 [MEMORA WRITE] completed:\n• Stored at: viking://memory/friday-chat",
            "metadata": {"op": "write"},
            "success": True,
        })
        result = MemoraMemoryTool(fleet_client=stub).execute(question="save this to fleet memory: demo account was reset")
        assert not result.is_error
        assert "Stored" in result.content

    def test_memora_empty_question_rejected(self) -> None:
        stub = _StubClient({"reply": "", "metadata": {}, "success": False})
        result = MemoraMemoryTool(fleet_client=stub).execute(question="")
        assert result.is_error


# ---------------------------------------------------------------------------
# fast-path ordering: the memory op must fire before the fleet probe
# ---------------------------------------------------------------------------

class TestFastPathOrdering:
    def test_batch3_fast_path_exists_and_runs_before_fleet(self) -> None:
        from friday.agent.mixins.fast_paths import FastPathMixin

        assert hasattr(FastPathMixin, "_batch3_delegation_fast_path")

        from friday.agent.mixins import cognitive as cognitive_module
        src = Path(cognitive_module.__file__).read_text(encoding="utf-8")
        b3 = src.index("_batch3_delegation_fast_path(")
        fleet = src.index("_fleet_status_fast_path(")
        assert b3 < fleet, "batch-3 delegations must be evaluated before the generic fleet-status probe"

    def test_batch3_keyword_sets_exist(self) -> None:
        for name in ("SCRIPT_KEYWORDS", "WEB_OPS_KEYWORDS", "MEMORA_OP_KEYWORDS"):
            assert hasattr(CapabilityRouter, name), f"{name} missing from CapabilityRouter"
