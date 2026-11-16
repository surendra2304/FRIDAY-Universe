"""TASK-FRD-002 regression tests: process termination has exactly one,
authorization-gated path, and every registered tool name is unique.

Background (live evidence, 2026-11-15): FRIDAY's production authorizer
(DefaultSecureAuthorizer, headless) auto-approves SAFE tools unconditionally,
and SENSITIVE tools too while autonomous/full-access mode is on. The
SAFE-classified ``system_control`` tool nevertheless exposed a working
``terminate_process`` action — an ungated duplicate of the DANGEROUS
``kill_process`` tool. These tests pin the fix so the bypass cannot return
silently.
"""
from friday.core.types import SafetyLevel
from friday.tools.builtin.system_control import SystemControlTool
from friday.tools.builtin.system_monitor import KillProcessTool


def test_system_control_schema_has_no_terminate_action():
    actions = SystemControlTool.parameters["properties"]["action"]["enum"]
    assert "terminate_process" not in actions
    assert set(actions) == {"list_processes", "system_status"}


def test_system_control_terminate_attempt_is_an_error():
    res = SystemControlTool().execute(action="terminate_process", process_name="csrss.exe")
    assert res.is_error
    assert "Unknown action" in res.content


def test_kill_process_remains_the_gated_terminator():
    tool = KillProcessTool()
    assert tool.name == "kill_process"
    assert tool.safety_level == SafetyLevel.DANGEROUS


def test_default_registry_tool_names_are_unique():
    """Build the production default registry on a stub agent and assert the
    registry did not silently overwrite one tool with another (the registry
    keys by name and only logs a warning on collision)."""
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
    registry = agent._create_default_registry()
    tools = registry.list_tools()
    names = [t.name for t in tools]
    assert len(names) == len(set(names)), (
        f"duplicate tool names registered: {sorted(n for n in set(names) if names.count(n) > 1)}"
    )
    # The full production surface as inventoried by TASK-FRD-002.
    # 90 at inventory time; 96 since the IG implementation wave registered
    # the six export-only tools (lead_generate, escrcpy_launch_plan,
    # escrcpy_automation, meeting_followup_create/list/decide) — see
    # test_ig_tool_registry_wiring.py.
    assert len(names) == 96
