"""
Agents subsystem for Project FORGE.
"""

try:
    from app.agents.base import AgentState, BaseAgent
    from app.agents.registry import AgentCapability, AgentRegistry, agent_registry
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
except ImportError:
    # Allow importing modules from this package directly
    pass

__all__ = [
    "AgentCapability",
    "AgentRegistry",
    "AgentState",
    "ArchitectRole",
    "BackendEngineerRole",
    "BaseAgent",
    "CodeReviewerRole",
    "DebuggerRole",
    "DeveloperRole",
    "FrontendEngineerRole",
    "PlannerRole",
    "ReleaseEngineerRole",
    "SecurityReviewerRole",
    "TesterRole",
    "agent_registry",
]
