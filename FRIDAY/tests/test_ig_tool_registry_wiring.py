"""IG implementation wave — live-registry wiring regression tests.

Background (supervisor AUDIT-2, 2026-11-16): three wave-2 features were
marked IMPLEMENTED with complete modules, tools and unit tests, but their
tools were only *exported* from ``friday.tools.builtin`` — never registered
in the production agent's live tool registry
(``agent/mixins/tools.py::_create_default_registry()``, consumed at
``agent.py``) and exposed on no API route. In a normal session the model
could not call them; their only execution path was the ToolCatalogue scan
in ``cognition/offline.py``.

These tests build the production registry exactly the way
``test_frd002_tool_gates.py`` does (stub agent through
``ToolExecutionMixin._create_default_registry``) and assert each tool is
present under its production name, bound to the right class. Removing any
``registry.register(...)`` line for these tools fails this file — that is
the point.
"""

from friday.tools.builtin.escrcpy_control import (
    EscrcpyAutomationTool,
    EscrcpyLaunchPlanTool,
)
from friday.tools.builtin.lead_gen_tools import LeadGenerateTool
from friday.tools.builtin.meeting_followup_tools import (
    MeetingFollowUpCreateTool,
    MeetingFollowUpDecideTool,
    MeetingFollowUpListTool,
)

EXPECTED = {
    # TASK-IG2-FRD-03 — delegated lead generation.
    "lead_generate": LeadGenerateTool,
    # TASK-IG2-LAP-01 — Escrcpy phone control.
    "escrcpy_launch_plan": EscrcpyLaunchPlanTool,
    "escrcpy_automation": EscrcpyAutomationTool,
    # TASK-IG2-FRD-04 — post-meeting follow-up automation.
    "meeting_followup_create": MeetingFollowUpCreateTool,
    "meeting_followup_list": MeetingFollowUpListTool,
    "meeting_followup_decide": MeetingFollowUpDecideTool,
}


def _production_registry():
    from friday.agent.mixins.tools import ToolExecutionMixin

    class _StubMemory:
        def search(self, *a, **k):
            return []

    agent = ToolExecutionMixin.__new__(ToolExecutionMixin)
    agent.memory = _StubMemory()
    agent.skill_registry = None
    agent.authorizer = None
    agent.llm_provider = None
    agent.provider = None
    return agent._create_default_registry()


def test_ig_tools_are_in_the_live_registry():
    registry = _production_registry()
    names = {t.name for t in registry.list_tools()}
    missing = sorted(set(EXPECTED) - names)
    assert not missing, (
        f"tools exported from friday.tools.builtin but missing from the "
        f"production registry: {missing}"
    )


def test_ig_tools_resolve_to_the_right_classes():
    registry = _production_registry()
    for name, cls in EXPECTED.items():
        tool = registry.get(name)
        assert tool is not None, f"{name} not resolvable from the registry"
        assert isinstance(tool, cls), (
            f"{name} resolved to {type(tool).__name__}, expected {cls.__name__}"
        )
