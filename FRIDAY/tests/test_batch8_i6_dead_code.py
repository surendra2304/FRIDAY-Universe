"""Checklist I6 (MASTER_COMPLETION_CHECKLIST) — Batch 8, ZAI Agent 2.

Contracts locked here:
- I6 dead-code audit: the audit script runs and reports a bounded set of
  unrouted tools (regression gate — if a new tool is registered without
  routing, this test fails);
- I6 wiring: the 3 previously-unrouted tools (DictionaryTool, DraftGmailTool,
  OpenWhatsAppTool) are now keyword-routed → TOOL_EXECUTION;
- I6 no-regression: existing keyword sets still route correctly (the new
  sets are additive and don't hijack existing intents).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class TestDeadCodeAudit:
    """I6: the audit script runs and reports a bounded set of unrouted tools."""

    def test_audit_script_runs_and_reports(self):
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "audit_dead_code.py")],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "UNREACHABLE" in proc.stdout
        # The 3 previously-unrouted tools should now be reachable (wired).
        # The audit must report 0 unreachable after I6 wiring.
        assert "UNREACHABLE: 0" in proc.stdout, f"unexpected unreachable tools:\n{proc.stdout}"


class TestI6Wiring:
    """I6: the 3 previously-unrouted tools are now keyword-routed."""

    @pytest.fixture()
    def router(self):
        from friday.routing.capability_router import CapabilityRouter

        return CapabilityRouter()

    def test_dictionary_phrasing_reaches_tool(self, router):
        from friday.routing.capability_router import ExecutionCapabilityType

        d = router.route_request("define serendipity")
        tools = [t for c in d.candidate_evaluations for t in (c.required_tools or [])]
        assert "dictionary" in tools
        assert any(c.capability_type == ExecutionCapabilityType.TOOL_EXECUTION for c in d.candidate_evaluations)

    def test_gmail_draft_phrasing_reaches_tool(self, router):
        d = router.route_request("draft an email to the team about the launch")
        tools = [t for c in d.candidate_evaluations for t in (c.required_tools or [])]
        assert "send_gmail" in tools

    def test_whatsapp_open_phrasing_reaches_tool(self, router):
        d = router.route_request("open whatsapp and send a message to mom")
        tools = [t for c in d.candidate_evaluations for t in (c.required_tools or [])]
        assert "open_whatsapp" in tools

    def test_no_regression_on_existing_keyword_sets(self, router):
        def tools(text: str) -> list[str]:
            d = router.route_request(text)
            return [t for c in d.candidate_evaluations for t in (c.required_tools or [])]

        # The neighbors must still route correctly.
        assert "intelx_research" in tools("research the crypto market")
        assert "get_fleet_status" in tools("how's the fleet?")
        assert "web_fetch_summarize" in tools("summarize this page https://example.com/x")
        assert "stratex_portfolio" in tools("how's my portfolio")
        assert "price_alert" in tools("alert me when BTC > 100k")
        assert "vyralx_render" in tools("render the script as a short")

    def test_plain_chat_stays_conversational(self, router):
        from friday.routing.capability_router import ExecutionCapabilityType

        d = router.route_request("hey how are you doing today")
        for c in d.candidate_evaluations:
            if c.capability_type == ExecutionCapabilityType.TOOL_EXECUTION:
                for t in (c.required_tools or []):
                    assert t not in {"dictionary", "send_gmail", "open_whatsapp"}
