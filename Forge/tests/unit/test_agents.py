"""
Unit tests for Specialist Agent Roles, Model Provider Decoupling, and Permission Checking.
"""

from uuid import uuid4

import pytest

from app.agents.registry import agent_registry
from app.agents.roles import (
    ArchitectRole,
    BackendEngineerRole,
    CodeReviewerRole,
    DebuggerRole,
    DeveloperRole,
    FrontendEngineerRole,
    PlannerRole,
    ReleaseEngineerRole,
    SecurityReviewerRole,
    TesterRole,
)
from app.execution.engine import execution_engine
from app.execution.permissions import (
    PermissionDeniedError,
    ToolPermission,
    permission_manager,
)
from app.providers.direct import DirectProvider


def test_registry_registers_11_specialist_roles():
    capabilities = agent_registry.list_all()
    assert len(capabilities) >= 11

    expected_roles = [
        "planner",
        "codebase_analyzer",
        "architect",
        "developer",
        "frontend",
        "backend",
        "tester",
        "debugger",
        "security_reviewer",
        "code_reviewer",
        "release_engineer",
    ]
    registered_names = [c.name for c in capabilities]
    for r in expected_roles:
        assert r in registered_names


def test_agent_factory_instantiation():
    roles = [
        ("planner", PlannerRole),
        ("architect", ArchitectRole),
        ("developer", DeveloperRole),
        ("frontend", FrontendEngineerRole),
        ("backend", BackendEngineerRole),
        ("tester", TesterRole),
        ("debugger", DebuggerRole),
        ("security_reviewer", SecurityReviewerRole),
        ("code_reviewer", CodeReviewerRole),
        ("release_engineer", ReleaseEngineerRole),
    ]

    for role_name, expected_class in roles:
        agent = agent_registry.create_agent(role_name)
        assert isinstance(agent, expected_class)
        assert agent.role_name == role_name
        assert len(agent.system_prompt) > 10


def test_interchangeable_model_provider_swapping():
    agent = DeveloperRole()
    default_provider = agent.provider
    assert default_provider.model_name == "direct-developer"

    new_provider = DirectProvider(
        model_name="claude-3-opus-mock", mock_response="Custom mock output"
    )
    agent.set_provider(new_provider)

    assert agent.provider.model_name == "claude-3-opus-mock"


def test_agent_permission_allowlist_enforcement():
    # Planner should only have read permissions
    planner_perms = permission_manager.get_role_permissions("planner")
    assert ToolPermission.FS_READ in planner_perms
    assert ToolPermission.FS_WRITE not in planner_perms
    assert ToolPermission.TERMINAL_EXEC not in planner_perms

    # Check permission check methods
    permission_manager.check_permission("planner", ToolPermission.FS_READ)
    with pytest.raises(PermissionDeniedError, match="Security Violation"):
        permission_manager.check_permission("planner", ToolPermission.FS_WRITE)


@pytest.mark.asyncio
async def test_specialist_agent_step_execution():
    task_id = str(uuid4())
    architect = ArchitectRole()
    result = await architect.execute_step(
        task_id=task_id,
        node_title="Design Database Schema",
        context={"goal": "E-commerce platform"},
        engine=execution_engine,
    )
    assert result["status"] == "success"
    assert result["agent"] == "architect"
